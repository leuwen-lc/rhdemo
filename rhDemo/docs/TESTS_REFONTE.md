# Refonte des tests rhDemo

## 0. Contexte et objectifs

### Objectifs
1. **Conserver** les tests à forte valeur métier (comportements applicatifs, validations, règles de sécurité) et ceux validant une transformation importante (mappings DTO, extraction de rôles, dérivation d'URI Keycloak…).
2. **Supprimer** les tests triviaux (getters/setters/`equals`/`hashCode`/`toString` autogénérés sur records ou entités JPA) et ceux qui ne font que dupliquer un appel mocké sans valider de logique.
3. **Refactorer** le code applicatif pour rendre testables sans réflexion les éléments qui le sont actuellement (méthodes privées de `SecurityConfig`, champ `@Value` de `GrantedAuthoritiesKeyCloakMapper`).
4. **Repositionner** certains tests entre unit (Surefire) et IT (Failsafe) selon le principe : *tests métier en unitaire, tests de chaîne HTTP / sécurité / persistance en IT*.
5. **Préserver** le quality gate SonarQube de **≥ 50 % de couverture** instructions sur le code mesuré (avec exclusions ciblées et justifiées en dernier recours).

### Méthode
- Analyse nominative (fichier par fichier, méthode par méthode) des 15 fichiers de test actuels.
- Croisement avec les rapports JaCoCo existants (`target/site/jacoco/jacoco.csv` et `target/site/jacoco-it/jacoco.csv`).
- Estimation d'impact sur la couverture après chaque action.

### Couverture actuelle (rapports JaCoCo générés au dernier build)

| Périmètre | Couverture instructions |
|---|---|
| Tests unitaires seuls (`target/site/jacoco/jacoco.csv`) | **84,21 %** (1317 / 1564) |
| Tests d'intégration seuls (`target/site/jacoco-it/jacoco.csv`) | **51,85 %** (811 / 1564) |
| Agrégée (visée Sonar via `jacoco-aggregate.exec`) | ≈ **99 %** sauf `SecurityConfig` (45,7 %) et `SpaCsrfTokenRequestHandler` (0 %) |

Le quality gate à 50 % est donc **largement atteint aujourd'hui**. La marge permet de supprimer des tests sans danger pour la cible chiffrée — le travail consiste avant tout à améliorer la qualité, pas à monter le taux.

---

## 1. Tests à SUPPRIMER (triviaux ou trop liés à l'implémentation)

### 1.1 `EmployeResponseDTOTest` — 4 tests triviaux à supprimer

Le DTO est un `record` Java : `equals`, `hashCode` et `toString` sont autogénérés par le compilateur. Les tester revient à tester le compilateur Java, pas du code applicatif.

| Test à supprimer | Motif |
|---|---|
| `testEquals_SameValues_ShouldBeEqual` | `record` : `equals` autogénéré |
| `testEquals_DifferentId_ShouldNotBeEqual` | idem |
| `testHashCode_SameValues_ShouldBeEqual` | idem |
| `testToString_ShouldContainFieldValues` | `record` : `toString` autogénéré |

À **conserver** dans ce fichier : les 3 tests sur `from(Employe)` (mapping entité → DTO, vraie transformation).

**Impact couverture** : nul. Les méthodes `equals`/`hashCode`/`toString` ne portent aucune logique métier et la classe `EmployeResponseDTO` reste à 100 % couverte par les tests `from()`.

---

### 1.2 `AccueilControllerTest` — fichier entier à supprimer

Ce fichier teste `AccueilController` sans contexte Spring (instanciation directe). Tous ses tests sont strictement redondants avec `AccueilControllerIT` qui valide la même chose dans la vraie chaîne HTTP avec Spring Security.

| Test unitaire | Test IT équivalent |
|---|---|
| `getUserInfo_ShouldReturnUsernameAndRoles` | `testUserInfo_WithConsultRole_ShouldReturnUsernameAndRoles` |
| `getUserInfo_WithMultipleRoles_ShouldReturnAllRoles` | `testUserInfo_WithMultipleRoles_ShouldReturnAllRoles` |
| `getInfo_ShouldReturnInfoPage` | `testAccueil_ShouldReturnWelcomeMessage` (assertion plus large, à renforcer si besoin) |

Le contrôleur ne porte pas de logique métier autre qu'un mapping de rôles trivial — l'IT couvre tout, y compris l'autorisation `@PreAuthorize`.

**Action complémentaire** : enrichir `AccueilControllerIT.testAccueil_ShouldReturnWelcomeMessage` pour reproduire les assertions de contenu de `getInfo_ShouldReturnInfoPage` (présence de `/api/`, `/front`, `Swagger UI`, `OpenAPI`, `Logout`) avant de supprimer.

**Impact couverture** : nul (`AccueilController` reste 100 % couvert par l'IT).

---

### 1.3 `EmployeControllerTest` — fichier entier à supprimer

Tests unitaires Mockito sur `EmployeController` qui dupliquent intégralement `EmployeControllerIT` (37 tests IT couvrent CRUD + pagination + tri + filtres + autorisations + validation).

Les 6 tests unitaires (`getEmployesPage_WithSort_*`, `getEmployes_ShouldDelegateToService`, `getEmploye_ShouldDelegateToService`, `createEmploye_ShouldDelegateToService`, `updateEmploye_ShouldDelegateToService`, `deleteEmploye_ShouldDelegateToService`) ne font que vérifier que le contrôleur **délègue au service** — c'est typiquement du test d'implémentation : ils figent le pattern d'appel au lieu d'un comportement.

Le seul test apportant une vraie logique propre au contrôleur (`getEmployesPage_WithSort_ShouldCreateSortedPageable` qui inspecte le `Pageable` via `ArgumentCaptor`) est déjà validé fonctionnellement par `EmployeControllerIT.testGetEmployesPage_WithSort_ShouldReturnSortedList` (vérification du tri sur le résultat réel — bien plus probant).

**Impact couverture** : nul (`EmployeController` reste 100 % couvert par l'IT).

---

### 1.4 `EmployeServiceTest` — 1 test trivial à supprimer

| Test à supprimer | Motif |
|---|---|
| `testGetEmployes_WhenEmpty_ShouldReturnEmptyList` | Trivial : on mocke `findAll()` retournant `emptyList()` et on vérifie la taille 0. Ne valide aucune règle métier. |

À **conserver** : tous les autres tests de ce fichier — ils valident de vraies règles :
- `EmployeNotFoundException` levée sur ID inexistant (CREATE, UPDATE, DELETE, GET)
- `createEmploye` nullifie l'id du body (règle métier : l'id vient toujours de la base)
- `updateEmploye` écrase l'id du body par l'id du path (règle métier : path > body)
- Délégation des filtres au repository via `Specification`

**Impact couverture** : nul.

---

### 1.5 `SecurityConfigIT.testCspHeader_*` — 12 tests à supprimer

**⚠️ Constat critique** : ces 12 tests s'exécutent avec le profil `test`, qui désactive `SecurityConfig` (annoté `@Profile("!test")`) et active `TestSecurityConfig`. Les assertions portent donc sur le CSP de la **config de test** (`TestSecurityConfig.buildCspDirectives`), pas sur celui de la **production** (`SecurityConfig.buildCspDirectives`).

Exemple concret de divergence :
- `TestSecurityConfig` (ligne 75) : `frame-ancestors 'self'`
- `SecurityConfig` (ligne 117) : `frame-ancestors 'none'`
- L'IT `testCspHeader_ShouldContainFrameAncestors` asserte `'self'` → il valide la version **dupliquée pour les tests**, pas la prod.

Ces 12 tests donnent une **fausse confiance** sur le CSP de production. À supprimer, en les remplaçant par des tests unitaires sur la classe extraite `CspPolicyBuilder` (cf. §2.1 ci-dessous), qui sera utilisée à la fois par `SecurityConfig` et `TestSecurityConfig`.

Tests à **conserver** dans `SecurityConfigIT` : les 4 tests d'autorisation (`/actuator/health` public, `/actuator/loggers` 401/403 selon rôle) → ils valident la vraie chaîne `TestSecurityConfig` qui replique la matrice d'autorisation de production.

Tests à **supprimer** :
- `testCspHeader_ShouldBePresent`
- `testCspHeader_ShouldContainDefaultSrcSelf`
- `testCspHeader_ShouldContainScriptSrcSelfOnly`
- `testCspHeader_ShouldContainStyleSrcSelfOnly`
- `testCspHeader_ShouldContainImgSrc`
- `testCspHeader_ShouldContainFontSrc`
- `testCspHeader_ShouldContainConnectSrc`
- `testCspHeader_ShouldContainFrameSrc`
- `testCspHeader_ShouldContainFrameAncestors`
- `testCspHeader_ShouldContainFormAction`
- `testCspHeader_ShouldContainObjectSrcNone`
- `testCspHeader_ShouldContainBaseUri`

**Impact couverture** : pas d'impact sur `SecurityConfig` (IT déjà à 0 % sur cette classe en raison de `@Profile("!test")`). La couverture du CSP est rétablie par les tests unitaires de `CspPolicyBuilder` (§2.1).

---

### 1.6 `SecurityConfigCspDynamicTest` — fichier entier à supprimer puis remplacer

Ce fichier (269 lignes, 13 tests) teste 3 méthodes **privées** de `SecurityConfig` (`extractKeycloakBaseUrl`, `buildCspDirectives`, `createCsrfTokenRepository`) **via `ReflectionTestUtils.invokeMethod`** + injection de champs `@Value` via `ReflectionTestUtils.setField`. C'est l'exemple-type du test fragile lié à l'implémentation.

Action : supprimer ce fichier et remplacer par des tests unitaires propres sur la nouvelle classe `CspPolicyBuilder` (cf. §2.1). Le contenu des assertions (URIs Keycloak, directives CSP, options CSRF Cookie) sera **strictement préservé** — seule la mécanique d'invocation change.

**Impact couverture** : neutre — les 146 instructions actuellement couvertes dans `SecurityConfig` migrent dans `CspPolicyBuilder` qui sera 100 % couvert.

---

### 1.7 Récapitulatif des suppressions

| Fichier | Tests supprimés | Lignes supprimées (≈) |
|---|---|---|
| `EmployeResponseDTOTest.java` | 4 tests sur 7 | ~35 |
| `AccueilControllerTest.java` | Fichier entier (3 tests) | 81 |
| `EmployeControllerTest.java` | Fichier entier (6 tests) | 189 |
| `EmployeServiceTest.java` | 1 test sur 13 | ~13 |
| `SecurityConfigIT.java` | 12 tests sur 16 | ~100 |
| `SecurityConfigCspDynamicTest.java` | Fichier entier (13 tests) | 269 |
| **Total** | **39 tests** | **~687 lignes** |

---

## 2. Refactorings du code applicatif (pour rendre testable sans réflexion)

### 2.1 Extraire `CspPolicyBuilder` depuis `SecurityConfig`

**Problème** : `SecurityConfig` mélange (a) la configuration Spring (filterChain bean, OAuth2, logout), (b) une logique de calcul des directives CSP, (c) le câblage du repository CSRF. Cette logique de calcul est testée par réflexion, et elle est dupliquée dans `TestSecurityConfig`.

**Refactoring** : créer une classe publique `fr.leuwen.rhdemoAPI.springconfig.CspPolicyBuilder`, instanciée comme bean Spring, prenant en constructeur :
- `String keycloakAuthorizationUri` (injecté via `@Value`)
- `boolean cookieSecureFlag` (injecté via `@Value`)

Et exposant **publiquement** :
- `String extractKeycloakBaseUrl()` (actuellement privé)
- `String buildCspDirectives()` (actuellement privé)
- `CookieCsrfTokenRepository createCsrfTokenRepository()` (actuellement privé)

`SecurityConfig` reçoit ce bean par injection constructeur et l'utilise dans `filterChain(...)`. `TestSecurityConfig` peut faire de même — la duplication du `buildCspDirectives` simplifié disparaît, et les tests d'intégration testeront le **vrai** CSP de production.

**Bénéfices** :
- Suppression de toute réflexion dans les tests CSP.
- Tests unitaires écrits avec un constructeur normal : `new CspPolicyBuilder(uri, secureFlag).buildCspDirectives()`.
- Suppression de la divergence test/prod sur le CSP (cf. §1.5).
- `SecurityConfig` redevient une simple classe de configuration Spring sans logique métier.

**Tests unitaires à créer** : `CspPolicyBuilderTest` reprenant 1:1 les assertions actuelles de `SecurityConfigCspDynamicTest` mais sans `ReflectionTestUtils`. ~13 tests.

---

### 2.2 Rendre `GrantedAuthoritiesKeyCloakMapper` testable sans `setField`

**Problème** : le champ `@Value private String rhDemoClientID` est injecté par Spring. En test unitaire pur (sans contexte Spring), il faut le forcer via `ReflectionTestUtils.setField(mapper, "rhDemoClientID", CLIENT_ID)`.

**Refactoring** : passer en injection par constructeur.

```java
@Component
@Profile("!test")
public class GrantedAuthoritiesKeyCloakMapper implements GrantedAuthoritiesMapper {

    private final String rhDemoClientID;

    public GrantedAuthoritiesKeyCloakMapper(
            @Value("${spring.security.oauth2.client.registration.keycloak.client-id}") String rhDemoClientID) {
        this.rhDemoClientID = rhDemoClientID;
    }
    // ...
}
```

C'est strictement la pratique recommandée par Spring depuis longtemps (immutabilité, testabilité, échec rapide si propriété manquante).

**Tests unitaires** : `GrantedAuthoritiesKeyCloakMapperTest.setUp()` devient `mapper = new GrantedAuthoritiesKeyCloakMapper(CLIENT_ID);` — plus de `setField`. Aucun test à modifier sur le fond, juste cette ligne.

**Impact couverture** : nul (la classe reste 100 % couverte).

---

### 2.3 (Optionnel — à n'envisager qu'après §2.1) Faire utiliser `CspPolicyBuilder` par `TestSecurityConfig`

Une fois `CspPolicyBuilder` extrait, `TestSecurityConfig.buildCspDirectives()` devient inutile : remplacer par injection du bean `CspPolicyBuilder` (déclarer le bean sans `@Profile("!test")` ou créer une variante pour test). Cela élimine la duplication et garantit que les IT testent vraiment la CSP de production.

---

## 3. Bascules unit ↔ IT

L'analyse n'a pas révélé de cas où une bascule franche est nécessaire — le découpage actuel est globalement correct :

- **Tests métier en unit (Surefire)** : `EmployeServiceTest`, `EmployeRequestDTOTest`, `EmployeResponseDTOTest`, `GrantedAuthoritiesKeyCloakMapperTest`, `KeycloakLogoutSuccessHandlerTest`, et le futur `CspPolicyBuilderTest` → ✅ conformes à la consigne « privilégier l'unitaire pour les couches métier ».
- **Tests d'infrastructure en IT (Failsafe)** : `EmployeControllerIT`, `AccueilControllerIT`, `GlobalExceptionHandlerIT`, `SecurityConfigIT` (allégé), `EmployeSpecificationTest` (utilise `@DataJpaTest` donc passe par Spring, mais le suffixe `Test` le fait tourner en Surefire — voir §3.1).

### 3.1 Cas particulier : `EmployeSpecificationTest`

Ce fichier utilise `@DataJpaTest` qui démarre un contexte Spring partiel + H2. Techniquement, c'est un test d'intégration au sens « démarrage de framework », mais il a un suffixe `Test` donc il tourne dans **Surefire**.

**Recommandation** : renommer `EmployeSpecificationTest` → `EmployeSpecificationIT` pour le faire basculer dans **Failsafe**. Raisons :
1. Cohérence : tout test démarrant un contexte Spring est dans Failsafe (autres exemples : `*ControllerIT`, `GlobalExceptionHandlerIT`).
2. Surefire reste léger (pas de bootstrap Spring) → pipeline CI plus rapide sur la phase test unitaire.
3. Aucun changement de logique ni d'assertions.

**Alternative** si on souhaite garder un vrai test unitaire** : extraire les prédicats JPA dans une classe `EmployeSpecificationBuilder` instanciable sans BDD et tester sa logique de composition sans `@DataJpaTest`. Plus lourd, peu de bénéfice — non recommandé.

---

## 4. Exclusions SonarQube (dernier recours)

Aucune exclusion n'est strictement **nécessaire** pour atteindre 50 % de couverture (on est largement au-dessus). Mais certaines classes biaisent le rapport en mêlant du code non métier au calcul. Les exclusions proposées améliorent la **lisibilité** du rapport sans masquer de risque réel.

À ajouter dans `sonar-project.properties` :

```properties
# Exclusions de la couverture de code
# (les classes restent analysées pour les règles qualité/sécurité — seule la couverture est exclue)
sonar.coverage.exclusions=\
    **/RhdemoApplication.java,\
    **/springconfig/SecurityConfig.java,\
    **/springconfig/SpaCsrfTokenRequestHandler.java,\
    **/springconfig/WebMvcConfig.java,\
    **/controller/FrontendController.java
```

### Justification classe par classe

| Classe | Couverture actuelle | Justification de l'exclusion |
|---|---|---|
| `RhdemoApplication` | 37,5 % | Méthode `main()` Spring Boot — boilerplate non testable hors démarrage complet. Pattern standard. |
| `SecurityConfig` | 45,7 % (unit), 0 % (IT) | Après extraction de `CspPolicyBuilder` (§2.1), il ne reste que le bean `filterChain` (DSL Spring Security fluent) qui est de la configuration déclarative. Profil `!test` empêche l'IT d'y entrer. Tester cette classe demande de monter un contexte avec profil de production ET de désactiver les mocks d'authentification, ce qui est disproportionné. |
| `SpaCsrfTokenRequestHandler` | 0 % | Classe interne à `SecurityConfig`, instanciée uniquement en profil de production. Même raison que ci-dessus. À tester via les tests E2E Selenium (déjà en place dans `rhDemoAPITestIHM/`, hors couverture JaCoCo de toute façon). |
| `WebMvcConfig` | 100 % (chargée par le contexte) mais sans assertion réelle | Mappe statiquement des chemins vers `classpath:/static/...`. Pas de logique, pas de branchement. Le test serait un « assertResourceHandlerRegistered » sans valeur. |
| `FrontendController` | 27 % | Retourne un `ResponseEntity` enveloppant `static/index.html`. Tester nécessiterait un contexte Spring complet servant la ressource — coût disproportionné pour une indirection triviale. Couvert fonctionnellement par les tests Selenium. |

### Ne PAS exclure
- `GlobalExceptionHandler` — déjà ~97 % couvert, c'est le formatage des erreurs API, comportement observable critique.
- `EmployeNotFoundException` — petite classe mais déjà 60 % couverte (la branche non couverte est le constructeur `(String)` non utilisé : à supprimer plutôt qu'à exclure, cf. §6).

---

## 5. Estimation d'impact

### Couverture estimée après refonte

| Classe | Avant (unit) | Après (unit + IT + CspPolicyBuilder) |
|---|---|---|
| `EmployeService` | 100 % | 100 % |
| `EmployeSpecification` | 100 % | 100 % (renommé `*IT` mais reste couvert) |
| `EmployeRequestDTO` | 100 % | 100 % |
| `EmployeResponseDTO` | 100 % | 100 % (4 tests triviaux retirés, `from()` toujours testé) |
| `EmployeController` | 100 % | 100 % (via IT seul, plus de doublon unitaire) |
| `AccueilController` | 100 % | 100 % (via IT seul) |
| `GlobalExceptionHandler` | 97 % | 97 % |
| `GrantedAuthoritiesKeyCloakMapper` | 100 % | 100 % (sans réflexion) |
| `KeycloakLogoutSuccessHandler` | 100 % | 100 % |
| `CspPolicyBuilder` (nouveau) | — | **100 %** |
| `SecurityConfig` | 45,7 % | **exclu** |
| `SpaCsrfTokenRequestHandler` | 0 % | **exclu** |
| `WebMvcConfig` | 100 % | **exclu** |
| `FrontendController` | 27 % | **exclu** |
| `RhdemoApplication` | 37 % | **exclu** |

**Couverture globale estimée après exclusions : > 95 %** (très largement au-dessus du seuil de 50 %).

### Coût du refactoring

| Action | Effort estimé |
|---|---|
| Suppression des 39 tests listés | ~30 min |
| Extraction `CspPolicyBuilder` (classe + bean Spring) | ~1 h |
| Réécriture des tests CSP en unit sur la nouvelle classe (~13 tests) | ~1 h |
| Refactoring `GrantedAuthoritiesKeyCloakMapper` (constructeur injection) | ~15 min |
| Refactoring `TestSecurityConfig` pour réutiliser `CspPolicyBuilder` (§2.3) | ~30 min |
| Renommage `EmployeSpecificationTest` → `*IT` | ~5 min |
| Ajout des exclusions Sonar | ~10 min |
| Vérification (build + couverture) | ~30 min |
| **Total** | **~4 h** |

---

## 6. Nettoyages secondaires (constatés au passage)

Ces points ne sont pas demandés explicitement mais identifiés pendant l'analyse :

1. **`EmployeNotFoundException(String message)`** : constructeur non utilisé. À supprimer plutôt qu'à conserver pour la couverture.
2. **`AccueilController.getInfo()`** : la chaîne renvoyée référence `/actuator (dispo en dev local uniquement)` et `/api-docs/...` — vérifier que ces mentions sont à jour avec la configuration `stagingkub` (les actuator y sont sur port 9001 non exposé).
3. **`SpaCsrfTokenRequestHandler` et `TestSpaCsrfTokenRequestHandler`** : strictement identiques. Après §2.3, supprimer `TestSpaCsrfTokenRequestHandler` et faire réutiliser le handler de production par `TestSecurityConfig`.

---

## 7. Plan d'exécution proposé

Ordre recommandé pour minimiser les régressions :

1. **§2.2** Refactor `GrantedAuthoritiesKeyCloakMapper` (constructeur) + adapter son test → build vert.
2. **§2.1** Extraire `CspPolicyBuilder` + créer `CspPolicyBuilderTest` (reprise des assertions de `SecurityConfigCspDynamicTest`) → build vert.
3. **§1.6** Supprimer `SecurityConfigCspDynamicTest` → build vert (couverture conservée par §2.1).
4. **§1.5** Supprimer les 12 tests CSP de `SecurityConfigIT` → build vert.
5. **§2.3** Refactorer `TestSecurityConfig` pour réutiliser `CspPolicyBuilder` → build vert.
6. **§1.1, §1.2, §1.3, §1.4** Supprimer les tests triviaux/dupliqués → build vert.
7. **§3.1** Renommer `EmployeSpecificationTest` → `EmployeSpecificationIT` → build vert.
8. **§4** Ajouter les exclusions dans `sonar-project.properties` → push et vérifier le rapport Sonar.

À chaque étape : lancer `./mvnw verify` et vérifier que la couverture reste > 50 % via le rapport `target/site/jacoco/jacoco.csv`.

---

## Annexe — Cartographie complète des tests

| Fichier | Type | Statut après refonte | Action |
|---|---|---|---|
| `config/TestDataLoader.java` | Helper IT | Conservé | — |
| `config/TestSecurityConfig.java` | Helper IT | Refactoré | Réutilise `CspPolicyBuilder` |
| `controller/AccueilControllerIT.java` | IT | Conservé | Enrichir 1 assertion |
| `controller/AccueilControllerTest.java` | Unit | **Supprimé** | Couvert par IT |
| `controller/EmployeControllerIT.java` | IT | Conservé | — |
| `controller/EmployeControllerTest.java` | Unit | **Supprimé** | Couvert par IT |
| `dto/EmployeRequestDTOTest.java` | Unit | Conservé | — |
| `dto/EmployeResponseDTOTest.java` | Unit | Allégé | 4 tests triviaux retirés |
| `exception/GlobalExceptionHandlerIT.java` | IT | Conservé | — |
| `repository/EmployeSpecificationTest.java` | Unit (en réalité IT) | Renommé `*IT` | Bascule Failsafe |
| `service/EmployeServiceTest.java` | Unit | Allégé | 1 test trivial retiré |
| `springconfig/GrantedAuthoritiesKeyCloakMapperTest.java` | Unit | Conservé | Plus de `setField` |
| `springconfig/KeycloakLogoutSuccessHandlerTest.java` | Unit | Conservé | — |
| `springconfig/SecurityConfigCspDynamicTest.java` | Unit (réflexion) | **Supprimé** | Remplacé par `CspPolicyBuilderTest` |
| `springconfig/SecurityConfigIT.java` | IT | Allégé | 12 tests CSP retirés, 4 d'autorisation conservés |
| `springconfig/CspPolicyBuilderTest.java` (nouveau) | Unit | **À créer** | Tests de §2.1 sans réflexion |
