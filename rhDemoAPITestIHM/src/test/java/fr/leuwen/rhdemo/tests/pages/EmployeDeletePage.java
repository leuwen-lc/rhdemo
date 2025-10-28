package fr.leuwen.rhdemo.tests.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.time.Duration;

/**
 * Page Object pour la page de suppression d'un employé
 */
public class EmployeDeletePage {
    
    private final WebDriver driver;
    private final WebDriverWait wait;
    
    // Locators utilisant data-testid pour une meilleure stabilité
    private final By idInput = By.cssSelector("[data-testid='delete-id-input']");
    private final By searchButton = By.cssSelector("[data-testid='search-employe-button']");
    private final By employeDetails = By.cssSelector("[data-testid='employe-details']");
    private final By deleteButton = By.cssSelector("[data-testid='confirm-delete-button']");
    //private final By confirmButton = By.cssSelector("[data-testid='confirm-deletex2-button']"); 
    //private final By confirmButton = By.xpath("//button[contains(text(), 'Oui, supprimer')]");
    private final By confirmButton = By.xpath("//html/body/div[2]/div/div/div[2]/button[2]");
    private final By cancelButton = By.cssSelector("[data-testid='cancel-delete-button']");
    private final By successMessage = By.cssSelector("[data-testid='delete-success-alert']");
    private final By errorAlert = By.cssSelector("[data-testid='delete-error-alert']");
    
    public EmployeDeletePage(WebDriver driver) {
        this.driver = driver;
        this.wait = new WebDriverWait(driver, Duration.ofSeconds(15));
    }
    
    /**
     * Recherche un employé par son ID
     */
    public void searchEmployeById(String id) {
        wait.until(ExpectedConditions.visibilityOfElementLocated(idInput));
        driver.findElement(idInput).clear();
        driver.findElement(idInput).sendKeys(id);
        
        wait.until(ExpectedConditions.elementToBeClickable(searchButton));
        driver.findElement(searchButton).click();
    }
    
    /**
     * Vérifie si les détails de l'employé sont affichés
     */
    public boolean areEmployeDetailsDisplayed() {
        try {
            wait.until(ExpectedConditions.visibilityOfElementLocated(employeDetails));
            return driver.findElement(employeDetails).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }
    
    /**
     * Récupère les détails affichés de l'employé
     */
    public String getEmployeDetails() {
        wait.until(ExpectedConditions.visibilityOfElementLocated(employeDetails));
        return driver.findElement(employeDetails).getText();
    }
    
    /**
     * Vérifie si les détails contiennent les informations attendues
     */
    public boolean detailsContain(String text) {
        String details = getEmployeDetails();
        return details.contains(text);
    }
    
    /**
     * Clique sur le bouton Supprimer
     */
    public void clickDeleteButton() {
        wait.until(ExpectedConditions.elementToBeClickable(deleteButton));
        driver.findElement(deleteButton).click();
    }
    
    /**
     * Confirme la suppression dans la boîte de dialogue
     */
    public void confirmDeletion() {
        // Attendre que la boîte de dialogue de confirmation apparaisse
        wait.until(ExpectedConditions.visibilityOfElementLocated(By.cssSelector(".el-message-box, .el-popconfirm")));
        
        // Cliquer sur le bouton de confirmation
        wait.until(ExpectedConditions.elementToBeClickable(confirmButton));
        driver.findElement(confirmButton).click();
    }
    
    /**
     * Annule la suppression
     */
    public void cancelDeletion() {
        wait.until(ExpectedConditions.elementToBeClickable(cancelButton));
        driver.findElement(cancelButton).click();
    }
    
    /**
     * Supprime un employé (recherche + suppression + confirmation)
     */
    public void deleteEmployeById(String id) {
        searchEmployeById(id);
        clickDeleteButton();
        confirmDeletion();
    }
    
    /**
     * Vérifie si le message de succès est affiché
     */
    public boolean isSuccessMessageDisplayed() {
        try {
            wait.until(ExpectedConditions.visibilityOfElementLocated(successMessage));
            return true;
        } catch (Exception e) {
            return false;
        }
    }
    
    /**
     * Récupère le message de succès
     */
    public String getSuccessMessage() {
        wait.until(ExpectedConditions.visibilityOfElementLocated(successMessage));
        return driver.findElement(successMessage).getText();
    }
    
    /**
     * Vérifie si un message d'erreur est affiché
     */
    public boolean isErrorMessageDisplayed() {
        try {
            return driver.findElement(errorAlert).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }
}
