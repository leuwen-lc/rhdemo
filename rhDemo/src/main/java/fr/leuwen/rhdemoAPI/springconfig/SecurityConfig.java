package fr.leuwen.rhdemoAPI.springconfig;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.oauth2.client.oidc.web.logout.OidcClientInitiatedLogoutSuccessHandler;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.logout.LogoutSuccessHandler;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
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

    // Autowired par défaut avec Spring Boot
    public SecurityConfig(GrantedAuthoritiesKeyCloakMapper keycloakmapper) {
        this.keycloakmapper = keycloakmapper;
    }
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http, LogoutSuccessHandler logoutSuccessHandler) throws Exception {
	http 
	// Active la protection CSRF avec cookie accessible en JavaScript
	.csrf(csrf -> csrf
	    .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse()) //NOSONAR - Ce cookie doit être lu par le js pour qu'il puisse renvoyer le token attendu par le serveur
	    .csrfTokenRequestHandler(new SpaCsrfTokenRequestHandler())
	    // Ignorer CSRF pour les endpoints publics et actuator
	    .ignoringRequestMatchers("/who", "/error*", "/api-docs", "/actuator/**") //NOSONAR - désactivation CSRF pour pages spécifiques peu sensibles ou modules annexes prets à l'emploi
	)
	.authorizeHttpRequests(auth -> ( auth
            .requestMatchers("/who","/error*","/logout","/api-docs").permitAll()
            .requestMatchers("/front")).hasAnyRole("consult","MAJ")
            .requestMatchers("/actuator/**").hasRole("admin")
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
    
    //Logout handler spécifique appelé par Spring.
    @Bean
    public LogoutSuccessHandler oidcLogoutSuccessHandler(ClientRegistrationRepository clientRegistrationRepository) {
        OidcClientInitiatedLogoutSuccessHandler successHandler =
            new OidcClientInitiatedLogoutSuccessHandler(clientRegistrationRepository);
        successHandler.setPostLogoutRedirectUri("{baseUrl}/"); // optionnel, page de retour
        return successHandler;
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
