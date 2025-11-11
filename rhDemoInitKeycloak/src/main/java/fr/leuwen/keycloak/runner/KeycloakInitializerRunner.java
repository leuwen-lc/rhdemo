package fr.leuwen.keycloak.runner;

import org.keycloak.admin.client.Keycloak;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import fr.leuwen.keycloak.config.KeycloakProperties;
import fr.leuwen.keycloak.service.ClientRoleService;
import fr.leuwen.keycloak.service.ClientService;
import fr.leuwen.keycloak.service.RealmService;
import fr.leuwen.keycloak.service.UserService;

/**
 * Runner qui exécute l'initialisation de Keycloak au démarrage de l'application
 */
@Component
public class KeycloakInitializerRunner implements CommandLineRunner {

    private static final Logger logger = LoggerFactory.getLogger(KeycloakInitializerRunner.class);
    
    private final KeycloakProperties properties;
    private final Keycloak keycloak;

    public KeycloakInitializerRunner(KeycloakProperties properties, Keycloak keycloak) {
        this.properties = properties;
        this.keycloak = keycloak;
    }

    @Override
    public void run(String... args) throws Exception {
        logger.info("╔════════════════════════════════════════════════════════════╗");
        logger.info("║  Initialisation de la configuration Keycloak pour RHDemo  ║");
        logger.info("╚════════════════════════════════════════════════════════════╝");
        logger.info("");
        logger.info("✅ Client Keycloak configuré avec succès!");

        try {
            // 2. Création du Realm
            logger.info("");
            logger.info("🏛️ ÉTAPE 2: Création du Realm...");
            RealmService realmService = new RealmService(keycloak, properties);
            if (!realmService.createRealm()) {
                logger.error("❌ Échec de la création du realm. Arrêt du processus.");
                System.exit(1);
            }
            realmService.displayRealmInfo();

            // 3. Création du Client
            logger.info("");
            logger.info("🔧 ÉTAPE 3: Création du Client RHDemo...");
            ClientService clientService = new ClientService(keycloak, properties);
            String clientInternalId = clientService.createClient();
            if (clientInternalId == null) {
                logger.error("❌ Échec de la création du client. Arrêt du processus.");
                System.exit(1);
            }
            clientService.displayClientInfo(properties.getClient().getClientId());

            // 4. Création des Client Roles
            logger.info("");
            logger.info("👔 ÉTAPE 4: Création des Client Roles...");
            ClientRoleService roleService = new ClientRoleService(keycloak, properties);
            if (!roleService.createClientRoles(clientInternalId)) {
                logger.error("❌ Échec de la création des client roles. Arrêt du processus.");
                System.exit(1);
            }
            roleService.listClientRoles(clientInternalId);

            // 5. Création des Utilisateurs
            logger.info("");
            logger.info("👥 ÉTAPE 5: Création des Utilisateurs...");
            UserService userService = new UserService(keycloak, properties);
            if (!userService.createAllUsers(clientInternalId)) {
                logger.error("❌ Échec de la création des utilisateurs. Arrêt du processus.");
                System.exit(1);
            }
            userService.listAllUsers();

            // 6. Récapitulatif final
            logger.info("");
            logger.info("╔════════════════════════════════════════════════════════════╗");
            logger.info("║           ✅ Configuration terminée avec succès!           ║");
            logger.info("╚════════════════════════════════════════════════════════════╝");
            logger.info("");
            logger.info("📝 Récapitulatif de la configuration créée:");
            logger.info("   ✓ Realm: {}", properties.getRealm().getName());
            logger.info("   ✓ Client: {}", properties.getClient().getClientId());
            logger.info("   ✓ Client Roles: {}", String.join(", ", properties.getClient().getRoles()));
            logger.info("   ✓ Utilisateurs créés: {}", properties.getUsers().size());
            logger.info("");
            logger.info("🌐 Vous pouvez maintenant vous connecter à votre application RHDemo:");
            logger.info("   URL: {}", properties.getClient().getBaseUrl());
            logger.info("");
            logger.info("🔐 Console d'administration Keycloak:");
            logger.info("   URL: {}/admin", properties.getServerUrl());
            logger.info("");

        } catch (Exception e) {
            logger.error("💥 Erreur fatale lors de l'initialisation de Keycloak", e);
            System.exit(1);
        } finally {
            logger.info("🔌 Fermeture de la connexion Keycloak...");
            keycloak.close();
        }
    }
}
