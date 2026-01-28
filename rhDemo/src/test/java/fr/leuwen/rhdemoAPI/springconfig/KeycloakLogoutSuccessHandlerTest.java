package fr.leuwen.rhdemoAPI.springconfig;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.client.authentication.OAuth2AuthenticationToken;
import org.springframework.security.oauth2.core.oidc.OidcIdToken;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;

import jakarta.servlet.ServletException;
import java.io.IOException;
import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

/**
 * Tests unitaires pour KeycloakLogoutSuccessHandler.
 *
 * Ce handler résout le problème de logout OIDC quand issuer-uri ne peut pas être configuré.
 * Il dérive l'URL de logout depuis authorization-uri en remplaçant /auth par /logout.
 */
@DisplayName("KeycloakLogoutSuccessHandler")
class KeycloakLogoutSuccessHandlerTest {

    private static final String AUTH_URI = "https://keycloak.example.com/realms/RHDemo/protocol/openid-connect/auth";
    private static final String LOGOUT_URI = "https://keycloak.example.com/realms/RHDemo/protocol/openid-connect/logout";
    private static final String POST_LOGOUT_URI = "{baseUrl}/";

    @Mock
    private HttpServletRequest request;

    @Mock
    private HttpServletResponse response;

    @Mock
    private OAuth2AuthenticationToken authentication;

    @Mock
    private OidcUser oidcUser;

    private KeycloakLogoutSuccessHandler handler;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        handler = new KeycloakLogoutSuccessHandler(AUTH_URI, POST_LOGOUT_URI);

        // Configuration par défaut de la requête (accès direct sans proxy)
        when(request.getScheme()).thenReturn("https");
        when(request.getServerName()).thenReturn("rhdemo.example.com");
        when(request.getServerPort()).thenReturn(443);
    }

    // ==================== Tests deriveLogoutUri ====================

    @Nested
    @DisplayName("deriveLogoutUri")
    class DeriveLogoutUriTests {

        @ParameterizedTest(name = "URI: {0} → {1}")
        @CsvSource({
            "https://keycloak.example.com/realms/RHDemo/protocol/openid-connect/auth, https://keycloak.example.com/realms/RHDemo/protocol/openid-connect/logout",
            "http://localhost:8080/realms/test/protocol/openid-connect/auth, http://localhost:8080/realms/test/protocol/openid-connect/logout",
            "https://keycloak-stagingkub.intra.leuwen-lc.fr/realms/RHDemo/protocol/openid-connect/auth, https://keycloak-stagingkub.intra.leuwen-lc.fr/realms/RHDemo/protocol/openid-connect/logout",
            "https://keycloak.ephemere.local/realms/RHDemo/protocol/openid-connect/auth, https://keycloak.ephemere.local/realms/RHDemo/protocol/openid-connect/logout"
        })
        @DisplayName("doit transformer correctement les URIs d'autorisation en URIs de logout")
        void shouldDeriveLogoutUriFromAuthUri(String authUri, String expectedLogoutUri) {
            String result = handler.deriveLogoutUri(authUri);
            assertThat(result).isEqualTo(expectedLogoutUri);
        }

        @ParameterizedTest(name = "URI invalide: [{0}]")
        @NullAndEmptySource
        @DisplayName("doit retourner null pour les URIs null ou vides")
        void shouldReturnNullForNullOrEmptyUri(String invalidUri) {
            String result = handler.deriveLogoutUri(invalidUri);
            assertThat(result).isNull();
        }

        @Test
        @DisplayName("doit retourner null si l'URI ne contient pas /auth")
        void shouldReturnNullIfNoAuthPath() {
            String result = handler.deriveLogoutUri("https://keycloak.example.com/some/other/path");
            assertThat(result).isNull();
        }

        @Test
        @DisplayName("doit gérer les URIs avec /protocol/openid-connect/auth au milieu")
        void shouldHandleAuthPathInMiddle() {
            String uri = "https://keycloak.example.com/realms/RHDemo/protocol/openid-connect/auth?param=value";
            // Le handler cherche /auth à la fin, donc ce cas retourne null
            // car l'URI ne se termine pas par /auth
            String result = handler.deriveLogoutUri(uri);
            // Avec query params, ça ne finit pas par /auth donc fallback sur indexOf
            assertThat(result).isEqualTo("https://keycloak.example.com/realms/RHDemo/protocol/openid-connect/logout");
        }
    }

    // ==================== Tests extractIdToken ====================

    @Nested
    @DisplayName("extractIdToken")
    class ExtractIdTokenTests {

        @Test
        @DisplayName("doit extraire le token ID d'un utilisateur OIDC authentifié")
        void shouldExtractIdTokenFromOidcUser() {
            String expectedToken = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test";

            OidcIdToken idToken = new OidcIdToken(
                expectedToken,
                Instant.now(),
                Instant.now().plusSeconds(3600),
                Map.of("sub", "user123")
            );

            when(authentication.getPrincipal()).thenReturn(oidcUser);
            when(oidcUser.getIdToken()).thenReturn(idToken);

            String result = handler.extractIdToken(authentication);

            assertThat(result).isEqualTo(expectedToken);
        }

        @Test
        @DisplayName("doit retourner null si l'authentification est null")
        void shouldReturnNullIfAuthenticationIsNull() {
            String result = handler.extractIdToken(null);
            assertThat(result).isNull();
        }

        @Test
        @DisplayName("doit retourner null si le principal n'est pas un OidcUser")
        void shouldReturnNullIfPrincipalIsNotOidcUser() {
            // Créer un OAuth2User non-OIDC (qui n'est pas une instance de OidcUser)
            org.springframework.security.oauth2.core.user.OAuth2User nonOidcUser =
                mock(org.springframework.security.oauth2.core.user.OAuth2User.class);
            when(authentication.getPrincipal()).thenReturn(nonOidcUser);

            String result = handler.extractIdToken(authentication);

            assertThat(result).isNull();
        }

        @Test
        @DisplayName("doit retourner null si le token ID est null")
        void shouldReturnNullIfIdTokenIsNull() {
            when(authentication.getPrincipal()).thenReturn(oidcUser);
            when(oidcUser.getIdToken()).thenReturn(null);

            String result = handler.extractIdToken(authentication);

            assertThat(result).isNull();
        }

        @Test
        @DisplayName("doit retourner null pour une authentification non-OAuth2")
        void shouldReturnNullForNonOAuth2Authentication() {
            Authentication basicAuth = mock(Authentication.class);

            String result = handler.extractIdToken(basicAuth);

            assertThat(result).isNull();
        }
    }

    // ==================== Tests buildBaseUrl ====================

    @Nested
    @DisplayName("buildBaseUrl")
    class BuildBaseUrlTests {

        @Test
        @DisplayName("doit construire l'URL de base depuis une requête directe HTTPS")
        void shouldBuildBaseUrlFromDirectHttpsRequest() {
            when(request.getScheme()).thenReturn("https");
            when(request.getServerName()).thenReturn("rhdemo.example.com");
            when(request.getServerPort()).thenReturn(443);

            String result = handler.buildBaseUrl(request);

            assertThat(result).isEqualTo("https://rhdemo.example.com");
        }

        @Test
        @DisplayName("doit construire l'URL de base depuis une requête directe HTTP")
        void shouldBuildBaseUrlFromDirectHttpRequest() {
            when(request.getScheme()).thenReturn("http");
            when(request.getServerName()).thenReturn("localhost");
            when(request.getServerPort()).thenReturn(80);

            String result = handler.buildBaseUrl(request);

            assertThat(result).isEqualTo("http://localhost");
        }

        @Test
        @DisplayName("doit inclure le port non standard")
        void shouldIncludeNonStandardPort() {
            when(request.getScheme()).thenReturn("http");
            when(request.getServerName()).thenReturn("localhost");
            when(request.getServerPort()).thenReturn(9000);

            String result = handler.buildBaseUrl(request);

            assertThat(result).isEqualTo("http://localhost:9000");
        }

        @ParameterizedTest(name = "X-Forwarded: proto={0}, host={1}, port={2} → {3}")
        @CsvSource({
            "https, rhdemo-stagingkub.intra.leuwen-lc.fr, 443, https://rhdemo-stagingkub.intra.leuwen-lc.fr",
            "https, rhdemo.example.com, 8443, https://rhdemo.example.com:8443",
            "https, rhdemo.example.com, , https://rhdemo.example.com"
        })
        @DisplayName("doit construire l'URL correctement avec les headers X-Forwarded-*")
        void shouldBuildUrlWithForwardedHeaders(String proto, String host, String port, String expectedUrl) {
            when(request.getHeader("X-Forwarded-Proto")).thenReturn(proto);
            when(request.getHeader("X-Forwarded-Host")).thenReturn(host);
            // CsvSource traite les valeurs vides comme null
            when(request.getHeader("X-Forwarded-Port")).thenReturn(port != null && port.isEmpty() ? null : port);

            String result = handler.buildBaseUrl(request);

            assertThat(result).isEqualTo(expectedUrl);
        }
    }

    // ==================== Tests resolvePostLogoutRedirectUri ====================

    @Nested
    @DisplayName("resolvePostLogoutRedirectUri")
    class ResolvePostLogoutRedirectUriTests {

        @Test
        @DisplayName("doit remplacer {baseUrl} par l'URL de base")
        void shouldReplaceBaseUrlPlaceholder() {
            String result = handler.resolvePostLogoutRedirectUri(request);

            assertThat(result).isEqualTo("https://rhdemo.example.com/");
        }

        @Test
        @DisplayName("doit retourner l'URL statique si pas de placeholder")
        void shouldReturnStaticUri() {
            KeycloakLogoutSuccessHandler staticHandler =
                new KeycloakLogoutSuccessHandler(AUTH_URI, "https://static.example.com/logged-out");

            String result = staticHandler.resolvePostLogoutRedirectUri(request);

            assertThat(result).isEqualTo("https://static.example.com/logged-out");
        }

        @Test
        @DisplayName("doit retourner l'URL de base + / si postLogoutRedirectUri est null")
        void shouldReturnBaseUrlIfPostLogoutUriIsNull() {
            KeycloakLogoutSuccessHandler nullHandler = new KeycloakLogoutSuccessHandler(AUTH_URI, null);

            String result = nullHandler.resolvePostLogoutRedirectUri(request);

            assertThat(result).isEqualTo("https://rhdemo.example.com/");
        }

        @Test
        @DisplayName("doit retourner l'URL de base + / si postLogoutRedirectUri est vide")
        void shouldReturnBaseUrlIfPostLogoutUriIsEmpty() {
            KeycloakLogoutSuccessHandler emptyHandler = new KeycloakLogoutSuccessHandler(AUTH_URI, "");

            String result = emptyHandler.resolvePostLogoutRedirectUri(request);

            assertThat(result).isEqualTo("https://rhdemo.example.com/");
        }
    }

    // ==================== Tests determineTargetUrl ====================

    @Nested
    @DisplayName("determineTargetUrl")
    class DetermineTargetUrlTests {

        @Test
        @DisplayName("doit construire l'URL complète de logout avec id_token_hint")
        void shouldBuildCompleteLogoutUrl() {
            String idToken = "test-id-token";
            OidcIdToken oidcIdToken = new OidcIdToken(
                idToken, Instant.now(), Instant.now().plusSeconds(3600), Map.of("sub", "user")
            );
            when(authentication.getPrincipal()).thenReturn(oidcUser);
            when(oidcUser.getIdToken()).thenReturn(oidcIdToken);

            String result = handler.determineTargetUrl(request, authentication);

            assertThat(result)
                .startsWith(LOGOUT_URI)
                .contains("id_token_hint=" + idToken)
                .contains("post_logout_redirect_uri=https://rhdemo.example.com/");
        }

        @Test
        @DisplayName("doit construire l'URL de logout sans id_token_hint si pas d'authentification")
        void shouldBuildLogoutUrlWithoutIdToken() {
            String result = handler.determineTargetUrl(request, null);

            assertThat(result)
                .startsWith(LOGOUT_URI)
                .doesNotContain("id_token_hint")
                .contains("post_logout_redirect_uri=https://rhdemo.example.com/");
        }

        @Test
        @DisplayName("doit retourner l'URL locale si pas d'authorization-uri configuré")
        void shouldReturnLocalUrlIfNoAuthUri() {
            KeycloakLogoutSuccessHandler noAuthHandler = new KeycloakLogoutSuccessHandler(null, POST_LOGOUT_URI);

            String result = noAuthHandler.determineTargetUrl(request, authentication);

            assertThat(result).isEqualTo("https://rhdemo.example.com/");
        }

        @Test
        @DisplayName("doit retourner l'URL locale si authorization-uri est vide")
        void shouldReturnLocalUrlIfEmptyAuthUri() {
            KeycloakLogoutSuccessHandler emptyAuthHandler = new KeycloakLogoutSuccessHandler("", POST_LOGOUT_URI);

            String result = emptyAuthHandler.determineTargetUrl(request, authentication);

            assertThat(result).isEqualTo("https://rhdemo.example.com/");
        }

        @Test
        @DisplayName("doit retourner l'URL locale si l'authorization-uri est invalide")
        void shouldReturnLocalUrlIfInvalidAuthUri() {
            KeycloakLogoutSuccessHandler invalidHandler =
                new KeycloakLogoutSuccessHandler("invalid-uri-without-auth", POST_LOGOUT_URI);

            String result = invalidHandler.determineTargetUrl(request, authentication);

            assertThat(result).isEqualTo("https://rhdemo.example.com/");
        }
    }

    // ==================== Tests onLogoutSuccess ====================

    @Nested
    @DisplayName("onLogoutSuccess")
    class OnLogoutSuccessTests {

        @Test
        @DisplayName("doit rediriger vers Keycloak logout")
        void shouldRedirectToKeycloakLogout() throws IOException, ServletException {
            when(response.isCommitted()).thenReturn(false);

            handler.onLogoutSuccess(request, response, null);

            verify(response).sendRedirect(contains(LOGOUT_URI));
        }

        @Test
        @DisplayName("ne doit pas rediriger si la réponse est déjà committed")
        void shouldNotRedirectIfResponseCommitted() throws IOException, ServletException {
            when(response.isCommitted()).thenReturn(true);

            handler.onLogoutSuccess(request, response, null);

            verify(response, never()).sendRedirect(anyString());
        }

        @Test
        @DisplayName("doit inclure le token ID dans la redirection")
        void shouldIncludeIdTokenInRedirect() throws IOException, ServletException {
            String idToken = "my-id-token";
            OidcIdToken oidcIdToken = new OidcIdToken(
                idToken, Instant.now(), Instant.now().plusSeconds(3600), Map.of("sub", "user")
            );
            when(authentication.getPrincipal()).thenReturn(oidcUser);
            when(oidcUser.getIdToken()).thenReturn(oidcIdToken);
            when(response.isCommitted()).thenReturn(false);

            handler.onLogoutSuccess(request, response, authentication);

            verify(response).sendRedirect(contains("id_token_hint=" + idToken));
        }
    }
}
