package fr.leuwen.rhdemo.tests.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.List;

/**
 * Page Object pour la liste des employés
 */
public class EmployeListPage {

    private static final Logger logger = LoggerFactory.getLogger(EmployeListPage.class);

    private final WebDriver driver;
    private final WebDriverWait wait;
    
    // Locators utilisant data-testid pour une meilleure stabilité
    private final By employeTable = By.cssSelector("[data-testid='employes-table']");
    private final By tableRows = By.cssSelector("[data-testid='employes-table'] tbody tr");
    private final By addEmployeButton = By.cssSelector("[data-testid='add-employe-button']");
    private final By refreshButton = By.cssSelector("[data-testid='refresh-button']");
    private final By pageTitle = By.xpath("//h2[contains(text(), 'Liste de tous les Employés')]");

    // Locators pour la pagination
    private final By pagination = By.cssSelector("[data-testid='pagination']");
    private final By paginationPrevButton = By.cssSelector("[data-testid='pagination'] button.btn-prev");
    private final By paginationNextButton = By.cssSelector("[data-testid='pagination'] button.btn-next");
    private final By paginationNumbers = By.cssSelector("[data-testid='pagination'] .el-pager li");
    private final By paginationTotal = By.cssSelector("[data-testid='pagination'] .el-pagination__total");
    
    public EmployeListPage(WebDriver driver) {
        this.driver = driver;
        this.wait = new WebDriverWait(driver, Duration.ofSeconds(15));
    }
    
    /**
     * Attend que la table soit chargée
     */
    public void waitForTableToLoad() {
        wait.until(ExpectedConditions.visibilityOfElementLocated(employeTable));
    }
    
    /**
     * Récupère toutes les lignes du tableau
     */
    public List<WebElement> getAllEmployeRows() {
        waitForTableToLoad();
        return driver.findElements(tableRows);
    }
    
    /**
     * Compte le nombre d'employés dans la liste
     */
    public int getEmployeCount() {
        waitForTableToLoad();
        return getAllEmployeRows().size();
    }
    
    /**
     * Vérifie si un employé est présent dans la liste par son email
     */
    public boolean isEmployePresentByEmail(String email) {
        waitForTableToLoad();
        List<WebElement> rows = getAllEmployeRows();
        
        for (WebElement row : rows) {
            String rowText = row.getText();
            if (rowText.contains(email)) {
                return true;
            }
        }
        return false;
    }
    
    /**
     * Vérifie si un employé est présent par prénom et nom
     */
    public boolean isEmployePresentByName(String prenom, String nom) {
        waitForTableToLoad();
        List<WebElement> rows = getAllEmployeRows();
        
        for (WebElement row : rows) {
            String rowText = row.getText();
            if (rowText.contains(prenom) && rowText.contains(nom)) {
                return true;
            }
        }
        return false;
    }
    
    /**
     * Récupère l'ID d'un employé par son email
     */
    public String getEmployeIdByEmail(String email) {
        waitForTableToLoad();
        List<WebElement> rows = getAllEmployeRows();
        
        for (WebElement row : rows) {
            String rowText = row.getText();
            if (rowText.contains(email)) {
                // L'ID est dans la première colonne
                WebElement firstCell = row.findElement(By.cssSelector("td:first-child"));
                return firstCell.getText().trim();
            }
        }
        return null;
    }
    
    /**
     * Récupère toutes les données d'un employé par son email
     */
    public String getEmployeDataByEmail(String email) {
        waitForTableToLoad();
        List<WebElement> rows = getAllEmployeRows();
        
        for (WebElement row : rows) {
            String rowText = row.getText();
            if (rowText.contains(email)) {
                return rowText;
            }
        }
        return null;
    }
    
    /**
     * Clique sur le bouton "Ajouter un employé"
     */
    public void clickAddEmployeButton() {
        wait.until(ExpectedConditions.elementToBeClickable(addEmployeButton));
        driver.findElement(addEmployeButton).click();
    }
    
    /**
     * Clique sur le bouton "Actualiser"
     */
    public void clickRefreshButton() {
        wait.until(ExpectedConditions.elementToBeClickable(refreshButton));
        driver.findElement(refreshButton).click();
        waitForTableToLoad();
    }
    
    /**
     * Vérifie si la page est chargée
     */
    public boolean isPageLoaded() {
        try {
            wait.until(ExpectedConditions.visibilityOfElementLocated(pageTitle));
            return true;
        } catch (Exception e) {
            return false;
        }
    }
    
    /**
     * Clique sur le bouton "Voir" pour un employé spécifique par email
     */
    public void clickViewButtonForEmploye(String email) {
        waitForTableToLoad();
        List<WebElement> rows = getAllEmployeRows();
        
        for (WebElement row : rows) {
            if (row.getText().contains(email)) {
                // Récupérer l'ID depuis la première colonne
                WebElement firstCell = row.findElement(By.cssSelector("td:first-child"));
                String employeId = firstCell.getText().trim();
                
                // Utiliser le data-testid avec l'ID
                WebElement viewButton = row.findElement(By.cssSelector("[data-testid='view-button-" + employeId + "']"));
                viewButton.click();
                break;
            }
        }
    }
    
    /**
     * Clique sur le bouton "Editer" pour un employé spécifique par ID
     */
    public void clickEditButtonForEmploye(String employeId) {
        waitForTableToLoad();
        WebElement editButton = driver.findElement(By.cssSelector("[data-testid='edit-button-" + employeId + "']"));
        editButton.click();
    }
    
    /**
     * Clique sur le bouton "Supprimer" pour un employé spécifique par ID
     */
    public void clickDeleteButtonForEmploye(String employeId) {
        waitForTableToLoad();
        WebElement deleteButton = driver.findElement(By.cssSelector("[data-testid='delete-button-" + employeId + "']"));
        deleteButton.click();
    }
    
    // ============= MÉTHODES DE PAGINATION =============
    
    /**
     * Vérifie si la pagination est présente sur la page
     */
    public boolean isPaginationPresent() {
        try {
            return driver.findElement(pagination).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }
    
    /**
     * Récupère le nombre total d'éléments depuis la pagination
     */
    public int getTotalElementsFromPagination() {
        if (!isPaginationPresent()) {
            return getEmployeCount();
        }
        
        try {
            WebElement totalElement = driver.findElement(paginationTotal);
            String totalText = totalElement.getText(); // Format: "Total: 303"
            return Integer.parseInt(totalText.replaceAll("[^0-9]", ""));
        } catch (Exception e) {
            return 0;
        }
    }
    
    /**
     * Navigue vers la dernière page en cliquant sur le dernier numéro de page
     */
    public void goToLastPage() {
        if (!isPaginationPresent()) {
            return; // Pas de pagination, déjà sur la seule page
        }
        
        try {
            // Trouver tous les numéros de page
            List<WebElement> pageNumbers = driver.findElements(paginationNumbers);
            
            if (!pageNumbers.isEmpty()) {
                // Le dernier élément non-actif est la dernière page
                WebElement lastPageNumber = null;
                for (WebElement pageNumber : pageNumbers) {
                    if (!pageNumber.getAttribute("class").contains("is-active") 
                        && !pageNumber.getAttribute("class").contains("more")) {
                        lastPageNumber = pageNumber;
                    }
                }
                
                if (lastPageNumber != null) {
                    lastPageNumber.click();
                    waitForTableToLoad();
                    // Attendre que la page soit chargée
                    Thread.sleep(1000);
                }
            }
        } catch (Exception e) {
            System.err.println("Erreur lors de la navigation vers la dernière page: " + e.getMessage());
        }
    }
    
    /**
     * Navigue vers la page suivante
     */
    public void goToNextPage() {
        if (!isPaginationPresent()) {
            return;
        }
        
        try {
            WebElement nextButton = driver.findElement(paginationNextButton);
            if (nextButton.isEnabled()) {
                nextButton.click();
                waitForTableToLoad();
                Thread.sleep(500);
            }
        } catch (Exception e) {
            System.err.println("Erreur lors de la navigation vers la page suivante: " + e.getMessage());
        }
    }
    
    /**
     * Navigue vers la page précédente
     */
    public void goToPreviousPage() {
        if (!isPaginationPresent()) {
            return;
        }
        
        try {
            WebElement prevButton = driver.findElement(paginationPrevButton);
            if (prevButton.isEnabled()) {
                prevButton.click();
                waitForTableToLoad();
                Thread.sleep(500);
            }
        } catch (Exception e) {
            System.err.println("Erreur lors de la navigation vers la page précédente: " + e.getMessage());
        }
    }
    
    /**
     * Cherche un employé par email dans toutes les pages (pagination robuste)
     * Commence par la dernière page (où se trouvent les nouveaux employés)
     */
    public boolean findEmployeByEmailAcrossPages(String email) {
        if (!isPaginationPresent()) {
            // Pas de pagination, recherche simple
            return isEmployePresentByEmail(email);
        }
        
        // D'abord vérifier la dernière page (les nouveaux employés y sont)
        goToLastPage();
        if (isEmployePresentByEmail(email)) {
            return true;
        }
        
        // Si pas trouvé, parcourir toutes les pages depuis le début
        goToFirstPage();
        
        do {
            if (isEmployePresentByEmail(email)) {
                return true;
            }
        } while (goToNextPageIfPossible());
        
        return false;
    }
    
    /**
     * Navigue vers la première page
     */
    public void goToFirstPage() {
        if (!isPaginationPresent()) {
            return;
        }
        
        try {
            List<WebElement> pageNumbers = driver.findElements(paginationNumbers);
            if (!pageNumbers.isEmpty()) {
                // Le premier élément est toujours la page 1
                pageNumbers.get(0).click();
                waitForTableToLoad();
                Thread.sleep(500);
            }
        } catch (Exception e) {
            System.err.println("Erreur lors de la navigation vers la première page: " + e.getMessage());
        }
    }
    
    /**
     * Navigue vers la page suivante si possible
     * @return true si la navigation a réussi, false sinon (dernière page)
     */
    private boolean goToNextPageIfPossible() {
        if (!isPaginationPresent()) {
            return false;
        }
        
        try {
            WebElement nextButton = driver.findElement(paginationNextButton);
            if (nextButton.isEnabled() && !nextButton.getAttribute("class").contains("disabled")) {
                nextButton.click();
                waitForTableToLoad();
                Thread.sleep(500);
                return true;
            }
        } catch (Exception e) {
            // Fin de pagination ou erreur
        }
        return false;
    }
    
    /**
     * Récupère l'ID d'un employé par email en parcourant toutes les pages si nécessaire
     */
    public String getEmployeIdByEmailAcrossPages(String email) {
        if (!isPaginationPresent()) {
            return getEmployeIdByEmail(email);
        }
        
        // Commencer par la dernière page
        goToLastPage();
        String employeId = getEmployeIdByEmail(email);
        if (employeId != null) {
            return employeId;
        }
        
        // Parcourir depuis le début
        goToFirstPage();
        do {
            employeId = getEmployeIdByEmail(email);
            if (employeId != null) {
                return employeId;
            }
        } while (goToNextPageIfPossible());
        
        return null;
    }
}
