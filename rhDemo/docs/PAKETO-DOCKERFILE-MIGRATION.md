# Migration de Paketo Buildpacks vers Dockerfile classique

Date : 2025-12-11

> **Document historique.** Décrit la bascule initiale (image de base Eclipse
> Temurin **21**). Depuis, l'image de base a suivi la montée Java du projet et
> est aujourd'hui **Eclipse Temurin 25** (`maven:3.9-eclipse-temurin-25-noble`
> pour le build, `eclipse-temurin:25-jre-*` pour le runtime — voir `rhDemo/Dockerfile`
> pour l'état courant). Le pipeline CI construit l'image via `docker build` sur ce
> Dockerfile ; la configuration `spring-boot:build-image` (Paketo) reste présente
> dans `pom.xml` comme voie alternative, épinglée sur `BP_JVM_VERSION=25`.
> Toutes les mentions de « 21 » ci-dessous sont à lire au sens de « la version
> Java d'alors ».

## 🎯 Objectif

Remplacer la construction d'image Docker via Paketo Buildpacks par un Dockerfile classique basé sur Eclipse Temurin 21, afin d'éviter les problèmes réseau et obtenir plus de contrôle sur le processus de build.

## ❌ Problèmes rencontrés avec Paketo Buildpacks

### Erreur de téléchargement Syft
```
unable to invoke layer creator
unable to get dependency Syft. see DEBUG log level
ERROR: failed to build: exit status 1
```

**Causes** :
- Dépendance réseau externe pour télécharger Syft depuis GitHub
- Sensible aux problèmes réseau ou limitations de débit
- Manque de contrôle sur le processus de téléchargement

### Autres limitations

1. **Taille des images** : 500-800 MB (buildpacks incluent beaucoup de composants)
2. **Temps de build** : Plus lent car télécharge de nombreux composants
3. **Cache complexe** : Nécessite buildpacks-cache layer distinct
4. **Debugging difficile** : Moins de visibilité sur les étapes de construction

## ✅ Solution : Dockerfile classique avec Eclipse Temurin 21

### Avantages

| Critère | Paketo Buildpacks | Dockerfile classique |
|---------|-------------------|----------------------|
| **Taille** | 500-800 MB | 200-300 MB |
| **Contrôle** | ⚠️ Limité | ✅ Total |
| **Reproductibilité** | ⚠️ Dépend réseau externe | ✅ Cache Docker local |
| **Debugging** | ❌ Complexe | ✅ Simple et transparent |
| **Maintenance** | ⚠️ Dépend buildpacks | ✅ Standard Docker |
| **Configuration** | 🔧 Variables BP_* | 🔧 ARG/ENV Dockerfile |

### Architecture choisie : Multi-stage build

```
┌─────────────────────────────────────────────────────────┐
│ STAGE 1 : BUILD                                         │
│ Image: maven:3.9-eclipse-temurin-21-jammy               │
│                                                          │
│ 1. Copier pom.xml, .mvn, mvnw                           │
│ 2. ./mvnw dependency:go-offline (layer caché)           │
│ 3. Copier src/ et frontend/                             │
│ 4. ./mvnw clean package -DskipTests                     │
│                                                          │
│ Résultat: /build/target/*.jar                           │
└─────────────────────────────────────────────────────────┘
                          ↓ COPY JAR
┌─────────────────────────────────────────────────────────┐
│ STAGE 2 : RUNTIME                                       │
│ Image: eclipse-temurin:21-jre-jammy                     │
│                                                          │
│ 1. Créer utilisateur non-root (spring:spring)           │
│ 2. Copier JAR depuis stage 1                            │
│ 3. Configurer JVM optimisée pour containers             │
│ 4. HEALTHCHECK via actuator                             │
│                                                          │
│ Résultat: Image finale ~200-300 MB                      │
└─────────────────────────────────────────────────────────┘
```

## 📁 Fichiers modifiés

### 1. Nouveau Dockerfile

**Fichier** : `/home/leno-vo/git/repository/rhDemo/Dockerfile`

**Caractéristiques** :
- Multi-stage build (builder + runtime)
- Base image : `eclipse-temurin:21-jre-jammy`
- Utilisateur non-root : `spring:spring` (UID 1000)
- JVM optimisée pour containers :
  - `UseContainerSupport` : Détecte limites mémoire
  - `MaxRAMPercentage=75.0` : Utilise max 75% RAM pour heap
  - `UseG1GC` : Garbage Collector G1 (recommandé Java 21)
  - `ExitOnOutOfMemoryError` : Arrêt propre en cas d'OOM
- Healthcheck : `/actuator/health`
- Labels OCI standards (version, build date, VCS ref)

**Build arguments** :
```dockerfile
ARG BUILD_DATE      # Date de construction (format ISO 8601)
ARG VCS_REF         # Git commit hash
ARG VERSION=1.0.0   # Version de l'application
```

### 2. Jenkinsfile modifié

**Stage** : `🏗️ Build Docker Image` (lignes 665-695)

**Ancien build (Paketo)** :
```bash
cd rhDemo && ./mvnw clean spring-boot:build-image \
    -Dspring-boot.build-image.imageName=${DOCKER_IMAGE_NAME}:${APP_VERSION} \
    -Dspring-boot.build-image.pullPolicy=IF_NOT_PRESENT \
    -Dspring-boot.build-image.publish=false \
    -Dspring-boot.build-image.cleanCache=true \
    -DskipTests
```

**Nouveau build (Dockerfile)** :
```bash
cd rhDemo
docker build -t ${DOCKER_IMAGE_NAME}:${APP_VERSION} \
             -t ${DOCKER_IMAGE_NAME}:latest \
             --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
             --build-arg VCS_REF=$(git rev-parse --short HEAD) \
             --build-arg VERSION=${APP_VERSION} \
             .
```

**Changements dans le stage** :

| Ligne | Ancien (Paketo) | Nouveau (Dockerfile) |
|-------|-----------------|----------------------|
| 665 | "Construction avec Paketo Buildpacks..." | "Construction avec Dockerfile (Eclipse Temurin 21)..." |
| 668 | "Nettoyage cache Docker + target/ + images..." | "Nettoyage images existantes..." |
| 671-674 | Supprime buildpacks cache | Supprime images versionnées + latest |
| 676-681 | Supprime target/ | *(Supprimé, inutile avec multi-stage)* |
| 683-691 | Commande mvn spring-boot:build-image | Commande docker build avec args |
| 689-692 | Liste images grep | Affichage formaté avec taille |

**Affichage amélioré** :
```bash
echo "📊 Images créées:"
docker images ${DOCKER_IMAGE_NAME} --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
```

## 🔄 Impact sur le pipeline Jenkins

### Étapes de build modifiées

**Avant (Paketo)** :
1. ✅ Compiler avec Maven (`mvn verify`)
2. 🐳 Build image via `spring-boot:build-image`
   - Maven télécharge buildpacks
   - Buildpacks téléchargent Syft, lifecycle, etc.
   - Création image ~500-800 MB
3. ✅ Tests
4. ✅ SonarQube
5. ✅ Push registry

**Après (Dockerfile)** :
1. ✅ Compiler avec Maven (`mvn verify`)
2. 🐳 Build image via `docker build`
   - Docker télécharge base images (une seule fois)
   - Maven rebuild dans container builder
   - Création image ~200-300 MB
3. ✅ Tests
4. ✅ SonarQube
5. ✅ Push registry

### Optimisations de cache Docker

Le Dockerfile utilise le **layer caching** de Docker :

```dockerfile
# Layer 1 (rarement modifié) : Dépendances Maven
COPY pom.xml .mvn mvnw
RUN ./mvnw dependency:go-offline

# Layer 2 (souvent modifié) : Code source
COPY src frontend
RUN ./mvnw clean package
```

**Bénéfices** :
- Si `pom.xml` ne change pas → réutilise layer des dépendances (très rapide)
- Si seulement le code change → rebuild uniquement layer 2

## 🧪 Tests et validation

### Test local du Dockerfile

```bash
cd /home/leno-vo/git/repository/rhDemo

# Build
docker build -t rhdemo-test:local \
  --build-arg VERSION=1.0.0-test \
  --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
  --build-arg VCS_REF=$(git rev-parse --short HEAD) \
  .

# Vérifier la taille
docker images rhdemo-test:local

# Lancer le container
docker run -d -p 8081:8080 --name rhdemo-test rhdemo-test:local

# Vérifier le healthcheck
curl http://localhost:8081/actuator/health

# Cleanup
docker stop rhdemo-test && docker rm rhdemo-test
docker rmi rhdemo-test:local
```

### Test dans Jenkins

1. **Lancer le pipeline** avec `DEPLOY_ENV=stagingkub`
2. **Vérifier le stage** `🏗️ Build Docker Image`
3. **Contrôler la sortie** :
   ```
   🐳 Construction de l'image Docker avec Dockerfile (Eclipse Temurin 21)...
      Version détectée: 1.0.0
      Image à construire: rhdemo-api:1.0.0
   ⚠️  Nettoyage complet: suppression images existantes...
   ...
   ✅ Image Docker créée: rhdemo-api:1.0.0

   📊 Images créées:
   REPOSITORY:TAG         SIZE      CREATED
   rhdemo-api:1.0.0       287MB     2025-12-11T19:00:00+01:00
   rhdemo-api:latest      287MB     2025-12-11T19:00:00+01:00
   ```

## 🔐 Sécurité

### Bonnes pratiques implémentées

✅ **Utilisateur non-root** : L'application s'exécute sous `spring:spring` (UID 1000)
```dockerfile
USER spring:spring
```

✅ **Image minimale** : JRE seulement (pas de JDK dans runtime)
```dockerfile
FROM eclipse-temurin:21-jre-jammy
```

✅ **Healthcheck configuré** : Kubernetes peut vérifier la santé du pod
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1
```

✅ **Pas de secrets dans l'image** : Variables d'environnement injectées par Kubernetes

## 📊 Comparaison des tailles d'images

| Type d'image | Taille estimée | Contenu |
|--------------|----------------|---------|
| **Paketo Buildpacks** | 500-800 MB | Buildpacks runtime + JRE + app + SBOM |
| **Dockerfile classique** | 200-300 MB | JRE + app uniquement |
| **Réduction** | **~60%** | ✅ Image plus légère |

**Impacts** :
- ✅ Pull plus rapide depuis le registry
- ✅ Moins d'espace disque sur les nodes Kubernetes
- ✅ Déploiement plus rapide


## 🔧 Configuration JVM

### Variables d'environnement par défaut

```dockerfile
ENV JAVA_OPTS="-XX:+UseContainerSupport \
               -XX:MaxRAMPercentage=75.0 \
               -XX:+UseG1GC \
               -XX:+ExitOnOutOfMemoryError \
               -Djava.security.egd=file:/dev/./urandom"
```

### Surcharge possible via Kubernetes

Dans `values.yaml` du Helm chart :
```yaml
rhdemo:
  env:
    JAVA_OPTS: "-XX:MaxRAMPercentage=80.0 -XX:+UseG1GC -Xlog:gc*"
```

## ⚠️ Changements de configuration

### Utilisateur container : `cnb` → `spring`

Avec Paketo Buildpacks, l'image utilisait l'utilisateur `cnb:cnb` (Cloud Native Buildpacks).
Avec le nouveau Dockerfile, l'utilisateur est `spring:spring` (UID 1000).

**Fichiers modifiés** :
- **Jenkinsfile** (lignes 1238-1246) : Scripts de copie secrets pour environnement staging
  - Ancien : `chown cnb:cnb`
  - Nouveau : `chown spring:spring`

**Impact** : Si vous avez des scripts personnalisés qui référencent l'utilisateur `cnb`, ils doivent être mis à jour vers `spring`.

## 📖 Documentation associée

- [Dockerfile](../Dockerfile) : Fichier de construction
- [Jenkinsfile](../Jenkinsfile) : Pipeline modifié (lignes 665-695, 1238-1246)
- [CHANGELOG-JENKINS-STAGINGKUB.md](infra/stagingkub/CHANGELOG-JENKINS-STAGINGKUB.md) : Historique complet des modifications Jenkins
- [JENKINS-NETWORK-ANALYSIS.md](infra/stagingkub/JENKINS-NETWORK-ANALYSIS.md) : Analyse réseau Jenkins ↔ stagingkub

## 📝 Notes

### Pourquoi Eclipse Temurin ?

- ✅ Distribution officielle OpenJDK par Eclipse Foundation (ex-AdoptOpenJDK)
- ✅ Support LTS pour Java 21
- ✅ Images Docker officielles maintenues
- ✅ Largement utilisé en production
- ✅ Compatible avec Spring Boot

### Alternatives considérées

| Base image | Avantages | Inconvénients |
|------------|-----------|---------------|
| **Eclipse Temurin** | ✅ Support officiel, LTS | - |
| Amazon Corretto | ✅ Support AWS | ⚠️ Moins universel |
| Red Hat UBI | ✅ Support Red Hat | ⚠️ Plus volumineux |
| Alpine + JRE | ✅ Très léger (~150 MB) | ⚠️ Problèmes compatibilité (musl vs glibc) |

**Choix** : Eclipse Temurin pour équilibre taille/compatibilité/support.

---

**Date** : 2025-12-11
**Version** : 1.0.0
