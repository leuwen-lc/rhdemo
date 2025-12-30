# DOCUMENTATIONS À METTRE À JOUR - PROJET RHDEMO

**Date:** 30 décembre 2025
**Version:** 1.0
**Répertoire:** /home/leno-vo/git/repository/rhDemo/docs

---

## RÉSUMÉ EXÉCUTIF

Cette étude inventorie et analyse **16 fichiers de documentation** du projet rhDemo pour identifier les éléments obsolètes suite aux mises à jour de versions.

**Documents à mettre à jour:** 16 / 16 (100%)
- **Critique:** 6 documents
- **Important:** 5 documents
- **Mineur:** 5 documents

**Problèmes majeurs:** 1
- **Version Nginx désynchronisée** entre documentation et implémentation (1.27.3 vs 1.29.4)

**Effort estimé:** 12-16 heures

---

## 1. INVENTAIRE DES FICHIERS

| # | Fichier | Taille | Sujet | Priorité |
|---|---------|--------|-------|----------|
| 1 | CSRF_GUIDE.md | 17,9 KB | Configuration CSRF Spring Security | **CRITIQUE** |
| 2 | DATA_TESTID_GUIDE.md | 12,1 KB | Attributs data-testid Selenium | IMPORTANT |
| 3 | DATABASE.md | 5,8 KB | Gestion base de données PostgreSQL | **CRITIQUE** |
| 4 | JENKINS_EMAIL_SETUP.md | 13,1 KB | Configuration notifications email Jenkins | IMPORTANT |
| 5 | JENKINS_REFACTORING.md | 5,9 KB | Refactorisation du Jenkinsfile | IMPORTANT |
| 6 | MIGRATION-STAGING-TO-EPHEMERE.md | 26,7 KB | Migration environnement staging → ephemere | **CRITIQUE** |
| 7 | OWASP_DEPENDENCY_CHECK.md | 12,4 KB | Analyse vulnérabilités dépendances | **CRITIQUE** |
| 8 | PAGINATION.md | 9,4 KB | Système de pagination côté serveur | MINEUR |
| 9 | PAKETO-DOCKERFILE-MIGRATION.md | 11,8 KB | Migration Paketo → Dockerfile classique | MINEUR |
| 10 | PIPELINES_CI_CD.md | 17,1 KB | Pipelines CI/CD Jenkins | **CRITIQUE** |
| 11 | SECURITE_WEB_CSP.md | 8,9 KB | Content Security Policy | IMPORTANT |
| 12 | SECURITY_ADVISORIES.md | 6,2 KB | Vulnérabilités et remédiations | **CRITIQUE** |
| 13 | SOPS_SETUP.md | 13,8 KB | Configuration SOPS/AGE chiffrement | IMPORTANT |
| 14 | TESTS_INTEGRATION_SANS_KEYCLOAK.md | 7,4 KB | Tests intégration sans Keycloak | MINEUR |
| 15 | TESTS_SECURITY_COVERAGE.md | 10,8 KB | Tests couverture Spring Security | MINEUR |
| 16 | TRIVY_SECURITY_SCAN.md | 6,5 KB | Scan sécurité Trivy images Docker | **CRITIQUE** |

---

## 2. INCOHÉRENCES CRITIQUES IDENTIFIÉES

### 2.1 VERSION NGINX DÉSYNCHRONISÉE ❌ CRITIQUE

**Problème:**
- **SECURITY_ADVISORIES.md** mentionne: `nginx:1.27.3-alpine3.21`
- **docker-compose.yml** affiche: `nginx:1.29.4-alpine`
- **TRIVY_SECURITY_SCAN.md** mentionne: `nginx:1.27.3-alpine3.21`

**Impact:**
- Documentation obsolète OU implémentation non à jour
- Vulnérabilités CVE potentielles non corrigées (CVE-2025-49794/49796)

**Action requise:**
1. Vérifier version Nginx réellement utilisée en production
2. Valider si 1.29.4 contient les CVE fixes
3. Synchroniser docker-compose.yml OU documentation
4. Re-scanner Trivy après synchronisation

### 2.2 SPRING BOOT 3.5.5 vs 3.5.8

**Problème:**
- **CSRF_GUIDE.md** mentionne: "Spring Boot 3.5.5"
- **pom.xml** utilise: version 3.5.8

**Impact:** Mineur (version patch)

**Action requise:** Mettre à jour numéro version dans CSRF_GUIDE.md

---

## 3. MATRICE VERSIONS ACTUELLES vs DOCUMENTÉES

### 3.1 Java & Maven

| Composant | Documenté | Actuel (pom.xml) | Statut |
|-----------|-----------|------------------|--------|
| Java | 21 | 21 (ligne 30) | ✅ Synchro |
| Maven | 3.9 | 3.9-eclipse-temurin-21 | ✅ Synchro |
| Spring Boot | 3.5.5 | 3.5.8 (ligne 8) | ⚠️ Mineur |
| Spring Security | 6+ | 6.x (via parent) | ✅ Synchro |

### 3.2 Frontend

| Composant | Documenté | Actuel (package.json) | Statut |
|-----------|-----------|----------------------|--------|
| Vue.js | 3.0.0 | ^3.0.0 | ✅ Synchro |
| Element Plus | Mentionné | ^2.11.5 | ✅ Synchro |
| Axios | Mentionné | ^1.6.0 | ✅ Synchro |
| Vue Router | Mentionné | ^4.0.0 | ✅ Synchro |

### 3.3 Infrastructure & Conteneurs

| Composant | Documenté | Actuel | Statut |
|-----------|-----------|--------|--------|
| PostgreSQL | 16-alpine | 16-alpine | ✅ Synchro |
| Keycloak | 26.4.2 | 26.4.2 | ✅ Synchro |
| **Nginx** | **1.27.3-alpine3.21** | **1.29.4-alpine** | ❌ **DÉSYNCHRONISÉ** |
| Eclipse Temurin | 21-jre | 21-jre-jammy | ✅ Synchro |

### 3.4 Outils Build/Test

| Composant | Documenté | Actuel | Statut |
|-----------|-----------|--------|--------|
| Trivy | Mentionné (latest) | Latest | ✅ Synchro |
| OWASP Dependency-Check | 11.1.1 | À vérifier pom.xml | ⚠️ À valider |
| Selenium | Mentionné | À lister versions | ⚠️ À valider |
| SonarQube | Mentionné | À vérifier | ⚠️ À valider |
| SOPS | 3.9.0 | À vérifier | ⚠️ À valider |
| AGE | 1.1.1 | À vérifier | ⚠️ À valider |

---

## 4. DOCUMENTS À METTRE À JOUR (PAR PRIORITÉ)

### CRITIQUE (< 24h)

#### 1. SECURITY_ADVISORIES.md
**Priorité:** CRITIQUE
**Effort:** 2h

**Modifications requises:**
- [ ] Valider version Nginx réelle (1.27.3 vs 1.29.4)
- [ ] Mettre à jour si 1.29.4 utilisée
- [ ] Re-valider status CVE-2025-49794/49796 sur version 1.29.4
- [ ] Ajouter timeline validation finale

**Lignes concernées:** Section "Vulnérabilités détectées"

**Fichier:** [SECURITY_ADVISORIES.md](SECURITY_ADVISORIES.md)

---

#### 2. MIGRATION-STAGING-TO-EPHEMERE.md
**Priorité:** CRITIQUE
**Effort:** 3h

**Modifications requises:**
- [ ] Synchroniser versions conteneurs (Nginx surtout)
- [ ] Vérifier port 58443 toujours utilisé
- [ ] Mettre à jour diagrammes réseau si architecture change
- [ ] Valider nommage ressources Docker actuels

**Sections obsolètes:**
- Mentionne `nginx:1.27-alpine` (ligne à localiser)
- Référence Alpine 3.20 vs 3.21

**Fichier:** [MIGRATION-STAGING-TO-EPHEMERE.md](MIGRATION-STAGING-TO-EPHEMERE.md)

---

#### 3. TRIVY_SECURITY_SCAN.md
**Priorité:** CRITIQUE
**Effort:** 1h

**Modifications requises:**
- [ ] Mettre à jour version Nginx (1.29.4 vs 1.27.3)
- [ ] Re-générer rapport consolidé avec versions actuelles
- [ ] Valider CVE CRITICAL toujours à zéro

**Images à mettre à jour:**
```yaml
# Actuellement documenté
- postgres:16-alpine ✅
- quay.io/keycloak/keycloak:26.4.2 ✅
- nginx:1.27.3-alpine3.21 ❌ (devrait être 1.29.4-alpine)
- rhdemo-api:build-${BUILD_NUMBER} ✅
```

**Fichier:** [TRIVY_SECURITY_SCAN.md](TRIVY_SECURITY_SCAN.md)

---

#### 4. PIPELINES_CI_CD.md
**Priorité:** CRITIQUE
**Effort:** 2h

**Modifications requises:**
- [ ] Synchroniser descriptions stages avec Jenkinsfile-CI réel
- [ ] Valider tous les stages existent
- [ ] Mettre à jour versions images si changements

**Stages à vérifier:**
- OWASP Dependency-Check
- Trivy security scan
- SonarQube Quality Gate
- Selenium tests
- OWASP ZAP security

**Fichier:** [PIPELINES_CI_CD.md](PIPELINES_CI_CD.md)

---

#### 5. OWASP_DEPENDENCY_CHECK.md
**Priorité:** CRITIQUE
**Effort:** 1h

**Modifications requises:**
- [ ] Valider version dependency-check-maven (11.1.1) dans pom.xml
- [ ] Mettre à jour seuils CVSS par environnement si nécessaire
- [ ] Ajouter références CVE majeures traitées

**Configuration à vérifier:**
```xml
<failBuildOnCVSS>7.0</failBuildOnCVSS>
```

**Fichier:** [OWASP_DEPENDENCY_CHECK.md](OWASP_DEPENDENCY_CHECK.md)

---

#### 6. DATABASE.md
**Priorité:** CRITIQUE
**Effort:** 30min

**Modifications requises:**
- [ ] Valider chemins pgschema.sql et pgdata.sql
- [ ] Mettre à jour TODO Liquibase si implémenté
- [ ] Synchroniser commandes kubectl avec cluster réel

**Date dernière mise à jour:** 2025-12-12 (récent)

**Fichier:** [DATABASE.md](DATABASE.md)

---

### IMPORTANT (< 1 semaine)

#### 7. CSRF_GUIDE.md
**Priorité:** IMPORTANT
**Effort:** 30min

**Modifications requises:**
- [ ] Mettre à jour version Spring Boot (3.5.5 → 3.5.8)
- [ ] Re-valider exemples code avec version actuelle
- [ ] Vérifier liens Spring Security documentation

**Lignes concernées:**
- Références "Spring Boot 3.5.5" (à localiser)

**Fichier:** [CSRF_GUIDE.md](CSRF_GUIDE.md)

---

#### 8. JENKINS_EMAIL_SETUP.md
**Priorité:** IMPORTANT
**Effort:** 1h

**Modifications requises:**
- [ ] Valider plugins Jenkins installés
- [ ] Mettre à jour adresses SMTP si changement fournisseur
- [ ] Tester configuration réelle

**Configuration à vérifier:**
- Email Extension Plugin
- Mailer Plugin
- Serveurs SMTP (Gmail, Outlook, SendGrid)

**Fichier:** [JENKINS_EMAIL_SETUP.md](JENKINS_EMAIL_SETUP.md)

---

#### 9. SECURITE_WEB_CSP.md
**Priorité:** IMPORTANT
**Effort:** 2h

**Modifications requises:**
- [ ] Mettre à jour captures d'écran Nginx/Keycloak CSP
- [ ] Re-générer rapport ZAP sécurité complet
- [ ] Documenter vulnérabilités acceptées en détail

**Résultats tests ZAP:** 7 vulnérabilités → 2 acceptées (à re-valider)

**Fichier:** [SECURITE_WEB_CSP.md](SECURITE_WEB_CSP.md)

---

#### 10. JENKINS_REFACTORING.md
**Priorité:** IMPORTANT
**Effort:** 30min

**Modifications requises:**
- [ ] Valider fichiers rhDemoLib.groovy existent
- [ ] Vérifier scripts dans scripts/jenkins/ corrects
- [ ] Mettre à jour métriques si code change

**Date:** 2025-12-02 (récent)

**Fichier:** [JENKINS_REFACTORING.md](JENKINS_REFACTORING.md)

---

#### 11. SOPS_SETUP.md
**Priorité:** IMPORTANT
**Effort:** 1h

**Modifications requises:**
- [ ] Valider versions SOPS/AGE installées (3.9.0 / 1.1.1)
- [ ] Tester URLs téléchargement GitHub
- [ ] Mettre à jour si versions plus récentes

**Versions documentées:**
- SOPS: 3.9.0
- AGE: 1.1.1

**Fichier:** [SOPS_SETUP.md](SOPS_SETUP.md)

---

### MINEUR (< 1 mois)

#### 12. DATA_TESTID_GUIDE.md
**Priorité:** MINEUR
**Effort:** 1h

**Modifications requises:**
- [ ] Vérifier tous data-testid existent dans composants Vue réels
- [ ] Valider que Page Objects Selenium correspondent

**Fichier:** [DATA_TESTID_GUIDE.md](DATA_TESTID_GUIDE.md)

---

#### 13. PAGINATION.md
**Priorité:** MINEUR
**Effort:** 30min

**Modifications requises:**
- [ ] Vérifier endpoint /api/employes/page implémenté
- [ ] Valider performances mentionnées (200ms réel)
- [ ] Mettre à jour si pagination change

**Fichier:** [PAGINATION.md](PAGINATION.md)

---

#### 14. PAKETO-DOCKERFILE-MIGRATION.md
**Priorité:** MINEUR
**Effort:** 15min

**Modifications requises:**
- Document surtout historique, peu de changements attendus
- [ ] Mettre à jour si migration vers buildpack inversée

**Date:** 2025-12-11 (très récent)

**Fichier:** [PAKETO-DOCKERFILE-MIGRATION.md](PAKETO-DOCKERFILE-MIGRATION.md)

---

#### 15. TESTS_INTEGRATION_SANS_KEYCLOAK.md
**Priorité:** MINEUR
**Effort:** 30min

**Modifications requises:**
- [ ] Vérifier fichiers test existent et sont à jour
- [ ] Lister données test chargées (test-data.sql)

**Fichier:** [TESTS_INTEGRATION_SANS_KEYCLOAK.md](TESTS_INTEGRATION_SANS_KEYCLOAK.md)

---

#### 16. TESTS_SECURITY_COVERAGE.md
**Priorité:** MINEUR
**Effort:** 1h

**Modifications requises:**
- [ ] Valider fichiers test existent
- [ ] Générer rapport couverture Jacoco actuel
- [ ] Mettre à jour % couverture réels

**Objectif documenté:** 50% couverture code

**Fichiers test à vérifier:**
- `GrantedAuthoritiesKeyCloakMapperTest.java` (100% couverture documentée)
- `SecurityConfigTest.java` (100% couverture documentée)
- `SecurityConfigCspDynamicTest.java`

**Fichier:** [TESTS_SECURITY_COVERAGE.md](TESTS_SECURITY_COVERAGE.md)

---

## 5. ÉLÉMENTS VISUELS À VÉRIFIER

### Screenshots potentiellement obsolètes

| Document | Section | Action |
|----------|---------|--------|
| CSRF_GUIDE.md | DevTools cookies (lignes 217-236) | Vérifier conformité |
| SECURITE_WEB_CSP.md | Diagrammes Nginx/CSP | Mettre à jour |
| MIGRATION-STAGING-TO-EPHEMERE.md | Diagrammes réseau | Valider architecture |

### Liens externes à valider

| Document | Lien | Type | Statut |
|----------|------|------|--------|
| CSRF_GUIDE.md | docs.spring.io/spring-security | Externe | À vérifier |
| CSRF_GUIDE.md | cheatsheetseries.owasp.org | Externe | À vérifier |
| JENKINS_EMAIL_SETUP.md | plugins.jenkins.io/email-ext | Externe | À vérifier |
| JENKINS_EMAIL_SETUP.md | support.google.com/accounts | Externe | À vérifier |
| JENKINS_EMAIL_SETUP.md | support.microsoft.com | Externe | À vérifier |
| SECURITY_ADVISORIES.md | nvd.nist.gov (CVE-2025-49794) | Externe | À vérifier |
| SECURITY_ADVISORIES.md | seal.security.blog | Externe | À vérifier |

---

## 6. PLAN D'ACTION RECOMMANDÉ

### Semaine 1: Documents CRITIQUES

**Jour 1 (2h):**
- [ ] SECURITY_ADVISORIES.md
- [ ] TRIVY_SECURITY_SCAN.md

**Jour 2 (3h):**
- [ ] MIGRATION-STAGING-TO-EPHEMERE.md

**Jour 3 (2h):**
- [ ] PIPELINES_CI_CD.md

**Jour 4 (1h30):**
- [ ] OWASP_DEPENDENCY_CHECK.md
- [ ] DATABASE.md

### Semaine 2: Documents IMPORTANTS

**Jour 1 (2h):**
- [ ] CSRF_GUIDE.md
- [ ] JENKINS_EMAIL_SETUP.md

**Jour 2 (2h):**
- [ ] SECURITE_WEB_CSP.md

**Jour 3 (1h30):**
- [ ] JENKINS_REFACTORING.md
- [ ] SOPS_SETUP.md

### Semaine 3: Documents MINEURS

**Jour 1 (3h):**
- [ ] DATA_TESTID_GUIDE.md
- [ ] PAGINATION.md
- [ ] PAKETO-DOCKERFILE-MIGRATION.md
- [ ] TESTS_INTEGRATION_SANS_KEYCLOAK.md
- [ ] TESTS_SECURITY_COVERAGE.md

---

## 7. ACTIONS PRIORITAIRES

### Action 1: Résoudre désynchronisation Nginx (URGENT)

**Urgence:** CRITIQUE
**Délai:** < 24h

**Tâches:**
1. Vérifier version Nginx réellement utilisée en production
2. Valider si 1.29.4 contient les CVE fixes
3. Mettre à jour docker-compose.yml OU documentation
4. Re-scanner Trivy après synchronisation

**Documents impactés:**
- SECURITY_ADVISORIES.md
- TRIVY_SECURITY_SCAN.md
- MIGRATION-STAGING-TO-EPHEMERE.md

---

### Action 2: Mise à jour versions documentation

**Urgence:** IMPORTANT
**Délai:** < 1 semaine

**Tâches:**
1. Spring Boot 3.5.8 (mettre à jour CSRF_GUIDE.md)
2. Versions images Docker (MIGRATION-STAGING-TO-EPHEMERE.md)
3. Versions outils (JENKINS_REFACTORING.md, SOPS_SETUP.md)

---

### Action 3: Re-validation sécurité

**Urgence:** IMPORTANT
**Délai:** < 2 semaines

**Tâches:**
1. Exécuter scan Trivy complet et documenter résultats
2. Exécuter scan OWASP ZAP et documenter corrections
3. Générer rapport Dependency-Check avec versions actuelles
4. Mettre à jour SECURITY_ADVISORIES.md et TRIVY_SECURITY_SCAN.md

---

### Action 4: Validation tests & couverture

**Urgence:** MINEUR
**Délai:** < 1 mois

**Tâches:**
1. Vérifier tous fichiers test existent (Selenium, Security)
2. Générer rapport couverture Jacoco
3. Mettre à jour TESTS_SECURITY_COVERAGE.md et DATA_TESTID_GUIDE.md

---

## 8. RÉCAPITULATIF EFFORT

### Par priorité

| Priorité | Nombre de Documents | Effort Estimé |
|----------|---------------------|---------------|
| CRITIQUE | 6 | 8-10h |
| IMPORTANT | 5 | 6-8h |
| MINEUR | 5 | 3-4h |
| **TOTAL** | **16** | **17-22h** |

### Par type de modification

| Type | Effort Estimé |
|------|---------------|
| Mises à jour versions | 2-3h |
| Synchronisation configurations | 4-5h |
| Re-génération rapports sécurité | 3-4h |
| Mise à jour diagrammes/screenshots | 2-3h |
| Validation tests/couverture | 2-3h |
| Vérification liens externes | 1-2h |
| **TOTAL** | **14-20h** |

---

## 9. CHECKLIST GLOBALE

### Avant de Commencer

- [ ] Créer branche Git: `feature/update-documentation`
- [ ] Sauvegarder versions actuelles des docs
- [ ] Préparer environnement pour tests (accès Jenkins, SonarQube, ZAP)

### Pendant la Mise à Jour

- [ ] Suivre ordre de priorité (CRITIQUE → IMPORTANT → MINEUR)
- [ ] Valider chaque modification avec code source réel
- [ ] Re-générer rapports si nécessaire (Trivy, ZAP, Jacoco)
- [ ] Tester liens externes
- [ ] Mettre à jour screenshots obsolètes

### Après la Mise à Jour

- [ ] Review complète par pair (développeur senior)
- [ ] Validation technique (exécuter commandes documentées)
- [ ] Commit et push: `git commit -m "docs: update all documentation to reflect current versions"`
- [ ] Pull request avec checklist des changements

---

## 10. CONTACTS ET RESSOURCES

### Documentation de référence

- **Spring Boot:** https://docs.spring.io/spring-boot/docs/current/reference/html/
- **Vue.js:** https://vuejs.org/guide/
- **Element Plus:** https://element-plus.org/en-US/
- **Keycloak:** https://www.keycloak.org/documentation
- **PostgreSQL:** https://www.postgresql.org/docs/
- **Nginx:** https://nginx.org/en/docs/
- **Jenkins:** https://www.jenkins.io/doc/
- **OWASP:** https://owasp.org/

### Outils de validation

- **Trivy:** `trivy image <image_name>`
- **OWASP ZAP:** `docker run -t zaproxy/zap-stable zap-baseline.py`
- **SonarQube:** `./mvnw sonar:sonar`
- **OWASP Dependency-Check:** `./mvnw dependency-check:check`

---

## 11. CONCLUSION

Votre projet rhDemo dispose d'une **documentation très complète** (16 fichiers couvrant tous les aspects techniques, sécurité, CI/CD, tests).

**Points positifs:**
- Documentation exhaustive et bien structurée
- Couverture complète (infrastructure, code, sécurité, tests)
- Mise à jour récente de plusieurs docs (décembre 2025)

**Points d'attention:**
- **Désynchronisation critique Nginx** (1.27.3 vs 1.29.4) à résoudre immédiatement
- Versions mineures à synchroniser (Spring Boot 3.5.5 vs 3.5.8)
- Screenshots et diagrammes potentiellement obsolètes

**Recommandation:** Prioritiser la résolution de l'incohérence Nginx (implications sécurité CVE) avant toute autre mise à jour.

---

**Fin du document**
