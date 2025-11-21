package fr.leuwen.rhdemoAPI.controller;

import static org.hamcrest.CoreMatchers.is;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

/**
 * Tests d'intégration pour EmployeController
 * Teste les endpoints REST avec autorisation et validation
 */
@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.yml")
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class EmployeControllerIT {

    @Autowired
    private MockMvc mockMvc;

    // ════════════════════════════════════════════════════════════════
    // Tests GET /api/employes (liste complète)
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployes_WithConsultRole_ShouldReturnList() throws Exception {
        mockMvc.perform(get("/api/employes"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray())
                .andExpect(jsonPath("$.length()").value(4))
                .andExpect(jsonPath("$[0].prenom", is("Laurent")));
    }

    @Test
    @WithMockUser(username = "user", roles = {"BadRole"})
    public void testGetEmployes_WithWrongRole_ShouldReturn403() throws Exception {
        mockMvc.perform(get("/api/employes"))
                .andExpect(status().isForbidden());
    }

    // ════════════════════════════════════════════════════════════════
    // Tests GET /api/employes/page (pagination)
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_DefaultParams_ShouldReturnFirstPage() throws Exception {
        mockMvc.perform(get("/api/employes/page"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content").isArray())
                .andExpect(jsonPath("$.totalElements").value(4))
                .andExpect(jsonPath("$.size").value(20))
                .andExpect(jsonPath("$.number").value(0));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_CustomPageSize_ShouldReturnCorrectSize() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("page", "0")
                        .param("size", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content.length()").value(2))
                .andExpect(jsonPath("$.size").value(2));
    }

    @Test
    @WithMockUser(username = "user", roles = {"BadRole"})
    public void testGetEmployesPage_WithWrongRole_ShouldReturn403() throws Exception {
        mockMvc.perform(get("/api/employes/page"))
                .andExpect(status().isForbidden());
    }

    // ════════════════════════════════════════════════════════════════
    // Tests GET /api/employe?id=X (récupération)
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmploye_WithValidId_ShouldReturnEmploye() throws Exception {
        mockMvc.perform(get("/api/employe").param("id", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(1))
                .andExpect(jsonPath("$.prenom").exists())
                .andExpect(jsonPath("$.nom").exists());
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmploye_WithInvalidId_ShouldReturn404() throws Exception {
        mockMvc.perform(get("/api/employe").param("id", "999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").exists());
    }

    @Test
    @WithMockUser(username = "user", roles = {"BadRole"})
    public void testGetEmploye_WithWrongRole_ShouldReturn403() throws Exception {
        mockMvc.perform(get("/api/employe").param("id", "1"))
                .andExpect(status().isForbidden());
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmploye_WithInvalidIdType_ShouldReturn400() throws Exception {
        mockMvc.perform(get("/api/employe").param("id", "invalid"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").exists());
    }

    // ════════════════════════════════════════════════════════════════
    // Tests POST /api/employe (création/modification)
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"MAJ"})
    public void testSaveEmploye_WithValidData_ShouldReturn200() throws Exception {
        String validEmployeJson = """
                {
                    "prenom": "Jean",
                    "nom": "Dupont",
                    "mail": "jean.dupont@example.com",
                    "adresse": "123 Rue de Paris"
                }
                """;

        mockMvc.perform(post("/api/employe")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validEmployeJson))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").exists())
                .andExpect(jsonPath("$.prenom").value("Jean"))
                .andExpect(jsonPath("$.nom").value("Dupont"))
                .andExpect(jsonPath("$.mail").value("jean.dupont@example.com"));
    }

    @Test
    @WithMockUser(username = "user", roles = {"MAJ"})
    public void testSaveEmploye_WithInvalidEmail_ShouldReturn400() throws Exception {
        String invalidEmployeJson = """
                {
                    "prenom": "Jean",
                    "nom": "Dupont",
                    "mail": "invalid-email",
                    "adresse": "123 Rue de Paris"
                }
                """;

        mockMvc.perform(post("/api/employe")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(invalidEmployeJson))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Erreur de validation des données"))
                .andExpect(jsonPath("$.errors").exists());
    }

    @Test
    @WithMockUser(username = "user", roles = {"MAJ"})
    public void testSaveEmploye_WithMissingFields_ShouldReturn400() throws Exception {
        String invalidEmployeJson = """
                {
                    "prenom": "",
                    "nom": "",
                    "mail": "",
                    "adresse": ""
                }
                """;

        mockMvc.perform(post("/api/employe")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(invalidEmployeJson))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Erreur de validation des données"))
                .andExpect(jsonPath("$.errors").exists());
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testSaveEmploye_WithConsultRole_ShouldReturn403() throws Exception {
        String validEmployeJson = """
                {
                    "prenom": "Jean",
                    "nom": "Dupont",
                    "mail": "jean.dupont@example.com",
                    "adresse": "123 Rue de Paris"
                }
                """;

        mockMvc.perform(post("/api/employe")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validEmployeJson))
                .andExpect(status().isForbidden());
    }

    // ════════════════════════════════════════════════════════════════
    // Tests DELETE /api/employe?id=X (suppression)
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"MAJ"})
    @DirtiesContext
    public void testDeleteEmploye_WithValidId_ShouldReturn200() throws Exception {
        // D'abord créer un employé à supprimer
        String newEmployeJson = """
                {
                    "prenom": "ToDelete",
                    "nom": "Test",
                    "mail": "todelete@example.com",
                    "adresse": "123 Test Street"
                }
                """;

        String createResponse = mockMvc.perform(post("/api/employe")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(newEmployeJson))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        // Extraire l'ID de la réponse (simple parsing)
        String id = createResponse.split("\"id\":")[1].split(",")[0];

        // Supprimer l'employé
        mockMvc.perform(delete("/api/employe").param("id", id))
                .andExpect(status().isOk());

        // Vérifier que l'employé n'existe plus (avec authentification)
        mockMvc.perform(get("/api/employe")
                        .param("id", id)
                        .with(org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user("user").roles("consult")))
                .andExpect(status().isNotFound());
    }

    @Test
    @WithMockUser(username = "user", roles = {"MAJ"})
    public void testDeleteEmploye_WithInvalidId_ShouldReturn404() throws Exception {
        mockMvc.perform(delete("/api/employe").param("id", "999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").exists());
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testDeleteEmploye_WithConsultRole_ShouldReturn403() throws Exception {
        mockMvc.perform(delete("/api/employe").param("id", "1"))
                .andExpect(status().isForbidden());
    }
}
