# 🔐 RH Demo - Keycloak Initialization Tool

Outil d'initialisation automatique de la configuration Keycloak pour l'application RHDemo.

Ce projet Java autonome utilise l'API Admin REST de Keycloak pour créer automatiquement tous les éléments de configuration nécessaires au fonctionnement de l'application RHDemo.

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Prérequis](#prérequis)
- [Configuration](#configuration)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Détails de la configuration créée](#détails-de-la-configuration-créée)
- [Dépannage](#dépannage)
- [Structure du projet](#structure-du-projet)

---

## 🎯 Vue d'ensemble

Cet outil non destiné à la production automatise la configuration minimale de Keycloak pour test de RHDemo en exécutant les étapes suivantes :

1. **Création du Realm** : `LeuwenRealm`
2. **Création du Client OAuth2/OIDC** : `RHDemo` avec toute sa configuration
3. **Création des Client Roles** : `admin`, `consult`, `MAJ`
4. **Création des utilisateurs** :
   - `admil` avec le role `admin`
   - `consuela` avec le role `consult`
   - `madjid` avec les roles `consult` et `MAJ`

Une configuration de Keycloak pour la prod devrait être largement complétée et renforcée. Probablement qu'on fera appel à un Keycloak mutualisé potentiellement déjà existant pour la production.

Cet outil manipule des secrets et crée des utilisateurs fictifs dans l'unique but de test de l'application RHDemo

---

## ✅ Prérequis

### 1. Keycloak en cours d'exécution

- **Keycloak 23.0+** installé et démarré
- Accessible sur `http://localhost:8080` (ou modifier la configuration)
- Console d'administration accessible

### 2. Compte administrateur Keycloak

- Avoir un compte admin du realm `master`
- Par défaut : username `admin`, password `admin`
- Si vos credentials sont différents, les modifier dans `application.properties`

### 3. Java et Maven

- **Java 21** installé
- **Maven 3.6+** installé

---

## ⚙️ Configuration

Le fichier `src/main/resources/application.properties` contient toute la configuration.

### Configuration Keycloak Server

```properties
# URL du serveur Keycloak
keycloak.server.url=http://localhost:8080

# Credentials de l'administrateur (realm master)
keycloak.admin.realm=master
keycloak.admin.username=admin
keycloak.admin.password=admin
keycloak.admin.client=admin-cli
```

### Configuration du Realm

```properties
# Nom du realm à créer
keycloak.realm.name=LeuwenRealm
keycloak.realm.displayName=Leuwen Realm
keycloak.realm.enabled=true
```

### Configuration du Client RHDemo

```properties
# Identifiants du client
keycloak.client.id=RHDemo
keycloak.client.secret=lmax7TDMmHk5g7ZgCCXK9ILpjHHvHYga

# URLs de l'application
keycloak.client.rootUrl=http://localhost:9000/
keycloak.client.redirectUris=http://localhost:9000/*
keycloak.client.webOrigins=http://localhost:9000/*
```

### Configuration des Client Roles

```properties
# Roles séparés par des virgules
keycloak.client.roles=admin,consult,MAJ
```

### Configuration des Utilisateurs

```properties
# Utilisateur 1 : admil
keycloak.users.admil.username=admil
keycloak.users.admil.password=admil123
keycloak.users.admil.email=admil@leuwen.fr
keycloak.users.admil.firstname=Admin
keycloak.users.admil.lastname=Admil
keycloak.users.admil.roles=admin

# Utilisateur 2 : consuela
keycloak.users.consuela.username=consuela
keycloak.users.consuela.password=consuela123
keycloak.users.consuela.email=consuela@leuwen.fr
keycloak.users.consuela.firstname=Consuela
keycloak.users.consuela.lastname=Consulte
keycloak.users.consuela.roles=consult

# Utilisateur 3 : madjid
keycloak.users.madjid.username=madjid
keycloak.users.madjid.password=madjid123
keycloak.users.madjid.email=madjid@leuwen.fr
keycloak.users.madjid.firstname=Madjid
keycloak.users.madjid.lastname=Majeur
keycloak.users.madjid.roles=consult,MAJ
```

⚠️ **Important** : Changez les mots de passe dans un environnement de production !

---

## 🔨 Installation

### 1. Cloner ou télécharger le projet

```bash
cd /home/leno-vo/git/repository/rhDemoInitKeycloak
```

### 2. Compiler le projet

```bash
mvn clean package
```

Cette commande va :
- Compiler les sources Java
- Télécharger toutes les dépendances nécessaires
- Créer un JAR exécutable avec toutes les dépendances : `target/rhDemoInitKeycloak-1.0.0-jar-with-dependencies.jar`

---

## 🚀 Utilisation

### Méthode 1 : Exécution avec Maven

```bash
mvn exec:java -Dexec.mainClass="fr.leuwen.keycloak.KeycloakInitializer"
```

### Méthode 2 : Exécution du JAR

```bash
java -jar target/rhDemoInitKeycloak-1.0.0-jar-with-dependencies.jar
```

### Sortie attendue

```
╔════════════════════════════════════════════════════════════╗
║  Initialisation de la configuration Keycloak pour RHDemo  ║
╚════════════════════════════════════════════════════════════╝

📋 ÉTAPE 1: Chargement de la configuration...
✅ Configuration chargée

🔌 ÉTAPE 2: Connexion au serveur Keycloak...
   🔗 Serveur: http://localhost:8080
   🏛️ Realm admin: master
   👤 Utilisateur admin: admin
✅ Connexion établie avec succès!

🏛️ ÉTAPE 3: Création du Realm...
➡️ Le realm 'LeuwenRealm' n'existe pas, création en cours...
✅ Realm 'LeuwenRealm' créé avec succès!

🔧 ÉTAPE 4: Création du Client RHDemo...
➡️ Le client 'RHDemo' n'existe pas, création en cours...
✅ Client 'RHDemo' créé avec succès!

👔 ÉTAPE 5: Création des Client Roles...
🔧 Création de 3 client roles...
➡️ Le role 'admin' n'existe pas, création en cours...
✅ Role 'admin' créé avec succès!
➡️ Le role 'consult' n'existe pas, création en cours...
✅ Role 'consult' créé avec succès!
➡️ Le role 'MAJ' n'existe pas, création en cours...
✅ Role 'MAJ' créé avec succès!

👥 ÉTAPE 6: Création des Utilisateurs...
➡️ L'utilisateur 'admil' n'existe pas, création en cours...
✅ Utilisateur 'admil' créé avec succès!
➡️ Assignation du role 'admin' à l'utilisateur
✅ 1 role(s) assigné(s) avec succès
[... suite pour consuela et madjid ...]

╔════════════════════════════════════════════════════════════╗
║           ✅ Configuration terminée avec succès!           ║
╚════════════════════════════════════════════════════════════╝

📝 Récapitulatif de la configuration créée:
   ✓ Realm: LeuwenRealm
   ✓ Client: RHDemo
   ✓ Client Roles: admin, consult, MAJ
   ✓ Utilisateurs créés:
      - admil (role: admin)
      - consuela (role: consult)
      - madjid (roles: consult, MAJ)
```

---

## 📦 Détails de la configuration créée

### Realm : LeuwenRealm

- **Display Name** : Leuwen Realm
- **Enabled** : true
- **Registration** : Désactivée (pour la sécurité)
- **Login with Email** : Activé
- **SSO Session Idle Timeout** : 30 minutes
- **Access Token Lifespan** : 5 minutes

### Client : RHDemo

- **Client ID** : RHDemo
- **Client Secret** : `lmax7TDMmHk5g7ZgCCXK9ILpjHHvHYga`
- **Protocol** : OpenID Connect
- **Access Type** : Confidential
- **Standard Flow** : Enabled
- **Direct Access Grants** : Enabled
- **Root URL** : `http://localhost:9000/`
- **Valid Redirect URIs** : `http://localhost:9000/*`
- **Web Origins** : `http://localhost:9000/*`

#### Protocol Mapper

Un mapper personnalisé est configuré pour inclure les client roles dans le token JWT :

```json
{
  "name": "client roles",
  "protocolMapper": "oidc-usermodel-client-role-mapper",
  "claim.name": "resource_access.${client_id}.roles",
  "access.token.claim": "true",
  "multivalued": "true"
}
```

Cela permet à Spring Security de lire les rôles depuis `resource_access.RHDemo.roles` dans le JWT.

### Client Roles

| Role | Description |
|------|-------------|
| **admin** | Administration complète de l'application |
| **consult** | Consultation des données (lecture seule) |
| **MAJ** | Mise à jour des données (écriture) |

### Utilisateurs

| Username | Password | Email | Prénom | Nom | Roles |
|----------|----------|-------|---------|-----|-------|
| **admil** | admil123 | admil@leuwen.fr | Admin | Admil | admin |
| **consuela** | consuela123 | consuela@leuwen.fr | Consuela | Consulte | consult |
| **madjid** | madjid123 | madjid@leuwen.fr | Madjid | Majeur | consult, MAJ |

---

## 🔧 Dépannage

### Erreur : "Cannot connect to Keycloak"

**Causes possibles :**
- Keycloak n'est pas démarré
- L'URL du serveur est incorrecte dans `application.properties`
- Problème de réseau/firewall

**Solution :**
```bash
# Vérifier que Keycloak est accessible
curl http://localhost:8080

# Démarrer Keycloak si nécessaire
# (dépend de votre installation)
```

### Erreur : "401 Unauthorized"

**Cause :** Credentials administrateur incorrects

**Solution :**
Vérifiez les credentials dans `application.properties` :
```properties
keycloak.admin.username=admin
keycloak.admin.password=admin
```

### Erreur : "Realm already exists"

**Cause :** Le realm `LeuwenRealm` existe déjà

**Solution :** L'outil détecte automatiquement les éléments existants et ne les recrée pas. C'est un comportement normal.

Si vous voulez tout réinitialiser :
1. Supprimer manuellement le realm dans la console Keycloak
2. Relancer l'outil

### Erreur de compilation : "Package does not match expected package"

**Cause :** Erreur d'affichage de l'IDE, pas un vrai problème

**Solution :** Lancer Maven depuis le terminal :
```bash
mvn clean package
```

### Les utilisateurs ne peuvent pas se connecter

**Causes possibles :**
- Le client secret ne correspond pas entre Keycloak et l'application RHDemo
- Les redirect URIs ne sont pas correctes

**Solution :**
1. Vérifier le client secret dans `application.properties` de RHDemo :
```properties
RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET=lmax7TDMmHk5g7ZgCCXK9ILpjHHvHYga
```

2. Vérifier les redirect URIs dans Keycloak :
   - Aller dans la console admin Keycloak
   - Realm LeuwenRealm → Clients → RHDemo
   - Vérifier que `http://localhost:9000/*` est dans les Valid Redirect URIs

---

## 📁 Structure du projet

```
rhDemoInitKeycloak/
├── pom.xml                                    # Configuration Maven
├── README.md                                  # Cette documentation
└── src/
    └── main/
        ├── java/fr/leuwen/keycloak/
        │   ├── KeycloakInitializer.java       # Classe principale (main)
        │   ├── ConfigLoader.java              # Chargeur de configuration
        │   └── service/
        │       ├── RealmService.java          # Service de création du realm
        │       ├── ClientService.java         # Service de création du client
        │       ├── ClientRoleService.java     # Service de gestion des roles
        │       └── UserService.java           # Service de gestion des users
        └── resources/
            └── application.properties         # Configuration de l'application
```

---

## 🔄 Utilisation répétée

L'outil est **idempotent** : il peut être exécuté plusieurs fois sans problème.

- Si un élément existe déjà (realm, client, role, user), il sera détecté et **non recréé**
- Seuls les éléments manquants seront créés
- Aucun doublon ne sera créé

Cela permet de :
- Réinitialiser une configuration partielle
- Ajouter des éléments manquants
- Vérifier l'état de la configuration

---

## 📚 Ressources complémentaires

- **Documentation Keycloak Admin REST API** : [https://www.keycloak.org/docs-api/latest/rest-api/](https://www.keycloak.org/docs-api/latest/rest-api/)
- **Keycloak Admin Client Java** : [https://www.keycloak.org/docs/latest/server_development/#admin-rest-api](https://www.keycloak.org/docs/latest/server_development/#admin-rest-api)
- **Documentation Spring Security OAuth2** : [https://docs.spring.io/spring-security/reference/servlet/oauth2/index.html](https://docs.spring.io/spring-security/reference/servlet/oauth2/index.html)

---

## 📝 Notes importantes

### Sécurité

⚠️ **Dans un environnement de production :**

1. **Changez tous les mots de passe** dans `application.properties`
2. **Protégez le fichier `application.properties`** (ne jamais le commiter dans Git avec les vrais credentials)
3. **Utilisez des secrets management tools** (Vault, AWS Secrets Manager, etc.)
4. **Activez HTTPS** sur Keycloak et l'application RHDemo
5. **Restreignez les Web Origins** aux domaines autorisés uniquement

### Personnalisation

Pour adapter cet outil à d'autres projets :

1. Modifier `application.properties` avec vos valeurs
2. Ajouter/retirer des utilisateurs dans la configuration
3. Modifier les rôles selon vos besoins
4. Adapter les URLs selon votre environnement

---

## 👨‍💻 Auteur

**Leuwen**

---

## 📄 Licence

Ce projet est créé pour l'application RHDemo.

---

## ✅ Checklist de déploiement

Avant d'utiliser cet outil en production :

- [ ] Keycloak est installé et démarré
- [ ] Les credentials admin sont corrects dans `application.properties`
- [ ] Les mots de passe des utilisateurs ont été changés
- [ ] Le client secret correspond entre Keycloak et l'application RHDemo
- [ ] Les URLs (rootUrl, redirectUris, webOrigins) sont correctes pour votre environnement
- [ ] HTTPS est activé (recommandé en production)
- [ ] Le fichier `application.properties` est protégé et non versionné avec Git

---

**🎉 Bonne utilisation !**
