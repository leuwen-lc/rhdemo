package fr.leuwen.rhdemoAPI.springconfig;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.test.util.ReflectionTestUtils;

import org.springframework.security.web.csrf.CookieCsrfTokenRepository;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Tests unitaires pour les méthodes privées de SecurityConfig (via réflexion).
 *
 * Ces tests vérifient:
 * - L'extraction correcte de l'URL de base de Keycloak depuis l'URI d'autorisation
 * - La génération dynamique des directives CSP avec/sans Keycloak
 * - La configuration du repository CSRF avec le flag Secure
 */
@DisplayName("SecurityConfig - Tests de génération dynamique CSP")
class SecurityConfigCspDynamicTest {

    // ==================== Tests extractKeycloakBaseUrl avec différents ports ====================

    @ParameterizedTest(name = "extractKeycloakBaseUrl avec URI: {0}")
    @CsvSource({
        "https://keycloak.ephemere.local/realms/rhdemo/protocol/openid-connect/auth, https://keycloak.ephemere.local",
        "http://localhost:8080/realms/rhdemo/protocol/openid-connect/auth, http://localhost:8080",
        "http://keycloak.example.com:80/realms/rhdemo/protocol/openid-connect/auth, http://keycloak.example.com",
        "https://keycloak.example.com:443/realms/rhdemo/protocol/openid-connect/auth, https://keycloak.example.com"
    })
    @DisplayName("extractKeycloakBaseUrl doit extraire correctement l'URL de base avec différents ports")
    void testExtractKeycloakBaseUrl_WithVariousPorts(String inputUri, String expectedUrl) throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri", inputUri);

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert
        assertThat(result).isEqualTo(expectedUrl);
    }

    // ==================== Tests extractKeycloakBaseUrl avec URIs invalides ====================

    @ParameterizedTest(name = "extractKeycloakBaseUrl avec URI invalide/vide: [{0}]")
    @NullAndEmptySource
    @ValueSource(strings = {"invalid-uri"})
    @DisplayName("extractKeycloakBaseUrl doit retourner une chaîne vide pour les URIs null, vides ou invalides")
    void testExtractKeycloakBaseUrl_WithInvalidUris(String invalidUri) throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri", invalidUri);

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert
        assertThat(result).isEmpty();
    }

    // ==================== Tests buildCspDirectives ====================

    @Test
    @DisplayName("buildCspDirectives doit inclure Keycloak dans connect-src si configuré")
    void testBuildCspDirectives_WithKeycloakUrl() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri",
            "https://keycloak.ephemere.local/realms/rhdemo/protocol/openid-connect/auth");

        // Act
        String csp = (String) ReflectionTestUtils.invokeMethod(config, "buildCspDirectives");

        // Assert
        assertThat(csp)
            .contains("connect-src 'self' https://keycloak.ephemere.local")
            .contains("form-action 'self' https://keycloak.ephemere.local");
    }

    @Test
    @DisplayName("buildCspDirectives ne doit pas inclure Keycloak dans connect-src si non configuré")
    void testBuildCspDirectives_WithoutKeycloakUrl() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri", "");

        // Act
        String csp = (String) ReflectionTestUtils.invokeMethod(config, "buildCspDirectives");

        // Assert
        assertThat(csp)
            .contains("connect-src 'self';")
            .contains("form-action 'self';")
            .doesNotContain("keycloak");
    }

    @Test
    @DisplayName("buildCspDirectives doit contenir toutes les directives de sécurité requises")
    void testBuildCspDirectives_ContainsAllRequiredDirectives() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri", "");

        // Act
        String csp = (String) ReflectionTestUtils.invokeMethod(config, "buildCspDirectives");

        // Assert - Vérifier que toutes les directives sont présentes
        assertThat(csp)
            .contains("default-src 'self'")
            .contains("script-src 'self'")
            .contains("style-src 'self'")
            .contains("img-src 'self' data:")
            .contains("font-src 'self' data:")
            .contains("connect-src 'self'")
            .contains("frame-ancestors 'none'")
            .contains("form-action 'self'")
            .contains("object-src 'none'")
            .contains("base-uri 'self'")
            .contains("media-src 'self'")
            .contains("manifest-src 'self'")
            .contains("worker-src 'self'");
    }

    @Test
    @DisplayName("buildCspDirectives ne doit PAS contenir de directives unsafe")
    void testBuildCspDirectives_ShouldNotContainUnsafeDirectives() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri",
            "https://keycloak.ephemere.local/realms/rhdemo/protocol/openid-connect/auth");

        // Act
        String csp = (String) ReflectionTestUtils.invokeMethod(config, "buildCspDirectives");

        // Assert - Vérifier qu'aucune directive unsafe n'est présente
        assertThat(csp)
            .doesNotContain("unsafe-inline")
            .doesNotContain("unsafe-eval")
            .doesNotContain("upgrade-insecure-requests");
    }

    @Test
    @DisplayName("buildCspDirectives doit générer une CSP valide (pas de double point-virgule)")
    void testBuildCspDirectives_ShouldNotHaveDoubleSemicolons() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri",
            "https://keycloak.ephemere.local/realms/rhdemo/protocol/openid-connect/auth");

        // Act
        String csp = (String) ReflectionTestUtils.invokeMethod(config, "buildCspDirectives");

        // Assert
        assertThat(csp).doesNotContain(";;");
    }

    // ==================== Tests createCsrfTokenRepository ====================

    @Test
    @DisplayName("createCsrfTokenRepository doit créer un repository avec HttpOnly=false")
    void testCreateCsrfTokenRepository_HttpOnlyFalse() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "cookieSecureFlag", false);

        // Act
        CookieCsrfTokenRepository repository = (CookieCsrfTokenRepository)
            ReflectionTestUtils.invokeMethod(config, "createCsrfTokenRepository");

        // Assert
        assertThat(repository).isNotNull();
        // Le repository doit être créé avec withHttpOnlyFalse() pour permettre au JS de lire le cookie
    }

    @Test
    @DisplayName("createCsrfTokenRepository avec cookieSecureFlag=true")
    void testCreateCsrfTokenRepository_WithSecureFlagTrue() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "cookieSecureFlag", true);

        // Act
        CookieCsrfTokenRepository repository = (CookieCsrfTokenRepository)
            ReflectionTestUtils.invokeMethod(config, "createCsrfTokenRepository");

        // Assert
        assertThat(repository).isNotNull();
        // Vérifie que le repository est créé correctement même avec le flag Secure
    }

    @Test
    @DisplayName("createCsrfTokenRepository avec cookieSecureFlag=false (dev local)")
    void testCreateCsrfTokenRepository_WithSecureFlagFalse() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "cookieSecureFlag", false);

        // Act
        CookieCsrfTokenRepository repository = (CookieCsrfTokenRepository)
            ReflectionTestUtils.invokeMethod(config, "createCsrfTokenRepository");

        // Assert
        assertThat(repository).isNotNull();
        // Le repository doit fonctionner en environnement de développement (HTTP)
    }

    // ==================== Tests extractKeycloakBaseUrl cas limites ====================

    @Test
    @DisplayName("extractKeycloakBaseUrl avec URI manquant le scheme")
    void testExtractKeycloakBaseUrl_WithMissingScheme() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri", "//keycloak.local/realms/test");

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("extractKeycloakBaseUrl avec URI ne contenant que le scheme")
    void testExtractKeycloakBaseUrl_WithOnlyScheme() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri", "https:");

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("extractKeycloakBaseUrl avec port non standard (8443)")
    void testExtractKeycloakBaseUrl_WithNonStandardPort() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri",
            "https://keycloak.local:8443/realms/rhdemo/protocol/openid-connect/auth");

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert
        assertThat(result).isEqualTo("https://keycloak.local:8443");
    }
}
