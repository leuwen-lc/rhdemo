# Normalisation REST de l'API Employé

## Vue d'ensemble

Ce document décrit les modifications apportées à l'API REST de gestion des employés
dans le cadre de la branche `evolutions-post-1.1.6`, ainsi que l'écart restant par
rapport à une normalisation REST complète.

---

## Évolution 1 — Séparation des endpoints create/update et correction DELETE

### Contexte

Avant ces modifications, l'API employé présentait trois problèmes de conception :

- `POST /api/employe` traitait à la fois la création et la mise à jour selon la nullité
  de l'`id` dans le corps — couplage implicite, surface d'attaque ouverte.
- `DELETE /api/employe?id=X` passait l'identifiant en query parameter — contraire aux
  conventions REST qui placent l'identifiant de ressource dans le chemin.
- `saveEmploye()` dans le service ne distinguait pas les deux opérations, rendant
  impossible la validation métier spécifique à chaque cas.

### Endpoints après modification

| Verbe | URL | Rôle | Code succès | Avant |
| --- | --- | --- | --- | --- |
| `POST` | `/api/employe` | `MAJ` | `201 Created` | `POST /api/employe` → 200 |
| `PUT` | `/api/employe/{id}` | `MAJ` | `200 OK` | *inexistant* |
| `DELETE` | `/api/employe/{id}` | `MAJ` | `204 No Content` | `DELETE /api/employe?id=X` → 200 |

Les endpoints GET restent inchangés :

| Verbe | URL | Rôle |
| --- | --- | --- |
| `GET` | `/api/employes` | `consult` |
| `GET` | `/api/employes/page` | `consult` |
| `GET` | `/api/employe?id=X` | `consult` |

### Comportements de sécurité ajoutés

**Création (`POST`) :**

- `EmployeService.createEmploye()` force `employe.setId(null)` avant le `save()`,
  quelle que soit la valeur reçue dans le corps.

**Mise à jour (`PUT`) :**

- `EmployeService.updateEmploye(Long id, Employe employe)` vérifie l'existence via
  `existsById()` avant d'écrire — tentative sur un id inexistant → `404 Not Found`.
- L'id est pris exclusivement depuis le chemin (`@PathVariable`).

**Suppression (`DELETE`) :**

- L'id se trouve dans le chemin (`/api/employe/{id}`).
- Code de retour `204 No Content`.

### Fichiers modifiés

| Fichier | Nature du changement |
| --- | --- |
| `service/EmployeService.java` | `saveEmploye()` → `createEmploye()` + `updateEmploye(id, employe)` |
| `controller/EmployeController.java` | Trois endpoints distincts, verbes et codes HTTP corrects |
| `frontend/src/services/api.js` | `saveEmploye()` → `createEmploye()` + `updateEmploye(id, data)` · URL delete corrigée |
| `frontend/src/components/EmployeForm.vue` | Branchement `isEditing` → `createEmploye` ou `updateEmploye` |
| `test/service/EmployeServiceTest.java` | 5 tests : create, createIgnoreId, update, updatePathId, updateNotFound |
| `test/controller/EmployeControllerTest.java` | Tests adaptés aux nouvelles signatures |
| `test/controller/EmployeControllerIT.java` | POST→201, nouveaux tests PUT, DELETE path variable + 204 |

### Résultats des tests

```text
Tests unitaires   : 110 tests, 0 échec
Tests intégration :  56 tests, 0 échec
```

---

## Évolution 2 — DTOs immutables (records Java)

### Contexte

Après l'évolution 1, l'entité JPA `Employe` était encore exposée directement par l'API.
Les annotations `@Entity`, `@Column` cohabitaient avec `@NotBlank`, `@Email`, `@Size`
dans la même classe. Tout champ interne ajouté à l'entité aurait été automatiquement
sérialisé côté client.

La séparation create/update avait également résolu le problème du champ `id` nullable :
`EmployeRequestDTO` n'en a structurellement pas besoin, l'id venant du chemin pour PUT
et de la base pour POST.

### Architecture après modification

La couche service reste entity-centric. La conversion DTO ↔ entité se fait dans le
contrôleur, frontière du contrat API.

```text
Client → EmployeRequestDTO → Controller → Employe → Service → Repository
                                       ← EmployeResponseDTO ←
```

**`EmployeResponseDTO`** — contrat de sortie (tous les GET, POST, PUT) :

```java
public record EmployeResponseDTO(Long id, String prenom, String nom, String mail, String adresse) {
    public static EmployeResponseDTO from(Employe employe) { ... }
}
```

**`EmployeRequestDTO`** — contrat d'entrée (POST et PUT) — sans champ `id` :

```java
public record EmployeRequestDTO(
    @NotBlank @Size(min = 2, max = 50) String prenom,
    @NotBlank @Size(min = 2, max = 50) String nom,
    @NotBlank @Email @Size(max = 100) String mail,
    @Size(max = 200) String adresse
) {
    public Employe toEmploye() { ... }
}
```

### Fichiers créés

| Fichier | Contenu |
| --- | --- |
| `dto/EmployeResponseDTO.java` | Record immuable, méthode `from(Employe)` |
| `dto/EmployeRequestDTO.java` | Record sans `id`, Bean Validation, méthode `toEmploye()` |
| `test/dto/EmployeResponseDTOTest.java` | 7 tests : mapping tous champs, adresse null, id null, equals/hashCode/toString |
| `test/dto/EmployeRequestDTOTest.java` | 16 tests : validation NotBlank/Email/Size, edge cases, `toEmploye()` |

### Fichiers modifiés

| Fichier | Nature du changement |
| --- | --- |
| `controller/EmployeController.java` | Toutes les méthodes reçoivent/retournent des DTOs |
| `test/controller/EmployeControllerTest.java` | Types de retour `EmployeResponseDTO`, stubs `any(Employe.class)` |
| `model/Employe.java` | `@NotBlank`, `@Email`, `@Size` retirés — seuls `@Column` JPA conservés |

### Fichier supprimé

| Fichier | Raison |
| --- | --- |
| `test/model/EmployeValidationTest.java` | Migré vers `test/dto/EmployeRequestDTOTest.java` — tester la validation sur l'entité n'avait plus de sens après retrait des annotations Bean Validation |

### Résultats des tests

```text
Tests unitaires   : 120 tests, 0 échec  (+10 : 7 EmployeResponseDTOTest + 16 EmployeRequestDTOTest - 13 EmployeValidationTest)
Tests intégration :  56 tests, 0 échec
```

---

## Écart restant — plan de normalisation complet

### Priorité 1 — Cohérence singulier/pluriel et GET par path variable

**État actuel :**

```text
GET    /api/employes          ← pluriel (correct)
GET    /api/employes/page     ← pluriel (correct)
GET    /api/employe?id=X      ← singulier + query param  ← à corriger
POST   /api/employe           ← singulier                ← à corriger
PUT    /api/employe/{id}      ← singulier                ← à corriger
DELETE /api/employe/{id}      ← singulier                ← à corriger
```

**Forme cible REST standard :**

```text
GET    /api/employes
GET    /api/employes/page
GET    /api/employes/{id}
POST   /api/employes
PUT    /api/employes/{id}
DELETE /api/employes/{id}
```

Ces deux corrections (singulier → pluriel et query param → path variable sur le GET)
peuvent être réalisées dans le même commit.

**Fichiers impactés :**

- `EmployeController.java` : changer `@RequestParam` en `@PathVariable` sur `getEmploye()`,
  renommer tous les mappings `/api/employe` → `/api/employes`
- `api.js` : `` api.get(`/employes/${id}`) `` au lieu de `api.get('/employe', { params: { id } })`
- `EmployeControllerIT.java` : URLs dans les tests
- `EmployeDelete.vue`, `EmployeModify.vue` : aucun changement (appellent `getEmploye(id)`)
- Tests Selenium : aucun changement (pilotent le navigateur, pas les URLs HTTP)

---

### Priorité 2 — `ErrorResponse` en record

**Problème :** `ErrorResponse` est un POJO mutable avec 4 setters jamais utilisés
(seuls les constructeurs sont appelés dans `GlobalExceptionHandler`).

**Forme cible :**

```java
public record ErrorResponse(
    int status, String message, LocalDateTime timestamp, Map<String, String> errors
) {
    public ErrorResponse(int status, String message, LocalDateTime timestamp) {
        this(status, message, timestamp, null);
    }
}
```

**Fichiers impactés :** `ErrorResponse.java` uniquement. `GlobalExceptionHandler` n'utilise
que les constructeurs — aucune modification nécessaire.

---

### Bilan

| Action | Statut | Effort | Valeur |
| --- | --- | --- | --- |
| Séparation endpoints create/update | Appliqué | — | Sécurité |
| Correction DELETE path variable + 204 | Appliqué | — | Conformité REST |
| DTOs immutables (records) | Appliqué | — | Sécurité + architecture |
| GET path variable + pluriel URLs | Restant | Faible | Cohérence API |
| `ErrorResponse` → record | Restant | Très faible | Qualité code |
