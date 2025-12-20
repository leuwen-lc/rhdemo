# Migration Staging → Ephemere - Problèmes et Solutions

## Contexte

Migration de l'environnement de test de **staging** vers **ephemere** avec changement de port d'accès externe de **443** vers **58443**.

## Date
2025-12-19

---

## 📋 Problèmes Rencontrés

### 1. Nommage incohérent des images Docker

**Symptôme** : Différence entre le nom de l'image produite et le nom utilisé par docker-compose.

**Détails** :
- Image construite : `rhdemo-api:build-123`
- Image attendue par docker-compose : `rhdemo-api:${APP_VERSION}`
- Résultat : docker-compose ne trouve pas l'image

**Cause racine** :
- Variable `RHDEMO_IMAGE` définie statiquement dans `environment` avec format `build-${BUILD_NUMBER}`
- docker-compose.yml utilise `${APP_VERSION}` pour référencer l'image

### 2. Erreur "Invalid parameter: redirect_uri" lors de l'authentification

**Symptôme** : Échec d'authentification Keycloak avec erreur `Invalid parameter: redirect_uri`

**URL problématique** :
```
https://keycloak.ephemere.local:58443/realms/RHDemo/protocol/openid-connect/auth?
  response_type=code&client_id=RHDemo&scope=openid&
  redirect_uri=https://rhdemo.ephemere.local:58443/login/oauth2/code/keycloak
```

**Détails** :
- Spring Boot construit redirect_uri avec port `:58443` (provenant de `X-Forwarded-Port`)
- Configuration Keycloak acceptait uniquement redirect_uri **sans port** (`:443` implicite)
- Keycloak rejetait les redirect_uri avec port explicite `:58443`

**Cause racine** :
- Migration du port 443 → 58443 non répercutée dans configuration Keycloak
- Headers `X-Forwarded-Port` dans nginx configurés avec port fixe 58443
- Redirect URIs Keycloak configurés sans port explicite

### 3. Échec des tests Selenium - Timeout sur champ username

**Symptôme** : Tests Selenium échouent avec timeout lors de l'authentification Keycloak

**Erreur** :
```
TimeoutException: Expected condition failed: waiting for visibility of
element located by By.id: username (tried for 20 second(s))
```

**Détails observés** :
- Page de login Keycloak détectée (`📋 Page de login Keycloak détectée`)
- Champ username jamais visible
- Fonctionnait en accès manuel sur `https://rhdemo.ephemere.local:58443`
- Fonctionnait avant migration (ancien environnement staging sur port 443)

**Cause racine** :
- Selenium accédait via alias réseau Docker interne sur port **443** (`https://rhdemo.ephemere.local`)
- Spring Boot générait redirect_uri avec port **58443** (`X-Forwarded-Port: 58443`)
- Incompatibilité : redirection vers port 58443 mais Selenium écoute sur port 443
- Selenium ne pouvait pas suivre les redirections OAuth2 correctement

### 4. Accumulation d'images Docker

**Symptôme** : Les anciennes images `rhdemo-api` s'accumulent à chaque build

**Impact** : Saturation espace disque sur serveur Jenkins

### 5. Proxy ZAP ne peut pas résoudre host.docker.internal

**Symptôme** : Tests Selenium échouent avec erreur ZAP

**Erreur ZAP** :
```
An exception occurred while attempting to connect to: https://host.docker.internal:58443/front/ajout
The exception was:
host.docker.internal
```

**Détails** :
- Selenium configure proxy ZAP pour intercepter le trafic HTTPS
- ZAP tente de se connecter à `host.docker.internal:58443`
- ZAP ne peut pas résoudre ce nom DNS (spécifique aux conteneurs Docker)
- Toutes les requêtes HTTP échouent

**Cause racine** :
- `host.docker.internal` est un nom DNS spécial Docker
- Fonctionne uniquement pour les connexions sortantes des conteneurs
- Proxy ZAP (application Java) ne peut pas résoudre ce nom
- Besoin d'une IP réelle accessible depuis le réseau Docker

### 6. Nginx route les requêtes IP vers le mauvais serveur

**Symptôme** : Accès via IP gateway `https://172.18.0.1:58443/front/` affiche "Page not found" de Keycloak

**Erreur** :
```
URL actuelle: https://172.18.0.1:58443/front/
Titre de la page: Sign in to Keycloak
Détail erreur: Page not found
```

**Détails** :
- Configuration nginx avec `server_name` spécifiques (rhdemo.ephemere.local, keycloak.ephemere.local)
- Accès via IP ne matche aucun `server_name`
- Nginx route vers le premier serveur trouvé (Keycloak) au lieu de l'application
- Keycloak retourne 404 car `/front/` n'existe pas dans Keycloak

**Cause racine** :
- Absence de serveur par défaut dans nginx
- `server_name` ne supporte pas l'accès via IP
- Tests Selenium doivent accéder via IP gateway pour compatibility ZAP
- Nginx doit savoir router les requêtes IP vers l'application et non vers Keycloak

---

## ✅ Solutions Implémentées

### Solution 1 : Harmonisation du nommage des images

**Fichier** : `rhDemo/Jenkinsfile-CI`

**Changements** :

1. **Suppression définition statique** (ligne 67-68)
   ```groovy
   // AVANT
   RHDEMO_IMAGE = "${DOCKER_IMAGE_NAME}:build-${env.BUILD_NUMBER}"

   // APRÈS
   // Variable supprimée de environment{}
   ```

2. **Définition dynamique après lecture version Maven** (lignes 164-165)
   ```groovy
   // Construire le nom complet de l'image Docker avec version-buildnumber
   env.RHDEMO_IMAGE = "${env.DOCKER_IMAGE_NAME}:${env.APP_VERSION}-${env.BUILD_NUMBER}"
   ```

3. **Export variable pour docker-compose** (ligne 685)
   ```bash
   export APP_VERSION=${env.APP_VERSION}-${env.BUILD_NUMBER}
   ```

**Résultat** :
- Format unifié : `rhdemo-api:1.1.1-SNAPSHOT-123`
- Correspondance parfaite entre build, docker-compose et registry

### Solution 2 : Configuration redirect URIs Keycloak avec port explicite

**Fichier** : `rhDemo/Jenkinsfile-CI`

**Changements** (lignes 378-392) :

```yaml
client:
  client-id: RHDemo
  root-url: https://${TEST_DOMAIN}:58443/
  redirect-uris:
    - https://${TEST_DOMAIN}:58443/*
    - https://rhdemo.ephemere.local:58443/*
    - https://keycloak.ephemere.local:58443/*
    - https://host.docker.internal:58443/*  # Pour Selenium
    - http://localhost:9000/*
  web-origins:
    - https://${TEST_DOMAIN}:58443
    - https://rhdemo.ephemere.local:58443
    - https://keycloak.ephemere.local:58443
    - https://host.docker.internal:58443
    - http://localhost:9000
```

**Fichiers** : `rhDemo/infra/ephemere/nginx/conf.d/{rhdemo,keycloak}.conf`

**Changements** :
```nginx
# Configuration header X-Forwarded-Port avec port public
proxy_set_header X-Forwarded-Port 58443;  # Port HTTPS public
```

### Solution 3 : Accès Selenium via IP Gateway Docker

**Problématique** :
- Accès réseau Docker interne → port 443
- Accès depuis l'hôte → port 58443
- Selenium doit se comporter comme utilisateur externe (port 58443)
- `host.docker.internal` ne fonctionne pas avec proxy ZAP (ZAP ne peut pas résoudre ce nom DNS)

**Solution** : Utiliser l'IP de la gateway Docker détectée dynamiquement

**Fichier** : `rhDemo/Jenkinsfile-CI`

**Détection IP Gateway** (lignes 327-330) :
```bash
# Détecter l'IP de la gateway Docker pour les tests Selenium
GATEWAY_IP=$(docker network inspect rhdemo-jenkins-network --format='{{range .IPAM.Config}}{{.Gateway}}{{end}}')
echo "🔍 Gateway IP détectée pour redirect URIs: ${GATEWAY_IP}"
```

**Configuration redirect URIs Keycloak** (lignes 390, 396) :
```yaml
redirect-uris:
  - https://${GATEWAY_IP}:58443/*
web-origins:
  - https://${GATEWAY_IP}:58443
```

**URLs Selenium** (lignes 1147-1151) :
```bash
# Détecter l'IP de la gateway pour Selenium
GATEWAY_IP=$(docker network inspect rhdemo-jenkins-network --format='{{range .IPAM.Config}}{{.Gateway}}{{end}}')
APP_URL="https://${GATEWAY_IP}:58443"
KEYCLOAK_URL="https://${GATEWAY_IP}:58443/realms/RHDemo"
```

**Bénéfices** :
- ✅ Selenium utilise le port public 58443
- ✅ Compatible avec redirect_uri générés par Spring Boot
- ✅ Keycloak accepte les redirect_uri (IP gateway dans whitelist)
- ✅ Proxy ZAP peut résoudre l'IP (contrairement à host.docker.internal)
- ✅ Tests fonctionnent comme en manuel

### Solution 4 : Nettoyage automatique des images Docker

**Fichier** : `rhDemo/Jenkinsfile-CI` (lignes 590-600)

**Changements** :

```bash
echo "📊 Images rhdemo-api avant nettoyage:"
docker images rhdemo-api --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" || true

echo "🧹 Suppression de toutes les images rhdemo-api..."
docker images rhdemo-api -q | xargs -r docker rmi -f 2>/dev/null || echo "Aucune image rhdemo-api à supprimer"

echo "✅ Nettoyage terminé"
```

**Résultat** :
- Suppression de toutes les images `rhdemo-api` avant chaque build
- Évite accumulation et saturation disque
- Force reconstruction complète

### Solution 5 : Nginx serveur par défaut pour accès via IP

**Fichier** : `rhDemo/infra/ephemere/nginx/conf.d/rhdemo.conf` (ligne 32-34)

**Changement** :

```nginx
server {
    listen 443 ssl default_server;  # Serveur par défaut pour les accès via IP
    http2 on;
    server_name rhdemo.ephemere.local _;  # _ = wildcard pour tout servername non matché
```

**Avant** :
```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name rhdemo.ephemere.local;  # Seulement ce domaine
```

**Problème résolu** :
- Accès via IP `https://172.18.0.1:58443` était routé vers Keycloak (premier serveur trouvé)
- Keycloak retournait "Page not found" car `/front/` n'existe pas
- Tests Selenium échouaient immédiatement

**Résultat** :
- ✅ Nginx route les requêtes IP vers l'application (serveur par défaut)
- ✅ Selenium peut accéder via IP gateway sans erreur 404
- ✅ Accès par domaine (`rhdemo.ephemere.local`) fonctionne toujours
- ✅ Compatible avec ZAP proxy et redirect URIs OAuth2

---

### Solution 6 : Nginx écoute aussi sur le port 58443 en interne

**Fichiers** :
- `rhDemo/infra/ephemere/nginx/conf.d/rhdemo.conf` (ligne 33)
- `rhDemo/infra/ephemere/nginx/conf.d/keycloak.conf` (ligne 24)

**Changement** :

```nginx
# rhdemo.conf
server {
    listen 443 ssl default_server;  # Standard interne
    listen 58443 ssl;  # Port externe, pour redirects OAuth2 depuis containers
    http2 on;
    server_name rhdemo.ephemere.local _;
```

```nginx
# keycloak.conf
server {
    listen 443 ssl;
    listen 58443 ssl;  # Port externe, pour redirects OAuth2 depuis containers
    http2 on;
    server_name keycloak.ephemere.local;
```

**Problème résolu** :
- ZAP (et Selenium) sont à l'intérieur du réseau Docker ephemere
- Spring Boot génère des redirects OAuth2 avec `:58443` (à cause de `X-Forwarded-Port: 58443`)
- Exemple : `https://keycloak.ephemere.local:58443/realms/RHDemo/protocol/openid-connect/auth?...`
- Firefox (via ZAP) essaie de se connecter à `:58443` mais nginx n'écoutait que sur `:443` en interne
- Erreur : `ZAP Error [HttpHostConnectException]: Connect to https://keycloak.ephemere.local:58443 failed: Connection refused`

**Résultat** :
- ✅ Nginx écoute maintenant sur 443 ET 58443 à l'intérieur du réseau Docker
- ✅ Le port 58443 est mappé vers l'extérieur via `58443:443` dans docker-compose.yml (MAIS nginx écoute désormais directement sur 58443 aussi)
- ✅ ZAP peut suivre les redirects OAuth2 avec `:58443` sans erreur de connexion
- ✅ Compatible avec accès manuel (navigateur → host:58443 → nginx:443)

**Note importante** : Le mapping de port dans docker-compose.yml (`58443:443`) signifie "port host:port container". Mais ici, nginx écoute maintenant AUSSI sur le port 58443 en interne, ce qui permet aux autres containers du même réseau de s'y connecter directement.

---

## 🎯 Architecture Réseau Finale

### Accès Utilisateur Manuel
```
Navigateur (host) → https://rhdemo.ephemere.local:58443
                ↓
          Host mapping (58443 → nginx:443)
                ↓
           Nginx:443 (docker-compose port mapping 58443:443)
                ↓
           Spring Boot (X-Forwarded-Port: 58443)
                ↓
           Redirect URI: https://rhdemo.ephemere.local:58443/login/oauth2/code/keycloak
```

### Accès Tests Selenium/ZAP (Jenkins containers)
```
Firefox (via ZAP) → https://rhdemo.ephemere.local:58443 (MÊMES URLs que l'accès manuel!)
                ↓
           ZAP connecté au réseau rhdemo-ephemere-network
                ↓
           Nginx:58443 (écoute AUSSI en interne sur 58443 pour redirects OAuth2)
                ↓
           Spring Boot (X-Forwarded-Port: 58443)
                ↓
           Redirect URI: https://rhdemo.ephemere.local:58443/login/oauth2/code/keycloak
           ET https://keycloak.ephemere.local:58443/realms/RHDemo/...
                ↓
           Firefox suit le redirect → ZAP → Nginx:58443 → Keycloak:8080
```

**Points clés** :
- ✅ **URLs identiques** pour tests Selenium et accès manuel : `rhdemo.ephemere.local:58443`
- ✅ **Plus besoin de détecter l'IP gateway Docker** : simplification majeure du Jenkinsfile
- ✅ **Redirect URIs simplifiés** : pas d'IP variable à whitelister dans Keycloak
- ZAP est connecté au réseau `rhdemo-ephemere-network`, peut résoudre les alias réseau
- Nginx écoute sur 443 ET 58443 en interne pour permettre aux redirects OAuth2 de fonctionner
- Les redirects OAuth2 utilisent `:58443` car Spring Boot reçoit `X-Forwarded-Port: 58443`
- Sans `listen 58443` dans nginx, ZAP obtiendrait "Connection refused" sur les redirects Keycloak

### Healthcheck Jenkins
```
Jenkins → https://rhdemo.ephemere.local:443 (alias réseau interne)
      ↓
  Nginx:443 (port standard interne)
      ↓
  Spring Boot
```

---

## 📊 Tableau Récapitulatif des Ports

| Contexte | Protocole | Domaine | Port | Commentaire |
|----------|-----------|---------|------|-------------|
| Utilisateur externe | HTTPS | rhdemo.ephemere.local | 58443 | Accès manuel navigateur via host |
| Selenium/ZAP (Jenkins) | HTTPS | rhdemo.ephemere.local | 58443 | **MÊMES URLs** que l'accès externe! |
| Réseau Docker interne | HTTPS | rhdemo.ephemere.local | 443 | Healthcheck, communication standard |
| Nginx (écoute interne) | HTTPS | - | 443 **ET** 58443 | Nginx écoute sur les deux ports |
| Nginx (exposition hôte) | HTTPS | - | 58443 | Port mappé `58443:443` dans docker-compose |

**Note importante** : Nginx écoute maintenant sur **deux ports en interne** :
- Port **443** : Communication standard entre conteneurs (healthcheck, etc.)
- Port **58443** : Permet aux redirects OAuth2 (générés avec `:58443`) de fonctionner depuis ZAP/Selenium

**Simplification majeure** : Depuis que nginx écoute sur le port 58443 en interne, les tests Selenium utilisent les **mêmes URLs** que les utilisateurs manuels. Plus besoin de détecter l'IP gateway Docker ni de whitelister des IPs variables dans Keycloak!

---

## 🔑 Points Clés de la Migration

1. **Nginx écoute sur deux ports en interne** : 443 (standard) ET 58443 (redirects OAuth2)
2. **URLs identiques tests/manuel** : `rhdemo.ephemere.local:58443` pour tous les accès
3. **X-Forwarded-Port: 58443** : Indique à Spring Boot le port public pour construire les URLs
4. **Redirect URIs simplifiés** : Pas besoin de whitelister l'IP gateway variable
5. **Nommage images** : Format `version-buildnumber` pour cohérence complète
6. **Nettoyage images** : Évite accumulation et problèmes d'espace disque

---

## 🚀 Tests de Validation

### Test Manuel
```bash
# Depuis navigateur sur poste
https://rhdemo.ephemere.local:58443
```
✅ Doit rediriger vers Keycloak et permettre authentification

### Test Selenium (Jenkins)
```bash
# Stage 🧪 Tests Selenium dans Jenkinsfile-CI
APP_URL="https://host.docker.internal:58443"
```
✅ Doit authentifier et exécuter tous les tests

### Test Healthcheck
```bash
# Depuis Jenkins (réseau Docker)
curl -k https://rhdemo.ephemere.local/front/
```
✅ Doit retourner HTTP 200 ou 302

---

## 📝 Fichiers Modifiés

1. `rhDemo/Jenkinsfile-CI`
   - Nommage images (lignes 164-165, 685)
   - Configuration Keycloak (lignes 378-392)
   - URLs Selenium (lignes 1132-1133)
   - Nettoyage images (lignes 590-600)

2. `rhDemo/infra/ephemere/nginx/conf.d/rhdemo.conf`
   - Header X-Forwarded-Port (ligne 76)

3. `rhDemo/infra/ephemere/nginx/conf.d/keycloak.conf`
   - Header X-Forwarded-Port (ligne 66)

4. `rhDemo/infra/ephemere/docker-compose.yml`
   - Port mapping nginx : `58443:443` (ligne 153)

---

## ⚠️ Points d'Attention

### Variable Substitution dans Jenkinsfile
- **CRITIQUE** : Utiliser `sh '''` (single quotes) pour éviter l'interprétation Groovy des variables
- **Avec `sh '''`** : Toutes les variables `${VAR}` sont substituées par bash (pas par Groovy)
- **Variables disponibles en bash** :
  - Variables d'environnement Jenkins (définies dans `environment` block) : `TEST_DOMAIN`, `KEYCLOAK_DOMAIN`, etc.
  - Variables bash locales : `GATEWAY_IP` (détectée dynamiquement)
  - Variables chargées depuis env-vars.sh : `KEYCLOAK_ADMIN_USER`, secrets, etc.
- **Dans le heredoc YAML** : Toutes les variables utilisent la syntaxe bash standard `${VAR}`
- Heredoc sans quotes (`<< YMLEOF`) permet substitution bash de toutes les variables
- Vérification ajoutée : `grep -A 5 "redirect-uris:" fichier.yml` pour valider substitution

### IP Gateway Docker
- L'IP de la gateway est détectée dynamiquement à chaque build
- Typiquement : `172.17.0.1`, `172.18.0.1`, etc.
- Compatible tous systèmes (Linux, Mac, Windows)
- Permet au proxy ZAP de résoudre correctement l'adresse

### Compatibilité Proxy ZAP
- **CRITIQUE** : ZAP ne peut pas résoudre `host.docker.internal`
- Solution : utiliser IP gateway détectée dynamiquement
- ZAP doit pouvoir accéder à l'hôte via cette IP pour intercepter le trafic HTTPS

### Certificats SSL
- Certificats auto-signés acceptés via `setAcceptInsecureCerts(true)` dans Selenium
- Firefox configuré pour accepter certificats invalides
- Production : utiliser certificats valides (Let's Encrypt)

### Proxy ZAP
- Configuré pour intercepter trafic HTTPS
- Préférences Firefox ajoutées pour compatibilité proxy ZAP
- Exclure Keycloak du proxy si problèmes de certificats persistent

---

## 🔄 Rollback

Pour revenir à l'ancienne configuration :

1. Rétablir port 443 dans docker-compose.yml
2. Supprimer port explicite des redirect URIs Keycloak
3. Selenium : utiliser alias réseau `https://rhdemo.ephemere.local`
4. Rétablir `X-Forwarded-Port: $server_port` dans nginx

---

## 🔧 Troubleshooting

### Erreur "No such property: KEYCLOAK_ADMIN_USER" lors du build Jenkins

**Symptômes** :
```
groovy.lang.MissingPropertyException: No such property: KEYCLOAK_ADMIN_USER for class: groovy.lang.Binding
```

**Cause** :
- Utilisation de `sh """` (double quotes) fait que Groovy essaie de substituer **toutes** les variables `${...}`
- Les variables bash (provenant de `env-vars.sh` ou créées dans le script) ne sont pas connues de Groovy
- Groovy échoue en essayant de résoudre les variables avant même d'exécuter le script bash

**Solution** :
- **Utiliser `sh '''`** (single quotes) au lieu de `sh """`
- Avec single quotes, Groovy ne substitue aucune variable, bash les substitue toutes
- Les variables d'environnement Jenkins (définies dans `environment` block) sont automatiquement disponibles en bash
- Exemple : `TEST_DOMAIN` défini dans `environment` est directement accessible comme `${TEST_DOMAIN}` en bash

---

### Erreur "We are sorry..." de Keycloak lors des tests

**Symptômes** :
- Selenium accède à `https://<GATEWAY_IP>:58443/front/ajout`
- Redirection vers Keycloak fonctionne
- Keycloak affiche "We are sorry..." au lieu du formulaire de login

**Causes possibles** :

1. **Variables non substituées dans application-ephemere.yml**
   - Vérifier les logs Jenkins pour la section "Vérification de la section redirect-uris"
   - Les redirect URIs doivent montrer l'IP réelle (ex: `172.18.0.1`) et non `${GATEWAY_IP}`
   - Si `${GATEWAY_IP}` apparaît littéralement, problème de substitution bash

2. **Redirect URI non whitelisté dans Keycloak**
   - Vérifier que `https://<GATEWAY_IP>:58443/*` est dans la liste des redirect URIs
   - Accéder à l'admin Keycloak : `https://keycloak.ephemere.local:58443/admin`
   - Aller dans le realm RHDemo > Client RHDemo > Settings > Valid redirect URIs

3. **Problème de timing (Keycloak pas complètement initialisé)**
   - Vérifier les logs du conteneur `keycloak-ephemere`
   - Attendre que le healthcheck soit vert avant les tests

4. **Proxy ZAP interfère avec OAuth2/OIDC**
   - Le proxy ZAP intercepte et re-signe les certificats HTTPS
   - Peut causer des problèmes avec les cookies Secure/SameSite
   - Peut perturber les redirections complexes de Keycloak

5. **ZAP ne peut pas se connecter au port 58443 en interne**
   - Symptôme : Logs montrent `ZAP Error [HttpHostConnectException]: Connect to https://keycloak.ephemere.local:58443 failed: Connection refused`
   - Cause : Le port 58443 est mappé uniquement vers le host (`58443:443` dans docker-compose.yml)
   - À l'intérieur du réseau Docker, nginx écoute uniquement sur le port 443
   - Spring Boot génère des redirects OAuth2 avec `:58443` à cause du header `X-Forwarded-Port: 58443`
   - Firefox (via ZAP) essaie de suivre ce redirect mais le port 58443 n'existe pas en interne

**Logs de debug automatiques** :

En cas d'échec du stage Selenium, les éléments suivants sont automatiquement archivés:

- **Screenshots** : `target/screenshots/error-page-keycloak.png`
- **Logs conteneurs** : archivés dans `debug-logs/`
  - `app-springboot.log` : Logs de l'application (500 dernières lignes)
  - `keycloak.log` : Logs Keycloak (500 dernières lignes)
  - `nginx.log` : Logs Nginx (500 dernières lignes)
  - `zap.log` : Logs OWASP ZAP (500 dernières lignes)
  - `network-ephemere.json` : Configuration réseau Docker ephemere
  - `network-jenkins.json` : Configuration réseau Docker jenkins
  - `containers-status.txt` : État des conteneurs
  - `gateway-ip.txt` : IP gateway détectée
- **Logs Selenium enrichis** : Analyse automatique de la page Keycloak avec:
  - URL complète avec paramètres OAuth2 (state, nonce masqués)
  - Message d'erreur Keycloak extrait
  - Causes possibles suggérées

**Commandes de diagnostic manuelles** :

```bash
# Vérifier le fichier généré
cat rhDemoInitKeycloak/src/main/resources/application-ephemere.yml | grep -A 10 "redirect-uris"

# Vérifier les logs Keycloak
docker logs keycloak-ephemere | tail -50

# Tester manuellement l'authentification avec l'IP gateway
curl -k -v "https://<GATEWAY_IP>:58443/front/"

# Vérifier la configuration du client dans Keycloak (via API)
# Remplacer <ADMIN_TOKEN> par un token admin Keycloak valide
curl -k "https://keycloak.ephemere.local:58443/admin/realms/RHDemo/clients" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" | jq '.[] | select(.clientId=="RHDemo") | .redirectUris'
```

---

## 📚 Références

- [Spring Boot Behind Proxy](https://docs.spring.io/spring-boot/reference/web/servlet.html#web.servlet.embedded-container.customizing.samesite)
- [Keycloak Redirect URI Validation](https://www.keycloak.org/docs/latest/server_admin/#_clients)
- [Docker host.docker.internal](https://docs.docker.com/desktop/networking/#i-want-to-connect-from-a-container-to-a-service-on-the-host)
- [Selenium Firefox Options](https://www.selenium.dev/documentation/webdriver/browsers/firefox/)
- [Jenkins Pipeline Shell Step](https://www.jenkins.io/doc/pipeline/steps/workflow-durable-task-step/#sh-shell-script)
- [Bash Heredoc](https://tldp.org/LDP/abs/html/here-docs.html)
