package fr.leuwen.rhdemoAPI.springconfig;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Tests d'intégration pour la matrice d'autorisation (TestSecurityConfig en profil "test").
 *
 * Note: les tests de directives CSP ont été déplacés dans CspPolicyBuilderTest (tests unitaires
 * sur la vraie classe de production). Auparavant, les tests CSP exécutés ici portaient sur
 * TestSecurityConfig (configuration dupliquée des tests), ce qui donnait une fausse confiance
 * sur le CSP réellement servi en production.
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DisplayName("SecurityConfig - Tests d'intégration (matrice d'autorisation)")
class SecurityConfigIT {

    @Autowired
    private MockMvc mockMvc;

    @Test
    @DisplayName("GET /actuator/health doit être accessible sans authentification (Kubernetes probe)")
    void testActuatorHealth_ShouldBePublic() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(status().isOk());
    }

    @Test
    @DisplayName("GET /actuator/health doit être accessible avec le role ROLE_admin")
    @WithMockUser(roles = {"admin"})
    void testActuatorEndpoint_WithAdminRole_ShouldBeAccessible() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(status().isOk());
    }

    @Test
    @DisplayName("GET /actuator/loggers doit refuser l'accès sans role admin (Spring Security bloque avant le routing)")
    @WithMockUser(roles = {"consult"})
    void testActuatorEndpoint_WithoutAdminRole_ShouldBeForbidden() throws Exception {
        mockMvc.perform(get("/actuator/loggers"))
            .andExpect(status().isForbidden());
    }

    @Test
    @DisplayName("GET /actuator/loggers doit refuser l'accès sans authentification")
    void testActuatorEndpoint_WithoutAuthentication_ShouldBeUnauthorized() throws Exception {
        mockMvc.perform(get("/actuator/loggers"))
            .andExpect(status().isUnauthorized());
    }
}
