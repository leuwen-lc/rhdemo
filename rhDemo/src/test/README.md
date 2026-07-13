# Tests RHDemo API

## Organisation

Deux familles de tests, exécutées par deux plugins Maven distincts :

| Plugin | Suffixe | Phase Maven | Démarrage Spring |
|---|---|---|---|
| Surefire | `*Test.java` | `test` | Non (ou minimal) |
| Failsafe | `*IT.java` / `*ITCase.java` | `integration-test` / `verify` | Oui (`@SpringBootTest` ou `@DataJpaTest`) |

Voir `docs/TESTS_REFONTE.md` pour la justification de cette répartition et l'historique de la refonte.

## Tests unitaires (Surefire — `*Test.java`)

Tests métier isolés, sans contexte Spring (sauf exceptions ci-dessous), généralement avec Mockito.

| Classe | Périmètre testé |
|---|---|
| `service.EmployeServiceTest` | Logique métier `EmployeService` : règles d'écrasement d'id (POST nullifie, PUT impose le path), exceptions `EmployeNotFoundException` sur ID inexistant, délégation des filtres au repository via `Specification`. |
| `dto.EmployeRequestDTOTest` | Contraintes Bean Validation (`@NotBlank`, `@Email`, `@Size`) sur les champs du DTO d'entrée + mapping `toEmploye()`. |
| `dto.EmployeResponseDTOTest` | Mapping `EmployeResponseDTO.from(Employe)` (entité → DTO). |
| `springconfig.GrantedAuthoritiesKeyCloakMapperTest` | Extraction des rôles depuis `resource_access` du token OIDC Keycloak, filtrage des rôles non préfixés `ROLE_`, gestion des claims manquants/null. |
| `springconfig.KeycloakLogoutSuccessHandlerTest` | Dérivation de l'URL `logout` depuis `authorization-uri`, extraction du `id_token_hint`, construction de l'URL de base derrière `ForwardedHeaderFilter`. |
| `springconfig.CspPolicyBuilderTest` | Extraction de l'URL de base Keycloak, construction des directives Content-Security-Policy (sans `unsafe-*`), configuration du repository CSRF Cookie. |

## Tests d'intégration (Failsafe — `*IT.java`)

Tests démarrant un contexte Spring (souvent avec `MockMvc`) — valident la chaîne HTTP, la sécurité, la persistance.

| Classe | Périmètre testé |
|---|---|
| `controller.EmployeControllerIT` | CRUD complet `/api/employes`, pagination, tri, filtres, autorisations `@PreAuthorize`, validation HTTP. |
| `controller.AccueilControllerIT` | Endpoints `/` (page d'info) et `/api/userinfo` avec autorisations basées rôles. |
| `exception.GlobalExceptionHandlerIT` | Formatage JSON des erreurs : 404 `EmployeNotFoundException`, 400 validation/type, et non-interception des exceptions Spring Security. |
| `repository.EmployeSpecificationIT` | Specifications JPA contre H2 en mémoire (`@DataJpaTest`) : filtres simples, combinés, insensibles à la casse, partiels. |
| `springconfig.SecurityConfigIT` | Matrice d'autorisation : `/actuator/health` public, `/actuator/loggers` restreint au rôle `admin`, 401/403 selon le contexte. |

> Note : les directives CSP sont testées en unitaire sur `CspPolicyBuilder` (qui est la classe réellement utilisée par `SecurityConfig` **et** par `TestSecurityConfig`). Ce qui évite la divergence test/prod qui existait avant la refonte.

## Configuration de test

| Fichier | Rôle |
|---|---|
| `config/TestSecurityConfig.java` | Configuration `@EnableWebSecurity` activée par `@Profile("test")`. Remplace `SecurityConfig` (désactivé en profil `test`), désactive OAuth2/Keycloak, simule l'authentification via `@WithMockUser`. Réutilise `CspPolicyBuilder` pour partager exactement le CSP de production. |
| `config/TestDataLoader.java` | `@TestConfiguration` qui charge 4 employés de test dans H2 au démarrage du contexte. Importé par les IT via `@Import(TestDataLoader.class)`. |
| `resources/application-test.yml` | Profil Spring `test` : datasource H2 in-memory, désactivation OAuth2, exposition actuator restreinte. |
| `resources/employe-test-data.sql` | Jeu de données SQL alternatif (utilisable au besoin). |

### Données de test injectées par `TestDataLoader`

| Prénom | Nom | Mail | Adresse |
|---|---|---|---|
| Laurent | Martin | laurent.martin@example.com | 1 Rue de la Paix, Paris |
| Sophie | Dubois | sophie.dubois@example.com | 2 Avenue des Champs, Lyon |
| Pierre | Bernard | pierre.bernard@example.com | 3 Boulevard Victor Hugo, Marseille |
| Marie | Durand | marie.durand@example.com | 4 Place de la République, Toulouse |

## Exécution

```bash
# Tests unitaires uniquement (Surefire)
./mvnw test

# Tests unitaires + intégration + couverture JaCoCo
./mvnw verify
# Rapport HTML : target/site/jacoco/index.html
# Rapport CSV  : target/site/jacoco/jacoco.csv

# Filtrer un test
./mvnw test -Dtest=EmployeServiceTest
./mvnw verify -Dit.test=EmployeControllerIT#testGetEmployesPage_WithSort_ShouldReturnSortedList
```

## Couverture de code

**Quality gate SonarQube** : couverture instructions ≥ **50 %** sur le nouveau code.

Couverture mesurée après refonte (rapport aggregate `target/site/jacoco/jacoco.csv`) : **~82 %** brute, **~97 %** après exclusions Sonar.

Classes exclues du calcul de couverture (déclaré dans `sonar-project.properties`, justifications dans `docs/TESTS_REFONTE.md` §4) :
- `RhdemoApplication` — main Spring Boot.
- `SecurityConfig`, `SpaCsrfTokenRequestHandler` — `@Profile("!test")`, configuration déclarative Spring Security DSL non exercée en test.
- `WebMvcConfig` — mapping statique de ressources, pas de logique.
- `FrontendController` — pass-through vers `index.html`, validé fonctionnellement par les tests Selenium du projet `rhDemoAPITestIHM/`.

## Conventions

1. **Nommage** : `testMethodName_Condition_ExpectedResult` (style assertion) ou `methodName_Scenario` (style BDD). Les deux cohabitent dans le projet.
2. **Structure** : Arrange / Act / Assert lisible (séparateurs `// ════` autorisés pour grouper visuellement).
3. **Pas de réflexion** : si un test a besoin de `ReflectionTestUtils`, c'est le signal d'un défaut de testabilité du code applicatif — refactoring préféré (cf. extraction `CspPolicyBuilder` et injection constructeur de `GrantedAuthoritiesKeyCloakMapper`).
4. **Tests métier en unitaire** privilégiés (Surefire, sans Spring) — IT réservé à ce qui ne se teste pas autrement : sécurité, persistance, contrat HTTP, formatage des réponses.
5. **Pas de doublon unit/IT** sur un même comportement : choisir le niveau le plus représentatif.
6. **Marqueurs Selenium** : les attributs `data-testid` sont posés côté frontend pour la robustesse des tests E2E (cf. `docs/DATA_TESTID_GUIDE.md`).

## Voir aussi

- `docs/TESTS_REFONTE.md` — Refonte des tests : suppressions, refactorings, exclusions Sonar.
- `docs/TESTS_SECURITE_COUVERTURE.md` — Couverture des tests de sécurité.
- `docs/DATA_TESTID_GUIDE.md` — Marqueurs `data-testid` pour Selenium.
- `rhDemoAPITestIHM/` — Tests E2E Selenium (projet séparé, hors couverture JaCoCo).
