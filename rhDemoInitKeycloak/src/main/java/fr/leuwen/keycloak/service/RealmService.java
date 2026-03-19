package fr.leuwen.keycloak.service;

import org.keycloak.admin.client.Keycloak;
import org.keycloak.representations.idm.RealmRepresentation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

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
            
            // STRATÉGIE: Créer un realm MINIMAL d'abord, puis le configurer après création
            // L'erreur "unable to read contents from stream" indique un problème de sérialisation JSON
            // Probablement des champs avec valeurs par défaut incompatibles
            
            logger.info("🔧 Tentative 1: Création realm MINIMAL (seulement nom + enabled)...");
            RealmRepresentation realm = new RealmRepresentation();
            realm.setRealm(realmName);
            realm.setEnabled(true);
            
            logger.debug("═══════════════════════════════════════════════════════════");
            logger.debug("🔍 DEBUG: RealmRepresentation MINIMAL à envoyer:");
            logger.debug("   - realm: {}", realm.getRealm());
            logger.debug("   - enabled: {}", realm.isEnabled());
            logger.debug("═══════════════════════════════════════════════════════════");
            
            // Créer le realm via l'API (version minimale)
            keycloak.realms().create(realm);
            logger.info("✅ Realm '{}' créé avec succès (version minimale)!", realmName);
            
            // Maintenant, mettre à jour avec la configuration complète
            logger.info("🔧 Configuration du realm avec les paramètres souhaités...");
            try {
                RealmRepresentation realmToUpdate = keycloak.realm(realmName).toRepresentation();
                
                // Appliquer la configuration souhaitée
                realmToUpdate.setDisplayName(properties.getRealm().getDisplayName());
                realmToUpdate.setRegistrationAllowed(properties.getRealm().isRegistrationAllowed());
                realmToUpdate.setRegistrationEmailAsUsername(properties.getRealm().isRegistrationEmailAsUsername());
                realmToUpdate.setResetPasswordAllowed(properties.getRealm().isResetPasswordAllowed());
                realmToUpdate.setEditUsernameAllowed(properties.getRealm().isEditUsernameAllowed());
                realmToUpdate.setLoginWithEmailAllowed(properties.getRealm().isLoginWithEmailAllowed());
                realmToUpdate.setDuplicateEmailsAllowed(properties.getRealm().isDuplicateEmailsAllowed());
                realmToUpdate.setSsoSessionIdleTimeout(properties.getRealm().getSsoSessionIdleTimeout());
                realmToUpdate.setSsoSessionMaxLifespan(properties.getRealm().getSsoSessionMaxLifespan());
                realmToUpdate.setAccessTokenLifespan(properties.getRealm().getAccessTokenLifespan());

                // Configuration des headers de sécurité du navigateur (browserSecurityHeaders)
                // Objectif : expliciter toutes les directives CSP pour éviter les alertes ZAP/OWASP
                // "Failure to Define Directive with No Fallback" et "Wildcard Directive".
                //
                // Limites connues (thème Keycloak 26 par défaut) :
                // - 'unsafe-inline' et 'unsafe-eval' sur script-src sont imposés par les templates
                //   du thème Keycloak (scripts inline dans les pages de login).
                //   Supprimables uniquement avec un thème custom (hors scope de ce projet).
                // - L'absence de token CSRF classique détectée par ZAP est un faux positif :
                //   la protection est assurée par le paramètre 'state' OAuth2.
                // Partir des headers existants (défauts Keycloak) pour ne pas écraser
                // xContentTypeOptions, xFrameOptions, strictTransportSecurity, etc.
                Map<String, String> browserSecurityHeaders = realmToUpdate.getBrowserSecurityHeaders();
                if (browserSecurityHeaders == null) {
                    browserSecurityHeaders = new HashMap<>();
                }
                browserSecurityHeaders.put("contentSecurityPolicy",
                        "default-src 'self'; " +
                        "script-src 'self' 'unsafe-eval' 'unsafe-inline'; " +
                        "style-src 'self' 'unsafe-inline'; " +
                        "img-src 'self' data:; " +
                        "font-src 'self' data:; " +
                        "connect-src 'self'; " +
                        "frame-src 'self'; " +
                        "frame-ancestors 'self'; " +
                        "object-src 'none'; " +
                        "base-uri 'self'; " +
                        "form-action 'self'");
                browserSecurityHeaders.put("referrerPolicy", "no-referrer");
                realmToUpdate.setBrowserSecurityHeaders(browserSecurityHeaders);

                // Mettre à jour le realm
                keycloak.realm(realmName).update(realmToUpdate);
                logger.info("✅ Configuration du realm '{}' appliquée avec succès!", realmName);
                
            } catch (Exception e) {
                logger.warn("⚠️  Realm créé mais échec de la configuration avancée: {}", e.getMessage());
                logger.info("   Le realm existe mais avec configuration par défaut");
            }
            
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
