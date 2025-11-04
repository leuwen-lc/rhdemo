package fr.leuwen.rhdemo.tests;

import fr.leuwen.rhdemo.tests.base.BaseSeleniumTest;
import fr.leuwen.rhdemo.tests.config.TestConfig;
import fr.leuwen.rhdemo.tests.pages.EmployeAddPage;
import fr.leuwen.rhdemo.tests.pages.EmployeDeletePage;
import fr.leuwen.rhdemo.tests.pages.EmployeListPage;
import org.junit.jupiter.api.*;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Test du cycle complet de gestion d'un employé :
 * 1. Ajout d'un employé
 * 2. Vérification de sa présence dans la liste
 * 3. Suppression de l'employé
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
public class EmployeLifecycleTest extends BaseSeleniumTest {
    
    private static EmployeAddPage addPage;
    private static EmployeListPage listPage;
    private static EmployeDeletePage deletePage;
    
    // Données de test
    private static final String TEST_PRENOM = "Selenium";
    private static final String TEST_NOM = "TestUser";
    private static final String TEST_EMAIL = "selenium.test@example.com";
    private static final String TEST_ADRESSE = "123 Test Street, Selenium City";
    private static String employeId; // ID de l'employé créé (sera récupéré après l'ajout)
    
    @BeforeAll
    public static void setUpTests() {
        // Initialisation des pages après le setup du driver
        addPage = new EmployeAddPage(driver);
        listPage = new EmployeListPage(driver);
        deletePage = new EmployeDeletePage(driver);
    }
    
    @Test
    @Order(1)
    @DisplayName("1. Ajout d'un nouvel employé")
    public void testAddEmploye() {
        System.out.println("🔵 ÉTAPE 1: Ajout d'un nouvel employé");
        
        // Aller sur la page d'ajout
        driver.get(TestConfig.EMPLOYE_ADD_URL);
        
        // Remplir le formulaire
        addPage.fillEmployeForm(TEST_PRENOM, TEST_NOM, TEST_EMAIL, TEST_ADRESSE);
        
        // Soumettre le formulaire
        addPage.clickAddButton();
        
        // Vérifier que le message de succès s'affiche
        assertThat(addPage.isSuccessMessageDisplayed())
            .as("Le message de succès devrait être affiché")
            .isTrue();
        
        String successMessage = addPage.getSuccessMessage();
        assertThat(successMessage)
            .as("Le message devrait confirmer l'ajout")
            .containsIgnoringCase("succès");
        
        // Attendre la redirection vers la liste
        addPage.waitForRedirectToEmployesList();
        
        System.out.println("✅ Employé ajouté avec succès");
    }
    
    @Test
    @Order(2)
    @DisplayName("2. Vérification de la présence de l'employé dans la liste")
    public void testEmployePresentInList() {
        System.out.println("🔵 ÉTAPE 2: Vérification de la présence dans la liste");
        
        // Aller sur la page de liste
        driver.get(TestConfig.EMPLOYES_LIST_URL);
        
        // Attendre que la table soit chargée
        listPage.waitForTableToLoad();
        
        // Vérifier que la page est bien chargée
        assertThat(listPage.isPageLoaded())
            .as("La page de liste devrait être chargée")
            .isTrue();
        
        // Vérifier si la pagination est présente
        boolean hasPagination = listPage.isPaginationPresent();
        System.out.println("Pagination présente: " + (hasPagination ? "Oui" : "Non"));
        
        if (hasPagination) {
            // Avec pagination: l'employé est sur la dernière page (ajout récent)
            System.out.println("Navigation vers la dernière page...");
            listPage.goToLastPage();
            
            // Vérifier que l'employé est présent sur la dernière page
            assertThat(listPage.isEmployePresentByEmail(TEST_EMAIL))
                .as("L'employé devrait être présent sur la dernière page")
                .isTrue();
            
            // Récupérer l'ID sur cette page
            employeId = listPage.getEmployeIdByEmail(TEST_EMAIL);
        } else {
            // Sans pagination: recherche simple
            assertThat(listPage.isEmployePresentByEmail(TEST_EMAIL))
                .as("L'employé devrait être présent dans la liste")
                .isTrue();
            
            employeId = listPage.getEmployeIdByEmail(TEST_EMAIL);
        }
        
        assertThat(employeId)
            .as("L'ID de l'employé devrait être récupéré")
            .isNotNull()
            .isNotEmpty();
        
        System.out.println("✅ Employé trouvé dans la liste avec l'ID: " + employeId);
        
        // Vérifier que les données complètes sont présentes
        String employeData = listPage.getEmployeDataByEmail(TEST_EMAIL);
        assertThat(employeData)
            .as("Les données de l'employé devraient contenir toutes les informations")
            .contains(TEST_PRENOM, TEST_NOM, TEST_EMAIL);
        
        System.out.println("✅ Toutes les données de l'employé sont correctes");
    }
    
    @Test
    @Order(3)
    @DisplayName("3. Suppression de l'employé")
    public void testDeleteEmploye() {
        System.out.println("🔵 ÉTAPE 3: Suppression de l'employé");
        
        // Si l'ID n'est pas défini, le récupérer
        if (employeId == null || employeId.isEmpty()) {
            driver.get(TestConfig.EMPLOYES_LIST_URL);
            listPage.waitForTableToLoad();
            employeId = listPage.getEmployeIdByEmail(TEST_EMAIL);
            assertThat(employeId)
                .as("L'ID de l'employé doit être disponible pour la suppression")
                .isNotNull()
                .isNotEmpty();
        }
        
        System.out.println("ID de l'employé à supprimer: " + employeId);
        
        // Aller sur la page de suppression
        driver.get(TestConfig.EMPLOYE_DELETE_URL);
        
        // Rechercher l'employé par ID
        deletePage.searchEmployeById(employeId);
        
        // Vérifier que les détails sont affichés
        assertThat(deletePage.areEmployeDetailsDisplayed())
            .as("Les détails de l'employé devraient être affichés")
            .isTrue();
        
        // Vérifier que les détails contiennent les bonnes informations
        assertThat(deletePage.detailsContain(TEST_PRENOM))
            .as("Les détails devraient contenir le prénom")
            .isTrue();
        assertThat(deletePage.detailsContain(TEST_NOM))
            .as("Les détails devraient contenir le nom")
            .isTrue();
        assertThat(deletePage.detailsContain(TEST_EMAIL))
            .as("Les détails devraient contenir l'email")
            .isTrue();
        
        System.out.println("✅ Employé trouvé, lancement de la suppression...");
        
        // Supprimer l'employé
        deletePage.clickDeleteButton();
        deletePage.confirmDeletion();
        
        // Vérifier le message de succès
        assertThat(deletePage.isSuccessMessageDisplayed())
            .as("Le message de succès de suppression devrait être affiché")
            .isTrue();
        
        System.out.println("✅ Employé supprimé avec succès");
    }
    
    @Test
    @Order(4)
    @DisplayName("4. Vérification que l'employé n'est plus dans la liste")
    public void testEmployeNotInListAfterDeletion() {
        System.out.println("🔵 ÉTAPE 4: Vérification de l'absence de l'employé dans la liste");
        
        // Aller sur la page de liste
        driver.get(TestConfig.EMPLOYES_LIST_URL);
        
        // Attendre que la table soit chargée
        listPage.waitForTableToLoad();
        
        // Actualiser la liste pour s'assurer d'avoir les données à jour
        listPage.clickRefreshButton();
        
        // Vérifier avec gestion de pagination
        boolean employeStillPresent;
        if (listPage.isPaginationPresent()) {
            // Recherche dans toutes les pages
            employeStillPresent = listPage.findEmployeByEmailAcrossPages(TEST_EMAIL);
        } else {
            // Recherche simple
            employeStillPresent = listPage.isEmployePresentByEmail(TEST_EMAIL);
        }
        
        // Vérifier que l'employé n'est plus présent
        assertThat(employeStillPresent)
            .as("L'employé ne devrait plus être présent dans la liste")
            .isFalse();
        
        System.out.println("✅ Employé bien supprimé de la liste");
        System.out.println("🎉 Test complet du cycle de vie terminé avec succès!");
    }
}
