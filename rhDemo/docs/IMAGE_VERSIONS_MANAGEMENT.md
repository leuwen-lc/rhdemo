# Gestion des versions d'images Docker

## Vue d'ensemble

Toutes les images Docker externes du projet sont **épinglées par digest SHA-256** pour garantir l'immuabilité des déploiements. Un tag Docker est mutable (un push upstream peut remplacer son contenu), alors qu'un digest identifie de manière cryptographique le contenu exact d'une image.

**Format utilisé** : `image:tag@sha256:<digest>`

Le tag est conservé pour la lisibilité ; le digest assure l'intégrité.

---

## Table des matières

- [Images externes utilisées](#images-externes-utilisées)
- [Organisation par environnement](#organisation-par-environnement)
- [Procédure de mise à jour d'une image](#procédure-de-mise-à-jour-dune-image)
- [Gestion de la version de RHDemo API](#gestion-de-la-version-de-rhdemo-api)
- [Pourquoi épingler par digest ?](#pourquoi-épingler-par-digest-)

---

## Images externes utilisées

| Image | Usage | Environnements |
|---|---|---|
| `postgres:18.2-alpine3.22` | BDD rhdemo + keycloak, backups | dev, ephemere, stagingkub |
| `quay.io/keycloak/keycloak:26.5.0` | Serveur d'authentification | dev, ephemere, stagingkub |
| `nginx:1.29.4-alpine` | Reverse proxy HTTPS | ephemere, Jenkinsfile-CI |
| `busybox:1.36` | Init containers (fix-permissions, wait-for) | stagingkub |
| `quay.io/prometheuscommunity/postgres-exporter:v0.15.0` | Métriques PostgreSQL | stagingkub |

> **Note** : `rhdemo-api` est l'image applicative construite par le pipeline CI, elle n'est pas concernée par l'épinglage externe.

---

## Organisation par environnement

### Docker Compose (dev, ephemere)

Les images sont référencées directement dans les fichiers Docker Compose avec le digest en suffixe.

**Fichiers** :
- [`infra/dev/docker-compose.yml`](../infra/dev/docker-compose.yml) : postgres, keycloak
- [`infra/ephemere/docker-compose.yml`](../infra/ephemere/docker-compose.yml) : postgres, keycloak, nginx

Les images ephemere acceptent un override via variable d'environnement (ex : `POSTGRES_IMAGE`), la valeur par défaut inclut le digest :

```yaml
image: ${POSTGRES_IMAGE:-postgres:18.2-alpine3.22@sha256:198c...}
```

### Jenkinsfile-CI

Les images sont définies dans les variables d'environnement du pipeline.

**Fichier** : [`Jenkinsfile-CI`](../Jenkinsfile-CI) (variables `NGINX_IMAGE`, `POSTGRES_IMAGE`, `KEYCLOAK_IMAGE`)

```groovy
environment {
    NGINX_IMAGE = "nginx:1.29.4-alpine@sha256:a60a..."
    POSTGRES_IMAGE = "postgres:18.2-alpine3.22@sha256:198c..."
    KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.5.0@sha256:2489..."
}
```

Ces variables sont exportées vers Docker Compose lors du déploiement ephemere et utilisées par le scan Trivy.

### Helm / Kubernetes (stagingkub)

Les images tierces sont **centralisées** dans la section `global.images` de `values.yaml`. Toutes les templates Helm consomment cette source unique.

**Fichier** : [`infra/stagingkub/helm/rhdemo/values.yaml`](../infra/stagingkub/helm/rhdemo/values.yaml)

```yaml
global:
  images:
    postgres: "postgres:18.2-alpine3.22@sha256:198c..."
    keycloak: "quay.io/keycloak/keycloak:26.5.0@sha256:2489..."
    busybox: "busybox:1.36@sha256:0ad6..."
    postgresExporter: "quay.io/prometheuscommunity/postgres-exporter:v0.15.0@sha256:31bd..."
  imagePullPolicy: IfNotPresent
```

**Templates consommateurs** (via `{{ .Values.global.images.<nom> }}`) :

| Template | Images utilisées |
|---|---|
| `postgresql-rhdemo-statefulset.yaml` | postgres, postgresExporter, busybox |
| `postgresql-keycloak-statefulset.yaml` | postgres, busybox |
| `keycloak-deployment.yaml` | keycloak, busybox |
| `rhdemo-app-deployment.yaml` | busybox |
| `postgresql-backup-cronjob.yaml` | postgres, busybox |

**Avantage** : une seule ligne à modifier dans `values.yaml` pour mettre à jour postgres dans tous les StatefulSets, Deployments et CronJobs.

### Différence architecturale ephemere vs stagingkub

| Composant | Ephemere | Stagingkub |
|-----------|----------|------------|
| PostgreSQL | `postgres:18.2-alpine3.22` (conteneur) | `postgres:18.2-alpine3.22` (StatefulSet) |
| Keycloak | `quay.io/keycloak/keycloak:26.5.0` | idem |
| Nginx | `nginx:1.29.4-alpine` (reverse proxy) | NGINX Gateway Fabric (composant K8s) |

---

## Procédure de mise à jour d'une image

### 1. Récupérer le nouveau digest

```bash
# Récupérer le digest linux/amd64 d'une image
docker buildx imagetools inspect <image>:<nouveau-tag> --raw \
  | python3 -c "
import sys, json
m = json.load(sys.stdin)
for d in m.get('manifests', []):
    p = d.get('platform', {})
    if p.get('architecture') == 'amd64' and p.get('os') == 'linux':
        print(d['digest'])
"
```

### 2. Mettre à jour les fichiers

| Scope | Fichier à modifier |
|---|---|
| **Helm (stagingkub)** | `values.yaml` → `global.images.<nom>` |
| **Docker Compose dev** | `infra/dev/docker-compose.yml` |
| **Docker Compose ephemere** | `infra/ephemere/docker-compose.yml` |
| **Pipeline CI** | `Jenkinsfile-CI` (variables d'environnement) |

> **Important** : pour que les versions soient cohérentes entre environnements, modifier **tous** les fichiers concernés.

### 3. Vérifier

```bash
# Helm : vérifier les manifests générés
helm template rhdemo infra/stagingkub/helm/rhdemo/ \
  --set postgresql-rhdemo.database.password=x \
  --set postgresql-keycloak.database.password=x \
  --set keycloak.admin.password=x \
  | grep "image:"

# Docker Compose : vérifier la syntaxe
docker compose -f infra/dev/docker-compose.yml config | grep "image:"
docker compose -f infra/ephemere/docker-compose.yml config | grep "image:"
```

---

## Gestion de la version de RHDemo API

### Version lue depuis pom.xml

La version de l'application est **automatiquement lue depuis `pom.xml`** par le pipeline CI :

```groovy
stage('Lecture Version Maven') {
    steps {
        script {
            env.APP_VERSION = sh(
                script: 'cd rhDemo && ./mvnw help:evaluate -Dexpression=project.version -q -DforceStdout',
                returnStdout: true
            ).trim()
        }
    }
}
```

### Workflow de version

1. **Développement** : Version `X.Y.Z-SNAPSHOT` dans `pom.xml`
2. **Release** : Version `X.Y.Z-RELEASE` dans `pom.xml`, tag git `vX.Y.Z`
3. **Jenkins** : Lit automatiquement la version et construit l'image `rhdemo-api:X.Y.Z-RELEASE`

---

## Pourquoi épingler par digest ?

### Risques sans digest (tag seul)

- **Supply chain attack** : un tag peut être remplacé par une image malveillante sur le registry
- **Dérive silencieuse** : un rebuild upstream change le contenu sans changer le tag
- **Non-reproductibilité** : impossible de garantir que deux déploiements utilisent exactement la même image

### Garanties avec digest

- **Immuabilité** : le digest SHA-256 identifie le contenu exact, bit à bit
- **Reproductibilité** : un déploiement produit toujours le même résultat
- **Auditabilité** : on peut vérifier a posteriori quelle image était déployée
- **Détection de tampering** : toute modification du contenu invalide le digest

### Complémentarité tag + digest

Le format `image:tag@sha256:digest` combine les avantages :
- Le **tag** donne la lisibilité (on voit la version)
- Le **digest** donne la sécurité (on garantit le contenu)
- Si le registry retourne un contenu différent du digest, le pull échoue

---

## Références

- [Docker Image Digests](https://docs.docker.com/reference/cli/docker/image/pull/#pull-an-image-by-digest-immutable-identifier)
- [SLSA Supply Chain Levels](https://slsa.dev/) - Bonnes pratiques supply chain
- [Kubernetes - Container Images](https://kubernetes.io/docs/concepts/containers/images/#image-pull-policy)

---

**Dernière mise à jour** : 19 février 2026
