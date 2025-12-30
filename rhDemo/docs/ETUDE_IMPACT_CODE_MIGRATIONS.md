# ÉTUDE D'IMPACT - MIGRATIONS CODE (Java, Maven, Spring Boot, Vue, Element Plus, PostgreSQL)

**Date:** 30 décembre 2025
**Version:** 1.0
**Projets concernés:** rhDemo, rhDemoAPITestIHM, rhDemoInitKeycloak

---

## RÉSUMÉ EXÉCUTIF

Cette étude analyse l'impact des migrations suivantes sur le code des 3 projets :

| Composant | Version Actuelle | Version Cible | Risque |
|-----------|------------------|---------------|--------|
| Java | 21 | 25.0.1 | MOYEN |
| Maven | 3.9.11 | 3.9.12 | FAIBLE |
| Spring Boot | 3.5.8 | 4.0.1 | **CRITIQUE** |
| Vue.js | 3.0.0 | 3.5.26 | FAIBLE |
| Element Plus | 2.11.5 | 2.13.0 | FAIBLE |
| PostgreSQL | 16-alpine | 18.1 | MOYEN |

**Verdict global:** Migration **PARTIELLEMENT RECOMMANDÉE**

**Recommandation principale:** NE PAS migrer vers Spring Boot 4.0.1 immédiatement (version trop récente, dépendances instables).

---

## 1. JAVA 21 → 25.0.1

### 1.1 Breaking Changes Confirmés

#### JEP 451 - Dynamic Agent Loading
**Impact:** MOYEN
**Affecté:** Tests avec Mockito (rhDemo/pom.xml lignes 146-148)

```xml
<argLine>
    -javaagent:${settings.localRepository}/org/mockito/mockito-core/${mockito.version}/mockito-core-${mockito.version}.jar
</argLine>
```

**Action:** Warnings attendus lors de l'exécution des tests (non bloquant).

#### JEP 490 - Generational ZGC obligatoire
**Impact:** FAIBLE
Vous utilisez G1GC (Dockerfile ligne 78) → pas d'impact.

#### Compact Object Headers (JEP 519)
**Impact:** POSITIF
Réduction mémoire de 10-15% automatique.

### 1.2 Compatibilité Dépendances

| Bibliothèque | Version Actuelle | Statut Java 25 |
|--------------|------------------|----------------|
| Selenium WebDriver | 4.15.0 | ✅ Compatible (recommandé: upgrade vers 4.35.0) |
| Keycloak Admin Client | 26.0.7 | ✅ Compatible |
| PostgreSQL JDBC | Géré par Spring Boot | ✅ Compatible |
| Spring Boot | 3.5.8 | ✅ Compatible |

### 1.3 Fichiers à Modifier

**Obligatoires:**

1. `/home/leno-vo/git/repository/rhDemo/pom.xml`
   - Ligne 30: `<java.version>25</java.version>`
   - Ligne 135: `<BP_JVM_VERSION>25</BP_JVM_VERSION>`

2. `/home/leno-vo/git/repository/rhDemo/Dockerfile`
   - Lignes 11, 41: `eclipse-temurin:25-jre-jammy`

3. `/home/leno-vo/git/repository/rhDemoAPITestIHM/pom.xml`
   - Lignes 17-18: `<maven.compiler.source>25</maven.compiler.source>` et `.target`

4. `/home/leno-vo/git/repository/rhDemoInitKeycloak/pom.xml`
   - Ligne 24: `<java.version>25</java.version>`

**Recommandés:**

5. `/home/leno-vo/git/repository/rhDemoAPITestIHM/pom.xml`
   - Ligne 19: Upgrade Selenium vers `4.35.0`

### 1.4 Tests Requis

- [ ] Tests unitaires: `./mvnw test` (vérifier warnings JEP 451)
- [ ] Tests d'intégration: `./mvnw verify`
- [ ] Tests Selenium: `cd rhDemoAPITestIHM && ./mvnw test`
- [ ] Build Docker: Vérifier images avec JRE 25

---

## 2. MAVEN 3.9.11 → 3.9.12

### 2.1 Breaking Changes

**Aucun breaking change critique** pour vos plugins.

### 2.2 Fichiers à Modifier

**Obligatoires:**

1. `/home/leno-vo/git/repository/rhDemo/.mvn/wrapper/maven-wrapper.properties`
   - Ligne 2: `distributionUrl=...apache-maven-3.9.12-bin.zip`

2. Répéter pour les 2 autres projets si wrappers présents:
   - `/home/leno-vo/git/repository/rhDemoAPITestIHM/.mvn/wrapper/maven-wrapper.properties`
   - `/home/leno-vo/git/repository/rhDemoInitKeycloak/.mvn/wrapper/maven-wrapper.properties`

### 2.3 Tests Requis

- [ ] `./mvnw clean verify` sur chaque projet
- [ ] Vérifier absence de warnings plugins

---

## 3. SPRING BOOT 3.5.8 → 4.0.1

### ⚠️ ATTENTION: MIGRATION CRITIQUE

### 3.1 Prérequis Obligatoires

- **Jakarta EE 11**
- **Spring Framework 7.x**
- **Java 17 minimum** (25 recommandé)
- **JUnit 6** (au lieu de JUnit 5)
- **Jackson 3.x** (au lieu de 2.x)

### 3.2 Breaking Changes Majeurs

#### 3.2.1 BLOQUANT - springdoc-openapi incompatible

**Situation actuelle:** `springdoc-openapi-starter-webmvc-ui:2.8.14`
**Requis:** `springdoc-openapi-starter-webmvc-ui:3.0.0-M1` (MILESTONE - non stable)

**Risque:** Version milestone non production-ready, bugs possibles avec Jackson 3.x.

#### 3.2.2 CRITIQUE - Spring Security 7

**Fichiers impactés:**
- `/home/leno-vo/git/repository/rhDemo/src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java` (210 lignes)
- `/home/leno-vo/git/repository/rhDemo/src/main/java/fr/leuwen/rhdemoAPI/springconfig/GrantedAuthoritiesKeyCloakMapper.java`

**Changements API attendus:**
- `SecurityFilterChain` configuration
- `CsrfTokenRepository` et `CsrfTokenRequestHandler`
- `OAuth2LoginConfigurer`
- Headers CSP dynamiques

**Action:** Refactorisation complète nécessaire (estimation: 15-20 j/h).

#### 3.2.3 Migration JUnit 5 → JUnit 6

**Impact:** Tous les fichiers `*Test.java` et `*IT.java` (environ 24 fichiers Java dans rhDemo).

#### 3.2.4 Properties renommées

**Exemples:**
```yaml
# AVANT
management.tracing.enabled: true
spring.dao.exceptiontranslation.enabled: true

# APRÈS
management.tracing.export.enabled: true
spring.persistence.exceptiontranslation.enabled: true
```

### 3.3 Fichiers à Modifier (si migration)

**Obligatoires:**

1. `/home/leno-vo/git/repository/rhDemo/pom.xml`
   - Ligne 8: `<version>4.0.1</version>`
   - Ligne 79: springdoc-openapi `<version>3.0.0-M1</version>`

2. `/home/leno-vo/git/repository/rhDemoInitKeycloak/pom.xml`
   - Ligne 11: `<version>4.0.1</version>`

3. **Refactorisation SecurityConfig.java** (critique)

4. **Migration tests JUnit 5 → JUnit 6**

5. **Mise à jour application*.yml** (properties renommées)

### 3.4 Risques Identifiés

| Risque | Niveau | Mitigation |
|--------|--------|------------|
| springdoc-openapi 3.0.0-M1 instable | CRITIQUE | Tests intensifs Swagger UI |
| SecurityConfig refactorisation | CRITIQUE | Pair programming, tests sécurité complets |
| OAuth2 Keycloak incompatibilité | ÉLEVÉ | Validation avec Keycloak 26.4.7 |
| JUnit 6 migration | MOYEN | Migration progressive, tests automatisés |
| Jackson 3.x | MOYEN | Tests sérialisation/désérialisation JSON |

### 3.5 RECOMMANDATION SPRING BOOT 4.0

**❌ NE PAS MIGRER vers Spring Boot 4.0.1 en production immédiatement**

**Raisons:**
1. springdoc-openapi 3.0.0-M1 est MILESTONE (non stable)
2. Spring Boot 4.0 sorti récemment (novembre 2025) - maturité insuffisante
3. Risque critique sur SecurityConfig (210 lignes à refactoriser)
4. Effort: 15-20 jours/homme

**Alternative recommandée:**
- Rester en Spring Boot 3.5.8 (stable)
- Attendre Spring Boot 4.0.x stable + springdoc-openapi 3.0.0 stable (Q1-Q2 2026)

---

## 4. VUE 3.0.0 → 3.5.26

### 4.1 Breaking Changes

**Aucun breaking change** entre Vue 3.0.0 et 3.5.26 (rétrocompatible).

### 4.2 Changements Mineurs (Vue 3.4)

**Event listeners @vnodeXXX dépréciés:**
```vue
<!-- AVANT -->
<component @vnodeMounted="handler" />

<!-- APRÈS -->
<component @vue:mounted="handler" />
```

**Action:** Audit du code frontend pour détecter `@vnodeXXX`.

### 4.3 Améliorations Performance

- Système de réactivité: -56% mémoire
- Impact: **POSITIF** (amélioration gratuite)

### 4.4 Fichiers à Modifier

**Obligatoires:**

1. `/home/leno-vo/git/repository/rhDemo/frontend/package.json`
   - Ligne 13: `"vue": "^3.5.26"`

**Recommandés:**

2. Audit des fichiers `.vue` pour détecter `@vnodeXXX`

### 4.5 Tests Requis

- [ ] Build frontend: `npm run build` (via frontend-maven-plugin)
- [ ] Tests visuels complets de tous les écrans
- [ ] Tests Selenium IHM: Vérifier tous les scénarios

---

## 5. ELEMENT PLUS 2.11.5 → 2.13.0

### 5.1 Breaking Changes

**Aucun breaking change majeur** documenté.

### 5.2 Bug Fixes (2.13.0)

Composants corrigés:
- `splitter`: Conservation taille panel
- `tree-v2`: Icônes affichage
- `textarea`: Autosize dans Splitter
- `form-item`: inline-message undefined par défaut
- `select/v2`: Largeur dropdown
- `time-picker`: Auto-génération ID pour type range

### 5.3 Fichiers à Modifier

**Obligatoires:**

1. `/home/leno-vo/git/repository/rhDemo/frontend/package.json`
   - Ligne 12: `"element-plus": "^2.13.0"`

### 5.4 Tests Requis

- [ ] Test visuel complet de tous les composants Element Plus utilisés
- [ ] Vérifier formulaires (form-item, textarea, select)
- [ ] Tests Selenium: Scénarios CRUD complets

---

## 6. POSTGRESQL 16 → 18.1

### 6.1 Breaking Changes Critiques

#### Data Checksums activés par défaut

**Impact:** Migration depuis PostgreSQL 16 sans checksums nécessite option `--no-data-checksums` OU dump/restore.

**Action:** Utiliser dump/restore (recommandé pour environnements containerisés).

#### Time Zone Abbreviations

**Impact:** FAIBLE (pas d'utilisation de TZ abbreviations custom détectée).

### 6.2 Compatibilité SQL

**Schéma analysé:** `pgschema.sql` (1 table `employes`, 5 index)

| Instruction | PostgreSQL 16 | PostgreSQL 18 | Statut |
|-------------|---------------|---------------|--------|
| `BIGSERIAL` | ✅ | ✅ | Compatible |
| `VARCHAR(n)` | ✅ | ✅ | Compatible |
| `CREATE INDEX` | ✅ | ✅ | Compatible |
| `CREATE UNIQUE INDEX` | ✅ | ✅ | Compatible |
| `INSERT INTO` | ✅ | ✅ | Compatible |

**Verdict:** Schéma et données **100% compatibles** sans modification.

### 6.3 Nouvelles Fonctionnalités

| Feature | Bénéfice |
|---------|----------|
| Asynchronous I/O (AIO) | Amélioration jusqu'à 3x pour scans séquentiels |
| Skip Scan | Optimisation index B-tree multi-colonnes |
| Data Checksums | Détection corruption données |
| uuidv7() | UUIDs ordonnés par timestamp |

### 6.4 Driver JDBC PostgreSQL

**Version actuelle:** Gérée par Spring Boot 3.5.8 (~42.7.x)
**Compatibilité:** PostgreSQL 8.4 → PostgreSQL 18+ ✅

**Action:** Aucune mise à jour driver nécessaire.

### 6.5 Procédure de Migration

**Option recommandée:** Dump/Restore

```bash
# 1. Sauvegarde PostgreSQL 16
docker exec rhdemo-db pg_dumpall -U rhdemo > rhdemo_pg16_backup.sql

# 2. Arrêter et supprimer volumes
docker-compose down -v

# 3. Mettre à jour docker-compose.yml
# Remplacer postgres:16-alpine par postgres:18.1-alpine

# 4. Démarrer PostgreSQL 18.1
docker-compose up -d rhdemo-db

# 5. Restaurer données
docker exec -i rhdemo-db psql -U rhdemo < rhdemo_pg16_backup.sql

# 6. Vérifier checksums
docker exec rhdemo-db pg_controldata | grep checksum
```

### 6.6 Fichiers à Modifier

**Environnement DEV:**
- `/home/leno-vo/git/repository/rhDemo/infra/dev/docker-compose.yml`
  - Ligne 6: `postgres:18.1-alpine`

**Environnement EPHEMERE:**
- `/home/leno-vo/git/repository/rhDemo/infra/ephemere/docker-compose.yml`
  - Lignes 6 et 29: `postgres:18.1-alpine`
- `/home/leno-vo/git/repository/rhDemo/Jenkinsfile-CI`
  - Ligne 49: `POSTGRES_IMAGE = "postgres:18.1-alpine"`

**Environnement STAGINGKUB:**
- `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/rhdemo/values.yaml`
  - Lignes 15-16: `tag: "18.1-alpine"`
  - Lignes 50-52: `tag: "18.1-alpine"`

### 6.7 Tests Requis

- [ ] Vérifier version: `SELECT version();`
- [ ] Vérifier checksums: `pg_controldata | grep checksum`
- [ ] Compter employés: `SELECT COUNT(*) FROM employes;` (doit retourner 304)
- [ ] Tests d'intégration API complets
- [ ] Mesures performance I/O (avant/après)

### 6.8 Rollback

**ATTENTION:** Migration PostgreSQL 16 → 18 est **IRRÉVERSIBLE** (PostgreSQL 16 ne peut pas lire dumps PG 18).

**Stratégie:** Conserver dumps PostgreSQL 16 avant migration. En cas d'échec: détruire volumes PG 18 et restaurer depuis dump PG 16.

---

## 7. PLAN DE MIGRATION RECOMMANDÉ

### Phase 1: Fondations (Java 25 + Maven 3.9.12)
**Durée:** 1 semaine
**Risque:** FAIBLE à MOYEN

1. Maven Wrapper 3.9.11 → 3.9.12
2. Java 21 → 25.0.1
3. Upgrade Selenium 4.15.0 → 4.35.0 (rhDemoAPITestIHM)

**Validation:**
- Tests unitaires: 100% passés
- Tests d'intégration: 100% passés
- Tests Selenium IHM: 100% passés
- Warnings JEP 451 acceptables (documentés)

### Phase 2: Frontend (Vue 3.5.26 + Element Plus 2.13.0)
**Durée:** 3 jours
**Risque:** FAIBLE

1. Vue 3.0.0 → 3.5.26
2. Element Plus 2.11.5 → 2.13.0
3. Audit code `.vue` pour `@vnodeXXX`

**Validation:**
- Build frontend: succès
- Tests Selenium IHM: 100% passés
- Tests visuels UI: tous composants fonctionnels

### Phase 3: PostgreSQL 18.1
**Durée:** 1 semaine (incluant backups)
**Risque:** MOYEN

1. **BACKUP COMPLET** obligatoire
2. Migration dump/restore
3. Validation intégrité données

**Validation:**
- Dump pre-migration réussi
- Migration réussie
- Vérification intégrité: COUNT(*) = 304
- Tests d'intégration API: 100% passés
- Performance I/O: mesures avant/après

### Phase 4: Spring Boot 4.0.1 (NON RECOMMANDÉ)
**Durée:** 3-4 semaines
**Risque:** **CRITIQUE**

**RECOMMANDATION:** **ATTENDRE Q1-Q2 2026** pour:
- Spring Boot 4.0.x stable
- springdoc-openapi 3.0.0 stable
- Écosystème mature

---

## 8. EFFORT ET PLANNING

### 8.1 Estimation Effort

| Phase | Durée | Effort (j/h) | Risque |
|-------|-------|--------------|--------|
| Phase 1: Java 25 + Maven | 1 semaine | 3 j/h | FAIBLE |
| Phase 2: Frontend | 3 jours | 2 j/h | FAIBLE |
| Phase 3: PostgreSQL 18.1 | 1 semaine | 5 j/h | MOYEN |
| Phase 4: Spring Boot 4.0 (NON RECOMMANDÉ) | 3-4 semaines | 15-20 j/h | CRITIQUE |

**Total recommandé (Phases 1-3):** 10 jours/homme
**Total complet (Phases 1-4):** 25-30 jours/homme

### 8.2 Planning Suggéré

**Semaine 1-2:** Phase 1 (Java 25 + Maven)
**Semaine 3:** Phase 2 (Frontend)
**Semaine 4-5:** Phase 3 (PostgreSQL 18.1)
**Q1-Q2 2026:** Phase 4 (Spring Boot 4.0 quand stable)

---

## 9. CHECKLIST PRÉ-MIGRATION

### Avant de Commencer

- [ ] Backup complet base de données PostgreSQL
- [ ] Tags Git sur branches master des 3 projets
- [ ] Documentation architecture actuelle
- [ ] Environnement de staging fonctionnel
- [ ] Lecture Spring Boot 4.0 Migration Guide (si Phase 4)
- [ ] Review breaking changes Java 25
- [ ] Validation disponibilité équipe (10 j/h)
- [ ] Communication stakeholders

### Pendant la Migration

- [ ] Tests après chaque phase
- [ ] Logs de migration détaillés
- [ ] Documentation changements
- [ ] Revue de code (pair programming pour SecurityConfig si Phase 4)

### Après la Migration

- [ ] Tests de régression complets
- [ ] Tests de performance (baseline vs post-migration)
- [ ] Documentation mise à jour
- [ ] Formation équipe sur nouveautés
- [ ] Monitoring production renforcé (1 semaine)

---

## 10. MATRICE DE RISQUES

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Warnings JEP 451 (Java 25) | Élevé | Faible | Accepter warnings, documenter |
| Régression tests Selenium | Faible | Moyen | Suite tests complète |
| Migration PostgreSQL échec | Faible | Élevé | Backup obligatoire, dump/restore |
| Spring Boot 4.0 instabilité | **Élevé** | **Critique** | **NE PAS MIGRER maintenant** |
| springdoc-openapi milestone | **Élevé** | **Critique** | **ATTENDRE version stable** |
| SecurityConfig refactorisation | Moyen | Critique | Tests sécurité intensifs, pair programming |

---

## 11. RECOMMANDATIONS FINALES

### 11.1 Migration Partielle (RECOMMANDÉ)

**Migrer maintenant:**
- ✅ Java 21 → 25.0.1
- ✅ Maven 3.9.11 → 3.9.12
- ✅ Vue 3.0.0 → 3.5.26
- ✅ Element Plus 2.11.5 → 2.13.0
- ✅ PostgreSQL 16 → 18.1

**Attendre Q1-Q2 2026:**
- ❌ Spring Boot 3.5.8 → 4.0.x (attendre version stable)

**Avantages:**
- Bénéficier immédiatement de Java 25 (performances, sécurité)
- Vue 3.5.26 + Element Plus 2.13.0 (stabilité, performances)
- PostgreSQL 18.1 (I/O asynchrone, skip scan)
- Rester en Spring Boot 3.5.8 (version stable, testée)
- Attendre maturité Spring Boot 4.0 + écosystème

### 11.2 Mesures de Mitigation

**SI migration Spring Boot 4.0 décidée:**

1. Environnement de staging dédié (tests 2-4 semaines)
2. Rollback plan complet (backups, scripts automatisés)
3. Monitoring renforcé (Actuator, logs DEBUG, erreurs Swagger)
4. Support communautaire (suivre issues GitHub springdoc/spring-boot)
5. Plan de contingence (rollback vers 3.5.8 si bugs bloquants)

---

## 12. SOURCES

### Java 25
- [Significant Changes in JDK 25](https://docs.oracle.com/en/java/javase/25/migrate/significant-changes-jdk-25.html)
- [Migrating from Java 21 to Java 25 - OpenJ9](https://eclipse.dev/openj9/docs/migrating21to25/)
- [Java 25 Migration Guide PDF](https://docs.oracle.com/en/java/javase/25/migrate/jdk-migration-guide.pdf)

### Maven
- [Maven 3.9.12 Release Notes](https://maven.apache.org/docs/3.9.12/release-notes.html)

### Spring Boot 4.0
- [Spring Boot 4.0 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide)
- [Spring Boot 4.0 Release Notes](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Release-Notes)
- [Spring Boot 4.0.0 available now](https://spring.io/blog/2025/11/20/spring-boot-4-0-0-available-now/)

### Vue.js
- [Announcing Vue 3.5](https://blog.vuejs.org/posts/vue-3-5)
- [Vue.js Changelog](https://github.com/vuejs/core/blob/main/CHANGELOG.md)

### Element Plus
- [Element Plus Changelog](https://element-plus.org/en-US/guide/changelog)
- [Element Plus Releases](https://github.com/element-plus/element-plus/releases)

### PostgreSQL
- [PostgreSQL 18.1 Release Notes](https://www.postgresql.org/docs/current/release-18-1.html)
- [PostgreSQL 18 Release Notes](https://www.postgresql.org/docs/current/release-18.html)
- [PostgreSQL JDBC Driver](https://jdbc.postgresql.org/)

---

**Fin du document**
