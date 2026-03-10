# Normalisation REST de l'API Employé

## Vue d'ensemble

Ce document décrit les modifications apportées à l'API REST de gestion des employés dans le cadre de la branche `evolutions-post-1.1.6`, ainsi que l'écart restant par rapport à une normalisation REST complète.

---

## Modifications apportées

### Contexte

Avant ces modifications, l'API employé présentait trois problèmes de conception :

1. **`POST /api/employe` traitait à la fois la création et la mise à jour** selon la nullité de l'`id` dans le corps de la requête — couplage implicite, surface d'attaque ouverte.
2. **`DELETE /api/employe?id=X`** passait l'identifiant en query parameter — contraire aux conventions REST qui placent l'identifiant de ressource dans le chemin.
3. **`saveEmploye()` dans le service** ne distinguait pas les deux opérations, rendant impossible la validation métier spécifique à chaque cas (ex. vérifier l'existence avant une mise à jour).

### Nouveaux endpoints

| Verbe | URL | Rôle requis | Code succès | Avant |
|---|---|---|---|---|
| `POST` | `/api/employe` | `MAJ` | `201 Created` | `POST /api/employe` → 200 |
| `PUT` | `/api/employe/{id}` | `MAJ` | `200 OK` | *inexistant* |
| `DELETE` | `/api/employe/{id}` | `MAJ` | `204 No Content` | `DELETE /api/employe?id=X` → 200 |

Les endpoints GET restent inchangés :

| Verbe | URL | Rôle requis |
|---|---|---|
| `GET` | `/api/employes` | `consult` |
| `GET` | `/api/employes/page` | `consult` |
| `GET` | `/api/employe?id=X` | `consult` |

### Comportements de sécurité ajoutés

**Création (`POST`) :**
- `EmployeService.createEmploye()` force `employe.setId(null)` avant le `save()`, quelle que soit la valeur reçue dans le corps.
- Un client qui envoie `{ "id": 99, "prenom": "..." }` voit l'id ignoré : la ressource est toujours créée avec un id généré par la base.

**Mise à jour (`PUT`) :**
- `EmployeService.updateEmploye(Long id, Employe employe)` vérifie l'existence via `existsById()` avant d'écrire — une tentative de mise à jour sur un id inexistant retourne `404 Not Found`.
- L'id de la ressource est pris exclusivement depuis le chemin (`@PathVariable`) et écrase toute valeur présente dans le corps via `employe.setId(id)`.

**Suppression (`DELETE`) :**
- L'id se trouve désormais dans le chemin (`/api/employe/{id}`) conformément aux conventions REST.
- Le code de retour passe de `200 OK` à `204 No Content` : sémantiquement correct, la ressource supprimée n'a rien à retourner.

### Fichiers modifiés

| Fichier | Nature du changement |
|---|---|
| `service/EmployeService.java` | `saveEmploye()` remplacé par `createEmploye()` et `updateEmploye(id, employe)` |
| `controller/EmployeController.java` | Trois endpoints distincts avec verbes et codes HTTP corrects |
| `frontend/src/services/api.js` | `saveEmploye()` remplacé par `createEmploye()` et `updateEmploye(id, data)` · `deleteEmploye(id)` URL corrigée · fonction `testSaveEmploye()` inutilisée supprimée |
| `frontend/src/components/EmployeForm.vue` | Branchement conditionnel sur `isEditing` pour appeler la bonne fonction |
| `test/service/EmployeServiceTest.java` | 2 tests `saveEmploye` → 5 tests couvrant create, createIgnoreId, update, updatePathId, updateNotFound |
| `test/controller/EmployeControllerTest.java` | Tests unitaires adaptés aux nouvelles signatures |
| `test/controller/EmployeControllerIT.java` | POST→201, nouveaux tests PUT, DELETE path variable + 204 |

### Résultats des tests après modification

```
Tests unitaires  : 110 tests, 0 échec
Tests intégration :  56 tests, 0 échec
```

---

## Écart restant par rapport à une normalisation REST complète

### 1. GET par id — query parameter au lieu de path variable

**État actuel :**
```
GET /api/employe?id=5
```

**Forme REST standard :**
```
GET /api/employe/5
```

**Impact :** Incohérence dans la conception de l'API — les opérations de modification (PUT, DELETE) utilisent désormais `/{id}` alors que la lecture utilise `?id=`. Cela peut surprendre les consommateurs de l'API et complexifie la génération de documentation OpenAPI cohérente.

**Complexité de correction :** Modérée.
- Backend : changer `@RequestParam` en `@PathVariable` sur `getEmploye()`.
- Frontend : `getEmploye(id)` dans `api.js` passe de `api.get('/employe', { params: { id } })` à ``api.get(`/employe/${id}`)``.
- `EmployeDelete.vue` et `EmployeModify.vue` appellent `getEmploye(id)` sans connaître l'URL — aucun changement dans les composants.
- Tests IT : les `get("/api/employe").param("id", ...)` deviennent `get("/api/employe/{id}", id)`.
- Tests Selenium : transparents (pilotent le navigateur, pas l'URL HTTP directement).

**Note :** `GET /api/employes` (liste complète) et `GET /api/employes/page` (pagination) sont déjà au pluriel et conformes. Seul `GET /api/employe?id=X` reste à corriger.

---

### 2. Plural vs singular dans les URLs

**État actuel :**
```
GET  /api/employes          ← pluriel (correct)
GET  /api/employes/page     ← pluriel (correct)
GET  /api/employe?id=X      ← singulier
POST /api/employe           ← singulier
PUT  /api/employe/{id}      ← singulier
DELETE /api/employe/{id}    ← singulier
```

**Convention REST standard :** toutes les opérations sur une même ressource partagent la même base d'URL au pluriel.
```
GET    /api/employes
GET    /api/employes/page
GET    /api/employes/{id}
POST   /api/employes
PUT    /api/employes/{id}
DELETE /api/employes/{id}
```

**Impact :** L'incohérence singulier/pluriel est un signal d'alerte dans une revue d'API. Elle complique la mise en place d'un gateway ou d'un client généré depuis OpenAPI.

**Complexité de correction :** Faible en termes de logique, mais nécessite de changer toutes les URLs dans le contrôleur, `api.js`, et les tests IT. Les tests Selenium sont transparents.

---

### 3. Absence de DTOs immutables (records Java)

**État actuel :** L'entité JPA `Employe` est exposée directement par l'API — les annotations `@Entity`, `@Column` cohabitent avec les annotations de validation `@NotBlank`, `@Email`, `@Size` dans la même classe.

**Problèmes restants :**
- Tout champ ajouté à l'entité (audit, soft-delete, champ interne) est automatiquement sérialisé côté client.
- L'entité est mutable — Jackson peut écrire n'importe quel champ déclaré.
- Pas de contrat API stable découplé du modèle de persistance.

**Forme cible :**
```java
// Réponse API (record immutable)
public record EmployeResponseDTO(Long id, String prenom, String nom, String mail, String adresse) {
    public static EmployeResponseDTO from(Employe employe) { ... }
}

// Requête API (record avec validation)
public record EmployeRequestDTO(
    @NotBlank @Size(min=2, max=50) String prenom,
    @NotBlank @Size(min=2, max=50) String nom,
    @NotBlank @Email @Size(max=100) String mail,
    @Size(max=200) String adresse
) {
    public Employe toEmploye() { ... }
}
```

Avec cette forme, `PUT /api/employe/{id}` reçoit un `EmployeRequestDTO` sans champ `id` — l'id ne peut structurellement pas figurer dans le corps d'une mise à jour.

**Complexité de correction :** Modérée — voir `docs/API_REST_NORMALISATION.md` plan DTO.

---

### 4. `ErrorResponse` — classe mutable avec setters inutilisés

**État actuel :** `ErrorResponse` est un POJO avec 4 setters qui ne sont jamais appelés (seuls les constructeurs sont utilisés).

**Forme cible :**
```java
public record ErrorResponse(int status, String message, LocalDateTime timestamp, Map<String, String> errors) {
    public ErrorResponse(int status, String message, LocalDateTime timestamp) {
        this(status, message, timestamp, null);
    }
}
```

**Complexité de correction :** Très faible — aucun test à modifier, `GlobalExceptionHandler` n'utilise que les constructeurs.

---

### 5. Codes HTTP des GET — pas de `404` structuré sur liste vide

**État actuel :** `GET /api/employes` retourne `200 OK` avec un tableau vide `[]` si aucun employé n'existe. C'est le comportement standard et correct pour une collection.

**Pas un problème à corriger.** Mentionné pour mémoire : retourner `404` sur une liste vide serait une erreur de conception REST (l'absence d'éléments n'est pas une erreur).

---

## Ordre de correction recommandé pour compléter la normalisation

```
Priorité 1 — Impact sécurité fort
  └── DTOs immutables (records) + retrait validation de l'entité JPA

Priorité 2 — Cohérence API
  └── GET /api/employe?id=X → GET /api/employes/{id}
  └── Unification singulier → pluriel sur toutes les URLs

Priorité 3 — Nettoyage qualité
  └── ErrorResponse → record
```

Les priorités 2 et 3 peuvent être réalisées dans le même commit car l'impact frontend est limité à `api.js` et les tests IT.
