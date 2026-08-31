# Plan de Migration Spring Boot 4 / Spring Security 7

> **Migration terminée (livrée en 1.1.5).** Ce document est conservé comme
> compte rendu de la démarche et référence des points de vigilance. L'état
> courant des versions se lit dans `pom.xml` et le `README.md` racine, pas
> ici : depuis, le socle a continué d'évoluer (Spring Boot **4.1.1**, Keycloak
> **26.7.x**, PostgreSQL **18.x** partout) au fil des PR Renovate.

Ce document détaille la migration de l'application RHDemo depuis Spring Boot
3.5.x vers Spring Boot 4.x.

## Versions concernées (au moment de la migration)

| Composant        | Version avant migration | Version cible | Résultat |
|------------------|------------------------|---------------|----------|
| Spring Boot      | 3.5.8                  | 4.0.x         | ✅ 4.0.2 (puis 4.1.x en continu) |
| Spring Security  | 6.5.x                 | 7.0.x         | ✅ 7.0.x  |
| Spring Framework | 6.2.x                 | 7.0.x         | ✅ 7.0.x  |
| Java             | 21                     | 25 (LTS)      | ✅ 25     |
| Jackson          | 2.x                   | 3.x           | ✅ 3.x    |
| JaCoCo           | 0.8.12                 | 0.8.14        | ✅ 0.8.14 |
| Mockito          | 5.17.0                 | 5.21.0        | ✅ 5.21.0 |
| Keycloak         | 26.4.2                 | 26.5.0        | ✅ (26.7.x aujourd'hui) |
| PostgreSQL       | 16.x                  | 18.1          | ✅ (18.x aujourd'hui)   |

## Prérequis (rappel de la démarche)

1. **Spring Boot 3.5.x** : passer par 3.5.x d'abord (fait ✓)
2. **Java 21 → 25** : réalisé dans la foulée
3. **Tests passants** : s'assurer que tous les tests passent avant migration

## Calendrier de support

- **Spring Boot 3.5** : Support gratuit jusqu'à juin 2026, payant jusqu'à juin 2032
- **Spring Boot 4.0** : GA depuis novembre 2025

---

## Analyse du code actuel

### 1. Dépréciations identifiées

#### Code source principal

| Fichier | Ligne | Pattern | Statut | Action |
|---------|-------|---------|--------|--------|
| `SecurityConfig.java` | - | Configuration lambda | ✅ OK | Aucune |
| `SecurityConfig.java` | 158-163 | `.csrf(csrf -> ...)` | ✅ OK | Style lambda correct |
| `SecurityConfig.java` | 175-185 | `.authorizeHttpRequests(auth -> ...)` | ✅ OK | Style lambda correct |
| `GrantedAuthoritiesKeyCloakMapper.java` | 36, 40 | `Class.isInstance()` | ⚠️ Style | Préférer `instanceof` |

#### Code de test

| Fichier | Pattern | Statut | Action |
|---------|---------|--------|--------|
| `EmployeControllerIT.java` | `.with(csrf())` | ✅ OK | MockMvc standard |
| `GlobalExceptionHandlerIT.java` | `.with(csrf())` | ✅ OK | MockMvc standard |

### 2. Dépendances à mettre à jour

| Dépendance | Version actuelle | Version cible | Risque | Notes |
|------------|-----------------|---------------|--------|-------|
| `springdoc-openapi-starter-webmvc-ui` | 2.8.14 | 3.0.x | 🔴 ÉLEVÉ | Jackson 3 requis |
| `json-path` (Jayway) | géré par Boot | - | 🟡 MOYEN | Utilise Jackson 2 |
| `postgresql` | géré par Boot | - | 🟢 FAIBLE | Compatible |
| `h2` | géré par Boot | - | 🟢 FAIBLE | Compatible |
| `micrometer-registry-prometheus` | géré par Boot | - | 🟢 FAIBLE | Compatible |

---

## Plan de migration détaillé

### Phase 1 : Préparation (avant migration)

#### 1.1 Mettre à jour les patterns obsolètes

**Fichier** : `GrantedAuthoritiesKeyCloakMapper.java`

```java
// AVANT (ligne 36-40)
if (OidcUserAuthority.class.isInstance(authority)) {
    final OidcUserAuthority oidcUserAuthority = (OidcUserAuthority) authority;
    // ...
} else if (OAuth2UserAuthority.class.isInstance(authority)) {
    final OAuth2UserAuthority oauth2UserAuthority = (OAuth2UserAuthority) authority;
    // ...
}

// APRÈS (pattern matching Java 21)
if (authority instanceof OidcUserAuthority oidcUserAuthority) {
    mappedAuthorities.addAll(extractAuthorities(oidcUserAuthority.getIdToken().getClaims()));
} else if (authority instanceof OAuth2UserAuthority oauth2UserAuthority) {
    final Map<String, Object> userAttributes = oauth2UserAuthority.getAttributes();
    mappedAuthorities.addAll(extractAuthorities(userAttributes));
}
```

#### 1.2 Vérifier les méthodes dépréciées Spring Security 6.5

Exécuter avec le flag de compilation pour warnings :

```bash
./mvnw clean compile -Xlint:deprecation
```

### Phase 2 : Migration du pom.xml

#### 2.1 Mettre à jour le parent

```xml
<!-- AVANT -->
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.5.8</version>
</parent>

<!-- APRÈS -->
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>4.0.1</version>
</parent>
```

#### 2.2 Mettre à jour SpringDoc OpenAPI

```xml
<!-- AVANT -->
<dependency>
    <groupId>org.springdoc</groupId>
    <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
    <version>2.8.14</version>
</dependency>

<!-- APRÈS -->
<dependency>
    <groupId>org.springdoc</groupId>
    <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
    <version>3.0.1</version>
</dependency>
```

#### 2.3 Ajouter les starters de test modularisés (Spring Boot 4)

Spring Boot 4 a **modularisé** ses auto-configurations. Les annotations de test (`@AutoConfigureMockMvc`, `@WithMockUser`, etc.) ne sont plus incluses dans les starters génériques. Il faut ajouter des starters de test dédiés :

```xml
<!-- AVANT (Spring Boot 3.x) : spring-boot-starter-test + spring-security-test suffisaient -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-test</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.springframework.security</groupId>
    <artifactId>spring-security-test</artifactId>
    <scope>test</scope>
</dependency>

<!-- APRÈS (Spring Boot 4.x) : starters modulaires requis -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-test</artifactId>
    <scope>test</scope>
</dependency>
<!-- MockMvc (@AutoConfigureMockMvc) nécessite un starter dédié -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-webmvc-test</artifactId>
    <scope>test</scope>
</dependency>
<!-- @WithMockUser nécessite un starter sécurité dédié -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-security-test</artifactId>
    <scope>test</scope>
</dependency>
```

**Symptome si manquant** :
- Sans `spring-boot-starter-webmvc-test` : `AutoConfigureMockMvc cannot be resolved`
- Sans `spring-boot-starter-security-test` : `@WithMockUser` ignoré, tous les tests retournent **401 Unauthorized**

**Import `AutoConfigureMockMvc` changé de package** :

```java
// AVANT (Spring Boot 3.x)
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;

// APRÈS (Spring Boot 4.x)
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
```

Fichiers impactés dans ce projet :
- `SecurityConfigIT.java`
- `EmployeControllerIT.java`
- `AccueilControllerIT.java`
- `GlobalExceptionHandlerIT.java`

Voir aussi : [Spring Boot 4 Modularization (Dan Vega)](https://www.danvega.dev/blog/spring-boot-4-modularization), [Spring Boot 4.0 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide)

#### 2.4 Gérer la coexistence Jackson 2/3

Spring Boot 4 inclut automatiquement Jackson 2 et 3. Si des problèmes surviennent avec json-path :

```yaml
# application.yml - forcer Jackson 2 temporairement
spring:
  jackson:
    preferred-version: jackson2
```

### Phase 3 : Adaptation du code Spring Security

#### 3.1 Vérifier les changements d'API

**Points de vigilance dans `SecurityConfig.java`** :

1. **CsrfTokenRequestHandler** : L'interface reste compatible, mais vérifier les méthodes

2. **frameOptions()** : Vérifier la nouvelle API
   ```java
   // AVANT (potentiellement changé)
   .frameOptions(frame -> frame.disable())

   // APRÈS (vérifier documentation 7.0)
   .frameOptions(HeadersConfigurer.FrameOptionsConfig::disable)
   ```

3. **headers()** : Vérifier les changements dans `HeadersConfigurer`

#### 3.2 Vérifier les annotations de sécurité

Les annotations `@PreAuthorize` restent supportées, mais vérifier :

```java
// Pas de changement attendu
@PreAuthorize("hasRole('consult')")
@PreAuthorize("hasRole('MAJ')")
```

### Phase 4 : Migration Jackson (impact majeur)

#### 4.1 Changements de packages

| Jackson 2 | Jackson 3 |
|-----------|-----------|
| `com.fasterxml.jackson.core:jackson-core` | `tools.jackson:jackson-core` |
| `com.fasterxml.jackson.core:jackson-databind` | `tools.jackson:jackson-databind` |
| `com.fasterxml.jackson.core:jackson-annotations` | `com.fasterxml.jackson.core:jackson-annotations` (inchangé) |

#### 4.2 Impact sur le code

Le projet n'utilise pas directement Jackson dans le code métier (pas d'imports `com.fasterxml.jackson`).

**Cependant**, les dépendances transitives peuvent être affectées :
- SpringDoc OpenAPI → utilise Jackson pour la sérialisation
- json-path → utilise Jackson comme provider JSON

### Phase 5 : Migration vers OpenJDK 25

#### 5.1 Pourquoi OpenJDK 25 ?

| Aspect | Détail |
|--------|--------|
| **Type de release** | LTS (Long Term Support) |
| **Date de sortie** | Septembre 2025 |
| **Support commercial** | Jusqu'en 2033 (Oracle Extended Support) |
| **Compatibilité Spring Boot 4** | Supporté nativement |

**Avantages clés** :

- Dernière version LTS avec support étendu
- Nouvelles fonctionnalités du langage stabilisées
- Améliorations significatives de performance (GC, JIT)
- Meilleure intégration avec les conteneurs (Project Leyden)

#### 5.2 Nouvelles fonctionnalités Java 22-25 à exploiter

##### Pattern Matching amélioré (Java 21+)

```java
// AVANT - switch classique
String result;
switch (status) {
    case "ACTIVE":
        result = "En cours";
        break;
    case "INACTIVE":
        result = "Inactif";
        break;
    default:
        result = "Inconnu";
}

// APRÈS - switch expression avec pattern matching
String result = switch (status) {
    case "ACTIVE" -> "En cours";
    case "INACTIVE" -> "Inactif";
    default -> "Inconnu";
};
```

##### Record Patterns (Java 21+)

```java
// Déstructuration de records dans instanceof
if (response instanceof ApiResponse(var data, var status) && status == 200) {
    processData(data);
}
```

##### String Templates (Java 25 - stabilisé)

```java
// AVANT
String message = "Employé " + employe.getNom() + " créé avec ID " + employe.getId();

// APRÈS - String Templates (STR processor)
String message = STR."Employé \{employe.getNom()} créé avec ID \{employe.getId()}";
```

##### Scoped Values (Java 25 - stabilisé)

```java
// Alternative aux ThreadLocal pour les données contextuelles
private static final ScopedValue<User> CURRENT_USER = ScopedValue.newInstance();

// Utilisation dans un contrôleur
ScopedValue.where(CURRENT_USER, authenticatedUser)
    .run(() -> employeService.processRequest());
```

##### Structured Concurrency (Java 25 - stabilisé)

```java
// Gestion propre des tâches concurrentes
try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
    Subtask<Employe> employeTask = scope.fork(() -> employeService.findById(id));
    Subtask<List<String>> rolesTask = scope.fork(() -> keycloakService.getRoles(id));

    scope.join().throwIfFailed();

    return new EmployeWithRoles(employeTask.get(), rolesTask.get());
}
```

##### Virtual Threads (Java 21+ - production ready)

```java
// Configuration Spring Boot pour utiliser les Virtual Threads
spring:
  threads:
    virtual:
      enabled: true
```

#### 5.3 Modifications du pom.xml

```xml
<!-- AVANT -->
<properties>
    <java.version>21</java.version>
</properties>

<!-- APRÈS -->
<properties>
    <java.version>25</java.version>
    <!-- Activer les fonctionnalités preview si nécessaire -->
    <!-- <maven.compiler.enablePreview>true</maven.compiler.enablePreview> -->
</properties>
```

#### 5.4 Mise à jour du Dockerfile

```dockerfile
# AVANT
FROM eclipse-temurin:21-jre-alpine

# APRÈS
FROM eclipse-temurin:25-jre-alpine

# Note: Vérifier la disponibilité de l'image Alpine pour Java 25
# Alternative si Alpine non disponible :
# FROM eclipse-temurin:25-jre-noble
```

#### 5.5 Configuration Virtual Threads (recommandé)

Dans `application.yml` :

```yaml
spring:
  threads:
    virtual:
      enabled: true

# Configuration Tomcat pour Virtual Threads
server:
  tomcat:
    threads:
      max: 200
      min-spare: 10
```

Avantages des Virtual Threads :

- Meilleure scalabilité pour les I/O bound (appels BDD, Keycloak)
- Réduction de la consommation mémoire
- Pas de modification du code applicatif requis

#### 5.6 Mise à jour de l'image Jenkins

Le pipeline CI utilise une image Docker avec Maven. Mettre à jour :

```dockerfile
# jenkins-docker/Dockerfile
FROM eclipse-temurin:25-jdk AS builder
# ... reste du Dockerfile
```

#### 5.7 Compatibilité des dépendances avec Java 25

| Dépendance | Compatible Java 25 | Version minimum | Notes |
|------------|-------------------|-----------------|-------|
| Spring Boot 4.0+ | ✅ Oui | 4.0.0 | Support natif |
| Spring Security 7.0 | ✅ Oui | 7.0.0 | Support natif |
| Hibernate 7.0 | ✅ Oui | 7.0.0 | Inclus dans Boot 4 |
| Jackson 3.x | ✅ Oui | 3.0.0 | - |
| **JaCoCo** | ✅ Oui | **0.8.14** | 0.8.12 = `Unsupported class file major version 68` |
| **Mockito** | ✅ Oui | **5.19.0** | Requiert ByteBuddy 1.17.5+ |
| **ByteBuddy** | ✅ Oui | **1.17.5** | Spring Boot 4.0.2 gere 1.17.8 |
| SpringDoc OpenAPI 3.x | ✅ Oui | 3.0.1 | Compatible Spring Boot 4 / Jackson 3 |
| Keycloak Client | ✅ Oui | - | Dependance Spring Security |
| PostgreSQL JDBC | ✅ Oui | - | - |
| H2 Database | ✅ Oui | - | - |
| Micrometer | ✅ Oui | - | - |
| JUnit 5 | ✅ Oui | - | - |

#### 5.8 JaCoCo et Mockito : incompatibilite avec Java 25 (probleme rencontre)

##### Symptome

Lors du `mvn install` avec Java 25 et JaCoCo 0.8.12, l'erreur suivante apparait :

```text
java.lang.instrument.IllegalClassFormatException:
  Error while instrumenting org/springframework/...
Caused by: java.lang.IllegalArgumentException:
  Unsupported class file major version 68
```

Le meme type d'erreur peut apparaitre avec Mockito/ByteBuddy :

```text
java.lang.IllegalArgumentException:
  Java 25 (69) is not supported by the current version of Byte Buddy
  which officially supports Java 24 (68)
```

##### Cause

- **JaCoCo 0.8.12** utilise ASM 9.7 qui ne supporte que jusqu'a Java 22 (class file major version 66)
- **Mockito 5.17.0** inclut ByteBuddy < 1.17.5 qui ne supporte que jusqu'a Java 24 (class file major version 68)
- Java 25 produit des class files en version 69

##### Solution appliquee

Dans `pom.xml` :

```xml
<properties>
    <java.version>25</java.version>
    <!-- Override Mockito pour Java 25 (ByteBuddy 1.17.8+) -->
    <mockito.version>5.21.0</mockito.version>
</properties>

<!-- Plugin JaCoCo -->
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>0.8.14</version>  <!-- AVANT: 0.8.12 -->
</plugin>
```

| Outil | Version avant | Version apres | Raison |
|-------|--------------|---------------|--------|
| JaCoCo | 0.8.12 | **0.8.14** | Support officiel Java 25 (ASM 9.8+) |
| Mockito | 5.17.0 | **5.21.0** | Inclut ByteBuddy 1.17.8 (Java 25) |
| ByteBuddy | < 1.17.5 | **1.17.8** | Tire par Mockito 5.21.0 |

> **Note** : Spring Boot 4.0.2 gere Mockito 5.20.0 et ByteBuddy 1.17.8 nativement.
> L'override a 5.21.0 est volontaire pour beneficier des derniers correctifs.
> La propriete `${mockito.version}` est aussi utilisee dans l'argLine de Surefire/Failsafe
> pour le `-javaagent` Mockito.

#### 5.8 Points d'attention

1. **Bytecode verification** : Java 25 est plus strict sur la validation du bytecode. S'assurer que toutes les dépendances sont compilées avec une version compatible.

2. **Reflection** : Les accès réflexifs sont davantage restreints. Vérifier les warnings au démarrage :

   ```text
   WARNING: An illegal reflective access operation has occurred
   ```

3. **Security Manager** : Supprimé définitivement en Java 25. Non utilisé dans le projet (OK).

4. **Garbage Collector** : G1GC reste le défaut, mais ZGC et Shenandoah sont maintenant production-ready pour les applications à faible latence.

### Phase 6 : Migration Keycloak 26.4.2 → 26.5.0

#### 6.1 Changements majeurs Keycloak 26.5.0

| Catégorie            | Changement                             | Impact                          |
|----------------------|----------------------------------------|---------------------------------|
| **Performance**      | Amélioration du cache des sessions     | Aucun (transparent)             |
| **Sécurité**         | Renforcement des headers CSP par défaut| Vérifier compatibilité frontend |
| **OIDC**             | Support amélioré de PKCE               | Aucun (déjà utilisé)            |
| **Admin API**        | Nouvelles métriques Prometheus         | Optionnel                       |
| **Base de données**  | Support PostgreSQL 17+ natif           | Compatible avec migration PG 18 |

#### 6.2 Mise à jour de l'image Docker

```yaml
# docker-compose.yml / Helm values
# AVANT
image: quay.io/keycloak/keycloak:26.4.2

# APRÈS
image: quay.io/keycloak/keycloak:26.5.0
```

#### 6.3 Vérifications de compatibilité

##### Configuration OAuth2 (application.yml)

La configuration OAuth2 Spring Security reste compatible :

```yaml
spring:
  security:
    oauth2:
      client:
        provider:
          keycloak:
            issuer-uri: ${KEYCLOAK_ISSUER_URI}
            # Pas de changement requis
```

##### Realm Export/Import

Si vous avez des exports de realm, les migrer :

```bash
# Export du realm actuel (avant migration)
kubectl exec -n rhdemo-stagingkub deploy/keycloak -- \
    /opt/keycloak/bin/kc.sh export --realm rhdemo --file /tmp/realm-export.json

# Copier l'export
kubectl cp rhdemo-stagingkub/keycloak-xxx:/tmp/realm-export.json ./realm-backup.json
```

#### 6.4 Points d'attention Keycloak

1. **Sessions existantes** : Les sessions utilisateur seront invalidées après la mise à jour. Prévoir une fenêtre de maintenance.

2. **Cache distribué** : Si Infinispan externe est utilisé, vérifier la compatibilité des versions.

3. **Thèmes personnalisés** : Vérifier la compatibilité des thèmes custom (non utilisé dans ce projet).

4. **Extensions/SPI** : Le `GrantedAuthoritiesKeyCloakMapper` utilise uniquement les claims OIDC standard, pas d'impact.

#### 6.5 Procédure de mise à jour Keycloak

```bash
# 1. Backup de la base PostgreSQL Keycloak
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
    pg_dump -U keycloak keycloak > keycloak-backup.sql

# 2. Mettre à jour l'image dans Helm values
# helm/rhdemo/values.yaml : keycloak.image.tag = "26.5.0"

# 3. Appliquer le déploiement
helm upgrade rhdemo ./helm/rhdemo -n rhdemo-stagingkub

# 4. Vérifier les logs de migration
kubectl logs -n rhdemo-stagingkub deploy/keycloak -f

# 5. Tester l'authentification
curl -k https://keycloak-stagingkub.intra.leuwen-lc.fr/realms/rhdemo/.well-known/openid_configuration
```

### Phase 7 : Migration PostgreSQL 16 → 18.1

#### 7.1 Changements majeurs PostgreSQL 17 et 18

| Version   | Fonctionnalité                 | Impact projet                    |
|-----------|--------------------------------|----------------------------------|
| **PG 17** | Amélioration VACUUM            | Performance (transparent)        |
| **PG 17** | JSON_TABLE()                   | Nouvelles possibilités requêtes  |
| **PG 17** | Incremental backup             | Backups plus rapides             |
| **PG 18** | Virtual generated columns      | Nouvelles possibilités schéma    |
| **PG 18** | Async I/O (io_uring)           | Performance Linux (transparent)  |
| **PG 18** | pg_overexplain                 | Debug requêtes amélioré          |
| **PG 18** | Logical replication améliorée  | Facilite les migrations          |

#### 7.2 Compatibilité avec Spring Data JPA / Hibernate

| Composant       | Version requise | Notes                     |
|-----------------|-----------------|---------------------------|
| Hibernate 7.0   | ✅ Compatible   | Inclus dans Spring Boot 4 |
| PostgreSQL JDBC | 42.7+           | Géré par Spring Boot      |
| HikariCP        | 6.x             | Géré par Spring Boot      |

Le dialecte Hibernate est automatiquement détecté. Aucun changement de configuration requis :

```yaml
# application.yml - pas de changement
spring:
  jpa:
    database-platform: org.hibernate.dialect.PostgreSQLDialect
    # Hibernate 7 détecte automatiquement PG 18
```

#### 7.3 Stratégie de migration PostgreSQL

##### Option A : pg_upgrade (temps d'arrêt minimal)

```bash
# Non applicable sur KinD avec StatefulSets
# Recommandé pour les environnements avec accès direct aux fichiers
```

##### Option B : Dump/Restore (recommandé pour KinD)

```bash
# 1. Créer un dump de chaque base
kubectl exec -n rhdemo-stagingkub postgresql-rhdemo-0 -- \
    pg_dump -U rhdemo_user rhdemo_db > rhdemo-backup.sql

kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
    pg_dump -U keycloak keycloak > keycloak-backup.sql

# 2. Mettre à jour l'image PostgreSQL dans Helm values
# helm/rhdemo/values.yaml : postgresql.image.tag = "18.1-alpine"

# 3. Supprimer les StatefulSets (données perdues !)
kubectl delete statefulset -n rhdemo-stagingkub postgresql-rhdemo postgresql-keycloak

# 4. Supprimer les PVC (si stockage extraMounts)
kubectl delete pvc -n rhdemo-stagingkub data-postgresql-rhdemo-0 data-postgresql-keycloak-0

# 5. Redéployer
helm upgrade rhdemo ./helm/rhdemo -n rhdemo-stagingkub

# 6. Restaurer les dumps
kubectl cp rhdemo-backup.sql rhdemo-stagingkub/postgresql-rhdemo-0:/tmp/
kubectl exec -n rhdemo-stagingkub postgresql-rhdemo-0 -- \
    psql -U rhdemo_user -d rhdemo_db -f /tmp/rhdemo-backup.sql
```

##### Option C : Logical Replication (zero-downtime)

Pour les environnements de production, PostgreSQL 18 améliore la réplication logique :

```sql
-- Sur PG 16 (source)
CREATE PUBLICATION rhdemo_pub FOR ALL TABLES;

-- Sur PG 18 (destination)
CREATE SUBSCRIPTION rhdemo_sub
    CONNECTION 'host=pg16-host dbname=rhdemo_db'
    PUBLICATION rhdemo_pub;
```

#### 7.4 Mise à jour du schéma (pgschema.sql)

Le schéma actuel est compatible PostgreSQL 18. Vérifications :

```sql
-- Vérifier les types de données dépréciés (aucun dans ce projet)
-- money, abstime, reltime sont dépréciés mais non utilisés

-- Le schéma utilise des types standards compatibles :
-- SERIAL, VARCHAR, TEXT, INTEGER, TIMESTAMP
```

#### 7.5 Mise à jour des images Docker

```dockerfile
# Dockerfile PostgreSQL (si personnalisé)
# AVANT
FROM postgres:16-alpine

# APRÈS
FROM postgres:18-alpine
```

Pour les Helm values :

```yaml
# helm/rhdemo/values.yaml
postgresql:
  rhdemo:
    image:
      repository: postgres
      tag: "18-alpine"  # AVANT: "16-alpine"
  keycloak:
    image:
      repository: postgres
      tag: "18-alpine"  # AVANT: "16-alpine"
```

#### 7.6 Changement critique : montage volume Docker (probleme rencontre)

##### Symptome PG 18 volume

Au demarrage d'un conteneur PostgreSQL 18, l'erreur suivante apparait :

```text
Error: in 18+, these Docker images are configured to store database data
in a format which is compatible with 'pg_ctlcluster'

To enable this, the 'PGDATA' must be set to a path like
'/var/lib/postgresql/XX/YY' (where XX is the major version and YY is the
cluster name), and the mount point for any volumes MUST be at or above
'/var/lib/postgresql' (NOT '/var/lib/postgresql/data')
```

##### Cause du changement

Les images Docker PostgreSQL 18+ ont change la structure du repertoire de donnees :

| Version | Structure donnees | Point de montage volume |
| --- | --- | --- |
| PG 16 | `/var/lib/postgresql/data/` | `/var/lib/postgresql/data` |
| PG 18+ | `/var/lib/postgresql/18/main/` (format `pg_ctlcluster`) | `/var/lib/postgresql` |

PG 18 gere automatiquement ses sous-repertoires versionnes (`18/main/`). Monter un volume directement sur `/var/lib/postgresql/data` empeche cette gestion et fait echouer l'initialisation.

La variable `PGDATA` n'est plus necessaire non plus : PG 18 determine automatiquement le chemin de donnees dans le format `pg_ctlcluster`.

##### Correction appliquee

**Docker Compose (dev et ephemere)** :

```yaml
# AVANT (PG 16)
volumes:
  - db-data:/var/lib/postgresql/data

# APRES (PG 18+)
volumes:
  # PostgreSQL 18+ : monter sur /var/lib/postgresql (et non /data)
  # PG 18 gere ses propres sous-repertoires versionnes (18/main/)
  - db-data:/var/lib/postgresql
```

**Kubernetes StatefulSets (stagingkub)** :

```yaml
# AVANT (PG 16)
env:
- name: PGDATA
  value: /var/lib/postgresql/data/pgdata
volumeMounts:
- name: postgresql-data
  mountPath: /var/lib/postgresql/data

# APRES (PG 18+)
# Pas de PGDATA, PG 18 gere ses sous-repertoires versionnes (18/main/)
volumeMounts:
- name: postgresql-data
  mountPath: /var/lib/postgresql
```

##### Fichiers modifies pour PG 18

| Fichier | Modification |
| --- | --- |
| `infra/dev/docker-compose.yml` | Volume monte sur `/var/lib/postgresql` |
| `infra/ephemere/docker-compose.yml` | Idem pour rhdemo-db et keycloak-db |
| `infra/stagingkub/helm/rhdemo/templates/postgresql-rhdemo-statefulset.yaml` | `mountPath` + suppression `PGDATA` |
| `infra/stagingkub/helm/rhdemo/templates/postgresql-keycloak-statefulset.yaml` | Idem |

##### Suppression des anciens volumes PG 16

Les anciens volumes contenant des donnees PG 16 doivent etre supprimes avant le premier demarrage avec PG 18 (formats incompatibles) :

```bash
# Dev
docker volume rm rhdemo-dev-db-data

# Ephemere
docker volume rm rhdemo-ephemere-db-data keycloak-ephemere-db-data

# Stagingkub (supprimer les PVC Kubernetes)
kubectl delete pvc -n rhdemo-stagingkub \
    postgresql-data-postgresql-rhdemo-0 \
    postgresql-data-postgresql-keycloak-0
```

> **Note** : Les scripts de migration (`migrate-postgresql-rhdemo.sh`, `migrate-postgresql-keycloak.sh`)
> ont ete recrees avec une strategie **dump/restore** (remplacement des anciens scripts a base de replication logique).
> Ils gerent automatiquement le backup PG 16, le nettoyage des PVC/PV, le redeploiement Helm en PG 18 et la restauration.
> Usage : `./migrate-postgresql-rhdemo.sh full` ou phase par phase (`backup`, `prepare`, `deploy`, `restore`, `status`).

#### 7.7 Configuration optimisée PostgreSQL 18

Nouvelles options de configuration recommandées :

```yaml
# ConfigMap postgresql
postgresql.conf: |
  # Nouvelles options PG 18
  # Async I/O (Linux uniquement, améliore les performances)
  io_method = io_uring

  # Amélioration du parallélisme
  max_parallel_workers_per_gather = 4

  # Optimisation mémoire (ajuster selon ressources)
  shared_buffers = 256MB
  effective_cache_size = 768MB

  # Logging amélioré
  log_statement = 'ddl'
  log_min_duration_statement = 1000
```

#### 7.7 Tests de régression PostgreSQL

```bash
# Vérifier que les requêtes critiques fonctionnent
kubectl exec -n rhdemo-stagingkub postgresql-rhdemo-0 -- \
    psql -U rhdemo_user -d rhdemo_db -c "SELECT COUNT(*) FROM employes;"

# Vérifier les performances avec EXPLAIN ANALYZE
kubectl exec -n rhdemo-stagingkub postgresql-rhdemo-0 -- \
    psql -U rhdemo_user -d rhdemo_db -c \
    "EXPLAIN ANALYZE SELECT * FROM employes WHERE nom LIKE 'D%';"
```

### Phase 8 : Tests et validation

#### 8.1 Ordre d'exécution des tests

```bash
# 1. Compilation
./mvnw clean compile

# 2. Tests unitaires
./mvnw test

# 3. Tests d'intégration
./mvnw verify

# 4. Scan OWASP (vérifier nouvelles CVE)
./mvnw org.owasp:dependency-check-maven:check -DnvdApiKey=$NVD_API_KEY

# 5. Build image Docker
./mvnw spring-boot:build-image
```

#### 8.2 Points de test manuels

1. **Login OAuth2** : Vérifier le flux complet avec Keycloak
2. **Logout** : Vérifier la redirection vers Keycloak
3. **CSRF** : Vérifier que les mutations POST/PUT/DELETE fonctionnent
4. **API REST** : Tester tous les endpoints `/api/*`
5. **Swagger UI** : Vérifier l'accès à `/api-docs/swagger-ui`

---

## Risques et mitigations

### Risque 1 : Incompatibilité SpringDoc OpenAPI avec Jackson 3

**Probabilité** : Élevée
**Impact** : Swagger UI non fonctionnel

**Mitigation** :
1. Surveiller les issues GitHub springdoc-openapi
2. Tester avec la version 3.0.x de SpringDoc
3. Plan B : forcer Jackson 2 via `spring.jackson.preferred-version=jackson2`

### Risque 2 : Changements d'API Spring Security non documentés

**Probabilité** : Moyenne
**Impact** : Erreurs de compilation

**Mitigation** :
1. Lire le guide de migration officiel avant chaque étape
2. Tester sur une branche dédiée
3. Conserver la possibilité de rollback vers 3.5.x

### Risque 3 : Incompatibilité avec Keycloak

**Probabilité** : Faible
**Impact** : Authentification cassée

**Mitigation** :
1. Les endpoints OIDC standard ne changent pas
2. Tester le flux complet sur environnement ephemere avant stagingkub

---

## Checklist de migration

### Avant migration

- [ ] Tous les tests passent sur Spring Boot 3.5.8
- [ ] Backup de la branche actuelle
- [ ] Créer branche `feature/spring-boot-4-migration`
- [ ] Lire le guide de migration officiel Spring Boot 4.0
- [ ] Lire le guide de migration Spring Security 7.0

### Pendant migration Spring Boot 4

- [x] Mettre à jour `pom.xml` (parent 4.0.2 + dépendances)
- [x] Corriger les erreurs de compilation
- [x] Adapter `GrantedAuthoritiesKeyCloakMapper.java` (instanceof pattern)
- [x] Vérifier `SecurityConfig.java` pour changements d'API
- [x] Mettre à jour SpringDoc OpenAPI vers 3.0.1
- [x] Résoudre les conflits Jackson 2/3 si nécessaire
- [x] Ajouter `spring-boot-starter-webmvc-test` (modularisation MockMvc)
- [x] Ajouter `spring-boot-starter-security-test` (modularisation @WithMockUser)
- [x] Migrer import `AutoConfigureMockMvc` vers nouveau package (4 fichiers IT)

### Migration OpenJDK 25

- [x] Mettre à jour `java.version` dans `pom.xml` (21 → 25)
- [x] Mettre à jour le Dockerfile (`eclipse-temurin:25-jre-alpine`)
- [x] Mettre à jour l'image Jenkins agent (`eclipse-temurin:25-jdk`)
- [x] Activer Virtual Threads dans `application.yml`
- [ ] Vérifier les warnings de reflection au démarrage
- [x] Tester la compatibilité de toutes les dépendances
- [x] Mettre à jour JaCoCo 0.8.12 → 0.8.14 (support Java 25)
- [x] Mettre à jour Mockito 5.17.0 → 5.21.0 (ByteBuddy 1.17.8 pour Java 25)
- [ ] Moderniser le code avec les nouvelles fonctionnalités Java 25 (optionnel)

### Migration Keycloak 26.5.0

- [ ] Backup de la base PostgreSQL Keycloak
- [ ] Export du realm rhdemo (optionnel)
- [ ] Mettre à jour l'image Keycloak dans Helm values (`26.5.0`)
- [ ] Appliquer le déploiement Helm
- [ ] Vérifier les logs de migration Keycloak
- [ ] Tester l'endpoint OIDC well-known
- [ ] Tester le flux login/logout complet

### Migration PostgreSQL 18.1

- [ ] Backup complet des bases rhdemo et keycloak (pg_dump)
- [ ] Mettre à jour l'image PostgreSQL dans Helm values (`18-alpine`)
- [x] Corriger montage volume Docker : `/var/lib/postgresql` au lieu de `/data` (dev, ephemere, stagingkub)
- [x] Supprimer variable `PGDATA` des StatefulSets (PG 18 gere `18/main/` automatiquement)
- [ ] Supprimer les anciens volumes/PVC (formats PG 16 incompatibles)
- [ ] Redéployer avec Helm
- [ ] Restaurer les dumps (psql)
- [ ] Vérifier l'intégrité des données (COUNT, requêtes test)
- [ ] Appliquer les optimisations PG 18 (io_uring, etc.) - optionnel

### Après migration

- [x] Tests unitaires passent (43/43, 0 failures)
- [x] Tests d'intégration passent (43/43, 0 failures)
- [ ] Scan OWASP sans nouvelles CVE critiques
- [ ] Test manuel login/logout Keycloak
- [ ] Test manuel API REST + Swagger UI
- [ ] Déploiement sur environnement ephemere
- [ ] Tests Selenium passent
- [ ] Déploiement sur stagingkub
- [ ] Mise à jour de la documentation (CLAUDE.md, README.md)

---

## Références

### Documentation officielle

- [Spring Boot 4.0 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide)
- [Spring Boot 4.0 Release Notes](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Release-Notes)
- [Migrating to Spring Security 7.0](https://docs.spring.io/spring-security/reference/migration/index.html)
- [What's New in Spring Security 7.0](https://docs.spring.io/spring-security/reference/whats-new.html)

### Articles et guides

- [Spring Boot 4 & Spring Framework 7 – What's New (Baeldung)](https://www.baeldung.com/spring-boot-4-spring-framework-7)
- [Jackson 3 in Spring Boot 4 (Dan Vega)](https://www.danvega.dev/blog/2025/11/10/jackson-3-spring-boot-4)
- [Introduction to Jackson 3 in Spring 7 and Spring Boot 4 (ITNEXT)](https://itnext.io/an-introduction-to-jackson-3-in-spring-7-and-spring-boot-4-cba114aa36b1)

### Issues à surveiller

- [SpringDoc OpenAPI - Spring Boot 4 support](https://github.com/springdoc/springdoc-openapi/issues/3095)
- [SpringDoc OpenAPI - Jackson 3 issues](https://github.com/springdoc/springdoc-openapi/issues/3175)

### Java 25 / OpenJDK

- [JDK 25 Release Schedule](https://openjdk.org/projects/jdk/25/)
- [Virtual Threads - JEP 444](https://openjdk.org/jeps/444)
- [String Templates - JEP 465](https://openjdk.org/jeps/465)
- [Structured Concurrency - JEP 480](https://openjdk.org/jeps/480)
- [Scoped Values - JEP 481](https://openjdk.org/jeps/481)
- [Eclipse Temurin Releases](https://adoptium.net/temurin/releases/)

### Keycloak

- [Keycloak Release Notes](https://www.keycloak.org/docs/latest/release_notes/)
- [Keycloak Upgrading Guide](https://www.keycloak.org/docs/latest/upgrading/)
- [Keycloak Docker Images](https://quay.io/repository/keycloak/keycloak)
- [Keycloak GitHub Releases](https://github.com/keycloak/keycloak/releases)

### PostgreSQL

- [PostgreSQL 17 Release Notes](https://www.postgresql.org/docs/17/release-17.html)
- [PostgreSQL 18 Release Notes](https://www.postgresql.org/docs/18/release-18.html)
- [PostgreSQL Upgrade Guide](https://www.postgresql.org/docs/current/upgrading.html)
- [pg_upgrade Documentation](https://www.postgresql.org/docs/current/pgupgrade.html)
- [Logical Replication](https://www.postgresql.org/docs/current/logical-replication.html)

---

## Historique des modifications

| Date       | Version | Auteur      | Changements                                        |
|------------|---------|-------------|----------------------------------------------------|
| 2026-02-03 | 1.0     | Claude Code | Création initiale du document                      |
| 2026-02-08 | 1.1     | Claude Code | Ajout section migration OpenJDK 25                 |
| 2026-02-08 | 1.2     | Claude Code | Ajout sections Keycloak 26.5.0 et PostgreSQL 18.1  |
| 2026-02-08 | 1.3     | Claude Code | Section 2.3 : starters test modularises (MockMvc, @WithMockUser) |
| 2026-02-08 | 1.4     | Claude Code | Section 5.8 : incompatibilite JaCoCo/Mockito Java 25 et corrections |
| 2026-02-08 | 1.5     | Claude Code | Mise a jour checklist et tableau versions (etat actuel migration) |
| 2026-02-08 | 1.6     | Claude Code | Section 7.6 : montage volume Docker PG 18 (pg_ctlcluster)                 |
