package fr.leuwen.rhdemo.tests.pages;

import org.apache.commons.io.FileUtils;
import org.openqa.selenium.By;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.time.Duration;

/**
 * Page Object pour la page d'ajout d'un employé
 */
public class EmployeAddPage {
    
    private final WebDriver driver;
    private final WebDriverWait wait;
    
    // Locators utilisant data-testid pour une meilleure stabilité
    // Element Plus génère des wrappers, il faut chercher l'input natif à l'intérieur
    private final By prenomInput = By.cssSelector("[data-testid='employe-prenom-input'] input");
    private final By nomInput = By.cssSelector("[data-testid='employe-nom-input'] input");
    private final By emailInput = By.cssSelector("[data-testid='employe-email-input'] input");
    private final By adresseTextarea = By.cssSelector("[data-testid='employe-adresse-input'] textarea");
    private final By submitButton = By.cssSelector("[data-testid='employe-submit-button']");
    private final By cancelButton = By.cssSelector("[data-testid='employe-cancel-button']");
    private final By successAlert = By.cssSelector("[data-testid='employe-success-alert']");
    private final By errorAlert = By.cssSelector("[data-testid='employe-error-alert']");
    
    private static final Logger logger = LoggerFactory.getLogger(EmployeAddPage.class);
    
    private void takeScreenshot(String fileName) {
        try {
            File scrFile = ((TakesScreenshot) driver).getScreenshotAs(OutputType.FILE);
            File target = new File("screenshots/" + fileName);
            FileUtils.copyFile(scrFile, target);
        } catch (Exception e) {
            logger.error("Screenshot error: " + e.getMessage());
        }
    }
    
    
    public EmployeAddPage(WebDriver driver) {
        this.driver = driver;
        // Augmenter le timeout pour laisser Vue.js le temps de s'initialiser en headless
        this.wait = new WebDriverWait(driver, Duration.ofSeconds(30));
    }
    
    /**
     * Remplit le formulaire d'ajout d'employé
     */
    public void fillEmployeForm(String prenom, String nom, String email, String adresse) {
        // IMPORTANT: Attendre que Vue.js ait monté l'application
        // En headless, Vue.js peut mettre du temps à s'initialiser
        logger.info("⏳ Attente que Vue.js monte l'application...");

        // DEBUG: Capturer les logs de la console JavaScript
        try {
            Object logs = ((org.openqa.selenium.JavascriptExecutor) driver).executeScript(
                "return window.console ? 'Console disponible' : 'Console indisponible';"
            );
            logger.info("État console JavaScript: {}", logs);
        } catch (Exception ex) {
            logger.warn("Impossible de vérifier la console JS: {}", ex.getMessage());
        }

        wait.until(driver -> {
            try {
                // Vérifier si Vue.js a réellement monté l'application
                Object mounted = ((org.openqa.selenium.JavascriptExecutor) driver).executeScript(
                    "return window.__VUE_APP_MOUNTED__ === true;"
                );
                boolean vueLoaded = Boolean.TRUE.equals(mounted);
                if (!vueLoaded) {
                    logger.debug("Vue.js pas encore monté, __VUE_APP_MOUNTED__: {}", mounted);
                }
                return vueLoaded;
            } catch (Exception e) {
                logger.warn("Erreur lors de la vérification Vue.js: {}", e.getMessage());
                return false;
            }
        });
        logger.info("✅ Vue.js chargé, recherche du formulaire...");

        try {
            wait.until(ExpectedConditions.visibilityOfElementLocated(prenomInput));
        } catch (Exception e) {
            // DEBUG: Capturer l'état de la page
            logger.error("❌ Impossible de trouver le champ prenom");
            logger.error("URL actuelle: {}", driver.getCurrentUrl());
            logger.error("Titre de la page: {}", driver.getTitle());
            logger.error("HTML du body (1000 premiers caractères): {}",
                driver.findElement(By.tagName("body")).getAttribute("innerHTML").substring(0, Math.min(1000, driver.findElement(By.tagName("body")).getAttribute("innerHTML").length())));

            // Vérifier si les scripts sont chargés
            try {
                Long scriptCount = (Long) ((org.openqa.selenium.JavascriptExecutor) driver).executeScript(
                    "return document.querySelectorAll('script').length;"
                );
                logger.error("Nombre de balises <script>: {}", scriptCount);

                // Vérifier si window.__VUE_DEBUG__ est défini (notre variable de debug)
                Object vueDebug = ((org.openqa.selenium.JavascriptExecutor) driver).executeScript(
                    "return typeof window.__VUE_DEBUG__;"
                );
                logger.error("window.__VUE_DEBUG__ type: {}", vueDebug);

                // Vérifier si Vue.js a monté l'application
                Object vueMounted = ((org.openqa.selenium.JavascriptExecutor) driver).executeScript(
                    "return window.__VUE_APP_MOUNTED__;"
                );
                logger.error("window.__VUE_APP_MOUNTED__: {}", vueMounted);

                // Récupérer les erreurs de la console si disponibles
                Object consoleErrors = ((org.openqa.selenium.JavascriptExecutor) driver).executeScript(
                    "return window.__VUE_ERRORS__ || 'Pas d\\'erreurs capturées';"
                );
                logger.error("Erreurs console: {}", consoleErrors);
            } catch (Exception jsEx) {
                logger.error("Erreur lors de l'exécution JS: {}", jsEx.getMessage());
            }

            takeScreenshot("Impossible de trouver le champ prenom.png");
            throw e;
        }
        
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
