package fr.leuwen.keycloak.service;

import org.keycloak.admin.client.Keycloak;
import org.keycloak.representations.idm.RealmRepresentation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import fr.leuwen.keycloak.ConfigLoader;

/**
 * Service pour créer et configurer le Realm Keycloak
 */
public class RealmService {
    
    private static final Logger logger = LoggerFactory.getLogger(RealmService.class);
    private final Keycloak keycloak;
    private final ConfigLoader config;
    
    public RealmService(Keycloak keycloak, ConfigLoader config) {
        this.keycloak = keycloak;
        this.config = config;
    }
    
    /**
     * Crée le realm LeuwenRealm s'il n'existe pas déjà
     * @return true si le realm a été créé ou existe déjà, false en cas d'erreur
     */
    public boolean createRealm() {
        String realmName = config.getProperty("keycloak.realm.name", "LeuwenRealm");
        
        try {
            logger.info("🔍 Vérification de l'existence du realm '{}'...", realmName);
            
            // Vérifier si le realm existe déjà
            try {
                RealmRepresentation existingRealm = keycloak.realm(realmName).toRepresentation();
                if (existingRealm != null) {
                    logger.info("✅ Le realm '{}' existe déjà", realmName);
                    return true;
                }
            } catch (Exception e) {
                // Le realm n'existe pas, on va le créer
                logger.info("➡️ Le realm '{}' n'existe pas, création en cours...", realmName);
            }
            
            // Créer le nouveau realm
            RealmRepresentation realm = new RealmRepresentation();
            realm.setRealm(realmName);
            realm.setDisplayName(config.getProperty("keycloak.realm.displayName", "Leuwen Realm"));
            realm.setEnabled(config.getBooleanProperty("keycloak.realm.enabled", true));
            
            // Configuration de sécurité recommandée
            realm.setRegistrationAllowed(false);
            realm.setRegistrationEmailAsUsername(false);
            realm.setResetPasswordAllowed(true);
            realm.setEditUsernameAllowed(false);
            realm.setLoginWithEmailAllowed(true);
            realm.setDuplicateEmailsAllowed(false);
            
            // Paramètres de session
            realm.setSsoSessionIdleTimeout(1800); // 30 minutes
            realm.setSsoSessionMaxLifespan(36000); // 10 heures
            realm.setAccessTokenLifespan(300); // 5 minutes
            
            // Créer le realm via l'API
            keycloak.realms().create(realm);
            logger.info("✅ Realm '{}' créé avec succès!", realmName);
            return true;
            
        } catch (jakarta.ws.rs.ClientErrorException e) {
            if (e.getResponse().getStatus() == 409) {
                logger.info("ℹ️ Le realm '{}' existe déjà (HTTP 409)", realmName);
                return true; // Considérer comme un succès
            }
            logger.error("❌ Erreur lors de la création du realm '{}': HTTP {}", realmName, e.getResponse().getStatus(), e);
            return false;
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la création du realm '{}'", realmName, e);
            return false;
        }
    }
    
    /**
     * Supprime le realm (utile pour les tests)
     * @return true si le realm a été supprimé, false sinon
     */
    public boolean deleteRealm() {
        String realmName = config.getProperty("keycloak.realm.name", "LeuwenRealm");
        
        try {
            logger.warn("⚠️ Suppression du realm '{}'...", realmName);
            keycloak.realm(realmName).remove();
            logger.info("✅ Realm '{}' supprimé avec succès", realmName);
            return true;
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la suppression du realm '{}'", realmName, e);
            return false;
        }
    }
    
    /**
     * Affiche les informations du realm
     */
    public void displayRealmInfo() {
        String realmName = config.getProperty("keycloak.realm.name", "LeuwenRealm");
        
        try {
            RealmRepresentation realm = keycloak.realm(realmName).toRepresentation();
            logger.info("=== Informations du Realm '{}' ===", realmName);
            logger.info("Display Name: {}", realm.getDisplayName());
            logger.info("Enabled: {}", realm.isEnabled());
            logger.info("Registration Allowed: {}", realm.isRegistrationAllowed());
            logger.info("Login With Email: {}", realm.isLoginWithEmailAllowed());
            logger.info("SSO Session Idle Timeout: {} secondes", realm.getSsoSessionIdleTimeout());
            logger.info("Access Token Lifespan: {} secondes", realm.getAccessTokenLifespan());
            logger.info("=====================================");
        } catch (Exception e) {
            logger.error("❌ Impossible de récupérer les informations du realm '{}'", realmName, e);
        }
    }
}
