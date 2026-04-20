# Agents Jenkins Éphémères — Étude d'Impact et Plan de Migration

## Contexte et objectif

Les agents éphémères Jenkins sont un principe de sécurité fondamental : chaque build s'exécute dans un conteneur neuf, détruit immédiatement après. Cela élimine l'accumulation d'état entre les builds (résidus de fichiers, tokens en mémoire, dépendances implicites) et réduit considérablement la surface d'attaque en cas de compromission d'un build.

Ce document analyse l'écart entre l'architecture actuelle et une architecture à agents éphémères, et détaille les étapes de migration.

---

## 1. Architecture actuelle

### Agent permanent "builder"

L'agent actuel (`rhdemo-jenkins-agent`) est un conteneur Docker permanent avec `restart: on-failure` et `retentionStrategy: "always"` dans JCasC. Il est unique et partagé entre tous les builds.

```
jenkins-controller (0 exécuteurs)
    └── builder (2 exécuteurs, permanent, toujours actif)
         ├── Docker socket : /var/run/docker.sock
         ├── Volume workspace : rhdemo-jenkins-agent-workspace
         └── Volume Maven cache : rhdemo-maven-repository
```

**Outils installés dans l'image** (`Dockerfile.agent`) :
- JDK 25 (Eclipse Temurin), Maven 3.9.12
- Docker CLI, docker-compose
- SOPS 3.11.0, yq, jq
- Trivy (scanner Trivy)
- kubectl, Helm 3.20.0, Cosign 3.0.4
- Firefox ESR + Xvfb (tests Selenium headless)
- Node.js / npm

### Risques identifiés de l'agent permanent

| Risque | Niveau | Description |
|--------|--------|-------------|
| Contamination inter-builds | Moyen | Fichiers résiduels, variables d'environnement, processus orphelins entre builds successifs |
| Élévation de privilèges | Élevé | Accès permanent au socket Docker `/var/run/docker.sock` — compromission d'un build = accès à tous |
| Fuite de secrets | Élevé | Secrets déchiffrés par SOPS dans `/tmp` — un build suivant peut lire les résidus si nettoyage manque |
| Surface d'attaque | Moyen | L'agent contient Firefox, kubectl, Cosign, Helm, Trivy — image très large toujours active |
| Builds concurrents | Moyen | 2 exécuteurs sur le même agent → collisions possibles sur `/tmp/rhdemo-secrets-*` si `BUILD_NUMBER` réutilisé |

---

## 2. Impact par composant

### 2.1 `jenkins-casc.yaml` — Configuration JCasC

**Ce qui change :**

Le nœud permanent `builder` avec `retentionStrategy: "always"` est remplacé par un **Docker Cloud** configuré pour créer des agents à la demande via le plugin Docker.

```yaml
# AVANT
nodes:
  - permanent:
      name: "builder"
      retentionStrategy: "always"
      launcher:
        inbound:
          webSocket: true

# APRÈS
# Supprimer la section nodes (plus d'agent permanent)
# Ajouter une configuration Docker Cloud (voir étape 3)
```

Le contrôleur Jenkins doit lui-même avoir accès au socket Docker pour piloter la création des agents. Cela implique de monter `/var/run/docker.sock` dans le conteneur Jenkins controller (actuellement absent du `docker-compose.yml`).

### 2.2 `docker-compose.yml`

**Ce qui change :**

| Élément | Avant | Après |
|---------|-------|-------|
| Service `jenkins-agent` | Démarré en permanence | Retiré (ou conservé comme image de référence uniquement, non démarré) |
| Service `jenkins` | Pas de Docker socket | Ajout du montage `/var/run/docker.sock` |
| Volume `jenkins_agent_workspace` | Monté dans l'agent permanent | Configuré dans le template du Docker Cloud |
| Volume `maven_repository` | Monté dans l'agent permanent | Monté via Docker Cloud template (volume partagé entre builds) |

```yaml
# Ajout dans le service jenkins :
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  - /usr/bin/docker:/usr/bin/docker
```

> ⚠️ Monter le socket Docker dans le controller Jenkins est un compromis sécurité. L'alternative (un Docker daemon dédié accessible via TCP) est plus propre mais plus complexe à mettre en place sur un seul PC.

### 2.3 `Jenkinsfile-CI` — Points d'impact

#### ✅ Ce qui fonctionne sans modification

- `agent { label 'builder' }` : inchangé si le template Docker Cloud utilise le même label
- Déchiffrement SOPS dans `/tmp/rhdemo-secrets-${BUILD_NUMBER}` : chaque conteneur a son propre `/tmp`, isolation parfaite
- `withCredentials(...)` : géré par le controller, transmis à l'agent, inchangé
- `dir('rhDemo') { sh './mvnw ...' }` : inchangé
- Build de l'image Docker avec `docker build` : fonctionne si le socket est monté dans l'agent éphémère

#### ⚠️ Ce qui nécessite une attention particulière

**Pattern `docker network connect $(hostname)`** (lignes 758-763 CI, lignes 296-350 CD) :

```groovy
// Extrait actuel Jenkinsfile-CI
AGENT_CONTAINER=$(hostname)
docker network connect ${env.NETWORK_EPHEMERE} $AGENT_CONTAINER
```

Ce pattern utilise `hostname` pour obtenir le nom du conteneur agent. Avec un agent éphémère Docker, `hostname` retourne le court hash du conteneur (ex: `a1b2c3d4e5f6`), pas un nom stable. La commande `docker network connect` accepte un hash de conteneur — **ce pattern continue donc de fonctionner avec les agents éphémères sans modification**.

**Cache Trivy** (ligne ~1097 CI) :

```groovy
TRIVY_CACHE_DIR="$(pwd)/.trivy-cache-shared"
```

Ce cache est stocké dans le workspace. Avec un agent éphémère, ce cache est recréé à chaque build, ce qui ralentit les scans (re-téléchargement de la DB Trivy, ~300 Mo). **Solution** : monter un volume Docker dédié pour le cache Trivy dans le template d'agent.

**Cache Maven** :

Actuellement monté via le volume `maven_repository`. Sans ce volume dans le template d'agent, Maven re-télécharge toutes les dépendances à chaque build (~500 Mo, +5 minutes). **Solution** : configurer ce volume dans le template Docker Cloud.

**`load 'rhDemo/vars/rhDemoLib.groovy'`** :

Charge une bibliothèque Groovy depuis le workspace. Dépend du checkout SCM préalable. Fonctionne avec les agents éphémères car le checkout est la première étape du pipeline.

#### ❌ Ce qui doit être modifié

**Nettoyage de l'environnement éphémère Docker Compose** (post-stage) :

```groovy
// Extrait actuel
docker network disconnect ${env.NETWORK_EPHEMERE} $AGENT_CONTAINER
```

Avec un agent éphémère, ce nettoyage reste fonctionnel pendant l'exécution. Cependant, si le build échoue avant ce point, le réseau ephemere reste actif. Avec un agent éphémère détruit, la connexion réseau disparaît automatiquement à la destruction du conteneur — c'est en réalité **plus propre** qu'actuellement.

### 2.4 `Jenkinsfile-CD` — Points d'impact

#### ✅ Sans modification

- Déchiffrement SOPS : identique au CI
- `kubectl` et `helm` : disponibles dans l'image agent, inchangés
- `withCredentials([file(credentialsId: 'kubeconfig-stagingkub', ...)])` : inchangé

#### ⚠️ Attention

**Connexion au réseau Kind** (lignes 295-351 CD) :

```groovy
JENKINS_CONTAINER=$(hostname)
docker network connect kind $JENKINS_CONTAINER
```

Même analyse que le CI — fonctionne avec les agents éphémères. La déconnexion en `post { always { ... } }` est également gérée correctement.

**Accès au registry local** :

L'agent doit voir `kind-registry:5000`. Ce résolveur DNS est géré par le réseau Docker `rhdemo-jenkins-network`. Le conteneur agent éphémère doit être démarré sur ce réseau dans sa configuration template.

---

## 3. Plan de migration étape par étape

### Étape 1 — Installer le plugin Docker pour Jenkins

Dans `plugins.txt`, ajouter :

```
docker-plugin:latest
docker-workflow:latest
```

Reconstruire l'image Jenkins controller et redémarrer.

### Étape 2 — Monter le socket Docker dans le controller

Dans `docker-compose.yml`, service `jenkins`, ajouter :

```yaml
volumes:
  - jenkins_home:/var/jenkins_home
  - ./jenkins-casc.yaml:/var/jenkins_home/casc_configs/jenkins.yaml:ro
  # Ajout pour le Docker Cloud
  - /var/run/docker.sock:/var/run/docker.sock
  - /usr/bin/docker:/usr/bin/docker
group_add:
  - 984  # GID du groupe docker sur l'hôte
```

### Étape 3 — Configurer le Docker Cloud dans JCasC

Dans `jenkins-casc.yaml`, remplacer la section `nodes:` par une configuration Docker Cloud :

```yaml
jenkins:
  numExecutors: 0
  mode: EXCLUSIVE
  # Supprimer la section nodes: - permanent:

clouds:
  - docker:
      name: "docker-local"
      dockerApi:
        dockerHost:
          uri: "unix:///var/run/docker.sock"
      templates:
        - labelString: "builder"
          dockerTemplateBase:
            image: "rhdemo-jenkins-agent:latest"
            # Volumes : cache Maven et Trivy partagés entre builds (performance)
            volumes:
              - "rhdemo-maven-repository:/home/jenkins/.m2"
              - "rhdemo-trivy-cache:/home/jenkins/.cache/trivy"
              # Socket Docker pour les commandes docker/docker-compose du pipeline
              - "/var/run/docker.sock:/var/run/docker.sock"
              - "/usr/bin/docker:/usr/bin/docker"
            # Connecter l'agent au réseau Jenkins pour accès au registry
            network: "rhdemo-jenkins-network"
            # GID du groupe docker
            group_add:
              - "984"
          remoteFs: "/home/jenkins/agent"
          connector:
            attach:
              user: "jenkins"
          instanceCapStr: "3"
          # L'agent est détruit dès que le build est terminé
          removeVolumes: false   # conserver les volumes de cache
          pullStrategy: PULL_NEVER  # l'image est construite localement
```

> **Note `PULL_NEVER`** : L'image `rhdemo-jenkins-agent:latest` est construite localement par `docker-compose build`. Le Docker Cloud ne doit pas tenter de la télécharger depuis un registry externe.

### Étape 4 — Créer le volume de cache Trivy

```bash
docker volume create rhdemo-trivy-cache
```

Ajouter ce volume dans `docker-compose.yml` section `volumes:` :

```yaml
volumes:
  # ... volumes existants
  rhdemo-trivy-cache:
    name: rhdemo-trivy-cache
    driver: local
```

### Étape 5 — Adapter le cache Trivy dans `Jenkinsfile-CI`

Modifier la variable `TRIVY_CACHE_DIR` pour pointer vers le cache monté dans l'agent :

```groovy
// AVANT
TRIVY_CACHE_DIR="$(pwd)/.trivy-cache-shared"

// APRÈS
TRIVY_CACHE_DIR="/home/jenkins/.cache/trivy"
```

Cette modification est localisée dans le stage `🔍 Scan Sécurité Images Docker (Trivy)`.

### Étape 6 — Arrêter le service `jenkins-agent` permanent

Une fois le Docker Cloud opérationnel, le service `jenkins-agent` dans `docker-compose.yml` n'est plus nécessaire comme service démarré. Deux options :

**Option A (recommandée)** : Supprimer le service `jenkins-agent` du `docker-compose.yml`. L'image reste constructible avec `docker-compose build jenkins-agent` pour référence.

**Option B** : Le commenter et le conserver comme documentation de l'image.

### Étape 7 — Supprimer le nœud permanent de JCasC

Dans `jenkins-casc.yaml`, supprimer entièrement :

```yaml
# À supprimer
nodes:
  - permanent:
      name: "builder"
      ...
```

### Étape 8 — Mettre à jour les variables d'environnement dans le pipeline (optionnel)

Le nom `COMPOSE_PROJECT_NAME` inclut `${env.BUILD_NUMBER}` pour l'isolation. Avec des agents éphémères, les builds concurrents sont mieux isolés. Vérifier que la variable `COMPOSE_PROJECT_NAME = "rhdemo-ephemere-${env.BUILD_NUMBER}"` est bien définie avant le premier `docker-compose` (c'est déjà le cas).

### Étape 9 — Tests de validation

Après migration, valider dans cet ordre :

1. Déclencher un build CI et vérifier que l'agent éphémère est créé dans Docker : `docker ps | grep jenkins`
2. Vérifier que le workspace est correctement peuplé après checkout
3. Vérifier que le cache Maven est utilisé (second build plus rapide que le premier)
4. Vérifier que le cache Trivy est utilisé (pas de re-téléchargement de la DB)
5. Vérifier que les connexions réseau ephemere fonctionnent (stage `🔗 Connexion Agent au Réseau Staging`)
6. Vérifier la destruction automatique du conteneur agent après le build : `docker ps | grep jenkins` (doit disparaître)
7. Déclencher un build CD et valider le déploiement Kubernetes complet

---

## 4. Récapitulatif des modifications par fichier

| Fichier | Type de modification | Complexité |
|---------|---------------------|------------|
| `plugins.txt` | Ajout de `docker-plugin`, `docker-workflow` | Faible |
| `docker-compose.yml` | Montage socket dans jenkins controller, ajout volume trivy-cache, retrait service jenkins-agent | Faible |
| `jenkins-casc.yaml` | Remplacement `nodes: permanent` par `clouds: docker` | Moyenne |
| `Jenkinsfile-CI` | Modification `TRIVY_CACHE_DIR` uniquement | Faible |
| `Jenkinsfile-CD` | Aucune modification requise | Nulle |

---

## 5. Bénéfices attendus après migration

| Critère | Avant | Après |
|---------|-------|-------|
| Isolation entre builds | Partielle (même container) | Totale (container neuf) |
| Résidus de secrets entre builds | Possible si nettoyage échoue | Impossible (filesystem détruit) |
| Surface d'attaque | Permanente | Limitée à la durée du build |
| Scalabilité | 2 builds max simultanés (fixes) | Configurable via `instanceCapStr` |
| Nettoyage réseau ephemere | Manuel (post-stage) | Automatique à la destruction |
| Temps de build (cold) | Identique | +2-5 min (init container) |
| Temps de build (warm, caches) | Identique | Identique si volumes montés |

---

## 6. Points de vigilance spécifiques à ce projet

### Docker-in-Docker (DinD)

L'accès au socket Docker `/var/run/docker.sock` reste nécessaire pour les pipelines (docker-compose, docker build, docker network). Ce n'est pas éliminé par les agents éphémères mais **limité dans le temps** à la durée du build. En cas de compromission, la fenêtre d'exposition est réduite.

### Limitation PC 16 Go RAM

Chaque agent éphémère consomme la RAM de l'image Firefox/Selenium (~400 Mo). Avec `instanceCapStr: "3"`, la consommation maximale reste maîtrisée. Ne pas dépasser 2 agents simultanés en pratique compte tenu de l'environnement ephemere Docker Compose qui tourne en parallèle.

### Volume `maven_repository`

Ce volume doit impérativement être monté dans le template Docker Cloud. Sans lui, chaque build CI re-télécharge ~500 Mo de dépendances Maven, rendant le pipeline inutilisable en pratique (~15 min de téléchargements vs ~2 min avec cache).

### Gestion du secret agent Jenkins

Avec le Docker plugin, la connexion controller ↔ agent est gérée automatiquement. Le mécanisme `JENKINS_SECRET` du service permanent (configuré manuellement via l'UI) disparaît — c'est une simplification opérationnelle.
