# Refonte de la gestion des null — Java 25

**Date :** 2026-05-19  
**Branche :** `evolutions-post-1.1.7`

## Contexte

Audit de la gestion des null sur l'ensemble du code source `rhDemo`, conduit en préparation de la version post-1.1.7. L'objectif est d'aligner le code avec les pratiques Java 25 : contrats explicites, `Optional` pour les absences de valeur, élimination des null silencieux, robustesse face aux données malformées.

---

## Changements appliqués

### 1. `GrantedAuthoritiesKeyCloakMapper` — CRITIQUE

**Problème :** Un JWT Keycloak malformé contenant `null` dans la liste `roles` provoquait une `NullPointerException` dans le stream, avant toute authentification de l'utilisateur. De plus, `Collectors.toList()` retournait une liste mutable inutilement.

**Correction :**
```java
// Avant
grantedAuths = roles.stream()
    .filter(e -> e.startsWith("ROLE_"))
    .map(SimpleGrantedAuthority::new)
    .collect(Collectors.toList());

// Après
grantedAuths = roles.stream()
    .filter(e -> e != null && e.startsWith("ROLE_"))
    .<GrantedAuthority>map(SimpleGrantedAuthority::new)
    .toList();
```

---

### 2. `CspPolicyBuilder` — CRITIQUE / MINEUR

**Problème 1 (CRITIQUE) :** Toute exception dans `extractKeycloakBaseUrl()` était avalée silencieusement par un `catch (Exception _)`. En cas d'URI Keycloak invalide en production (erreur de configuration), la CSP se dégradait à `connect-src 'self'` sans aucun log, rendant le diagnostic impossible.

**Correction :** Catch ciblé `IllegalArgumentException` (seule exception lancée par `URI.create`) avec log explicite.

```java
// Avant
} catch (Exception _) {
    return "";
}

// Après
} catch (IllegalArgumentException e) {
    log.warn("URI Keycloak invalide '{}', connect-src dégradé : {}", keycloakAuthorizationUri, e.getMessage());
    return "";
}
```

**Problème 2 (MINEUR) :** `isEmpty()` remplacé par `isBlank()` pour rejeter aussi les chaînes ne contenant que des espaces. Le guard `== null` est conservé car le constructeur est appelé directement dans les tests avec des valeurs null (hors contexte Spring).

---

### 3. `GlobalExceptionHandler` — MODÉRÉ

**Problème :** Le cast `(FieldError) error` sur `getAllErrors()` pouvait lancer une `ClassCastException` si une contrainte de niveau objet (non-field) était violée. De plus, `getDefaultMessage()` peut retourner `null`.

**Correction :** Pattern matching `instanceof` (Java 21+) avec message null-safe.

```java
// Avant
ex.getBindingResult().getAllErrors().forEach((error) -> {
    String fieldName = ((FieldError) error).getField();
    String errorMessage = error.getDefaultMessage();
    errors.put(fieldName, errorMessage);
});

// Après
ex.getBindingResult().getAllErrors().forEach(error -> {
    if (error instanceof FieldError fe) {
        errors.put(fe.getField(),
            fe.getDefaultMessage() != null ? fe.getDefaultMessage() : "Erreur de validation");
    }
});
```

---

### 4. `ErrorResponse` — MODÉRÉ

**Problème :** Le constructeur compact passait `null` pour le champ `errors`, sérialisé en `"errors": null` dans la réponse JSON, incohérent avec les réponses comportant des erreurs.

**Correction :**
```java
// Avant
public ErrorResponse(int status, String message, LocalDateTime timestamp) {
    this(status, message, timestamp, null);
}

// Après
public ErrorResponse(int status, String message, LocalDateTime timestamp) {
    this(status, message, timestamp, Map.of());
}
```

---

### 5. `EmployeResponseDTO.from()` — MODÉRÉ

**Problème :** La méthode factory `from()` n'exprimait pas que `employe` ne peut pas être null. Un appel inadvertant avec null aurait provoqué une NPE implicite sur `employe.getId()`.

**Correction :**
```java
public static EmployeResponseDTO from(Employe employe) {
    Objects.requireNonNull(employe, "employe ne peut pas être null");
    return new EmployeResponseDTO(...);
}
```

---

### 6. `Employe` (entité JPA) — MINEUR

**Problème :** Aucune annotation de nullabilité sur les champs. Le caractère nullable d'`adresse` (seul champ nullable en BDD) n'était pas documenté dans le code.

**Correction :** Annotations JSpecify (disponible comme dépendance transitive de Spring Framework).

```java
private @NonNull String prenom;
private @NonNull String nom;
private @NonNull String mail;
private @Nullable String adresse;
```

---

### 7. `KeycloakLogoutSuccessHandler` — MODÉRÉ

**Problème :** `deriveLogoutUri()` et `extractIdToken()` retournaient `null` explicitement, forçant les appelants à faire des null-checks manuels. Le contrat d'absence de valeur n'était pas exprimé dans la signature.

**Correction :** Passage à `Optional<String>` pour les deux méthodes, et simplification de l'appelant.

```java
// Avant
String logoutUri = deriveLogoutUri(authorizationUri);
if (logoutUri == null) { ... }
String idToken = extractIdToken(authentication);
if (idToken != null) { builder.queryParam("id_token_hint", idToken); }

// Après
Optional<String> logoutUri = deriveLogoutUri(authorizationUri);
if (logoutUri.isEmpty()) { ... }
extractIdToken(authentication).ifPresent(token -> builder.queryParam("id_token_hint", token));
```

Le check `authorizationUri == null || authorizationUri.isBlank()` est conservé car le constructeur accepte null (appels explicites en test et config absente).

Les tests de `KeycloakLogoutSuccessHandlerTest` ont été mis à jour en conséquence (`isNull()` → `isEmpty()`, `isEqualTo()` → `hasValue()`).

---

### 8. `EmployeSpecification` — MODÉRÉ

**Problème :** Les métacaractères LIKE (`%`, `_`, `\`) présents dans les paramètres de recherche n'étaient pas échappés, permettant à un utilisateur de réaliser des recherches non intentionnelles (ex. `%` pour tout matcher).

**Correction :** Ajout d'une méthode `escapeLike()` et utilisation du `like` à 3 arguments (avec caractère d'échappement).

```java
private static String escapeLike(String value) {
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
}

// Usage
cb.like(cb.lower(root.get("prenom")), "%" + escapeLike(prenom.toLowerCase()) + "%", '\\')
```

Compatible H2 (tests) et PostgreSQL (production).

---

### 9. `EmployeService` — MINEUR

**Problème :** Les paramètres `id` des méthodes de service n'exprimaient pas leur contrat de non-nullité. Un `null` passé provoquerait une exception JPA cryptique.

**Correction :** Annotations JSpecify `@NonNull` sur les paramètres `id`.

```java
public Employe getEmploye(final @NonNull Long id) { ... }
public void deleteEmploye(final @NonNull Long id) { ... }
public Employe updateEmploye(@NonNull Long id, Employe employe) { ... }
```

---

## Résultats

| Fichier | Sévérité | Type de correction |
|---|---|---|
| `GrantedAuthoritiesKeyCloakMapper` | CRITIQUE | Filtre null JWT + `.toList()` immuable |
| `CspPolicyBuilder` | CRITIQUE | Exception loggée + `isBlank()` |
| `GlobalExceptionHandler` | MODÉRÉ | Pattern matching `instanceof FieldError` |
| `ErrorResponse` | MODÉRÉ | `Map.of()` au lieu de `null` |
| `EmployeResponseDTO` | MODÉRÉ | `Objects.requireNonNull` |
| `KeycloakLogoutSuccessHandler` | MODÉRÉ | `Optional` sur retours null + `isBlank()` |
| `EmployeSpecification` | MODÉRÉ | Échappement métacaractères LIKE |
| `Employe` | MINEUR | Annotations JSpecify `@NonNull`/`@Nullable` |
| `EmployeService` | MINEUR | Annotations JSpecify `@NonNull` sur paramètres |

**Tests après refonte :** 95 tests unitaires, 0 échec, 0 régression.
