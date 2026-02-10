# 🚀 Jenkins CI/CD pour RHDemo

Infrastructure Jenkins complète avec architecture master/agent dédiée et tous les outils nécessaires pour exécuter les pipelines CI/CD RHDemo.


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

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          PLATEFORME CI/CD RHDEMO                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌───────────────────────────┐     ┌──────────────────────────────────────────────┐ │
│  │  JENKINS CONTROLLER       │     │  JENKINS AGENT (builder)                     │ │
│  │  (Port 8080, 50000)       │◄───►│  rhdemo-jenkins-agent                       │ │
│  │  rhdemo-jenkins           │     │                                              │ │
│  │                           │     │  Outils de build :                           │ │
│  │  Pilotage uniquement :    │     │  • JDK 25 (Eclipse Temurin)                  │ │
│  │  • numExecutors: 0        │     │  • Maven 3.9.12                              │ │
│  │  • Orchestration pipelines│     │  • Docker CLI + Docker Compose               │ │
│  │  • Interface web          │     │  • Node.js/npm (build frontend)              │ │
│  │  • Gestion credentials    │     │  • Firefox ESR + Xvfb (Selenium headless)    │ │
│  │  • JCasC                  │     │  • SOPS, yq (secrets & YAML)                 │ │
│  │                           │     │  • Trivy (scan CVE images Docker)            │ │
│  │  Plugins :                │     │  • kubectl, Helm (déploiement K8s)           │ │
│  │  • Pipeline & Git         │     │  • Cosign (signature images)                 │ │
│  │  • SonarQube Scanner      │     │                                              │ │
│  │  • Docker Workflow        │     │  Connexion : WebSocket (JNLP)                │ │
│  │  • Coverage               │     │  Docker-in-Docker via socket monté            │ │
│  │  • OWASP Dep-Check        │     └──────────────────────────────────────────────┘ │
│  │  • Email, BlueOcean       │                                                      │
│  └───────────────────────────┘     ┌──────────────────────────┐                     │
│                                    │      SONARQUBE           │                     │
│                                    │     (Port 9020)          │                     │
│                                    │                          │                     │
│                                    │ • Community Edition      │                     │
│                                    │ • Analyse qualité code   │                     │
│                                    │ • Couverture tests       │                     │
│                                    │ • Security hotspots      │                     │
│                                    └──────────┬───────────────┘                     │
│                                               │                                     │
│                                               ▼                                     │
│                                    ┌──────────────────────────┐                     │
│                                    │   PostgreSQL 16          │                     │
│                                    │   (sonarqube-db)         │                     │
│                                    │ • Base de données        │                     │
│                                    │   SonarQube              │                     │
│                                    └──────────────────────────┘                     │
│                                                                                     │
│  Autres services :                                                                  │
│  • kind-registry:5000 (Docker Registry local HTTPS)                                 │
│  • OWASP ZAP (CI/CD uniquement, docker-compose.zap.yml)                             │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   Réseau Docker Bridge        │
                    │   rhdemo-jenkins-network      │
                    └───────────┬───────────────────┘
                                │
                                │ Connexion dynamique (agent)
                                ▼
                    ┌───────────────────────────────┐
                    │   Réseau Staging (externe)    │
                    │   rhdemo-ephemere-network     │
                    │                               │
                    │ • Nginx (443)                 │
                    │ • RHDemo App (9000)           │
                    │ • Keycloak (8080)             │
                    │ • PostgreSQL (5432)           │
                    └───────────────────────────────┘
```

### Volumes persistants

| Volume | Usage | Taille estimée |
|--------|-------|----------------|
| `rhdemo-jenkins-home` | Configuration et jobs Jenkins (controller) | ~2 GB |
| `rhdemo-jenkins-agent-workspace` | Workspace de l'agent (builds) | ~2 GB |
| `rhdemo-maven-repository` | Cache Maven (.m2) sur l'agent | ~1 GB |
| `rhdemo-sonarqube-data` | Données SonarQube | ~500 MB |
| `rhdemo-sonarqube-extensions` | Plugins SonarQube | ~100 MB |
| `rhdemo-sonarqube-logs` | Logs SonarQube | ~50 MB |
| `rhdemo-sonarqube-db` | Base PostgreSQL SonarQube | ~200 MB |
| `kind-registry-data` | Images Docker locales | Variable |
| `rhdemo-jenkins-zap-sessions` | Sessions ZAP (réutilisation entre builds) | ~50 MB |
| `rhdemo-jenkins-zap-reports` | Rapports ZAP HTML/JSON | ~100 MB |

**Note** : Le volume `kind-registry-data` stocke les images du registry Docker local nommé `kind-registry`. Ce nom est standardisé pour garantir la résolution DNS dans les clusters Kubernetes (KinD).

### Services inclus

| Service | Description | Port | Fichier |
|---------|-------------|------|---------|
| `jenkins` | Controller Jenkins (pilotage uniquement) | 8080, 50000 | docker-compose.yml |
| `jenkins-agent` | Agent de build (exécute tous les pipelines) | - | docker-compose.yml |
| `sonarqube` | Analyse qualité du code | 9020 | docker-compose.yml |
| `sonarqube-db` | Base de données PostgreSQL pour SonarQube | - | docker-compose.yml |
| `owasp-zap` | Proxy de sécurité pour tests Selenium (CI/CD) | 8090 | docker-compose.zap.yml |
| `registry` | Docker Registry local (HTTPS) | 5000 | docker-compose.yml |

### 🤖 Architecture Master/Agent

Le master Jenkins (controller) ne fait que du **pilotage** : orchestration des pipelines, gestion des credentials, interface web et JCasC. Tous les builds sont délégués à l'agent dédié **"builder"** pour des raisons de sécurité (réduction de la surface d'attaque du master).

**Controller (`Dockerfile.jenkins`)** :

- `numExecutors: 0` — n'exécute aucun build
- `mode: EXCLUSIVE` — ne peut pas recevoir de jobs
- Contient uniquement les plugins et la configuration JCasC

**Agent "builder" (`Dockerfile.agent`)** :

- Image personnalisée basée sur `jenkins/inbound-agent:latest-jdk21`
- Connexion WebSocket (JNLP) au controller
- `numExecutors: 2` — exécute 2 jobs en parallèle
- Contient tous les outils de build :
  - JDK 25 (Eclipse Temurin) + Maven 3.9.12
  - Docker CLI + Docker Compose (DinD via socket)
  - Firefox ESR + Xvfb (tests Selenium headless)
  - SOPS, yq (secrets et parsing YAML)
  - Trivy (scan CVE images Docker)
  - kubectl, Helm (déploiement Kubernetes)
  - Cosign (signature d'images)
  - Node.js/npm (build frontend)

**Configuration du secret agent :**

1. Démarrer le master seul : `docker-compose up -d jenkins`
2. Aller dans Jenkins > Manage Jenkins > Nodes > builder
3. Copier le secret affiché
4. Mettre à jour `JENKINS_SECRET` dans `.env`
5. Démarrer l'agent : `docker-compose up -d jenkins-agent`

## ⚡ Installation rapide

### 0. Prérequis : Certificats TLS pour le registry Docker

Le registry Docker fonctionne en **HTTPS** avec un certificat auto-signé.

```bash
cd rhDemo/infra/jenkins-docker

# Générer les certificats (une seule fois)
./init-registry-certs.sh

# Configurer Docker daemon pour faire confiance au certificat
sudo mkdir -p /etc/docker/certs.d/localhost:5000
sudo cp certs/registry/registry.crt /etc/docker/certs.d/localhost:5000/ca.crt
sudo systemctl restart docker
```

> **Note** : Le script `start-jenkins.sh` vérifie automatiquement ces prérequis et vous guide si nécessaire.

### 1. Démarrage en une commande

```bash
cd rhDemo/infra/jenkins-docker
./start-jenkins.sh
```

Le script va :
- ✅ Vérifier les prérequis
- ✅ Vérifier/générer les certificats TLS du registry
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

```text
jenkins-docker/
├── docker-compose.yml          # Configuration des services (controller + agent)
├── Dockerfile.jenkins          # Image controller (pilotage uniquement)
├── Dockerfile.agent            # Image agent (tous les outils de build)
├── plugins.txt                 # Liste des plugins à installer
├── jenkins-casc.yaml          # Configuration as Code (JCasC)
├── .env.example               # Template des variables d'environnement
├── .env                       # Vos variables (à créer, non commité)
├── start-jenkins.sh           # Script de démarrage
├── init-registry-certs.sh     # Génération certificats TLS registry
└── certs/registry/            # Certificats TLS (non commités, à générer)
    ├── registry.crt           # Certificat public
    └── registry.key           # Clé privée
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

   # Email notifications (optionnel)
   SMTP_USER=votre-email@gmail.com
   SMTP_PASSWORD=votre-mot-de-passe-app
   ```

### Configuration Jenkins as Code (JCasC)

Le fichier `jenkins-casc.yaml` configure automatiquement :
- ✅ Utilisateur admin
- ✅ Controller en mode pilotage (`numExecutors: 0`, `mode: EXCLUSIVE`)
- ✅ Agent permanent "builder" (2 executors, WebSocket JNLP)
- ✅ Outils (JDK25, Maven3, Git, OWASP Dependency-Check)
- ✅ Intégrations (SonarQube)
- ✅ Jobs pipeline (CI + CD)

Pour modifier la configuration :
```bash
nano jenkins-casc.yaml
docker-compose restart jenkins
```
### Configuration de SOPS et des credentials dans Jenkins

(Obligatoire pour pouvoir lancer le pipeline Jenkinsfile-CI)
>>> Voir le fichier QUICKSTART.md


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

# Controller uniquement
docker-compose logs -f jenkins

# Agent de build
docker-compose logs -f jenkins-agent

# Dernières 100 lignes
docker-compose logs --tail=100 jenkins-agent
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

### Accéder aux conteneurs

```bash
# Controller (pilotage)
docker-compose exec jenkins bash

# Agent (builds)
docker-compose exec jenkins-agent bash
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
- Coverage (remplace JaCoCo, supporte JaCoCo parser)
- Warnings NG
- Checkstyle, PMD, FindBugs

### Tests
- JUnit
- TestNG
- HTML Publisher
- Performance Plugin

### Sécurité
- OWASP Dependency-Check Jenkins Plugin
  - Utilisation : Publication des rapports uniquement (dependencyCheckPublisher)
  - Exécution : Via plugin Maven 12.1.9 (support CVSS v4.0)
  - Cache NVD : Local dans target/dependency-check-data/

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

## 🔨 Création des pipelines CI et CD pour RHDemo

Les pipelines sont créés automatiquement au démarrage dans la section `jobs:` dans `jenkins-casc.yaml`.


## 🐳 Docker-in-Docker (DinD)

L'**agent Jenkins** (pas le controller) peut exécuter des commandes Docker et docker-compose grâce au montage du socket Docker :

```yaml
# Dans le service jenkins-agent
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  - /usr/bin/docker:/usr/bin/docker
```

### Vérifier Docker dans l'agent

```bash
docker-compose exec jenkins-agent docker --version
docker-compose exec jenkins-agent docker-compose --version
docker-compose exec jenkins-agent docker ps
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

### Docker Registry local (HTTPS)

Le registry Docker local (`kind-registry`) stocke les images Docker construites par le pipeline CI. Il est configuré en **HTTPS** avec un certificat auto-signé pour sécuriser les communications.

**Configuration initiale :**

```bash
cd rhDemo/infra/jenkins-docker

# 1. Générer les certificats TLS (une seule fois)
./init-registry-certs.sh

# 2. Configurer Docker daemon pour faire confiance au certificat
sudo mkdir -p /etc/docker/certs.d/localhost:5000
sudo cp certs/registry/registry.crt /etc/docker/certs.d/localhost:5000/ca.crt
sudo systemctl restart docker
```

**Fichiers générés :**
- `certs/registry/registry.crt` : Certificat public (valide 10 ans)
- `certs/registry/registry.key` : Clé privée (ne pas commiter !)

**SANs (Subject Alternative Names) :**
- `localhost` : accès depuis l'hôte
- `kind-registry` : accès depuis les conteneurs Docker
- `127.0.0.1` : accès IP

**Utilisation :**
```bash
# Depuis l'hôte (via Docker daemon)
docker push localhost:5000/mon-image:tag

# Depuis un conteneur (appels HTTP directs)
curl --cacert /etc/ssl/certs/registry.crt https://kind-registry:5000/v2/_catalog
```

**Volume persistant :**
- `kind-registry-data` : Images Docker stockées

**Dépannage :**
```bash
# Vérifier que le registry répond en HTTPS
curl -k https://localhost:5000/v2/

# Vérifier le certificat
openssl s_client -connect localhost:5000 -servername localhost < /dev/null 2>/dev/null | openssl x509 -noout -dates
```

### Email

Configuration dans `.env` :
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=votre-app-password
```

### OWASP Dependency-Check

Le plugin OWASP Dependency-Check est préconfiguré pour analyser les vulnérabilités des dépendances.

**Configuration automatique :**
- ✅ Plugin Maven OWASP : Version 12.1.9 (configuré dans pom.xml)
- ✅ Support CVSS v4.0
- ✅ Cache NVD local : `rhDemo/target/dependency-check-data/`
- ✅ Exécution : `./mvnw org.owasp:dependency-check-maven:check`

**Configuration de la clé API NVD (recommandé) :**

Pour éviter les limitations de taux (rate limiting) de l'API NVD :

1. **Obtenir une clé API gratuite :**
   - Aller sur https://nvd.nist.gov/developers/request-an-api-key
   - Remplir le formulaire avec votre email professionnel
   - Confirmer l'email
   - Vous recevrez une clé au format : `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
   - ⚠️ La clé peut prendre 2-24 heures pour être activée

2. **Créer le credential dans Jenkins :**
   - Aller dans **Manage Jenkins** → **Manage Credentials**
   - Cliquer sur **(global)** sous **Stores scoped to Jenkins**
   - **Add Credentials**
   - Remplir :
     - **Kind** : Secret text
     - **Scope** : Global
     - **Secret** : Coller votre clé API NVD (vérifier qu'il n'y a pas d'espaces)
     - **ID** : `nvd-api-key`
     - **Description** : `NVD API Key for OWASP Dependency-Check`
   - **Create**

3. **Tester la clé** avant de relancer Jenkins :
   ```bash
   curl -H "apiKey: YOUR_API_KEY" \
     "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=1"
   ```
   Si la clé est valide, vous verrez un JSON avec `"resultsPerPage": 1`

4. **Relancer un build** pour vérifier que la clé est bien prise en compte (voir logs Jenkins)

**Sans clé API :**
- Limite : 10 requêtes / 30 secondes
- Risque de timeout au premier scan (téléchargement complet NVD ~2-3 GB)
- ✅ Fonctionne avec le cache local si déjà téléchargé

**Avec clé API :**
- Limite : 50 requêtes / 30 secondes
- Scans plus rapides et fiables
- Données NVD à jour

**Dépannage clé invalide :** Voir [../../docs/TEST_NVD_API_KEY.md](../../docs/TEST_NVD_API_KEY.md)

### OWASP ZAP - Proxy de sécurité pour tests Selenium

OWASP ZAP (Zed Attack Proxy) est un proxy de sécurité qui intercepte le trafic HTTP/HTTPS entre les tests Selenium et l'application RHDemo pour détecter automatiquement les vulnérabilités web.

**Architecture :**
```text
Agent builder (Firefox) → ZAP Proxy (8090) → Nginx (rhdemo-ephemere) → RHDemo App
                                 ↓
                          Analyse passive
                          + Spider
                          + Active Scan
                                 ↓
                          Rapport HTML/JSON
```

**Démarrage automatique :**

ZAP démarre automatiquement lors du stage `🔒 Démarrage OWASP ZAP Proxy` dans le Jenkinsfile-CI si le paramètre `RUN_SELENIUM_TESTS` = `true`

**Architecture réseau dynamique :**

L'agent Jenkins et ZAP utilisent une connexion réseau dynamique gérée par le Jenkinsfile :

**Agent Jenkins (builder) :**
1. **Réseau permanent** : `rhdemo-jenkins-network`
   - Défini dans docker-compose.yml
   - Communication avec le controller, SonarQube, Registry

2. **Réseau temporaire** : `rhdemo-ephemere-network`
   - L'agent se connecte dynamiquement via `$(hostname)`
   - Permet l'accès aux alias DNS ephemere pour orchestration
   - Déconnecté après les tests Selenium (bloc `post: always`)

**ZAP :**
1. **Réseau permanent** : `rhdemo-jenkins-network`
   - Défini dans docker-compose.zap.yml
   - Permet la communication API avec Jenkins

2. **Réseau temporaire** : `rhdemo-ephemere-network`
   - Connecté lors du stage `🔒 Démarrage OWASP ZAP`
   - Permet l'accès aux alias DNS (`rhdemo.ephemere.local`, `keycloak.ephemere.local`)
   - Déconnecté après les tests Selenium (bloc `post: always`)

**Cycle de vie réseau :**
```text
Stage "Déploiement"        : Agent connecté à rhdemo-ephemere-network
Stage "Démarrage ZAP"      : ZAP connecté à rhdemo-ephemere-network
Stage "Tests Selenium"     : Agent + ZAP ont accès au réseau ephemere
Post "Tests Selenium"      : ZAP déconnecté + Agent déconnecté
```

Cette approche offre :
- ✅ Accès DNS aux services ephemere uniquement durant le déploiement/tests
- ✅ Isolation réseau stricte en dehors des phases actives
- ✅ Sécurité renforcée (principe du moindre privilège)
- ✅ Traçabilité complète du cycle de connexion/déconnexion

**Démarrage manuel :**

```bash
cd infra/jenkins-docker

# Démarrer ZAP
docker-compose -f docker-compose.yml \
               -f docker-compose.zap.yml \
               up -d owasp-zap

# Vérifier l'état
docker logs rhdemo-jenkins-zap

# Tester l'API ZAP
docker exec rhdemo-jenkins-zap curl -s http://localhost:8090/JSON/core/view/version/?apikey=changeme
```

**Configuration Selenium :**

Les tests Selenium détectent automatiquement le proxy ZAP via les variables d'environnement :
- `ZAP_PROXY_HOST=owasp-zap`
- `ZAP_PROXY_PORT=8090`

Ces variables sont configurées dans le Jenkinsfile-CI (stage `🌐 Tests Selenium IHM`).

**Rapports ZAP :**

Les rapports sont stockés dans le volume `rhdemo-jenkins-zap-reports` et peuvent être archivés par Jenkins pour consultation ultérieure.

**Arrêt de ZAP :**

```bash
# Arrêter ZAP
docker-compose -f docker-compose.yml \
               -f docker-compose.zap.yml \
               stop owasp-zap

# Supprimer le container
docker-compose -f docker-compose.yml \
               -f docker-compose.zap.yml \
               rm -f owasp-zap
```

**Volumes ZAP :**
- `rhdemo-jenkins-zap-sessions` : Sessions ZAP réutilisables entre builds (~50 MB)
- `rhdemo-jenkins-zap-reports` : Rapports générés (HTML/JSON) (~100 MB)

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

# Doit être accessible au groupe docker (984)
sudo chmod 666 /var/run/docker.sock
```

**Dans le conteneur agent :**
```bash
docker-compose exec jenkins-agent docker ps
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

### L'agent Jenkins se relance en boucle

**Symptôme :** Logs montrant "Secret is required for inbound agents"

**Cause :** Le secret de l'agent n'est pas configuré dans `.env`.

**Solution :**

1. Vérifier que le master est démarré et sain : `docker-compose ps jenkins`
2. Aller dans Jenkins > Manage Jenkins > Nodes > builder
3. Copier le secret affiché sur la page du noeud
4. Mettre à jour `JENKINS_SECRET=<secret>` dans `.env`
5. Redémarrer l'agent : `docker-compose up -d jenkins-agent`

**Vérification :**
```bash
# Logs de l'agent
docker-compose logs -f jenkins-agent

# Doit afficher : "INFO: Connected"
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
