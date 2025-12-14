# Environnements rhDemo

Ce document décrit les différents environnements disponibles pour développer et tester l'application rhDemo.

## Vue d'ensemble

| Environnement | Usage | Emplacement | Infrastructure |
|---------------|-------|-------------|----------------|
| **Dev Local** | Développement sur machine locale | [infra/dev/](../infra/dev/) | Docker Compose (Keycloak + PostgreSQL) |
| **Staging** | Tests d'intégration CI/CD | [infra/staging/](../infra/staging/) | Docker Compose complet (App + Keycloak + PostgreSQL + nginx) |

---

## 🛠️ Environnement de développement local

### Description

Environnement minimal pour développer l'application rhDemo sur votre machine locale.

### Architecture

```
┌─────────────────────────────────────────────────┐
│  Machine locale (développement)                 │
│                                                  │
│  ┌──────────────────┐                           │
│  │  rhDemo App      │  ← Lancée via mvnw        │
│  │  (Spring Boot)   │                           │
│  └────────┬─────────┘                           │
│           │                                      │
│           │ connexions                           │
│           ├──────────────┐                       │
│           │              │                       │
│  ┌────────▼────────┐   ┌▼─────────────────┐    │
│  │  PostgreSQL     │   │  Keycloak        │    │
│  │  (Docker)       │   │  (Docker + H2)   │    │
│  │  Port: 5432     │   │  Port: 6090      │    │
│  └─────────────────┘   └──────────────────┘    │
└─────────────────────────────────────────────────┘
```

### Services Docker

| Service | Port | Base de données | Données persistées |
|---------|------|-----------------|-------------------|
| PostgreSQL | 5432 | dbrhdemo | ✅ Oui (volume Docker) |
| Keycloak | 6090 | H2 (en mémoire) | ❌ Non (redémarrage = perte) |

### Démarrage rapide

```bash
cd infra/dev

# Première utilisation: configurer l'environnement
cp .env.template .env

# Démarrer l'infrastructure
./start.sh

# Initialiser Keycloak (première fois)
cd ../../rhDemoInitKeycloak
# Créer application-dev.yml puis:
./mvnw spring-boot:run -Dspring-boot.run.profiles=dev

# Initialiser la base de données (première fois)
cd ../infra/dev
# Créer le schéma (tables + index)
docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < ../../pgschema.sql
# Insérer les données de test (optionnel)
docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < ../../pgdata.sql

# Configurer les secrets (première fois)
cd ../../secrets
cp secrets.yml.template secrets-rhdemo.yml
vim secrets-rhdemo.yml  # Éditer avec vos secrets

# Démarrer l'application rhDemo
cd ..
./mvnw spring-boot:run
```

### Arrêt

```bash
cd infra/dev

# Arrêter (conserve les données PostgreSQL)
./stop.sh

# Tout nettoyer (⚠️ perte des données)
./stop.sh --clean
```

### Documentation

Voir [infra/dev/README.md](../infra/dev/README.md) pour plus de détails.

---

## 🚀 Environnement staging (CI/CD)

### Description

Environnement complet utilisé par Jenkins pour les tests d'intégration automatisés.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Jenkins Pipeline (Docker)                                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Docker Compose Network (rhdemo-stagingkub-network)     │  │
│  │                                                       │  │
│  │  ┌─────────────┐   ┌──────────────┐   ┌──────────┐ │  │
│  │  │   nginx     │   │  rhDemo App  │   │ Keycloak │ │  │
│  │  │   (HTTPS)   ├──→│  (Container) │←──│          │ │  │
│  │  │  Port: 443  │   │  Port: 9000  │   │  :8080   │ │  │
│  │  └─────────────┘   └──────┬───────┘   └────┬─────┘ │  │
│  │                           │                  │       │  │
│  │                    ┌──────▼──────┐   ┌──────▼────┐ │  │
│  │                    │ PostgreSQL  │   │PostgreSQL │ │  │
│  │                    │   rhDemo    │   │ Keycloak  │ │  │
│  │                    └─────────────┘   └───────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Services Docker

| Service | Container | Port (externe) | Base de données | HTTPS |
|---------|-----------|----------------|-----------------|-------|
| nginx | rhdemo-stagingkub-nginx | 443 | - | ✅ Oui |
| rhDemo App | rhdemo-stagingkub-app | - | PostgreSQL | via nginx |
| Keycloak | keycloak-staging | - | PostgreSQL | via nginx |
| PostgreSQL (rhDemo) | rhdemo-stagingkub-db | - | rhdemo | - |
| PostgreSQL (Keycloak) | keycloak-staging-db | - | keycloak | - |

### Gestion des secrets

L'environnement staging utilise **SOPS/AGE** pour chiffrer les secrets.

#### Flux des secrets (principe du moindre privilège)

```
secrets-staging.yml (chiffré SOPS)
         ↓
   Jenkins déchiffre
         ↓
    ┌────────────────────────────┐
    │  env-vars.sh               │  ← Tous les secrets (infra)
    │  (utilisé par Jenkins)     │
    └────────────────────────────┘
         ↓
    ┌────────────────────────────┐
    │  secrets-rhdemo.yml        │  ← Secrets filtrés (rhDemo uniquement)
    │  (copié dans container)    │
    └────────────────────────────┘
         ↓
    Container rhdemo-stagingkub-app
    (accès limité aux secrets rhDemo)
```

#### Secrets accessibles par rhDemo

Le container `rhdemo-stagingkub-app` reçoit **uniquement** :
- ✅ Mot de passe PostgreSQL rhDemo
- ✅ Secret client Keycloak OAuth2
- ✅ Mot de passe H2 (tests)

**Exclus (sécurité)** :
- ❌ Mot de passe admin Keycloak
- ❌ Mot de passe PostgreSQL Keycloak
- ❌ Mots de passe utilisateurs de test
- ❌ URLs serveurs

Voir [SECURITY_LEAST_PRIVILEGE.md](SECURITY_LEAST_PRIVILEGE.md) pour plus de détails.

### Démarrage

L'environnement staging est démarré automatiquement par Jenkins via le [Jenkinsfile](../Jenkinsfile).

Étapes principales :
1. Déchiffrement SOPS des secrets
2. Extraction des secrets rhDemo (moindre privilège)
3. Build Maven de l'application
4. Build de l'image Docker (Paketo Buildpacks)
5. Démarrage Docker Compose
6. Injection du fichier secrets dans le container
7. Initialisation PostgreSQL (schéma + données)
8. Configuration Keycloak (realm + clients + utilisateurs)
9. Tests Selenium
10. Analyse SonarQube

### Documentation

Voir [infra/staging/README.md](../infra/staging/README.md) pour plus de détails (à créer si nécessaire).

---

## Comparaison des environnements

### Tableau récapitulatif

| Aspect | Dev Local | Staging |
|--------|-----------|---------|
| **Usage** | Développement manuel | Tests automatisés CI/CD |
| **Démarrage** | `./start.sh` | Jenkins pipeline |
| **App rhDemo** | Lancée via `mvnw` | Container Docker (Paketo) |
| **PostgreSQL** | 1 instance (port 5432) | 2 instances (rhDemo + Keycloak) |
| **Keycloak DB** | H2 (en mémoire) | PostgreSQL dédiée |
| **Keycloak port** | 6090 | 8080 (interne) |
| **HTTPS** | ❌ Non | ✅ Oui (nginx reverse proxy) |
| **Certificats SSL** | - | Auto-signés |
| **Réseau** | rhdemo-dev-network | rhdemo-stagingkub-network |
| **Secrets** | Fichier local non chiffré | SOPS/AGE chiffré |
| **Données persistées** | PostgreSQL uniquement | Tous les volumes Docker |
| **Tests Selenium** | Manuel | Automatiques (headless) |
| **Healthchecks** | - | ✅ Tous les services |

### Choix de l'environnement

**Utilisez Dev Local si** :
- ✅ Vous développez une nouvelle fonctionnalité
- ✅ Vous déboguez du code Java
- ✅ Vous voulez des retours rapides (hot reload)
- ✅ Vous n'avez pas besoin de HTTPS
- ✅ Vous voulez contrôler le démarrage/arrêt

**Utilisez Staging si** :
- ✅ Vous testez le pipeline CI/CD
- ✅ Vous validez une pull request
- ✅ Vous testez en conditions proches de la production
- ✅ Vous voulez exécuter les tests Selenium
- ✅ Vous voulez tester HTTPS et les certificats

---

## Configuration des secrets

### Installation SOPS/AGE (requis pour staging)

Pour déchiffrer les secrets de staging, vous devez installer SOPS et AGE.

**Voir le guide complet : [SOPS_SETUP.md](SOPS_SETUP.md)**

Résumé rapide :
```bash
# Linux - Installation manuelle
wget "https://github.com/getsops/sops/releases/download/v3.9.0/sops-v3.9.0.linux.amd64" -O /tmp/sops
chmod +x /tmp/sops && sudo mv /tmp/sops /usr/local/bin/sops

wget "https://github.com/FiloSottile/age/releases/download/v1.1.1/age-v1.1.1-linux-amd64.tar.gz" -O /tmp/age.tar.gz
tar xzf /tmp/age.tar.gz -C /tmp && sudo mv /tmp/age/age* /usr/local/bin/

# macOS - Via Homebrew
brew install sops age

# Générer une clé AGE
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
```

### Dev Local

Créer `secrets/secrets-rhdemo.yml` depuis le template :

```bash
cd secrets
cp secrets.yml.template secrets-rhdemo.yml
vim secrets-rhdemo.yml
```

Contenu minimal requis :
```yaml
rhdemo:
  datasource:
    password:
      pg: changeme  # Mot de passe PostgreSQL
      h2: password  # Mot de passe H2 (tests)
  client:
    registration:
      keycloak:
        client:
          secret: votre-secret-client-keycloak
```

### Staging

Les secrets sont gérés par Jenkins via `secrets/secrets-staging.yml` (chiffré SOPS).

Voir [REFACTOR_SECRETS_NAMING.md](REFACTOR_SECRETS_NAMING.md) pour la structure complète.

---

## Ports utilisés

### Dev Local

| Service | Port | Protocol | Accessible depuis |
|---------|------|----------|-------------------|
| PostgreSQL | 5432 | TCP | localhost |
| Keycloak | 6090 | HTTP | localhost |
| rhDemo App | 8080 | HTTP | localhost (si lancée) |

### Staging

| Service | Port externe | Port interne | Protocol | Accessible depuis |
|---------|--------------|--------------|----------|-------------------|
| nginx | 443 | 443 | HTTPS | localhost (host Docker) |
| rhDemo App | - | 9000 | HTTP | réseau Docker uniquement |
| Keycloak | - | 8080 | HTTP | réseau Docker uniquement |
| PostgreSQL rhDemo | - | 5432 | TCP | réseau Docker uniquement |
| PostgreSQL Keycloak | - | 5432 | TCP | réseau Docker uniquement |

---

## Références

- [SOPS_SETUP.md](SOPS_SETUP.md) - Installation et configuration SOPS/AGE
- [SECURITY_LEAST_PRIVILEGE.md](SECURITY_LEAST_PRIVILEGE.md) - Gestion sécurisée des secrets
- [REFACTOR_SECRETS_NAMING.md](REFACTOR_SECRETS_NAMING.md) - Nomenclature des fichiers secrets
- [infra/dev/README.md](../infra/dev/README.md) - Documentation environnement dev
- [Jenkinsfile](../Jenkinsfile) - Pipeline CI/CD staging
