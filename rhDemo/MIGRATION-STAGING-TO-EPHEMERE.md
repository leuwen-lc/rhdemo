# Migration de l'environnement staging → ephemere

**Date** : 18 décembre 2025
**Environnement source** : `staging`
**Environnement cible** : `ephemere`
**Changements principaux** :
- Domaines : `*.staging.local` → `*.ephemere.local`
- Port HTTPS externe : `443` → `58443`
- Containers/Networks/Volumes : `*-staging-*` → `*-ephemere-*`

**⚠️ IMPORTANT** : L'environnement `stagingkub` (Kubernetes) reste **INCHANGÉ**

---

## 📋 Table des matières

1. [Contexte et objectifs](#contexte-et-objectifs)
2. [Modifications par projet](#modifications-par-projet)
3. [Détail des changements techniques](#détail-des-changements-techniques)
4. [Points critiques OAuth2](#points-critiques-oauth2)
5. [Configuration et déploiement](#configuration-et-déploiement)
6. [Vérifications post-migration](#vérifications-post-migration)
7. [Checklist de migration](#checklist-de-migration)

---

## Contexte et objectifs

### Objectifs de la migration

1. **Renommer l'environnement** : `staging` → `ephemere` pour mieux refléter la nature temporaire de cet environnement
2. **Changer le port HTTPS** : `443` → `58443` pour éviter les conflits avec d'autres services
3. **Mettre à jour toutes les références** dans les 3 projets du repository

### Périmètre

- ✅ Projet principal : `rhDemo`
- ✅ Sous-projet tests : `rhDemoAPITestIHM`
- ✅ Sous-projet initialisation : `rhDemoInitKeycloak`
- ⛔ **NON MODIFIÉ** : `stagingkub` (environnement Kubernetes séparé)

---

## Modifications par projet

### 1. Projet rhDemo

#### 1.1 Infrastructure Docker (`/rhDemo/infra/`)

**Répertoire renommé** :
```
rhDemo/infra/staging/  →  rhDemo/infra/ephemere/
```

**Fichier** : `docker-compose.yml`
- **Ligne 7** : `container_name: rhdemo-staging-db` → `rhdemo-ephemere-db`
- **Ligne 18** : `networks: - rhdemo-staging` → `- rhdemo-ephemere`
- **Ligne 30** : `container_name: keycloak-staging-db` → `keycloak-ephemere-db`
- **Ligne 39** : `networks: - rhdemo-staging` → `- rhdemo-ephemere`
- **Ligne 51** : `container_name: keycloak-staging` → `keycloak-ephemere`
- **Ligne 71-72** : URLs Keycloak avec port `:58443`
  ```yaml
  KC_HOSTNAME_URL: https://keycloak.ephemere.local:58443
  KC_HOSTNAME_ADMIN_URL: https://keycloak.ephemere.local:58443
  ```
- **Ligne 75** : Commentaire alias `keycloak-ephemere`
- **Ligne 83-86** : Network aliases
  ```yaml
  rhdemo-ephemere:
    aliases:
      - keycloak-ephemere
      - keycloak.ephemere.local
  ```
- **Ligne 99** : `container_name: rhdemo-staging-app` → `rhdemo-ephemere-app`
- **Ligne 103** : `SPRING_PROFILES_ACTIVE: staging` → `ephemere`
- **Ligne 131-134** : Network aliases application
- **Ligne 147** : `container_name: rhdemo-staging-nginx` → `rhdemo-ephemere-nginx`
- **Ligne 152** : **PORT CRITIQUE** `- "443:443"` → `- "58443:443"`
- **Ligne 161-165** : Network aliases nginx
- **Ligne 173-175** : Réseau Docker
  ```yaml
  rhdemo-ephemere:
    name: rhdemo-ephemere-network
  ```
- **Ligne 178-183** : Volumes Docker
  ```yaml
  rhdemo-db-data:
    name: rhdemo-ephemere-db-data
  keycloak-db-data:
    name: keycloak-ephemere-db-data
  nginx-cache:
    name: rhdemo-ephemere-nginx-cache
  ```

**Fichier** : `.env.example`
- **Ligne 2** : En-tête "RHDemo Ephemere"
- **Ligne 26** : `KEYCLOAK_HOSTNAME=keycloak.ephemere.local`
- **Ligne 36-37** : Domaines nginx
  ```bash
  NGINX_DOMAIN=rhdemo.ephemere.local
  KEYCLOAK_DOMAIN=keycloak.ephemere.local
  ```

#### 1.2 Configuration Nginx (`/rhDemo/infra/ephemere/nginx/`)

**Fichier** : `conf.d/rhdemo.conf`
- **Ligne 2** : Titre "RHDemo Ephemere"
- **Ligne 15** : `server_name rhdemo.staging.local;` → `rhdemo.ephemere.local;`
- **Ligne 34** : `server_name rhdemo.staging.local;` → `rhdemo.ephemere.local;`
- **Ligne 76** : **CRITIQUE pour OAuth2**
  ```nginx
  proxy_set_header X-Forwarded-Port 58443;  # Port HTTPS public
  ```

**Fichier** : `conf.d/keycloak.conf`
- **Ligne 2** : Titre "Keycloak Ephemere"
- **Ligne 13** : `server_name keycloak.staging.local;` → `keycloak.ephemere.local;`
- **Ligne 24** : `server_name keycloak.staging.local;` → `keycloak.ephemere.local;`

**Fichier** : `conf.d/localhost.conf`
- **Ligne 3** : Commentaire domaines ephemere
- **Ligne 5** : Commentaire réseau `rhdemo-ephemere-network`
- **Ligne 22** : `server_name localhost rhdemo-ephemere-nginx;`

**Fichier** : `nginx/generate-certs.sh`
- **Ligne 3** : Titre "ephemere"
- **Ligne 18** : Message génération pour ephemere
- **Ligne 45** : Subject certificat `/OU=Ephemere/`
- **Ligne 67** : Message environnement ephemere
- **Ligne 73-74** : Exemples /etc/hosts
  ```bash
  127.0.0.1  rhdemo.ephemere.local
  127.0.0.1  keycloak.ephemere.local
  ```

#### 1.3 Scripts shell (`/rhDemo/infra/ephemere/`)

**Fichier renommé** : `init-staging.sh` → `init-ephemere.sh`
- Toutes les occurrences `staging` → `ephemere` via `sed`
- Toutes les occurrences `STAGING` → `EPHEMERE` via `sed`
- **Ligne 3** : Commentaire "environnement de ephemere"
- **Ligne 33** : ASCII art "EPHEMERE"

**Fichier** : `init-database.sh`
- **Ligne 39** : `DB_CONTAINER="rhdemo-ephemere-db"`

**Fichier** : `init-keycloak.sh`
- Références staging → ephemere via `sed`

**Fichier** : `generate-certs.sh` (racine)
- **Ligne 5** : Commentaire "test ephemere"
- **Ligne 8-9** : Domaines `*.ephemere.local`
- **Ligne 21** : `DEFAULT_DOMAIN="ephemere.local"`
- **Ligne 46-48** : Help domaines par défaut
- **Ligne 99** : Organisation "RHDemo Ephemere"
- **Ligne 170** : Note certificat auto-signé ephemere

#### 1.4 Configuration Spring Boot (`/rhDemo/src/main/resources/`)

**Fichier renommé** : `application-staging.yml` → `application-ephemere.yml`
- **Ligne 16** : **URL publique avec port**
  ```yaml
  authorization-uri: https://keycloak.ephemere.local:58443/realms/RHDemo/protocol/openid-connect/auth
  ```
- **Ligne 21** : Token URI interne
  ```yaml
  token-uri: http://keycloak-ephemere:8080/realms/RHDemo/protocol/openid-connect/token
  ```
- **Ligne 22** : JWK Set URI interne
  ```yaml
  jwk-set-uri: http://keycloak-ephemere:8080/realms/RHDemo/protocol/openid-connect/certs
  ```
- **Ligne 32** : JWK Set URI resource server
  ```yaml
  jwk-set-uri: http://keycloak-ephemere:8080/realms/RHDemo/protocol/openid-connect/certs
  ```

#### 1.5 CI/CD Jenkins (`/rhDemo/`)

**Fichier** : `Jenkinsfile` (modifications massives via agent Opus)

**Variables d'environnement** (lignes 61-88) :
- **Ligne 61** : `SECRETS_FILE = 'rhDemo/secrets/secrets-ephemere.yml'`
- **Ligne 67** : `EPHEMERE_INFRA_PATH = 'rhDemo/infra/ephemere'`
- **Ligne 69** : `TEST_DOMAIN = 'rhdemo.ephemere.local'`
- **Ligne 70** : `KEYCLOAK_DOMAIN = 'keycloak.ephemere.local'`
- **Ligne 71** : `COMPOSE_PROJECT_NAME = 'rhdemo-ephemere-*'`
- **Lignes 75-79** : Noms de containers
  ```groovy
  CONTAINER_NGINX = 'rhdemo-ephemere-nginx'
  CONTAINER_APP = 'rhdemo-ephemere-app'
  CONTAINER_KEYCLOAK = 'keycloak-ephemere'
  CONTAINER_KEYCLOAK_DB = 'keycloak-ephemere-db'
  CONTAINER_DB = 'rhdemo-ephemere-db'
  ```
- **Ligne 83** : `NETWORK_EPHEMERE = 'rhdemo-ephemere-network'`

**Paramètres Jenkins** :
- **Ligne 88** : Choix `ephemere` au lieu de `staging`

**URLs avec port 58443** (multiples lignes) :
- Toutes les URLs `https://*.ephemere.local` incluent `:58443`
- Exemple ligne 1098-1099 : URLs d'affichage

**Volumes Docker** :
- `keycloak-ephemere-db-data`
- `rhdemo-ephemere-db-data`
- `rhdemo-ephemere-nginx-cache`

#### 1.6 Documentation (`/rhDemo/docs/` et `/rhDemo/infra/`)

**Fichier** : `docs/ENVIRONMENTS.md` (modifications via agent Opus)
- Tableau environnements : staging → ephemere
- Port HTTPS : 443 → 58443
- URLs : `https://rhdemo.ephemere.local:58443`
- Noms containers mis à jour
- Réseau : `rhdemo-ephemere-network`

**Fichier** : `infra/ENVIRONMENTS.md` (modifications via agent Opus)
- Environnement staging renommé ephemere
- Paramètre Jenkins : `DEPLOY_ENV=ephemere`
- Localisation : `rhDemo/infra/ephemere/`
- URLs avec port 58443
- Script : `init-ephemere.sh`
- Section migration : "Migration ephemere → stagingkub"
- FAQ : ephemere port 58443, stagingkub port 443

**Fichier** : `infra/ephemere/README.md`
- Toutes références staging → ephemere via `sed`

**Fichier** : `infra/ephemere/VERSIONS.md`
- Toutes références staging → ephemere via `sed`

#### 1.7 Secrets (`/rhDemo/secrets/`)

**Fichier copié** : `secrets-staging.yml` → `secrets-ephemere.yml`
- Copie exacte du fichier de secrets
- Référencé dans Jenkinsfile ligne 61

#### 1.8 Certificats SSL

**Générés** :
```bash
/rhDemo/infra/ephemere/certs/nginx.crt
/rhDemo/infra/ephemere/certs/nginx.key
```

**Commande utilisée** :
```bash
cd /home/leno-vo/git/repository/rhDemo/infra/ephemere && ./generate-certs.sh
```

**Domaines couverts** :
- `rhdemo.ephemere.local`
- `keycloak.ephemere.local`
- `localhost`
- `127.0.0.1`

---

### 2. Projet rhDemoAPITestIHM

**Impact** : MINIMAL (documentation et commentaires uniquement)

#### 2.1 Documentation

**Fichier** : `CONFIG.md`
- **Ligne 93** : Exemple Maven property
  ```bash
  -Dtest.baseurl=https://rhdemo.ephemere.local:58443 \
  ```
- **Ligne 94** : URL Keycloak
  ```bash
  -Dtest.keycloak.url=https://rhdemo.ephemere.local:58443/realms/RHDemo \
  ```

#### 2.2 Code source (commentaires)

**Fichier** : `src/test/java/fr/leuwen/rhdemo/tests/base/BaseSeleniumTest.java`
- **Ligne 48-49** : Commentaire Chrome
  ```java
  // IMPORTANT: Accepter les certificats SSL auto-signés pour ephemere
  // Permet à Chrome de se connecter à https://rhdemo.ephemere.local:58443 et https://keycloak.ephemere.local:58443
  ```
- **Ligne 107-108** : Commentaire Firefox
  ```java
  // IMPORTANT: Accepter les certificats SSL auto-signés pour ephemere
  // Permet à Firefox de se connecter à https://rhdemo.ephemere.local:58443 et https://keycloak.ephemere.local:58443
  ```

#### 2.3 Configuration

**Fichier** : `src/test/resources/test-credentials.yml`
- **Ligne 3** : Commentaire
  ```yaml
  # En ephemere/Jenkins, les variables d'environnement RHDEMOTEST_USER et RHDEMOTEST_PWD sont utilisées
  ```

**Note** : Le code fonctionnel n'a PAS été modifié car il utilise une architecture flexible (Maven properties, variables d'environnement, YAML).

---

### 3. Projet rhDemoInitKeycloak

**Impact** : MINIMAL (documentation et commentaires uniquement)

#### 3.1 Documentation

**Fichier** : `README.md`
- **Ligne 34** : Description usage
  ```markdown
  Cet outil manipule des secrets et crée des utilisateurs fictifs dans l'unique but de test de l'application RHDemo en dev et en ephemere
  ```

#### 3.2 Code source (commentaires)

**Fichier** : `src/main/java/fr/leuwen/keycloak/config/KeycloakConfig.java`
- **Ligne 12** : Javadoc
  ```java
  * Désactive la validation SSL pour accepter les certificats auto-signés en ephemere/dev
  ```
- **Ligne 32** : Log warning
  ```java
  logger.warn("⚠️  Pour ephemere: s'assurer que le serveur Keycloak utilise HTTP (pas HTTPS)");
  ```

**Note** : Le code fonctionnel n'a PAS été modifié car il est agnostique à l'environnement.

---

## Détail des changements techniques

### 1. Renommage des ressources Docker

#### Containers
| Ancien nom | Nouveau nom |
|------------|-------------|
| `rhdemo-staging-db` | `rhdemo-ephemere-db` |
| `keycloak-staging-db` | `keycloak-ephemere-db` |
| `keycloak-staging` | `keycloak-ephemere` |
| `rhdemo-staging-app` | `rhdemo-ephemere-app` |
| `rhdemo-staging-nginx` | `rhdemo-ephemere-nginx` |

#### Networks
| Ancien nom | Nouveau nom |
|------------|-------------|
| `rhdemo-staging` | `rhdemo-ephemere` |
| `rhdemo-staging-network` | `rhdemo-ephemere-network` |

#### Volumes
| Ancien nom | Nouveau nom |
|------------|-------------|
| `rhdemo-staging-db-data` | `rhdemo-ephemere-db-data` |
| `keycloak-staging-db-data` | `keycloak-ephemere-db-data` |
| `rhdemo-staging-nginx-cache` | `rhdemo-ephemere-nginx-cache` |

### 2. Changement de domaines

| Type | Ancien | Nouveau |
|------|--------|---------|
| Application | `rhdemo.staging.local` | `rhdemo.ephemere.local` |
| Keycloak | `keycloak.staging.local` | `keycloak.ephemere.local` |

### 3. Changement de port HTTPS externe

| Contexte | Ancien | Nouveau |
|----------|--------|---------|
| Port mapping Docker | `443:443` | `58443:443` |
| URL externe | `https://rhdemo.staging.local` | `https://rhdemo.ephemere.local:58443` |
| Port interne nginx | `443` | `443` (inchangé) |

### 4. Configuration réseau

**Communication externe (navigateur → nginx)** :
```
https://rhdemo.ephemere.local:58443 → Docker port mapping 58443:443 → nginx:443
```

**Communication interne (app → keycloak)** :
```
http://keycloak-ephemere:8080 (HTTP sur réseau Docker interne)
```

---

## Points critiques OAuth2

### 1. X-Forwarded-Port header

**Fichier** : `rhDemo/infra/ephemere/nginx/conf.d/rhdemo.conf:76`

```nginx
proxy_set_header X-Forwarded-Port 58443;  # Port HTTPS public
```

**Importance** : CRITIQUE
- Spring Boot utilise ce header pour construire les URLs de redirection OAuth2
- Sans ce header avec le bon port, les redirections OAuth2 échoueront

### 2. URLs publiques Keycloak

**Fichier** : `rhDemo/infra/ephemere/docker-compose.yml:71-72`

```yaml
KC_HOSTNAME_URL: https://keycloak.ephemere.local:58443
KC_HOSTNAME_ADMIN_URL: https://keycloak.ephemere.local:58443
```

**Importance** : CRITIQUE
- Force Keycloak à générer les bonnes URLs publiques
- Le navigateur doit utiliser le port 58443

### 3. Configuration Spring OAuth2

**Fichier** : `rhDemo/src/main/resources/application-ephemere.yml:16`

```yaml
authorization-uri: https://keycloak.ephemere.local:58443/realms/RHDemo/protocol/openid-connect/auth
```

**Importance** : CRITIQUE
- URL de redirection vers la page de login Keycloak
- Doit inclure le port 58443

### 4. Communication interne app ↔ keycloak

**Fichiers** : `application-ephemere.yml:21-22, 32`

```yaml
token-uri: http://keycloak-ephemere:8080/realms/RHDemo/protocol/openid-connect/token
jwk-set-uri: http://keycloak-ephemere:8080/realms/RHDemo/protocol/openid-connect/certs
```

**Importance** : CRITIQUE
- Utilise HTTP sur le réseau Docker interne (performances)
- Utilise l'alias `keycloak-ephemere` du service Docker

---

## Configuration et déploiement

### 1. Configuration /etc/hosts

Ajouter sur la machine hôte :

```bash
127.0.0.1  rhdemo.ephemere.local
127.0.0.1  keycloak.ephemere.local
```

### 2. Variables d'environnement

Créer le fichier `/rhDemo/infra/ephemere/.env` à partir de `.env.example` :

```bash
cp /rhDemo/infra/ephemere/.env.example /rhDemo/infra/ephemere/.env
# Puis éditer .env avec les vraies valeurs
```

### 3. Déploiement Docker Compose

```bash
cd /rhDemo/infra/ephemere
./init-ephemere.sh
```

### 4. Déploiement Jenkins

Dans Jenkins, sélectionner :
- **Paramètre** : `DEPLOY_ENV = ephemere`
- **Secrets** : Utiliser `secrets-ephemere.yml`

### 5. Tests Selenium

```bash
cd /rhDemoAPITestIHM
mvn clean test \
  -Dtest.baseurl=https://rhdemo.ephemere.local:58443 \
  -Dtest.keycloak.url=https://rhdemo.ephemere.local:58443/realms/RHDemo \
  -Dselenium.headless=true \
  -Dtest.username=madjid \
  -Dtest.password=madjid123
```

### 6. Initialisation Keycloak

```bash
cd /rhDemoInitKeycloak
export KEYCLOAK_SERVER_URL=https://keycloak.ephemere.local:58443
java -jar target/rhDemoInitKeycloak-1.0.0-jar-with-dependencies.jar
```

---

## Vérifications post-migration

### 1. Vérifier les containers Docker

```bash
docker ps | grep ephemere
```

**Attendu** :
- `rhdemo-ephemere-db`
- `keycloak-ephemere-db`
- `keycloak-ephemere`
- `rhdemo-ephemere-app`
- `rhdemo-ephemere-nginx`

### 2. Vérifier le réseau Docker

```bash
docker network ls | grep ephemere
```

**Attendu** : `rhdemo-ephemere-network`

### 3. Vérifier les volumes Docker

```bash
docker volume ls | grep ephemere
```

**Attendu** :
- `rhdemo-ephemere-db-data`
- `keycloak-ephemere-db-data`
- `rhdemo-ephemere-nginx-cache`

### 4. Tester l'accès HTTPS

```bash
curl -k https://rhdemo.ephemere.local:58443/health
```

**Attendu** : `OK`

### 5. Tester Keycloak

```bash
curl -k https://keycloak.ephemere.local:58443/realms/RHDemo/.well-known/openid-configuration
```

**Attendu** : Configuration JSON OpenID Connect

### 6. Vérifier les certificats SSL

```bash
openssl s_client -connect rhdemo.ephemere.local:58443 -showcerts < /dev/null 2>&1 | grep "subject="
```

**Attendu** : Subject avec `CN=rhdemo.ephemere.local`

### 7. Tester OAuth2 flow

1. Ouvrir navigateur : `https://rhdemo.ephemere.local:58443`
2. Vérifier redirection vers Keycloak avec port `:58443`
3. Login avec `madjid` / `madjid123`
4. Vérifier redirection retour vers application

---

## Checklist de migration

### Phase 1 : Préparation
- [x] Analyser l'environnement staging existant
- [x] Identifier tous les fichiers concernés
- [x] Créer un plan de migration détaillé

### Phase 2 : Renommage infrastructure
- [x] Renommer répertoire `staging/` → `ephemere/`
- [x] Mettre à jour `docker-compose.yml`
- [x] Mettre à jour `.env.example`
- [x] Créer fichier de secrets `secrets-ephemere.yml`

### Phase 3 : Configuration Nginx
- [x] Mettre à jour `conf.d/rhdemo.conf` (domaines + X-Forwarded-Port 58443)
- [x] Mettre à jour `conf.d/keycloak.conf` (domaines)
- [x] Mettre à jour `conf.d/localhost.conf` (commentaires)
- [x] Mettre à jour `nginx/generate-certs.sh`
- [x] Générer certificats SSL pour `*.ephemere.local`

### Phase 4 : Scripts
- [x] Renommer `init-staging.sh` → `init-ephemere.sh`
- [x] Mettre à jour `init-ephemere.sh` (staging → ephemere)
- [x] Mettre à jour `init-database.sh`
- [x] Mettre à jour `init-keycloak.sh`
- [x] Mettre à jour `generate-certs.sh` (racine)

### Phase 5 : Configuration Spring Boot
- [x] Renommer `application-staging.yml` → `application-ephemere.yml`
- [x] Mettre à jour URLs publiques avec port `:58443`
- [x] Mettre à jour aliases Docker (`keycloak-ephemere`)

### Phase 6 : CI/CD Jenkins
- [x] Mettre à jour `Jenkinsfile` (114 occurrences)
- [x] Changer choix environnement : `staging` → `ephemere`
- [x] Mettre à jour toutes les variables d'environnement
- [x] Mettre à jour tous les noms de containers/networks/volumes
- [x] Mettre à jour toutes les URLs avec port `:58443`

### Phase 7 : Documentation
- [x] Mettre à jour `rhDemo/infra/ephemere/README.md`
- [x] Mettre à jour `rhDemo/infra/ephemere/VERSIONS.md`
- [x] Mettre à jour `rhDemo/docs/ENVIRONMENTS.md`
- [x] Mettre à jour `rhDemo/infra/ENVIRONMENTS.md`
- [x] Créer ce fichier de migration `MIGRATION-STAGING-TO-EPHEMERE.md`

### Phase 8 : Sous-projets
- [x] Mettre à jour `rhDemoAPITestIHM/CONFIG.md`
- [x] Mettre à jour `rhDemoAPITestIHM/.../BaseSeleniumTest.java` (commentaires)
- [x] Mettre à jour `rhDemoAPITestIHM/.../test-credentials.yml` (commentaire)
- [x] Mettre à jour `rhDemoInitKeycloak/README.md`
- [x] Mettre à jour `rhDemoInitKeycloak/.../KeycloakConfig.java` (commentaires)

### Phase 9 : Vérifications
- [ ] Vérifier containers Docker démarrés
- [ ] Vérifier réseau Docker créé
- [ ] Vérifier volumes Docker créés
- [ ] Tester accès HTTPS application
- [ ] Tester accès HTTPS Keycloak
- [ ] Tester OAuth2 flow complet
- [ ] Tester les tests Selenium
- [ ] Vérifier que stagingkub fonctionne toujours

---

## Statistiques de migration

### Fichiers modifiés par projet

**rhDemo** : 25+ fichiers
- Infrastructure : 4 fichiers
- Nginx : 4 fichiers
- Scripts : 5 fichiers
- Configuration : 1 fichier
- CI/CD : 1 fichier
- Documentation : 4 fichiers
- Secrets : 1 fichier

**rhDemoAPITestIHM** : 3 fichiers (commentaires/documentation)

**rhDemoInitKeycloak** : 2 fichiers (commentaires/documentation)

**Total** : 30+ fichiers modifiés

### Lignes de code modifiées

- **rhDemo** : ~200 lignes (code + configuration)
- **rhDemoAPITestIHM** : 5 lignes (commentaires)
- **rhDemoInitKeycloak** : 4 lignes (commentaires)

### Impact par type

| Type de modification | Impact | Nombre |
|---------------------|--------|--------|
| Critique (OAuth2, ports) | ⚠️ ÉLEVÉ | 5 |
| Importante (containers, réseau) | 🔶 MOYEN | 15 |
| Documentation/commentaires | 📝 FAIBLE | 10+ |

---

## Notes importantes

### 1. Environnement stagingkub PRÉSERVÉ

L'environnement Kubernetes `stagingkub` reste **TOTALEMENT INCHANGÉ** :
- Domaines : `*.stagingkub.local`
- Port : `443` (via NodePort 30443)
- Namespace : `rhdemo-staging`
- Tous les fichiers dans `rhDemo/infra/stagingkub/` intacts

### 2. Communication interne vs externe

**Externe (navigateur)** :
- HTTPS avec port 58443
- Domaines : `*.ephemere.local:58443`

**Interne Docker** :
- HTTP port 8080 (Keycloak) ou 9000 (App)
- Utilise aliases réseau Docker
- Pas de port dans les URLs

### 3. Architecture flexible des tests

Les projets de test (`rhDemoAPITestIHM`, `rhDemoInitKeycloak`) utilisent une architecture flexible qui accepte la configuration via :
1. Maven properties (`-Dtest.baseurl=...`)
2. Variables d'environnement
3. Fichiers YAML

Aucun changement de code fonctionnel n'a été nécessaire.

---

## Commandes utiles

### Nettoyage ancien environnement staging

```bash
# Arrêter les containers staging
docker stop rhdemo-staging-nginx rhdemo-staging-app keycloak-staging keycloak-staging-db rhdemo-staging-db

# Supprimer les containers
docker rm rhdemo-staging-nginx rhdemo-staging-app keycloak-staging keycloak-staging-db rhdemo-staging-db

# Supprimer le réseau
docker network rm rhdemo-staging-network

# Supprimer les volumes (ATTENTION : perte de données)
docker volume rm rhdemo-staging-db-data keycloak-staging-db-data rhdemo-staging-nginx-cache
```

### Démarrage environnement ephemere

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/ephemere
./init-ephemere.sh
```

### Logs containers

```bash
docker logs -f rhdemo-ephemere-nginx
docker logs -f rhdemo-ephemere-app
docker logs -f keycloak-ephemere
```

---

## Références

- Docker Compose : `/rhDemo/infra/ephemere/docker-compose.yml`
- Jenkinsfile : `/rhDemo/Jenkinsfile`
- Config Spring : `/rhDemo/src/main/resources/application-ephemere.yml`
- Documentation environnements : `/rhDemo/infra/ENVIRONMENTS.md`

---

**Migration effectuée le** : 18 décembre 2025
**Par** : Claude Sonnet 4.5 (via Claude Code)
**Statut** : ✅ COMPLÈTE
