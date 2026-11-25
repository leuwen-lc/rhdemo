---
statut: actif
verifie_le: 2026-11-25
sources:
  - rhDemo/Jenkinsfile-CI
  - rhDemo/vars/rhDemoLib.groovy
  - rhDemo/Jenkinsfile-CD
  - rhDemo/Jenkinsfile-Renovate
  - rhDemo/infra/jenkins-docker/casc/jenkins-casc.yaml
---

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

Le projet RHDemo utilise **cinq pipelines Jenkins distincts** :

| Pipeline | Rôle | Déclenchement | Doc dédiée |
|---|---|---|---|
| **RHDemo-CI** (`Jenkinsfile-CI`) | Build, tests, scans qualité/sécurité, déploiement ephemere, tests Selenium/ZAP, publication image | SCM sur les branches d'évolution | ce document |
| **RHDemo-CD** (`Jenkinsfile-CD`) | Déploiement Helm de l'image validée sur stagingkub (K8s) | Automatique après un build CI réussi qui publie l'image, ou manuel | ce document |
| **RHDemo-Renovate** (`Jenkinsfile-Renovate`) | Scan Renovate, ouverture des PR, build/test/OWASP puis **merge automatique** des PR patch/minor qui passent la CI | Cron | [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md) |
| **RHDemo-Stagingkub-Upgrade-Deploy** (`Jenkinsfile-Stagingkub-Upgrade-Deploy`) | Application réelle (post-merge) des montées de version en place des composants d'infra stagingkub | Après merge d'une PR Renovate d'infra | [STAGINGKUB_REBUILD_PIPELINE.md](etudes/STAGINGKUB_REBUILD_PIPELINE.md) |
| **RHDemo-FixCVE** (`Jenkinsfile-FixCVE`) | Remédiation automatique des CVE bloquantes Trivy/OWASP de la CI, validation ou rollback au build suivant | Fin de chaque build CI (`post { always }`), cron de secours horaire | [FIXCVE_AUTO.md](FIXCVE_AUTO.md) |

Les pipelines envoient une **notification email** (email-ext) : à chaque fin de
build pour la CI et la CD, en cas d'échec ou d'alerte pour les autres. L'ancien `Jenkinsfile` monolithique (CI+CD
mélangés) a été **supprimé**.

Enchaînement CI → CD :

```
┌─────────────────────────────────────────────────────────────────┐
│                       JENKINSFILE-CI                            │
│                  (Intégration Continue)                         │
├─────────────────────────────────────────────────────────────────┤
│ 1. Build & Tests                                               │
│    ├─ Compilation Maven                                        │
│    ├─ Tests unitaires et d'intégration                         │
│    ├─ Tests des scripts (run-all.sh)                           │
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
│    ├─ Scan Trivy des images + SBOM CycloneDX                   │
│    ├─ Tests Selenium                                           │
│    └─ Tests sécurité OWASP ZAP                                 │
│                                                                 │
│ 4. Publication                                                  │
│    ├─ Push de l'image validée vers le registry                 │
│    └─ Signature Cosign (clé Transit d'OpenBao)                 │
│                                                                 │
│ ✅ Résultat: image publiée et signée, CD déclenchée            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Image validée, publiée et signée
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       JENKINSFILE-CD                            │
│                   (Déploiement Continu)                         │
├─────────────────────────────────────────────────────────────────┤
│ 1. Préparation                                                  │
│    ├─ Tag + digest : paramètre ou artefact du build CI         │
│    └─ Vérification de l'image dans le registry                 │
│                                                                 │
│ 2. Configuration Kubernetes                                     │
│    ├─ Connexion au cluster KinD                                │
│    ├─ Vérification de la signature Cosign                      │
│    └─ ExternalSecret synchronisés (ESO, OpenBao)               │
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
- Génération des secrets d'ephemere (valeurs aléatoires à chaque build, jamais stockées)
- Configuration Keycloak

#### Phase 2 : Build et Tests
- Compilation Maven
- Tests unitaires et d'intégration
- Tests des scripts (`rhDemo/scripts/tests/run-all.sh`, hors réseau) : poller fixcve-auto exécuté de bout en bout, rotation des secrets, OpenBao
- Analyse OWASP Dependency-Check
- Analyse SonarQube (optionnel) : SonarQube est démarré au début du stage puis arrêté après la Quality Gate, pour libérer la mémoire du poste (voir `infra/jenkins-docker/README.md`)
- Quality Gate SonarQube (optionnel)
- Couverture de code (JaCoCo)

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

#### Phase 5 : Scans, tests Selenium et OWASP ZAP
- Scan Trivy des images ([TRIVY_SECURITY_SCAN.md](TRIVY_SECURITY_SCAN.md)) et SBOM CycloneDX
- Tests Selenium (optionnel)
- Tests sécurité OWASP ZAP

#### Phase 6 : Publication
- Vérification du nom du registry : **DOIT être `kind-registry`** (sinon échec du pipeline)
- Tag de l'image avec la version finale :
  - **SNAPSHOT** : `<VERSION>-<BUILD_NUMBER>` (ex: `1.1.0-SNAPSHOT-95`)
  - **RELEASE** : `<VERSION>` (ex: `1.0.0-RELEASE`)
- Push vers le registry Docker local (`localhost:5000`) ; pas de tag `latest`
- Tag, digest et référence de l'image écrits dans `image-digest/`, archivés pour la CD
- Signature Cosign par la clé Transit d'OpenBao (AppRole `openbao-cosign-approle`, clé non exportable, voir [OPENBAO.md](OPENBAO.md))
- Nettoyage du registry : seuls les 3 derniers SNAPSHOT sont gardés, les signatures Cosign orphelines sont supprimées, puis garbage collection

#### Phase 7 : Archivage
- Archivage du JAR
- Archivage des rapports (tests, OWASP, ZAP)

#### Fin de build
- Déclenchement de `RHDemo-FixCVE` quel que soit le résultat (sans attendre sa fin)
- Si le build réussit et publie l'image : déclenchement de `RHDemo-CD` avec `CI_BUILD_NUMBER`, pour déployer exactement l'image de ce build
- Notification email

### Paramètres

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `RUN_SELENIUM_TESTS` | Boolean | `true` | Exécuter les tests Selenium |
| `RUN_SONAR` | Boolean | `true` | Exécuter l'analyse SonarQube |
| `PUBLISH_IMAGE` | Boolean | `true` | Publier l'image sur le registry (et déclencher la CD) |
| `SIGN_IMAGE` | Boolean | `true` | Signer l'image avec Cosign après publication |
| `KEEP_EPHEMERE_ENV` | Boolean | `false` | Garder l'environnement ephemere pour le débogage |
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
  - **SNAPSHOT** : `rhdemo-api:1.1.0-SNAPSHOT-95`
  - **RELEASE** : `rhdemo-api:1.0.0-RELEASE`
- `image-digest/` : tag, digest et référence de l'image publiée (lus par la CD)
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
  - **Avec paramètre `IMAGE_TAG`** : utilise le tag spécifié (ex: `1.1.0-SNAPSHOT-95`) ; le digest est lu dans le registry
  - **Sans `IMAGE_TAG`** : tag et digest lus dans l'artefact `image-digest/` du build CI `CI_BUILD_NUMBER` (passé par la CI quand elle déclenche la CD), ou à défaut du dernier build CI réussi (Copy Artifact)
- Secrets applicatifs : plus déchiffrés par le pipeline, créés dans le namespace par External Secrets Operator depuis OpenBao ([OPENBAO.md](OPENBAO.md))

#### Phase 2 : Configuration Kubernetes
- Configuration de l'accès au cluster KinD
- Vérification du nom du registry : **DOIT être `kind-registry`** (sinon échec du pipeline)
- Connexion automatique du registry au réseau `kind` avec alias DNS `kind-registry`
- Vérification de l'image dans le registry
- Vérification de la signature Cosign avec la clé publique Transit (`cosign-public-key-transit`), sauf si `VERIFY_SIGNATURE=false`
- Vérification que les `ExternalSecret` sont synchronisés (lecture seule, aucun secret ne transite par Jenkins)

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
| `IMAGE_TAG` | String | `""` | Tag de l'image à déployer (ex: `1.1.0-SNAPSHOT-95`, `1.0.0-RELEASE`). Si vide : image du build CI `CI_BUILD_NUMBER`, ou du dernier build CI réussi |
| `CI_BUILD_NUMBER` | String | `""` | Build CI dont l'artefact `image-digest/` est lu (posé automatiquement par la CI) |
| `VERIFY_SIGNATURE` | Boolean | `true` | Vérifier la signature Cosign avant le déploiement |
| `FORCE_RECREATE_PODS` | Boolean | `false` | Forcer la recréation des pods (rollout restart) |
| `SKIP_HEALTH_CHECK` | Boolean | `false` | Ne pas attendre les health checks |

### Exemple d'utilisation

```bash
# Cas normal : rien à faire, la CI déclenche la CD avec CI_BUILD_NUMBER

# Redéployer l'image du dernier build CI réussi
# Pas de paramètres

# Déploiement d'une version précise
IMAGE_TAG=1.0.0-RELEASE

# Déploiement avec recréation forcée des pods
IMAGE_TAG=1.1.0-SNAPSHOT-95
FORCE_RECREATE_PODS=true
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
> Forgejo. Voir [CICD_JENKINS_VS_FORGEJO_ACTIONS.md](etudes/CICD_JENKINS_VS_FORGEJO_ACTIONS.md).

---

## 🧱 Jenkinsfile-Stagingkub-Upgrade-Deploy : montées d'infra en place

**Fichier**: [`Jenkinsfile-Stagingkub-Upgrade-Deploy`](../Jenkinsfile-Stagingkub-Upgrade-Deploy) — **doc de référence** : [STAGINGKUB_REBUILD_PIPELINE.md](etudes/STAGINGKUB_REBUILD_PIPELINE.md)

### Objectif

Appliquer réellement, **après merge** d'une PR Renovate d'infra, la montée de
version en place d'un composant du cluster stagingkub (Cilium, NGINX Gateway
Fabric, kube-prometheus-stack, Loki, Grafana Alloy, Grafana) via les scripts
idempotents `infra/stagingkub/scripts/components/install-or-upgrade-<composant>.sh`
(rollback automatique `--rollback-on-failure`, Helm 4).

### Points clés

- La **validation avant merge** est faite dans la boucle étendue de `Jenkinsfile-Renovate` par un `helm upgrade --dry-run=server` / `kubectl apply --dry-run=server`, après une garde qui limite le diff de la PR aux lignes de version et au manifeste officiel des CRD : le script modifié détient un credential capable de muter le cluster, le dry-run seul ne le garantit pas.
- ServiceAccount Kubernetes **dédié** `jenkins-infra-upgrader` (namespace `jenkins-infra`, credential `kubeconfig-stagingkub-infra-upgrader`), distinct de `jenkins-deployer` utilisé par RHDemo-CD. Ses droits en font l'équivalent d'un administrateur du cluster : `RHDemo-Renovate` n'exécute le script d'une PR avec ce credential qu'après la garde des PR d'infra ([RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md)).
- Agent éphémère standard (pas de `docker.sock`, pas de `kind`).
- `kindest/node` (version Kubernetes) reste **hors périmètre** : toute montée K8s passe par une reconstruction complète du cluster (cf. [MIGRATION_HELM4_KUB1.36.md](etudes/MIGRATION_HELM4_KUB1.36.md)).

---

## 🔄 Workflow recommandé

### 1. Développement quotidien

```bash
# À chaque commit/PR
1. git push : RHDemo-CI démarre par polling SCM
2. Vérifier les résultats :
   - Tests unitaires
   - Quality gate SonarQube
   - Tests Selenium
   - Scan sécurité ZAP
3. Si tous les tests passent → image publiée sur le registry
```

### 2. Déploiement sur stagingkub

Automatique : un build CI réussi qui publie l'image déclenche `RHDemo-CD` avec son
numéro de build ; la CD déploie le digest exact de ce build après avoir vérifié sa
signature. Pour redéployer une autre version, lancer `RHDemo-CD` à la main avec
`IMAGE_TAG`. Vérifier ensuite les pods, les health checks et l'accès à l'application.

### 3. Workflow complet

```
git push → RHDemo-CI (polling SCM)
             build, tests, scans, ephemere, Selenium + ZAP
             push rhdemo-api:<version>-<build>, signature Cosign
             │                         └─ fin de build → RHDemo-FixCVE
             ▼ succès + image publiée
           RHDemo-CD (CI_BUILD_NUMBER)
             vérification signature, ExternalSecret, Helm, health checks
             ▼
           https://rhdemo-stagingkub.intra.leuwen-lc.fr
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

**Tag créé par CI** : `rhdemo-api:1.1.0-SNAPSHOT-95` (avec numéro de build unique).

**Raison** : Chaque build SNAPSHOT est unique grâce au numéro de build Jenkins. Cela permet de :
- Tracer exactement quelle version est déployée
- Revenir à un build antérieur si nécessaire
- Éviter les conflits de cache

#### RELEASE (production)

```xml
<!-- Dans pom.xml -->
<version>1.0.0-RELEASE</version>
```

**Tag créé par CI** : `rhdemo-api:1.0.0-RELEASE` (version fixe, sans numéro de build).

Aucun tag `latest` n'est publié : la CD déploie toujours un tag précis, et vérifie la signature de son digest.

### Politique de pull (imagePullPolicy)

Le pipeline CD adapte automatiquement la politique de pull selon le tag :

| Tag | imagePullPolicy | Raison |
|-----|----------------|--------|
| contient `SNAPSHOT` | `Always` | Force le pull pour éviter d'utiliser une version en cache |
| autre (`*-RELEASE`) | `IfNotPresent` | Version fixe, peut utiliser le cache |

### Nettoyage automatique du registry

Le pipeline CI nettoie automatiquement les anciennes images SNAPSHOT pour économiser l'espace disque :

- **Politique de rétention** : Garde les 3 derniers builds SNAPSHOT
- **Signatures Cosign** : cosign range la signature d'une image sous le tag `sha256-<digest>` ; toute signature dont le digest ne correspond plus à aucune image taguée est supprimée (sans cette passe, les signatures des SNAPSHOT supprimés s'accumulaient : 334 constatées le 2026-11-22)
- **Garbage collection** : `registry garbage-collect` sur `/etc/distribution/config.yml` (emplacement de `registry:3`), lancé à chaque build, même sans SNAPSHOT à supprimer
- **Images RELEASE** : Jamais supprimées automatiquement, leurs signatures sont conservées

**Exemple** :
```
Avant build #98 :
  - rhdemo-api:1.1.0-SNAPSHOT-95
  - rhdemo-api:1.1.0-SNAPSHOT-96
  - rhdemo-api:1.1.0-SNAPSHOT-97

Après build #98 :
  - rhdemo-api:1.1.0-SNAPSHOT-96
  - rhdemo-api:1.1.0-SNAPSHOT-97
  - rhdemo-api:1.1.0-SNAPSHOT-98
```

---

## ⚙️ Configuration Jenkins

### 1. Création des jobs Jenkins

#### Option A : Configuration automatique (JCasC - Recommandé)

Le fichier [infra/jenkins-docker/casc/jenkins-casc.yaml](../infra/jenkins-docker/casc/jenkins-casc.yaml) configure **automatiquement** les cinq jobs au démarrage de Jenkins.

**Avantages** :
- ✅ Configuration versionnée dans Git
- ✅ Déploiement reproductible
- ✅ Pas de configuration manuelle

Les jobs créés automatiquement : `RHDemo-CI`, `RHDemo-CD`, `RHDemo-Renovate`,
`RHDemo-Stagingkub-Upgrade-Deploy`, `RHDemo-FixCVE`. Le dépôt est hébergé sur **Forgejo/Codeberg**
(pas GitHub/GitLab) ; se référer à `jenkins-casc.yaml` pour l'URL et les branches
exactes.

### 2. Credentials requis (aperçu — voir `jenkins-casc.yaml` pour la liste à jour)

| ID Credential | Type | Usage |
|---------------|------|-------|
| `openbao-approle` | Vault App Role | Plugin HashiCorp Vault : lecture de `kv/jenkins/*` ([OPENBAO.md](OPENBAO.md)) |
| `openbao-cosign-approle` | Username with password | RHDemo-CI : signature Cosign par la clé Transit d'OpenBao |
| `cosign-public-key-transit` | Secret file | RHDemo-CD : vérification de signature |
| `kubeconfig-stagingkub` | Secret file | RHDemo-CD (`jenkins-deployer`) |
| `kubeconfig-stagingkub-infra-upgrader` | Secret file | RHDemo-Stagingkub-Upgrade-Deploy (`jenkins-infra-upgrader`) |
| `renovate-forgejo-token`, `renovate-gpg-key`, `renovate-github-token`, `dockerhub-renovate-readonly`, `ci-bot-forgejo-token` | Références OpenBao | RHDemo-Renovate ([RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md#comptes-et-credentials)) |
| `fixcve-forgejo-token`, `fixcve-jenkins-api` | Références OpenBao | RHDemo-FixCVE (push du bot, lecture des builds CI) |

### 3. Outils globaux

| Outil | Version |
|-------|---------|
| JDK | **25** (Temurin) |
| Maven | via `mvnw` (wrapper) |
| Helm (agent) | **4** (version exacte : `HELM_VERSION` dans `Dockerfile.agent`) |

### 4. Déclenchement

Jenkins **n'est pas exposé sur Internet** : pas de webhook entrant depuis
Forgejo. RHDemo-CI se déclenche par **polling SCM** sur les branches
d'évolution ; RHDemo-Renovate par **cron** ; RHDemo-FixCVE à la fin de chaque build CI ; RHDemo-CD après un build CI réussi qui publie l'image. Les statuts CI ne remontent pas
vers Forgejo (`prCreation: immediate`), d'où le merge des PR piloté côté
Jenkins (cf. RENOVATE_AUTOMERGE_CI.md).

---

## 📊 Comparaison des pipelines

| Critère | Jenkinsfile-CI | Jenkinsfile-CD | Jenkinsfile-Renovate | Jenkinsfile-Stagingkub-Upgrade-Deploy | Jenkinsfile-FixCVE |
|---------|----------------|----------------|----------------------|---------------------------------------|--------------------|
| **Objectif** | Build + tests + scans + publish | Deploy Helm sur K8s | Scan + PR + automerge deps | Upgrade en place d'un composant infra | Remédiation des CVE bloquantes de la CI |
| **Durée indicative** | ~8 min (timeout 2 h) | ~2 min (timeout 30 min) | ~10-15 min | quelques min/composant | timeout 30 min |
| **Environnements** | ephemere (Docker Compose) | stagingkub (K8s) | agent éphémère | stagingkub (K8s) | agent `fixcve` (sans socket Docker) |
| **Tests** | Unitaires, IT, Selenium, ZAP | Health + smoke | Build + OWASP par PR | dry-run pré-merge, health post-upgrade | rescan local OWASP, preuve par le build CI suivant |
| **Déclenchement** | SCM (branches d'évolution) | Fin de CI réussie, ou manuel | Cron | Post-merge PR infra | Fin de chaque build CI, cron de secours |
| **ServiceAccount K8s** | — | `jenkins-deployer` | — | `jenkins-infra-upgrader` | — |

Les durées sont celles d'une exécution normale, sans contention de ressources sur la machine (le projet tourne sur un seul PC). Les valeurs « timeout » de la CI et de la CD sont les garde-fous définis dans `options { timeout(...) }` des Jenkinsfile : elles ne sont atteintes qu'en cas de forte contention ou de blocage, et ne représentent pas la durée habituelle.

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
# Vérifier les secrets (créés par ESO depuis OpenBao)
kubectl get externalsecrets,secrets -n rhdemo-stagingkub

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

Voir [REGISTRY.md](REGISTRY.md) et [JENKINS-NETWORK-ANALYSIS.md](etudes/JENKINS-NETWORK-ANALYSIS.md) pour plus de détails.

---

## 📚 Documentation complémentaire

- [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md) - Pipeline Renovate et merge automatique
- [STAGINGKUB_REBUILD_PIPELINE.md](etudes/STAGINGKUB_REBUILD_PIPELINE.md) - Montées d'infra en place / reconstruction de cluster
- [CICD_JENKINS_VS_FORGEJO_ACTIONS.md](etudes/CICD_JENKINS_VS_FORGEJO_ACTIONS.md) - Pourquoi Jenkins plutôt que Forgejo/Woodpecker
- [JENKINS_AGENTS_EPHEMERES.md](etudes/JENKINS_AGENTS_EPHEMERES.md) - Agents Jenkins éphémères
- [REGISTRY.md](REGISTRY.md) - Configuration du registry Docker local
- [JENKINS-NETWORK-ANALYSIS.md](etudes/JENKINS-NETWORK-ANALYSIS.md) - Analyse des problèmes réseau Jenkins/KinD
- [DATABASE.md](DATABASE.md) - Gestion de la base de données
- [POSTGRESQL_BACKUP_CRONJOBS.md](POSTGRESQL_BACKUP_CRONJOBS.md) - Backups automatiques PostgreSQL
- [../infra/jenkins-docker/README.md](../infra/jenkins-docker/README.md) - Configuration Jenkins complète

---

**Dernière mise à jour** : 2026-11-22 — job RHDemo-FixCVE, secrets par OpenBao et ESO,
signature Cosign par Transit, CD déclenchée par la CI sur le digest du build (pas de tag `latest`). Le détail par phase
ci-dessus reflète l'esprit des pipelines ; les fichiers `Jenkinsfile-*` font foi.
