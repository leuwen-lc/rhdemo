package fr.leuwen.rhdemo.tests.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.time.Duration;

/**
 * Page Object pour la page d'ajout d'un employé
 */
public class EmployeAddPage {
    
    private final WebDriver driver;
    private final WebDriverWait wait;
    
    // Locators utilisant data-testid pour une meilleure stabilité
    private final By prenomInput = By.cssSelector("[data-testid='employe-prenom-input']");
    private final By nomInput = By.cssSelector("[data-testid='employe-nom-input']");
    private final By emailInput = By.cssSelector("[data-testid='employe-email-input']");
    private final By adresseTextarea = By.cssSelector("[data-testid='employe-adresse-input']");
    private final By submitButton = By.cssSelector("[data-testid='employe-submit-button']");
    private final By cancelButton = By.cssSelector("[data-testid='employe-cancel-button']");
    private final By successAlert = By.cssSelector("[data-testid='employe-success-alert']");
    private final By errorAlert = By.cssSelector("[data-testid='employe-error-alert']");
    
    public EmployeAddPage(WebDriver driver) {
        this.driver = driver;
        this.wait = new WebDriverWait(driver, Duration.ofSeconds(15));
    }
    
    /**
     * Remplit le formulaire d'ajout d'employé
     */
    public void fillEmployeForm(String prenom, String nom, String email, String adresse) {
        wait.until(ExpectedConditions.visibilityOfElementLocated(prenomInput));
        
        driver.findElement(prenomInput).clear();
        driver.findElement(prenomInput).sendKeys(prenom);
        
        driver.findElement(nomInput).clear();
        driver.findElement(nomInput).sendKeys(nom);
        
        driver.findElement(emailInput).clear();
        driver.findElement(emailInput).sendKeys(email);
        
        if (adresse != null && !adresse.isEmpty()) {
            driver.findElement(adresseTextarea).clear();
            driver.findElement(adresseTextarea).sendKeys(adresse);
        }
    }
    
    /**
     * Remplit le formulaire sans adresse (champ optionnel)
     */
    public void fillEmployeFormWithoutAddress(String prenom, String nom, String email) {
        fillEmployeForm(prenom, nom, email, null);
    }
    
    /**
     * Clique sur le bouton Ajouter/Modifier
     */
    public void clickAddButton() {
        wait.until(ExpectedConditions.elementToBeClickable(submitButton));
        driver.findElement(submitButton).click();
    }
    
    /**
     * Clique sur le bouton Annuler
     */
    public void clickCancelButton() {
        wait.until(ExpectedConditions.elementToBeClickable(cancelButton));
        driver.findElement(cancelButton).click();
    }
    
    /**
     * Vérifie si le message de succès est affiché
     */
    public boolean isSuccessMessageDisplayed() {
        try {
            wait.until(ExpectedConditions.visibilityOfElementLocated(successAlert));
            return driver.findElement(successAlert).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }
    
    /**
     * Récupère le message de succès
     */
    public String getSuccessMessage() {
        wait.until(ExpectedConditions.visibilityOfElementLocated(successAlert));
        return driver.findElement(successAlert).getText();
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
    
    /**
     * Attend la redirection vers la liste des employés
     */
    public void waitForRedirectToEmployesList() {
        wait.until(ExpectedConditions.urlContains("/front/employes"));
    }
}
