# 🔄 Pipelines CI/CD - RHDemo

Ce document décrit l'architecture des pipelines CI/CD pour le projet RHDemo.

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Jenkinsfile-CI : Intégration Continue](#jenkinsfile-ci--intégration-continue)
- [Jenkinsfile-CD : Déploiement Continu](#jenkinsfile-cd--déploiement-continu)
- [Jenkinsfile-Renovate : mises à jour de dépendances](#jenkinsfile-renovate--mises-à-jour-de-dépendances)
- [Jenkinsfile-Stagingkub-Upgrade-Deploy : montées d'infra en place](#jenkinsfile-stagingkub-upgrade-deploy--montées-dinfra-en-place)
- [Workflow recommandé](#workflow-recommandé)
- [Configuration Jenkins](#configuration-jenkins)

---

## 🎯 Vue d'ensemble

Le projet RHDemo utilise **quatre pipelines Jenkins distincts** :

| Pipeline | Rôle | Déclenchement | Doc dédiée |
|---|---|---|---|
| **RHDemo-CI** (`Jenkinsfile-CI`) | Build, tests, scans qualité/sécurité, déploiement ephemere, tests Selenium/ZAP, publication image | SCM sur les branches d'évolution | ce document |
| **RHDemo-CD** (`Jenkinsfile-CD`) | Déploiement Helm de l'image validée sur stagingkub (K8s) | Manuel | ce document |
| **RHDemo-Renovate** (`Jenkinsfile-Renovate`) | Scan Renovate, ouverture des PR, build/test/OWASP puis **merge automatique** des PR patch/minor qui passent la CI | Cron | [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md) |
| **RHDemo-Stagingkub-Upgrade-Deploy** (`Jenkinsfile-Stagingkub-Upgrade-Deploy`) | Application réelle (post-merge) des montées de version en place des composants d'infra stagingkub | Après merge d'une PR Renovate d'infra | [STAGINGKUB_REBUILD_PIPELINE.md](STAGINGKUB_REBUILD_PIPELINE.md) |

Toutes les fins de build CI et CD, ainsi que l'upgrade d'infra, envoient une
**notification email** (email-ext). L'ancien `Jenkinsfile` monolithique (CI+CD
mélangés) a été **supprimé**.

Enchaînement CI → CD :

```
┌─────────────────────────────────────────────────────────────────┐
│                       JENKINSFILE-CI                            │
│                  (Intégration Continue)                         │
├─────────────────────────────────────────────────────────────────┤
│ 1. Build & Tests                                               │
│    ├─ Compilation Maven                                        │
│    ├─ Tests unitaires                                          │
│    ├─ Analyse OWASP Dependency-Check                           │
│    ├─ Build Maven (JAR)                                        │
│    └─ Analyse SonarQube + Quality Gate                         │
│                                                                 │
│ 2. Build Docker                                                │
│    └─ Construction de l'image Docker                           │
│                                                                 │
│ 3. Tests d'intégration (Staging Docker Compose)               │
│    ├─ Déploiement environnement ephemere Docker                 │
│    ├─ Initialisation base de données                           │
│    ├─ Initialisation Keycloak                                  │
│    ├─ Tests Selenium                                           │
│    └─ Tests sécurité OWASP ZAP                                 │
│                                                                 │
│ 4. Publication                                                  │
│    └─ Push de l'image validée vers le registry                 │
│                                                                 │
│ ✅ Résultat: Image Docker taggée et publiée                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Image validée et publiée
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       JENKINSFILE-CD                            │
│                   (Déploiement Continu)                         │
├─────────────────────────────────────────────────────────────────┤
│ 1. Préparation                                                  │
│    ├─ Déchiffrement des secrets SOPS                           │
│    └─ Vérification de l'image dans le registry                 │
│                                                                 │
│ 2. Configuration Kubernetes                                     │
│    ├─ Connexion au cluster KinD                                │
│    └─ Mise à jour des secrets Kubernetes                       │
│                                                                 │
│ 3. Déploiement                                                  │
│    ├─ Déploiement Helm sur stagingkub                          │
│    └─ Attente readiness des pods                               │
│                                                                 │
│ 4. Vérification                                                 │
│    ├─ Health checks                                            │
│    └─ Validation du déploiement                                │
│                                                                 │
│ ✅ Résultat: Application déployée sur Kubernetes               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Jenkinsfile-CI : Intégration Continue

**Fichier**: [`Jenkinsfile-CI`](../Jenkinsfile-CI)

### Objectif

Construire, tester et valider l'application, puis publier l'image Docker sur le registry.

### Phases

#### Phase 1 : Préparation
- Checkout du code source
- Lecture de la version Maven
- Déchiffrement des secrets SOPS
- Configuration Keycloak

#### Phase 2 : Build et Tests
- Compilation Maven
- Tests unitaires
- Analyse OWASP Dependency-Check
- Build Maven (création du JAR)
- Analyse SonarQube (optionnel)
- Quality Gate SonarQube (optionnel)

#### Phase 3 : Docker Build
- Construction de l'image Docker

#### Phase 4 : Staging Docker Compose
- Démarrage de l'environnement ephemere (Docker Compose)
  - PostgreSQL
  - Keycloak
  - Application RHDemo
  - NGINX
- Initialisation base de données (pgschema.sql + pgdata.sql)
- Initialisation Keycloak (realm + users)

#### Phase 5 : Tests Selenium et OWASP ZAP
- Tests Selenium (optionnel)
- Tests sécurité OWASP ZAP

#### Phase 6 : Publication
- Vérification du nom du registry : **DOIT être `kind-registry`** (sinon échec du pipeline)
- Tag de l'image avec la version finale :
  - **SNAPSHOT** : `<VERSION>-<BUILD_NUMBER>` (ex: `1.1.0-SNAPSHOT-95`)
  - **RELEASE** : `<VERSION>` (ex: `1.0.0-RELEASE`)
- Tag supplémentaire : `latest` (toujours mis à jour vers la dernière image validée)
- Push vers le registry Docker local (`localhost:5000` ou `kind-registry:5000`)

#### Phase 7 : Archivage
- Archivage du JAR
- Archivage des rapports (tests, OWASP, ZAP)

### Paramètres

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `RUN_SELENIUM_TESTS` | Boolean | `true` | Exécuter les tests Selenium |
| `RUN_SONAR` | Boolean | `true` | Exécuter l'analyse SonarQube |
| `PUBLISH_IMAGE` | Boolean | `true` | Publier l'image sur le registry |
| `IMAGE_TAG_SUFFIX` | String | `""` | Suffixe optionnel pour le tag (ex: `-rc1`, `-hotfix`) |

### Exemple d'utilisation

```bash
# Build standard avec tous les tests
# Pas de paramètres nécessaires (utilise les valeurs par défaut)

# Build sans SonarQube
RUN_SONAR=false

# Build avec tag personnalisé
IMAGE_TAG_SUFFIX=-rc1
```

### Artifacts produits

- Images Docker publiées sur le registry :
  - **SNAPSHOT** : `rhdemo-api:1.1.0-SNAPSHOT-95` + `rhdemo-api:latest`
  - **RELEASE** : `rhdemo-api:1.0.0-RELEASE` + `rhdemo-api:latest`
- JAR : `target/*.jar`
- Rapports :
  - Tests unitaires : `target/surefire-reports/**`
  - OWASP Dependency-Check : `target/dependency-check-report.html`
  - OWASP ZAP : `zap-reports/*`
  - Screenshots Selenium : `rhDemoAPITestIHM/target/screenshots/**/*.png`

---

## 🚀 Jenkinsfile-CD : Déploiement Continu

**Fichier**: [`Jenkinsfile-CD`](../Jenkinsfile-CD)

### Objectif

Déployer une image Docker validée (publiée par le pipeline CI) sur l'environnement Kubernetes stagingkub.

### Phases

#### Phase 1 : Préparation
- Checkout du code source
- Détermination de la version de l'image à déployer :
  - **Avec paramètre `IMAGE_TAG`** : Utilise le tag spécifié (ex: `1.1.0-SNAPSHOT-95`)
  - **Sans paramètre** : Utilise le tag `latest` (dernière image validée par CI)
- Déchiffrement des secrets SOPS
- Extraction des secrets applicatifs

#### Phase 2 : Configuration Kubernetes
- Configuration de l'accès au cluster KinD
- Vérification du nom du registry : **DOIT être `kind-registry`** (sinon échec du pipeline)
- Connexion automatique du registry au réseau `kind` avec alias DNS `kind-registry`
- Vérification de l'image dans le registry
- Mise à jour des secrets Kubernetes

#### Phase 3 : Déploiement
- Déploiement Helm sur stagingkub
- Redémarrage forcé des pods (optionnel)

#### Phase 4 : Vérification
- Attente de la readiness des pods
- Health checks des services
- Affichage du statut du déploiement

### Paramètres

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `IMAGE_TAG` | String | `""` | Tag de l'image à déployer (ex: `1.1.0-SNAPSHOT-95`, `1.0.0-RELEASE`). **Si vide, utilise `latest`** (dernière image validée par CI) |
| `FORCE_RECREATE_PODS` | Boolean | `false` | Forcer la recréation des pods (rollout restart) |
| `SKIP_HEALTH_CHECK` | Boolean | `false` | Ne pas attendre les health checks |

### Exemple d'utilisation

```bash
# Déploiement automatique de la dernière image validée par CI (tag 'latest')
# Pas de paramètres nécessaires
# → Utilise rhdemo-api:latest

# Déploiement d'une version SNAPSHOT spécifique (avec numéro de build)
IMAGE_TAG=1.1.0-SNAPSHOT-95
# → Utilise rhdemo-api:1.1.0-SNAPSHOT-95

# Déploiement d'une version RELEASE spécifique
IMAGE_TAG=1.0.0-RELEASE
# → Utilise rhdemo-api:1.0.0-RELEASE

# Déploiement avec recréation forcée des pods
IMAGE_TAG=1.1.0-SNAPSHOT-95
FORCE_RECREATE_PODS=true

# Déploiement rapide sans health checks
SKIP_HEALTH_CHECK=true
# → Utilise rhdemo-api:latest sans attendre les health checks
```

### Pré-requis

1. **Registry Docker nommé `kind-registry`** :
   ```bash
   # Vérifier le nom du registry
   docker ps --filter "publish=5000" --format '{{.Names}}'
   # DOIT afficher: kind-registry

   # Si incorrect, recréer le registry
   cd rhDemo/infra/jenkins-docker
   docker-compose up -d registry
   ```
   **Important** : Le nom `kind-registry` est obligatoire pour la résolution DNS dans KinD. Voir [REGISTRY.md](REGISTRY.md).

2. **Cluster KinD initialisé** :
   ```bash
   cd rhDemo/infra/stagingkub/scripts
   ./init-stagingkub.sh
   ```
   Le script connecte automatiquement le registry au réseau `kind` avec l'alias DNS.

3. **Image Docker publiée** : L'image doit exister dans le registry local (port 5000).

4. **Namespace créé** : Le namespace `rhdemo-stagingkub` doit exister avec les labels Helm.

### URLs d'accès

Après un déploiement réussi :

- **Application RHDemo** : https://rhdemo-stagingkub.intra.leuwen-lc.fr
- **Keycloak** : https://keycloak-stagingkub.intra.leuwen-lc.fr

---

## 🔁 Jenkinsfile-Renovate : mises à jour de dépendances

**Fichier**: [`Jenkinsfile-Renovate`](../Jenkinsfile-Renovate) — **doc de référence** : [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md)

### Objectif

Faire tourner Renovate depuis Jenkins (le scan a été rapatrié de Codeberg
Actions), ouvrir les PR de montée de version, puis **merger automatiquement**
celles qui passent la CI — patch/minor uniquement.

### Étapes

1. Scan Renovate (image officielle `renovate/renovate` en conteneur frère via docker-socket-proxy, commits signés GPG, compte bot Codeberg dédié).
2. Liste des PR Renovate ouvertes via l'API Forgejo ; rebase de celles en retard sur leur base.
3. Pour chaque PR patch/minor : build + tests + OWASP Dependency-Check (Maven **et** npm frontend).
4. **Merge automatique en squash** via l'API Forgejo si la CI est verte ; commentaire d'échec sinon (PR laissée ouverte). Fermeture automatique des PR supersédées.
5. Les PR **major** restent bloquées derrière `dependencyDashboardApproval` (approbation manuelle via le Dependency Dashboard).

> Pourquoi un merge piloté côté Jenkins plutôt que l'automerge natif de
> Renovate ? Jenkins n'est pas exposé sur Internet : Forgejo ne peut pas
> déclencher de webhook entrant et les statuts CI ne remontent jamais vers
> Forgejo. Voir [CICD_JENKINS_VS_FORGEJO_ACTIONS.md](CICD_JENKINS_VS_FORGEJO_ACTIONS.md).

---

## 🧱 Jenkinsfile-Stagingkub-Upgrade-Deploy : montées d'infra en place

**Fichier**: [`Jenkinsfile-Stagingkub-Upgrade-Deploy`](../Jenkinsfile-Stagingkub-Upgrade-Deploy) — **doc de référence** : [STAGINGKUB_REBUILD_PIPELINE.md](STAGINGKUB_REBUILD_PIPELINE.md)

### Objectif

Appliquer réellement, **après merge** d'une PR Renovate d'infra, la montée de
version en place d'un composant du cluster stagingkub (Cilium, NGINX Gateway
Fabric, kube-prometheus-stack, Loki, Grafana Alloy, Grafana) via les scripts
idempotents `infra/stagingkub/scripts/components/install-or-upgrade-<composant>.sh`
(rollback automatique `--rollback-on-failure`, Helm 4).

### Points clés

- La **validation avant merge** est faite dans la boucle étendue de `Jenkinsfile-Renovate` par un `helm upgrade --dry-run=server` / `kubectl apply --dry-run=server`, **sans jamais muter le cluster**.
- ServiceAccount Kubernetes **dédié** `jenkins-infra-upgrader` (RBAC de moindre privilège, credential `kubeconfig-stagingkub-infra-upgrader`), distinct de `jenkins-deployer` utilisé par RHDemo-CD.
- Agent éphémère standard (pas de `docker.sock`, pas de `kind`).
- `kindest/node` (version Kubernetes) reste **hors périmètre** : toute montée K8s passe par une reconstruction complète du cluster (cf. [MIGRATION_HELM4_KUB1.36.md](MIGRATION_HELM4_KUB1.36.md)).

---

## 🔄 Workflow recommandé

### 1. Développement quotidien

```bash
# À chaque commit/PR
1. Déclencher Jenkinsfile-CI
2. Vérifier les résultats :
   - Tests unitaires
   - Quality gate SonarQube
   - Tests Selenium
   - Scan sécurité ZAP
3. Si tous les tests passent → image publiée sur le registry
```

### 2. Déploiement sur stagingkub

```bash
# Option A : Déploiement automatique de la dernière version (recommandé pour dev)
1. Après un build CI réussi → l'image 'latest' est mise à jour
2. Déclencher Jenkinsfile-CD SANS paramètre
3. Le CD déploie automatiquement rhdemo-api:latest

# Option B : Déploiement d'une version spécifique (recommandé pour prod)
1. Noter le tag de l'image publiée par CI (ex: 1.1.0-SNAPSHOT-95)
2. Déclencher Jenkinsfile-CD avec IMAGE_TAG=1.1.0-SNAPSHOT-95
3. Le CD déploie exactement cette version

# Dans les deux cas, vérifier le déploiement :
   - Pods ready
   - Health checks OK
   - Application accessible
```

### 3. Workflow complet

```
┌──────────────┐
│ Développeur  │
│  git push    │
└──────┬───────┘
       │
       ▼
┌────────────────────────────────────────────────┐
│       Jenkinsfile-CI (automatique)             │
│  - Build #95                                   │
│  - Tests                                       │
│  - Docker build                                │
│  - Tests Selenium + ZAP                        │
│  - Publish image                               │
└──────┬─────────────────────────────────────────┘
       │
       │ ✅ Images publiées sur registry :
       │    - rhdemo-api:1.1.0-SNAPSHOT-95
       │    - rhdemo-api:latest (updated)
       │
       ▼
┌────────────────────────────────────────────────┐
│       Jenkinsfile-CD (manuel)                  │
│                                                │
│  Option A (dev) : Sans paramètre               │
│    → Déploie rhdemo-api:latest                 │
│    → imagePullPolicy: Always                   │
│                                                │
│  Option B (prod) : IMAGE_TAG=1.1.0-SNAPSHOT-95 │
│    → Déploie rhdemo-api:1.1.0-SNAPSHOT-95      │
│    → imagePullPolicy: Always                   │
│                                                │
│  - Pull image depuis registry                  │
│  - Deploy Helm                                 │
│  - Health checks                               │
└──────┬─────────────────────────────────────────┘
       │
       │ ✅ Déployé sur stagingkub
       │
       ▼
┌────────────────────────────────────────────────┐
│        Application accessible                  │
│  - https://rhdemo-stagingkub.intra.leuwen-lc.fr             │
│  - https://keycloak-stagingkub.intra.leuwen-lc.fr           │
└────────────────────────────────────────────────┘
```

---

## 🏷️ Versioning des images Docker

### Stratégie de tagging

Le pipeline CI applique automatiquement une stratégie de versioning basée sur la version Maven dans `pom.xml` :

#### SNAPSHOT (développement)

```xml
<!-- Dans pom.xml -->
<version>1.1.0-SNAPSHOT</version>
```

**Tags créés par CI** :
- `rhdemo-api:1.1.0-SNAPSHOT-95` (avec numéro de build unique)
- `rhdemo-api:latest` (mis à jour à chaque build)

**Raison** : Chaque build SNAPSHOT est unique grâce au numéro de build Jenkins. Cela permet de :
- Tracer exactement quelle version est déployée
- Revenir à un build antérieur si nécessaire
- Éviter les conflits de cache

#### RELEASE (production)

```xml
<!-- Dans pom.xml -->
<version>1.0.0-RELEASE</version>
```

**Tags créés par CI** :
- `rhdemo-api:1.0.0-RELEASE` (version fixe)
- `rhdemo-api:latest` (mis à jour à chaque build)

**Raison** : Les versions RELEASE sont immuables, pas besoin de numéro de build.

### Politique de pull (imagePullPolicy)

Le pipeline CD adapte automatiquement la politique de pull selon le tag :

| Tag | imagePullPolicy | Raison |
|-----|----------------|--------|
| `latest` | `Always` | Garantit qu'on récupère toujours la dernière image du registry |
| `*-SNAPSHOT-*` | `Always` | Force le pull pour éviter d'utiliser une version en cache |
| `*-RELEASE` | `IfNotPresent` | Version fixe, peut utiliser le cache |

### Exemples de workflow

#### Développement actif (SNAPSHOT)

```bash
# Build CI #95
pom.xml → 1.1.0-SNAPSHOT
CI → Pousse rhdemo-api:1.1.0-SNAPSHOT-95 + latest

# Déploiement CD automatique
CD (sans paramètre) → Déploie rhdemo-api:latest (=1.1.0-SNAPSHOT-95)

# Build CI #96
CI → Pousse rhdemo-api:1.1.0-SNAPSHOT-96 + latest (updated)

# Déploiement CD automatique
CD (sans paramètre) → Déploie rhdemo-api:latest (=1.1.0-SNAPSHOT-96)
  ↳ Avec imagePullPolicy=Always, récupère automatiquement la nouvelle version
```

#### Release en production

```bash
# Build CI avec version RELEASE
pom.xml → 1.0.0-RELEASE
CI → Pousse rhdemo-api:1.0.0-RELEASE + latest

# Déploiement CD avec tag spécifique
CD avec IMAGE_TAG=1.0.0-RELEASE → Déploie exactement cette version
  ↳ Avec imagePullPolicy=IfNotPresent, utilise le cache si disponible
```

### Nettoyage automatique du registry

Le pipeline CI nettoie automatiquement les anciennes images SNAPSHOT pour économiser l'espace disque :

- **Politique de rétention** : Garde les 3 derniers builds SNAPSHOT
- **Garbage collection** : Libère l'espace disque après suppression
- **Images RELEASE** : Jamais supprimées automatiquement

**Exemple** :
```
Avant build #98 :
  - rhdemo-api:1.1.0-SNAPSHOT-95
  - rhdemo-api:1.1.0-SNAPSHOT-96
  - rhdemo-api:1.1.0-SNAPSHOT-97
  - rhdemo-api:latest

Après build #98 :
  - rhdemo-api:1.1.0-SNAPSHOT-96
  - rhdemo-api:1.1.0-SNAPSHOT-97
  - rhdemo-api:1.1.0-SNAPSHOT-98
  - rhdemo-api:latest
```

---

## ⚙️ Configuration Jenkins

### 1. Créer deux pipelines Jenkins

#### Option A : Configuration automatique (JCasC - Recommandé)

Le fichier [infra/jenkins-docker/jenkins-casc.yaml](../infra/jenkins-docker/jenkins-casc.yaml) configure **automatiquement** les deux pipelines au démarrage de Jenkins.

**Avantages** :
- ✅ Configuration versionnée dans Git
- ✅ Déploiement reproductible
- ✅ Pas de configuration manuelle

Les jobs créés automatiquement : `RHDemo-CI`, `RHDemo-CD`, `RHDemo-Renovate`,
`RHDemo-Stagingkub-Upgrade-Deploy`. Le dépôt est hébergé sur **Forgejo/Codeberg**
(pas GitHub/GitLab) ; se référer à `jenkins-casc.yaml` pour l'URL et les branches
exactes.

### 2. Credentials requis (aperçu — voir `jenkins-casc.yaml` pour la liste à jour)

| ID Credential | Type | Usage |
|---------------|------|-------|
| `sops-age-key` | Secret file | Déchiffrement des secrets SOPS |
| `kubeconfig-stagingkub` | Secret file | RHDemo-CD (`jenkins-deployer`) |
| `kubeconfig-stagingkub-infra-upgrader` | Secret file | RHDemo-Stagingkub-Upgrade-Deploy (`jenkins-infra-upgrader`) |
| Token API Forgejo + clé GPG | — | RHDemo-Renovate (rebase/merge/commentaires, commits signés) |

### 3. Outils globaux

| Outil | Version |
|-------|---------|
| JDK | **25** (Temurin) |
| Maven | via `mvnw` (wrapper) |
| Helm (agent) | **4.2.x** (`HELM_VERSION` dans `Dockerfile.agent`) |

### 4. Déclenchement

Jenkins **n'est pas exposé sur Internet** : pas de webhook entrant depuis
Forgejo. RHDemo-CI se déclenche par **polling SCM** sur les branches
d'évolution ; RHDemo-Renovate par **cron**. Les statuts CI ne remontent pas
vers Forgejo (`prCreation: immediate`), d'où le merge des PR piloté côté
Jenkins (cf. RENOVATE_AUTOMERGE_CI.md).

---

## 📊 Comparaison des pipelines

| Critère | Jenkinsfile-CI | Jenkinsfile-CD | Jenkinsfile-Renovate | Jenkinsfile-Stagingkub-Upgrade-Deploy |
|---------|----------------|----------------|----------------------|---------------------------------------|
| **Objectif** | Build + tests + scans + publish | Deploy Helm sur K8s | Scan + PR + automerge deps | Upgrade en place d'un composant infra |
| **Durée indicative** | ~2 h max | ~30 min max | ~10-15 min | quelques min/composant |
| **Environnements** | ephemere (Docker Compose) | stagingkub (K8s) | agent éphémère | stagingkub (K8s) |
| **Tests** | Unitaires, IT, Selenium, ZAP | Health + smoke | Build + OWASP par PR | dry-run pré-merge, health post-upgrade |
| **Déclenchement** | SCM (branches d'évolution) | Manuel | Cron | Post-merge PR infra |
| **ServiceAccount K8s** | — | `jenkins-deployer` | — | `jenkins-infra-upgrader` |

---

## 🐛 Dépannage

### Problème : "Registry trouvé 'XXX' mais le nom attendu est 'kind-registry'"

**Cause** : Le registry Docker n'a pas le nom standardisé `kind-registry`.

**Solution** :
```bash
# Arrêter et supprimer le registry avec le mauvais nom
docker stop <mauvais-nom> && docker rm <mauvais-nom>

# Recréer le registry avec le bon nom
cd rhDemo/infra/jenkins-docker
docker-compose up -d registry

# Vérifier
docker ps --filter "publish=5000" --format '{{.Names}}'
# DOIT afficher: kind-registry
```

### Problème : Image not found dans le registry

**Cause** : Le pipeline CI n'a pas publié l'image ou le tag est incorrect.

**Solution** :
```bash
# Vérifier les images disponibles dans le registry
curl -s http://localhost:5000/v2/rhdemo-api/tags/list

# Relancer le pipeline CI avec PUBLISH_IMAGE=true
```

### Problème : Pods not ready après 10 minutes

**Cause** : Erreur de configuration ou ressources insuffisantes.

**Solution** :
```bash
# Vérifier les logs des pods
kubectl logs -n rhdemo-stagingkub <pod-name>

# Vérifier les événements
kubectl get events -n rhdemo-stagingkub --sort-by='.lastTimestamp'

# Vérifier les ressources
kubectl top nodes
kubectl top pods -n rhdemo-stagingkub
```

### Problème : Health check failed

**Cause** : Application non démarrée ou secrets incorrects.

**Solution** :
```bash
# Vérifier les secrets
kubectl get secrets -n rhdemo-stagingkub

# Vérifier les logs de l'application
kubectl logs -n rhdemo-stagingkub deployment/rhdemo

# Tester l'actuator en local dans le pod
kubectl exec -it <rhdemo-pod> -n rhdemo-stagingkub -- curl http://localhost:9000/actuator/health
```

### Problème : Jenkins ne peut pas accéder au cluster KinD

**Cause** : Jenkins n'est pas connecté au réseau Docker `kind`.

**Solution** :
```bash
# Connecter Jenkins au réseau kind
docker network connect kind <jenkins-container-name>

# Vérifier la connexion
docker exec <jenkins-container-name> ping -c 3 rhdemo-control-plane
```

### Problème : ImagePullBackOff sur les pods Kubernetes

**Cause** : Le registry n'est pas connecté au réseau `kind` ou l'alias DNS `kind-registry` est manquant.

**Solution** :
```bash
# Vérifier la connexion du registry au réseau kind
docker network inspect kind | grep kind-registry

# Vérifier l'alias DNS
docker network inspect kind | grep -A2 kind-registry | grep Aliases

# Reconnecter avec alias si nécessaire
docker network disconnect kind kind-registry 2>/dev/null || true
docker network connect kind kind-registry --alias kind-registry

# Supprimer le pod pour forcer une nouvelle tentative
kubectl delete pod <pod-name> -n rhdemo-stagingkub
```

Voir [REGISTRY.md](REGISTRY.md) et [JENKINS-NETWORK-ANALYSIS.md](JENKINS-NETWORK-ANALYSIS.md) pour plus de détails.

---

## 📚 Documentation complémentaire

- [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md) - Pipeline Renovate et merge automatique
- [STAGINGKUB_REBUILD_PIPELINE.md](STAGINGKUB_REBUILD_PIPELINE.md) - Montées d'infra en place / reconstruction de cluster
- [CICD_JENKINS_VS_FORGEJO_ACTIONS.md](CICD_JENKINS_VS_FORGEJO_ACTIONS.md) - Pourquoi Jenkins plutôt que Forgejo/Woodpecker
- [JENKINS_AGENTS_EPHEMERES.md](JENKINS_AGENTS_EPHEMERES.md) - Agents Jenkins éphémères
- [REGISTRY.md](REGISTRY.md) - Configuration du registry Docker local
- [JENKINS-NETWORK-ANALYSIS.md](JENKINS-NETWORK-ANALYSIS.md) - Analyse des problèmes réseau Jenkins/KinD
- [DATABASE.md](DATABASE.md) - Gestion de la base de données
- [POSTGRESQL_BACKUP_CRONJOBS.md](POSTGRESQL_BACKUP_CRONJOBS.md) - Backups automatiques PostgreSQL
- [../infra/jenkins-docker/README.md](../infra/jenkins-docker/README.md) - Configuration Jenkins complète

---

**Dernière mise à jour** : 2026-08-31 — ajout des pipelines Renovate et
Stagingkub-Upgrade-Deploy, suppression du `Jenkinsfile` monolithique, JDK 25,
Helm 4, notifications email, hébergement Forgejo/Codeberg. Le détail par phase
ci-dessus reflète l'esprit des pipelines ; les fichiers `Jenkinsfile-*` font foi.
