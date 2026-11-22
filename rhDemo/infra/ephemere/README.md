# Environnement de Ephemere - RHDemo

Infrastructure Docker Compose pour environnement ephemere isolé avec HTTPS, PostgreSQL et Keycloak.

## 📋 Architecture

```
nginx:58443 (HTTPS reverse proxy)
  ├─> rhdemo.ephemere.local → rhdemo-app:9000 (Spring Boot)
  │                            └─> rhdemo-db:5432 (PostgreSQL)
  └─> keycloak.ephemere.local → keycloak:8080 (Keycloak)
                                   └─> keycloak-db:5432 (PostgreSQL)
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| **nginx** | 58443 (HTTPS) | Reverse proxy avec SSL termination |
| **rhdemo-app** | 9000 | Application Spring Boot (image construite par le `Dockerfile` du projet) |
| **rhdemo-db** | 5432 | PostgreSQL (données applicatives) |
| **keycloak** | 8080 | Serveur d'authentification OAuth2/OIDC |
| **keycloak-db** | 5432 | PostgreSQL (données Keycloak) |

Seul le port 58443 de nginx est publié sur l'hôte ; les images et leurs versions sont dans [`docker-compose.yml`](docker-compose.yml).

### Réseau

- **Network isolé**: `rhdemo-ephemere-network` (bridge)
- **Volumes persistants**: 
  - `rhdemo-db-data` (données applicatives)
  - `keycloak-db-data` (données auth)
  - `nginx-cache` (cache statique)

## 🚀 Démarrage rapide

### Prérequis

- Docker 24.x+
- Docker Compose 2.x+
- Image Docker applicative `rhdemo-api:<version>` construite par le build CI en cours

### Construction de l'environnement Ephemere
La construction est obligatoirement pilotée par `Jenkinsfile-CI` (racine de `rhDemo/`) : il génère les secrets (aléatoires, jamais stockés) et les certificats (`generate-certs.sh`), démarre le Compose, initialise la base et Keycloak, lance Selenium à travers ZAP puis détruit l'environnement. Il n'y a pas de démarrage manuel ; le paramètre `KEEP_EPHEMERE_ENV` garde l'environnement après le build.


### Configuration DNS locale
Uniquement si vous souhaitez vous connecter manuellement après lancement du pipeline CI et en ayant choisi
l'option KEEP_EPHEMERE_ENV

Ajouter à votre `/etc/hosts`:

```bash
sudo nano /etc/hosts
```

```
127.0.0.1  rhdemo.ephemere.local
127.0.0.1  keycloak.ephemere.local
```


## 🔐 Accès aux services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Application** | https://rhdemo.ephemere.local:58443 | Via Keycloak |
| **Keycloak Admin** | https://keycloak.ephemere.local:58443 | `admin` ; mot de passe tiré au hasard par le build : `docker exec keycloak-ephemere printenv KEYCLOAK_ADMIN_PASSWORD` |
| **Actuator** | non exposé : `/actuator` est bloqué par nginx (403), healthchecks en direct sur `rhdemo-app:9000` | - |

⚠️ **Certificats auto-signés**: Acceptez l'avertissement de sécurité dans votre navigateur.

## 🔧 Configuration Keycloak

Initialisation automatique: Le pipeline utilise le sous projet **rhDemoInitKeycloak** (Spring Boot)