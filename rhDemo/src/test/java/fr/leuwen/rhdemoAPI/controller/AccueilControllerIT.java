package fr.leuwen.rhdemoAPI.controller;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

/**
 * Tests d'integration pour AccueilController
 * Teste les endpoints d'information et d'accueil
 */
@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.yml")
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class AccueilControllerIT {

    @Autowired
    private MockMvc mockMvc;

    // ════════════════════════════════════════════════════════════════
    // Tests GET / (page d'accueil)
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testAccueil_ShouldReturnWelcomeMessage() throws Exception {
        mockMvc.perform(get("/"))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("API")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests GET /api/userinfo (informations utilisateur JSON)
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "testuser", roles = {"consult"})
    public void testUserInfo_WithConsultRole_ShouldReturnUsernameAndRoles() throws Exception {
        mockMvc.perform(get("/api/userinfo"))
                .andExpect(status().isOk())
                .andExpect(content().contentType("application/json"))
                .andExpect(jsonPath("$.username").value("testuser"))
                .andExpect(jsonPath("$.roles").isArray())
                .andExpect(jsonPath("$.roles[0]").value("ROLE_consult"));
    }

    @Test
    @WithMockUser(username = "madjid", roles = {"consult", "MAJ"})
    public void testUserInfo_WithMultipleRoles_ShouldReturnAllRoles() throws Exception {
        mockMvc.perform(get("/api/userinfo"))
                .andExpect(status().isOk())
                .andExpect(content().contentType("application/json"))
                .andExpect(jsonPath("$.username").value("madjid"))
                .andExpect(jsonPath("$.roles").isArray())
                .andExpect(jsonPath("$.roles.length()").value(2));
    }
}
