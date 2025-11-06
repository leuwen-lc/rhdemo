package fr.leuwen.keycloak.service;

import org.keycloak.admin.client.Keycloak;
import org.keycloak.representations.idm.CredentialRepresentation;
import org.keycloak.representations.idm.RoleRepresentation;
import org.keycloak.representations.idm.UserRepresentation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import fr.leuwen.keycloak.ConfigLoader;

import jakarta.ws.rs.core.Response;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Service pour créer et gérer les utilisateurs dans Keycloak
 */
public class UserService {
    
    private static final Logger logger = LoggerFactory.getLogger(UserService.class);
    private final Keycloak keycloak;
    private final ConfigLoader config;
    private final String realmName;
    
    public UserService(Keycloak keycloak, ConfigLoader config) {
        this.keycloak = keycloak;
        this.config = config;
        this.realmName = config.getProperty("keycloak.realm.name", "LeuwenRealm");
    }
    
    /**
     * Crée tous les utilisateurs définis dans la configuration
     * @param clientInternalId L'ID interne du client pour l'assignation des rôles
     * @return true si tous les utilisateurs ont été créés avec succès, false sinon
     */
    public boolean createAllUsers(String clientInternalId) {
        logger.info("👥 Création des utilisateurs...");
        
        boolean allSuccess = true;
        
        // Créer admil
        if (!createUser("admil", clientInternalId)) {
            allSuccess = false;
        }
        
        // Créer consuela
        if (!createUser("consuela", clientInternalId)) {
            allSuccess = false;
        }
        
        // Créer madjid
        if (!createUser("madjid", clientInternalId)) {
            allSuccess = false;
        }
        
        return allSuccess;
    }
    
    /**
     * Crée un utilisateur spécifique avec ses rôles
     * @param userKey La clé de l'utilisateur dans la configuration (ex: "admil", "consuela", "madjid")
     * @param clientInternalId L'ID interne du client pour l'assignation des rôles
     * @return true si l'utilisateur a été créé avec succès, false sinon
     */
    public boolean createUser(String userKey, String clientInternalId) {
        String username = config.getProperty("keycloak.users." + userKey + ".username");
        String password = config.getProperty("keycloak.users." + userKey + ".password");
        String email = config.getProperty("keycloak.users." + userKey + ".email");
        String firstname = config.getProperty("keycloak.users." + userKey + ".firstname");
        String lastname = config.getProperty("keycloak.users." + userKey + ".lastname");
        String rolesStr = config.getProperty("keycloak.users." + userKey + ".roles");
        
        if (username == null || password == null) {
            logger.error("❌ Configuration incomplète pour l'utilisateur '{}'", userKey);
            return false;
        }
        
        try {
            logger.info("🔍 Vérification de l'utilisateur '{}'...", username);
            
            // Vérifier si l'utilisateur existe déjà
            List<UserRepresentation> existingUsers = keycloak.realm(realmName)
                    .users()
                    .search(username);
            
            String userId = null;
            boolean userExists = false;
            
            for (UserRepresentation user : existingUsers) {
                if (user.getUsername().equals(username)) {
                    logger.info("✅ L'utilisateur '{}' existe déjà", username);
                    userId = user.getId();
                    userExists = true;
                    break;
                }
            }
            
            // Créer l'utilisateur s'il n'existe pas
            if (!userExists) {
                logger.info("➡️ L'utilisateur '{}' n'existe pas, création en cours...", username);
                
                UserRepresentation user = buildUserRepresentation(
                        username, password, email, firstname, lastname);
                
                try (Response response = keycloak.realm(realmName).users().create(user)) {
                    if (response.getStatus() == 201) {
                        // Récupérer l'ID de l'utilisateur créé
                        String location = response.getHeaderString("Location");
                        userId = location.substring(location.lastIndexOf('/') + 1);
                        
                        logger.info("✅ Utilisateur '{}' créé avec succès! ID: {}", username, userId);
                    } else {
                        logger.error("❌ Échec de la création de l'utilisateur '{}'. Status: {}", 
                                username, response.getStatus());
                        return false;
                    }
                }
            }
            
            // Assigner les rôles client
            if (rolesStr != null && !rolesStr.trim().isEmpty() && userId != null) {
                String[] roles = rolesStr.split(",");
                assignClientRolesToUser(userId, clientInternalId, roles);
            }
            
            return true;
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la création de l'utilisateur '{}'", username, e);
            return false;
        }
    }
    
    /**
     * Construit la représentation d'un utilisateur
     */
    private UserRepresentation buildUserRepresentation(
            String username, String password, String email, 
            String firstname, String lastname) {
        
        UserRepresentation user = new UserRepresentation();
        user.setEnabled(true);
        user.setUsername(username);
        user.setEmail(email);
        user.setFirstName(firstname);
        user.setLastName(lastname);
        user.setEmailVerified(true);
        
        // Définir le mot de passe
        CredentialRepresentation credential = new CredentialRepresentation();
        credential.setType(CredentialRepresentation.PASSWORD);
        credential.setValue(password);
        credential.setTemporary(false); // Le mot de passe n'est pas temporaire
        
        user.setCredentials(Arrays.asList(credential));
        
        return user;
    }
    
    /**
     * Assigne des client roles à un utilisateur
     * @param userId L'ID de l'utilisateur
     * @param clientInternalId L'ID interne du client
     * @param roleNames Les noms des rôles à assigner
     */
    public void assignClientRolesToUser(String userId, String clientInternalId, String[] roleNames) {
        try {
            List<RoleRepresentation> rolesToAssign = new ArrayList<>();
            
            for (String roleName : roleNames) {
                String trimmedRoleName = roleName.trim();
                
                try {
                    RoleRepresentation role = keycloak.realm(realmName)
                            .clients()
                            .get(clientInternalId)
                            .roles()
                            .get(trimmedRoleName)
                            .toRepresentation();
                    
                    rolesToAssign.add(role);
                    logger.info("➡️ Assignation du role '{}' à l'utilisateur ID {}", trimmedRoleName, userId);
                    
                } catch (Exception e) {
                    logger.error("❌ Role '{}' non trouvé", trimmedRoleName, e);
                }
            }
            
            if (!rolesToAssign.isEmpty()) {
                keycloak.realm(realmName)
                        .users()
                        .get(userId)
                        .roles()
                        .clientLevel(clientInternalId)
                        .add(rolesToAssign);
                
                logger.info("✅ {} role(s) assigné(s) avec succès à l'utilisateur ID {}", 
                        rolesToAssign.size(), userId);
            }
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de l'assignation des rôles à l'utilisateur ID {}", userId, e);
        }
    }
    
    /**
     * Liste tous les utilisateurs du realm
     */
    public void listAllUsers() {
        try {
            List<UserRepresentation> users = keycloak.realm(realmName).users().list();
            
            logger.info("=== Utilisateurs du Realm '{}' ===", realmName);
            if (users.isEmpty()) {
                logger.info("Aucun utilisateur trouvé");
            } else {
                for (UserRepresentation user : users) {
                    logger.info("- {} ({} {}) - Email: {} - Enabled: {}", 
                            user.getUsername(),
                            user.getFirstName(),
                            user.getLastName(),
                            user.getEmail(),
                            user.isEnabled());
                }
            }
            logger.info("=====================================");
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la récupération des utilisateurs", e);
        }
    }
    
    /**
     * Affiche les rôles client d'un utilisateur
     * @param username Le nom d'utilisateur
     * @param clientInternalId L'ID interne du client
     */
    public void displayUserClientRoles(String username, String clientInternalId) {
        try {
            List<UserRepresentation> users = keycloak.realm(realmName)
                    .users()
                    .search(username);
            
            if (users.isEmpty()) {
                logger.warn("⚠️ Utilisateur '{}' non trouvé", username);
                return;
            }
            
            String userId = users.get(0).getId();
            
            List<RoleRepresentation> clientRoles = keycloak.realm(realmName)
                    .users()
                    .get(userId)
                    .roles()
                    .clientLevel(clientInternalId)
                    .listEffective();
            
            logger.info("=== Client Roles de '{}' ===", username);
            if (clientRoles.isEmpty()) {
                logger.info("Aucun client role assigné");
            } else {
                for (RoleRepresentation role : clientRoles) {
                    logger.info("- {}", role.getName());
                }
            }
            logger.info("================================");
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la récupération des rôles de '{}'", username, e);
        }
    }
    
    /**
     * Supprime un utilisateur
     * @param username Le nom d'utilisateur à supprimer
     * @return true si l'utilisateur a été supprimé, false sinon
     */
    public boolean deleteUser(String username) {
        try {
            List<UserRepresentation> users = keycloak.realm(realmName)
                    .users()
                    .search(username);
            
            if (users.isEmpty()) {
                logger.warn("⚠️ Utilisateur '{}' non trouvé", username);
                return false;
            }
            
            String userId = users.get(0).getId();
            
            logger.warn("⚠️ Suppression de l'utilisateur '{}'...", username);
            keycloak.realm(realmName).users().delete(userId);
            
            logger.info("✅ Utilisateur '{}' supprimé avec succès", username);
            return true;
            
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la suppression de l'utilisateur '{}'", username, e);
            return false;
        }
    }
}
