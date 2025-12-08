package fr.leuwen.rhdemoAPI.springconfig;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.oidc.OidcIdToken;
import org.springframework.security.oauth2.core.oidc.user.OidcUserAuthority;
import org.springframework.security.oauth2.core.user.OAuth2UserAuthority;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;
import java.util.*;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Tests unitaires pour GrantedAuthoritiesKeyCloakMapper.
 *
 * Couverture:
 * - Extraction de roles depuis OIDC ID Token
 * - Extraction de roles depuis OAuth2 User attributes
 * - Gestion des cas d'erreur (claims manquants)
 * - Filtrage des roles (seuls ceux commençant par ROLE_ sont conservés)
 */
@DisplayName("GrantedAuthoritiesKeyCloakMapper - Tests unitaires")
class GrantedAuthoritiesKeyCloakMapperTest {

    private GrantedAuthoritiesKeyCloakMapper mapper;
    private static final String CLIENT_ID = "rhdemo-client";

    @BeforeEach
    void setUp() {
        mapper = new GrantedAuthoritiesKeyCloakMapper();
        // Injecter le client ID via reflection (car @Value ne fonctionne pas dans les tests unitaires)
        ReflectionTestUtils.setField(mapper, "rhDemoClientID", CLIENT_ID);
    }

    @Test
    @DisplayName("Doit extraire les roles depuis un OIDC ID Token valide")
    void testMapAuthorities_WithOidcUserAuthority_ShouldExtractRoles() {
        // Arrange
        Map<String, Object> claims = buildValidClaims(Arrays.asList("ROLE_admin", "ROLE_MAJ"));
        OidcIdToken idToken = new OidcIdToken(
            "fake-token",
            Instant.now(),
            Instant.now().plusSeconds(3600),
            claims
        );
        OidcUserAuthority oidcAuthority = new OidcUserAuthority(idToken);
        Collection<GrantedAuthority> authorities = Collections.singletonList(oidcAuthority);

        // Act
        Collection<? extends GrantedAuthority> result = mapper.mapAuthorities(authorities);

        // Assert
        assertThat(result)
            .hasSize(2)
            .extracting(GrantedAuthority::getAuthority)
            .containsExactlyInAnyOrder("ROLE_admin", "ROLE_MAJ");
    }

    @Test
    @DisplayName("Doit extraire les roles depuis un OAuth2UserAuthority valide")
    void testMapAuthorities_WithOAuth2UserAuthority_ShouldExtractRoles() {
        // Arrange
        Map<String, Object> attributes = buildValidClaims(Arrays.asList("ROLE_consult", "ROLE_MAJ"));
        OAuth2UserAuthority oauth2Authority = new OAuth2UserAuthority(attributes);
        Collection<GrantedAuthority> authorities = Collections.singletonList(oauth2Authority);

        // Act
        Collection<? extends GrantedAuthority> result = mapper.mapAuthorities(authorities);

        // Assert
        assertThat(result)
            .hasSize(2)
            .extracting(GrantedAuthority::getAuthority)
            .containsExactlyInAnyOrder("ROLE_consult", "ROLE_MAJ");
    }

    @Test
    @DisplayName("Doit filtrer les roles qui ne commencent pas par ROLE_")
    void testMapAuthorities_ShouldFilterNonRoleAuthorities() {
        // Arrange
        List<String> roles = Arrays.asList(
            "ROLE_admin",      // ✅ Valide
            "ROLE_consult",    // ✅ Valide
            "offline_access",  // ❌ Filtré (pas de préfixe ROLE_)
            "uma_authorization", // ❌ Filtré
            "profile"          // ❌ Filtré
        );
        Map<String, Object> claims = buildValidClaims(roles);
        OidcIdToken idToken = new OidcIdToken("fake-token", Instant.now(), Instant.now().plusSeconds(3600), claims);
        OidcUserAuthority oidcAuthority = new OidcUserAuthority(idToken);

        // Act
        Collection<? extends GrantedAuthority> result = mapper.mapAuthorities(Collections.singletonList(oidcAuthority));

        // Assert - Seulement les roles avec ROLE_ sont conservés
        assertThat(result)
            .hasSize(2)
            .extracting(GrantedAuthority::getAuthority)
            .containsExactlyInAnyOrder("ROLE_admin", "ROLE_consult");
    }

    @Test
    @DisplayName("Doit lever une exception si resource_access est manquant")
    void testMapAuthorities_WithMissingResourceAccess_ShouldThrowException() {
        // Arrange
        Map<String, Object> claimsWithoutResourceAccess = new HashMap<>();
        claimsWithoutResourceAccess.put("sub", "user123");
        claimsWithoutResourceAccess.put("email", "user@example.com");
        // Pas de "resource_access" !

        OidcIdToken idToken = new OidcIdToken("fake-token", Instant.now(), Instant.now().plusSeconds(3600), claimsWithoutResourceAccess);
        OidcUserAuthority oidcAuthority = new OidcUserAuthority(idToken);

        // Act & Assert
        assertThatThrownBy(() -> mapper.mapAuthorities(Collections.singletonList(oidcAuthority)))
            .isInstanceOf(IllegalStateException.class)
            .hasMessageContaining("resource_access");
    }

    @Test
    @DisplayName("Doit retourner une liste vide si le client ID n'est pas trouvé dans resource_access")
    void testMapAuthorities_WithMissingClientId_ShouldReturnEmptyList() {
        // Arrange
        Map<String, Object> claims = new HashMap<>();
        Map<String, Object> resourceAccess = new HashMap<>();
        // Ajouter un autre client, mais pas "rhdemo-client"
        Map<String, Object> otherClientData = new HashMap<>();
        otherClientData.put("roles", Arrays.asList("ROLE_other"));
        resourceAccess.put("other-client", otherClientData);

        claims.put("resource_access", resourceAccess);

        OidcIdToken idToken = new OidcIdToken("fake-token", Instant.now(), Instant.now().plusSeconds(3600), claims);
        OidcUserAuthority oidcAuthority = new OidcUserAuthority(idToken);

        // Act
        Collection<? extends GrantedAuthority> result = mapper.mapAuthorities(Collections.singletonList(oidcAuthority));

        // Assert - Retourne une liste vide au lieu de lever une NPE
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("Doit retourner une liste vide si roles est null dans le client ID")
    void testMapAuthorities_WithNullRoles_ShouldReturnEmptyList() {
        // Arrange
        Map<String, Object> claims = new HashMap<>();
        Map<String, Object> resourceAccess = new HashMap<>();
        Map<String, Object> clientData = new HashMap<>();
        clientData.put("roles", null); // roles = null

        resourceAccess.put(CLIENT_ID, clientData);
        claims.put("resource_access", resourceAccess);

        OidcIdToken idToken = new OidcIdToken("fake-token", Instant.now(), Instant.now().plusSeconds(3600), claims);
        OidcUserAuthority oidcAuthority = new OidcUserAuthority(idToken);

        // Act
        Collection<? extends GrantedAuthority> result = mapper.mapAuthorities(Collections.singletonList(oidcAuthority));

        // Assert
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("Doit gérer une liste de roles vide")
    void testMapAuthorities_WithEmptyRolesList_ShouldReturnEmptyList() {
        // Arrange
        Map<String, Object> claims = buildValidClaims(Collections.emptyList());
        OidcIdToken idToken = new OidcIdToken("fake-token", Instant.now(), Instant.now().plusSeconds(3600), claims);
        OidcUserAuthority oidcAuthority = new OidcUserAuthority(idToken);

        // Act
        Collection<? extends GrantedAuthority> result = mapper.mapAuthorities(Collections.singletonList(oidcAuthority));

        // Assert
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("Doit traiter plusieurs authorities (OIDC + OAuth2)")
    void testMapAuthorities_WithMultipleAuthorities_ShouldCombineRoles() {
        // Arrange
        Map<String, Object> oidcClaims = buildValidClaims(Arrays.asList("ROLE_admin"));
        OidcIdToken idToken = new OidcIdToken("fake-token", Instant.now(), Instant.now().plusSeconds(3600), oidcClaims);
        OidcUserAuthority oidcAuthority = new OidcUserAuthority(idToken);

        Map<String, Object> oauth2Attributes = buildValidClaims(Arrays.asList("ROLE_MAJ"));
        OAuth2UserAuthority oauth2Authority = new OAuth2UserAuthority(oauth2Attributes);

        Collection<GrantedAuthority> authorities = Arrays.asList(oidcAuthority, oauth2Authority);

        // Act
        Collection<? extends GrantedAuthority> result = mapper.mapAuthorities(authorities);

        // Assert - Les roles des deux authorities doivent être combinés (dans un Set, donc pas de doublons)
        assertThat(result)
            .hasSize(2)
            .extracting(GrantedAuthority::getAuthority)
            .containsExactlyInAnyOrder("ROLE_admin", "ROLE_MAJ");
    }

    @Test
    @DisplayName("Doit gérer les authorities non-OIDC/OAuth2 en les ignorant")
    void testMapAuthorities_WithUnknownAuthorityType_ShouldIgnore() {
        // Arrange
        SimpleGrantedAuthority simpleAuthority = new SimpleGrantedAuthority("ROLE_simple");
        Map<String, Object> oidcClaims = buildValidClaims(Arrays.asList("ROLE_admin"));
        OidcIdToken idToken = new OidcIdToken("fake-token", Instant.now(), Instant.now().plusSeconds(3600), oidcClaims);
        OidcUserAuthority oidcAuthority = new OidcUserAuthority(idToken);

        Collection<GrantedAuthority> authorities = Arrays.asList(simpleAuthority, oidcAuthority);

        // Act
        Collection<? extends GrantedAuthority> result = mapper.mapAuthorities(authorities);

        // Assert - Seulement les OIDC/OAuth2 authorities sont traitées
        assertThat(result)
            .hasSize(1)
            .extracting(GrantedAuthority::getAuthority)
            .containsExactly("ROLE_admin");
    }

    @Test
    @DisplayName("Doit retourner une liste vide si aucune authority n'est fournie")
    void testMapAuthorities_WithEmptyAuthorities_ShouldReturnEmptyList() {
        // Act
        Collection<? extends GrantedAuthority> result = mapper.mapAuthorities(Collections.emptyList());

        // Assert
        assertThat(result).isEmpty();
    }

    // ==================== Méthodes utilitaires ====================

    /**
     * Construit une structure de claims Keycloak valide avec les roles fournis
     */
    private Map<String, Object> buildValidClaims(List<String> roles) {
        Map<String, Object> claims = new HashMap<>();
        Map<String, Object> resourceAccess = new HashMap<>();
        Map<String, Object> clientData = new HashMap<>();

        clientData.put("roles", roles);
        resourceAccess.put(CLIENT_ID, clientData);
        claims.put("resource_access", resourceAccess);

        return claims;
    }
}
