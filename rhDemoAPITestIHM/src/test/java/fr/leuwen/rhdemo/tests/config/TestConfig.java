package fr.leuwen.rhdemo.tests.config;

/**
 * Configuration centralisée pour les tests Selenium
 */
public class TestConfig {
    
    // URL de base de l'application à tester
    public static final String BASE_URL = "http://localhost:9000";
    
    // Timeouts en secondes
    public static final int IMPLICIT_WAIT = 10;
    public static final int EXPLICIT_WAIT = 15;
    public static final int PAGE_LOAD_TIMEOUT = 30;
    
    // URLs des pages
    public static final String HOME_URL = BASE_URL + "/front/";
    public static final String EMPLOYES_LIST_URL = BASE_URL + "/front/employes";
    public static final String EMPLOYE_ADD_URL = BASE_URL + "/front/ajout";
    public static final String EMPLOYE_MODIFY_URL = BASE_URL + "/front/modification";
    public static final String EMPLOYE_DELETE_URL = BASE_URL + "/front/suppression";
    public static final String EMPLOYE_SEARCH_URL = BASE_URL + "/front/recherche";
    
    // Mode headless (sans interface graphique)
    public static final boolean HEADLESS_MODE = false; // Mettre à true pour CI/CD
    
    // Navigateur à utiliser (chrome, firefox, edge)
    public static final String BROWSER = "firefox";
    
    // ========== Authentification Keycloak ==========
    
    // URL de la page de login Keycloak
    public static final String KEYCLOAK_LOGIN_URL = "http://localhost:6080/realms/LeuwenRealm";
    
    
    // Timeout pour l'authentification (secondes)
    public static final int AUTH_TIMEOUT = 20;
}
