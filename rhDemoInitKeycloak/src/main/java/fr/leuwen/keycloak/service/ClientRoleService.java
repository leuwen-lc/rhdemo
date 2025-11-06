package fr.leuwen.keycloak.service;

import org.keycloak.admin.client.Keycloak;
import org.keycloak.admin.client.resource.RoleResource;
import org.keycloak.representations.idm.RoleRepresentation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import fr.leuwen.keycloak.ConfigLoader;

import java.util.List;

/**
 * Service pour créer et gérer les Client Roles dans Keycloak
 */
public class ClientRoleService {
    
    private static final Logger logger = LoggerFactory.getLogger(ClientRoleService.class);
    private final Keycloak keycloak;
    private final ConfigLoader config;
    private final String realmName;
    
    public ClientRoleService(Keycloak keycloak, ConfigLoader config) {
        this.keycloak = keycloak;
        this.config = config;
        this.realmName = config.getProperty("keycloak.realm.name", "LeuwenRealm");
    }
    
    /**
     * Crée tous les client roles définis dans la configuration
     * @param clientInternalId L'ID interne du client
     * @return true si tous les rôles ont été créés avec succès, false sinon
     */
    public boolean createClientRoles(String clientInternalId) {
        String[] roles = config.getArrayProperty("keycloak.client.roles");
        
        if (roles.length == 0) {
            logger.warn("⚠️ Aucun client role défini dans la configuration");
            return true;
        }
        
        logger.info("🔧 Création de {} client roles...", roles.length);
        boolean allSuccess = true;
        
        for (String roleName : roles) {
            if (!createClientRole(clientInternalId, roleName.trim())) {
                allSuccess = false;
            }
        }
        
        return allSuccess;
    }
    
    /**
     * Crée un client role spécifique
     * @param clientInternalId L'ID interne du client
     * @param roleName Le nom du rôle à créer
     * @return true si le rôle a été créé ou existe déjà, false en cas d'erreur
     */
    public boolean createClientRole(String clientInternalId, String roleName) {
        try {
            logger.info("🔍 Vérification du role '{}'...", roleName);
            
            // Vérifier si le rôle existe déjà
            try {
                RoleRepresentation existingRole = keycloak.realm(realmName)
                        .clients()
                        .get(clientInternalId)
                        .roles()
                        .get(roleName)
                        .toRepresentation();
                
                if (existingRole != null) {
                    logger.info("✅ Le role '{}' existe déjà", roleName);
                    return true;
                }
            } catch (Exception e) {
                // Le rôle n'existe pas, on va le créer
                logger.info("➡️ Le role '{}' n'existe pas, création en cours...", roleName);
            }
            
            // Créer le nouveau rôle
            RoleRepresentation role = new RoleRepresentation();
            role.setName(roleName);
            role.setDescription("Client role " + roleName + " pour RHDemo");
            role.setClientRole(true);
            
            // Créer le rôle via l'API
            keycloak.realm(realmName)
                    .clients()
                    .get(clientInternalId)
                    .roles()
                    .create(role);
            
            logger.info("✅ Role '{}' créé avec succès!", roleName);
            return true;
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la création du role '{}'", roleName, e);
            return false;
        }
    }
    
    /**
     * Liste tous les client roles d'un client
     * @param clientInternalId L'ID interne du client
     */
    public void listClientRoles(String clientInternalId) {
        try {
            List<RoleRepresentation> roles = keycloak.realm(realmName)
                    .clients()
                    .get(clientInternalId)
                    .roles()
                    .list();
            
            logger.info("=== Client Roles ===");
            if (roles.isEmpty()) {
                logger.info("Aucun client role trouvé");
            } else {
                for (RoleRepresentation role : roles) {
                    logger.info("- {} (ID: {}, Description: {})", 
                            role.getName(), 
                            role.getId(), 
                            role.getDescription());
                }
            }
            logger.info("====================");
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la récupération des client roles", e);
        }
    }
    
    /**
     * Récupère un client role par son nom
     * @param clientInternalId L'ID interne du client
     * @param roleName Le nom du rôle
     * @return La représentation du rôle, ou null si non trouvé
     */
    public RoleRepresentation getClientRole(String clientInternalId, String roleName) {
        try {
            return keycloak.realm(realmName)
                    .clients()
                    .get(clientInternalId)
                    .roles()
                    .get(roleName)
                    .toRepresentation();
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la récupération du role '{}'", roleName, e);
            return null;
        }
    }
    
    /**
     * Supprime un client role
     * @param clientInternalId L'ID interne du client
     * @param roleName Le nom du rôle à supprimer
     * @return true si le rôle a été supprimé, false sinon
     */
    public boolean deleteClientRole(String clientInternalId, String roleName) {
        try {
            logger.warn("⚠️ Suppression du role '{}'...", roleName);
            
            RoleResource roleResource = keycloak.realm(realmName)
                    .clients()
                    .get(clientInternalId)
                    .roles()
                    .get(roleName);
            
            roleResource.remove();
            
            logger.info("✅ Role '{}' supprimé avec succès", roleName);
            return true;
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la suppression du role '{}'", roleName, e);
            return false;
        }
    }
}
