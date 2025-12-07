package fr.leuwen.rhdemoAPI.springconfig;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Tests unitaires pour les méthodes privées de SecurityConfig (via réflexion).
 *
 * Ces tests vérifient:
 * - L'extraction correcte de l'URL de base de Keycloak depuis l'URI d'autorisation
 * - La génération dynamique des directives CSP avec/sans Keycloak
 */
@DisplayName("SecurityConfig - Tests de génération dynamique CSP")
class SecurityConfigCspDynamicTest {

    @Test
    @DisplayName("extractKeycloakBaseUrl doit extraire l'URL de base depuis une URI HTTPS avec port standard")
    void testExtractKeycloakBaseUrl_WithHttpsStandardPort() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri",
            "https://keycloak.staging.local/realms/rhdemo/protocol/openid-connect/auth");

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert
        assertThat(result).isEqualTo("https://keycloak.staging.local");
    }

    @Test
    @DisplayName("extractKeycloakBaseUrl doit extraire l'URL de base avec port personnalisé")
    void testExtractKeycloakBaseUrl_WithCustomPort() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri",
            "http://localhost:8080/realms/rhdemo/protocol/openid-connect/auth");

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert
        assertThat(result).isEqualTo("http://localhost:8080");
    }

    @Test
    @DisplayName("extractKeycloakBaseUrl doit retourner une chaîne vide si l'URI est null")
    void testExtractKeycloakBaseUrl_WithNullUri() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri", null);

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("extractKeycloakBaseUrl doit retourner une chaîne vide si l'URI est vide")
    void testExtractKeycloakBaseUrl_WithEmptyUri() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri", "");

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("extractKeycloakBaseUrl doit gérer une URI invalide en retournant une chaîne vide")
    void testExtractKeycloakBaseUrl_WithInvalidUri() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri", "invalid-uri");

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("extractKeycloakBaseUrl ne doit pas inclure le port 80 pour HTTP")
    void testExtractKeycloakBaseUrl_WithPort80() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri",
            "http://keycloak.example.com:80/realms/rhdemo/protocol/openid-connect/auth");

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert - Port 80 ne doit pas être inclus dans l'URL
        assertThat(result).isEqualTo("http://keycloak.example.com");
    }

    @Test
    @DisplayName("extractKeycloakBaseUrl ne doit pas inclure le port 443 pour HTTPS")
    void testExtractKeycloakBaseUrl_WithPort443() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri",
            "https://keycloak.example.com:443/realms/rhdemo/protocol/openid-connect/auth");

        // Act
        String result = (String) ReflectionTestUtils.invokeMethod(config, "extractKeycloakBaseUrl");

        // Assert - Port 443 ne doit pas être inclus dans l'URL
        assertThat(result).isEqualTo("https://keycloak.example.com");
    }

    @Test
    @DisplayName("buildCspDirectives doit inclure Keycloak dans connect-src si configuré")
    void testBuildCspDirectives_WithKeycloakUrl() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri",
            "https://keycloak.staging.local/realms/rhdemo/protocol/openid-connect/auth");

        // Act
        String csp = (String) ReflectionTestUtils.invokeMethod(config, "buildCspDirectives");

        // Assert
        assertThat(csp)
            .contains("connect-src 'self' https://keycloak.staging.local")
            .contains("form-action 'self' https://keycloak.staging.local");
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
            .contains("img-src 'self' data: https:")
            .contains("font-src 'self' data:")
            .contains("connect-src 'self'")
            .contains("frame-src 'self'")
            .contains("frame-ancestors 'self'")
            .contains("form-action 'self'")
            .contains("object-src 'none'")
            .contains("base-uri 'self'");
    }

    @Test
    @DisplayName("buildCspDirectives ne doit PAS contenir de directives unsafe")
    void testBuildCspDirectives_ShouldNotContainUnsafeDirectives() throws Exception {
        // Arrange
        GrantedAuthoritiesKeyCloakMapper mockMapper = new GrantedAuthoritiesKeyCloakMapper();
        SecurityConfig config = new SecurityConfig(mockMapper);
        ReflectionTestUtils.setField(config, "keycloakAuthorizationUri",
            "https://keycloak.staging.local/realms/rhdemo/protocol/openid-connect/auth");

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
            "https://keycloak.staging.local/realms/rhdemo/protocol/openid-connect/auth");

        // Act
        String csp = (String) ReflectionTestUtils.invokeMethod(config, "buildCspDirectives");

        // Assert
        assertThat(csp).doesNotContain(";;");
    }
}
