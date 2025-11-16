package fr.leuwen.keycloak.service;

import org.keycloak.admin.client.Keycloak;
import org.keycloak.representations.idm.ClientRepresentation;
import org.keycloak.representations.idm.ProtocolMapperRepresentation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import fr.leuwen.keycloak.config.KeycloakProperties;

import jakarta.ws.rs.core.Response;
import java.util.*;

/**
 * Service pour créer et configurer le Client RHDemo dans Keycloak
 */
public class ClientService {
    
    private static final Logger logger = LoggerFactory.getLogger(ClientService.class);
    private final Keycloak keycloak;
    private final KeycloakProperties properties;
    private final String realmName;
    
    public ClientService(Keycloak keycloak, KeycloakProperties properties) {
        this.keycloak = keycloak;
        this.properties = properties;
        this.realmName = properties.getRealm().getName();
    }
    
    /**
     * Crée le client RHDemo (supprime et recrée s'il existe déjà pour forcer la mise à jour)
     * @return L'ID interne du client créé, null en cas d'erreur
     */
    public String createClient() {
        String clientId = properties.getClient().getClientId();
        
        try {
            logger.info("🔍 Vérification de l'existence du client '{}'...", clientId);
            
            // Vérifier si le client existe déjà
            List<ClientRepresentation> existingClients = keycloak.realm(realmName)
                    .clients()
                    .findByClientId(clientId);
            
            if (!existingClients.isEmpty()) {
                String existingId = existingClients.get(0).getId();
                logger.warn("⚠️  Le client '{}' existe déjà (ID: {}), suppression pour recréation...", clientId, existingId);
                keycloak.realm(realmName).clients().get(existingId).remove();
                logger.info("✅ Client existant supprimé");
            }
            
            logger.info("➡️ Création du client '{}'...", clientId);
            
            // Créer le nouveau client
            ClientRepresentation client = buildClientRepresentation();
            //debug jenkins
            logger.info(client.toString());
            
            // Créer le client via l'API
            try (Response response = keycloak.realm(realmName).clients().create(client)) {
                if (response.getStatus() == 201) {
                    // Récupérer l'ID du client créé depuis le header Location
                    String location = response.getHeaderString("Location");
                    String internalClientId = location.substring(location.lastIndexOf('/') + 1);
                    
                    logger.info("✅ Client '{}' créé avec succès! ID interne: {}", clientId, internalClientId);
                    return internalClientId;
                } else {
                    logger.error("❌ Échec de la création du client. Status: {}", response.getStatus());
                    logger.error("Raison: {}", response.getStatusInfo().getReasonPhrase());
                    return null;
                }
            }
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la création du client '{}'", clientId, e);
            return null;
        }
    }
    
    /**
     * Construit la représentation du client basée sur RHDemo.json et application.properties
     */
    private ClientRepresentation buildClientRepresentation() {
        ClientRepresentation client = new ClientRepresentation();
        
        // Identifiants et noms
        client.setClientId(properties.getClient().getClientId());
        client.setName(properties.getClient().getName());
        client.setDescription("authent des users API et Admin de RHDemo");
        
        // URLs
        client.setRootUrl(properties.getClient().getRootUrl());
        client.setBaseUrl(properties.getClient().getBaseUrl());
        client.setAdminUrl(properties.getClient().getAdminUrl());
        
        // Redirect URIs et Web Origins
        client.setRedirectUris(properties.getClient().getRedirectUris());
        client.setWebOrigins(properties.getClient().getWebOrigins());
        
    // Configuration d'authentification
    client.setEnabled(true);
    // CRITICAL: Forcer le client authenticator à 'client-secret' (équivalent à 'Client Id and Secret' dans l'admin UI)
    client.setClientAuthenticatorType("client-secret");
    client.setSecret(properties.getClient().getSecret());

    // Flow configuration
    client.setStandardFlowEnabled(true);
    client.setImplicitFlowEnabled(false);
    client.setDirectAccessGrantsEnabled(true);
    client.setServiceAccountsEnabled(false);
    client.setPublicClient(false);
    client.setFrontchannelLogout(true);
        
        // Protocol et autres paramètres
        client.setProtocol("openid-connect");
        client.setSurrogateAuthRequired(false);
        client.setBearerOnly(false);
        client.setAlwaysDisplayInConsole(false);
        client.setFullScopeAllowed(true);
        
        // Attributs additionnels
        Map<String, String> attributes = new HashMap<>();
        attributes.put("oidc.ciba.grant.enabled", "false");
        attributes.put("backchannel.logout.session.required", "true");
        attributes.put("login_theme", "base");
        attributes.put("display.on.consent.screen", "false");
        attributes.put("oauth2.device.authorization.grant.enabled", "false");
        attributes.put("backchannel.logout.revoke.offline.tokens", "false");
        client.setAttributes(attributes);
        
        // Protocol Mappers - Configuration pour mapper les client roles
        List<ProtocolMapperRepresentation> protocolMappers = new ArrayList<>();
        protocolMappers.add(createClientRolesMapper());
        client.setProtocolMappers(protocolMappers);
        
        // Default Client Scopes
        client.setDefaultClientScopes(Arrays.asList("web-origins", "acr", "profile", "roles", "email"));
        
        // Optional Client Scopes
        client.setOptionalClientScopes(Arrays.asList("address", "phone", "offline_access", "microprofile-jwt"));
        
        return client;
    }
    
    /**
     * Crée le Protocol Mapper pour les client roles
     * Correspond au mapper "client roles" dans RHDemo.json
     */
    private ProtocolMapperRepresentation createClientRolesMapper() {
        ProtocolMapperRepresentation mapper = new ProtocolMapperRepresentation();
        
        mapper.setName("client roles");
        mapper.setProtocol("openid-connect");
        mapper.setProtocolMapper("oidc-usermodel-client-role-mapper");
        // setConsentRequired a été supprimé dans les versions récentes de Keycloak
        
        Map<String, String> config = new HashMap<>();
        config.put("introspection.token.claim", "true");
        config.put("multivalued", "true");
        config.put("userinfo.token.claim", "true");  // CRITICAL: Inclure dans UserInfo endpoint pour Spring Security OAuth2
        config.put("user.attribute", "foo");
        config.put("id.token.claim", "true");  // IMPORTANT: Inclure dans l'ID token pour OAuth2 sans userinfo
        config.put("lightweight.claim", "false");
        config.put("access.token.claim", "true");
        config.put("claim.name", "resource_access.${client_id}.roles");
        config.put("jsonType.label", "String");
        
        mapper.setConfig(config);
        
        return mapper;
    }
    
    /**
     * Récupère l'ID interne du client par son clientId
     */
    public String getClientInternalId(String clientId) {
        try {
            List<ClientRepresentation> clients = keycloak.realm(realmName)
                    .clients()
                    .findByClientId(clientId);
            
            if (!clients.isEmpty()) {
                return clients.get(0).getId();
            }
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la récupération de l'ID du client '{}'", clientId, e);
        }
        return null;
    }
    
    /**
     * Affiche les informations du client
     */
    public void displayClientInfo(String clientId) {
        try {
            List<ClientRepresentation> clients = keycloak.realm(realmName)
                    .clients()
                    .findByClientId(clientId);
            
            if (clients.isEmpty()) {
                logger.warn("⚠️ Client '{}' non trouvé", clientId);
                return;
            }
            
            ClientRepresentation client = clients.get(0);
            logger.info("=== Informations du Client '{}' ===", clientId);
            logger.info("ID interne: {}", client.getId());
            logger.info("Nom: {}", client.getName());
            logger.info("Description: {}", client.getDescription());
            logger.info("Root URL: {}", client.getRootUrl());
            logger.info("Redirect URIs: {}", client.getRedirectUris());
            logger.info("Enabled: {}", client.isEnabled());
            logger.info("Protocol: {}", client.getProtocol());
            logger.info("=====================================");
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la récupération des informations du client", e);
        }
    }
}
