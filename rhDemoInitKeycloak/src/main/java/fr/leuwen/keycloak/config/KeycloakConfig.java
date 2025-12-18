package fr.leuwen.keycloak.config;

import org.keycloak.admin.client.Keycloak;
import org.keycloak.admin.client.KeycloakBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Configuration pour le client Keycloak Admin
 * Désactive la validation SSL pour accepter les certificats auto-signés en ephemere/dev
 */
@Configuration
public class KeycloakConfig {

    private static final Logger logger = LoggerFactory.getLogger(KeycloakConfig.class);
    
    @Bean
    public Keycloak keycloak(KeycloakProperties properties) {
        logger.info("🔌 Connexion au serveur Keycloak...");
        logger.info("   🔗 Serveur: {}", properties.getServerUrl());
        logger.info("   🏛️ Realm admin: {}", properties.getAdmin().getRealm());
        logger.info("   👤 Utilisateur admin: {}", properties.getAdmin().getUsername());

        try {
            // STRATÉGIE: Utiliser le client HTTP par défaut de Resteasy (pas de custom Apache HttpClient)
            // L'erreur "unable to read contents from stream" pourrait être causée par le ApacheHttpClient43Engine
            // qui a des problèmes avec certains payloads JSON
            
            logger.warn("⚠️  Utilisation du client HTTP par défaut (SSL non vérifié via système)");
            logger.warn("⚠️  Pour ephemere: s'assurer que le serveur Keycloak utilise HTTP (pas HTTPS)");

            // Client Keycloak avec configuration par défaut (plus simple et moins de problèmes potentiels)
            return KeycloakBuilder.builder()
                    .serverUrl(properties.getServerUrl())
                    .realm(properties.getAdmin().getRealm())
                    .username(properties.getAdmin().getUsername())
                    .password(properties.getAdmin().getPassword())
                    .clientId("admin-cli")
                    .build();

        } catch (Exception e) {
            logger.error("❌ Impossible de se connecter à Keycloak. Vérifiez que:");
            logger.error("   - Keycloak est démarré sur {}", properties.getServerUrl());
            logger.error("   - Les credentials admin sont corrects");
            logger.error("   - Le realm '{}' existe", properties.getAdmin().getRealm());
            throw new RuntimeException("Échec de connexion à Keycloak", e);
        }
    }
}
