# Migration de l'environnement staging → ephemere

**Date** : 18 décembre 2025
**Environnement source** : `staging`
**Environnement cible** : `ephemere`
**Changements principaux** :
- Domaines : `*.staging.local` → `*.ephemere.local`
- Port HTTPS externe : `443` → `58443`
- Containers/Networks/Volumes : `*-staging-*` → `*-ephemere-*`

**⚠️ IMPORTANT** : L'environnement `stagingkub` (Kubernetes) reste **INCHANGÉ**

  - [Contexte et objectifs](#contexte-et-objectifs)
    - [Objectifs de la migration](#objectifs-de-la-migration)
    - [Périmètre](#périmètre)
  - [Détail des changements techniques](#détail-des-changements-techniques)
    - [1. Renommage des ressources Docker](#1-renommage-des-ressources-docker)
      - [Containers](#containers)
      - [Networks](#networks)
      - [Volumes](#volumes)
    - [2. Changement de domaines](#2-changement-de-domaines)
    - [3. Changement de port HTTPS externe](#3-changement-de-port-https-externe)
    - [4. Configuration réseau](#4-configuration-réseau)
  - [Points critiques OAuth2](#points-critiques-oauth2)
    - [1. X-Forwarded-Port header](#1-x-forwarded-port-header)
    - [2. URLs publiques Keycloak](#2-urls-publiques-keycloak)
    - [3. Configuration Spring OAuth2](#3-configuration-spring-oauth2)
    - [4. Communication interne app ↔ keycloak](#4-communication-interne-app--keycloak)
  - [Configuration et déploiement](#configuration-et-déploiement)
    - [1. Configuration /etc/hosts](#1-configuration-etchosts)
    - [2. Déploiement Jenkins](#2-déploiement-jenkins)
  - [Notes importantes](#notes-importantes)
    - [1. Environnement stagingkub PRÉSERVÉ](#1-environnement-stagingkub-préservé)
    - [2. Communication interne vs externe](#2-communication-interne-vs-externe)
    - [3. Architecture flexible des tests](#3-architecture-flexible-des-tests)
  - [📋 Problèmes Rencontrés](#-problèmes-rencontrés)
    - [1. Nommage incohérent des images Docker](#1-nommage-incohérent-des-images-docker)
    - [2. Erreur "Invalid parameter: redirect\_uri" lors de l'authentification](#2-erreur-invalid-parameter-redirect_uri-lors-de-lauthentification)
    - [3. Échec des tests Selenium - Timeout sur champ username](#3-échec-des-tests-selenium---timeout-sur-champ-username)
    - [4. Accumulation d'images Docker](#4-accumulation-dimages-docker)
    - [5. Proxy ZAP ne peut pas résoudre host.docker.internal](#5-proxy-zap-ne-peut-pas-résoudre-hostdockerinternal)
    - [6. Nginx route les requêtes IP vers le mauvais serveur](#6-nginx-route-les-requêtes-ip-vers-le-mauvais-serveur)
  - [✅ Solutions Implémentées](#-solutions-implémentées)
    - [Solution 1 : Harmonisation du nommage des images](#solution-1--harmonisation-du-nommage-des-images)
    - [Solution 2 : Configuration redirect URIs Keycloak avec port explicite](#solution-2--configuration-redirect-uris-keycloak-avec-port-explicite)
    - [Solution 3 : Accès Selenium via IP Gateway Docker](#solution-3--accès-selenium-via-ip-gateway-docker)
    - [Solution 4 : Nettoyage automatique des images Docker](#solution-4--nettoyage-automatique-des-images-docker)
    - [Solution 5 : Nginx serveur par défaut pour accès via IP](#solution-5--nginx-serveur-par-défaut-pour-accès-via-ip)
    - [Solution 6 : Nginx écoute aussi sur le port 58443 en interne](#solution-6--nginx-écoute-aussi-sur-le-port-58443-en-interne)
  - [🎯 Architecture Réseau Finale](#-architecture-réseau-finale)
  - [📊 Tableau Récapitulatif des Ports](#-tableau-récapitulatif-des-ports)
  - [🔑 Points Clés de la Migration](#-points-clés-de-la-migration)
  - [🚀 Tests de Validation](#-tests-de-validation)
  - [📝 Fichiers Modifiés](#-fichiers-modifiés)
  - [⚠️ Points d'Attention](#️-points-dattention)
  - [📚 Références](#-références)

---

## Contexte et objectifs

### Objectifs de la migration

1. **Renommer l'environnement** : `staging` → `ephemere` pour mieux refléter la nature temporaire de cet environnement
2. **Changer le port HTTPS** d'écoute sur la machine host : `443` → `58443` pour éviter les conflits avec d'autres services
3. **Mettre à jour toutes les références** dans les 3 projets du repository

### Périmètre

- ✅ Projet principal : `rhDemo`
- ✅ Sous-projet tests : `rhDemoAPITestIHM`
- ✅ Sous-projet initialisation : `rhDemoInitKeycloak`
- ⛔ **NON MODIFIÉ** : `stagingkub` (environnement Kubernetes séparé)



**Note** : Le code fonctionnel n'a PAS été modifié car il utilise une architecture flexible (Maven properties, variables d'environnement, YAML).


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
### 2. Déploiement Jenkins

Dans Jenkins, sélectionner :
- **Paramètre** : `DEPLOY_ENV = ephemere`
- **Secrets** : Utiliser `secrets-ephemere.yml`


## Notes importantes

### 1. Environnement stagingkub PRÉSERVÉ

L'environnement Kubernetes `stagingkub` reste **TOTALEMENT INCHANGÉ** :
- Domaines : `*.stagingkub.intra.leuwen-lc.fr`
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
- nginx écoute néanmoins en interne également sur 58443 pour traiter les appels via Selenium/Zap qui se connectent au réseau interne de ephemere

### 3. Architecture flexible des tests

Les projets de test (`rhDemoAPITestIHM`, `rhDemoInitKeycloak`) utilisent une architecture flexible qui accepte la configuration via :
1. Maven properties (`-Dtest.baseurl=...`)
2. Variables d'environnement
3. Fichiers YAML

Aucun changement de code fonctionnel n'a été nécessaire.


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
- ✅ **Pas besoin de détecter l'IP gateway Docker** : simplification majeure du Jenkinsfile
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

**Simplification majeure** : Depuis que nginx écoute sur le port 58443 en interne, les tests Selenium utilisent les **mêmes URLs** que les utilisateurs manuels. Pas besoin de détecter l'IP gateway Docker ni de whitelister des IPs variables dans Keycloak!

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

### Compatibilité Proxy ZAP
- **CRITIQUE** : ZAP ne peut pas résoudre `host.docker.internal`
- Solution : ZAP doit pouvoir accéder à au réseau ephemere - nginx doit écouter également en interne sur le port 58443



## 📚 Références

- [Spring Boot Behind Proxy](https://docs.spring.io/spring-boot/reference/web/servlet.html#web.servlet.embedded-container.customizing.samesite)
- [Keycloak Redirect URI Validation](https://www.keycloak.org/docs/latest/server_admin/#_clients)
- [Docker host.docker.internal](https://docs.docker.com/desktop/networking/#i-want-to-connect-from-a-container-to-a-service-on-the-host)
- [Selenium Firefox Options](https://www.selenium.dev/documentation/webdriver/browsers/firefox/)
- [Jenkins Pipeline Shell Step](https://www.jenkins.io/doc/pipeline/steps/workflow-durable-task-step/#sh-shell-script)
- [Bash Heredoc](https://tldp.org/LDP/abs/html/here-docs.html)

