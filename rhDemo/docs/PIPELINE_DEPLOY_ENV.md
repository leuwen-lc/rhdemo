# Pipeline RHDemo - Paramètre DEPLOY_ENV

## Vue d'ensemble

Le paramètre `DEPLOY_ENV` contrôle l'étendue de l'exécution du pipeline Jenkins.

## Options disponibles

### `none` - Build et tests uniquement (CI rapide)

Pipeline **léger** pour validation rapide du code (Pull Requests, commits de développement).

**Stages exécutés** :
- ✅ Checkout du code
- ✅ Build Maven (compilation)
- ✅ Tests unitaires
- ✅ Tests d'intégration
- ✅ Analyse de couverture (JaCoCo)
- ✅ Analyse sécurité OWASP Dependency-Check
- ✅ Analyse SonarQube (si `RUN_SONAR=true`)
- ✅ Quality Gate SonarQube (si `RUN_SONAR=true`)

**Stages IGNORÉS** :
- ❌ Build Docker Image (Paketo)
- ❌ Tag Image Docker
- ❌ Démarrage Environnement Docker Compose
- ❌ Tests Selenium IHM
- ❌ Déploiement production
- ❌ Backup base de données

**Temps estimé** : ~5-10 minutes (sans SonarQube), ~15-20 minutes (avec SonarQube)

**Cas d'usage** :
- Validation de Pull Request
- Commit de développement
- Vérification rapide qualité/sécurité
- Builds fréquents

---

### `ephemere` - Pipeline complet avec déploiement ephemere

Pipeline **complet** incluant Docker, Selenium et déploiement en environnement de ephemere.

**Stages exécutés** :
- ✅ Tous les stages de `none`
- ✅ + Build Docker Image (Paketo Buildpacks)
- ✅ + Tag Image Docker
- ✅ + Démarrage Environnement Docker Compose (5 services)
- ✅ + Injection secrets dans container
- ✅ + Healthcheck services (PostgreSQL, Keycloak, nginx, application)
- ✅ + Tests Selenium IHM (si `RUN_SELENIUM_TESTS=true`)

**Stages IGNORÉS** :
- ❌ Approbation manuelle
- ❌ Backup base de données production
- ❌ Déploiement production
- ❌ Vérification post-déploiement

**Temps estimé** : ~30-40 minutes

**Cas d'usage** :
- Build de release candidate
- Validation complète avant production
- Tests fonctionnels end-to-end
- Démonstration client

---

### `production (simulation)` - Pipeline complet avec déploiement production

Pipeline **complet** incluant toutes les étapes de production (actuellement en simulation).

**Stages exécutés** :
- ✅ Tous les stages de `ephemere`
- ✅ + Approbation manuelle (sauf si `SKIP_MANUAL_APPROVAL=true`)
- ✅ + Backup base de données (simulation)
- ✅ + Déploiement production (simulation)
- ✅ + Vérification post-déploiement (simulation)

**Temps estimé** : ~35-45 minutes (+ temps d'attente approbation manuelle)

**Cas d'usage** :
- Déploiement en production
- Release officielle
- Mise en production planifiée

---

## Matrice de décision

| Stage | `none` | `ephemere` | `production` |
|-------|:------:|:---------:|:------------:|
| **Build & Compilation** | ✅ | ✅ | ✅ |
| **Tests unitaires** | ✅ | ✅ | ✅ |
| **Tests intégration** | ✅ | ✅ | ✅ |
| **OWASP Dependency-Check** | ✅ | ✅ | ✅ |
| **SonarQube** | ✅* | ✅* | ✅* |
| **Build Docker Image** | ❌ | ✅ | ✅ |
| **Déploiement ephemere** | ❌ | ✅ | ✅ |
| **Tests Selenium** | ❌ | ✅** | ✅** |
| **Approbation manuelle** | ❌ | ❌ | ✅*** |
| **Backup BDD** | ❌ | ❌ | ✅ |
| **Déploiement production** | ❌ | ❌ | ✅ |

\* Si `RUN_SONAR=true`
\*\* Si `RUN_SELENIUM_TESTS=true`
\*\*\* Sauf si `SKIP_MANUAL_APPROVAL=true`

---

## Paramètres complémentaires

### `RUN_SELENIUM_TESTS`

- **Type** : Boolean
- **Défaut** : `true`
- **Impact** :
  - Si `DEPLOY_ENV=none` → **Ignoré** (tests Selenium ne s'exécutent jamais)
  - Si `DEPLOY_ENV=ephemere/production` → Active/désactive tests Selenium

### `RUN_SONAR`

- **Type** : Boolean
- **Défaut** : `false`
- **Impact** : Active/désactive l'analyse SonarQube pour tous les modes

### `SKIP_MANUAL_APPROVAL`

- **Type** : Boolean
- **Défaut** : `false`
- **Impact** :
  - Si `DEPLOY_ENV=production` → Ignore l'approbation manuelle
  - Si `DEPLOY_ENV=none/ephemere` → **Ignoré** (pas d'approbation dans ces modes)

---

## Exemples de configurations

### Build rapide pour Pull Request

```groovy
DEPLOY_ENV: none
RUN_SELENIUM_TESTS: false (ignoré)
RUN_SONAR: false
```
**Résultat** : Build + tests unitaires/intégration + OWASP (~5-10 min)

---

### Build complet avec qualité pour release candidate

```groovy
DEPLOY_ENV: none
RUN_SELENIUM_TESTS: false (ignoré)
RUN_SONAR: true
```
**Résultat** : Build + tests + OWASP + SonarQube (~15-20 min)

---

### Validation complète avant production

```groovy
DEPLOY_ENV: ephemere
RUN_SELENIUM_TESTS: true
RUN_SONAR: true
```
**Résultat** : Pipeline complet ephemere + Selenium + SonarQube (~40-50 min)

---

### Déploiement production avec approbation

```groovy
DEPLOY_ENV: production (simulation)
RUN_SELENIUM_TESTS: true
RUN_SONAR: false
SKIP_MANUAL_APPROVAL: false
```
**Résultat** : Pipeline complet + attente approbation manuelle + déploiement production

---

### Déploiement production automatique (CI/CD complet)

```groovy
DEPLOY_ENV: production (simulation)
RUN_SELENIUM_TESTS: true
RUN_SONAR: false
SKIP_MANUAL_APPROVAL: true
```
**Résultat** : Pipeline complet sans intervention manuelle

---

## Recommandations

### Pour les développeurs

- **Commits quotidiens** : `DEPLOY_ENV=none`, `RUN_SONAR=false`
- **Pull Request** : `DEPLOY_ENV=none`, `RUN_SONAR=true`

### Pour les releases

- **Release Candidate** : `DEPLOY_ENV=ephemere`, `RUN_SELENIUM_TESTS=true`, `RUN_SONAR=true`
- **Production** : `DEPLOY_ENV=production`, `RUN_SELENIUM_TESTS=true`, `SKIP_MANUAL_APPROVAL=false`

### Pour les tests

- **Tests Selenium uniquement** : `DEPLOY_ENV=ephemere`, `RUN_SELENIUM_TESTS=true`, `RUN_SONAR=false`
- **Analyse qualité uniquement** : `DEPLOY_ENV=none`, `RUN_SONAR=true`

---

## Impact sur les ressources

| Mode | CPU | RAM | Disque | Durée |
|------|-----|-----|--------|-------|
| `none` | Faible | ~2 GB | ~500 MB | 5-20 min |
| `ephemere` | Moyen | ~6 GB | ~5 GB | 30-40 min |
| `production` | Moyen | ~6 GB | ~5 GB | 35-45 min |

---

## Modifications du Jenkinsfile

Les stages suivants ont une condition `when` qui vérifie `DEPLOY_ENV != 'none'` :

1. **Build Docker Image (Paketo)** - [Jenkinsfile:461-465](../Jenkinsfile#L461-L465)
   ```groovy
   when {
       expression { params.DEPLOY_ENV != 'none' }
   }
   ```

2. **Tag Image Docker** - [Jenkinsfile:642-648](../Jenkinsfile#L642-L648)
   ```groovy
   when {
       allOf {
           expression { params.DEPLOY_ENV != 'none' }
           expression { params.RUN_SELENIUM_TESTS == true }
       }
   }
   ```

3. **Démarrage Environnement Docker** - [Jenkinsfile:659-665](../Jenkinsfile#L659-L665)
   ```groovy
   when {
       allOf {
           expression { params.DEPLOY_ENV != 'none' }
           expression { params.RUN_SELENIUM_TESTS == true }
       }
   }
   ```

4. **Tests Selenium IHM** - [Jenkinsfile:1082-1088](../Jenkinsfile#L1082-L1088)
   ```groovy
   when {
       allOf {
           expression { params.DEPLOY_ENV != 'none' }
           expression { params.RUN_SELENIUM_TESTS == true }
       }
   }
   ```

---

## Date de mise à jour

**26 novembre 2025** - Ajout de la condition `DEPLOY_ENV != 'none'` pour arrêter le pipeline après SonarQube
