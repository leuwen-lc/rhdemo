# 🔄 Pipelines CI/CD - RHDemo

Ce document décrit l'architecture des pipelines CI/CD pour le projet RHDemo.

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Jenkinsfile-CI : Intégration Continue](#jenkinsfile-ci--intégration-continue)
- [Jenkinsfile-CD : Déploiement Continu](#jenkinsfile-cd--déploiement-continu)
- [Jenkinsfile (Déprécié)](#jenkinsfile-déprécié)
- [Workflow recommandé](#workflow-recommandé)
- [Configuration Jenkins](#configuration-jenkins)

---

## 🎯 Vue d'ensemble

Le projet RHDemo utilise **deux pipelines Jenkins distincts** pour séparer les responsabilités CI et CD :

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
│    ├─ Déploiement environnement staging Docker                 │
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
- Démarrage de l'environnement staging (Docker Compose)
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
- Tag de l'image avec la version finale
- Push vers le registry Docker local

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

- Image Docker : `rhdemo-api:<VERSION>[<SUFFIX>]`
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
- Détermination de la version de l'image à déployer
- Déchiffrement des secrets SOPS
- Extraction des secrets applicatifs

#### Phase 2 : Configuration Kubernetes
- Configuration de l'accès au cluster KinD
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
| `IMAGE_TAG` | String | `""` | Tag de l'image à déployer. Si vide, utilise la version de `pom.xml` |
| `FORCE_RECREATE_PODS` | Boolean | `false` | Forcer la recréation des pods (rollout restart) |
| `SKIP_HEALTH_CHECK` | Boolean | `false` | Ne pas attendre les health checks |

### Exemple d'utilisation

```bash
# Déploiement de la dernière version (depuis pom.xml)
# Pas de paramètres nécessaires

# Déploiement d'une version spécifique
IMAGE_TAG=1.1.0-SNAPSHOT

# Déploiement avec recréation forcée des pods
IMAGE_TAG=1.1.0-SNAPSHOT
FORCE_RECREATE_PODS=true

# Déploiement rapide sans health checks
IMAGE_TAG=1.1.0-SNAPSHOT
SKIP_HEALTH_CHECK=true
```

### Pré-requis

1. **Cluster KinD initialisé** :
   ```bash
   cd rhDemo/infra/stagingkub/scripts
   ./init-stagingkub.sh
   ```

2. **Image Docker publiée** : L'image doit exister dans le registry local (port 5000).

3. **Namespace créé** : Le namespace `rhdemo-staging` doit exister avec les labels Helm.

### URLs d'accès

Après un déploiement réussi :

- **Application RHDemo** : https://rhdemo.staging.local
- **Keycloak** : https://keycloak.staging.local

---

## ⚠️ Jenkinsfile (Déprécié)

**Fichier**: [`Jenkinsfile`](../Jenkinsfile)

### Statut

Ce fichier est **déprécié** et **ne doit plus être utilisé**.

Il est conservé pour compatibilité temporaire mais **sera supprimé dans une version future**.

### Pourquoi déprécié ?

1. **Trop complexe** : Mélange CI et CD dans un seul fichier (~2000 lignes)
2. **Difficult à maintenir** : Logique imbriquée avec conditions multiples
3. **Stages fictifs** : Contenait des simulations de production inutiles
4. **Manque de séparation des responsabilités** : CI et CD doivent être séparés

### Migration

- **Remplacer** par **Jenkinsfile-CI** pour la construction et les tests
- **Remplacer** par **Jenkinsfile-CD** pour le déploiement Kubernetes

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
# Après un build CI réussi
1. Noter le tag de l'image publiée (ex: 1.1.0-SNAPSHOT)
2. Déclencher Jenkinsfile-CD avec le paramètre IMAGE_TAG
3. Vérifier le déploiement :
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
┌──────────────────────────────────────┐
│     Jenkinsfile-CI (automatique)     │
│  - Build                             │
│  - Tests                             │
│  - Docker build                      │
│  - Tests Selenium + ZAP              │
│  - Publish image                     │
└──────┬───────────────────────────────┘
       │
       │ ✅ Image publiée : rhdemo-api:1.1.0-SNAPSHOT
       │
       ▼
┌──────────────────────────────────────┐
│     Jenkinsfile-CD (manuel)          │
│  Paramètre: IMAGE_TAG=1.1.0-SNAPSHOT │
│  - Pull image                        │
│  - Deploy Helm                       │
│  - Health checks                     │
└──────┬───────────────────────────────┘
       │
       │ ✅ Déployé sur stagingkub
       │
       ▼
┌──────────────────────────────────────┐
│  Application accessible              │
│  - https://rhdemo.staging.local      │
│  - https://keycloak.staging.local    │
└──────────────────────────────────────┘
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

Les jobs créés automatiquement :
- `RHDemo-CI` : Pipeline d'Intégration Continue
- `RHDemo-CD` : Pipeline de Déploiement Continu
- `rhdemo-pipeline-deprecated` : Ancien pipeline (désactivé)

#### Option B : Configuration manuelle

Si vous n'utilisez pas JCasC, créez manuellement :

**Pipeline CI**

```groovy
// Nom : RHDemo-CI
// Type : Pipeline
// Pipeline script from SCM :
//   - Repository : https://github.com/votre-repo/rhDemo.git
//   - Branch : */evol-kub
//   - Script Path : rhDemo/Jenkinsfile-CI
```

**Pipeline CD**

```groovy
// Nom : RHDemo-CD
// Type : Pipeline
// Pipeline script from SCM :
//   - Repository : https://github.com/votre-repo/rhDemo.git
//   - Branch : */evol-kub
//   - Script Path : rhDemo/Jenkinsfile-CD
// Build with Parameters : ✅ Activé
```

### 2. Credentials requis

| ID Credential | Type | Description |
|---------------|------|-------------|
| `sops-age-key` | Secret file | Clé AGE pour déchiffrer les secrets SOPS |

### 3. Outils globaux

| Outil | Nom | Version |
|-------|-----|---------|
| JDK | `JDK21` | OpenJDK 21 |
| Maven | `Maven3` | Maven 3.9+ |

### 4. Plugins requis

- Pipeline
- Git
- Docker Pipeline
- SonarQube Scanner (optionnel)
- HTML Publisher
- JUnit

### 5. Webhooks (optionnel)

Pour déclencher automatiquement le pipeline CI :

```bash
# GitHub Webhook
URL : https://your-jenkins.com/github-webhook/
Events : Push events

# GitLab Webhook
URL : https://your-jenkins.com/project/RHDemo-CI
Trigger : Push events
```

---

## 📊 Comparaison des pipelines

| Critère | Jenkinsfile-CI | Jenkinsfile-CD | Jenkinsfile (déprécié) |
|---------|----------------|----------------|------------------------|
| **Objectif** | Build + Tests + Publish | Deploy Kubernetes | Tout (CI + CD + Prod fictif) |
| **Durée moyenne** | 20-30 min | 5-10 min | 30-40 min |
| **Environnements** | Staging Docker Compose | Kubernetes stagingkub | Les deux + prod fictif |
| **Tests** | Unitaires, Selenium, ZAP | Health checks | Unitaires, Selenium, ZAP |
| **Artifacts** | JAR + Image Docker + Rapports | - | JAR + Image Docker + Rapports |
| **Déclenchement** | Automatique (push) | Manuel | Automatique ou manuel |
| **Paramètres** | 4 | 3 | 8+ |
| **Lignes de code** | ~950 | ~600 | ~2000 |
| **Maintenance** | ✅ Facile | ✅ Facile | ❌ Difficile |

---

## 🐛 Dépannage

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
kubectl logs -n rhdemo-staging <pod-name>

# Vérifier les événements
kubectl get events -n rhdemo-staging --sort-by='.lastTimestamp'

# Vérifier les ressources
kubectl top nodes
kubectl top pods -n rhdemo-staging
```

### Problème : Health check failed

**Cause** : Application non démarrée ou secrets incorrects.

**Solution** :
```bash
# Vérifier les secrets
kubectl get secrets -n rhdemo-staging

# Vérifier les logs de l'application
kubectl logs -n rhdemo-staging deployment/rhdemo

# Tester l'actuator en local dans le pod
kubectl exec -it <rhdemo-pod> -n rhdemo-staging -- curl http://localhost:9000/actuator/health
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

---

## 📚 Documentation complémentaire

- [DATABASE.md](../DATABASE.md) - Gestion de la base de données
- [JENKINS_SETUP.md](../bin/JENKINS_SETUP.md) - Configuration Jenkins complète
- [JENKINSFILE_REFACTORING.md](JENKINSFILE_REFACTORING.md) - Historique du refactoring (si existant)

---

**Dernière mise à jour** : 2025-12-12
**Auteur** : Migration automatisée via Claude Code
