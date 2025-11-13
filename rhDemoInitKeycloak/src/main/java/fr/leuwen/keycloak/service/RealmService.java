package fr.leuwen.keycloak.service;

import org.keycloak.admin.client.Keycloak;
import org.keycloak.representations.idm.RealmRepresentation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import fr.leuwen.keycloak.config.KeycloakProperties;

/**
 * Service pour créer et configurer le Realm Keycloak
 */
public class RealmService {
    
    private static final Logger logger = LoggerFactory.getLogger(RealmService.class);
    private final Keycloak keycloak;
    private final KeycloakProperties properties;
    
    public RealmService(Keycloak keycloak, KeycloakProperties properties) {
        this.keycloak = keycloak;
        this.properties = properties;
    }
    
    /**
     * Crée le realm LeuwenRealm s'il n'existe pas déjà
     * @return true si le realm a été créé ou existe déjà, false en cas d'erreur
     */
    public boolean createRealm() {
        String realmName = properties.getRealm().getName();
        
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
            realm.setDisplayName(properties.getRealm().getDisplayName());
            realm.setEnabled(properties.getRealm().isEnabled());
            
            // Configuration de sécurité recommandée
            realm.setRegistrationAllowed(properties.getRealm().isRegistrationAllowed());
            realm.setRegistrationEmailAsUsername(properties.getRealm().isRegistrationEmailAsUsername());
            realm.setResetPasswordAllowed(properties.getRealm().isResetPasswordAllowed());
            realm.setEditUsernameAllowed(properties.getRealm().isEditUsernameAllowed());
            realm.setLoginWithEmailAllowed(properties.getRealm().isLoginWithEmailAllowed());
            realm.setDuplicateEmailsAllowed(properties.getRealm().isDuplicateEmailsAllowed());
            
            // Paramètres de session
            realm.setSsoSessionIdleTimeout(properties.getRealm().getSsoSessionIdleTimeout());
            realm.setSsoSessionMaxLifespan(properties.getRealm().getSsoSessionMaxLifespan());
            realm.setAccessTokenLifespan(properties.getRealm().getAccessTokenLifespan());
            
            // DEBUG: Logger la représentation complète avant envoi
            logger.info("═══════════════════════════════════════════════════════════");
            logger.info("🔍 DEBUG: RealmRepresentation à envoyer à Keycloak:");
            logger.info("   - realm: {}", realm.getRealm());
            logger.info("   - displayName: {}", realm.getDisplayName());
            logger.info("   - enabled: {}", realm.isEnabled());
            logger.info("   - registrationAllowed: {}", realm.isRegistrationAllowed());
            logger.info("   - loginWithEmailAllowed: {}", realm.isLoginWithEmailAllowed());
            logger.info("   - ssoSessionIdleTimeout: {}", realm.getSsoSessionIdleTimeout());
            logger.info("   - ssoSessionMaxLifespan: {}", realm.getSsoSessionMaxLifespan());
            logger.info("   - accessTokenLifespan: {}", realm.getAccessTokenLifespan());
            logger.info("═══════════════════════════════════════════════════════════");
            
            // Créer le realm via l'API
            keycloak.realms().create(realm);
            logger.info("✅ Realm '{}' créé avec succès!", realmName);
            return true;
            
        } catch (jakarta.ws.rs.ClientErrorException e) {
            if (e.getResponse().getStatus() == 409) {
                logger.info("ℹ️ Le realm '{}' existe déjà (HTTP 409)", realmName);
                return true; // Considérer comme un succès
            }
            
            // Capturer le message d'erreur détaillé de Keycloak
            String errorBody = "N/A";
            try {
                errorBody = e.getResponse().readEntity(String.class);
            } catch (Exception ex) {
                logger.warn("Impossible de lire le corps de la réponse d'erreur");
            }
            
            logger.error("❌ Erreur lors de la création du realm '{}': HTTP {}", realmName, e.getResponse().getStatus());
            logger.error("📋 Message d'erreur Keycloak: {}", errorBody);
            logger.error("🔍 Stack trace:", e);
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
        String realmName = properties.getRealm().getName();
        
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
        String realmName = properties.getRealm().getName();
        
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
