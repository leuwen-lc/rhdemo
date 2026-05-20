# Tests de Couverture - Spring Security

## Vue d'ensemble

Ce document décrit la stratégie de tests pour les composants Spring Security de l'application rhDemo, avec pour objectif d'atteindre **50% de couverture de code** sur le périmètre mesuré.

## Composants testés

### 1. `GrantedAuthoritiesKeyCloakMapper` (Mapper des rôles)

**Fichier source:** `src/main/java/fr/leuwen/rhdemoAPI/springconfig/GrantedAuthoritiesKeyCloakMapper.java`

**Fichier de test:** `src/test/java/fr/leuwen/rhdemoAPI/springconfig/GrantedAuthoritiesKeyCloakMapperTest.java`

La classe utilise l'injection par constructeur (`@Value` en paramètre de constructeur), ce qui permet d'instancier directement dans le test sans `ReflectionTestUtils.setField` :

```java
mapper = new GrantedAuthoritiesKeyCloakMapper(CLIENT_ID);
```

#### Couverture fonctionnelle

| Fonctionnalité | Tests | Couverture |
|----------------|-------|------------|
| Extraction de rôles depuis OIDC ID Token | ✅ | 100% |
| Extraction de rôles depuis OAuth2 User Attributes | ✅ | 100% |
| Filtrage des rôles (seuls `ROLE_*` conservés) | ✅ | 100% |
| Gestion des claims manquants | ✅ | 100% |
| Gestion des rôles null/vides | ✅ | 100% |
| Combinaison de multiples authorities | ✅ | 100% |
| Gestion des authorities inconnues | ✅ | 100% |

#### Tests détaillés

1. **`testMapAuthorities_WithOidcUserAuthority_ShouldExtractRoles`**
   - Vérifie l'extraction correcte des rôles depuis un token OIDC valide
   - Cas nominal avec `ROLE_admin` et `ROLE_MAJ`

2. **`testMapAuthorities_WithOAuth2UserAuthority_ShouldExtractRoles`**
   - Vérifie l'extraction depuis OAuth2UserAuthority
   - Cas nominal avec `ROLE_consult` et `ROLE_MAJ`

3. **`testMapAuthorities_ShouldFilterNonRoleAuthorities`**
   - Vérifie que seuls les rôles commençant par `ROLE_` sont conservés
   - Filtre `offline_access`, `uma_authorization`, `profile`

4. **`testMapAuthorities_WithMissingResourceAccess_ShouldThrowException`**
   - Vérifie qu'une exception est levée si `resource_access` est manquant
   - Test de robustesse pour tokens malformés

5. **`testMapAuthorities_WithMissingClientId_ShouldReturnEmptyList`**
   - Vérifie le comportement quand le client ID n'est pas trouvé
   - Retourne une liste vide au lieu de crasher

6. **`testMapAuthorities_WithNullRoles_ShouldReturnEmptyList`**
   - Vérifie le comportement quand `roles` est `null`

7. **`testMapAuthorities_WithEmptyRolesList_ShouldReturnEmptyList`**
   - Vérifie le comportement avec une liste de rôles vide

8. **`testMapAuthorities_WithMultipleAuthorities_ShouldCombineRoles`**
   - Vérifie la combinaison de rôles depuis OIDC + OAuth2
   - Teste le Set (pas de doublons)

9. **`testMapAuthorities_WithUnknownAuthorityType_ShouldIgnore`**
   - Vérifie que les authorities non-OIDC/OAuth2 sont ignorées

10. **`testMapAuthorities_WithEmptyAuthorities_ShouldReturnEmptyList`**
    - Vérifie le comportement avec une collection vide

---

### 2. `CspPolicyBuilder` (Génération dynamique de la CSP)

**Fichier source:** `src/main/java/fr/leuwen/rhdemoAPI/springconfig/CspPolicyBuilder.java`

**Fichier de test:** `src/test/java/fr/leuwen/rhdemoAPI/springconfig/CspPolicyBuilderTest.java`

Classe extraite de `SecurityConfig` pour rendre la logique CSP testable sans réflexion. Elle est injectée par constructeur dans `SecurityConfig` et `TestSecurityConfig`, ce qui garantit que les tests valident la **même implémentation** que la production (contrairement à l'ancienne approche où `TestSecurityConfig` dupliquait `buildCspDirectives` en divergeant sur certaines directives, ex. `frame-ancestors`).

```java
// Instanciation directe dans les tests (pas de contexte Spring)
CspPolicyBuilder builder = new CspPolicyBuilder(keycloakAuthUri, cookieSecureFlag);
```

#### Couverture fonctionnelle

| Fonctionnalité | Tests | Couverture |
|----------------|-------|------------|
| Extraction URL Keycloak (ports standard/non-standard) | ✅ | 100% |
| Extraction URL Keycloak (URI null/vide/invalide) | ✅ | 100% |
| Extraction URL Keycloak (scheme manquant / URI tronquée) | ✅ | 100% |
| Génération CSP avec Keycloak configuré | ✅ | 100% |
| Génération CSP sans Keycloak | ✅ | 100% |
| Présence de toutes les directives requises | ✅ | 100% |
| Absence de directives `unsafe-*` | ✅ | 100% |
| Absence de double point-virgule | ✅ | 100% |
| Création repository CSRF (`cookieSecureFlag=false`) | ✅ | 100% |
| Création repository CSRF (`cookieSecureFlag=true`) | ✅ | 100% |

#### Tests détaillés

**Extraction URL Keycloak (`extractKeycloakBaseUrl`) :**

1. **`extractKeycloakBaseUrl_WithVariousPorts`** — `@ParameterizedTest` (4 cas)
   - HTTPS port standard, HTTP localhost, port 80 omis, port 443 omis

2. **`extractKeycloakBaseUrl_WithInvalidUris`** — `@ParameterizedTest` (3 cas)
   - `null`, chaîne vide, URI sans scheme (`invalid-uri`)

3. **`extractKeycloakBaseUrl_WithMissingScheme`**
   - URI de type `//keycloak.local/realms/...` → chaîne vide

4. **`extractKeycloakBaseUrl_WithOnlyScheme`**
   - URI tronquée `https:` → chaîne vide

5. **`extractKeycloakBaseUrl_WithNonStandardPort`**
   - Port 8443 conservé dans l'URL résultante

**Génération CSP (`buildCspDirectives`) :**

6. **`buildCspDirectives_WithKeycloakUrl`**
   - `connect-src` et `form-action` incluent l'origine Keycloak

7. **`buildCspDirectives_WithoutKeycloakUrl`**
   - `connect-src` et `form-action` limités à `'self'`, pas de mention Keycloak

8. **`buildCspDirectives_ContainsAllRequiredDirectives`**
   - Présence de : `default-src`, `script-src`, `style-src`, `img-src`, `font-src`, `connect-src`, `frame-ancestors`, `form-action`, `object-src`, `base-uri`, `media-src`, `manifest-src`, `worker-src`

9. **`buildCspDirectives_ShouldNotContainUnsafeDirectives`**
   - Absence de `unsafe-inline`, `unsafe-eval`, `upgrade-insecure-requests`

10. **`buildCspDirectives_ShouldNotHaveDoubleSemicolons`**
    - Validation syntaxique : pas de `;;`

**Repository CSRF (`createCsrfTokenRepository`) :**

11. **`createCsrfTokenRepository_WithSecureFlagFalse`**
    - Repository non null avec `cookieSecureFlag=false`

12. **`createCsrfTokenRepository_WithSecureFlagTrue`**
    - Repository non null avec `cookieSecureFlag=true`

---

### 3. `SecurityConfig` (Configuration de sécurité — autorisation)

**Fichier source:** `src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java`

**Fichier de test:** `src/test/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfigIT.java`

`SecurityConfig` est annotée `@Profile("!test")` : elle n'est pas chargée pendant les tests. Les tests d'intégration s'exécutent avec `TestSecurityConfig` qui réplique la matrice d'autorisation et réutilise `CspPolicyBuilder` pour la CSP.

`SecurityConfig` est **exclue des métriques de couverture SonarQube** (cf. `sonar-project.properties`) : après extraction de `CspPolicyBuilder`, il ne reste que le bean `filterChain` (DSL Spring Security déclaratif), dont le test demanderait un contexte avec profil de production, disproportionné par rapport au bénéfice.

Les tests d'intégration valident la **matrice d'autorisation** via `TestSecurityConfig` (qui réplique fidèlement les règles de production) :

#### Tests d'intégration (`SecurityConfigIT`) — 4 tests

1. **`testActuatorHealth_ShouldBePublic`**
   - `/actuator/health` accessible sans authentification

2. **`testActuatorEndpoint_WithAdminRole_ShouldBeAccessible`**
   - `/actuator/loggers` accessible avec le rôle `ROLE_admin`

3. **`testActuatorEndpoint_WithoutAdminRole_ShouldBeForbidden`**
   - `/actuator/loggers` retourne 403 pour un rôle non-admin

4. **`testActuatorEndpoint_WithoutAuthentication_ShouldBeUnauthorized`**
   - `/actuator/loggers` retourne 401 sans authentification

---

## Configuration de test

### Profil "test"

Les composants de sécurité de production utilisent `@Profile("!test")` pour se désactiver pendant les tests (Keycloak n'est pas disponible).

**Fichiers de configuration:**
- `src/test/resources/application-test.yml` — Configuration Spring Boot pour les tests
- `src/test/java/.../TestSecurityConfig.java` — Configuration de sécurité simplifiée, réutilise `CspPolicyBuilder` pour garantir la cohérence avec la CSP de production

### Base de données de test

Les tests utilisent H2 en mémoire au lieu de PostgreSQL :

```yaml
spring:
  datasource:
    url: jdbc:h2:mem:testdb
    driver-class-name: org.h2.Driver
```

---

## Exécution des tests

### Via Maven

```bash
cd /home/leno-vo/git/repository/rhDemo

# Tests unitaires uniquement (Surefire)
./mvnw test

# Tests d'intégration + rapport de couverture complet (JaCoCo)
./mvnw verify
```

Le rapport de couverture agrégé est généré dans `target/site/jacoco/index.html`.

### Tests spécifiques

```bash
# Tests du mapper seulement
./mvnw test -Dtest=GrantedAuthoritiesKeyCloakMapperTest

# Tests CSP seulement
./mvnw test -Dtest=CspPolicyBuilderTest

# Tests d'autorisation seulement
./mvnw verify -Dit.test=SecurityConfigIT
```

---

## Couverture

### Par composant

| Composant | LOC | Tests | Couverture |
|-----------|-----|-------|------------|
| `GrantedAuthoritiesKeyCloakMapper` | ~80 | 10 unitaires | ~100% |
| `CspPolicyBuilder` | ~60 | 12 unitaires | 100% |
| `SecurityConfig` | ~200 | — | **Exclu SonarQube** |
| `SpaCsrfTokenRequestHandler` | ~20 | — | **Exclu SonarQube** |

### Exclusions SonarQube (`sonar-project.properties`)

Les classes suivantes sont exclues de la **mesure de couverture** uniquement (les règles qualité/sécurité continuent de s'appliquer) :

| Classe | Justification |
|--------|---------------|
| `RhdemoApplication` | `main()` Spring Boot — boilerplate non testable hors démarrage complet |
| `SecurityConfig` | `@Profile("!test")` + DSL Spring Security déclaratif — la logique métier (CSP, CSRF) est extraite dans `CspPolicyBuilder` |
| `SpaCsrfTokenRequestHandler` | Classe interne à `SecurityConfig`, même contrainte de profil |
| `WebMvcConfig` | Mapping statique de ressources, aucune logique testable |
| `FrontendController` | Sert `index.html` en pass-through, validé fonctionnellement par les tests Selenium |

### Couverture globale estimée

**> 95%** sur le périmètre mesuré — largement au-dessus du seuil SonarQube de 50%.

---

## Points clés testés

### Sécurité

- ✅ Protection XSS via CSP stricte (pas de `unsafe-inline`/`unsafe-eval`) — `CspPolicyBuilderTest`
- ✅ `frame-ancestors 'none'` (anti-clickjacking) — `CspPolicyBuilderTest`
- ✅ Protection CSRF : cookie `XSRF-TOKEN` avec flag Secure configurable — `CspPolicyBuilderTest`
- ✅ Contrôle d'accès basé sur les rôles — `SecurityConfigIT`
- ✅ Endpoints publics correctement exposés — `SecurityConfigIT`
- ✅ Extraction et mapping des rôles Keycloak — `GrantedAuthoritiesKeyCloakMapperTest`

### Robustesse

- ✅ Gestion des claims JWT manquants — `GrantedAuthoritiesKeyCloakMapperTest`
- ✅ Gestion des URIs Keycloak invalides/null/vides — `CspPolicyBuilderTest`
- ✅ Gestion des listes de rôles vides/null — `GrantedAuthoritiesKeyCloakMapperTest`
- ✅ Filtrage correct des rôles (préfixe `ROLE_`) — `GrantedAuthoritiesKeyCloakMapperTest`

### Configuration dynamique

- ✅ Extraction automatique de l'URL Keycloak (ports standard et non-standard) — `CspPolicyBuilderTest`
- ✅ Génération de CSP adaptée à l'environnement — `CspPolicyBuilderTest`
- ✅ CSP cohérente entre production et tests (même `CspPolicyBuilder`) — `TestSecurityConfig`

---

## Cas non testés (et pourquoi)

### Logout OAuth2 (`KeycloakLogoutSuccessHandler.onLogoutSuccess`)

**Raison:** Validé par `KeycloakLogoutSuccessHandlerTest` en unitaire. Le flow HTTP complet nécessiterait Keycloak.

**Alternative:** Tests E2E Selenium dans `rhDemoAPITestIHM`.

### Workflow OAuth2 complet

**Raison:** Nécessite le flow complet OAuth2/OIDC avec Keycloak.

**Alternative:** Tests manuels ou tests E2E Selenium (déjà implémentés dans `rhDemoAPITestIHM`).

---

## Cartographie des fichiers de test (périmètre sécurité)

| Fichier | Type | Statut |
|---------|------|--------|
| `springconfig/GrantedAuthoritiesKeyCloakMapperTest.java` | Unit (Surefire) | Actif — injection constructeur |
| `springconfig/CspPolicyBuilderTest.java` | Unit (Surefire) | Actif — remplace `SecurityConfigCspDynamicTest` |
| `springconfig/SecurityConfigIT.java` | IT (Failsafe) | Actif — 4 tests d'autorisation uniquement |
| `springconfig/KeycloakLogoutSuccessHandlerTest.java` | Unit (Surefire) | Actif |
| `config/TestSecurityConfig.java` | Helper IT | Actif — réutilise `CspPolicyBuilder` |
| ~~`springconfig/SecurityConfigCspDynamicTest.java`~~ | ~~Unit (réflexion)~~ | **Supprimé** — remplacé par `CspPolicyBuilderTest` |

---

**Date de mise à jour:** 2026-05-11
**Version:** 2.0
**Status:** ✅ Couverture > 95% sur le périmètre mesuré (seuil SonarQube 50% largement dépassé)
