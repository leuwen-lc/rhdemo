# Environnement de développement local pour exécution du code applicatif en local ou depuis un IDE par exemple

Prérequis 
- Git en version récente
- Docker Compose en version récente pour exécuter l'infrastructure nécessaire au développement local de rhDemo.

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

## Conflits de ports

En cas de conflit de ports avec des services existants sur votre poste et qui ne peuvent pas être stoppés, vous pouvez reconfigurer en changeant dans le fichier docker-compose.yml de rhDemo/infra/dev

Vous pouvez également changer le port de lancement 9000 par défaut de l'application

il faudra par contre répercuter ces changements dans les différents fichiers de configuration
- rhDemoInitKeycloak/src/main/application.yml (créé en étape 3 ci-dessou)
- rhDemo/src/main/application.yml
- rhDemoAPITestIHM/src/main/test.yml si besoin de lancer les tests Selenium

## Installation

### 1. Configurer les variables d'environnement

```bash
cd infra/dev

# Copier le template
cp .env.template .env

# Éditer avec vos valeurs pour les différents secrets
nano .env
```

NB : le fichier .env contenant des secrets à usage uniquement local, il est dans le .gitignore

### 2. Démarrer les services

```bash
# Démarrer tous les services
docker compose up -d

# Vérifier les logs
docker compose logs -f

# Vérifier l'état des services
docker compose ps
```

### 3. Initialiser Keycloak (après chaque démarrage du container car pas de BDD)

Une fois Keycloak démarré, vous devez créer le realm et les clients:

**Option 1**: Utiliser `rhDemoInitKeycloak` (recommandé)

- copier le template rhDemoInitKeycloak/src/main/resources/application.yml.template pour créer un fichier application.yml
- editez ce fichier application.yml
- reporter le secret KEYCLOAK_ADMIN_PASSWORD choisi dans rhDemo/infra/dev.env dans le champ correspondant
- choisir un client secret pour le client keycloak (sert à l'application rhDemo à s'authentifier pour gérer le dialogue OIDC avec keycloak),
- choisir des secrets pour vos utilisateurs de test 

NB : le fichier application.yml de rhDemoInitKeycloak contenant des secrets à usage uniquement local, il est dans le .gitignore

# Exécuter l'initialisation

```bash
cd monCheminGit/rhDemoInitKeycloak
./mvnw spring-boot:run -Dspring-boot.run.profiles=dev
```

**Option 2**: Configuration manuelle

1. Accéder à http://localhost:6090
2. Se connecter avec `admin` / `admin` (ou vos credentials du .env)
3. Créer le realm `RHDemo`
4. Créer le client OAuth2 pour l'application
5. Créer les utilisateurs de test

### 4. Initialiser la base de données (schéma + jeu de données fictif)

Exécuté automatiquement dans le docker compose si base vide

Si besoin d'exécution manuelle
```bash
cd monCheminGit/rhDemo
# Créer le schéma (tables + index)
docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < pgschema.sql
# Insérer les données de test (optionnel)
docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < pgdata.sql
```

### 5. Créez un fichier secrets-rhdemo.yml

- copier le template rhDemo/secrets/secrets.rhdemo.yml.template pour créer un fichier secrets.rhdemo.yml
- editez ce fichier application.yml et saisissez les secrets en cohérences avec 
    - Le secret Postgresql défini en étape 1
    - Le client secret Keycloack défini en étape 3 
- Saisissez un mot de passe quelconque pour la base de données H2 (tests d'intégration Spring uniquement)

NB : le fichier secrets-rhdemo.yml contenant des secrets à usage uniquement local, il est dans le .gitignore contrairement au fichier secrets-ephemere.yml utilisé pour le déploiement mais qui est chiffré avec SOPS.

### 6.Démarrer l'application rhDemo


Une fois l'infrastructure démarrée, et l'ensemble des secrets configurés vous pouvez lancer l'application


```bash
cd monCheminGit/rhDemo

# Démarrer l'application
./mvnw spring-boot:run
```

Par défaut l'application se connectera automatiquement à:
- PostgreSQL sur `localhost:5432`
- Keycloak sur `localhost:6090`

Elle est ensuite accessible sur http://localhost:9000/front

### 7.Démarrer les tests Selenium```bash

Vérifiez que l'application est accessible puis

```bash
cd monCheminGit/rhDemoAPITestIHM
# Démarrer les tests (ouvre un firefox)
./mvnw test
```
Le test cherche Firefox sous divers emplacements (Snap, apt, installations manuelle)
Pour une raison non complétement élucidée, la version snap(lié à ubuntu) n'était pas pilotable par les tests Selenium quand je l'ai essayée.

La solution validée sur Ubuntu 24/04 nécessite d'installer manuellement Firefox (téléchargement direct sur le site FF) sous mon répertoire home ~/firefox

### Arrêter les services

```bash
cd infra/dev

# Arrêter sans supprimer les volumes
docker compose stop

# Arrêter et supprimer les containers (conserve les volumes/données)
docker compose down

# Arrêter et supprimer TOUT (y compris les données PostgreSQL)
docker compose down -v
```

## Accès aux services

| Service | URL | Credentials |
|---------|-----|-------------|
| Keycloak Admin Console | http://localhost:6090 | admin / admin |
| PostgreSQL | localhost:5432 | dbrhdemo / changeme |
| Application rhDemo | http://localhost:9000 | (démarrer séparément) |

## Différences avec l'environnement ephemere

| Aspect | Dev local | Staging |
|--------|-----------|---------|
| Keycloak DB | H2 (en mémoire) | PostgreSQL dédié |
| Keycloak port | 6090 | 8080 (interne Docker) |
| PostgreSQL port | 5432 (exposé) | 5432 (interne Docker) |
| HTTPS | Non | Oui (nginx reverse proxy) |
| Réseau | rhdemo-dev | rhdemo-ephemere |
| Application | Lancée manuellement | Container Docker |

## Logs et débogage

```bash
# Voir les logs de tous les services
docker compose logs -f

# Logs d'un service spécifique
docker compose logs -f keycloak-dev
docker compose logs -f rhdemo-db-dev

# Se connecter à PostgreSQL
docker exec -it rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo

# Se connecter au container Keycloak
docker exec -it keycloak-dev bash

# Vérifier l'état de santé
docker compose ps
```

## Nettoyage complet

Si vous voulez repartir de zéro:

```bash
# Arrêter et tout supprimer
docker compose down -v

# Supprimer les volumes manuellement si nécessaire
docker volume rm rhdemo-dev-db-data

# Redémarrer
docker compose up -d
```

## Notes

- **Keycloak en mode dev**: Les données Keycloak sont perdues à chaque redémarrage (H2 en mémoire). Pour persister, il faudrait configurer une base PostgreSQL dédiée.
- **PostgreSQL**: Les données sont persistées dans un volume Docker (`rhdemo-dev-db-data`)
- **Port 6090**: Choisi pour éviter les conflits avec d'autres services locaux (Keycloak ephemere utilise 8080 en interne)
- **Réseau isolé**: Les services communiquent via le réseau Docker `rhdemo-dev-network`
