package fr.leuwen.rhdemo.tests.base;

import fr.leuwen.rhdemo.tests.config.TestConfig;
import io.github.bonigarcia.wdm.WebDriverManager;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.firefox.FirefoxDriver;
import org.openqa.selenium.firefox.FirefoxOptions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.List;

/**
 * Classe de base pour tous les tests Selenium
 * Gère l'initialisation et la fermeture du WebDriver
 * Le navigateur est lancé une seule fois pour toute la suite de tests
 */
public abstract class BaseSeleniumTest {
    
    private static final Logger log = LoggerFactory.getLogger(BaseSeleniumTest.class);
    
    protected static WebDriver driver;
    protected static WebDriverWait wait;
    
    // Identifiants de test à positionner dans des variables d'environnement
    private static String testUsername = System.getenv("RHDEMOTEST_USER");
    private static String testPwd = System.getenv("RHDEMOTEST_PWD");
    
    @BeforeAll
    public static void setUpClass() {
        log.info("🚀 Initialisation du navigateur pour la suite de tests...");
        
        // Configuration du WebDriver selon le navigateur choisi
        if (TestConfig.BROWSER.equalsIgnoreCase("chrome")) {
            WebDriverManager.chromedriver().setup();
            ChromeOptions options = new ChromeOptions();
            if (TestConfig.HEADLESS_MODE) {
                options.addArguments("--headless");
                options.addArguments("--disable-gpu");
            }
            options.addArguments("--start-maximized");
            options.addArguments("--disable-extensions");
            options.addArguments("--no-sandbox");
            options.addArguments("--disable-dev-shm-usage");
            driver = new ChromeDriver(options);
        } else if (TestConfig.BROWSER.equalsIgnoreCase("firefox")) {
            WebDriverManager.firefoxdriver().setup();
            FirefoxOptions options = new FirefoxOptions();
            if (TestConfig.HEADLESS_MODE) {
                options.addArguments("--headless");
            }
            driver = new FirefoxDriver(options);
        } else {
            throw new IllegalArgumentException("Navigateur non supporté: " + TestConfig.BROWSER);
        }
        
        // Configuration des timeouts
        driver.manage().timeouts().implicitlyWait(Duration.ofSeconds(TestConfig.IMPLICIT_WAIT));
        driver.manage().timeouts().pageLoadTimeout(Duration.ofSeconds(TestConfig.PAGE_LOAD_TIMEOUT));
        
        // Initialisation du WebDriverWait
        wait = new WebDriverWait(driver, Duration.ofSeconds(TestConfig.EXPLICIT_WAIT));
        
        log.info("✅ Navigateur {} initialisé avec succès", TestConfig.BROWSER);
        
        // Authentification Keycloak

        authenticateKeycloak();
    }
    
    /**
     * Authentification sur Keycloak
     * Cette méthode est appelée une seule fois au début de la suite de tests
     */
    private static void authenticateKeycloak() {
        log.info("🔐 Authentification Keycloak en cours...");
        
        try {
            // Aller sur la page d'accueil (qui redirige vers Keycloak si pas authentifié)
            driver.get(TestConfig.HOME_URL);
            
            // Attendre que la page de login Keycloak soit chargée
            // On vérifie la présence du champ username
            WebDriverWait authWait = new WebDriverWait(driver, Duration.ofSeconds(TestConfig.AUTH_TIMEOUT));
            
            // Locators Keycloak
            By usernameField = By.id("username");
            By passwordField = By.id("password");
            By loginButton = By.id("kc-login");
            
            // Vérifier si on est sur la page de login Keycloak
            if (driver.getCurrentUrl().contains("keycloak") || driver.getCurrentUrl().contains("realms")) {
                log.info("📋 Page de login Keycloak détectée");
                
                // Attendre que le formulaire soit visible
                authWait.until(ExpectedConditions.visibilityOfElementLocated(usernameField));
                
                // Remplir le username
                WebElement usernameInput = driver.findElement(usernameField);
                usernameInput.clear();
                usernameInput.sendKeys(testUsername);
                log.info("✏️ Username saisi: {}", testUsername);

                // Remplir le password
                WebElement passwordInput = driver.findElement(passwordField);
                passwordInput.clear();
                passwordInput.sendKeys(testPwd);
                log.info("✏️ Password saisi");
                
                // Cliquer sur le bouton de connexion
                WebElement submitButton = driver.findElement(loginButton);
                submitButton.click();
                log.info("🔘 Bouton de connexion cliqué");
                
                // Attendre la redirection vers l'application
                authWait.until(ExpectedConditions.urlContains(TestConfig.BASE_URL));
                
                // Vérifier qu'on est bien authentifié (on ne doit plus être sur la page Keycloak)
                String currentUrl = driver.getCurrentUrl();
                if (!currentUrl.contains("keycloak") && !currentUrl.contains("realms")) {
                    log.info("✅ Authentification Keycloak réussie !");
                    log.info("🌐 URL actuelle: {}", currentUrl);
                } else {
                    log.warn("⚠️ Toujours sur la page Keycloak après authentification");
                    log.warn("URL: {}", currentUrl);
                }
                
            } else {
                log.info("ℹ️ Déjà authentifié (pas de redirection vers Keycloak)");
            }
            
        } catch (Exception e) {
            log.error("❌ Erreur lors de l'authentification Keycloak: {}", e.getMessage(), e);
            // On ne lance pas d'exception pour ne pas bloquer tous les tests
            // Les tests individuels échoueront si l'authentification a échoué
        }
    }
    
    @AfterAll
    public static void tearDownClass() {
        log.info("🛑 Fermeture du navigateur...");
        if (driver != null) {
            driver.quit();
            log.info("✅ Navigateur fermé");
        }
    }
    
    // ==================== Méthodes utilitaires ====================
    
    /**
     * Attend qu'un élément soit visible
     */
    protected WebElement waitForElement(By locator) {
        return wait.until(ExpectedConditions.visibilityOfElementLocated(locator));
    }
    
    /**
     * Attend qu'un élément soit cliquable
     */
    protected WebElement waitForClickable(By locator) {
        return wait.until(ExpectedConditions.elementToBeClickable(locator));
    }
    
    /**
     * Attend que le texte soit présent dans un élément
     */
    protected boolean waitForTextInElement(By locator, String text) {
        return wait.until(ExpectedConditions.textToBePresentInElementLocated(locator, text));
    }
    
    /**
     * Attend qu'un élément soit présent dans le DOM
     */
    protected WebElement waitForPresence(By locator) {
        return wait.until(ExpectedConditions.presenceOfElementLocated(locator));
    }
    
    /**
     * Remplit un champ de formulaire
     */
    protected void fillInput(By locator, String value) {
        WebElement element = waitForElement(locator);
        element.clear();
        element.sendKeys(value);
    }
    
    /**
     * Clique sur un élément après avoir attendu qu'il soit cliquable
     */
    protected void clickElement(By locator) {
        WebElement element = waitForClickable(locator);
        element.click();
    }
    
    /**
     * Récupère le texte d'un élément
     */
    protected String getElementText(By locator) {
        return waitForElement(locator).getText();
    }
    
    /**
     * Vérifie si un élément est visible
     */
    protected boolean isElementVisible(By locator) {
        try {
            return driver.findElement(locator).isDisplayed();
        } catch (Exception e) {
            return false;
        }
    }
    
    /**
     * Récupère tous les éléments correspondant au locator
     */
    protected List<WebElement> findElements(By locator) {
        return driver.findElements(locator);
    }
    
    /**
     * Attente simple
     */
    protected void waitSeconds(int seconds) {
        try {
            Thread.sleep(seconds * 1000L);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
