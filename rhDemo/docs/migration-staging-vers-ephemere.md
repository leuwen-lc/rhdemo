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

### Solution 3 : Accès Selenium via host.docker.internal

**Problématique** :
- Accès réseau Docker interne → port 443
- Accès depuis l'hôte → port 58443
- Selenium doit se comporter comme utilisateur externe (port 58443)

**Solution** : Utiliser `host.docker.internal` pour accès hôte depuis conteneur

**Fichier** : `rhDemo/Jenkinsfile-CI` (lignes 1132-1133)

```bash
# Selenium accède comme un utilisateur externe via l'hôte
APP_URL="https://host.docker.internal:58443"
KEYCLOAK_URL="https://host.docker.internal:58443/realms/RHDemo"
```

**Bénéfices** :
- ✅ Selenium utilise le port public 58443
- ✅ Compatible avec redirect_uri générés par Spring Boot
- ✅ Keycloak accepte les redirect_uri (whitelist)
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

---

## 🎯 Architecture Réseau Finale

### Accès Utilisateur Manuel
```
Navigateur → https://rhdemo.ephemere.local:58443
         ↓
    Nginx (port 58443:443)
         ↓
    Spring Boot (X-Forwarded-Port: 58443)
         ↓
    Redirect URI: https://rhdemo.ephemere.local:58443/login/oauth2/code/keycloak
```

### Accès Tests Selenium (Jenkins)
```
Firefox (Jenkins) → https://host.docker.internal:58443
                ↓
           Nginx (port 58443:443)
                ↓
           Spring Boot (X-Forwarded-Port: 58443)
                ↓
           Redirect URI: https://host.docker.internal:58443/login/oauth2/code/keycloak
```

### Healthcheck Jenkins
```
Jenkins → https://rhdemo.ephemere.local:443 (alias réseau interne)
      ↓
  Nginx (port interne 443)
      ↓
  Spring Boot
```

---

## 📊 Tableau Récapitulatif des Ports

| Contexte | Protocole | Domaine | Port | Commentaire |
|----------|-----------|---------|------|-------------|
| Utilisateur externe | HTTPS | rhdemo.ephemere.local | 58443 | Accès manuel navigateur |
| Selenium (Jenkins) | HTTPS | host.docker.internal | 58443 | Tests automatisés |
| Réseau Docker interne | HTTPS | rhdemo.ephemere.local | 443 | Healthcheck, communication inter-conteneurs |
| Nginx (écoute interne) | HTTPS | - | 443 | Port conteneur |
| Nginx (exposition hôte) | HTTPS | - | 58443 | Port mappé `58443:443` |

---

## 🔑 Points Clés de la Migration

1. **host.docker.internal** : Permet aux conteneurs Jenkins d'accéder à l'hôte (comme utilisateur externe)
2. **X-Forwarded-Port: 58443** : Indique à Spring Boot le port public pour construire les URLs
3. **Redirect URIs avec port explicite** : Keycloak accepte `:58443` dans tous les domaines
4. **Nommage images** : Format `version-buildnumber` pour cohérence complète
5. **Nettoyage images** : Évite accumulation et problèmes d'espace disque

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

### Compatibilité Docker
- `host.docker.internal` fonctionne sur Docker Desktop (Mac/Windows)
- Sur Linux standard, peut nécessiter configuration supplémentaire
- Alternative Linux : utiliser IP gateway réseau (`docker network inspect`)

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

## 📚 Références

- [Spring Boot Behind Proxy](https://docs.spring.io/spring-boot/reference/web/servlet.html#web.servlet.embedded-container.customizing.samesite)
- [Keycloak Redirect URI Validation](https://www.keycloak.org/docs/latest/server_admin/#_clients)
- [Docker host.docker.internal](https://docs.docker.com/desktop/networking/#i-want-to-connect-from-a-container-to-a-service-on-the-host)
- [Selenium Firefox Options](https://www.selenium.dev/documentation/webdriver/browsers/firefox/)
