# Environnement de Ephemere - RHDemo

Infrastructure Docker Compose pour environnement ephemere isolé avec HTTPS, PostgreSQL et Keycloak.

## 📋 Architecture

```
nginx:58443 (HTTPS reverse proxy)
  ├─> rhdemo.ephemere.local → rhdemo-app:9000 (Spring Boot)
  │                            └─> rhdemo-db:5432 (PostgreSQL)
  └─> keycloak.ephemere.local → keycloak:8080 (Keycloak 26.0.7)
                                   └─> keycloak-db:5432 (PostgreSQL)
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| **nginx** | 58443 (HTTPS) | Reverse proxy avec SSL termination |
| **rhdemo-app** | 9000 | Application Spring Boot (image Paketo) |
| **rhdemo-db** | 5432 | PostgreSQL 16 (données applicatives) |
| **keycloak** | 8080 | Serveur d'authentification OAuth2/OIDC |
| **keycloak-db** | 5432 | PostgreSQL 16 (données Keycloak) |

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
- Image Docker applicative: `rhdemo-api:0.0.1-SNAPSHOT` (construite via Paketo)

### Construction de l'environnement Ephemere
La construction est obligatoirement pilotée par la chaine CI Jenkins avec le Jenkinsfile-CI déposé à la racine de rhDemo


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
| **Keycloak Admin** | https://keycloak.ephemere.local:58443 | admin / (voir `.env`) |
| **Actuator** | https://rhdemo.ephemere.local/actuator:58443 | - |

⚠️ **Certificats auto-signés**: Acceptez l'avertissement de sécurité dans votre navigateur.

## 🔧 Configuration Keycloak

Initialisation automatique: Le pipeline utilise le sous projet **rhDemoInitKeycloak** (Spring Boot)