package fr.leuwen.keycloak.config;

import org.apache.http.conn.ssl.NoopHostnameVerifier;
import org.apache.http.conn.ssl.SSLConnectionSocketFactory;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.ssl.SSLContextBuilder;
import org.jboss.resteasy.client.jaxrs.ResteasyClientBuilder;
import org.keycloak.admin.client.Keycloak;
import org.keycloak.admin.client.KeycloakBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.net.ssl.SSLContext;

/**
 * Configuration pour le client Keycloak Admin
 * Désactive la validation SSL pour accepter les certificats auto-signés en staging/dev
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
            // Créer un HTTP client qui accepte tous les certificats SSL (pour dev/staging)
            SSLContext sslContext = SSLContextBuilder.create()
                    .loadTrustMaterial((chain, authType) -> true) // Trust all certificates
                    .build();
            
            SSLConnectionSocketFactory sslSocketFactory = new SSLConnectionSocketFactory(
                    sslContext,
                    NoopHostnameVerifier.INSTANCE // Disable hostname verification
            );
            
            CloseableHttpClient httpClient = HttpClients.custom()
                    .setSSLSocketFactory(sslSocketFactory)
                    .build();
            
            logger.warn("⚠️  Validation SSL désactivée - À utiliser UNIQUEMENT en dev/staging!");

            // Créer le client Keycloak avec le HTTP client custom
            org.jboss.resteasy.client.jaxrs.ResteasyClient resteasyClient = 
                ((ResteasyClientBuilder) ResteasyClientBuilder.newBuilder())
                    .httpEngine(new org.jboss.resteasy.client.jaxrs.engines.ApacheHttpClient43Engine(httpClient))
                    .build();

            return KeycloakBuilder.builder()
                    .serverUrl(properties.getServerUrl())
                    .realm(properties.getAdmin().getRealm())
                    .username(properties.getAdmin().getUsername())
                    .password(properties.getAdmin().getPassword())
                    .clientId("admin-cli")
                    .resteasyClient(resteasyClient)
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
