# Configuration des Environnements - Variables par Contexte

Ce document liste toutes les variables de configuration qui diffèrent entre les environnements **local** et **staging**, ainsi que leurs emplacements de configuration.

---

## 📋 Vue d'ensemble

| Environnement       | Description                    | Réseau                 | Accès                        |
|:--------------------|:-------------------------------|:-----------------------|:-----------------------------|
| **Local**           | Développement sur poste local  | localhost              | Direct via ports exposés     |
| **Staging**         | Tests CI/CD dans Jenkins       | Docker réseau interne  | Via noms de services Docker  |

---

## 🔐 Variables Keycloak

### URLs d'accès Keycloak

| Variable                     | Local                                                                           | Staging                                                                                | Fichier de configuration                     |
|:-----------------------------|:--------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------|:---------------------------------------------|
| **Server URL (backend)**     | `http://localhost:6090`                                                         | `http://keycloak-staging:8080`                                                         | `application.yml` / `application-staging.yml` |
| **Authorization URI**        | `http://localhost:6090/realms/RHDemo/protocol/openid-connect/auth`             | `http://keycloak-staging:8080/realms/RHDemo/protocol/openid-connect/auth`             | `application.yml` / `application-staging.yml` |
| **Token URI**                | `http://localhost:6090/realms/RHDemo/protocol/openid-connect/token`            | `http://keycloak-staging:8080/realms/RHDemo/protocol/openid-connect/token`            | `application.yml` / `application-staging.yml` |
| **JWK Set URI**              | `http://localhost:6090/realms/RHDemo/protocol/openid-connect/certs`            | `http://keycloak-staging:8080/realms/RHDemo/protocol/openid-connect/certs`            | `application.yml` / `application-staging.yml` |

**Emplacements** :
- Local : `rhDemo/src/main/resources/application.yml`
- Staging : `rhDemo/src/main/resources/application-staging.yml`

### Secrets Keycloak

| Variable                     | Description                            | Fichier de configuration                                                     |
|:-----------------------------|:---------------------------------------|:-----------------------------------------------------------------------------|
| **Client Secret**            | Secret du client OAuth2 RHDemo         | Variable d'environnement ou `application.yml` (valeur par défaut locale)    |
| **Admin Username**           | Utilisateur admin Keycloak             | `secrets/secrets-dev.yml` / `secrets/secrets-staging.yml`                    |
| **Admin Password**           | Mot de passe admin Keycloak            | `secrets/secrets-dev.yml` / `secrets/secrets-staging.yml`                    |
| **Database Password**        | Mot de passe de la base Keycloak       | `secrets/secrets-dev.yml` / `secrets/secrets-staging.yml`                    |

**Emplacements** :
- Secrets locaux : `rhDemo/secrets/secrets-dev.yml` (chiffré avec SOPS)
- Secrets staging : `rhDemo/secrets/secrets-staging.yml` (chiffré avec SOPS)
- Variable d'env : 
  - Local : `SPRING_SECURITY_OAUTH2_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET`
  - Staging : Variable Docker Compose

### Configuration Keycloak (Initialisation)

| Variable                     | Description                            | Fichier de configuration                                                     |
|:-----------------------------|:---------------------------------------|:-----------------------------------------------------------------------------|
| **Keycloak Admin Realm**     | Realm d'administration                 | `rhDemoInitKeycloak/src/main/resources/application.yml`                      |
| **Target Realm Name**        | Nom du realm applicatif                | `rhDemoInitKeycloak/src/main/resources/application.yml`                      |
| **Client Root URL**          | URL racine du client OAuth2            | `rhDemoInitKeycloak/src/main/resources/application.yml`                      |
| **Redirect URIs**            | URLs de redirection autorisées         | `rhDemoInitKeycloak/src/main/resources/application.yml`                      |

**Emplacements** :
- Configuration générique : `rhDemoInitKeycloak/src/main/resources/application.yml`
- Profil staging : `rhDemoInitKeycloak/src/main/resources/application-staging.yml` (généré par Jenkins)

---

## 🗄️ Variables Base de Données

### URLs de connexion PostgreSQL

| Variable                     | Local                                       | Staging                                      | Fichier de configuration                                      |
|:-----------------------------|:--------------------------------------------|:---------------------------------------------|:--------------------------------------------------------------|
| **JDBC URL**                 | `jdbc:postgresql://localhost:5433/rhdemo`   | `jdbc:postgresql://rhdemo-db:5432/rhdemo`    | Variable d'environnement Docker                               |
| **Database Name**            | `rhdemo`                                    | `rhdemo`                                     | Variable d'environnement Docker                               |
| **Username**                 | `rhdemo`                                    | `rhdemo`                                     | Variable d'environnement Docker                               |
| **Password**                 | (secret dev)                                | (secret staging)                             | `secrets/secrets-dev.yml` / `secrets/secrets-staging.yml`     |

**Emplacements** :
- Local : `docker-compose.yml` (racine du projet)
- Staging : `rhDemo/infra/staging/docker-compose.yml`
- Secrets : `rhDemo/secrets/secrets-dev.yml` ou `secrets-staging.yml`

### Base de données Keycloak

| Variable                     | Local                                       | Staging                                      | Fichier de configuration                                      |
|:-----------------------------|:--------------------------------------------|:---------------------------------------------|:--------------------------------------------------------------|
| **Database Host**            | `localhost:5434`                            | `keycloak-db:5432`                           | `docker-compose.yml`                                          |
| **Database Name**            | `keycloak`                                  | `keycloak`                                   | Variable d'environnement Docker                               |
| **Username**                 | `keycloak`                                  | `keycloak`                                   | Variable d'environnement Docker                               |
| **Password**                 | (secret dev)                                | (secret staging)                             | `secrets/secrets-dev.yml` / `secrets/secrets-staging.yml`     |

**Emplacements** :
- Local : `docker-compose.yml` (racine du projet)
- Staging : `rhDemo/infra/staging/docker-compose.yml`

---

## 🌐 Variables Application RHDemo

### Ports d'écoute

| Variable                     | Local                                       | Staging                                      | Fichier de configuration                                      |
|:-----------------------------|:--------------------------------------------|:---------------------------------------------|:--------------------------------------------------------------|
| **Server Port**              | `9000`                                      | `9000`                                       | `application.yml`                                             |
| **Public Access**            | `http://localhost:9000`                     | Via Docker network (pas d'exposition)        | -                                                             |

### Profils Spring Boot

| Variable                     | Local                                       | Staging                                      | Activation                                                    |
|:-----------------------------|:--------------------------------------------|:---------------------------------------------|:--------------------------------------------------------------|
| **Active Profile**           | (par défaut)                                | `staging`                                    | Variable `SPRING_PROFILES_ACTIVE`                             |

**Emplacements** :
- Local : Aucune variable nécessaire (profil par défaut)
- Staging : `rhDemo/infra/staging/docker-compose.yml` → `SPRING_PROFILES_ACTIVE: staging`

---

## 🧪 Variables Tests Selenium

### URLs de test

| Variable                     | Local                                       | Staging                                      | Fichier de configuration                                      |
|:-----------------------------|:--------------------------------------------|:---------------------------------------------|:--------------------------------------------------------------|
| **Base URL Application**     | `http://localhost:9000`                     | `http://rhdemo-staging-app:9000`             | Paramètre Maven `-Dtest.baseurl`                              |
| **Keycloak URL**             | `http://localhost:6090`                     | `http://keycloak-staging:8080`               | Paramètre Maven `-Dtest.keycloak.url`                         |

**Emplacements** :
- Local : `rhDemoAPITestIHM/src/test/resources/test.properties`
- Staging : Ligne de commande Maven dans `Jenkinsfile`

### Utilisateurs de test

| Variable                     | Description                                 | Fichier de configuration                                      |
|:-----------------------------|:--------------------------------------------|:--------------------------------------------------------------|
| **Admin User**               | Utilisateur avec rôle admin                 | Paramètre Maven `-Dtest.admin.user`                           |
| **Admin Password**           | Mot de passe admin                          | Paramètre Maven `-Dtest.admin.password`                       |
| **Consult User**             | Utilisateur avec rôle consult               | Paramètre Maven `-Dtest.consult.user`                         |
| **Consult Password**         | Mot de passe consultant                     | Paramètre Maven `-Dtest.consult.password`                     |
| **Manager User**             | Utilisateur avec rôles consult + MAJ        | Paramètre Maven `-Dtest.manager.user`                         |
| **Manager Password**         | Mot de passe manager                        | Paramètre Maven `-Dtest.manager.password`                     |

**Emplacements** :
- Local : `rhDemoAPITestIHM/src/test/resources/test.properties`
- Staging : Ligne de commande Maven dans `Jenkinsfile`

### Mode d'exécution

| Variable                     | Local                                       | Staging                                      | Fichier de configuration                                      |
|:-----------------------------|:--------------------------------------------|:---------------------------------------------|:--------------------------------------------------------------|
| **Headless Mode**            | `false` (avec interface)                    | `true` (sans interface)                      | Paramètre Maven `-Dselenium.headless`                         |

**Emplacements** :
- Staging : `Jenkinsfile` → `-Dselenium.headless=true`

---

## 🐳 Variables Docker & CI/CD

### Noms de conteneurs et réseaux

| Variable                     | Local                                       | Staging                                      | Fichier de configuration                                      |
|:-----------------------------|:--------------------------------------------|:---------------------------------------------|:--------------------------------------------------------------|
| **Project Name**             | `rhdemo` (ou défaut Docker)                 | `rhdemo-staging-${BUILD_NUMBER}`             | `docker-compose -p`                                           |
| **Network Name**             | `rhdemo_default`                            | `rhdemo-staging-network`                     | `docker-compose.yml` → `networks:`                            |
| **Container Names**          | `rhdemo-app`, `rhdemo-db`, etc.             | `rhdemo-staging-app`, `rhdemo-staging-db`    | `docker-compose.yml` → `container_name:`                      |

**Emplacements** :
- Local : `docker-compose.yml` (racine)
- Staging : `rhDemo/infra/staging/docker-compose.yml` + `Jenkinsfile` (variables)

### Images Docker

| Variable                     | Local                                       | Staging                                      | Fichier de configuration                                      |
|:-----------------------------|:--------------------------------------------|:---------------------------------------------|:--------------------------------------------------------------|
| **Application Image**        | `rhdemo-api:latest` (ou version)            | `rhdemo-api:build-${BUILD_NUMBER}`           | `Jenkinsfile` (build) + `docker-compose.yml` (run)           |
| **Image Tag**                | Manuel ou snapshot                          | `build-${BUILD_NUMBER}`                      | `Jenkinsfile` → `DOCKER_IMAGE_TAG`                            |

**Emplacements** :
- Build : `rhDemo/Jenkinsfile` → `DOCKER_IMAGE_NAME` et `DOCKER_IMAGE_TAG`
- Run : `rhDemo/infra/staging/docker-compose.yml` → `image: rhdemo-api:${APP_VERSION}`

---

## 🔧 Variables Jenkins (Staging uniquement)

| Variable                     | Description                                 | Fichier de configuration                                      |
|:-----------------------------|:--------------------------------------------|:--------------------------------------------------------------|
| **BUILD_NUMBER**             | Numéro de build Jenkins                     | Variable Jenkins automatique                                  |
| **WORKSPACE**                | Répertoire de travail Jenkins               | Variable Jenkins automatique                                  |
| **SECRETS_FILE**             | Fichier secrets à déchiffrer                | `Jenkinsfile` → `SECRETS_FILE`                                |
| **COMPOSE_PROJECT_NAME**     | Nom du projet Docker Compose                | `Jenkinsfile` → `COMPOSE_PROJECT_NAME`                        |
| **STAGING_INFRA_PATH**       | Chemin vers infra staging                   | `Jenkinsfile` → `STAGING_INFRA_PATH`                          |

**Emplacements** :
- `rhDemo/Jenkinsfile` (section `environment`)

---

## 📂 Récapitulatif des fichiers de configuration

### Fichiers Spring Boot (Application RHDemo)

```
rhDemo/
├── src/main/resources/
│   ├── application.yml              # Configuration LOCAL par défaut
│   └── application-staging.yml      # Configuration STAGING (override)
```

**Principe** : `application-staging.yml` surcharge `application.yml` quand le profil `staging` est actif.

### Fichiers Keycloak Initialization

```
rhDemoInitKeycloak/
└── src/main/resources/
    ├── application.yml              # Configuration locale Keycloak
    └── application-staging.yml      # Généré dynamiquement par Jenkins
```

**Note** : Le fichier staging est généré par le script `generate-keycloak-config.sh` dans Jenkins.

### Fichiers Secrets (chiffrés SOPS)

```
rhDemo/
└── secrets/
    ├── secrets-dev.yml              # Secrets LOCAL (chiffré)
    ├── secrets-staging.yml          # Secrets STAGING (chiffré)
    └── secrets.yml.template         # Template pour référence
```

**Déchiffrement** :
- Local : Manuel via `sops -d secrets/secrets-dev.yml`
- Staging : Automatique via Jenkins + script `rhDemo/secrets/env-vars.sh`

### Fichiers Docker Compose

```
# LOCAL
rhDemo/
└── docker-compose.yml               # Services locaux (Keycloak + PostgreSQL)

# STAGING
rhDemo/
└── infra/staging/
    └── docker-compose.yml           # Services staging complets (app + Keycloak + DB + nginx)
```

### Fichiers Tests Selenium

```
rhDemoAPITestIHM/
└── src/test/resources/
    └── test.properties              # Configuration locale des tests
```

**Note** : En staging, les propriétés sont surchargées par paramètres Maven (`-D`) dans le Jenkinsfile.

---

## 🔄 Workflow de changement de configuration

### Pour modifier une URL Keycloak

1. **Local** : Modifier `rhDemo/src/main/resources/application.yml`
2. **Staging** : Modifier `rhDemo/src/main/resources/application-staging.yml`
3. Rebuild l'image Docker si nécessaire

### Pour modifier un secret

1. **Local** : 
   ```bash
   sops rhDemo/secrets/secrets-dev.yml
   # Modifier puis sauvegarder (chiffrement automatique)
   ```

2. **Staging** :
   ```bash
   sops rhDemo/secrets/secrets-staging.yml
   # Modifier puis sauvegarder
   git add secrets/secrets-staging.yml
   git commit -m "chore: Mise à jour secrets staging"
   git push
   ```

### Pour modifier une configuration Docker

1. **Local** : Modifier `docker-compose.yml` (racine)
2. **Staging** : Modifier `rhDemo/infra/staging/docker-compose.yml`

### Pour modifier les tests Selenium

1. **Configuration locale** : Modifier `rhDemoAPITestIHM/src/test/resources/test.properties`
2. **Configuration staging** : Modifier les paramètres Maven dans `rhDemo/Jenkinsfile` (section tests Selenium)

---

## ⚠️ Points d'attention

### Noms de services Docker vs Localhost

- **Local** : Utiliser `localhost` avec ports exposés (6090, 5433, etc.)
- **Staging** : Utiliser noms de services Docker (`keycloak-staging`, `rhdemo-db`, etc.)

### Profils Spring Boot

- Le profil `staging` **doit être activé** via `SPRING_PROFILES_ACTIVE=staging` dans docker-compose staging
- Sans profil, c'est `application.yml` (local) qui est utilisé

### Secrets jamais en clair

- ❌ Ne jamais commiter de secrets en clair dans Git
- ✅ Toujours utiliser SOPS pour chiffrer (`sops -e`)
- ✅ Les valeurs par défaut dans `application.yml` sont acceptables pour le développement local uniquement

### Images Docker

- **Local** : Peut utiliser `latest` ou versions manuelles
- **Staging** : **TOUJOURS** tagger avec `build-${BUILD_NUMBER}` pour traçabilité

---

## 📖 Références

- **SOPS** : Voir `rhDemo/SECRETS_MANAGEMENT.md`
- **Jenkinsfile** : Voir `rhDemo/JENKINS_SETUP.md`
- **Docker Compose** : Voir `rhDemo/infra/staging/README.md`
- **Tests Selenium** : Voir `rhDemoAPITestIHM/README.md`
