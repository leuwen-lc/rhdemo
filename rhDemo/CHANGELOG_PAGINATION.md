# Changement de structure de pagination API

## Date : 2025-11-22

## Modification

Activation du mode `VIA_DTO` pour la sérialisation des pages Spring Data afin d'avoir une structure JSON stable.

## Impact sur l'API

### Structure AVANT (PageImpl)

```json
GET /api/employes/page?page=0&size=20

{
  "content": [
    {
      "id": 1,
      "prenom": "Laurent",
      "nom": "Dupont",
      ...
    }
  ],
  "totalElements": 4,
  "totalPages": 1,
  "size": 20,
  "number": 0,
  "first": true,
  "last": true,
  "empty": false
}
```

### Structure APRÈS (PagedModel)

```json
GET /api/employes/page?page=0&size=20

{
  "content": [
    {
      "id": 1,
      "prenom": "Laurent",
      "nom": "Dupont",
      ...
    }
  ],
  "page": {
    "size": 20,
    "number": 0,
    "totalElements": 4,
    "totalPages": 1
  }
}
```

## Changements requis pour les clients

### Frontend Vue.js

**Avant :**
```javascript
const totalElements = response.data.totalElements;
const pageSize = response.data.size;
const pageNumber = response.data.number;
```

**Après :**
```javascript
const totalElements = response.data.page.totalElements;
const pageSize = response.data.page.size;
const pageNumber = response.data.page.number;
```

### Tests Backend

**Avant :**
```java
.andExpect(jsonPath("$.totalElements").value(4))
.andExpect(jsonPath("$.size").value(20))
```

**Après :**
```java
.andExpect(jsonPath("$.page.totalElements").value(4))
.andExpect(jsonPath("$.page.size").value(20))
```

## Avantages

✅ **Structure JSON stable et documentée** : Garantie de compatibilité future
✅ **Conforme aux bonnes pratiques Spring Data** : Recommandation officielle
✅ **Suppression du warning** : Logs propres
✅ **Meilleure séparation** : Métadonnées de pagination séparées du contenu

## Fichiers modifiés

- Backend : `RhdemoApplication.java` - Ajout annotation `@EnableSpringDataWebSupport`
- Frontend : `EmployeList.vue` - Accès à `response.data.page.totalElements`
- Tests : `EmployeControllerIT.java` - Mise à jour des assertions JSON

## Compatibilité

⚠️ **Breaking change** : Les clients existants doivent être mis à jour pour utiliser `response.data.page.*` au lieu de `response.data.*`

## Référence

Documentation Spring Data : https://docs.spring.io/spring-data/commons/reference/repositories/core-extensions.html#core.web.pageables
