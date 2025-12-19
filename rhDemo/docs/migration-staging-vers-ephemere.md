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

### Variable Substitution dans Jenkinsfile
- **CRITIQUE** : Utiliser `sh """` (double quotes) pour permettre substitution Groovy des variables d'environnement
- Variables Groovy (`${env.VAR}`) substituées par Groovy AVANT exécution bash
- Variables bash (`\${VAR}`) échappées avec `\` pour substitution APRÈS par bash
- Heredoc sans quotes (`<< YMLEOF`) permet substitution bash des variables dans le document
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

**Commandes de diagnostic** :

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
