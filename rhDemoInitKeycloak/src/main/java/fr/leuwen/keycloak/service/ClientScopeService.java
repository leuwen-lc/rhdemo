package fr.leuwen.keycloak.service;

import org.keycloak.admin.client.Keycloak;
import org.keycloak.representations.idm.ClientScopeRepresentation;
import org.keycloak.representations.idm.ProtocolMapperRepresentation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import fr.leuwen.keycloak.config.KeycloakProperties;

import java.util.List;
import java.util.Map;

/**
 * Service pour configurer les Client Scopes dans Keycloak
 */
public class ClientScopeService {
    
    private static final Logger logger = LoggerFactory.getLogger(ClientScopeService.class);
    private final Keycloak keycloak;
    private final String realmName;
    
    public ClientScopeService(Keycloak keycloak, KeycloakProperties properties) {
        this.keycloak = keycloak;
        this.realmName = properties.getRealm().getName();
    }
    
    /**
     * Configure le client scope "roles" pour ajouter les rôles au token ID
     * Important car sinon impossible de récupérer les roles dans l'applicatio 
     * ce qui déclenchera une erreur sur GrantedAuthoritiesKeyCloakMapper
     * @return true si la configuration a réussi, false sinon
     */
    public boolean configureRolesClientScope() {
        try {
            logger.info("🔧 Configuration du client scope 'roles'...");
            
            // Récupérer le client scope "roles"
            List<ClientScopeRepresentation> clientScopes = keycloak.realm(realmName)
                    .clientScopes()
                    .findAll();
            
            ClientScopeRepresentation rolesScope = null;
            for (ClientScopeRepresentation scope : clientScopes) {
                if ("roles".equals(scope.getName())) {
                    rolesScope = scope;
                    break;
                }
            }
            
            if (rolesScope == null) {
                logger.error("❌ Client scope 'roles' non trouvé");
                return false;
            }
            
            logger.info("✅ Client scope 'roles' trouvé: {}", rolesScope.getId());
            
            // Récupérer les protocol mappers du scope
            List<ProtocolMapperRepresentation> mappers = keycloak.realm(realmName)
                    .clientScopes()
                    .get(rolesScope.getId())
                    .getProtocolMappers()
                    .getMappers();
            
            // Trouver le mapper "client roles"
            ProtocolMapperRepresentation clientRolesMapper = null;
            for (ProtocolMapperRepresentation mapper : mappers) {
                if ("client roles".equals(mapper.getName())) {
                    clientRolesMapper = mapper;
                    break;
                }
            }
            
            if (clientRolesMapper == null) {
                logger.error("❌ Mapper 'client roles' non trouvé dans le scope 'roles'");
                return false;
            }
            
            logger.info("🔍 Mapper 'client roles' trouvé: {}", clientRolesMapper.getId());
            
            // Vérifier si id.token.claim est déjà activé
            Map<String, String> config = clientRolesMapper.getConfig();
            String currentValue = config.get("id.token.claim");
            
            if ("true".equals(currentValue)) {
                logger.info("✅ Le mapper 'client roles' a déjà 'Add to ID token' activé");
                return true;
            }
            
            // Activer "Add to ID token"
            logger.info("➡️ Activation de 'Add to ID token' pour le mapper 'client roles'...");
            config.put("id.token.claim", "true");
            clientRolesMapper.setConfig(config);
            
            // Mettre à jour le mapper
            keycloak.realm(realmName)
                    .clientScopes()
                    .get(rolesScope.getId())
                    .getProtocolMappers()
                    .update(clientRolesMapper.getId(), clientRolesMapper);
            
            logger.info("✅ Mapper 'client roles' mis à jour avec 'Add to ID token' = true");
            return true;
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la configuration du client scope 'roles'", e);
            return false;
        }
    }
    
    /**
     * Affiche les informations du client scope "roles"
     */
    public void displayRolesClientScopeInfo() {
        try {
            List<ClientScopeRepresentation> clientScopes = keycloak.realm(realmName)
                    .clientScopes()
                    .findAll();
            
            ClientScopeRepresentation rolesScope = null;
            for (ClientScopeRepresentation scope : clientScopes) {
                if ("roles".equals(scope.getName())) {
                    rolesScope = scope;
                    break;
                }
            }
            
            if (rolesScope == null) {
                logger.warn("⚠️ Client scope 'roles' non trouvé");
                return;
            }
            
            List<ProtocolMapperRepresentation> mappers = keycloak.realm(realmName)
                    .clientScopes()
                    .get(rolesScope.getId())
                    .getProtocolMappers()
                    .getMappers();
            
            logger.info("=== Client Scope 'roles' - Protocol Mappers ===");
            for (ProtocolMapperRepresentation mapper : mappers) {
                if ("client roles".equals(mapper.getName())) {
                    Map<String, String> config = mapper.getConfig();
                    logger.info("Mapper: {}", mapper.getName());
                    logger.info("  - Protocol: {}", mapper.getProtocol());
                    logger.info("  - Protocol Mapper: {}", mapper.getProtocolMapper());
                    logger.info("  - Add to ID token: {}", config.get("id.token.claim"));
                    logger.info("  - Add to access token: {}", config.get("access.token.claim"));
                    logger.info("  - Add to userinfo: {}", config.get("userinfo.token.claim"));
                }
            }
            logger.info("===============================================");
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la récupération des infos du client scope 'roles'", e);
        }
    }
}
