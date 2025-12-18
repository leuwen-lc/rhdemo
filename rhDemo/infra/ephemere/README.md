# Environnement de Ephemere - RHDemo

Infrastructure Docker Compose pour environnement de ephemere isolé avec HTTPS, PostgreSQL et Keycloak.

## 📋 Architecture

```
nginx:443 (HTTPS reverse proxy)
  ├─> rhdemo.ephemere.local → rhdemo-app:9000 (Spring Boot Paketo)
  │                            └─> rhdemo-db:5432 (PostgreSQL)
  └─> keycloak.ephemere.local → keycloak:8080 (Keycloak 26.0.7)
                                   └─> keycloak-db:5432 (PostgreSQL)
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| **nginx** | 443 (HTTPS) | Reverse proxy avec SSL termination |
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

### Tout doit être piloté par la chaine CI/CD Jenkins avec le Jenkinsfile déposé à la racine de rhDemo

### Si besoin d'exécution manuelle voir ci-dessous

### Étape 1: Construire l'image Docker (si nécessaire)

Depuis la racine du projet **rhdemo**:

```bash
cd /home/leno-vo/git/repository/rhDemo
./mvnw clean spring-boot:build-image
```

Vérification:
```bash
docker images | grep rhdemo-api
# rhdemo-api  0.0.1-SNAPSHOT  ...
```

### Étape 2: Configuration environnement

Créer le fichier `.env` à partir du template:

```bash
cd infra/ephemere
cp .env.example .env
```

Modifier `.env` avec vos valeurs:

```bash
# Versions
APP_VERSION=0.0.1-SNAPSHOT

# Bases de données (générer des mots de passe forts)
RHDEMO_DB_PASSWORD=changeme_rhdemo_db
KEYCLOAK_DB_PASSWORD=changeme_keycloak_db

# Keycloak admin
KEYCLOAK_ADMIN_USER=admin
KEYCLOAK_ADMIN_PASSWORD=changeme_admin

# OAuth2 (à générer depuis Keycloak)
RHDEMO_CLIENT_SECRET=changeme_client_secret

# Domaines
NGINX_DOMAIN=rhdemo.ephemere.local
KEYCLOAK_DOMAIN=keycloak.ephemere.local
```

### Étape 3: Générer les certificats SSL

Exécuter le script de génération:

```bash
cd nginx
./generate-certs.sh
```

Les certificats seront créés dans `nginx/ssl/`:
- `rhdemo.crt` / `rhdemo.key`
- `keycloak.crt` / `keycloak.key`

### Étape 4: Configuration DNS locale

Ajouter à votre `/etc/hosts`:

```bash
sudo nano /etc/hosts
```

```
127.0.0.1  rhdemo.ephemere.local
127.0.0.1  keycloak.ephemere.local
```

### Étape 5: Démarrer les services

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/ephemere
docker-compose up -d
```

Vérifier le démarrage:

```bash
docker-compose ps
docker-compose logs -f
```

### Étape 6: Vérifier les healthchecks

Attendre que tous les services soient `healthy`:

```bash
watch docker-compose ps
```

Status attendu:
```
NAME              STATE     HEALTH
nginx             running   healthy
rhdemo-app        running   healthy
rhdemo-db         running   healthy
keycloak          running   healthy
keycloak-db       running   healthy
```

## 🔐 Accès aux services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Application** | https://rhdemo.ephemere.local | Via Keycloak |
| **Keycloak Admin** | https://keycloak.ephemere.local | admin / (voir `.env`) |
| **Actuator** | https://rhdemo.ephemere.local/actuator | - |

⚠️ **Certificats auto-signés**: Acceptez l'avertissement de sécurité dans votre navigateur.

## 🔧 Configuration Keycloak

### Initialisation automatique

Utiliser le projet **rhDemoInitKeycloak** (déjà migré Spring Boot):

```bash
cd /home/leno-vo/git/repository/rhDemoInitKeycloak

# Modifier src/main/resources/application.properties
# keycloak.server-url=https://keycloak.ephemere.local
# keycloak.username=admin
# keycloak.password=${KEYCLOAK_ADMIN_PASSWORD}

./mvnw spring-boot:run
```

### Configuration manuelle

1. **Accéder à Keycloak Admin Console**:
   ```
   https://keycloak.ephemere.local
   Credentials: admin / (voir .env KEYCLOAK_ADMIN_PASSWORD)
   ```

2. **Créer le Realm "RHDemo"**

3. **Créer le Client "RHDemo"**:
   - Client ID: `RHDemo`
   - Access Type: `confidential`
   - Valid Redirect URIs: `https://rhdemo.ephemere.local/*`
   - Web Origins: `https://rhdemo.ephemere.local`
   
4. **Récupérer le Client Secret**:
   - Onglet "Credentials" → copier le secret
   - Mettre à jour `.env`: `RHDEMO_CLIENT_SECRET=xxx`
   - Redémarrer l'application:
     ```bash
     docker-compose restart rhdemo-app
     ```

5. **Créer les rôles**:
   - Client Roles → RHDemo → Add Role:
     - `consult` (lecture)
     - `MAJ` (écriture)
     - `admin` (administration)

6. **Créer des utilisateurs**:
   - Users → Add User
   - Assigner les rôles: Role Mappings → Client Roles → RHDemo

## 🛠️ Opérations courantes

### Logs

```bash
# Tous les services
docker-compose logs -f

# Service spécifique
docker-compose logs -f rhdemo-app
docker-compose logs -f keycloak
```

### Arrêter l'environnement

```bash
docker-compose down
```

### Arrêter et supprimer les volumes (⚠️ données perdues)

```bash
docker-compose down -v
```

### Redémarrer un service

```bash
docker-compose restart rhdemo-app
```

### Reconstruire l'application

```bash
# 1. Rebuild l'image Paketo
cd /home/leno-vo/git/repository/rhDemo
./mvnw clean spring-boot:build-image

# 2. Redémarrer le container
cd infra/ephemere
docker-compose up -d --force-recreate rhdemo-app
```

### Accéder à la base de données

```bash
# PostgreSQL applicatif
docker-compose exec rhdemo-db psql -U rhdemo -d rhdemodb

# PostgreSQL Keycloak
docker-compose exec keycloak-db psql -U keycloak -d keycloakdb
```

### Shell dans un container

```bash
docker-compose exec rhdemo-app bash
docker-compose exec nginx sh
```

## 📊 Monitoring

### Healthchecks

```bash
# Application Spring Boot
curl -k https://rhdemo.ephemere.local/actuator/health

# Keycloak
curl -k https://keycloak.ephemere.local/health
```

### Métriques Prometheus

```bash
curl -k https://rhdemo.ephemere.local/actuator/prometheus
```

### État des services

```bash
docker-compose ps
docker stats
```

## 🔒 Sécurité

### Certificats SSL

- **Ephemere**: Certificats auto-signés générés par `generate-certs.sh`
- **Production**: Utilisez Let's Encrypt ou certificats CA reconnus

### Headers de sécurité (configurés dans Nginx)

- `Strict-Transport-Security` (HSTS)
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy`

### Mots de passe

⚠️ **IMPORTANT**: Changez tous les mots de passe par défaut dans `.env` avant utilisation!

Générer des mots de passe forts:

```bash
# Linux
openssl rand -base64 32

# Alternative
pwgen -s 32 1
```

## 🐛 Dépannage

### L'application ne démarre pas

```bash
# Vérifier les logs
docker-compose logs rhdemo-app

# Vérifier les variables d'environnement
docker-compose exec rhdemo-app env | grep SPRING
```

### Keycloak inaccessible

```bash
# Attendre le démarrage complet (peut prendre 60-90s)
docker-compose logs -f keycloak

# Vérifier la connexion BDD
docker-compose exec keycloak-db pg_isready -U keycloak
```

### Nginx erreur 502 Bad Gateway

```bash
# Vérifier que l'application est démarrée
docker-compose ps rhdemo-app

# Tester depuis nginx
docker-compose exec nginx wget -O- http://rhdemo-app:9000/actuator/health
```

### Certificats SSL invalides

```bash
# Régénérer les certificats
cd nginx
rm ssl/*.crt ssl/*.key
./generate-certs.sh
docker-compose restart nginx
```

### Volumes corrompus

```bash
# Sauvegarder les données si nécessaire
docker-compose exec rhdemo-db pg_dump -U rhdemo rhdemodb > backup.sql

# Recréer les volumes
docker-compose down -v
docker-compose up -d

# Restaurer les données
cat backup.sql | docker-compose exec -T rhdemo-db psql -U rhdemo -d rhdemodb
```

## 📁 Structure des fichiers

```
infra/ephemere/
├── docker-compose.yml          # Orchestration des services
├── .env                        # Variables d'environnement (non versionné)
├── .env.example                # Template de configuration
├── README.md                   # Cette documentation
└── nginx/
    ├── nginx.conf              # Configuration principale Nginx
    ├── generate-certs.sh       # Script génération certificats SSL
    ├── conf.d/
    │   ├── rhdemo.conf         # Vhost application
    │   └── keycloak.conf       # Vhost Keycloak
    └── ssl/                    # Certificats SSL (généré)
        ├── rhdemo.crt
        ├── rhdemo.key
        ├── keycloak.crt
        └── keycloak.key
```

## 🔗 Références

- [Spring Boot Documentation](https://docs.spring.io/spring-boot/docs/current/reference/html/)
- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Paketo Buildpacks](https://paketo.io/)
- [Docker Compose](https://docs.docker.com/compose/)
- [Nginx Documentation](https://nginx.org/en/docs/)

## 📝 Notes

- **Performance**: JVM configurée avec `MaxRAMPercentage=75%` et `BPL_JVM_THREAD_COUNT=50`
- **Cache**: Assets statiques cachés 1 an par Nginx
- **Isolation**: Réseau bridge dédié, pas d'exposition des ports PostgreSQL sur l'hôte
- **Healthchecks**: Tous les services surveillés (PostgreSQL, Keycloak, Spring Boot Actuator)
- **Production-ready**: Configuration adaptée pour ephemere proche de la production
