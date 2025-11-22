package fr.leuwen.rhdemo.tests.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.yaml.snakeyaml.Yaml;

import java.io.InputStream;
import java.util.Map;

/**
 * Configuration centralisée unifiée pour les tests Selenium
 *
 * Stratégie de chargement hiérarchique (ordre de priorité) :
 * 1. Propriétés Maven (-Dkey=value)
 * 2. Variables d'environnement
 * 3. Fichiers YAML (test.yml / test-credentials.yml)
 * 4. Valeurs par défaut
 *
 */
public class TestConfig {

    private static final Logger log = LoggerFactory.getLogger(TestConfig.class);

    // Chargement des fichiers YAML
    private static final Map<String, Object> config;
    private static final Map<String, Object> credentials;

    static {
        // Charger test.yml (configuration)
        config = loadYamlFile("test.yml");

        // Charger test-credentials.yml (credentials - optionnel)
        credentials = loadYamlFile("test-credentials.yml");

        log.info("📋 Configuration TestConfig initialisée");
        log.info("   - Fichier test.yml: {}", config != null ? "✅ chargé" : "❌ non trouvé");
        log.info("   - Fichier test-credentials.yml: {}", credentials != null ? "✅ chargé" : "❌ non trouvé (fallback env vars)");
    }

    // ========== URLs et Configuration Applicative ==========

    /**
     * URL de base de l'application à tester
     * Priorité: -Dtest.baseurl > test.yml > défaut localhost:9000
     */
    public static final String BASE_URL = getConfigProperty(
        "test.baseurl",           // Propriété Maven
        null,                     // Pas d'env var pour cette config
        "app.base.url",          // Chemin dans test.yml
        "http://localhost:9000"  // Défaut
    );

    /**
     * URL Keycloak pour l'authentification
     * Priorité: -Dtest.keycloak.url > test.yml > défaut localhost:6090
     */
    public static final String KEYCLOAK_LOGIN_URL = getConfigProperty(
        "test.keycloak.url",
        null,
        "keycloak.url",
        "http://localhost:6090/realms/RHDemo"
    );

    // URLs dérivées des pages
    public static final String HOME_URL = BASE_URL + "/front/";
    public static final String EMPLOYES_LIST_URL = BASE_URL + "/front/employes";
    public static final String EMPLOYE_ADD_URL = BASE_URL + "/front/ajout";
    public static final String EMPLOYE_MODIFY_URL = BASE_URL + "/front/modification";
    public static final String EMPLOYE_DELETE_URL = BASE_URL + "/front/suppression";
    public static final String EMPLOYE_SEARCH_URL = BASE_URL + "/front/recherche";

    // ========== Configuration Selenium ==========

    /**
     * Mode headless (sans interface graphique)
     * Priorité: -Dselenium.headless > env var > test.yml > défaut false
     */
    public static final boolean HEADLESS_MODE = getBooleanProperty(
        "selenium.headless",
        "SELENIUM_HEADLESS",
        "headless.mode",
        false
    );

    /**
     * Navigateur à utiliser (chrome, firefox, edge)
     * Priorité: -Dselenium.browser > env var > test.yml > défaut firefox
     */
    public static final String BROWSER = getConfigProperty(
        "selenium.browser",
        "SELENIUM_BROWSER",
        "browser",
        "firefox"
    );

    // ========== Timeouts (en secondes) ==========

    public static final int IMPLICIT_WAIT = getIntProperty("timeout.implicit", 10);
    public static final int EXPLICIT_WAIT = getIntProperty("timeout.explicit", 15);
    public static final int PAGE_LOAD_TIMEOUT = getIntProperty("timeout.page.load", 30);
    public static final int AUTH_TIMEOUT = getIntProperty("keycloak.timeout", 20);

    // ========== Credentials ==========

    /**
     * Username pour les tests
     * Priorité: -Dtest.username > RHDEMOTEST_USER > test-credentials.yml > erreur
     */
    public static final String USERNAME = getCredential(
        "test.username",
        "RHDEMOTEST_USER",
        "credentials.username"
    );

    /**
     * Password pour les tests
     * Priorité: -Dtest.password > RHDEMOTEST_PWD > test-credentials.yml > erreur
     */
    public static final String PASSWORD = getCredential(
        "test.password",
        "RHDEMOTEST_PWD",
        "credentials.password"
    );

    // Validation des credentials au chargement
    static {
        if (USERNAME == null || USERNAME.isEmpty()) {
            throw new RuntimeException(
                "❌ Username non configuré ! Utiliser :\n" +
                "   1. Propriété Maven: -Dtest.username=xxx\n" +
                "   2. Variable env: RHDEMOTEST_USER\n" +
                "   3. Fichier: test-credentials.yml"
            );
        }
        if (PASSWORD == null || PASSWORD.isEmpty()) {
            throw new RuntimeException(
                "❌ Password non configuré ! Utiliser :\n" +
                "   1. Propriété Maven: -Dtest.password=xxx\n" +
                "   2. Variable env: RHDEMOTEST_PWD\n" +
                "   3. Fichier: test-credentials.yml"
            );
        }

        log.info("🔐 Credentials configurés:");
        log.info("   - Username: {}", USERNAME);
        log.info("   - Password: ********");
    }

    // ========== Méthodes Utilitaires ==========

    /**
     * Récupère une propriété de configuration avec fallback hiérarchique
     */
    private static String getConfigProperty(String mavenKey, String envKey, String yamlPath, String defaultValue) {
        // 1. Propriété Maven
        String mavenValue = System.getProperty(mavenKey);
        if (mavenValue != null && !mavenValue.isEmpty()) {
            log.debug("   {} = {} (depuis propriété Maven)", mavenKey, mavenValue);
            return mavenValue;
        }

        // 2. Variable d'environnement
        if (envKey != null) {
            String envValue = System.getenv(envKey);
            if (envValue != null && !envValue.isEmpty()) {
                log.debug("   {} = {} (depuis env var {})", mavenKey, envValue, envKey);
                return envValue;
            }
        }

        // 3. Fichier YAML
        if (yamlPath != null && config != null) {
            String yamlValue = getNestedProperty(config, yamlPath, null);
            if (yamlValue != null) {
                log.debug("   {} = {} (depuis test.yml)", mavenKey, yamlValue);
                return yamlValue;
            }
        }

        // 4. Valeur par défaut
        log.debug("   {} = {} (défaut)", mavenKey, defaultValue);
        return defaultValue;
    }

    /**
     * Récupère un credential avec fallback hiérarchique
     */
    private static String getCredential(String mavenKey, String envKey, String yamlPath) {
        // 1. Propriété Maven
        String mavenValue = System.getProperty(mavenKey);
        if (mavenValue != null && !mavenValue.isEmpty()) {
            log.info("   Credential {} chargé depuis propriété Maven", mavenKey);
            return mavenValue;
        }

        // 2. Variable d'environnement
        String envValue = System.getenv(envKey);
        if (envValue != null && !envValue.isEmpty()) {
            log.info("   Credential {} chargé depuis variable d'environnement {}", mavenKey, envKey);
            return envValue;
        }

        // 3. Fichier YAML credentials
        if (yamlPath != null && credentials != null) {
            String yamlValue = getNestedProperty(credentials, yamlPath, null);
            if (yamlValue != null) {
                log.info("   Credential {} chargé depuis test-credentials.yml", mavenKey);
                return yamlValue;
            }
        }

        // Aucune source trouvée
        return null;
    }

    /**
     * Charge un fichier YAML
     */
    private static Map<String, Object> loadYamlFile(String filename) {
        try (InputStream input = TestConfig.class.getClassLoader().getResourceAsStream(filename)) {
            if (input != null) {
                Yaml yaml = new Yaml();
                return yaml.load(input);
            }
        } catch (Exception e) {
            log.warn("⚠️ Impossible de charger {} : {}", filename, e.getMessage());
        }
        return null;
    }

    /**
     * Récupère une propriété nested dans un Map YAML
     */
    @SuppressWarnings("unchecked")
    private static String getNestedProperty(Map<String, Object> source, String path, String defaultValue) {
        if (source == null) {
            return defaultValue;
        }

        String[] keys = path.split("\\.");
        Map<String, Object> current = source;

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

    /**
     * Récupère une propriété entière depuis test.yml
     */
    private static int getIntProperty(String path, int defaultValue) {
        if (config == null) {
            return defaultValue;
        }

        String value = getNestedProperty(config, path, null);
        if (value == null) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    /**
     * Récupère une propriété booléenne avec fallback hiérarchique
     */
    private static boolean getBooleanProperty(String mavenKey, String envKey, String yamlPath, boolean defaultValue) {
        String value = getConfigProperty(mavenKey, envKey, yamlPath, null);
        if (value == null) {
            return defaultValue;
        }
        return Boolean.parseBoolean(value);
    }
}
