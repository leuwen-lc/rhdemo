package fr.leuwen.keycloak;

import org.keycloak.admin.client.Keycloak;
import org.keycloak.admin.client.KeycloakBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import fr.leuwen.keycloak.service.ClientRoleService;
import fr.leuwen.keycloak.service.ClientScopeService;
import fr.leuwen.keycloak.service.ClientService;
import fr.leuwen.keycloak.service.RealmService;
import fr.leuwen.keycloak.service.UserService;

/**
 * Classe principale pour initialiser la configuration Keycloak pour RHDemo
 * 
 * Cette classe orchestre la création complète de la configuration Keycloak :
 * 1. Création du realm LeuwenRealm
 * 2. Création du client RHDemo avec sa configuration OAuth2/OIDC
 * 3. Création des client roles (admin, consult, MAJ)
 * 4. Création des utilisateurs avec leurs rôles respectifs
 * 
 * Usage:
 * java -jar rhDemoInitKeycloak-1.0.0-jar-with-dependencies.jar
 * 
 * @author Leuwen
 * @version 1.0.0
 */
public class KeycloakInitializer {
    
    private static final Logger logger = LoggerFactory.getLogger(KeycloakInitializer.class);
    
    public static void main(String[] args) {
        logger.info("╔════════════════════════════════════════════════════════════╗");
        logger.info("║  Initialisation de la configuration Keycloak pour RHDemo  ║");
        logger.info("╚════════════════════════════════════════════════════════════╝");
        logger.info("");
        
        Keycloak keycloak = null;
        
        try {
            // 1. Charger la configuration
            logger.info("📋 ÉTAPE 1: Chargement de la configuration...");
            ConfigLoader config = new ConfigLoader();
            
            // Afficher la configuration (sans les mots de passe)
            if (logger.isDebugEnabled()) {
                config.listProperties();
            }
            
            // 2. Connexion à Keycloak
            logger.info("");
            logger.info("🔌 ÉTAPE 2: Connexion au serveur Keycloak...");
            keycloak = connectToKeycloak(config);
            logger.info("✅ Client Keycloak configuré avec succès!");
            
            // 3. Création du Realm
            logger.info("");
            logger.info("🏛️ ÉTAPE 3: Création du Realm...");
            RealmService realmService = new RealmService(keycloak, config);
            if (!realmService.createRealm()) {
                logger.error("❌ Échec de la création du realm. Arrêt du processus.");
                System.exit(1);
            }
            realmService.displayRealmInfo();
            
            // 4. Création du Client
            logger.info("");
            logger.info("🔧 ÉTAPE 4: Création du Client RHDemo...");
            ClientService clientService = new ClientService(keycloak, config);
            String clientInternalId = clientService.createClient();
            if (clientInternalId == null) {
                logger.error("❌ Échec de la création du client. Arrêt du processus.");
                System.exit(1);
            }
            clientService.displayClientInfo(config.getProperty("keycloak.client.id", "RHDemo"));
            
            // 5. Création des Client Roles
            logger.info("");
            logger.info("👔 ÉTAPE 5: Création des Client Roles...");
            ClientRoleService roleService = new ClientRoleService(keycloak, config);
            if (!roleService.createClientRoles(clientInternalId)) {
                logger.error("❌ Échec de la création des client roles. Arrêt du processus.");
                System.exit(1);
            }
            roleService.listClientRoles(clientInternalId);
            
            // 6. Configuration du Client Scope "roles"
            logger.info("");
            logger.info("🎯 ÉTAPE 6: Configuration du Client Scope 'roles'...");
            ClientScopeService clientScopeService = new ClientScopeService(keycloak, config);
            if (!clientScopeService.configureRolesClientScope()) {
                logger.warn("⚠️ Échec de la configuration du client scope 'roles'. Continuons...");
            }
            clientScopeService.displayRolesClientScopeInfo();
            
            // 7. Création des Utilisateurs
            logger.info("");
            logger.info("👥 ÉTAPE 7: Création des Utilisateurs...");
            UserService userService = new UserService(keycloak, config);
            if (!userService.createAllUsers(clientInternalId)) {
                logger.error("❌ Échec de la création des utilisateurs. Arrêt du processus.");
                System.exit(1);
            }
            userService.listAllUsers();
            
            // 8. Vérification des rôles assignés
            logger.info("");
            logger.info("🔍 ÉTAPE 8: Vérification des rôles assignés...");
            userService.displayUserClientRoles("admil", clientInternalId);
            userService.displayUserClientRoles("consuela", clientInternalId);
            userService.displayUserClientRoles("madjid", clientInternalId);
            
            // 9. Récapitulatif final
            logger.info("");
            logger.info("╔════════════════════════════════════════════════════════════╗");
            logger.info("║           ✅ Configuration terminée avec succès!           ║");
            logger.info("╚════════════════════════════════════════════════════════════╝");
            logger.info("");
            logger.info("📝 Récapitulatif de la configuration créée:");
            logger.info("   ✓ Realm: {}", config.getProperty("keycloak.realm.name"));
            logger.info("   ✓ Client: {}", config.getProperty("keycloak.client.id"));
            logger.info("   ✓ Client Roles: {}", String.join(", ", config.getArrayProperty("keycloak.client.roles")));
            logger.info("   ✓ Utilisateurs créés:");
            logger.info("      - admil (role: admin)");
            logger.info("      - consuela (role: consult)");
            logger.info("      - madjid (roles: consult, MAJ)");
            logger.info("");
            logger.info("🌐 Vous pouvez maintenant vous connecter à votre application RHDemo:");
            logger.info("   URL: {}", config.getProperty("keycloak.client.rootUrl"));
            logger.info("");
            logger.info("🔐 Console d'administration Keycloak:");
            logger.info("   URL: {}/admin", config.getProperty("keycloak.server.url"));
            logger.info("");
            
        } catch (Exception e) {
            logger.error("💥 Erreur fatale lors de l'initialisation de Keycloak", e);
            System.exit(1);
        } finally {
            if (keycloak != null) {
                logger.info("🔌 Fermeture de la connexion Keycloak...");
                keycloak.close();
            }
        }
    }
    
    /**
     * Établit une connexion avec le serveur Keycloak en tant qu'admin
     * @param config Configuration chargée
     * @return Instance Keycloak connectée
     */
    private static Keycloak connectToKeycloak(ConfigLoader config) {
        String serverUrl = config.getProperty("keycloak.server.url", "http://localhost:8080");
        String adminRealm = config.getProperty("keycloak.admin.realm", "master");
        String adminUsername = config.getProperty("keycloak.admin.username", "admin");
        String adminPassword = config.getProperty("keycloak.admin.password", "admin");
        String adminClient = config.getProperty("keycloak.admin.client", "admin-cli");
        
        logger.info("   🔗 Serveur: {}", serverUrl);
        logger.info("   🏛️ Realm admin: {}", adminRealm);
        logger.info("   👤 Utilisateur admin: {}", adminUsername);
        
        // Log détaillé pour diagnostic
        logger.debug("Configuration complète:");
        logger.debug("  serverUrl: {}", serverUrl);
        logger.debug("  realm: {}", adminRealm);
        logger.debug("  clientId: {}", adminClient);
        
        try {
            // Configurer Jackson pour ignorer les propriétés inconnues (compatibilité versions)
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            mapper.configure(com.fasterxml.jackson.databind.DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
            mapper.configure(com.fasterxml.jackson.databind.DeserializationFeature.FAIL_ON_IGNORED_PROPERTIES, false);
            
            // Créer le provider JSON avec le mapper configuré
            org.jboss.resteasy.plugins.providers.jackson.ResteasyJackson2Provider jsonProvider = 
                new org.jboss.resteasy.plugins.providers.jackson.ResteasyJackson2Provider();
            jsonProvider.setMapper(mapper);
            
            // Créer le client REST avec les providers nécessaires
            org.jboss.resteasy.client.jaxrs.ResteasyClient client = (org.jboss.resteasy.client.jaxrs.ResteasyClient) 
                jakarta.ws.rs.client.ClientBuilder.newClient()
                .register(org.jboss.resteasy.plugins.providers.FormUrlEncodedProvider.class)
                .register(jsonProvider);
            
            // Créer le client Keycloak avec le RestEasy client personnalisé
            Keycloak kc = KeycloakBuilder.builder()
                    .serverUrl(serverUrl)
                    .realm(adminRealm)
                    .username(adminUsername)
                    .password(adminPassword)
                    .clientId(adminClient)
                    .resteasyClient(client)
                    .build();
            
            logger.debug("Client Keycloak créé avec serverUrl: {}", serverUrl);
            return kc;
        } catch (Exception e) {
            logger.error("❌ Impossible de se connecter à Keycloak. Vérifiez que:");
            logger.error("   - Keycloak est démarré sur {}", serverUrl);
            logger.error("   - Les credentials admin sont corrects");
            logger.error("   - Le realm '{}' existe", adminRealm);
            throw new RuntimeException("Échec de connexion à Keycloak", e);
        }
    }
}
