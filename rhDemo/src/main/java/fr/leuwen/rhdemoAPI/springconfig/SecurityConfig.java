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

    // URL Keycloak extraite automatiquement depuis spring.security.oauth2.client.provider.keycloak.authorization-uri
    @org.springframework.beans.factory.annotation.Value("${spring.security.oauth2.client.provider.keycloak.authorization-uri:}")
    private String keycloakAuthorizationUri;

    // Flag Secure pour les cookies (activé via application-ephemere.yml et application-stagingkub.yml)
    @org.springframework.beans.factory.annotation.Value("${server.servlet.session.cookie.secure:false}")
    private boolean cookieSecureFlag;

    // Autowired par défaut avec Spring Boot
    public SecurityConfig(GrantedAuthoritiesKeyCloakMapper keycloakmapper) {
        this.keycloakmapper = keycloakmapper;
    }

    /**
     * Extrait l'URL de base de Keycloak depuis l'URI d'autorisation OAuth2.
     * Exemple: "https://keycloak.ephemere.local/realms/..." → "https://keycloak.ephemere.local"
     */
    private String extractKeycloakBaseUrl() {
        if (keycloakAuthorizationUri == null || keycloakAuthorizationUri.isEmpty()) {
            return "";
        }
        try {
            java.net.URI uri = java.net.URI.create(keycloakAuthorizationUri);
            // Vérifier que l'URI est valide (scheme et host non null)
            if (uri.getScheme() == null || uri.getHost() == null) {
                return "";
            }
            return uri.getScheme() + "://" + uri.getHost() + (uri.getPort() > 0 && uri.getPort() != 80 && uri.getPort() != 443 ? ":" + uri.getPort() : "");
        } catch (Exception _) {
            return "";
        }
    }

    /**
     * Construit les directives Content-Security-Policy (CSP) de manière dynamique.
     *
     * Cette méthode génère une politique CSP adaptée à l'environnement en extrayant
     * automatiquement l'URL de Keycloak depuis la configuration OAuth2.
     *
     * Directives expliquées:
     * - default-src 'self': Par défaut, n'autorise que les ressources du même origine
     * - script-src 'self': Scripts locaux uniquement (SÉCURISÉ - pas de 'unsafe-inline' ni 'unsafe-eval')
     * - style-src 'self': Styles locaux uniquement (SÉCURISÉ - pas de 'unsafe-inline')
     * - img-src 'self' data: https:: Images locales + data URIs
     * - font-src 'self' data:: Polices locales + data URIs
     * - connect-src: Connexions AJAX vers l'app et Keycloak (extrait dynamiquement de la config)
     * - frame-src 'self': iframes uniquement du même origine
     * - frame-ancestors 'none': Empêche l'embedding dans une iframe (protection clickjacking)
     * - form-action: Soumission de formulaires vers l'app et Keycloak (pour login OAuth2)
     * - object-src 'none': Interdit les plugins obsolètes (Flash, Java applets)
     * - base-uri 'self': Empêche l'injection de balises <base>
     * - media-src 'self': Ressources média (audio/vidéo) uniquement locales
     * - manifest-src 'self': Manifest PWA uniquement local
     * - worker-src 'self': Web Workers et Service Workers uniquement locaux
     *
     * Protection renforcée:
     * Tous les scripts et styles ont été externalisés dans des fichiers séparés:
     * - frontend/public/js/error-handler.js: Gestion d'erreurs Vue.js (anciennement inline)
     * - frontend/public/css/loading.css: Styles du placeholder de chargement (anciennement inline)
     * - src/main/resources/static/css/error.css: Styles de la page d'erreur (anciennement inline)
     *
     * Cette configuration offre une protection maximale contre:
     * - Injection de scripts malveillants (XSS)
     * - Injection de styles malveillants
     * - Exécution de code inline non autorisé
     *
     * @return Les directives CSP sous forme de String
     */
    private String buildCspDirectives() {
        String keycloakBaseUrl = extractKeycloakBaseUrl();

        StringBuilder csp = new StringBuilder();
        csp.append("default-src 'self'; ");
        // Scripts: Tous externalisés - plus besoin de 'unsafe-inline' ni 'unsafe-eval'
        csp.append("script-src 'self'; ");
        // Styles: Tous externalisés - plus besoin de 'unsafe-inline'
        csp.append("style-src 'self'; ");
        csp.append("img-src 'self' data:; ");  // data: pour les images base64
        csp.append("font-src 'self' data:; ");

        // Connexions AJAX: application + Keycloak (si configuré)
        if (!keycloakBaseUrl.isEmpty()) {
            csp.append("connect-src 'self' ").append(keycloakBaseUrl).append("; ");
        } else {
            csp.append("connect-src 'self'; ");
        }

        csp.append("frame-ancestors 'none'; ");

        // Soumission de formulaires: application + Keycloak (pour login OAuth2)
        if (!keycloakBaseUrl.isEmpty()) {
            csp.append("form-action 'self' ").append(keycloakBaseUrl).append("; ");
        } else {
            csp.append("form-action 'self'; ");
        }

        csp.append("object-src 'none'; ");
        csp.append("base-uri 'self'; ");
        // Directives supplémentaires pour conformité sécurité (Trivy/ZAP)
        csp.append("media-src 'self'; ");       // Audio/vidéo uniquement locaux
        csp.append("manifest-src 'self'; ");    // PWA manifest uniquement local
        csp.append("worker-src 'self'");        // Web/Service Workers uniquement locaux
        // Note: upgrade-insecure-requests retiré car il force HTTPS pour TOUTES les ressources
        // ce qui peut causer des problèmes en développement local (HTTP)

        return csp.toString();
    }

    /**
     * Configure le repository de tokens CSRF avec les flags de sécurité appropriés.
     *
     * Le flag Secure est activé uniquement dans les environnements avec HTTPS (ephemere, stagingkub)
     * via la propriété server.servlet.session.cookie.secure définie dans les fichiers de profil.
     *
     * @return Le repository CSRF configuré
     */
    private CookieCsrfTokenRepository createCsrfTokenRepository() {
        //pas de HttpOnly car ce cookie doit être lu par le js pourqu'il puisse renvoyer le token attendu par le serveur
        CookieCsrfTokenRepository repository = CookieCsrfTokenRepository.withHttpOnlyFalse();// NOSONAR
        // Applique le même flag Secure que les cookies de session (configuré par profil)
        repository.setCookieCustomizer(cookieCustomizer -> cookieCustomizer.secure(cookieSecureFlag));
        return repository;
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http, LogoutSuccessHandler logoutSuccessHandler) {
	http
	// Active la protection CSRF avec cookie accessible en JavaScript
	.csrf(csrf -> csrf
	    .csrfTokenRepository(createCsrfTokenRepository()) //NOSONAR - Ce cookie doit être lu par le js pour qu'il puisse renvoyer le token attendu par le serveur
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
	        .policyDirectives(buildCspDirectives())
	    )
	)
	.authorizeHttpRequests(auth -> ( auth
            .requestMatchers("/error*","/logout","/api-docs").permitAll()
            // Endpoints actuator health accessibles sans authentification (pour Kubernetes probes)
                    .requestMatchers("/actuator/health", "/actuator/health/**").permitAll()
            // Endpoint prometheus accessible sans authentification (scraping Prometheus interne, protégé par NetworkPolicy)
                    .requestMatchers("/actuator/prometheus").permitAll()
            // Autres endpoints actuator réservés aux admins
            .requestMatchers("/actuator/**").hasRole("admin")
            .requestMatchers("/front")).hasAnyRole("consult","MAJ")
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
