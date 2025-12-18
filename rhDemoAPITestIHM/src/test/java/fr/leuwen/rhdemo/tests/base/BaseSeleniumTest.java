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

    // Credentials chargés depuis TestConfig unifié
    // Priorité: Maven properties > env vars > YAML files
    private static final String testUsername = TestConfig.USERNAME;
    private static final String testPwd = TestConfig.PASSWORD;
    
    @BeforeAll
    public static void setUpClass() {
        log.info("🚀 Initialisation du navigateur pour la suite de tests...");
        
        // Configuration du WebDriver selon le navigateur choisi
        if (TestConfig.BROWSER.equalsIgnoreCase("chrome")) {
            WebDriverManager.chromedriver().setup();
            ChromeOptions options = new ChromeOptions();

            // IMPORTANT: Accepter les certificats SSL auto-signés pour ephemere
            // Permet à Chrome de se connecter à https://rhdemo.ephemere.local:58443 et https://keycloak.ephemere.local:58443
            options.setAcceptInsecureCerts(true);

            // Configuration du proxy ZAP (si activé via variable d'environnement)
            String zapProxyHost = System.getenv("ZAP_PROXY_HOST");
            String zapProxyPort = System.getenv("ZAP_PROXY_PORT");
            if (zapProxyHost != null && zapProxyPort != null) {
                log.info("🔒 Configuration du proxy OWASP ZAP: {}:{}", zapProxyHost, zapProxyPort);
                org.openqa.selenium.Proxy proxy = new org.openqa.selenium.Proxy();
                String proxyAddress = zapProxyHost + ":" + zapProxyPort;
                proxy.setHttpProxy(proxyAddress);
                proxy.setSslProxy(proxyAddress);
                proxy.setNoProxy(""); // Tout passe par ZAP
                options.setProxy(proxy);
                log.info("✅ Proxy ZAP configuré: {}", proxyAddress);
            }

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

            // Configuration du binaire Firefox pour éviter les problèmes de détection automatique
            // Selenium cherche parfois dans /snap/firefox qui n'existe pas toujours
            String firefoxBinary = System.getProperty("webdriver.firefox.bin");
            if (firefoxBinary == null || firefoxBinary.isEmpty()) {
                // Auto-détection : essayer plusieurs emplacements standards
                String[] possiblePaths = {
                    "/usr/bin/firefox-esr",             // Jenkins + conteneurs Debian/Ubuntu (apt)
                    "/usr/bin/firefox",                 // Installation apt standard
                    "/usr/local/bin/firefox",           // Installation manuelle dans /usr/local
                    "/opt/firefox/firefox"              // Installation manuelle dans /opt
                };
                boolean foundFirefox = false;
                for (String path : possiblePaths) {
                    if (new java.io.File(path).exists()) {
                        log.info("🦊 Firefox détecté: {}", path);
                        options.setBinary(path);
                        foundFirefox = true;
                        break;
                    }
                }
                if (!foundFirefox) {
                    log.warn("⚠️  Aucun Firefox détecté aux emplacements standards, utilisation de la détection par défaut");
                }
            } else {
                log.info("🦊 Utilisation du binaire Firefox spécifié: {}", firefoxBinary);
                options.setBinary(firefoxBinary);
            }

            // IMPORTANT: Accepter les certificats SSL auto-signés pour ephemere
            // Permet à Firefox de se connecter à https://rhdemo.ephemere.local:58443 et https://keycloak.ephemere.local:58443
            options.setAcceptInsecureCerts(true);

            // Configuration du proxy ZAP (si activé via variable d'environnement)
            String zapProxyHost = System.getenv("ZAP_PROXY_HOST");
            String zapProxyPort = System.getenv("ZAP_PROXY_PORT");
            if (zapProxyHost != null && zapProxyPort != null) {
                log.info("🔒 Configuration du proxy OWASP ZAP: {}:{}", zapProxyHost, zapProxyPort);
                org.openqa.selenium.Proxy proxy = new org.openqa.selenium.Proxy();
                String proxyAddress = zapProxyHost + ":" + zapProxyPort;
                proxy.setHttpProxy(proxyAddress);
                proxy.setSslProxy(proxyAddress);
                proxy.setNoProxy(""); // Tout passe par ZAP
                options.setProxy(proxy);
                log.info("✅ Proxy ZAP configuré: {}", proxyAddress);
            }

            if (TestConfig.HEADLESS_MODE) {
                options.addArguments("-headless");  // Firefox utilise -headless (un seul tiret)
                // Options supplémentaires pour environnement conteneur Docker
                options.addArguments("--no-sandbox");
                options.addArguments("--disable-dev-shm-usage");
                options.addPreference("browser.download.folderList", 2);
                options.addPreference("browser.helperApps.alwaysAsk.force", false);
                // Forcer le mode headless via variable d'environnement
                options.addPreference("MOZ_HEADLESS", "1");
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
                
                // Vérifier qu'on est bien authentifié (vérification stricte)
                String currentUrl = driver.getCurrentUrl();
                log.info("🌐 URL après authentification: {}", currentUrl);
                
                if (currentUrl.contains("/login?error")) {
                    log.error("❌ Échec d'authentification: redirection vers /login?error");
                    log.error("Causes possibles:");
                    log.error("  - Credentials invalides");
                    log.error("  - Rôles manquants dans le token JWT");
                    log.error("  - Client Keycloak mal configuré (mappers)");
                    throw new RuntimeException("Authentification Keycloak échouée: " + currentUrl);
                } else if (currentUrl.contains("keycloak") || currentUrl.contains("realms")) {
                    log.warn("⚠️ Toujours sur la page Keycloak après authentification");
                    throw new RuntimeException("Redirection OAuth2 incomplète: " + currentUrl);
                } else if (currentUrl.contains("/front")) {
                    log.info("✅ Authentification Keycloak réussie !");
                } else {
                    log.warn("⚠️ URL inattendue après authentification: {}", currentUrl);
                }
                
            } else {
                log.info("ℹ️ Déjà authentifié (pas de redirection vers Keycloak)");
            }
            
        } catch (Exception e) {
            log.error("❌ Erreur lors de l'authentification Keycloak: {}", e.getMessage(), e);
            // CRITICAL: Relancer l'exception pour arrêter immédiatement la suite de tests
            // Si l'authentification échoue, aucun test ne peut réussir
            throw new RuntimeException("❌ AUTHENTIFICATION KEYCLOAK ÉCHOUÉE - Arrêt de la suite de tests", e);
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
