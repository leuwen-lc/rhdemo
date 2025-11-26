# 🚀 Jenkins CI/CD pour RHDemo

Infrastructure Jenkins complète avec support Docker-in-Docker et tous les plugins nécessaires pour exécuter le pipeline RHDemo.

## 📋 Table des matières

- [Prérequis](#prérequis)
- [Architecture](#architecture)
- [Installation rapide](#installation-rapide)
- [Configuration détaillée](#configuration-détaillée)
- [Utilisation](#utilisation)
- [Plugins installés](#plugins-installés)
- [Dépannage](#dépannage)

## 🔧 Prérequis

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4 GB RAM minimum (8 GB recommandé)
- 20 GB d'espace disque

### Vérification des prérequis

```bash
docker --version
docker-compose --version
docker info
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PLATEFORME CI/CD RHDEMO                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────┐      ┌──────────────────────────┐       │
│  │       JENKINS            │      │      SONARQUBE           │       │
│  │   (Port 8080, 50000)     │◄────►│     (Port 9020)          │       │
│  │                          │      │                          │       │
│  │ • JDK 21                 │      │ • Community Edition 10   │       │
│  │ • Maven 3.9.6            │      │ • Analyse qualité code   │       │
│  │ • Docker CLI             │      │ • Couverture tests       │       │
│  │ • Node.js/npm            │      │ • Security hotspots      │       │
│  │                          │      │ • Code smells            │       │
│  │ Plugins:                 │      │                          │       │
│  │ • Pipeline & Git         │      └──────────┬───────────────┘       │
│  │ • SonarQube Scanner      │                 │                       │
│  │ • Docker Workflow        │                 ▼                       │
│  │ • JaCoCo                 │      ┌──────────────────────────┐       │
│  │ • Slack & Email          │      │   PostgreSQL 16          │       │
│  │ • BlueOcean UI           │      │   (sonarqube-db)         │       │
│  └──────────┬───────────────┘      │                          │       │
│             │                      │ • Base de données        │       │
│             │                      │   SonarQube              │       │
│             │                      │ • Volume persistant      │       │
│             ▼                      └──────────────────────────┘       │
│  ┌──────────────────────────┐                                        │
│  │    DOCKER SOCKET         │                                        │
│  │  /var/run/docker.sock    │                                        │
│  │                          │                                        │
│  │ • Docker-in-Docker (DinD)│                                        │
│  │ • Lance conteneurs       │                                        │
│  │ • Build images           │                                        │
│  │ • Deploy staging         │                                        │
│  └──────────────────────────┘                                        │
│                                                                       │
│  Services optionnels:                                                │
│  • jenkins-agent (agents distribués)                                 │
│  • registry:5000 (Docker Registry local)                             │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   Réseau Docker Bridge        │
                    │   rhdemo-jenkins-network      │
                    └───────────────────────────────┘
```

### Volumes persistants

| Volume | Usage | Taille estimée |
|--------|-------|----------------|
| `rhdemo-jenkins-home` | Configuration et jobs Jenkins | ~2 GB |
| `rhdemo-maven-repository` | Cache Maven (.m2) | ~1 GB |
| `rhdemo-sonarqube-data` | Données SonarQube | ~500 MB |
| `rhdemo-sonarqube-extensions` | Plugins SonarQube | ~100 MB |
| `rhdemo-sonarqube-logs` | Logs SonarQube | ~50 MB |
| `rhdemo-sonarqube-db` | Base PostgreSQL SonarQube | ~200 MB |
| `rhdemo-docker-registry` | Images Docker locales | Variable |

### Services inclus

| Service | Description | Port |
|---------|-------------|------|
| `jenkins` | Serveur Jenkins principal | 8080, 50000 |
| `sonarqube` | Analyse qualité du code | 9020 |
| `sonarqube-db` | Base de données PostgreSQL pour SonarQube | - |
| `jenkins-agent` | Agent Jenkins (optionnel) | - |
| `registry` | Docker Registry local | 5000 |
| `nginx` | Reverse proxy (optionnel) | 80, 443 |

## ⚡ Installation rapide

### 1. Démarrage en une commande

```bash
cd infra
./start-jenkins.sh
```

Le script va :
- ✅ Vérifier les prérequis
- ✅ Créer le fichier `.env` depuis `.env.example`
- ✅ Builder l'image Jenkins personnalisée
- ✅ Démarrer tous les services
- ✅ Attendre que Jenkins soit prêt

### 2. Accès à Jenkins

Ouvrez votre navigateur : **http://localhost:8080**

**Identifiants par défaut :**
- Utilisateur : `admin`
- Mot de passe : `xxxxxxx` (défini dans `.env`)

⚠️ **IMPORTANT** : Mettez un mot de passe fort !

## 📝 Configuration détaillée

### Fichiers de configuration

```
infra/
├── docker-compose.yml          # Configuration des services
├── Dockerfile.jenkins          # Image Jenkins personnalisée
├── plugins.txt                 # Liste des plugins à installer
├── jenkins-casc.yaml          # Configuration as Code (JCasC)
├── .env.example               # Template des variables d'environnement
├── .env                       # Vos variables (à créer, non commité)
├── start-jenkins.sh           # Script de démarrage
└── README.md                  # Ce fichier
```

### Configuration des secrets

1. **Copier le fichier d'exemple :**
   ```bash
   cp .env.example .env
   ```

2. **Éditer `.env` avec vos valeurs :**
   ```bash
   nano .env
   ```

3. **Variables importantes à configurer :**
   ```env
   # Admin Jenkins
   JENKINS_ADMIN_PASSWORD=votre-mot-de-passe-securise
   
   # Serveurs
   STAGING_SERVER_URL=staging.exemple.com
   PROD_SERVER_URL=prod.exemple.com
   
   # GitHub
   GITHUB_TOKEN=ghp_votre_token_github
   ```

### Configuration Jenkins as Code (JCasC)

Le fichier `jenkins-casc.yaml` configure automatiquement :
- ✅ Utilisateur admin
- ✅ Outils (JDK21, Maven3)
- ✅ Credentials
- ✅ Intégrations (SonarQube, Slack)
- ✅ Jobs pipeline

Pour modifier la configuration :
```bash
nano jenkins-casc.yaml
docker-compose restart jenkins
```

## 🎯 Utilisation

### Démarrer Jenkins

```bash
cd infra
docker-compose up -d
```

### Voir les logs

```bash
# Tous les services
docker-compose logs -f

# Jenkins uniquement
docker-compose logs -f jenkins

# Dernières 100 lignes
docker-compose logs --tail=100 jenkins
```

### Arrêter Jenkins

```bash
# Arrêt simple
docker-compose stop

# Arrêt et suppression des conteneurs
docker-compose down

# Tout supprimer (y compris les volumes)
docker-compose down -v
```

### Redémarrer Jenkins

```bash
docker-compose restart jenkins
```

### Accéder au conteneur Jenkins

```bash
docker-compose exec jenkins bash
```

## 🔌 Plugins installés

<details>
<summary><b>Voir la liste complète des plugins (cliquez pour développer)</b></summary>

### Gestion du code source
- Git, GitHub, GitLab, Bitbucket

### Build & Outils Java
- Maven Plugin
- Pipeline Maven
- JDK Tool

### Qualité du code
- SonarQube Scanner
- JaCoCo
- Warnings NG
- Checkstyle, PMD, FindBugs

### Tests
- JUnit
- TestNG
- HTML Publisher
- Performance Plugin

### Sécurité
- OWASP Dependency Check
- Aqua Security Scanner

### Docker & Kubernetes
- Docker Workflow
- Docker Plugin
- Kubernetes

### Notifications
- Slack
- Email Extension
- Mailer

### UI & Reporting
- Blue Ocean
- Dashboard View
- Build Monitor
- Pipeline Graph View
- AnsiColor

### Configuration as Code
- Configuration as Code (JCasC)
- Job DSL

</details>

## 🔨 Créer un pipeline pour RHDemo

### Méthode 1 : Via l'interface Web

1. Aller sur http://localhost:8080
2. Cliquer sur **"New Item"**
3. Nom : `rhdemo-api`
4. Type : **"Pipeline"**
5. Configuration :
   - **Pipeline** → **Definition** : Pipeline script from SCM
   - **SCM** : Git
   - **Repository URL** : `https://github.com/leuwen-lc/rhdemo.git`
   - **Script Path** : `Jenkinsfile`
6. **Save**

### Méthode 2 : Automatique via JCasC

Le pipeline est créé automatiquement au démarrage si vous décommentez la section `jobs:` dans `jenkins-casc.yaml`.

### Lancer un build

1. Aller sur le job `rhdemo-api`
2. Cliquer sur **"Build with Parameters"**
3. Configurer :
   - **DEPLOY_ENV** : `none`, `staging`, ou `production`
   - **RUN_SELENIUM_TESTS** : `true`/`false`
   - **RUN_SONAR** : `true`/`false`
4. Cliquer sur **"Build"**

## 🐳 Docker-in-Docker (DinD)

Jenkins peut exécuter des commandes Docker et docker-compose grâce au montage du socket Docker :

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  - /usr/bin/docker:/usr/bin/docker
```

### Vérifier Docker dans Jenkins

```bash
docker-compose exec jenkins docker --version
docker-compose exec jenkins docker-compose --version
docker-compose exec jenkins docker ps
```

## 📊 Intégrations

### SonarQube

SonarQube est inclus dans le docker-compose et démarre automatiquement avec Jenkins.

**Accès à SonarQube :**
- URL : http://localhost:9020
- Identifiants par défaut : `admin` / `admin` (changez-les au premier login)

**Configuration initiale :**
1. Connectez-vous à http://localhost:9020
2. Changez le mot de passe admin
3. Allez dans **Administration** → **Security** → **Users**
4. Créez un token pour Jenkins : **My Account** → **Security** → **Generate Token**
5. Ajoutez le token dans `.env` :
   ```env
   SONAR_TOKEN=votre-token-sonar-genere
   ```
6. Redémarrez Jenkins : `docker compose restart jenkins`

**Services SonarQube :**
- `sonarqube` : Serveur SonarQube Community Edition 10
- `sonarqube-db` : Base de données PostgreSQL 16 dédiée

**Volumes persistants :**
- `rhdemo-sonarqube-data` : Données SonarQube
- `rhdemo-sonarqube-extensions` : Plugins SonarQube
- `rhdemo-sonarqube-logs` : Logs SonarQube
- `rhdemo-sonarqube-db` : Base de données PostgreSQL

### Slack

Configuration dans `.env` :
```env
SLACK_TEAM=votre-team
SLACK_TOKEN=xoxb-votre-token
SLACK_CHANNEL=#rhdemo-ci
```

### Email

Configuration dans `.env` :
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=votre-app-password
```

## 🔧 Dépannage

### Jenkins ne démarre pas

**Vérifier les logs :**
```bash
docker-compose logs jenkins
```

**Problèmes courants :**

1. **Port 8080 déjà utilisé**
   ```bash
   # Vérifier ce qui utilise le port
   sudo lsof -i :8080
   
   # Changer le port dans docker-compose.yml
   ports:
     - "8081:8080"  # Utiliser 8081 au lieu de 8080
   ```

2. **Permissions Docker**
   ```bash
   # Ajouter votre utilisateur au groupe docker
   sudo usermod -aG docker $USER
   
   # Redémarrer la session
   newgrp docker
   ```

3. **Mémoire insuffisante**
   
   Augmenter dans `docker-compose.yml` :
   ```yaml
   environment:
     - JAVA_OPTS=-Xmx4g -Xms1g
   ```

### Plugins ne s'installent pas

**Solution :**
```bash
# Reconstruire l'image
docker-compose build --no-cache jenkins

# Redémarrer
docker-compose up -d --force-recreate jenkins
```

### Docker-in-Docker ne fonctionne pas

**Vérifier les permissions :**
```bash
# Sur l'hôte
ls -la /var/run/docker.sock

# Doit être accessible au groupe docker (999)
sudo chmod 666 /var/run/docker.sock
```

**Dans le conteneur :**
```bash
docker-compose exec jenkins docker ps
```

### Réinitialiser complètement Jenkins

```bash
# Arrêter et supprimer TOUT (⚠️ PERTE DE DONNÉES)
docker-compose down -v

# Supprimer les volumes
docker volume rm rhdemo-jenkins-home
docker volume rm rhdemo-maven-repository

# Redémarrer
./start-jenkins.sh
```

## 📈 Monitoring

### Healthcheck

```bash
# Vérifier la santé des conteneurs
docker-compose ps

# Healthcheck manuel
curl http://localhost:8080/login
```

### Métriques Prometheus

Jenkins expose des métriques Prometheus sur :
```
http://localhost:8080/prometheus
```

### Espace disque

```bash
# Vérifier l'espace des volumes
docker system df -v

# Nettoyer les anciennes images/conteneurs
docker system prune -a
```

## 🔒 Sécurité

### Recommandations

1. **Changer le mot de passe admin** immédiatement
2. **Utiliser HTTPS** en production (via nginx)
3. **Limiter l'accès réseau** aux ports Jenkins
4. **Configurer l'authentification** LDAP/OAuth
5. **Activer les audits** (Job Config History plugin)
6. **Sauvegarder régulièrement** le volume `jenkins_home`

### Backup

```bash
# Backup manuel
docker run --rm \
  -v rhdemo-jenkins-home:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/jenkins-backup-$(date +%Y%m%d).tar.gz -C /data .

# Restauration
docker run --rm \
  -v rhdemo-jenkins-home:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/jenkins-backup-20250107.tar.gz -C /data
```

## 📚 Ressources

- [Documentation Jenkins](https://www.jenkins.io/doc/)
- [Jenkins Configuration as Code](https://github.com/jenkinsci/configuration-as-code-plugin)
- [Pipeline Syntax](https://www.jenkins.io/doc/book/pipeline/syntax/)
- [Jenkinsfile du projet](../Jenkinsfile)

## 🆘 Support

En cas de problème :

1. Vérifier les logs : `docker-compose logs -f jenkins`
2. Consulter la section [Dépannage](#dépannage)
3. Vérifier la configuration dans `.env`
4. Redémarrer : `docker-compose restart jenkins`

## 📝 Licence

Ce setup Jenkins est fourni pour le projet RHDemo.
