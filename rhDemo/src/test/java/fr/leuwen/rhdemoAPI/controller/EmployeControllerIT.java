package fr.leuwen.rhdemoAPI.controller;

import static org.hamcrest.CoreMatchers.is;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import fr.leuwen.rhdemoAPI.config.TestDataLoader;

/**
 * Tests d'intégration pour EmployeController
 * Teste les endpoints REST avec autorisation et validation
 *
 * Note: Les données de test sont chargées via TestDataLoader au démarrage du contexte Spring.
 */
@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.yml")
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(TestDataLoader.class)
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
                .andExpect(jsonPath("$.page.totalElements").value(4))
                .andExpect(jsonPath("$.page.size").value(20))
                .andExpect(jsonPath("$.page.number").value(0));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_CustomPageSize_ShouldReturnCorrectSize() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("page", "0")
                        .param("size", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content.length()").value(2))
                .andExpect(jsonPath("$.page.size").value(2));
    }

    @Test
    @WithMockUser(username = "user", roles = {"BadRole"})
    public void testGetEmployesPage_WithWrongRole_ShouldReturn403() throws Exception {
        mockMvc.perform(get("/api/employes/page"))
                .andExpect(status().isForbidden());
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_WithSort_ShouldReturnSortedList() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("page", "0")
                        .param("size", "20")
                        .param("sort", "nom")
                        .param("order", "ASC"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content").isArray())
                .andExpect(jsonPath("$.content[0].nom").value("Bernard"))
                .andExpect(jsonPath("$.content[1].nom").value("Dubois"));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_WithSortDesc_ShouldReturnSortedListDescending() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("page", "0")
                        .param("size", "20")
                        .param("sort", "prenom")
                        .param("order", "DESC"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content").isArray())
                .andExpect(jsonPath("$.content[0].prenom").value("Sophie"))
                .andExpect(jsonPath("$.content[1].prenom").value("Pierre"));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_WithoutSort_ShouldReturnUnsortedList() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("page", "0")
                        .param("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content").isArray())
                .andExpect(jsonPath("$.content.length()").value(4));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests GET /api/employes/page avec filtres
    // ════════════════════════════════════════════════════════════════

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_FilterByNom_ShouldReturnMatchingEmployes() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("filterNom", "Martin"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page.totalElements").value(1))
                .andExpect(jsonPath("$.content[0].nom").value("Martin"));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_FilterByPrenom_ShouldReturnMatchingEmployes() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("filterPrenom", "Sophie"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page.totalElements").value(1))
                .andExpect(jsonPath("$.content[0].prenom").value("Sophie"));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_FilterCombined_ShouldReturnIntersection() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("filterPrenom", "Sophie")
                        .param("filterNom", "Dubois"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page.totalElements").value(1))
                .andExpect(jsonPath("$.content[0].prenom").value("Sophie"))
                .andExpect(jsonPath("$.content[0].nom").value("Dubois"));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_FilterNoResult_ShouldReturnEmptyPage() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("filterNom", "Inexistant"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page.totalElements").value(0))
                .andExpect(jsonPath("$.content").isArray())
                .andExpect(jsonPath("$.content.length()").value(0));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_FilterCaseInsensitive_ShouldMatch() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("filterNom", "martin"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page.totalElements").value(1))
                .andExpect(jsonPath("$.content[0].nom").value("Martin"));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_FilterWithPagination_ShouldRespectPageSize() throws Exception {
        // filterMail="example" matches all 4 employees, but size=1 should return only 1
        mockMvc.perform(get("/api/employes/page")
                        .param("filterMail", "example")
                        .param("size", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content.length()").value(1))
                .andExpect(jsonPath("$.page.totalElements").value(4))
                .andExpect(jsonPath("$.page.totalPages").value(4));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_FilterWithSort_ShouldFilterAndSort() throws Exception {
        // filterNom with "D" matches Dubois and Durand, sorted by prenom ASC → Marie, Sophie
        mockMvc.perform(get("/api/employes/page")
                        .param("filterNom", "Du")
                        .param("sort", "prenom")
                        .param("order", "ASC"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page.totalElements").value(2))
                .andExpect(jsonPath("$.content[0].prenom").value("Marie"))
                .andExpect(jsonPath("$.content[1].prenom").value("Sophie"));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_NoFilters_ShouldReturnAllEmployes() throws Exception {
        // Retrocompatibility: no filter params should return all employees
        mockMvc.perform(get("/api/employes/page"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page.totalElements").value(4));
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testGetEmployesPage_FilterByAdresse_ShouldReturnMatchingEmployes() throws Exception {
        mockMvc.perform(get("/api/employes/page")
                        .param("filterAdresse", "Paris"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page.totalElements").value(1))
                .andExpect(jsonPath("$.content[0].adresse", is("1 Rue de la Paix, Paris")));
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
                        .with(csrf())
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
                        .with(csrf())
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
                        .with(csrf())
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
                        .with(csrf())
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
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(newEmployeJson))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        // Extraire l'ID de la réponse (simple parsing)
        String id = createResponse.split("\"id\":")[1].split(",")[0];

        // Supprimer l'employé
        mockMvc.perform(delete("/api/employe")
                        .with(csrf())
                        .param("id", id))
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
        mockMvc.perform(delete("/api/employe")
                        .with(csrf())
                        .param("id", "999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").exists());
    }

    @Test
    @WithMockUser(username = "user", roles = {"consult"})
    public void testDeleteEmploye_WithConsultRole_ShouldReturn403() throws Exception {
        mockMvc.perform(delete("/api/employe")
                        .with(csrf())
                        .param("id", "1"))
                .andExpect(status().isForbidden());
    }
}
