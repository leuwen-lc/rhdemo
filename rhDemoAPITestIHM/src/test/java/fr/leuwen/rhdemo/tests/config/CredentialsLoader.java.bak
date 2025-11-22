package fr.leuwen.rhdemo.tests.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.yaml.snakeyaml.Yaml;

import java.io.InputStream;
import java.util.Map;

/**
 * Chargeur de credentials pour les tests Selenium
 *
 * Stratégie de chargement avec fallback :
 * 1. Essayer de charger depuis test-credentials.yml (local)
 * 2. Si non trouvé, utiliser les variables d'environnement (staging/Jenkins)
 */
public class CredentialsLoader {

    private static final Logger log = LoggerFactory.getLogger(CredentialsLoader.class);

    private static final String CREDENTIALS_FILE = "test-credentials.yml";
    private static final String ENV_USERNAME = "RHDEMOTEST_USER";
    private static final String ENV_PASSWORD = "RHDEMOTEST_PWD";

    private final String username;
    private final String password;

    public CredentialsLoader() {
        Credentials creds = loadCredentials();
        this.username = creds.username;
        this.password = creds.password;

        // Validation
        if (this.username == null || this.username.isEmpty()) {
            throw new RuntimeException("❌ Username non configuré ! " +
                "Créer test-credentials.yml ou définir " + ENV_USERNAME);
        }
        if (this.password == null || this.password.isEmpty()) {
            throw new RuntimeException("❌ Password non configuré ! " +
                "Créer test-credentials.yml ou définir " + ENV_PASSWORD);
        }
    }

    private Credentials loadCredentials() {
        // Essayer de charger depuis le fichier YAML local
        try (InputStream input = getClass().getClassLoader().getResourceAsStream(CREDENTIALS_FILE)) {
            if (input != null) {
                Yaml yaml = new Yaml();
                Map<String, Object> data = yaml.load(input);

                @SuppressWarnings("unchecked")
                Map<String, String> credentials = (Map<String, String>) data.get("credentials");

                if (credentials != null) {
                    String username = credentials.get("username");
                    String password = credentials.get("password");

                    if (username != null && password != null) {
                        log.info("✅ Credentials chargés depuis {}", CREDENTIALS_FILE);
                        return new Credentials(username, password);
                    }
                }
            }
        } catch (Exception e) {
            log.warn("⚠️ Impossible de charger {} : {}", CREDENTIALS_FILE, e.getMessage());
        }

        // Fallback sur les variables d'environnement
        String envUsername = System.getenv(ENV_USERNAME);
        String envPassword = System.getenv(ENV_PASSWORD);

        if (envUsername != null && envPassword != null) {
            log.info("✅ Credentials chargés depuis variables d'environnement ({}, {})",
                ENV_USERNAME, ENV_PASSWORD);
            return new Credentials(envUsername, envPassword);
        }

        // Aucune source de credentials trouvée
        log.error("❌ Aucune source de credentials trouvée !");
        log.error("   Option 1: Créer {} depuis {}.template", CREDENTIALS_FILE, CREDENTIALS_FILE);
        log.error("   Option 2: Définir les variables d'environnement {} et {}",
            ENV_USERNAME, ENV_PASSWORD);

        return new Credentials(null, null);
    }

    public String getUsername() {
        return username;
    }

    public String getPassword() {
        return password;
    }

    /**
     * Classe interne pour stocker les credentials
     */
    private static class Credentials {
        final String username;
        final String password;

        Credentials(String username, String password) {
            this.username = username;
            this.password = password;
        }
    }
}
