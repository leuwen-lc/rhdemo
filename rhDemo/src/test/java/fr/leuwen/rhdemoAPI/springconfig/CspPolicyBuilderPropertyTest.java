package fr.leuwen.rhdemoAPI.springconfig;

import net.jqwik.api.*;
import net.jqwik.api.constraints.StringLength;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Tests par propriétés (PBT) pour CspPolicyBuilder.
 *
 * Complète CspPolicyBuilderTest (exemples ciblés) en vérifiant des invariants
 * sur un espace d'entrée large généré automatiquement par jqwik.
 *
 * Propriétés couvertes :
 * - Invariant de sécurité absolu : la CSP ne contient jamais de directive unsafe
 *   quelle que soit l'URL Keycloak fournie (y compris injections tentées).
 * - Syntaxe CSP valide : pas de double point-virgule pour toute entrée.
 * - Directives obligatoires : toujours présentes quelle que soit l'entrée.
 * - Pas de fuite de chemin : extractKeycloakBaseUrl() n'inclut jamais le path dans son résultat.
 * - Idempotence : ré-appliquer extractKeycloakBaseUrl() sur son propre résultat donne le même résultat.
 */
@Label("CspPolicyBuilder — Tests par propriétés")
class CspPolicyBuilderPropertyTest {

    // ==================== Invariants de sécurité (entrée arbitraire) ====================

    @Property
    @Label("jamais unsafe-inline ni unsafe-eval pour toute chaîne en entrée")
    void csp_neverContainsUnsafeDirectives(@ForAll @StringLength(max = 200) String anyInput) {
        String csp = new CspPolicyBuilder(anyInput, false).buildCspDirectives();
        assertThat(csp)
                .doesNotContain("unsafe-inline")
                .doesNotContain("unsafe-eval");
    }

    @Property
    @Label("pas de double point-virgule dans la CSP pour toute chaîne en entrée")
    void csp_neverContainsDoubleSemicolon(@ForAll @StringLength(max = 200) String anyInput) {
        String csp = new CspPolicyBuilder(anyInput, false).buildCspDirectives();
        assertThat(csp).doesNotContain(";;");
    }

    @Property
    @Label("directives obligatoires toujours présentes quelle que soit l'entrée")
    void csp_alwaysContainsRequiredDirectives(@ForAll @StringLength(max = 200) String anyInput) {
        String csp = new CspPolicyBuilder(anyInput, false).buildCspDirectives();
        assertThat(csp)
                .contains("default-src 'self'")
                .contains("script-src 'self'")
                .contains("frame-ancestors 'none'")
                .contains("object-src 'none'")
                .contains("base-uri 'self'");
    }

    // ==================== Propriétés structurelles (URLs bien formées) ====================

    @Property
    @Label("extractKeycloakBaseUrl: le résultat ne contient jamais de chemin (pas de '/' après le host)")
    void extractBaseUrl_resultNeverContainsPath(@ForAll("structuredUrls") String url) {
        String result = new CspPolicyBuilder(url, false).extractKeycloakBaseUrl();
        if (!result.isEmpty()) {
            String withoutScheme = result.replaceFirst("^https?://", "");
            assertThat(withoutScheme)
                    .as("Le résultat '%s' (entrée : '%s') ne doit pas contenir de chemin", result, url)
                    .doesNotContain("/");
        }
    }

    @Property
    @Label("extractKeycloakBaseUrl: idempotence — ré-appliquer sur le résultat + chemin donne le même résultat")
    void extractBaseUrl_isIdempotent(@ForAll("structuredUrls") String url) {
        String first = new CspPolicyBuilder(url, false).extractKeycloakBaseUrl();
        if (!first.isEmpty()) {
            String second = new CspPolicyBuilder(
                    first + "/realms/test/protocol/openid-connect/auth", false
            ).extractKeycloakBaseUrl();
            assertThat(second)
                    .as("Idempotence violée pour l'entrée '%s' (base extraite : '%s')", url, first)
                    .isEqualTo(first);
        }
    }

    // ==================== Générateurs ====================

    /**
     * Génère des URLs structurées de la forme scheme://host.local:port/realms/xxx/protocol/openid-connect/auth,
     * représentatives des URIs d'autorisation Keycloak.
     */
    @Provide
    Arbitrary<String> structuredUrls() {
        Arbitrary<String> schemes = Arbitraries.of("http", "https");
        Arbitrary<String> hosts = Arbitraries.strings()
                .withCharRange('a', 'z')
                .ofMinLength(1).ofMaxLength(15)
                .map(h -> h + ".local");
        Arbitrary<Integer> ports = Arbitraries.integers().between(1, 65535);
        Arbitrary<String> realms = Arbitraries.strings()
                .withCharRange('a', 'z')
                .ofMinLength(2).ofMaxLength(20);

        return Combinators.combine(schemes, hosts, ports, realms)
                .as((scheme, host, port, realm) ->
                        scheme + "://" + host + ":" + port
                                + "/realms/" + realm + "/protocol/openid-connect/auth");
    }
}
