package fr.leuwen.rhdemoAPI.controller;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Collection;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Tests unitaires pour AccueilController.
 * Teste les méthodes du contrôleur sans contexte Spring.
 */
class AccueilControllerTest {

    private final AccueilController controller = new AccueilController();

    // ════════════════════════════════════════════════════════════════
    // Tests getUserInfo (informations utilisateur JSON)
    // ════════════════════════════════════════════════════════════════

    @Test
    void getUserInfo_ShouldReturnUsernameAndRoles() {
        Authentication auth = mockAuthentication("testuser",
                List.of(new SimpleGrantedAuthority("ROLE_consult")));

        Map<String, Object> result = controller.getUserInfo(auth);

        assertThat(result).containsEntry("username", "testuser");
        @SuppressWarnings("unchecked")
        List<String> roles = (List<String>) result.get("roles");
        assertThat(roles).containsExactly("ROLE_consult");
    }

    @Test
    void getUserInfo_WithMultipleRoles_ShouldReturnAllRoles() {
        Authentication auth = mockAuthentication("admin",
                List.of(new SimpleGrantedAuthority("ROLE_consult"),
                        new SimpleGrantedAuthority("ROLE_MAJ")));

        Map<String, Object> result = controller.getUserInfo(auth);

        assertThat(result).containsEntry("username", "admin");
        @SuppressWarnings("unchecked")
        List<String> roles = (List<String>) result.get("roles");
        assertThat(roles).containsExactly("ROLE_consult", "ROLE_MAJ");
    }

    // ════════════════════════════════════════════════════════════════
    // Tests getInfo (page d'accueil)
    // ════════════════════════════════════════════════════════════════

    @Test
    void getInfo_ShouldReturnInfoPage() {
        String result = controller.getInfo();

        assertThat(result)
                .contains("API disponibles sur /api/")
                .contains("Front end disponible sur /front")
                .contains("Logout sur /logout")
                .contains("Swagger UI")
                .contains("OpenAPI");
    }

    @SuppressWarnings("unchecked")
    private Authentication mockAuthentication(String username,
            Collection<? extends GrantedAuthority> authorities) {
        Authentication auth = mock(Authentication.class);
        when(auth.getName()).thenReturn(username);
        when((Collection<GrantedAuthority>) auth.getAuthorities())
                .thenReturn((Collection<GrantedAuthority>) authorities);
        return auth;
    }
}
