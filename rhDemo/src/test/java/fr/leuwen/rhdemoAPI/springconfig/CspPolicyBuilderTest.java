package fr.leuwen.rhdemoAPI.springconfig;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Tests unitaires pour CspPolicyBuilder.
 *
 * Couverture:
 * - Extraction de l'URL de base de Keycloak depuis l'URI d'autorisation (différents ports, URIs invalides).
 * - Génération dynamique des directives CSP avec/sans Keycloak.
 * - Configuration du repository CSRF avec le flag Secure.
 *
 * Remplace l'ancien SecurityConfigCspDynamicTest qui passait par ReflectionTestUtils
 * sur les méthodes privées de SecurityConfig.
 */
@DisplayName("CspPolicyBuilder - Tests de génération dynamique CSP")
class CspPolicyBuilderTest {

    private static CspPolicyBuilder builderWith(String keycloakAuthUri) {
        return new CspPolicyBuilder(keycloakAuthUri, false);
    }

    private static CspPolicyBuilder builderWith(String keycloakAuthUri, boolean cookieSecureFlag) {
        return new CspPolicyBuilder(keycloakAuthUri, cookieSecureFlag);
    }

    // ==================== extractKeycloakBaseUrl ====================

    @ParameterizedTest(name = "extractKeycloakBaseUrl avec URI: {0}")
    @CsvSource({
        "https://keycloak.ephemere.local/realms/rhdemo/protocol/openid-connect/auth, https://keycloak.ephemere.local",
        "http://localhost:8080/realms/rhdemo/protocol/openid-connect/auth, http://localhost:8080",
        "http://keycloak.example.com:80/realms/rhdemo/protocol/openid-connect/auth, http://keycloak.example.com",
        "https://keycloak.example.com:443/realms/rhdemo/protocol/openid-connect/auth, https://keycloak.example.com"
    })
    @DisplayName("doit extraire correctement l'URL de base avec différents ports")
    void extractKeycloakBaseUrl_WithVariousPorts(String inputUri, String expectedUrl) {
        assertThat(builderWith(inputUri).extractKeycloakBaseUrl()).isEqualTo(expectedUrl);
    }

    @ParameterizedTest(name = "extractKeycloakBaseUrl avec URI invalide/vide: [{0}]")
    @NullAndEmptySource
    @ValueSource(strings = {"invalid-uri"})
    @DisplayName("doit retourner une chaîne vide pour les URIs null, vides ou invalides")
    void extractKeycloakBaseUrl_WithInvalidUris(String invalidUri) {
        assertThat(builderWith(invalidUri).extractKeycloakBaseUrl()).isEmpty();
    }

    @Test
    @DisplayName("doit retourner une chaîne vide pour une URI sans scheme")
    void extractKeycloakBaseUrl_WithMissingScheme() {
        assertThat(builderWith("//keycloak.local/realms/test").extractKeycloakBaseUrl()).isEmpty();
    }

    @Test
    @DisplayName("doit retourner une chaîne vide pour une URI ne contenant que le scheme")
    void extractKeycloakBaseUrl_WithOnlyScheme() {
        assertThat(builderWith("https:").extractKeycloakBaseUrl()).isEmpty();
    }

    @Test
    @DisplayName("doit conserver le port non standard (8443)")
    void extractKeycloakBaseUrl_WithNonStandardPort() {
        assertThat(builderWith("https://keycloak.local:8443/realms/rhdemo/protocol/openid-connect/auth").extractKeycloakBaseUrl())
            .isEqualTo("https://keycloak.local:8443");
    }

    // ==================== buildCspDirectives ====================

    @Test
    @DisplayName("doit inclure Keycloak dans connect-src et form-action si configuré")
    void buildCspDirectives_WithKeycloakUrl() {
        String csp = builderWith("https://keycloak.ephemere.local/realms/rhdemo/protocol/openid-connect/auth").buildCspDirectives();

        assertThat(csp)
            .contains("connect-src 'self' https://keycloak.ephemere.local")
            .contains("form-action 'self' https://keycloak.ephemere.local");
    }

    @Test
    @DisplayName("ne doit pas inclure Keycloak si non configuré")
    void buildCspDirectives_WithoutKeycloakUrl() {
        String csp = builderWith("").buildCspDirectives();

        assertThat(csp)
            .contains("connect-src 'self';")
            .contains("form-action 'self';")
            .doesNotContain("keycloak");
    }

    @Test
    @DisplayName("doit contenir toutes les directives de sécurité requises")
    void buildCspDirectives_ContainsAllRequiredDirectives() {
        String csp = builderWith("").buildCspDirectives();

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
    @DisplayName("ne doit PAS contenir de directives unsafe")
    void buildCspDirectives_ShouldNotContainUnsafeDirectives() {
        String csp = builderWith("https://keycloak.ephemere.local/realms/rhdemo/protocol/openid-connect/auth").buildCspDirectives();

        assertThat(csp)
            .doesNotContain("unsafe-inline")
            .doesNotContain("unsafe-eval")
            .doesNotContain("upgrade-insecure-requests");
    }

    @Test
    @DisplayName("doit générer une CSP valide (pas de double point-virgule)")
    void buildCspDirectives_ShouldNotHaveDoubleSemicolons() {
        String csp = builderWith("https://keycloak.ephemere.local/realms/rhdemo/protocol/openid-connect/auth").buildCspDirectives();

        assertThat(csp).doesNotContain(";;");
    }

    // ==================== createCsrfTokenRepository ====================

    @Test
    @DisplayName("doit créer un repository CSRF non null avec cookieSecureFlag=false")
    void createCsrfTokenRepository_WithSecureFlagFalse() {
        CookieCsrfTokenRepository repository = builderWith("", false).createCsrfTokenRepository();

        assertThat(repository).isNotNull();
    }

    @Test
    @DisplayName("doit créer un repository CSRF non null avec cookieSecureFlag=true")
    void createCsrfTokenRepository_WithSecureFlagTrue() {
        CookieCsrfTokenRepository repository = builderWith("", true).createCsrfTokenRepository();

        assertThat(repository).isNotNull();
    }
}
