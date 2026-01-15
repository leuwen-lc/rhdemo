# Guide Claude - Projet RHDemo

## 📋 Vue d'ensemble

Projet école de preuve de concept démontrant le développement d'une application web full-stack avec approche DevSecOps complète. L'objectif est de démontrer des pratiques professionnelles sur une application CRUD simple d'employés RH, tout en pouvant fonctionner sur un seul PC Linux 16Go.

**Philosophie** : Logiciel libre à 100%, indépendance vis-à-vis des grandes plateformes (GitHub/GitLab SaaS), accent mis sur la sécurité dès la conception.

---

## 🏗️ Structure du dépôt

Le dépôt contient **3 projets distincts** :

```
/home/leno-vo/git/repository/
├── rhDemo/                      # ⭐ PROJET PRINCIPAL
│   ├── src/main/java/          # Backend Spring Boot
│   ├── frontend/               # Frontend Vue.js
│   ├── infra/                  # Configuration déploiement
│   │   ├── dev/               # Tests locaux (PostgreSQL + Keycloak)
│   │   ├── ephemere/          # Environnement CI Docker Compose
│   │   ├── stagingkub/        # Environnement Kubernetes (KinD)
│   │   └── jenkins-docker/    # Environnement CI/CD Jenkins
│   ├── docs/                   # Documentation technique
│   ├── Jenkinsfile-CI         # Pipeline CI (build, tests, scan, deploy ephemere)
│   └── Jenkinsfile-CD         # Pipeline CD (deploy stagingkub)
│
├── rhDemoAPITestIHM/           # Tests Selenium isolés (Java)
│
└── rhDemoInitKeycloak/         # Chargement données Keycloak initial
```

---

## 🎯 Architecture technique

### Backend (Spring Boot 3.5.8)
- **Langage** : Java 21
- **Framework** : Spring Boot (Web, Security, Data JPA, OAuth2 Client/Resource Server)
- **Architecture** : 3 couches classiques (Controller → Service → Repository)
- **Package** : `fr.leuwen.rhdemoAPI`
  - `controller/` - 3 contrôleurs REST (Employe, Accueil, Frontend)
  - `service/` - Logique métier
  - `repository/` - Accès données (JPA)
  - `model/` - Entités JPA
  - `springconfig/` - Configuration Spring Security, OIDC
  - `exception/` - Gestion erreurs
- **BDD** : PostgreSQL 16 (dev, ephemere, stagingkub)
- **API** : REST avec documentation OpenAPI/Swagger (SpringDoc 2.8.14)
- **Tests** : JUnit, H2 en mémoire pour tests d'intégration

### Frontend (Vue.js 3)
- **Framework** : Vue 3 + Vue Router 4
- **UI Components** : Element Plus 2.11.5 (design system)
- **HTTP Client** : Axios 1.6.0
- **Build** : Vue CLI Service 5.0
- **Composants** (7 fichiers .vue) :
  - `EmployeList.vue` - Liste paginée
  - `EmployeForm.vue` - Création
  - `EmployeModify.vue` - Modification
  - `EmployeDelete.vue` - Suppression
  - `EmployeDetail.vue` - Détail
  - `EmployeSearch.vue` - Recherche
  - `HomeMenu.vue` - Menu principal

### Build & Packaging
- **Maven** : Build unique pour backend + frontend
- **Plugin frontend-maven-plugin** : Compile Vue.js et copie dans `target/classes/static/`
- **Image Docker** : OpenJDK 21 Eclipse Temurin (migration depuis Paketo Buildpacks v1.1.0)
- **Version actuelle** : `1.1.2-RELEASE`

---

## 🔐 Sécurité (DevSecOps)

### Authentification & Autorisation
- **Keycloak 26.4.2** : IAM centralisé, OIDC/OAuth2
- **Pattern BFF (Backend For Frontend)** :
  - Le backend récupère les tokens auprès de Keycloak
  - Session stateful avec cookie (pas de JWT côté client)
  - Protection CSRF activée via `CookieCsrfTokenRepository`
- **RBAC** : Rôles portés par Keycloak et transmis dans l'id_token OIDC
- **Custom mapper** : `GrantedAuthoritiesKeyCloakMapper` pour extraire les rôles

### Headers & Content Security Policy (CSP)
- **CSP stricte** : Pas de JavaScript inline, interdiction `unsafe-inline` et `unsafe-eval`
- **Configuration dynamique** : URL Keycloak extraite automatiquement de la config OAuth2
- **Headers sécurité** : X-Frame-Options, X-Content-Type-Options, HSTS (via Nginx)
- **Masquage versions** : Nginx et Spring Boot ne révèlent pas leurs versions

### Gestion des secrets
- **SOPS** : Chiffrement des secrets versionnés dans Git
- **Séparation par environnement** :
  - Dev local : `secrets/secrets-rhdemo.yml`
  - Ephemere : Variables d'environnement + `docker cp`
  - Stagingkub : Kubernetes Secrets déchiffrés par SOPS

### Scans & Audits (dans pipeline CI)
- **OWASP Dependency-Check 12.1.9** : Scan vulnérabilités Maven (fail si CVSS ≥7)
- **SonarQube** : Quality gate (couverture ≥50%, sécurité stricte)
- **Trivy** : Scan images Docker (scans en parallèle avec caches séparés)
- **OWASP ZAP** : Analyse dynamique durant tests Selenium
- **JaCoCo** : Couverture de code (tests unitaires + intégration)

### TLS
- **Certificats auto-signés** : Activés sur ephemere (port 58443) et stagingkub (port 443)
- **Nginx reverse proxy** : Terminaison TLS

---

## 🚀 Environnements de déploiement

### 1. **dev** (Développement local)
- **Localisation** : `rhDemo/infra/dev/`
- **Usage** : Tests en local avec PostgreSQL + Keycloak via Docker Compose
- **Commande** : `./mvnw spring-boot:run` depuis `rhDemo/`
- **URL** : http://localhost:9000/front

### 2. **ephemere** (CI - Docker Compose)
- **Localisation** : `rhDemo/infra/ephemere/`
- **Usage** : Environnement jetable pour tests Selenium + ZAP dans pipeline CI
- **Architecture** : 5 conteneurs (nginx, rhdemo-app, keycloak, 2× PostgreSQL)
- **Port HTTPS** : 58443
- **URLs** :
  - App : https://rhdemo.ephemere.local:58443
  - Keycloak : https://keycloak.ephemere.local:58443
- **Avantages** : Rapide (~2min), facile à débugger, peu de ressources
- **Script** : `./init-ephemere.sh` puis `docker-compose up -d`

### 3. **stagingkub** (CD - Kubernetes/KinD)
- **Localisation** : `rhDemo/infra/stagingkub/`
- **Usage** : Environnement représentatif d'une production Kubernetes
- **Technologie** : KinD (Kubernetes in Docker) 0.30+
- **Namespace** : `rhdemo-stagingkub`
- **Cluster** : `kind-rhdemo`
- **Ressources** :
  - 2 StatefulSets (PostgreSQL rhdemo + keycloak)
  - 2 Deployments (rhdemo-app + keycloak)
  - 1 Ingress (Nginx Ingress Controller)
  - 5 Services, 4 Secrets, 2 PVC
- **Port HTTPS** : 443 (NodePort 30443)
- **URLs** :
  - App : https://rhdemo.stagingkub.local
  - Keycloak : https://keycloak.stagingkub.local
- **Observabilité** : Promtail → Loki → Grafana (logs centralisés)
- **Persistance des données** :
  - extraMounts KinD : `/home/leno-vo/kind-data/rhdemo-stagingkub`
  - Survit aux redémarrages machine
  - Configuration dans [kind-config.yaml](rhDemo/infra/stagingkub/kind-config.yaml)
- **Scripts** :
  - Init : `./scripts/init-stagingkub.sh`
  - Deploy : `./scripts/deploy.sh <version>`
  - Init Keycloak : `./scripts/init-keycloak-stagingkub.sh`

### 4. **jenkins-docker** (CI/CD Jenkins)
- **Localisation** : `rhDemo/infra/jenkins-docker/`
- **Usage** : Environnement Jenkins pour exécuter les pipelines CI/CD
- **Version** : Jenkins 2.528.1
- **Réseau** : Dédié avec connexion dynamique au réseau ephemere
- **Démarrage** : Suivre `QUICKSTART.md` et `README.md`

---

## 🔄 Pipelines CI/CD

### Pipeline CI (`Jenkinsfile-CI`) - ~2h max
**Objectif** : Build, tests, scans qualité/sécurité, déploiement ephemere, tests Selenium/ZAP, publication image Docker

**Étapes principales** :
1. **Build** : Compilation Maven (backend + frontend intégré)
2. **Tests unitaires** : Surefire (exclut `*IT.java`)
3. **Tests intégration** : Failsafe (H2 en mémoire, inclut `*IT.java`)
4. **Qualité** : SonarQube avec quality gate
5. **Sécurité** :
   - OWASP Dependency-Check (CVSS ≥7 → fail)
   - Trivy scan images Docker (3 images : app, postgres, keycloak)
6. **Image Docker** : Build `rhdemo-api:<VERSION>` (Dockerfile OpenJDK 21)
7. **Deploy ephemere** : Docker Compose (`rhDemo/infra/ephemere/`)
8. **Tests E2E** :
   - Tests Selenium (projet `rhDemoAPITestIHM`)
   - Proxy ZAP pour analyse dynamique
9. **Publication** : Push image validée dans registry Docker local

**Variables clés** :
- `APP_NAME=rhdemo-api`
- `NGINX_IMAGE=nginx:1.29.4-alpine`
- `POSTGRES_IMAGE=postgres:16-alpine`
- `KEYCLOAK_IMAGE=quay.io/keycloak/keycloak:26.4.2`

### Pipeline CD (`Jenkinsfile-CD`) - ~30min max
**Objectif** : Déployer l'image validée sur l'environnement Kubernetes stagingkub

**Étapes principales** :
1. **Récupération image** : Pull depuis registry local
2. **Préparation K8s** : Vérification cluster KinD `rhdemo`
3. **Déploiement Helm** : Namespace `rhdemo-stagingkub`
4. **Health checks** : Validation déploiement
5. **Tests fumée** : Vérification endpoints

**Variables clés** :
- `K8S_NAMESPACE=rhdemo-stagingkub`
- `K8S_CONTEXT=kind-rhdemo`
- `CLUSTER_NAME=rhdemo`

---

## 📦 Dépendances clés

### Backend Maven (pom.xml)
```xml
<java.version>21</java.version>
<spring-boot.version>3.5.8</spring-boot.version>
<mockito.version>5.17.0</mockito.version>
<commons-lang3.version>3.18.0</commons-lang3.version> <!-- Fix CVE-2025-48924 -->
<springdoc-openapi.version>2.8.14</springdoc-openapi.version> <!-- Fix CVE-2025-26791 -->
```

**Dépendances principales** :
- `spring-boot-starter-web`
- `spring-boot-starter-security`
- `spring-boot-starter-oauth2-client`
- `spring-boot-starter-oauth2-resource-server`
- `spring-boot-starter-data-jpa`
- `spring-boot-starter-actuator`
- `spring-boot-starter-validation`
- `postgresql` (runtime)
- `h2` (test)
- `micrometer-registry-prometheus`
- `springdoc-openapi-starter-webmvc-ui`

**Plugins** :
- `spring-boot-maven-plugin` (build image)
- `maven-surefire-plugin` (tests unitaires, exclut `*IT.java`)
- `maven-failsafe-plugin` (tests intégration, inclut `*IT.java`)
- `jacoco-maven-plugin` (couverture)
- `frontend-maven-plugin` (build Vue.js)
- `maven-resources-plugin` (copie frontend dans `static/`)
- `sonar-maven-plugin`
- `dependency-check-maven-plugin` (OWASP 12.1.9)

### Frontend NPM (package.json)
```json
{
  "dependencies": {
    "vue": "^3.0.0",
    "vue-router": "^4.0.0",
    "element-plus": "^2.11.5",
    "@element-plus/icons-vue": "^2.3.2",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@vue/cli-service": "~5.0.0"
  }
}
```

---

## 🧪 Tests

### Tests unitaires (Surefire)
- **Framework** : JUnit 5, Mockito 5.17.0
- **Exclusions** : `**/*IT.java`, `**/*ITCase.java`
- **Commande** : `./mvnw test`

### Tests d'intégration Spring Boot (Failsafe)
- **BDD** : H2 en mémoire
- **Annotations** : `@SpringBootTest`
- **Inclusions** : `**/*IT.java`, `**/*ITCase.java`
- **Commande** : `./mvnw verify`

### Tests E2E Selenium (projet séparé)
- **Projet** : `rhDemoAPITestIHM/`
- **Langage** : Java + Selenium WebDriver
- **Stratégie** : Marqueurs CSS `data-testid` pour robustesse
- **Exécution** : Pipeline CI après déploiement ephemere
- **Proxy** : OWASP ZAP pour analyse dynamique

---

## 📝 Conventions de code

### Backend Java
- **Package racine** : `fr.leuwen.rhdemoAPI`
- **Architecture** : Controller → Service → Repository
- **Naming** :
  - Contrôleurs : `*Controller.java`
  - Services : `*Service.java`
  - Repositories : `*Repository.java`
  - Entités : Noms simples (ex: `Employe.java`)
  - Tests intégration : `*IT.java` ou `*ITCase.java`
- **Sécurité méthodes** : Annotations `@PreAuthorize("hasRole('ROLE_XX')")`
- **Gestion erreurs** : Package `exception/` avec handlers personnalisés

### Frontend Vue.js
- **Composants** : PascalCase (ex: `EmployeList.vue`)
- **Routes** : Définies dans `router/`
- **Services** : Abstractions HTTP dans `services/`
- **Marqueurs tests** : Attributs `data-testid` sur éléments interactifs

### Configuration
- **Profils Spring** :
  - Défaut : `application.yml`
  - Ephemere : `application-ephemere.yml`
  - Stagingkub : `application-stagingkub.yml`
  - Test : `application-test.yml` (désactive SecurityConfig)
- **Secrets** : Fichiers YAML externes importés via `spring.config.import`

---

## 🔍 Points d'entrée clés

### Backend
- **Main** : `fr.leuwen.rhdemoAPI.RhdemoApplication` (non visible dans le scan, inféré)
- **SecurityConfig** : [src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java](rhDemo/src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java)
- **Contrôleurs** :
  - [EmployeController.java](rhDemo/src/main/java/fr/leuwen/rhdemoAPI/controller/EmployeController.java) - API REST CRUD employés
  - [AccueilController.java](rhDemo/src/main/java/fr/leuwen/rhdemoAPI/controller/AccueilController.java) - Page accueil
  - [FrontendController.java](rhDemo/src/main/java/fr/leuwen/rhdemoAPI/controller/FrontendController.java) - Routing SPA

### Frontend
- **Entry point** : [frontend/src/main.js](rhDemo/frontend/src/main.js)
- **Router** : [frontend/src/router/](rhDemo/frontend/src/router/)
- **App root** : [frontend/src/App.vue](rhDemo/frontend/src/App.vue)

### Configuration
- **Application** : [src/main/resources/application.yml](rhDemo/src/main/resources/application.yml)
- **Base données** : [pgschema.sql](rhDemo/pgschema.sql) + [pgdata.sql](rhDemo/pgdata.sql)
- **Docker** : [Dockerfile](rhDemo/Dockerfile)
- **KinD stagingkub** : [infra/stagingkub/kind-config.yaml](rhDemo/infra/stagingkub/kind-config.yaml)

### Pipelines
- **CI** : [Jenkinsfile-CI](rhDemo/Jenkinsfile-CI) (ligne 1-50 visible)
- **CD** : [Jenkinsfile-CD](rhDemo/Jenkinsfile-CD) (ligne 1-50 visible)

---

## 📚 Documentation importante

### Docs générales
- [README.md](README.md) - Vue d'ensemble du projet
- [ENVIRONMENTS.md](rhDemo/infra/ENVIRONMENTS.md) - Comparaison environnements
- [PIPELINES_CI_CD.md](rhDemo/docs/PIPELINES_CI_CD.md) - Détail pipelines

### Sécurité
- [SECURITE_WEB_CSP.md](rhDemo/docs/SECURITE_WEB_CSP.md) - Content Security Policy
- [CSRF_GUIDE.md](rhDemo/docs/CSRF_GUIDE.md) - Protection CSRF
- [SOPS_SETUP.md](rhDemo/docs/SOPS_SETUP.md) - Gestion secrets
- [OWASP_DEPENDENCY_CHECK.md](rhDemo/docs/OWASP_DEPENDENCY_CHECK.md) - Scan dépendances
- [TRIVY_SECURITY_SCAN.md](rhDemo/docs/TRIVY_SECURITY_SCAN.md) - Scan images Docker
- [TESTS_SECURITY_COVERAGE.md](rhDemo/docs/TESTS_SECURITY_COVERAGE.md) - Couverture tests sécu
- [SECURITY_ADVISORIES.md](rhDemo/docs/SECURITY_ADVISORIES.md) - Advisories de sécurité

### Infrastructure & Déploiement
- [infra/dev/README.md](rhDemo/infra/dev/README.md) - Setup dev local
- [infra/ephemere/README.md](rhDemo/infra/ephemere/README.md) - Environnement ephemere
- [infra/stagingkub/README.md](rhDemo/infra/stagingkub/README.md) - Environnement Kubernetes
- [infra/stagingkub/kind-config.yaml](rhDemo/infra/stagingkub/kind-config.yaml) - Configuration KinD avec persistance
- [infra/stagingkub/scripts/README-INIT-KEYCLOAK.md](rhDemo/infra/stagingkub/scripts/README-INIT-KEYCLOAK.md) - Initialisation Keycloak
- [infra/jenkins-docker/QUICKSTART.md](rhDemo/infra/jenkins-docker/QUICKSTART.md) - Démarrage rapide Jenkins
- [infra/jenkins-docker/README.md](rhDemo/infra/jenkins-docker/README.md) - Configuration Jenkins
- [**docs/POSTGRESQL_BACKUP_CRONJOBS.md**](rhDemo/docs/POSTGRESQL_BACKUP_CRONJOBS.md) - 🆕 Backups PostgreSQL automatiques avec CronJobs
- [**docs/REGISTRY_SETUP.md**](rhDemo/docs/REGISTRY_SETUP.md) - 🆕 Configuration simplifiée du registry Docker

### Technique
- [DATABASE.md](rhDemo/docs/DATABASE.md) - Configuration PostgreSQL
- [PAGINATION.md](rhDemo/docs/PAGINATION.md) - Implémentation pagination
- [DATA_TESTID_GUIDE.md](rhDemo/docs/DATA_TESTID_GUIDE.md) - Marqueurs tests Selenium
- [REGISTRY.md](rhDemo/docs/REGISTRY.md) - Registry Docker local
- [LOKI_STACK_INTEGRATION.md](rhDemo/docs/LOKI_STACK_INTEGRATION.md) - Logs centralisés (v1.1.1)
- [GRAFANA_DASHBOARD.md](rhDemo/docs/GRAFANA_DASHBOARD.md) - Dashboards Grafana
- [PAKETO-DOCKERFILE-MIGRATION.md](rhDemo/docs/PAKETO-DOCKERFILE-MIGRATION.md) - Migration build Docker

---

## ⚠️ Limites connues

### Production readiness
Le projet **n'est PAS prêt pour la production**. Points critiques :
- Modules périphériques exposés (OpenAPI/Swagger sur `:9000`)
- Keycloak en mode dev (pas de vérification email, MFA, politique mdp stricte)
- Verbosité logs excessive (niveau INFO)
- Pas de collecte métriques/logs complète avec alertes
- Pas de mécanisme de scalabilité (Redis pour sessions partagées)
- Configuration Jenkins simplifiée (tout sur master node)
- Network Policy Kubernetes basique

### Fonctionnalités métier
Application volontairement simpliste :
- Informations employés minimalistes
- Adresse dans un seul champ (devrait être table séparée, norme internationale)
- Pas de gestion hiérarchique, départements, contrats, etc.

---

## 🗓️ Changelog

### Version 1.1.3 (En cours)
- **Persistance des données KinD** : Configuration extraMounts pour survivre aux redémarrages machine
- Création fichier `kind-config.yaml` persistant avec montage `/home/leno-vo/kind-data/rhdemo-stagingkub`
- Modification `init-stagingkub.sh` pour utiliser la configuration persistante
- **Suppression complète de CloudNativePG** : Retour aux StatefulSets PostgreSQL classiques avec CronJobs de backup
- Amélioration rapports ZAP : Suppression versions NGINX, élimination doublons HSTS, durcissement CSP
- Suppression warnings Keycloak et Spring Boot

### Version 1.1.2-RELEASE
- Configuration caches Loki (réduction mémoire de 11Go → acceptable)
- Déplacement fichiers Helm values dans `infra/stagingkub/helm/observability`
- Suppression niveaux logs dans `application-stagingkub.yaml` (priorité à `values.yaml`)
- Duplication caches Trivy pour scans parallèles sans conflit

### Version 1.1.1-RELEASE
- Ajout stack Promtail/Loki/Grafana pour logs centralisés (voir [LOKI_STACK_INTEGRATION.md](rhDemo/docs/LOKI_STACK_INTEGRATION.md))
- Réglage niveaux logs via `infra/stagingkub/helm/rhdemo/values.yaml`

### Version 1.1.0-RELEASE
- Ajout environnement stagingkub (Kubernetes/KinD)
- Découpage CI/CD en 2 pipelines distincts (CI + CD)
- Migration build Paketo → Dockerfile OpenJDK 21 (image plus légère)
- Persistance données entre déploiements

---

## 🚧 Feuille de route

### Fonctionnalités
- [ ] Champs de recherche par colonne dans liste employés
- [ ] Mécanisme de migration schéma (Liquibase)

### Scalabilité
- [ ] Redis pour sessions partagées
- [x] **Backups PostgreSQL automatisés** : CronJobs quotidiens avec rétention 7 jours

### Sécurité & Qualité
- [ ] Génération SBOM (Syft, CycloneDX, OWASP Dependency Track)
- [ ] Snyk pour dépendances frontend
- [ ] Revue pipelines selon OWASP Top 10 CI/CD Security Risks
- [ ] Network Policy production-ready

### Observabilité
- [ ] Collecte métriques Prometheus + Grafana
- [ ] Seuils d'alertes logs/métriques

---

## 💡 Décisions techniques

### Pourquoi BFF (Backend For Frontend) ?
- **Sécurité** : Tokens OAuth2 ne transitent jamais côté client
- **Session stateful** : Cookie `JSESSIONID` avec protection CSRF
- **Simplicité frontend** : Pas de gestion de rafraîchissement token côté Vue.js

### Pourquoi Keycloak ?
- IAM standard de l'industrie, open source
- SSO inter-applications
- Politiques de mots de passe, MFA, vérification email
- Intégration OIDC native avec Spring Security

### Pourquoi 2 environnements de déploiement ?
- **ephemere** : Tests rapides CI, debugging facile
- **stagingkub** : Validation Kubernetes, proche production
- Démontre la portabilité de l'application

### Pourquoi SOPS pour les secrets ?
- Secrets versionnés dans Git (chiffrés)
- Pas besoin d'infrastructure centralisée (Vault) pour démarrer
- Compatible avec workflows Git (review, audit)
- Migration vers Vault possible sans changer l'applicatif

### Pourquoi Maven pour le frontend ?
- Build unique backend + frontend
- Simplifie CI/CD (une seule commande `mvnw clean package`)
- Frontend copié dans `target/classes/static/` automatiquement
- Image Docker finale contient l'application complète

### Pourquoi KinD plutôt que Minikube/K3s ?
- Kubernetes-in-Docker : isolation, reproductibilité
- Clusters éphémères faciles à créer/détruire
- Compatible CI/CD (Docker-in-Docker)
- Représentatif d'un vrai cluster K8s
- **extraMounts** pour persistance des données hors du conteneur

### Pourquoi StatefulSets + CronJobs pour PostgreSQL ?
- **Simplicité** : Pas de dépendance à un opérateur externe
- **Ressources limitées** : Adapté à un environnement PC (16Go RAM)
- **Backups automatiques** : CronJobs quotidiens avec rétention configurable (7 jours)
- **Persistance garantie** : extraMounts KinD assurent la survie aux redémarrages
- **Contrôle total** : Configuration PostgreSQL directe sans abstraction
- **Débogage facile** : kubectl logs/exec standards, pas de CRDs complexes

---

## 🛠️ Commandes utiles

### Build & Tests locaux
```bash
# Build complet (backend + frontend)
./mvnw clean package

# Tests unitaires uniquement
./mvnw test

# Tests intégration uniquement
./mvnw verify

# Lancer app en dev
./mvnw spring-boot:run

# Build image Docker
./mvnw spring-boot:build-image

# Scan OWASP Dependency-Check
./mvnw org.owasp:dependency-check-maven:check -DnvdApiKey=YOUR_KEY
```

### Docker Compose (ephemere)
```bash
cd rhDemo/infra/ephemere
./init-ephemere.sh
docker-compose up -d
docker-compose logs -f rhdemo-app
docker-compose down
```

### Kubernetes (stagingkub)
```bash
cd rhDemo/infra/stagingkub

# Initialisation cluster (une seule fois)
./scripts/init-stagingkub.sh

# Déploiement
./scripts/deploy.sh 1.1.2-RELEASE

# Vérification
kubectl get all -n rhdemo-stagingkub
kubectl logs -n rhdemo-stagingkub deployment/rhdemo-app -f

# Accès base de données
kubectl port-forward -n rhdemo-stagingkub statefulset/postgresql-rhdemo 5432:5432
```

### Jenkins
```bash
cd rhDemo/infra/jenkins-docker
# Voir QUICKSTART.md pour setup initial

# Logs Jenkins
docker logs -f jenkins-docker-jenkins-1

# Accès Jenkins
# http://localhost:8090
```

---

## 🤝 Contribuer

1. Ouvrir une issue décrivant la modification souhaitée
2. Créer une branche `feature/ma-feature` ou `fix/ma-correction`
3. Respecter les conventions de commits (Conventional Commits)
4. Ajouter/mettre à jour les tests si nécessaire
5. Vérifier que les pipelines CI/CD passent

---

## 📄 Licence

Apache 2.0

---

## 📞 Support

- **Issues** : Ouvrir une issue sur le dépôt Git
- **Documentation** : Voir dossier `docs/` pour guides détaillés

---

**Dernière mise à jour** : 2026-01-10 (Claude Code scan initial)
**Version applicative** : 1.1.2-RELEASE
