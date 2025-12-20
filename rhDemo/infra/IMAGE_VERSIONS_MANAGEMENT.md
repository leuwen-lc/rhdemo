# Gestion des Versions d'Images Docker

## Gestion des versions Nginx et Keycloak

### 📍 **Environnement EPHEMERE** (Docker Compose)

**Fichiers de référence :**
- `rhDemo/infra/ephemere/docker-compose.yml` : Valeurs par défaut
- `rhDemo/Jenkinsfile-CI` : Variables d'environnement Jenkins (source de vérité)

**Versions actuelles :**
```yaml
# Jenkinsfile-CI (lignes 48-50)
NGINX_IMAGE = "nginx:1.29.4-alpine"
POSTGRES_IMAGE = "postgres:16-alpine"
KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.4.2"

# docker-compose.yml avec fallback
image: ${NGINX_IMAGE:-nginx:1.29.4-alpine}
image: ${KEYCLOAK_IMAGE:-quay.io/keycloak/keycloak:26.4.2}
```

**Fonctionnement :**
1. Jenkins définit les variables dans `environment` block
2. Jenkins exporte ces variables avant `docker-compose up` (ligne 707-709)
3. Docker Compose utilise ces variables, ou les valeurs par défaut si absentes

---

### 🎯 **Environnement STAGINGKUB** (Kubernetes/Helm)

**Fichiers de référence :**
- `rhDemo/infra/stagingkub/helm/rhdemo/values.yaml` : Configuration Helm

**Versions actuelles :**
```yaml
# values.yaml
postgresql-rhdemo:
  image:
    repository: postgres
    tag: "16-alpine"

postgresql-keycloak:
  image:
    repository: postgres
    tag: "16-alpine"

keycloak:
  image:
    repository: quay.io/keycloak/keycloak
    tag: "26.4.2"

# NGINX = Ingress Controller Kubernetes (pas une image custom)
nginx-ingress:
  enabled: true
  install: true
  # Version gérée par la chart Helm nginx-ingress
```

**Différence importante :**
- **Ephemere** : Utilise nginx comme **reverse proxy custom** (conteneur Docker)
- **Stagingkub** : Utilise **Nginx Ingress Controller** (composant Kubernetes standard)

---

## 🔄 État actuel : Versions IDENTIQUES ✅

| Composant | Ephemere | Stagingkub | Statut |
|-----------|----------|------------|--------|
| PostgreSQL | `postgres:16-alpine` | `postgres:16-alpine` | ✅ Identique |
| Keycloak | `quay.io/keycloak/keycloak:26.4.2` | `quay.io/keycloak/keycloak:26.4.2` | ✅ Identique |
| Nginx | `nginx:1.29.4-alpine` (reverse proxy) | Ingress Controller (K8s) | ⚠️ Différent (architecture) |

---

## 📝 Recommandations

**Problème actuel :** Les versions sont **dupliquées** entre :
- `Jenkinsfile-CI` (lignes 48-50)
- `docker-compose.yml` (valeurs par défaut)
- `values.yaml` (stagingkub)

**Solution suggérée :** Centraliser dans un fichier unique

Créer `rhDemo/versions.properties` :
```properties
POSTGRES_VERSION=16-alpine
KEYCLOAK_VERSION=26.4.2
NGINX_VERSION=1.29.4-alpine
```

Puis :
- Jenkinsfile charge ce fichier
- docker-compose.yml référence les mêmes versions (fallback)
- values.yaml peut être généré ou maintenu manuellement

---

## Comment mettre à jour une version

### Pour EPHEMERE

**Option 1 : Modifier le Jenkinsfile** (source de vérité pour CI/CD)

```groovy
// rhDemo/Jenkinsfile-CI
environment {
    NGINX_IMAGE = "nginx:1.29.5-alpine"  // ← Modifier ici
    KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.5.0"
}
```

**Option 2 : Modifier docker-compose.yml** (pour tests manuels locaux)

```yaml
# rhDemo/infra/ephemere/docker-compose.yml
services:
  nginx:
    image: ${NGINX_IMAGE:-nginx:1.29.5-alpine}  // ← Modifier la valeur par défaut
```

⚠️ **Important** : Pour que les versions soient cohérentes, modifier LES DEUX fichiers.

### Pour STAGINGKUB

Modifier uniquement `values.yaml` :

```yaml
# rhDemo/infra/stagingkub/helm/rhdemo/values.yaml
keycloak:
  image:
    repository: quay.io/keycloak/keycloak
    tag: "26.5.0"  # ← Modifier ici
```

---

## Gestion de la version de RHDemo API

### Version lue depuis pom.xml

La version de l'application RHDemo est **automatiquement lue depuis `pom.xml`** dans le stage `🔢 Lecture Version Maven` :

```groovy
stage('🔢 Lecture Version Maven') {
    steps {
        script {
            // Lire la version depuis le pom.xml
            env.APP_VERSION = sh(
                script: 'cd rhDemo && ./mvnw help:evaluate -Dexpression=project.version -q -DforceStdout',
                returnStdout: true
            ).trim()

            // Mettre à jour les variables Docker
            env.DOCKER_IMAGE_TAG = env.APP_VERSION

            echo "✅ Version Maven détectée: ${env.APP_VERSION}"
        }
    }
}
```

### Workflow de version

1. **Développement** : Version `X.Y.Z-SNAPSHOT` dans `pom.xml`
2. **Release** :
   - Créer un tag git : `git tag -a vX.Y.Z -m "Release X.Y.Z"`
   - Mettre à jour `pom.xml` : `<version>X.Y.Z</version>`
   - Commit et push : `git push && git push --tags`
3. **Jenkins** : Lit automatiquement la version et construit l'image `rhdemo-api:X.Y.Z`

### Exemple de mise à jour de version

```bash
# Passer de 1.0.0-RELEASE à 1.1.0-SNAPSHOT
cd rhDemo
./mvnw versions:set -DnewVersion=1.1.0-SNAPSHOT
git add pom.xml
git commit -m "chore: bump version to 1.1.0-SNAPSHOT"
git push
```

Le prochain build Jenkins utilisera automatiquement `1.1.0-SNAPSHOT`.

---

## Scan de sécurité Trivy

Le stage Trivy extrait automatiquement les versions depuis les variables Jenkins :

```groovy
stage('🔍 Scan Sécurité Images Docker (Trivy)') {
    steps {
        script {
            def imagesToScan = [
                [image: env.POSTGRES_IMAGE, name: 'postgres'],
                [image: env.KEYCLOAK_IMAGE, name: 'keycloak'],
                [image: env.NGINX_IMAGE, name: 'nginx'],
                [image: "rhdemo-api:${env.DOCKER_IMAGE_TAG}", name: 'rhdemo-api']
            ]

            imagesToScan.each { imageInfo ->
                echo "🔍 Scan: ${imageInfo.image}"
                // ... scan Trivy ...
            }
        }
    }
}
```

---

## Références

- [Docker Compose variable substitution](https://docs.docker.com/compose/environment-variables/set-environment-variables/)
- [Helm values.yaml](https://helm.sh/docs/chart_template_guide/values_files/)
- [Trivy image scanning](https://aquasecurity.github.io/trivy/)

---

**Dernière mise à jour** : 20 décembre 2025
