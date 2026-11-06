---
statut: actif
verifie_le: 2026-11-06
sources:
  - rhDemo/infra/stagingkub/helm/rhdemo/values.yaml
  - rhDemo/infra/ephemere/docker-compose.yml
  - rhDemo/infra/dev/docker-compose.yml
  - rhDemo/infra/jenkins-docker/
  - rhDemo/infra/stagingkub/kind-config.yaml
  - rhDemo/Dockerfile
  - rhDemo/Jenkinsfile-CI
  - renovate.json
---

# Gestion des versions d'images Docker

Toutes les images tierces exécutées par l'application, ses environnements et la CI sont **épinglées par digest** : `image:tag@sha256:<digest>`. Le tag est gardé pour la lisibilité, le digest garantit le contenu. Les montées de version et de digest sont proposées par Renovate puis mergées par Jenkins après validation ([RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md)).

Ce document dit **où** chaque image est déclarée et **comment** elle est mise à jour. Les versions et digests en vigueur se lisent dans les fichiers cités, jamais ici.

## Règles

- **Digest de l'index multi-architecture**, celui que renvoie `docker buildx imagetools inspect <image>:<tag>` (ligne `Digest:`) et que Renovate épingle. Pas le digest d'une seule plateforme.
- **Tag versionné plutôt que flottant** (`3.9.16-…` plutôt que `3.9-…`, `v0.5.0` plutôt que `latest`) : une nouvelle version publiée sous un tag flottant arriverait comme une simple mise à jour de digest, avec un délai de 48 h au lieu de 7 jours. Seule exception : `jenkins/inbound-agent:latest-jdk25` (voir [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md#délai-des-images-docker)).
- **Images prises sur Docker Hub** : c'est le seul registre qui fournit une date de publication à Renovate, nécessaire au délai avant installation. Keycloak, postgres-exporter et ZAP sont publiés à l'identique sur Docker Hub et sur Quay ou ghcr ; on prend Docker Hub.
- **Une annotation Renovate par référence** hors des formats natifs (Dockerfile, Docker Compose) : `# renovate: datasource=docker depName=<image>` sur la ligne qui précède.

## Où sont déclarées les images

### Application et environnements

| Fichier | Images | Suivi Renovate |
| --- | --- | --- |
| [`Dockerfile`](../Dockerfile) | builder `maven`, base d'exécution `eclipse-temurin` | manager natif `dockerfile` |
| [`Jenkinsfile-CI`](../Jenkinsfile-CI) | `NGINX_IMAGE`, `POSTGRES_IMAGE`, `KEYCLOAK_IMAGE` | annotations + `customManagers` de `renovate.json` |
| [`infra/ephemere/docker-compose.yml`](../infra/ephemere/docker-compose.yml) | postgres (×2), keycloak, nginx | manager natif `docker-compose` |
| [`infra/dev/docker-compose.yml`](../infra/dev/docker-compose.yml) | postgres, keycloak | manager natif `docker-compose` |
| [`infra/stagingkub/helm/rhdemo/values.yaml`](../infra/stagingkub/helm/rhdemo/values.yaml) | `global.images` : postgres, keycloak, busybox, postgresExporter | annotations + `customManagers` |
| [`infra/stagingkub/kind-config.yaml`](../infra/stagingkub/kind-config.yaml) | `kindest/node` (version de Kubernetes) | annotation ; **approbation manuelle**, la montée impose une reconstruction du cluster |

Dans ephemere, les images de postgres, keycloak et nginx acceptent une surcharge par variable d'environnement (`${KEYCLOAK_IMAGE:-…}`), dont la valeur par défaut porte le digest. `Jenkinsfile-CI` exporte ses trois variables vers Docker Compose : **les valeurs de `Jenkinsfile-CI` et des fichiers Compose doivent rester identiques**, ce que Renovate assure en les mettant à jour dans la même PR.

Dans stagingkub, `global.images` est la source unique des images tierces du chart `rhdemo` : les templates les consomment par `{{ .Values.global.images.<nom> }}`.

| Template | Images |
| --- | --- |
| `postgresql-rhdemo-statefulset.yaml` | postgres, postgresExporter, busybox |
| `postgresql-keycloak-statefulset.yaml` | postgres, busybox |
| `keycloak-deployment.yaml` | keycloak, busybox |
| `rhdemo-app-deployment.yaml` | busybox |
| `postgresql-backup-cronjob.yaml` | postgres, busybox |

### Usine logicielle (Jenkins)

| Fichier | Images |
| --- | --- |
| [`infra/jenkins-docker/Dockerfile.jenkins`](../infra/jenkins-docker/Dockerfile.jenkins) | `jenkins/jenkins` (contrôleur) |
| [`infra/jenkins-docker/Dockerfile.agent`](../infra/jenkins-docker/Dockerfile.agent) | `jenkins/inbound-agent` (agents) |
| [`infra/jenkins-docker/docker-compose.yml`](../infra/jenkins-docker/docker-compose.yml) | `tecnativa/docker-socket-proxy` |
| [`infra/jenkins-docker/docker-compose.zap.yml`](../infra/jenkins-docker/docker-compose.zap.yml) | `zaproxy/zap-stable` |

Restent **épinglées par tag seulement** : SonarQube, sa base `postgres:18-alpine` et le registre local `registry:3` (`infra/jenkins-docker/docker-compose.yml`), ainsi que l'image `renovate/renovate` (`RENOVATE_IMAGE` de `Jenkinsfile-Renovate`). Renovate les suit par tag, avec le délai de 7 jours des nouvelles versions.

### Composants système de stagingkub

Cilium, NGINX Gateway Fabric, kube-prometheus-stack, Loki, Alloy et Grafana sont installés par Helm à partir des scripts `infra/stagingkub/scripts/components/install-or-upgrade-*.sh`. On y fixe la **version du chart** (variable `*_VERSION` annotée pour Renovate), pas les images : chaque chart référence ses propres images. Ces images sont scannées par Trivy à chaque montée de chart, à partir du rendu `helm template` ([TRIVY_SECURITY_SCAN.md](TRIVY_SECURITY_SCAN.md#périmètre-du-scan)).

Le chart NGF est publié uniquement en OCI sur ghcr, qui ne donne pas de date : Renovate le suit par les releases GitHub `nginx/nginx-gateway-fabric`, dont les versions sont celles du chart. Une montée de `NGF_VERSION` exige aussi les CRDs Gateway API de la nouvelle version (`vendor-gateway-api-crds.sh <version>`, dans la même PR), sinon le script d'installation échoue.

### Image de l'application

`rhdemo-api` est construite par `Jenkinsfile-CI`, signée avec cosign puis publiée sur le registre local `kind-registry` (port 5000). Son tag reprend la version de `pom.xml` (lue par `mvnw help:evaluate`), suivie du numéro de build pour une version `-SNAPSHOT`. `Jenkinsfile-CD` vérifie la signature avant de déployer et passe le tag au chart (`--set rhdemo.image.tag=…`) ; la valeur `rhdemo.image.tag` de `values.yaml` n'est qu'un défaut. Renovate ignore cette image (`matchPackageNames: ["rhdemo-api"]`). Procédure de version : [GIT-PROCEDURE-RELEASE.md](GIT-PROCEDURE-RELEASE.md).

## Mise à jour

**Cas normal : Renovate.** Il ouvre une PR par image (version ou digest), qui met à jour toutes les références à cette image. `Jenkinsfile-Renovate` attend le délai prévu (7 jours pour une version, 48 h pour un digest), valide la PR selon les fichiers qu'elle touche, puis la merge. Les montées majeures et `kindest/node` attendent une approbation dans le tableau de bord Renovate.

La validation avant merge dépend des fichiers ([aiguillage](RENOVATE_AUTOMERGE_CI.md#aiguillage-de-la-validation)) : scan Trivy de l'image seulement si la PR ne touche que `Jenkinsfile-CI` et `values.yaml` (busybox, postgres-exporter) ; dry-run Kubernetes et Trivy pour un composant système. Une PR qui touche aussi un Dockerfile ou un fichier Compose (postgres, keycloak, nginx, images de l'usine logicielle) est mergée **sans scan préalable** : l'image est scannée ensuite par `RHDemo-CI` sur la branche de base, pour celles qu'il couvre.

**Mise à jour manuelle** (correctif urgent, par exemple une CVE critique) :

1. Lire le digest de l'index : `docker buildx imagetools inspect <image>:<tag>`, ligne `Digest:`.
2. Remplacer `tag@digest` dans **tous** les fichiers qui référencent l'image : `git grep -n '<image>:'`.
3. Vérifier le rendu : `helm template` du chart (images de `global.images`) et `docker compose -f <fichier> config` pour les fichiers Compose.
4. Une mise à jour manuelle ne bénéficie pas du délai avant installation : vérifier la date et l'origine de l'image avant de commiter.

Pour une CVE détectée par la CI, `/fixcve` et fixcve-auto savent repiner Keycloak, nginx et postgres ([FIXCVE_AUTO.md](FIXCVE_AUTO.md)).

## Pourquoi épingler par digest ?

Un tag est mutable : l'éditeur, ou un attaquant qui a pris le contrôle de son compte, peut publier un autre contenu sous le même tag. Sans digest, deux déploiements du même fichier peuvent exécuter des images différentes, et une image compromise s'installe au prochain téléchargement. Avec un digest, le contenu est fixé bit à bit, le téléchargement échoue si le registre renvoie autre chose, et l'image déployée reste vérifiable a posteriori. Toute nouvelle image passe alors par une PR : elle est datée, scannée et retardée avant d'être installée.

## Références

- [Docker : pull par digest](https://docs.docker.com/reference/cli/docker/image/pull/#pull-an-image-by-digest-immutable-identifier)
- [Renovate : Docker](https://docs.renovatebot.com/docker/)
- [SLSA](https://slsa.dev/)
