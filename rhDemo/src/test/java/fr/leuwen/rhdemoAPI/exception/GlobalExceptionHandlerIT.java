package fr.leuwen.rhdemoAPI.exception;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

/**
 * Tests d'intégration pour GlobalExceptionHandler
 * Vérifie que les exceptions sont correctement interceptées et formatées
 */
@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.yml")
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class GlobalExceptionHandlerIT {

    @Autowired
    private MockMvc mockMvc;

    // ════════════════════════════════════════════════════════════════
    // Tests EmployeNotFoundException
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testEmployeNotFoundException_ShouldReturn404WithErrorResponse() throws Exception {
        mockMvc.perform(get("/api/employe").param("id", "999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").exists())
                .andExpect(jsonPath("$.timestamp").exists())
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("999")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests MethodArgumentNotValidException (validation errors)
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"MAJ"})
    public void testValidationError_WithBlankFields_ShouldReturn400() throws Exception {
        String invalidJson = """
                {
                    "prenom": "",
                    "nom": "",
                    "mail": "",
                    "adresse": ""
                }
                """;

        mockMvc.perform(post("/api/employe")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(invalidJson))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.message").value("Erreur de validation des données"))
                .andExpect(jsonPath("$.timestamp").exists())
                .andExpect(jsonPath("$.errors").exists())
                .andExpect(jsonPath("$.errors.prenom").exists())
                .andExpect(jsonPath("$.errors.nom").exists())
                .andExpect(jsonPath("$.errors.mail").exists());
    }

    @Test
    @WithMockUser(username = "user", roles = {"MAJ"})
    public void testValidationError_WithInvalidEmail_ShouldReturn400() throws Exception {
        String invalidJson = """
                {
                    "prenom": "Jean",
                    "nom": "Dupont",
                    "mail": "invalid-email",
                    "adresse": "123 Rue de Paris"
                }
                """;

        mockMvc.perform(post("/api/employe")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(invalidJson))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.message").value("Erreur de validation des données"))
                .andExpect(jsonPath("$.errors.mail").exists());
    }

    @Test
    @WithMockUser(username = "user", roles = {"MAJ"})
    public void testValidationError_WithTooLongFields_ShouldReturn400() throws Exception {
        String tooLongString = "a".repeat(101); // Dépasse la limite de 100 caractères
        String invalidJson = String.format("""
                {
                    "prenom": "%s",
                    "nom": "Dupont",
                    "mail": "jean@example.com",
                    "adresse": "123 Rue de Paris"
                }
                """, tooLongString);

        mockMvc.perform(post("/api/employe")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(invalidJson))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.errors.prenom").exists());
    }

    // ════════════════════════════════════════════════════════════════
    // Tests MethodArgumentTypeMismatchException (type errors)
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testTypeMismatchException_WithInvalidIdType_ShouldReturn400() throws Exception {
        mockMvc.perform(get("/api/employe").param("id", "not-a-number"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.message").exists())
                .andExpect(jsonPath("$.timestamp").exists())
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("id")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests pour vérifier que les exceptions de sécurité ne sont PAS interceptées
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"BadRole"})
    public void testSecurityException_ShouldNotBeCaughtByHandler() throws Exception {
        // L'exception AccessDeniedException ne doit PAS être interceptée par GlobalExceptionHandler
        // Elle doit être gérée par Spring Security
        mockMvc.perform(get("/api/employes"))
                .andExpect(status().isForbidden());
        // Note: Si GlobalExceptionHandler l'interceptait, on aurait une ErrorResponse JSON
        // Au lieu de ça, Spring Security gère directement le 403
    }
}
