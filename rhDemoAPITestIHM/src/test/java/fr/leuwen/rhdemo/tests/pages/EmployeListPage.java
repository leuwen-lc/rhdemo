package fr.leuwen.rhdemo.tests.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.time.Duration;
import java.util.List;

/**
 * Page Object pour la liste des employés
 */
public class EmployeListPage {
    
    private final WebDriver driver;
    private final WebDriverWait wait;
    
    // Locators utilisant data-testid pour une meilleure stabilité
    private final By employeTable = By.cssSelector("[data-testid='employes-table']");
    private final By tableRows = By.cssSelector("[data-testid='employes-table'] tbody tr");
    private final By addEmployeButton = By.cssSelector("[data-testid='add-employe-button']");
    private final By refreshButton = By.cssSelector("[data-testid='refresh-button']");
    private final By pageTitle = By.xpath("//h2[contains(text(), 'Liste de tous les Employés')]");
    
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
}
