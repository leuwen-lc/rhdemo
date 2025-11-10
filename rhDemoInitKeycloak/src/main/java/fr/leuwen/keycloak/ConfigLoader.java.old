package fr.leuwen.keycloak;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.yaml.snakeyaml.Yaml;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Map;
import java.util.Properties;

/**
 * Classe utilitaire pour charger et accéder aux propriétés de configuration
 * Supporte les formats .properties et .yml/.yaml
 */
public class ConfigLoader {
    
    private static final Logger log = LoggerFactory.getLogger(ConfigLoader.class);
    
    private static final String DEFAULT_CONFIG_FILE = "application.yml";
    private final Properties properties;
    
    public ConfigLoader() throws IOException {
        this(DEFAULT_CONFIG_FILE);
    }
    
    public ConfigLoader(String configFile) throws IOException {
        properties = new Properties();
        
        // Déterminer si c'est un fichier YAML ou Properties
        if (configFile.endsWith(".yml") || configFile.endsWith(".yaml")) {
            loadYaml(configFile);
        } else {
            loadProperties(configFile);
        }
    }
    
    private void loadYaml(String configFile) throws IOException {
        InputStream input = getClass().getClassLoader().getResourceAsStream(configFile);
        if (input == null) {
            // Essayer depuis le système de fichiers
            try (FileInputStream fileInput = new FileInputStream(configFile)) {
                Yaml yaml = new Yaml();
                Map<String, Object> data = yaml.load(fileInput);
                flattenYaml("", data, properties);
            }
        } else {
            try (input) {
                Yaml yaml = new Yaml();
                Map<String, Object> data = yaml.load(input);
                flattenYaml("", data, properties);
            }
        }
    }
    
    private void loadProperties(String configFile) throws IOException {
        // Essayer de charger depuis le classpath
        try (InputStream input = getClass().getClassLoader().getResourceAsStream(configFile)) {
            if (input != null) {
                properties.load(input);
                return;
            }
        }
        
        // Essayer de charger depuis le système de fichiers
        try (FileInputStream input = new FileInputStream(configFile)) {
            properties.load(input);
        }
    }
    
    @SuppressWarnings("unchecked")
    private void flattenYaml(String prefix, Map<String, Object> map, Properties properties) {
        for (Map.Entry<String, Object> entry : map.entrySet()) {
            String key = prefix.isEmpty() ? entry.getKey() : prefix + "." + entry.getKey();
            Object value = entry.getValue();
            
            if (value instanceof Map) {
                flattenYaml(key, (Map<String, Object>) value, properties);
            } else {
                properties.setProperty(key, value == null ? "" : value.toString());
            }
        }
    }
    
    public String getProperty(String key) {
        return properties.getProperty(key);
    }
    
    public String getProperty(String key, String defaultValue) {
        return properties.getProperty(key, defaultValue);
    }
    
    public String[] getArrayProperty(String key) {
        String value = properties.getProperty(key);
        if (value == null || value.trim().isEmpty()) {
            return new String[0];
        }
        return value.split(",");
    }
    
    public boolean getBooleanProperty(String key, boolean defaultValue) {
        String value = properties.getProperty(key);
        if (value == null) {
            return defaultValue;
        }
        return Boolean.parseBoolean(value);
    }
    
    public void listProperties() {
        log.info("=== Configuration chargée ===");
        properties.forEach((key, value) -> {
            // Masquer les mots de passe
            if (key.toString().toLowerCase().contains("password") || 
                key.toString().toLowerCase().contains("secret")) {
                log.info("{} = ********", key);
            } else {
                log.info("{} = {}", key, value);
            }
        });
        log.info("=============================");
    }
}
