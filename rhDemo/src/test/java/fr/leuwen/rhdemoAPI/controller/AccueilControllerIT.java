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
 * Tests d'intégration pour AccueilController
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
    // Tests GET /who (informations utilisateur)
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "testuser", roles = {"consult"})
    public void testWho_WithAuthenticatedUser_ShouldReturnUserInfo() throws Exception {
        mockMvc.perform(get("/who"))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("testuser")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("ROLE_consult")));
    }

    @Test
    public void testWho_WithoutAuthentication_ShouldReturnAnonymousInfo() throws Exception {
        mockMvc.perform(get("/who"))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("anonymousUser")));
    }
}
