package fr.leuwen.keycloak;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

import fr.leuwen.keycloak.config.KeycloakProperties;

/**
 * Application Spring Boot pour initialiser Keycloak
 * Remplace l'ancien KeycloakInitializer avec une approche Spring Boot moderne
 * 
 * Usage:
 * java -jar rhDemoInitKeycloak-1.0.0.jar
 * 
 * @author Leuwen
 * @version 2.0.0 (Spring Boot)
 */
@SpringBootApplication
@EnableConfigurationProperties(KeycloakProperties.class)
public class KeycloakInitializerApplication {

    public static void main(String[] args) {
        // Désactiver la bannière Spring Boot pour une sortie plus propre
        SpringApplication app = new SpringApplication(KeycloakInitializerApplication.class);
        app.setBannerMode(org.springframework.boot.Banner.Mode.OFF);
        app.run(args);
    }
}
