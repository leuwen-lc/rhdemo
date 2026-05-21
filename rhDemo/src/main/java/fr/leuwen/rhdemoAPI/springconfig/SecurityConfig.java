package fr.leuwen.rhdemoAPI.springconfig;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
// Note: OidcClientInitiatedLogoutSuccessHandler remplacé par KeycloakLogoutSuccessHandler
// car il nécessite issuer-uri pour découvrir end_session_endpoint, ce qui ne fonctionne pas
// quand le pod ne peut pas résoudre l'URL externe de Keycloak
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.logout.LogoutSuccessHandler;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.security.web.csrf.CsrfTokenRequestAttributeHandler;
import org.springframework.security.web.csrf.CsrfTokenRequestHandler;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.function.Supplier;

@Configuration
@EnableWebSecurity
//Permet de positionner des annotations de type @PreAuthorize("hasRole('rolexx')")
@EnableMethodSecurity
@Profile("!test") // Désactive cette configuration pour le profil "test"
public class SecurityConfig {
    private final GrantedAuthoritiesKeyCloakMapper keycloakmapper;
    private final CspPolicyBuilder cspPolicyBuilder;

    @org.springframework.beans.factory.annotation.Value("${spring.security.oauth2.client.provider.keycloak.authorization-uri:}")
    private String keycloakAuthorizationUri;

    public SecurityConfig(GrantedAuthoritiesKeyCloakMapper keycloakmapper, CspPolicyBuilder cspPolicyBuilder) {
        this.keycloakmapper = keycloakmapper;
        this.cspPolicyBuilder = cspPolicyBuilder;
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http, LogoutSuccessHandler logoutSuccessHandler) {
	http
	// Active la protection CSRF avec cookie accessible en JavaScript
	.csrf(csrf -> csrf
	    .csrfTokenRepository(cspPolicyBuilder.createCsrfTokenRepository()) //NOSONAR - Ce cookie doit être lu par le js pour qu'il puisse renvoyer le token attendu par le serveur
	    .csrfTokenRequestHandler(new SpaCsrfTokenRequestHandler())
	    // Ignorer CSRF pour les endpoints publics et actuator
	    .ignoringRequestMatchers("/error*", "/api-docs", "/actuator/**") //NOSONAR - désactivation CSRF pour pages spécifiques peu sensibles ou modules annexes prets à l'emploi
	)
	// Configuration des headers de sécurité
	.headers(headers -> headers
	    // Désactiver X-Frame-Options car géré par nginx (évite les headers dupliqués)
	    .frameOptions(frame -> frame.disable())
	    // Désactiver HSTS car géré par nginx (évite les headers dupliqués)
	    .httpStrictTransportSecurity(hsts -> hsts.disable())
	    // Configurer Content-Security-Policy (CSP) pour protéger contre XSS et injections
	    .contentSecurityPolicy(csp -> csp
	        .policyDirectives(cspPolicyBuilder.buildCspDirectives())
	    )
	)
	.authorizeHttpRequests(auth -> auth
	        .requestMatchers("/error*", "/logout").permitAll()
	        // Endpoints actuator health accessibles sans authentification (pour Kubernetes probes)
	        .requestMatchers("/actuator/health", "/actuator/health/**").permitAll()
	        // Endpoint prometheus accessible sans authentification (scraping Prometheus interne, protégé par NetworkPolicy)
	        .requestMatchers("/actuator/prometheus").permitAll()
	        // Autres endpoints actuator réservés aux admins
	        .requestMatchers("/actuator/**").hasRole("admin")
	        // Documentation OpenAPI/Swagger restreinte aux admins (désactivée en stagingkub via springdoc config)
	        .requestMatchers("/api-docs/**").hasRole("admin")
	        .requestMatchers("/front").hasAnyRole("consult", "MAJ")
	        // Pour les requêtes REST les filtres de roles sont directement au niveau des méthodes du controleur
	        .anyRequest().authenticated())
	.oauth2Login(oauth2 -> oauth2
		    .userInfoEndpoint(userInfo -> userInfo
			        .userAuthoritiesMapper(this.keycloakmapper)))
	.logout(logout -> logout 
		.logoutUrl("/logout")
	        .logoutSuccessHandler(logoutSuccessHandler))
        ;
	return http.build();
    }
    
    /**
     * Logout handler personnalisé pour Keycloak.
     *
     * Utilise KeycloakLogoutSuccessHandler au lieu de OidcClientInitiatedLogoutSuccessHandler
     * car ce dernier nécessite la découverte de end_session_endpoint via issuer-uri,
     * ce qui ne fonctionne pas quand le pod ne peut pas résoudre l'URL externe de Keycloak.
     *
     * Le handler personnalisé dérive l'URL de logout depuis authorization-uri
     * en remplaçant /auth par /logout, ce qui fonctionne pour tous les environnements.
     */
    @Bean
    public LogoutSuccessHandler keycloakLogoutSuccessHandler() {
        return new KeycloakLogoutSuccessHandler(keycloakAuthorizationUri, "{baseUrl}/");
    }
}

/**
 * Gestionnaire de requêtes CSRF personnalisé pour les applications SPA.
 * Ce gestionnaire garantit que le token CSRF est toujours chargé et envoyé dans le cookie,
 * ce qui est essentiel pour les SPA qui lisent le token depuis le cookie XSRF-TOKEN.
 * 
 * Comportements clés :
 * 1. Force la création du token sur TOUTES les requêtes (y compris GET) en appelant csrfToken.get()
 * 2. Utilise une validation de token simple (NON encodé en XOR) compatible avec CookieCsrfTokenRepository
 * 3. Rend le token disponible en tant qu'attribut de requête pour le rendu
 */
final class SpaCsrfTokenRequestHandler implements CsrfTokenRequestHandler {
    private final CsrfTokenRequestAttributeHandler delegate = new CsrfTokenRequestAttributeHandler();

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, Supplier<CsrfToken> csrfToken) {
        // CRITIQUE : Force la génération du token en appelant get() explicitement
        // Cela garantit que CookieCsrfTokenRepository crée et envoie le cookie XSRF-TOKEN sur TOUTES les requêtes
        // Sinon le cookie n'est envoyé que sur les requêtes de mutation (POST, PUT, DELETE)
        // Et il n'existe pas avant la première requête de mutation --> erreur
        CsrfToken token = csrfToken.get();
        
        // Puis délègue au gestionnaire standard pour rendre le token disponible en tant qu'attribut de requête
        this.delegate.handle(request, response, () -> token);
    }

    @Override
    public String resolveCsrfTokenValue(HttpServletRequest request, CsrfToken csrfToken) {
        // Le client envoie le token depuis le cookie XSRF-TOKEN dans l'en-tête X-XSRF-TOKEN
        // Utilise la résolution standard (comparaison de token simple, pas de décodage XOR)
        return this.delegate.resolveCsrfTokenValue(request, csrfToken);
    }
}
