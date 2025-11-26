# Environnement de développement local

Docker Compose pour exécuter l'infrastructure nécessaire au développement local de rhDemo.

## Services fournis

### 1. PostgreSQL (`rhdemo-db-dev`)
- **Port**: `5432` (port standard PostgreSQL)
- **Base de données**: `dbrhdemo`
- **Utilisateur**: `dbrhdemo`
- **Mot de passe**: Configurable via `.env` (défaut: `changeme`)
- **Container**: `rhdemo-dev-db`

### 2. Keycloak (`keycloak-dev`)
- **Port**: `6090` (accès HTTP)
- **Admin Console**: http://localhost:6090
- **Mode**: `start-dev` (développement)
- **Base de données**: H2 (en mémoire, par défaut en mode dev)
- **Admin user**: Configurable via `.env` (défaut: `admin`)
- **Admin password**: Configurable via `.env` (défaut: `admin`)
- **Container**: `keycloak-dev`

## Installation

### 1. Configurer les variables d'environnement

```bash
cd infra/dev

# Copier le template
cp .env.template .env

# Éditer avec vos valeurs (optionnel, les valeurs par défaut fonctionnent)
vim .env
```

### 2. Démarrer les services

```bash
# Démarrer tous les services
docker-compose up -d

# Vérifier les logs
docker-compose logs -f

# Vérifier l'état des services
docker-compose ps
```

### 3. Initialiser Keycloak (première utilisation)

Une fois Keycloak démarré, vous devez créer le realm et les clients:

**Option 1**: Utiliser `rhDemoInitKeycloak` (recommandé)

```bash
cd ../../rhDemoInitKeycloak

# Créer application-dev.yml avec la configuration Keycloak
# (voir template dans rhDemoInitKeycloak/src/main/resources/)

# Exécuter l'initialisation
./mvnw spring-boot:run -Dspring-boot.run.profiles=dev
```

**Option 2**: Configuration manuelle

1. Accéder à http://localhost:6090
2. Se connecter avec `admin` / `admin` (ou vos credentials du .env)
3. Créer le realm `RHDemo`
4. Créer le client OAuth2 pour l'application
5. Créer les utilisateurs de test

### 4. Initialiser la base de données

```bash
cd ../..

# Exécuter le script SQL de création du schéma
docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < pgddl.sql
```

## Utilisation

### Démarrer l'application rhDemo

Une fois l'infrastructure démarrée, vous pouvez lancer l'application:

```bash
cd rhDemo

# S'assurer que secrets/secrets-rhdemo.yml existe et contient:
# rhdemo:
#   datasource:
#     password:
#       pg: changeme  # (ou votre mot de passe PostgreSQL)
#   client:
#     registration:
#       keycloak:
#         client:
#           secret: <votre-secret-client-keycloak>

# Démarrer l'application
./mvnw spring-boot:run
```

L'application se connectera automatiquement à:
- PostgreSQL sur `localhost:5432`
- Keycloak sur `localhost:6090`

### Arrêter les services

```bash
cd infra/dev

# Arrêter sans supprimer les volumes
docker-compose stop

# Arrêter et supprimer les containers (conserve les volumes/données)
docker-compose down

# Arrêter et supprimer TOUT (y compris les données PostgreSQL)
docker-compose down -v
```

## Accès aux services

| Service | URL | Credentials |
|---------|-----|-------------|
| Keycloak Admin Console | http://localhost:6090 | admin / admin |
| PostgreSQL | localhost:5432 | dbrhdemo / changeme |
| Application rhDemo | http://localhost:8080 | (démarrer séparément) |

## Différences avec l'environnement staging

| Aspect | Dev local | Staging |
|--------|-----------|---------|
| Keycloak DB | H2 (en mémoire) | PostgreSQL dédié |
| Keycloak port | 6090 | 8080 (interne Docker) |
| PostgreSQL port | 5432 (exposé) | 5432 (interne Docker) |
| HTTPS | Non | Oui (nginx reverse proxy) |
| Réseau | rhdemo-dev | rhdemo-staging |
| Application | Lancée manuellement | Container Docker |

## Logs et débogage

```bash
# Voir les logs de tous les services
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f keycloak-dev
docker-compose logs -f rhdemo-db-dev

# Se connecter à PostgreSQL
docker exec -it rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo

# Se connecter au container Keycloak
docker exec -it keycloak-dev bash

# Vérifier l'état de santé
docker-compose ps
```

## Nettoyage complet

Si vous voulez repartir de zéro:

```bash
# Arrêter et tout supprimer
docker-compose down -v

# Supprimer les volumes manuellement si nécessaire
docker volume rm rhdemo-dev-db-data

# Redémarrer
docker-compose up -d
```

## Notes

- **Keycloak en mode dev**: Les données Keycloak sont perdues à chaque redémarrage (H2 en mémoire). Pour persister, il faudrait configurer une base PostgreSQL dédiée.
- **PostgreSQL**: Les données sont persistées dans un volume Docker (`rhdemo-dev-db-data`)
- **Port 6090**: Choisi pour éviter les conflits avec d'autres services locaux (Keycloak staging utilise 8080 en interne)
- **Réseau isolé**: Les services communiquent via le réseau Docker `rhdemo-dev-network`
