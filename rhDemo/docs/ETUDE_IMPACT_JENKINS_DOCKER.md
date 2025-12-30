# ÉTUDE D'IMPACT - INFRASTRUCTURE JENKINS-DOCKER (ZAP, Jenkins, SonarQube)

**Date:** 30 décembre 2025
**Version:** 1.0
**Projet concerné:** rhDemo/infra/jenkins-docker

---

## RÉSUMÉ EXÉCUTIF

Cette étude analyse l'impact des migrations suivantes sur l'infrastructure Jenkins:

| Composant | Version Actuelle | Version Cible | Risque |
|-----------|------------------|---------------|--------|
| Jenkins LTS | 2.528.1 | 2.528.3 | FAIBLE |
| OWASP ZAP | stable | 2.17.0 | FAIBLE |
| SonarQube CE | 25.11.0 | 2025.4 LTA | MOYEN |

**Verdict global:** Migration **RECOMMANDÉE** avec précautions standards.

**Durée estimée:** 4-6 heures (incluant tests complets).

---

## 1. JENKINS 2.528.1 → 2.528.3

### 1.1 Nature de la Mise à Jour

**Type:** Mise à jour mineure (patch de sécurité)
**Date de sortie:** 10 décembre 2025

### 1.2 Breaking Changes

**Aucun breaking change critique** selon l'upgrade guide officiel.

### 1.3 Points d'Attention

#### Timestamper Plugin
**Prérequis:** Timestamper doit être à jour avant migration vers 2.528.x.

**Vérification:**
```bash
# Fichier: /home/leno-vo/git/repository/rhDemo/infra/jenkins-docker/plugins.txt
# Ligne 82: timestamper:latest
```
✅ Déjà configuré en mode `:latest` → compatible.

#### Correctifs de Sécurité
Inclus dans [security advisory 2025-12-10](https://community.jenkins.io/t/jenkins-jenkins-2-528-3-released/35861).

### 1.4 Fichiers à Modifier

**Fichier principal:**

`/home/leno-vo/git/repository/rhDemo/infra/jenkins-docker/Dockerfile.jenkins`

```dockerfile
# AVANT
FROM jenkins/jenkins:lts-jdk21

# APRÈS
FROM jenkins/jenkins:2.528.3-jdk21
```

### 1.5 Compatibilité Jenkinsfiles

**Jenkinsfile-CI** (1622 lignes):
- ✅ Compatible (syntaxe Pipeline Declarative standard)
- Pas de features deprecated détectées

**Jenkinsfile-CD** (698 lignes):
- ✅ Compatible (syntaxe standard)

### 1.6 Tests de Validation

- [ ] Jenkins démarre sans erreur: `docker logs -f rhdemo-jenkins`
- [ ] Tous les plugins chargent: Manage Jenkins → Plugin Manager
- [ ] JCasC appliqué: Vérifier configuration (jenkins-casc.yaml)
- [ ] Pipeline CI complet: Exécuter build test
- [ ] Stage OWASP Dependency-Check fonctionne

### 1.7 Procédure de Migration

```bash
# 1. Modifier Dockerfile.jenkins
cd /home/leno-vo/git/repository/rhDemo/infra/jenkins-docker

# 2. Rebuild image
docker-compose build jenkins

# 3. Redémarrer
docker-compose up -d jenkins

# 4. Vérifier logs
docker logs -f rhdemo-jenkins

# 5. Vérifier version
# Accès UI: http://localhost:8080
# Manage Jenkins → About Jenkins
```

### 1.8 Rollback

```bash
# Restaurer Dockerfile.jenkins avec version précédente
FROM jenkins/jenkins:2.528.1-jdk21

# Rebuild et redémarrer
docker-compose build jenkins
docker-compose up -d jenkins
```

---

## 2. OWASP ZAP stable → 2.17.0

### 2.1 Nature de la Mise à Jour

**Type:** Mise à jour majeure
**Date de sortie:** 15 décembre 2025

### 2.2 Versions Actuelles

**Fichier:** `/home/leno-vo/git/repository/rhDemo/infra/jenkins-docker/docker-compose.zap.yml`

```yaml
# Ligne 50
owasp-zap:
  image: ghcr.io/zaproxy/zaproxy:stable
```

**Recommandation:** Épingler la version spécifique au lieu de `stable`.

### 2.3 Nouvelles Fonctionnalités ZAP 2.17.0

#### Alert De-duplication
**Impact:** Réduction massive des alertes dupliquées.

**Conséquence:** Les rapports ZAP contiendront **MOINS d'alertes** (faux positifs réduits).

**Action:** Revoir les seuils de criticité dans le pipeline si configurés.

#### Systemic Alerts
**Impact:** Marquage des alertes site-wide.

**Nouveaux champs:** Rapports JSON/HTML contiennent section "Systemic".

**Action:** Vérifier l'archivage des rapports (Jenkinsfile-CI lignes 1254-1296).

#### Insights Feature
**Impact:** Nouvelle tab "Insights" pour informations non-vulnérabilités.

**Compatibilité:** Parsing existant reste fonctionnel.

#### Optimisation Ressources
**Impact positif:** Meilleure gestion des erreurs (détection disk/memory space).

#### Temporary HTTP Messages
**Impact:** Non persistés en mode headless par défaut → réduction usage disque.

### 2.4 Compatibilité API/CLI

**Aucun breaking change API documenté.**

**API Key:** Toujours requise (déjà configurée: `env.ZAP_API_KEY`).
**Port unique 8090:** Inchangé (API + Proxy fusionnés).
**Endpoints JSON:** Compatible avec appels existants.

### 2.5 Impact sur Jenkinsfile-CI

**Stages impactés:**

#### Stage "🔒 Démarrage OWASP ZAP Proxy" (lignes 1064-1127)
```groovy
// Aucune modification nécessaire - API compatible
docker-compose -f docker-compose.yml -f docker-compose.zap.yml up -d owasp-zap
```

#### Stage "📝 Génération Rapports" (lignes 1254-1296)
```bash
# API inchangée - endpoints valides
curl "http://${ZAP_HOST}:${ZAP_PORT}/OTHER/core/other/htmlreport/?apikey=${ZAP_API_KEY}"
curl "http://${ZAP_HOST}:${ZAP_PORT}/JSON/core/view/alerts/?apikey=${ZAP_API_KEY}"
```

**Parsing JSON actuel:** Utilise seulement `jq '. | length'` → aucun impact.

### 2.6 Fichiers à Modifier

`/home/leno-vo/git/repository/rhDemo/infra/jenkins-docker/docker-compose.zap.yml`

```yaml
# AVANT (ligne 50)
owasp-zap:
  image: ghcr.io/zaproxy/zaproxy:stable

# APRÈS
owasp-zap:
  image: ghcr.io/zaproxy/zaproxy:2.17.0
```

### 2.7 Prérequis

**Java 17+:** ✅ Déjà satisfait (Jenkins utilise JDK 21).

### 2.8 Tests de Validation

- [ ] Démarrer ZAP: `docker-compose -f docker-compose.zap.yml up -d`
- [ ] Healthcheck: Ligne 104-109 docker-compose.zap.yml
- [ ] Exécuter pipeline CI complet avec Selenium + ZAP
- [ ] Inspecter rapports générés (nouvelle section "Insights" attendue)
- [ ] Valider réduction des alertes dupliquées

### 2.9 Procédure de Migration

```bash
# 1. Modifier docker-compose.zap.yml
cd /home/leno-vo/git/repository/rhDemo/infra/jenkins-docker

# 2. Redémarrer ZAP
docker-compose -f docker-compose.yml -f docker-compose.zap.yml up -d owasp-zap

# 3. Vérifier logs
docker logs -f rhdemo-jenkins-zap

# 4. Vérifier version
curl http://localhost:8090/JSON/core/view/version/?apikey=<KEY>
```

### 2.10 Rollback

```bash
# Restaurer docker-compose.zap.yml
image: ghcr.io/zaproxy/zaproxy:stable

# Redémarrer
docker-compose -f docker-compose.zap.yml down
docker-compose -f docker-compose.yml -f docker-compose.zap.yml up -d owasp-zap
```

---

## 3. SONARQUBE 25.11.0 → 2025.4 LTA

### 3.1 Nature de la Mise à Jour

**Type:** Mise à jour majeure (nouvelle nomenclature version)
**Date de sortie:** Q4 2025

**Notation change:** `25.11.0.114957` (build) → `2025.4.0` (année.trimestre.patch)

### 3.2 Versions Actuelles

**Fichier:** `/home/leno-vo/git/repository/rhDemo/infra/jenkins-docker/docker-compose.yml`

```yaml
# Ligne 106
sonarqube:
  image: sonarqube:25.11.0.114957-community
```

### 3.3 Breaking Changes

**Aucun breaking change** selon la documentation officielle.

### 3.4 Nouvelles Fonctionnalités

#### JRE Auto-Provisioning
**Activé par défaut** pour scanners CI/CD.

**Impact:** Téléchargement automatique JRE si nécessaire (Java 21 déjà disponible).

**Action:** Peut être désactivé au niveau serveur si souhaité.

#### Scanner Engine Optimization
**Impact positif:** Réduction mémoire pour fichiers exclus.

### 3.5 Compatibilité Scanner Maven

**Version actuelle:** `sonar-maven-plugin:5.5.0.6356` (pom.xml ligne 318-319)

**Matrice de compatibilité:**
- ✅ SonarQube 2025.4 LTA requiert **minimum** Scanner Maven 5.1.0
- ✅ Version actuelle 5.5.0.6356 est **supérieure** et compatible
- ✅ **Pas de mise à jour scanner nécessaire**

Source: [SonarScanner Maven Compatibility](https://docs.sonarsource.com/sonarqube-server/analyzing-source-code/scanners/sonarscanner-for-maven)

### 3.6 Configuration pom.xml

**Aucune modification requise.**

```xml
<!-- pom.xml lignes 315-320 -->
<plugin>
    <groupId>org.sonarsource.scanner.maven</groupId>
    <artifactId>sonar-maven-plugin</artifactId>
    <version>5.5.0.6356</version>
</plugin>
```

### 3.7 Impact sur Jenkinsfile-CI

**Stages impactés:**

#### Stage "📊 Analyse SonarQube" (lignes 540-555)
```groovy
withSonarQubeEnv('SonarQube') {
    sh './mvnw sonar:sonar'
}
// Compatible - pas de modification nécessaire
```

#### Stage "🚦 Quality Gate SonarQube" (lignes 557-570)
```groovy
waitForQualityGate abortPipeline: true
// API Quality Gate inchangée - compatible
```

### 3.8 Migration Base de Données

**CRITIQUE:** SonarQube nécessite migration automatique de la DB PostgreSQL.

**Procédure:**

1. **Backup DB avant migration:**
```bash
docker exec rhdemo-sonarqube-db pg_dump -U sonar sonar > sonar_backup_$(date +%Y%m%d).sql
```

2. **Démarrage nouvelle version:**
- Premier démarrage: migration automatique (5-15 min)
- Logs à surveiller: `docker logs -f rhdemo-sonarqube`

3. **Vérification post-migration:**
- URL: http://localhost:9020
- Vérifier projets existants intacts
- Re-générer token si expiré (credential `jenkins-sonar-token`)

### 3.9 Fichiers à Modifier

`/home/leno-vo/git/repository/rhDemo/infra/jenkins-docker/docker-compose.yml`

```yaml
# AVANT (ligne 106)
sonarqube:
  image: sonarqube:25.11.0.114957-community

# APRÈS
sonarqube:
  image: sonarqube:2025.4.0-community
```

### 3.10 Tests de Validation

- [ ] Backup DB SonarQube avant test
- [ ] Démarrer nouveau SonarQube 2025.4
- [ ] Vérifier migration DB réussie (logs)
- [ ] Exécuter analyse Maven: `./mvnw sonar:sonar`
- [ ] Valider Quality Gate dans pipeline CI
- [ ] Inspecter nouvelles règles détectées

### 3.11 Procédure de Migration

```bash
# 1. Arrêter SonarQube actuel
docker-compose stop sonarqube

# 2. Backup DB (OBLIGATOIRE)
docker exec rhdemo-sonarqube-db pg_dump -U sonar sonar > sonar_backup_$(date +%Y%m%d).sql

# 3. Modifier docker-compose.yml
# Ligne 106: sonarqube:2025.4.0-community

# 4. Démarrer nouvelle version
docker-compose up -d sonarqube

# 5. Surveiller migration DB (peut prendre 5-15 min)
docker logs -f rhdemo-sonarqube

# 6. Attendre "SonarQube is operational"

# 7. Vérifier accès UI
# http://localhost:9020

# 8. Re-générer token si nécessaire
# Admin → My Account → Security → Tokens
# Mettre à jour credential Jenkins: jenkins-sonar-token
```

### 3.12 Rollback

```bash
# 1. Arrêter SonarQube 2025.4
docker-compose stop sonarqube sonarqube-db

# 2. Restaurer backup DB
docker exec -i rhdemo-sonarqube-db psql -U sonar -d sonar < sonar_backup_YYYYMMDD.sql

# 3. Restaurer image précédente
# Éditer docker-compose.yml → sonarqube:25.11.0.114957-community

# 4. Redémarrer
docker-compose up -d sonarqube
```

---

## 4. ORDRE DE MIGRATION

### Phase 1: Préparation (30 minutes)

**Backups complets:**

```bash
# Volumes Jenkins
docker run --rm -v rhdemo-jenkins-home:/data -v $(pwd):/backup \
  alpine tar czf /backup/jenkins_home_backup_$(date +%Y%m%d).tar.gz /data

# DB SonarQube
docker exec rhdemo-sonarqube-db pg_dump -U sonar sonar > sonar_backup_$(date +%Y%m%d).sql

# Volumes ZAP
docker run --rm -v rhdemo-jenkins-zap-sessions:/data -v $(pwd):/backup \
  alpine tar czf /backup/zap_sessions_backup_$(date +%Y%m%d).tar.gz /data
```

**Vérifier pré-requis:**
- [ ] Timestamper plugin à jour (plugins.txt ligne 82)
- [ ] Credential `jenkins-sonar-token` valide
- [ ] Clé API NVD configurée (`nvd-api-key`)

### Phase 2: Migration Jenkins (1 heure)

**Risque:** FAIBLE (mise à jour mineure 2.528.1 → 2.528.3)

1. Modifier Dockerfile.jenkins: `FROM jenkins/jenkins:2.528.3-jdk21`
2. Rebuild image: `docker-compose build jenkins`
3. Redémarrer: `docker-compose up -d jenkins`
4. Validation:
   - Accès UI: http://localhost:8080
   - Vérifier version: Manage Jenkins → About Jenkins
   - Tester pipeline CI (build test sans publish)

### Phase 3: Migration SonarQube (2-3 heures)

**Risque:** MOYEN (migration DB requise)

1. Arrêter SonarQube actuel
2. Backup DB (déjà fait en Phase 1)
3. Modifier docker-compose.yml: `sonarqube:2025.4.0-community`
4. Démarrer nouvelle version
5. Attendre fin migration (logs: "SonarQube is operational")
6. Vérifier token: http://localhost:9020 → Admin → My Account → Security
7. Validation:
   - Tester analyse: `./mvnw sonar:sonar`
   - Vérifier Quality Gate dans SonarQube UI

### Phase 4: Migration ZAP (30 minutes)

**Risque:** FAIBLE (API compatible)

1. Modifier docker-compose.zap.yml: `ghcr.io/zaproxy/zaproxy:2.17.0`
2. Redémarrer ZAP: `docker-compose -f docker-compose.yml -f docker-compose.zap.yml up -d owasp-zap`
3. Validation:
   - Healthcheck: `curl http://localhost:8090/JSON/core/view/version/?apikey=<KEY>`
   - Tester pipeline CI complet avec Selenium + ZAP

### Phase 5: Validation Globale (1 heure)

1. **Pipeline CI complet:**
   - Déclencher build avec `RUN_SELENIUM_TESTS=true`
   - Vérifier tous les stages passent
   - Inspecter rapports ZAP (nouvelles alertes "Systemic", section "Insights")

2. **Pipeline CD test:**
   - Déployer sur stagingkub
   - Valider health checks

3. **Rollback plan vérifié** (restaurer backups si nécessaire)

---

## 5. FICHIERS À MODIFIER (RÉCAPITULATIF)

### Modifications Critiques

1. `/home/leno-vo/git/repository/rhDemo/infra/jenkins-docker/Dockerfile.jenkins`
```dockerfile
FROM jenkins/jenkins:2.528.3-jdk21
```

2. `/home/leno-vo/git/repository/rhDemo/infra/jenkins-docker/docker-compose.yml`
```yaml
sonarqube:
  image: sonarqube:2025.4.0-community
```

3. `/home/leno-vo/git/repository/rhDemo/infra/jenkins-docker/docker-compose.zap.yml`
```yaml
owasp-zap:
  image: ghcr.io/zaproxy/zaproxy:2.17.0
```

### Modifications Optionnelles

4. `/home/leno-vo/git/repository/rhDemo/infra/jenkins-docker/README.md`
```markdown
| Jenkins LTS | 2.528.3 | Serveur CI/CD |
| OWASP ZAP | 2.17.0 | Proxy sécurité avec alertes de-duplicated |
| SonarQube CE | 2025.4.0 | Analyse qualité (LTA) |
```

### Fichiers à NE PAS Modifier

- ✅ jenkins-casc.yaml: Compatible tel quel
- ✅ plugins.txt: Mode `:latest` auto-compatible
- ✅ Jenkinsfile-CI: Syntaxe standard compatible
- ✅ Jenkinsfile-CD: Pas d'impact
- ✅ pom.xml: sonar-maven-plugin 5.5.0.6356 compatible

---

## 6. MATRICE DE RISQUES

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Migration DB SonarQube échoue | Faible | Critique | Backup DB obligatoire avant migration |
| Quality Gate cassé après SonarQube 2025.4 | Faible | Moyen | Tester analyse avant prod |
| Rapports ZAP changent de format | Très faible | Faible | API JSON rétrocompatible |
| Plugins Jenkins incompatibles | Très faible | Moyen | Plugins en `:latest` auto-update |
| Timeout migration SonarQube | Faible | Faible | Migration peut prendre 15 min |

---

## 7. CRITÈRES DE SUCCÈS

**Validation migration:**

✅ Jenkins 2.528.3 démarre sans erreur
✅ Tous les plugins chargent correctement
✅ JCasC appliqué sans erreur
✅ SonarQube accessible après migration DB
✅ ZAP healthcheck passe
✅ Pipeline CI complet exécuté avec succès:
- Stage Compilation Maven OK
- Stage Tests Unitaires OK
- Stage OWASP Dependency-Check OK
- Stage Analyse SonarQube OK
- Stage Quality Gate OK
- Stage Build Docker OK
- Stage Tests Selenium + ZAP OK
- Stage Rapports ZAP OK (JSON/HTML générés)
✅ Pipeline CD test OK (déploiement stagingkub)
✅ Scan Trivy: pas de CVE critiques

**Critères d'échec (rollback immédiat):**

❌ Jenkins ne démarre pas
❌ SonarQube refuse migration DB
❌ Keycloak 26.4.7 ne démarre pas
❌ Login OAuth2 échoue
❌ Tests Selenium échouent massivement (>20%)
❌ Quality Gate bloque builds valides

---

## 8. CHECKLIST DE DÉPLOIEMENT

### Avant Migration

- [ ] Backup volumes Jenkins (rhdemo-jenkins-home)
- [ ] Backup DB SonarQube (dump PostgreSQL)
- [ ] Backup volumes ZAP (rhdemo-jenkins-zap-sessions, rhdemo-jenkins-zap-reports)
- [ ] Vérifier credential `jenkins-sonar-token` valide
- [ ] Vérifier credential `nvd-api-key` configuré
- [ ] Vérifier credential `sops-age-key` présent
- [ ] Documenter versions actuelles (pour rollback)
- [ ] Planifier fenêtre de maintenance (4-6h)

### Pendant Migration

- [ ] Modifier Dockerfile.jenkins → Jenkins 2.528.3
- [ ] Modifier docker-compose.yml → SonarQube 2025.4.0
- [ ] Modifier docker-compose.zap.yml → ZAP 2.17.0
- [ ] Rebuild image Jenkins
- [ ] Redémarrer Jenkins, vérifier logs
- [ ] Démarrer SonarQube 2025.4, surveiller migration DB
- [ ] Redémarrer ZAP, vérifier healthcheck
- [ ] Tester pipeline CI complet
- [ ] Inspecter nouveaux rapports ZAP (Insights, alertes)

### Après Migration

- [ ] Vérifier tous les jobs Jenkins visibles
- [ ] Vérifier projets SonarQube visibles
- [ ] Tester Quality Gate sur nouveau build
- [ ] Valider rapports archivés (format compatible)
- [ ] Documenter nouvelles versions dans README.md
- [ ] Supprimer backups si migration réussie (après 1 semaine)
- [ ] Communiquer équipe dev sur nouvelles fonctionnalités ZAP/SonarQube

---

## 9. OPTIMISATIONS POST-MIGRATION

### SonarQube 2025.4 - JRE Auto-Provisioning
- Vérifier si téléchargement JRE automatique souhaité
- Désactiver au niveau serveur si environnement contrôlé

### ZAP 2.17.0 - Alertes Optimisées
- Revoir seuils de criticité si configurés (moins d'alertes dupliquées)
- Exploiter nouvelle section "Insights" dans rapports
- Configurer filtres pour alertes "Systemic" si besoin

### Jenkins - Plugins
- Envisager épingler versions critiques au lieu de `:latest` (meilleure reproductibilité)
- Exemple: `dependency-check-jenkins-plugin:5.2.4` au lieu de `latest`

---

## 10. SOURCES

- [Jenkins 2.528.3 Release Notes](https://community.jenkins.io/t/jenkins-jenkins-2-528-3-released/35861)
- [Jenkins LTS Upgrade Guide 2.528.x](https://www.jenkins.io/doc/upgrade-guide/2.528/)
- [OWASP ZAP 2.17.0 Release Blog](https://www.zaproxy.org/blog/2025-12-15-zap-2-17-0/)
- [OWASP ZAP 2.17.0 Release Notes](https://www.zaproxy.org/docs/desktop/releases/2.17.0/)
- [SonarQube 2025.4 LTA Release Notes](https://docs.sonarsource.com/sonarqube-server/2025.4/server-update-and-maintenance/release-notes)
- [SonarScanner for Maven Compatibility](https://docs.sonarsource.com/sonarqube-server/analyzing-source-code/scanners/sonarscanner-for-maven)

---

**Fin du document**
