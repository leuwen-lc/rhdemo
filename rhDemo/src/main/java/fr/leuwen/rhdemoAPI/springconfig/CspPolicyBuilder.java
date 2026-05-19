package fr.leuwen.rhdemoAPI.springconfig;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.stereotype.Component;

/**
 * Construit la politique Content-Security-Policy (CSP) et le repository CSRF Cookie
 * à partir de la configuration OAuth2 et du flag Secure des cookies.
 *
 * Extrait de SecurityConfig pour permettre :
 * - Des tests unitaires sans réflexion ni démarrage du contexte Spring.
 * - La réutilisation par TestSecurityConfig afin d'éviter la duplication entre
 *   la CSP de production et celle des tests (qui avait dérivé).
 */
@Component
public class CspPolicyBuilder {

    private static final Logger log = LoggerFactory.getLogger(CspPolicyBuilder.class);

    private final String keycloakAuthorizationUri;
    private final boolean cookieSecureFlag;

    public CspPolicyBuilder(
            @Value("${spring.security.oauth2.client.provider.keycloak.authorization-uri:}") String keycloakAuthorizationUri,
            @Value("${server.servlet.session.cookie.secure:false}") boolean cookieSecureFlag) {
        this.keycloakAuthorizationUri = keycloakAuthorizationUri;
        this.cookieSecureFlag = cookieSecureFlag;
    }

    /**
     * Extrait l'URL de base de Keycloak depuis l'URI d'autorisation OAuth2.
     * Exemple: "https://keycloak.ephemere.local/realms/..." → "https://keycloak.ephemere.local"
     */
    public String extractKeycloakBaseUrl() {
        if (keycloakAuthorizationUri == null || keycloakAuthorizationUri.isBlank()) {
            return "";
        }
        try {
            java.net.URI uri = java.net.URI.create(keycloakAuthorizationUri);
            if (uri.getScheme() == null || uri.getHost() == null) {
                return "";
            }
            return uri.getScheme() + "://" + uri.getHost()
                    + (uri.getPort() > 0 && uri.getPort() != 80 && uri.getPort() != 443 ? ":" + uri.getPort() : "");
        } catch (IllegalArgumentException e) {
            log.warn("URI Keycloak invalide '{}', connect-src dégradé : {}", keycloakAuthorizationUri, e.getMessage());
            return "";
        }
    }

    /**
     * Construit les directives Content-Security-Policy (CSP) de manière dynamique.
     * Aucune directive 'unsafe-inline' ni 'unsafe-eval'.
     */
    public String buildCspDirectives() {
        String keycloakBaseUrl = extractKeycloakBaseUrl();

        StringBuilder csp = new StringBuilder();
        csp.append("default-src 'self'; ");
        csp.append("script-src 'self'; ");
        csp.append("style-src 'self'; ");
        csp.append("img-src 'self' data:; ");
        csp.append("font-src 'self' data:; ");

        if (!keycloakBaseUrl.isEmpty()) {
            csp.append("connect-src 'self' ").append(keycloakBaseUrl).append("; ");
        } else {
            csp.append("connect-src 'self'; ");
        }

        csp.append("frame-ancestors 'none'; ");

        if (!keycloakBaseUrl.isEmpty()) {
            csp.append("form-action 'self' ").append(keycloakBaseUrl).append("; ");
        } else {
            csp.append("form-action 'self'; ");
        }

        csp.append("object-src 'none'; ");
        csp.append("base-uri 'self'; ");
        csp.append("media-src 'self'; ");
        csp.append("manifest-src 'self'; ");
        csp.append("worker-src 'self'");

        return csp.toString();
    }

    /**
     * Crée le repository de tokens CSRF (cookie XSRF-TOKEN lisible par JS, flag Secure piloté par profil).
     */
    public CookieCsrfTokenRepository createCsrfTokenRepository() {
        CookieCsrfTokenRepository repository = CookieCsrfTokenRepository.withHttpOnlyFalse();// NOSONAR
        repository.setCookieCustomizer(cookieCustomizer -> cookieCustomizer
                .secure(cookieSecureFlag)
                .sameSite("Strict"));
        return repository;
    }
}
