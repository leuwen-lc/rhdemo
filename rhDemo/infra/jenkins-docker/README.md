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
│  │  JENKINS CONTROLLER       │     │  DOCKER SOCKET PROXY                         │ │
│  │  (Port 8080, 50000)       │────►│  rhdemo-docker-socket-proxy                 │ │
│  │  rhdemo-jenkins           │     │  Port TCP: 2375 (API filtrée)               │ │
│  │                           │     │                                              │ │
│  │  Pilotage uniquement :    │     │  Endpoints autorisés :                       │ │
│  │  • numExecutors: 0        │     │  • POST /containers/create (créer agent)     │ │
│  │  • Orchestration pipelines│     │  • POST /containers/{id}/start              │ │
│  │  • Interface web          │     │  • POST /containers/{id}/stop               │ │
│  │  • Gestion credentials    │     │  • DELETE /containers/{id}                  │ │
│  │  • JCasC + Docker Cloud   │     │  Tout le reste : bloqué                     │ │
│  │                           │     └──────────────────────────────────────────────┘ │
│  └───────────────────────────┘                    │ crée/détruit                    │
│                                                   ▼                                 │
│                                    ┌──────────────────────────────────────────────┐ │
│                                    │  AGENTS ÉPHÉMÈRES (Docker Cloud)             │ │
│                                    │  Image: rhdemo-jenkins-agent:latest          │ │
│                                    │  Créés à la demande, détruits après le build │ │
│                                    │                                              │ │
│                                    │  Outils de build :                           │ │
│                                    │  • JDK 25 (Eclipse Temurin) + Maven 3.9.12  │ │
│                                    │  • Docker CLI + Docker Compose (socket hôte) │ │
│                                    │  • Node.js/npm (build frontend)              │ │
│                                    │  • Firefox ESR + Xvfb (Selenium headless)    │ │
│                                    │  • SOPS, yq (secrets & YAML)                 │ │
│                                    │  • Trivy, kubectl, Helm, Cosign              │ │
│                                    └──────────────────────────────────────────────┘ │
│                                                                                     │
│  ┌──────────────────────────┐                                                       │
│  │      SONARQUBE           │                                                       │
│  │     (Port 9020)          │                                                       │
│  │ • Community Edition      │                                                       │
│  │ • Analyse qualité code   │                                                       │
│  └──────────┬───────────────┘                                                       │
│             ▼                                                                       │
│  ┌──────────────────────────┐                                                       │
│  │   PostgreSQL 16          │                                                       │
│  │   (sonarqube-db)         │                                                       │
│  └──────────────────────────┘                                                       │
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
        ┌───────────────────────┴────────────────────────────────────┐
        │                                                            │
   CI : connexion réseau dynamique             CD + Upgrade infra : kubectl + Helm
   (agent éphémère)                            (kubeconfig-stagingkub / -infra-upgrader)
        ▼                                                            ▼
┌───────────────────────────────┐    ┌──────────────────────────────────────┐
│   rhdemo-ephemere-network     │    │   KinD Cluster kind-rhdemo (CD)      │
│   (Docker Compose — CI)       │    │                                      │
│                               │    │   Namespace : rhdemo-stagingkub      │
│ • Nginx (443)                 │    │   ┌────────────────────────────────┐ │
│ • RHDemo App (9000)           │    │   │ ServiceAccount                 │ │
│ • Keycloak (8080)             │    │   │ jenkins-deployer (RBAC)        │ │
│ • PostgreSQL (5432)           │    │   │ Accès limité au namespace      │ │
└───────────────────────────────┘    │   └────────────────────────────────┘ │
                                     │ • rhdemo-app  (Deployment)           │
                                     │ • keycloak    (Deployment)           │
                                     │ • postgresql  (StatefulSet x2)       │
                                     │ • Nginx Ingress (NodePort 443)       │
                                     │   ┌────────────────────────────────┐ │
                                     │   │ ServiceAccount (distinct)       │ │
                                     │   │ jenkins-infra-upgrader (RBAC)   │ │
                                     │   │ Cilium/NGF/observabilité        │ │
                                     │   │ (nginx-gateway, loki-stack,     │ │
                                     │   │  monitoring, kube-system restr.)│ │
                                     │   └────────────────────────────────┘ │
                                     └──────────────────────────────────────┘
```

> Deux ServiceAccounts Kubernetes distincts pour `stagingkub`, générés par `init-stagingkub.sh` : `jenkins-deployer` (déploiement applicatif, `Jenkinsfile-CD`) et `jenkins-infra-upgrader` (mise à jour en place de l'infrastructure — Cilium, NGINX Gateway Fabric, kube-prometheus-stack, Loki, Promtail, Grafana — `Jenkinsfile-Stagingkub-Upgrade-Deploy`). Voir [docs/STAGINGKUB_REBUILD_PIPELINE.md](../../docs/STAGINGKUB_REBUILD_PIPELINE.md) et [stagingkub/rbac/README.md](../stagingkub/rbac/README.md).

### Volumes persistants

| Volume | Usage | Taille estimée |
|--------|-------|----------------|
| `rhdemo-jenkins-home` | Configuration et jobs Jenkins (controller) | ~2 GB |
| `rhdemo-maven-repository` | Cache Maven (.m2) partagé entre agents éphémères | ~1 GB |
| `rhdemo-trivy-cache` | Cache DB Trivy partagé entre agents éphémères | ~300 MB |
| `rhdemo-wdm-cache` | Cache WebDriverManager (geckodriver) partagé entre agents éphémères | ~50 MB |
| `rhdemo-sonarqube-data` | Données SonarQube | ~500 MB |
| `rhdemo-sonarqube-extensions` | Plugins SonarQube | ~100 MB |
| `rhdemo-sonarqube-logs` | Logs SonarQube | ~50 MB |
| `rhdemo-sonarqube-db` | Base PostgreSQL SonarQube | ~200 MB |
| `kind-registry-data` | Images Docker locales | Variable |
| `rhdemo-jenkins-zap-sessions` | Sessions ZAP (réutilisation entre builds) | ~50 MB |
| `rhdemo-jenkins-zap-reports` | Rapports ZAP HTML/JSON | ~100 MB |

> Les caches Maven et Trivy sont montés dans chaque agent éphémère via le template Docker Cloud — les builds successifs restent rapides malgré la destruction du conteneur après chaque build.

**Note** : Le volume `kind-registry-data` stocke les images du registry Docker local nommé `kind-registry`. Ce nom est standardisé pour garantir la résolution DNS dans les clusters Kubernetes (KinD).

### Services inclus

| Service | Description | Port | Fichier |
|---------|-------------|------|---------|
| `jenkins` | Controller Jenkins (pilotage uniquement) | 8080, 50000 | docker-compose.yml |
| `docker-socket-proxy` | Proxy API Docker filtré (création/arrêt agents uniquement) | 2375 (interne) | docker-compose.yml |
| `sonarqube` | Analyse qualité du code | 9020 | docker-compose.yml |
| `sonarqube-db` | Base de données PostgreSQL pour SonarQube | - | docker-compose.yml |
| `owasp-zap` | Proxy de sécurité pour tests Selenium (CI/CD) | 8090 | docker-compose.zap.yml |
| `registry` | Docker Registry local (HTTPS) | 5000 | docker-compose.yml |
| agents éphémères | Créés à la demande par Docker Cloud, détruits après le build | - | Docker Cloud (JCasC) |

### 🤖 Architecture Controller / Agents éphémères

Le controller Jenkins ne fait que du **pilotage** : orchestration des pipelines, gestion des credentials, interface web et JCasC. Tous les builds sont délégués à des **agents éphémères** créés à la demande via le Docker Plugin (Docker Cloud).

**Controller (`Dockerfile.jenkins`)** :

- `numExecutors: 0` — n'exécute aucun build
- `mode: EXCLUSIVE` — ne peut pas recevoir de jobs
- Contient uniquement les plugins et la configuration JCasC
- Se connecte au daemon Docker via `docker-socket-proxy` (API filtrée TCP)
- N'a pas accès direct à `/var/run/docker.sock`

**Docker Socket Proxy** :

- Seul service montant `/var/run/docker.sock` de l'hôte
- Expose une API TCP filtrée sur le port 2375 (interne au réseau Jenkins)
- Autorise uniquement : création, démarrage, arrêt, suppression de conteneurs
- Bloque : builds d'images, gestion volumes/réseaux, exec, system info

**Agents éphémères (`Dockerfile.agent`)** :

- Image `rhdemo-jenkins-agent:latest` instanciée à la demande par Docker Cloud
- Créés pour chaque build, détruits immédiatement après
- Max 2 simultanés (`instanceCapStr: "2"`)
- Contiennent tous les outils de build :
  - JDK 25 (Eclipse Temurin) + Maven 3.9.12
  - Docker CLI + Docker Compose (socket hôte monté dans l'agent)
  - Firefox ESR + Xvfb (tests Selenium headless)
  - SOPS, yq (secrets et parsing YAML)
  - Trivy (scan CVE images Docker)
  - kubectl, Helm (déploiement Kubernetes)
  - Cosign (signature d'images)
  - Node.js/npm (build frontend)

> Il n'y a plus de `JENKINS_SECRET` à configurer — la connexion controller ↔ agent est gérée automatiquement par le Docker Plugin.

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
   ```

   Les notifications email (optionnelles) ne se configurent **pas** dans `.env` — voir la
   section [Email](#email) plus bas.

### Configuration Jenkins as Code (JCasC)

Le fichier `jenkins-casc.yaml` configure automatiquement :
- ✅ Utilisateur admin
- ✅ Controller en mode pilotage (`numExecutors: 0`, `mode: EXCLUSIVE`)
- ✅ Docker Cloud avec template agent éphémère (label `builder`, max 2 simultanés)
- ✅ Connexion Docker via `tcp://docker-socket-proxy:2375` (pas de socket direct)
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
Voir le fichier [QUICKSTART.md](QUICKSTART.md) pour la liste complète des credentials à créer.


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

# Proxy socket
docker-compose logs -f docker-socket-proxy

# Agent éphémère en cours (nom dynamique)
AGENT=$(docker ps --filter "ancestor=rhdemo-jenkins-agent" --format '{{.Names}}' | head -n1)
docker logs -f "$AGENT"
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

# Agent éphémère en cours (nom dynamique)
AGENT=$(docker ps --filter "ancestor=rhdemo-jenkins-agent" --format '{{.Names}}' | head -n1)
docker exec -it "$AGENT" bash
```

## 🔌 Plugins installés

Les plugins sont définis dans `plugins.txt` sous forme de **lockfile versionné** : toutes les versions (plugins directs + dépendances transitives) sont pinnées explicitement. Cela garantit des builds d'image Jenkins reproductibles et auditables.

### Plugins directs (utilisés par les pipelines)

| Catégorie | Plugin | Usage |
|-----------|--------|-------|
| Pipeline | `workflow-aggregator`, `pipeline-stage-view` | Pipeline déclaratif, visualisation des stages |
| SCM | `git` | `checkout scm` |
| Credentials | `credentials`, `credentials-binding`, `matrix-auth` | Gestion des secrets, droits par utilisateur |
| Build Java | `maven-plugin`, `jdk-tool` | `tools { maven 'Maven3' }`, `tools { jdk 'JDK21' }` |
| Qualité | `sonar`, `coverage` | `withSonarQubeEnv`, `recordCoverage` (JaCoCo) |
| Tests | `junit`, `htmlpublisher` | Rapports Surefire, Trivy, ZAP, OWASP |
| Sécurité | `dependency-check-jenkins-plugin` | Configuration outil OWASP Dependency-Check |
| Docker | `docker-plugin`, `docker-workflow` | Agents éphémères Docker Cloud, commandes Docker |
| Notifications | `mailer` (dépendance), `email-ext` | `emailext(...)` — notifications succès/échec RHDemo-CI, credential SMTP géré côté UI (pas JCasC, voir section [Email](#email)) |
| Pipeline options | `timestamper`, `build-timeout`, `ws-cleanup` | Timestamps, timeout, nettoyage workspace |
| Config as Code | `configuration-as-code`, `job-dsl` | `jenkins-casc.yaml`, définition des jobs |
| Utilitaires | `pipeline-utility-steps`, `copyartifact` | `readJSON`, `readYaml`, récupération digest CI |

Les dépendances transitives (~70 plugins) sont également pinnées dans `plugins.txt` pour une reproductibilité totale.

### Mettre à jour les plugins

Les mises à jour se font en deux étapes explicites pour rester auditables :

**Étape 1 — Mettre à jour via l'UI Jenkins :**

Manage Jenkins → Plugins → Updates → Update All, puis redémarrer Jenkins.

**Étape 2 — Régénérer le lockfile depuis l'instance mise à jour :**

```bash
# Prévisualiser les changements sans modifier plugins.txt
./generate-pluginslist.sh --dry-run

# Mettre à jour plugins.txt en place
./generate-pluginslist.sh
```

Le script met à jour les versions directement dans `plugins.txt` en préservant la structure (catégories, commentaires), et met à jour la date de génération dans l'en-tête. Committer ensuite — le diff git rend les changements de versions explicites et auditables.

> **Pourquoi pas `jenkins-plugin-cli --list` ?** Cette commande lit depuis `/usr/share/jenkins/ref/plugins/`, le répertoire baked dans l'image Docker au moment du build. Les mises à jour faites via l'UI Jenkins sont écrites dans le volume (`/var/jenkins_home/plugins/`) sans modifier la ref — les deux divergent. `generate-pluginslist.sh` lit directement les fichiers `MANIFEST.MF` dans le volume via `docker compose exec`, sans passer par l'API HTTP.

**Étape 3 — Reconstruire l'image proprement :**

```bash
./start-jenkins.sh --clean-plugins
```

> `--clean-plugins` purge les plugins du volume Jenkins **et** force `docker build --no-cache` pour que `jenkins-plugin-cli` réinstalle exactement les versions du lockfile (sans cache Docker). Sans `--no-cache`, Docker réutiliserait la couche `RUN jenkins-plugin-cli` même si les versions ont changé.

## 🔨 Création des pipelines pour RHDemo

Les pipelines sont créés automatiquement au démarrage dans la section `jobs:` de `jenkins-casc.yaml` :

| Job | Jenkinsfile | Rôle |
|-----|-------------|------|
| `RHDemo-CI` | `Jenkinsfile-CI` | Build, tests, scans sécurité, déploiement ephemere, publication image |
| `RHDemo-CD` | `Jenkinsfile-CD` | Déploiement de l'application sur stagingkub |
| `RHDemo-Renovate` | `Jenkinsfile-Renovate` | Scan Renovate + automerge des PRs de dépendances (patch/minor) |
| `RHDemo-Stagingkub-Upgrade-Deploy` | `Jenkinsfile-Stagingkub-Upgrade-Deploy` | Mise à jour en place d'un composant d'infra stagingkub (Cilium, NGF, kube-prometheus-stack, Loki, Promtail, Grafana), déclenché par `RHDemo-Renovate` après un merge réussi — voir [docs/STAGINGKUB_REBUILD_PIPELINE.md](../../docs/STAGINGKUB_REBUILD_PIPELINE.md) |


## 🐳 Docker-in-Docker (DinD)

Les **agents éphémères** (pas le controller) peuvent exécuter des commandes Docker et docker-compose grâce au montage du socket Docker configuré dans le template Docker Cloud :

```yaml
# Dans le template Docker Cloud (jenkins-casc.yaml)
volumes:
  - "/var/run/docker.sock:/var/run/docker.sock"
  - "/usr/bin/docker:/usr/bin/docker"
```

Le **controller** n'a pas accès au socket Docker directement — il passe par `docker-socket-proxy` (API filtrée limitée à la gestion du cycle de vie des conteneurs).

### Vérifier Docker dans un agent éphémère

```bash
# Pendant un build, identifier le conteneur agent
AGENT=$(docker ps --filter "ancestor=rhdemo-jenkins-agent" --format '{{.Names}}' | head -n1)

docker exec "$AGENT" docker --version
docker exec "$AGENT" docker ps
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

Notifications de succès/échec de `RHDemo-CI` (step `emailext`, plugin **email-ext** — pas le
Mailer basique, qui n'accepte qu'un couple username/password en clair sans passer par un
credential Jenkins).

**⚠️ Pas configurable via JCasC** : le configurateur `configuration-as-code` ne sait piloter ni
le credential SMTP du plugin Mailer (`UnknownAttributesException` au boot si on essaie), ni celui
d'email-ext (bug connu upstream, [configuration-as-code-plugin#679](https://github.com/jenkinsci/configuration-as-code-plugin/issues/679)).
La configuration se fait donc entièrement à la main, une seule fois, via l'UI — `jenkins-casc.yaml`
ne la gère pas et ne l'écrase donc pas au redémarrage.

**1. Créer le credential SMTP** (Manage Jenkins → Credentials → (global) → Add Credentials) :
- **Kind : `Username with password`** — ⚠️ pas `Secret text`. La liste déroulante SMTP
  d'Extended E-mail Notification ne montre que les credentials de ce type précis ; un mauvais
  choix ici est la cause la plus fréquente d'un credential invisible dans la page suivante,
  même après l'avoir recréé plusieurs fois.
- Username : votre adresse d'envoi, ex. `jenkinsadmin@gmail.com`
- Password : le mot de passe SMTP de cette adresse (souvent différent du mot de passe principal
  du compte — mot de passe d'application ou mot de passe IMAP/SMTP dédié selon le fournisseur)
- ID : ex. `smtp-credentials`

**2. Configurer le compte SMTP** (Manage Jenkins → System → Extended E-mail Notification) :
- SMTP server : ex. `smtp.exemple-fournisseur.com`
- Advanced → SMTP Port : selon le fournisseur (465 pour SSL implicite, 587 pour STARTTLS)
- Use SSL / Use TLS : cocher celui qui correspond au port choisi (pas les deux)
- Use OAuth2 : décoché, sauf fournisseur l'exigeant explicitement (incompatible avec un
  credential Username/password classique)
- Use SMTP Authentication : coché, credential = celui créé à l'étape 1
- Manage Jenkins → System → Jenkins Location → *System Admin e-mail address* : renseigner une
  adresse cohérente avec le domaine d'envoi — certains fournisseurs (Infomaniak notamment)
  rejettent silencieusement les mails dont le `From` ne correspond à aucun domaine authentifié

**3. Utilisation dans un pipeline**, voir `Jenkinsfile-CI` (`post { success/failure }`) pour un
exemple réel avec gestion d'erreur (une panne SMTP ne doit pas faire échouer un build) :
```groovy
emailext to: 'destinataire@exemple.com',
         subject: "Sujet",
         body: "Corps du message"
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

### Cosign - Signature d'images Docker

Cosign est installé sur l'agent Jenkins. Il signe l'image Docker produite par le pipeline CI et le pipeline CD vérifie cette signature avant tout déploiement.

**Flux :**
```text
CI  → cosign sign   --key cosign-private-key  → signature stockée dans le registry
CD  → cosign verify --key cosign-public-key   → rejet si image non signée ou altérée
```

**Génération de la paire de clés (une seule fois sur l'hôte) :**

```bash
cosign generate-key-pair
# Saisir et confirmer un mot de passe
# → cosign.key  (clé privée — NE PAS commiter)
# → cosign.pub  (clé publique)
```

**Credentials Jenkins à créer** (Manage Jenkins → Manage Credentials → (global) → Add Credentials) :

| ID                      | Kind         | Contenu                              | Utilisé par |
|-------------------------|--------------|--------------------------------------|-------------|
| `cosign-private-key`    | Secret file  | Fichier `cosign.key`                 | CI          |
| `cosign-password`       | Secret text  | Mot de passe saisi lors de la génération | CI      |
| `cosign-public-key`     | Secret file  | Fichier `cosign.pub`                 | CD          |

**Paramètre pipeline :**
- CI : le paramètre `SIGN_IMAGE` (booléen, défaut `true`) active/désactive la signature
- CD : le paramètre `VERIFY_SIGNATURE` (booléen, défaut `true`) active/désactive la vérification

**Dépannage signature invalide :**

```bash
# Vérifier manuellement depuis l'hôte
cosign verify --key cosign.pub \
    --insecure-ignore-tlog=true \
    kind-registry:5000/rhdemo-api:<TAG>@<DIGEST>
```

### Renovate - Automerge des PRs de dépendances

Le pipeline `RHDemo-Renovate` (job JCasC, cron `H 4 * * *`) scanne les dépendances avec Renovate puis merge automatiquement les PRs patch/minor dont la CI passe. Il a besoin de 4 credentials Jenkins dédiés, en plus de `nvd-api-key` et `ossindex-credentials` déjà créés pour `Jenkinsfile-CI`.

**Credentials Jenkins à créer** (Manage Jenkins → Manage Credentials → (global) → Add Credentials) :

| ID | Kind | Contenu | Utilisé par |
|----|------|---------|-------------|
| `ci-bot-forgejo-token` | Secret text | Token du compte Codeberg bot `rhdemo-ci-bot` (collaborateur **Write**, pas Admin), scopes `repository` + `issue` | Listing/sync/merge des PRs, commentaires |
| `renovate-forgejo-token` | Secret text | Token du compte bot Renovate (distinct de `rhdemo-ci-bot`), scopes `repository` + `issue` + `user` | Stage `🔄 Scan Renovate` |
| `renovate-gpg-key` | Secret text | Clé GPG privée dédiée, exportée en base64 (`gpg --export-secret-keys <KEY_ID> \| base64 -w0`) | Signature des commits Renovate |
| `renovate-github-token` | Secret text | Token GitHub read-only (dépôts publics) | Lookup changelogs/release notes GitHub |

**Pourquoi deux comptes bot distincts et pourquoi `renovate-forgejo-token` ne peut pas être fusionné avec `ci-bot-forgejo-token`** : voir [`docs/RENOVATE_AUTOMERGE_CI.md`](../../docs/RENOVATE_AUTOMERGE_CI.md) (sections 1 et « Credentials Jenkins nécessaires ») — en résumé, séparation propose/merge (deux identités distinctes côté audit Forgejo) et `ci-bot-forgejo-token` échoue avec `Authentication failure` au scan Renovate faute de scope `user`.

**Sécurité** : `ci-bot-forgejo-token` (accès Write) n'est jamais exposé en variable d'environnement pendant le build Maven/OWASP de la PR — voir section « Sécurité » du même document.

### Mise à jour en place de l'infrastructure stagingkub

Pour les PRs Renovate qui touchent un composant d'infrastructure (`rhDemo/infra/stagingkub/scripts/components/*.sh` ou `kind-config.yaml`), `RHDemo-Renovate` bascule automatiquement sur une validation Kubernetes (`helm upgrade --dry-run=server` / `kubectl apply --dry-run=server`) au lieu du build Maven+OWASP, puis déclenche `RHDemo-Stagingkub-Upgrade-Deploy` après le merge pour appliquer réellement la mise à jour sur le cluster.

**Credential Jenkins à créer** (Manage Jenkins → Manage Credentials → (global) → Add Credentials) :

| ID | Kind | Contenu | Utilisé par |
|----|------|---------|-------------|
| `kubeconfig-stagingkub-infra-upgrader` | Secret file | Fichier `jenkins-kubeconfig/kubeconfig-jenkins-infra-upgrader-rbac.yaml`, généré par `init-stagingkub.sh` | `RHDemo-Renovate` (validation dry-run) + `RHDemo-Stagingkub-Upgrade-Deploy` (application réelle) |

Ce credential porte les droits du ServiceAccount **dédié** `jenkins-infra-upgrader` — distinct de `kubeconfig-stagingkub`/`jenkins-deployer` utilisé par `RHDemo-CD`, qui ne gagne aucun droit supplémentaire de ce fait. Détail du RBAC et de l'étude ayant motivé cette séparation : [docs/STAGINGKUB_REBUILD_PIPELINE.md](../../docs/STAGINGKUB_REBUILD_PIPELINE.md) et [infra/stagingkub/rbac/README.md](../stagingkub/rbac/README.md).

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

```bash
# Purge du volume + rebuild image sans cache (réinstalle les versions du lockfile)
./start-jenkins.sh --clean-plugins

# Si le problème persiste, forcer aussi le rebuild de l'image agent
./start-jenkins.sh --clean-plugins --rebuild
```

### Docker-in-Docker ne fonctionne pas

**Vérifier les permissions :**
```bash
# Sur l'hôte
ls -la /var/run/docker.sock

# Doit être accessible au groupe docker (984)
sudo chmod 666 /var/run/docker.sock
```

**Dans un agent éphémère en cours de build :**
```bash
AGENT=$(docker ps --filter "ancestor=rhdemo-jenkins-agent" --format '{{.Names}}' | head -n1)
docker exec "$AGENT" docker ps
```

### Réinitialiser complètement Jenkins

```bash
# Arrêter et supprimer TOUT (⚠️ PERTE DE DONNÉES)
docker-compose down -v

# Supprimer les volumes
docker volume rm rhdemo-jenkins-home
docker volume rm rhdemo-maven-repository
docker volume rm rhdemo-trivy-cache
docker volume rm rhdemo-wdm-cache

# Redémarrer
./start-jenkins.sh
```

### Aucun agent ne démarre pour un build

**Symptôme :** Le build reste en attente ("waiting for available executor")

**Causes possibles :**

1. **`docker-socket-proxy` non démarré** : `docker-compose ps docker-socket-proxy`
2. **Image agent introuvable** : `docker images rhdemo-jenkins-agent` — construire avec `docker build -f Dockerfile.agent -t rhdemo-jenkins-agent:latest .`
3. **Docker Cloud mal configuré** : Jenkins > Manage Jenkins > Clouds > docker-local > Test Connection
4. **Capacité atteinte** : max 2 agents simultanés (`instanceCapStr: "2"`) — attendre qu'un build se termine

```bash
# Vérifier que le proxy répond
docker exec rhdemo-jenkins curl -s http://docker-socket-proxy:2375/version | head -c 100

# Logs du controller (chercher les erreurs Docker Cloud)
docker-compose logs jenkins | grep -i "docker\|cloud\|agent"
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
