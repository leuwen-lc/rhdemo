package fr.leuwen.rhdemoAPI.springconfig;

import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.client.authentication.OAuth2AuthenticationToken;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.security.web.authentication.logout.LogoutSuccessHandler;
import org.springframework.web.util.UriComponentsBuilder;

import java.io.IOException;

/**
 * Handler de logout personnalisé pour Keycloak.
 *
 * Ce handler résout le problème où Spring Security ne peut pas découvrir
 * l'endpoint de logout Keycloak (end_session_endpoint) car:
 * - L'issuer-uri ne peut pas être configuré (le pod ne peut pas résoudre l'URL externe)
 * - Le handler standard OidcClientInitiatedLogoutSuccessHandler nécessite cette découverte
 *
 * Solution: On dérive l'URL de logout depuis l'authorization-uri configuré.
 * L'authorization-uri se termine par ".../protocol/openid-connect/auth"
 * L'end_session_endpoint se termine par ".../protocol/openid-connect/logout"
 *
 * Ce handler est générique et fonctionne pour tous les environnements
 * (dev local, ephemere, stagingkub) car il utilise l'authorization-uri
 * qui est toujours configuré.
 */
public class KeycloakLogoutSuccessHandler implements LogoutSuccessHandler {

    private static final Logger logger = LoggerFactory.getLogger(KeycloakLogoutSuccessHandler.class);

    private final String authorizationUri;
    private final String postLogoutRedirectUri;

    /**
     * Construit le handler avec l'URI d'autorisation Keycloak.
     *
     * @param authorizationUri L'URI d'autorisation OAuth2 (spring.security.oauth2.client.provider.keycloak.authorization-uri)
     * @param postLogoutRedirectUri L'URI de redirection après logout (peut être "{baseUrl}/" pour dynamique)
     */
    public KeycloakLogoutSuccessHandler(String authorizationUri, String postLogoutRedirectUri) {
        this.authorizationUri = authorizationUri;
        this.postLogoutRedirectUri = postLogoutRedirectUri;
    }

    @Override
    public void onLogoutSuccess(HttpServletRequest request, HttpServletResponse response,
                                Authentication authentication) throws IOException, ServletException {

        String targetUrl = determineTargetUrl(request, authentication);

        if (response.isCommitted()) {
            logger.debug("Response already committed. Unable to redirect to {}", targetUrl);
            return;
        }

        logger.debug("Redirecting to Keycloak logout: {}", targetUrl);
        response.sendRedirect(targetUrl);
    }

    /**
     * Détermine l'URL de redirection pour le logout Keycloak.
     *
     * @param request La requête HTTP
     * @param authentication L'authentification courante (peut être null si déjà déconnecté)
     * @return L'URL de logout Keycloak complète ou l'URL de redirection locale si pas de Keycloak
     */
    String determineTargetUrl(HttpServletRequest request, Authentication authentication) {
        // Si pas d'authorization-uri configuré, redirection simple vers la page d'accueil
        if (authorizationUri == null || authorizationUri.isEmpty()) {
            return resolvePostLogoutRedirectUri(request);
        }

        // Construire l'URL de logout Keycloak en remplaçant /auth par /logout
        String logoutUri = deriveLogoutUri(authorizationUri);
        if (logoutUri == null) {
            logger.warn("Could not derive logout URI from authorization URI: {}", authorizationUri);
            return resolvePostLogoutRedirectUri(request);
        }

        UriComponentsBuilder builder = UriComponentsBuilder.fromUriString(logoutUri);

        // Ajouter l'id_token_hint si disponible (permet à Keycloak de savoir quel utilisateur déconnecter)
        String idToken = extractIdToken(authentication);
        if (idToken != null) {
            builder.queryParam("id_token_hint", idToken);
        }

        // Ajouter l'URL de redirection post-logout
        String redirectUri = resolvePostLogoutRedirectUri(request);
        builder.queryParam("post_logout_redirect_uri", redirectUri);

        return builder.build().toUriString();
    }

    /**
     * Dérive l'URL de logout depuis l'URL d'autorisation.
     *
     * Transforme: .../protocol/openid-connect/auth
     * En:         .../protocol/openid-connect/logout
     *
     * @param authUri L'URI d'autorisation OAuth2
     * @return L'URI de logout, ou null si la transformation échoue
     */
    String deriveLogoutUri(String authUri) {
        if (authUri == null || authUri.isEmpty()) {
            return null;
        }

        // L'authorization-uri se termine par /auth, on le remplace par /logout
        if (authUri.endsWith("/auth")) {
            return authUri.substring(0, authUri.length() - "/auth".length()) + "/logout";
        }

        // Fallback: essayer de trouver /protocol/openid-connect/auth dans l'URL
        int index = authUri.indexOf("/protocol/openid-connect/auth");
        if (index > 0) {
            return authUri.substring(0, index) + "/protocol/openid-connect/logout";
        }

        return null;
    }

    /**
     * Extrait le token ID de l'authentification OIDC.
     *
     * @param authentication L'authentification (peut être null ou non-OIDC)
     * @return Le token ID ou null si non disponible
     */
    String extractIdToken(Authentication authentication) {
        if (authentication == null) {
            return null;
        }

        if (authentication instanceof OAuth2AuthenticationToken oauthToken
                && oauthToken.getPrincipal() instanceof OidcUser oidcUser
                l
            return oidcUser.getIdToken().getTokenValue();
        }

        return null;
    }

    /**
     * Résout l'URI de redirection post-logout.
     *
     * Si l'URI contient {baseUrl}, il est remplacé par l'URL de base de la requête.
     *
     * @param request La requête HTTP
     * @return L'URI de redirection résolu
     */
    String resolvePostLogoutRedirectUri(HttpServletRequest request) {
        if (postLogoutRedirectUri == null || postLogoutRedirectUri.isEmpty()) {
            return buildBaseUrl(request) + "/";
        }

        if (postLogoutRedirectUri.contains("{baseUrl}")) {
            String baseUrl = buildBaseUrl(request);
            return postLogoutRedirectUri.replace("{baseUrl}", baseUrl);
        }

        return postLogoutRedirectUri;
    }

    /**
     * Construit l'URL de base à partir de la requête.
     * Prend en compte les headers X-Forwarded-* pour les reverse proxies.
     *
     * @param request La requête HTTP
     * @return L'URL de base (scheme://host[:port])
     */
    String buildBaseUrl(HttpServletRequest request) {
        // Vérifier les headers de proxy (X-Forwarded-*)
        String forwardedProto = request.getHeader("X-Forwarded-Proto");
        String forwardedHost = request.getHeader("X-Forwarded-Host");
        String forwardedPort = request.getHeader("X-Forwarded-Port");

        String scheme;
        String host;
        int port;

        if (forwardedProto != null && forwardedHost != null) {
            // Derrière un reverse proxy
            scheme = forwardedProto;
            host = forwardedHost;
            port = forwardedPort != null ? Integer.parseInt(forwardedPort) : -1;
        } else {
            // Accès direct
            scheme = request.getScheme();
            host = request.getServerName();
            port = request.getServerPort();
        }

        StringBuilder url = new StringBuilder();
        url.append(scheme).append("://").append(host);

        // Ajouter le port seulement s'il n'est pas standard
        if (port > 0 && !isStandardPort(scheme, port)) {
            url.append(":").append(port);
        }

        return url.toString();
    }

    /**
     * Vérifie si le port est un port standard pour le scheme donné.
     */
    private boolean isStandardPort(String scheme, int port) {
        return ("http".equals(scheme) && port == 80) || ("https".equals(scheme) && port == 443);
    }
}
