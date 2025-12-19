# 🐛 Problème de Tag d'Image Docker dans Jenkins

## Symptôme

```
08:26:15   rhdemo-app Error pull access denied for rhdemo-api, repository does not exist or may require 'docker login'
```

## Analyse

### Flux actuel

1. **Stage "Build Docker Image" (ligne 670)**
   - Construit l'image : `rhdemo-api:${APP_VERSION}` (ex: `rhdemo-api:0.0.1-SNAPSHOT`)
   - Variable `APP_VERSION` vient du POM Maven

2. **Stage "Tag Image Docker" (ligne 854-868)**
   - **Condition** : `params.DEPLOY_ENV == 'ephemere' || params.DEPLOY_ENV == 'production'`
   - Tag l'image : `rhdemo-api:0.0.1-SNAPSHOT` → `rhdemo-api:build-${BUILD_NUMBER}`
   - Variable `RHDEMO_IMAGE = "${DOCKER_IMAGE_NAME}:build-${env.BUILD_NUMBER}"` (ligne 72)

3. **Stage "Démarrage Environnement Docker" (ligne 1135)**
   - **Condition** : `params.DEPLOY_ENV == 'ephemere' || params.DEPLOY_ENV == 'production'`
   - Exporte : `export APP_VERSION=build-${env.BUILD_NUMBER}` (ligne 1154)
   - Lance : `docker-compose up -d`

4. **docker-compose.yml (ligne 98)**
   ```yaml
   image: rhdemo-api:${APP_VERSION:-0.0.1-SNAPSHOT}
   ```
   - Cherche l'image : `rhdemo-api:build-52`
   - **❌ L'image n'existe pas** → docker-compose essaie de la pull depuis Docker Hub → ERREUR

## Cause

L'image `rhdemo-api:build-52` doit exister **avant** que `docker-compose up -d` soit exécuté.

## Solutions possibles

### Solution 1 : Vérifier que le stage "Tag Image Docker" s'exécute bien

Le stage "Tag Image Docker" a la bonne condition `when` et devrait s'exécuter avant le stage "Démarrage Environnement Docker".

**Action** : Vérifier dans le log Jenkins complet si le stage "Tag Image Docker" est bien exécuté.

### Solution 2 : Forcer le tag avant le démarrage Docker

Déplacer le tag directement dans le stage "Démarrage Environnement Docker" :

```groovy
stage('🐳 Démarrage Environnement Docker') {
    when {
        expression { params.DEPLOY_ENV == 'ephemere' || params.DEPLOY_ENV == 'production' }
    }
    steps {
        script {
            echo '▶ Tag de l\'image Docker...'
            sh """
                docker tag ${env.DOCKER_IMAGE_NAME}:${env.APP_VERSION} ${env.RHDEMO_IMAGE}
            """

            echo '▶ Démarrage de l\'environnement Docker Compose...'
        }
        sh """
            # SÉCURITÉ: Désactiver l'écho des commandes
            set +x

            # Source les secrets SOPS
            . rhDemo/secrets/env-vars.sh

            cd ${EPHEMERE_INFRA_PATH}

            # Variables d'environnement pour Docker Compose
            export APP_VERSION=build-${env.BUILD_NUMBER}

            # ... reste du script
        """
    }
}
```

### Solution 3 : Utiliser directement APP_VERSION du Maven

Modifier `docker-compose.yml` et le Jenkinsfile pour utiliser directement `APP_VERSION` du POM Maven sans renommage :

**docker-compose.yml** :
```yaml
image: rhdemo-api:${APP_VERSION:-0.0.1-SNAPSHOT}
```

**Jenkinsfile** (ligne 1154) :
```bash
export APP_VERSION=${env.APP_VERSION}  # Utilise la version Maven
```

**Avantage** : Plus simple, pas besoin de tag supplémentaire
**Inconvénient** : Perd la numérotation par build (`build-52`)

## Recommandation

**Solution 2** est la plus fiable : déplacer le tag directement dans le stage "Démarrage Environnement Docker" pour garantir que l'image existe avant le `docker-compose up -d`.

## Vérification

Après correction, vérifier que :

```bash
# L'image taguée existe
docker images | grep rhdemo-api | grep build-

# Exemple de sortie attendue :
# rhdemo-api   build-52   abc123   5 minutes ago   500MB
```
