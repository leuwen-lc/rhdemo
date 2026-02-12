package fr.leuwen.rhdemo.tests.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

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
    
    private static final Logger logger = LoggerFactory.getLogger(EmployeAddPage.class);

    public EmployeAddPage(WebDriver driver) {
        this.driver = driver;
        this.wait = new WebDriverWait(driver, Duration.ofSeconds(15));
    }
    
    /**
     * Remplit le formulaire d'ajout d'employé
     */
    public void fillEmployeForm(String prenom, String nom, String email, String adresse) {
        try {
            // Attendre que la page soit complètement chargée
            // Vérifier d'abord si un loader/spinner est présent et attendre qu'il disparaisse
            By loadingIndicator = By.cssSelector(".loading, .spinner, [class*='loading'], [class*='spinner']");
            try {
                // Si un loader est présent, attendre qu'il disparaisse (max 5 secondes)
                WebDriverWait shortWait = new WebDriverWait(driver, Duration.ofSeconds(5));
                if (!driver.findElements(loadingIndicator).isEmpty()) {
                    logger.info("⏳ Page de chargement détectée, attente de sa disparition...");
                    shortWait.until(ExpectedConditions.invisibilityOfElementLocated(loadingIndicator));
                    logger.info("✅ Page de chargement terminée");
                }
            } catch (Exception ignored) {
                // Pas de loader ou déjà disparu, continuer
            }

            // Attendre que le champ prenom soit visible
            wait.until(ExpectedConditions.visibilityOfElementLocated(prenomInput));
        } catch (Exception e) {
            // DEBUG: Capturer l'état de la page en cas d'échec
            String currentUrl = driver.getCurrentUrl();
            String pageTitle = driver.getTitle();
            String bodyHtml = driver.findElement(By.tagName("body")).getAttribute("innerHTML");

            logger.error("❌ Impossible de trouver le champ prenom");
            logger.error("URL actuelle: {}", currentUrl);
            logger.error("Titre de la page: {}", pageTitle);
            logger.error("HTML du body (500 premiers caractères): \n{}",
                bodyHtml.substring(0, Math.min(500, bodyHtml.length())));

            // Si on détecte une page Keycloak avec erreur, logger plus de détails
            if (pageTitle.contains("Keycloak") || currentUrl.contains("keycloak") || currentUrl.contains("realms")) {
                logger.error("🔍 PAGE KEYCLOAK DÉTECTÉE - Analyse détaillée:");
                logger.error("   → Ceci indique un problème d'authentification OAuth2/OIDC");

                // Chercher le message d'erreur Keycloak dans le HTML
                if (bodyHtml.contains("We are sorry")) {
                    logger.error("   → Message Keycloak: 'We are sorry...' (erreur serveur Keycloak)");

                    // Essayer d'extraire plus de détails de l'erreur
                    try {
                        String errorDetail = driver.findElement(By.cssSelector(".pf-v5-c-login__main-body")).getText();
                        logger.error("   → Détail erreur: {}", errorDetail);
                    } catch (Exception ignored) {
                        // Si pas de détail disponible, continuer
                    }
                }

                // Logger l'URL complète de Keycloak pour debug
                if (currentUrl.contains("?")) {
                    logger.error("   → URL Keycloak avec paramètres:");
                    String[] urlParts = currentUrl.split("\\?");
                    logger.error("      Base: {}", urlParts[0]);
                    if (urlParts.length > 1) {
                        String[] params = urlParts[1].split("&");
                        for (String param : params) {
                            // Masquer les valeurs sensibles (state, nonce)
                            if (param.startsWith("state=") || param.startsWith("nonce=")) {
                                logger.error("      {}=<MASKED>", param.split("=")[0]);
                            } else {
                                logger.error("      {}", param);
                            }
                        }
                    }
                }

                logger.error("   → CAUSES POSSIBLES:");
                logger.error("      1. redirect_uri non whitelisté dans Keycloak client config");
                logger.error("      2. Problème de certificat SSL/TLS via proxy ZAP");
                logger.error("      3. Cookies de session OAuth2 bloqués ou invalides");
                logger.error("      4. Client ID invalide ou client désactivé dans Keycloak");
                logger.error("   → VÉRIFIER: logs Keycloak archivés dans debug-logs/keycloak.log");
            }

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
