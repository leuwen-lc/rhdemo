# Gestion des versions des images Docker

## Centralisation des versions

Les versions des images Docker de base sont définies dans **trois endroits synchronisés** :

| Fichier | Usage | Format |
|---------|-------|--------|
| [.env.example](.env.example) | **Template local** | Variables d'environnement |
| [docker-compose.yml](docker-compose.yml) | **Déploiement** | Variables avec valeurs par défaut |
| [Jenkinsfile](../../Jenkinsfile) | **CI/CD** | Variables d'environnement Jenkins |

## Versions actuelles

| Service | Version | Justification |
|---------|---------|---------------|
| **Nginx** | `1.27-alpine` | Version stable récente, alpine pour taille réduite |
| **PostgreSQL** | `16-alpine` | Version LTS, compatible Spring Boot 3.x |
| **Keycloak** | `26.4.2` | Version stable avec support PostgreSQL 16 |

## Comment mettre à jour une version

### 1. Mettre à jour .env.example

```bash
cd rhDemo/infra/staging
vim .env.example
```

```bash
# Versions des images Docker de base
NGINX_IMAGE=nginx:1.27-alpine        # Nouvelle version
POSTGRES_IMAGE=postgres:16-alpine    # Nouvelle version
KEYCLOAK_IMAGE=quay.io/keycloak/keycloak:26.4.2  # Nouvelle version
```

### 2. Mettre à jour docker-compose.yml

Les valeurs par défaut doivent correspondre à .env.example :

```yaml
services:
  rhdemo-db:
    image: ${POSTGRES_IMAGE:-postgres:16-alpine}  # ← Valeur par défaut

  keycloak:
    image: ${KEYCLOAK_IMAGE:-quay.io/keycloak/keycloak:26.4.2}  # ← Valeur par défaut

  nginx:
    image: ${NGINX_IMAGE:-nginx:1.27-alpine}  # ← Valeur par défaut
```

### 3. Mettre à jour Jenkinsfile

```groovy
environment {
    // Versions des images Docker de base
    NGINX_IMAGE = "nginx:1.27-alpine"
    POSTGRES_IMAGE = "postgres:16-alpine"
    KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.4.2"
}
```

### 4. Tester localement

```bash
# 1. Supprimer les anciennes images
docker-compose down -v
docker rmi nginx:ancienne-version postgres:ancienne-version

# 2. Créer un .env avec les nouvelles versions (optionnel, utilise .env.example par défaut)
cp .env.example .env

# 3. Lancer avec les nouvelles images
docker-compose up -d

# 4. Vérifier les versions
docker-compose ps
docker inspect rhdemo-staging-nginx | grep Image
docker inspect rhdemo-staging-db | grep Image
docker inspect keycloak-staging | grep Image
```

### 5. Tester avec Jenkins

Jenkins utilisera les variables définies dans `environment` du Jenkinsfile.

```bash
# Le Jenkinsfile exporte les variables avant docker-compose
export NGINX_IMAGE="${NGINX_IMAGE}"
export POSTGRES_IMAGE="${POSTGRES_IMAGE}"
export KEYCLOAK_IMAGE="${KEYCLOAK_IMAGE}"
docker-compose up -d
```

## Stratégie de montée de version

### Nginx

**Politique** : Suivre les versions stables alpine

```bash
# Vérifier les versions disponibles
docker search nginx | grep alpine
docker pull nginx:1.27-alpine

# Tester avant mise en production
docker run --rm nginx:1.27-alpine nginx -v
```

**Notes** :
- Toujours utiliser les tags `-alpine` pour réduire la taille
- Éviter le tag `latest` pour la reproductibilité

### PostgreSQL

**Politique** : Rester sur une version majeure LTS (16)

```bash
# Versions disponibles
docker search postgres | grep 16-alpine

# Vérification compatibilité
docker run --rm postgres:16-alpine postgres --version
```

**Notes** :
- PostgreSQL 16 est une version LTS (Long Term Support)
- Migrations majeures (ex: 16 → 17) nécessitent un pg_dump/restore
- Toujours tester les migrations avec un backup complet

### Keycloak

**Politique** : Suivre les versions stables récentes

```bash
# Vérifier les versions sur Quay.io
curl -s https://quay.io/api/v1/repository/keycloak/keycloak/tag/ | jq -r '.tags[].name' | grep "^26"

# Tester localement
docker pull quay.io/keycloak/keycloak:26.4.2
```

**Notes** :
- Keycloak 26.x est la dernière version majeure stable
- Vérifier les breaking changes dans les release notes
- Tester l'initialisation avec rhDemoInitKeycloak après montée de version

## Problèmes connus

### Nginx : Layers corrompus

**Symptôme** : `nginx.conf` créé comme répertoire au lieu de fichier

**Cause** : Cache Docker corrompu

**Solution** : Le Jenkinsfile supprime automatiquement l'image nginx avant rebuild
```bash
docker rmi ${NGINX_IMAGE} 2>/dev/null || true
```

### PostgreSQL : Incompatibilité de version

**Symptôme** : `FATAL: database files are incompatible with server`

**Cause** : Volume créé avec une ancienne version majeure de PostgreSQL

**Solution** :
```bash
# Backup avec ancienne version
docker-compose up -d rhdemo-db
docker exec rhdemo-staging-db pg_dump -U rhdemo rhdemo > backup.sql

# Supprimer volume et recréer avec nouvelle version
docker-compose down -v
docker volume rm rhdemo-staging-db-data

# Restaurer avec nouvelle version
docker-compose up -d rhdemo-db
cat backup.sql | docker exec -i rhdemo-staging-db psql -U rhdemo rhdemo
```

### Keycloak : Migration base de données

**Symptôme** : Keycloak refuse de démarrer après montée de version

**Cause** : Schéma de base de données incompatible

**Solution** : Keycloak migre automatiquement le schéma au démarrage
```bash
# Vérifier les logs de migration
docker logs keycloak-staging | grep "Liquibase"

# En cas d'erreur, backup et recréation
docker exec keycloak-staging-db pg_dump -U keycloak keycloak > keycloak-backup.sql
docker volume rm keycloak-staging-db-data
# Relancer docker-compose
```

## Checklist de montée de version

- [ ] Lire les release notes de la nouvelle version
- [ ] Mettre à jour `.env.example`
- [ ] Mettre à jour `docker-compose.yml` (valeurs par défaut)
- [ ] Mettre à jour `Jenkinsfile` (variables environment)
- [ ] Tester localement avec `docker-compose up -d`
- [ ] Vérifier les healthchecks : `docker-compose ps`
- [ ] Tester l'application : `curl https://rhdemo.staging.local/front`
- [ ] Tester l'authentification Keycloak
- [ ] Lancer les tests Selenium : `cd rhDemoAPITestIHM && mvn test`
- [ ] Tester avec Jenkins (build complet)
- [ ] Créer un commit avec la nouvelle version
- [ ] Documenter les breaking changes dans CHANGELOG

## Références

- [Nginx Docker Hub](https://hub.docker.com/_/nginx)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [Keycloak Quay.io](https://quay.io/repository/keycloak/keycloak?tab=tags)
- [Keycloak Release Notes](https://www.keycloak.org/docs/latest/release_notes/)
