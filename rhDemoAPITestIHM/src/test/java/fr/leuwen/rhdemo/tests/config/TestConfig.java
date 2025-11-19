package fr.leuwen.rhdemo.tests.config;

import org.yaml.snakeyaml.Yaml;

import java.io.InputStream;
import java.util.Map;

/**
 * Configuration centralisée pour les tests Selenium
 * Charge les propriétés depuis test.yml
 */
public class TestConfig {
    
    private static final Map<String, Object> config;
    
    static {
        Yaml yaml = new Yaml();
        InputStream inputStream = TestConfig.class.getClassLoader().getResourceAsStream("test.yml");
        config = yaml.load(inputStream);
    }
    
    // URL de base de l'application à tester
    // Priorité: propriété système -Dtest.baseurl > test.yml > localhost:9000
    public static final String BASE_URL = System.getProperty("test.baseurl",
        getNestedProperty("app.base.url", "http://localhost:9000"));
    
    // Timeouts en secondes
    public static final int IMPLICIT_WAIT = getIntProperty("timeout.implicit", 10);
    public static final int EXPLICIT_WAIT = getIntProperty("timeout.explicit", 15);
    public static final int PAGE_LOAD_TIMEOUT = getIntProperty("timeout.page.load", 30);
    
    // URLs des pages
    public static final String HOME_URL = BASE_URL + "/front/";
    public static final String EMPLOYES_LIST_URL = BASE_URL + "/front/employes";
    public static final String EMPLOYE_ADD_URL = BASE_URL + "/front/ajout";
    public static final String EMPLOYE_MODIFY_URL = BASE_URL + "/front/modification";
    public static final String EMPLOYE_DELETE_URL = BASE_URL + "/front/suppression";
    public static final String EMPLOYE_SEARCH_URL = BASE_URL + "/front/recherche";
    
    // Mode headless (sans interface graphique)
    // Priorité: propriété système -Dselenium.headless > test.yml > false
    public static final boolean HEADLESS_MODE = Boolean.parseBoolean(
        System.getProperty("selenium.headless", 
            getBooleanProperty("headless.mode", false) ? "true" : "false")
    );
    
    // Navigateur à utiliser (chrome, firefox, edge)
    // Priorité: propriété système -Dselenium.browser > test.yml > firefox
    public static final String BROWSER = System.getProperty("selenium.browser",
        getNestedProperty("browser", "firefox"));
    
    // ========== Authentification Keycloak ==========
    
    // URL de la page de login Keycloak
    // Priorité: propriété système -Dtest.keycloak.url > test.yml > localhost:6080
    public static final String KEYCLOAK_LOGIN_URL = System.getProperty("test.keycloak.url",
        getNestedProperty("keycloak.url", "http://localhost:6080/realms/LeuwenRealm"));
    
    // Timeout pour l'authentification (secondes)
    public static final int AUTH_TIMEOUT = getIntProperty("keycloak.timeout", 20);
    
    @SuppressWarnings("unchecked")
    private static String getNestedProperty(String path, String defaultValue) {
        String[] keys = path.split("\\.");
        Map<String, Object> current = config;
        
        for (int i = 0; i < keys.length - 1; i++) {
            Object next = current.get(keys[i]);
            if (next instanceof Map) {
                current = (Map<String, Object>) next;
            } else {
                return defaultValue;
            }
        }
        
        Object value = current.get(keys[keys.length - 1]);
        return value != null ? value.toString() : defaultValue;
    }
    
    private static int getIntProperty(String path, int defaultValue) {
        String value = getNestedProperty(path, null);
        if (value == null) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }
    
    private static boolean getBooleanProperty(String path, boolean defaultValue) {
        String value = getNestedProperty(path, null);
        if (value == null) {
            return defaultValue;
        }
        return Boolean.parseBoolean(value);
    }
}
