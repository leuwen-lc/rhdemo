# Documentation - Système de Pagination

## Vue d'ensemble

L'application RHDemo implémente un système de pagination côté serveur pour optimiser les performances lors de l'affichage de grandes listes d'employés. La pagination permet de charger uniquement un sous-ensemble de données à la fois, réduisant significativement les temps de chargement et de rendu.

## Architecture

Le système utilise une architecture en 3 couches :

1. **Base de données** : PostgreSQL utilise `LIMIT` et `OFFSET` pour récupérer uniquement les données nécessaires
2. **Backend** : Spring Data JPA gère la pagination via les interfaces `Pageable` et `Page`
3. **Frontend** : Vue.js avec Element Plus affiche les données paginées et gère la navigation

## Structure de l'API

### Endpoint de pagination

```
GET /api/employes/page?page=0&size=20&sort=nom&order=ASC&filterNom=Martin
```

**Paramètres :**
- `page` : Numéro de la page (commence à 0), défaut : 0
- `size` : Nombre d'éléments par page, défaut : 20
- `sort` : Nom de la colonne pour le tri (prenom, nom, mail, adresse), optionnel
- `order` : Direction du tri (`ASC` ou `DESC`), défaut : ASC
- `filterPrenom` : Filtre sur le prénom (recherche partielle, insensible à la casse), optionnel
- `filterNom` : Filtre sur le nom (recherche partielle, insensible à la casse), optionnel
- `filterMail` : Filtre sur l'email (recherche partielle, insensible à la casse), optionnel
- `filterAdresse` : Filtre sur l'adresse (recherche partielle, insensible à la casse), optionnel

### Format de réponse (PagedModel - VIA_DTO)

La réponse utilise le format **PagedModel** avec sérialisation `VIA_DTO` pour garantir une structure JSON stable et conforme aux bonnes pratiques Spring Data.

**Structure :**
```
{
  "content": [ ... ],           // Liste des employés de la page actuelle
  "page": {
    "size": 20,                 // Taille de la page
    "number": 0,                // Numéro de page actuel (base 0)
    "totalElements": 303,       // Nombre total d'employés
    "totalPages": 16            // Nombre total de pages
  }
}
```

**⚠️ Important :** Les métadonnées de pagination sont regroupées dans l'objet `page`, contrairement à l'ancien format où elles étaient à la racine de la réponse.

## Performances

### Impact mesurable

- **Temps de chargement** : ~200ms au lieu de ~2-3s (10x plus rapide)
- **Données transférées** : ~10 KB au lieu de ~150 KB
- **Éléments DOM** : ~100 au lieu de ~1500
- **Temps de rendu** : ~50ms au lieu de ~500ms

### Tailles de page recommandées

- **Par défaut** : 20 éléments (bon compromis performance/UX)
- **Options disponibles** : 10, 20, 50, 100 éléments
- **Maximum conseillé** : 100 éléments pour éviter la dégradation des performances

## Fonctionnalités

### Navigation

- **Numéros de pages** : Cliquables directement
- **Boutons Précédent/Suivant** : Navigation séquentielle
- **Champ "Aller à"** : Saut direct à une page spécifique
- **Sélecteur de taille** : Changement dynamique du nombre d'éléments par page

### Tri des colonnes

Le système de tri permet de trier l'ensemble de la table (pas seulement la page en cours) :

- **Colonnes triables** : Prénom, Nom, Email, Adresse
- **Tri côté serveur** : Exécuté via SQL `ORDER BY` pour des performances optimales
- **Modes de tri** :
  - 1er clic : Tri ascendant (A→Z)
  - 2ème clic : Tri descendant (Z→A)
  - 3ème clic : Annulation du tri
- **Indicateur visuel** : Flèche dans l'entête de colonne indiquant la direction du tri
- **Pagination préservée** : Le tri est maintenu lors du changement de page

**Exemple de requête :**
```
GET /api/employes/page?page=0&size=20&sort=nom&order=ASC
```

### Filtres par colonne

Le système de filtrage permet de rechercher des employés sur l'ensemble de la base de données (pas seulement la page en cours) :

- **Colonnes filtrables** : Prénom, Nom, Email, Adresse
- **Filtrage côté serveur** : Exécuté via JPA Specification (`LOWER(champ) LIKE '%terme%'`)
- **Recherche partielle** : Le terme saisi peut apparaître n'importe où dans la valeur du champ (CONTAINS)
- **Insensible à la casse** : "martin" trouve "Martin", "MARTIN", etc.
- **Filtres combinables** : Plusieurs filtres actifs simultanément sont combinés en AND (intersection)
- **Déclenchement** : Touche Entrée pour valider, bouton croix (clear) pour réinitialiser un filtre
- **Compatible avec le tri** : Les filtres fonctionnent conjointement avec le tri des colonnes
- **Pagination cohérente** : Le total affiché reflète le nombre d'employés filtrés

**Exemples de requêtes :**
```
GET /api/employes/page?filterNom=Martin              → Employés dont le nom contient "Martin"
GET /api/employes/page?filterPrenom=So&filterNom=Du   → Filtres combinés (AND)
GET /api/employes/page?filterMail=example&size=10     → Filtre + pagination
GET /api/employes/page?filterNom=Du&sort=prenom&order=ASC → Filtre + tri
```

### Comportement

- Retour automatique à la page 1 lors d'un changement de taille de page
- Retour automatique à la page 1 lors d'un changement de tri
- Retour automatique à la page 1 lors d'un changement de filtre
- Indicateur de chargement pendant les requêtes
- Affichage du nombre total d'éléments (tenant compte des filtres actifs)
- Gestion des cas limites (0 employé, 1 seul employé, aucun résultat de filtre)

## Sécurité

L'endpoint de pagination est protégé par Spring Security et requiert :
- **Authentification** : Via Keycloak OAuth2/OIDC
- **Autorisation** : Rôle `consult` minimum

## Implémentation technique

### Backend (EmployeController.java)

```java
@GetMapping("/api/employes/page")
@PreAuthorize("hasRole('consult')")
public Page<Employe> getEmployesPage(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size,
        @RequestParam(required = false) String sort,
        @RequestParam(defaultValue = "ASC") String order,
        @RequestParam(required = false) String filterPrenom,
        @RequestParam(required = false) String filterNom,
        @RequestParam(required = false) String filterMail,
        @RequestParam(required = false) String filterAdresse) {

    Pageable pageable;
    if (sort != null && !sort.isEmpty()) {
        Sort.Direction direction = "DESC".equalsIgnoreCase(order)
            ? Sort.Direction.DESC
            : Sort.Direction.ASC;
        pageable = PageRequest.of(page, size, Sort.by(direction, sort));
    } else {
        pageable = PageRequest.of(page, size);
    }

    Specification<Employe> spec = EmployeSpecification.withFilters(
        filterPrenom, filterNom, filterMail, filterAdresse);
    return employeservice.getEmployesPage(spec, pageable);
}
```

### Filtrage dynamique (EmployeSpecification.java)

```java
public static Specification<Employe> withFilters(
        String prenom, String nom, String mail, String adresse) {
    return (root, query, cb) -> {
        List<Predicate> predicates = new ArrayList<>();
        if (prenom != null && !prenom.isBlank()) {
            predicates.add(cb.like(cb.lower(root.get("prenom")),
                "%" + prenom.toLowerCase() + "%"));
        }
        // idem pour nom, mail, adresse...
        return cb.and(predicates.toArray(new Predicate[0]));
    };
}
```

Les valeurs sont passées en paramètres JPA Criteria (pas de concaténation SQL) → **aucun risque d'injection SQL**. Les wildcards `%` sont ajoutées côté backend, le frontend envoie le terme brut.

### Frontend (EmployeList.vue)

**Configuration du tableau avec filtres :**
```vue
<el-table
  :data="employes"
  @sort-change="handleSort"
>
  <el-table-column prop="prenom" sortable="custom">
    <template #header>
      <div>Prénom</div>
      <el-input
        v-model="filterPrenom"
        size="small"
        clearable
        placeholder="Filtrer..."
        data-testid="filter-prenom"
        @keyup.enter="applyFilters"
        @clear="applyFilters"
        @click.stop
      />
    </template>
  </el-table-column>
  <!-- idem pour nom, mail, adresse -->
</el-table>
```

**Gestion du tri et des filtres :**
```javascript
data() {
  return {
    sortField: null,
    sortOrder: 'ASC',
    filterPrenom: '',
    filterNom: '',
    filterMail: '',
    filterAdresse: ''
  };
},
methods: {
  applyFilters() {
    this.currentPage = 1;
    this.fetchEmployes();
  },
  handleSort({ prop, order }) {
    if (order) {
      this.sortField = prop;
      this.sortOrder = order === 'ascending' ? 'ASC' : 'DESC';
    } else {
      this.sortField = null;
      this.sortOrder = 'ASC';
    }
    this.currentPage = 1;
    this.fetchEmployes();
  }
}
```

### API Service (api.js)

```javascript
export function getEmployesPage(page = 0, size = 20, sort = null, order = 'ASC', filters = {}) {
  const params = { page, size };
  if (sort) {
    params.sort = sort;
    params.order = order;
  }
  if (filters.prenom) params.filterPrenom = filters.prenom;
  if (filters.nom) params.filterNom = filters.nom;
  if (filters.mail) params.filterMail = filters.mail;
  if (filters.adresse) params.filterAdresse = filters.adresse;
  return api.get('/employes/page', { params });
}
```

## Choix techniques

### Pourquoi JpaSpecificationExecutor ?

- **Standard Spring Data JPA** pour le filtrage dynamique avec pagination
- S'intègre nativement avec `Pageable` (pagination + tri préservés)
- Gère naturellement les combinaisons de filtres optionnels (0 à 4 filtres actifs)
- Les paramètres sont injectés via l'API Criteria de JPA → **aucun risque d'injection SQL**
- Aucune dépendance Maven supplémentaire (déjà inclus dans `spring-boot-starter-data-jpa`)

### Pourquoi déclenchement sur Entrée (et pas debounce sur saisie) ?

- Plus prévisible pour l'utilisateur : la requête part quand il valide
- Moins de requêtes serveur inutiles (pas de requête à chaque frappe)
- Cohérent avec le pattern Element Plus des filtres de tableau
- Le bouton `clearable` de l'`el-input` déclenche aussi la recherche (via `@clear`) pour réinitialiser le filtre

## Bonnes pratiques

### ✅ Recommandations

- **Conserver l'ancien endpoint** `/api/employes` pour assurer la rétrocompatibilité
- **Utiliser des valeurs par défaut** raisonnables (page=0, size=20)
- **Gérer les erreurs** de pagination (page inexistante, paramètres invalides)
- **Afficher un indicateur** de chargement pendant les requêtes
- **Optimiser les requêtes** en ajoutant des index sur les colonnes fréquemment triées
- **Documenter les breaking changes** lors de modifications du format d'API

### ❌ À éviter

- **Pagination côté client** uniquement (charge inutilement toutes les données)
- **Tailles de page excessives** (> 100 éléments)
- **Ignorer les cas limites** (collection vide, 1 seul élément)
- **Oublier la validation** des paramètres de pagination

## Migration et compatibilité

### Changement du format PageImpl vers PagedModel

**Date** : 22 novembre 2025

**Raison** : Conformité avec les recommandations Spring Data pour une structure JSON stable et documentée.

**Impact** : Breaking change - Les clients doivent accéder aux métadonnées via `response.data.page.*` au lieu de `response.data.*`

**Avantages :**
- ✅ Structure JSON garantie et stable
- ✅ Conforme aux standards Spring Data
- ✅ Suppression des warnings dans les logs
- ✅ Meilleure séparation entre contenu et métadonnées

### Fichiers impactés (pagination, tri, filtres)

- **Backend** :
  - `RhdemoApplication.java` - Annotation `@EnableSpringDataWebSupport`
  - `EmployeController.java` - Paramètres `sort`, `order` et filtres
  - `EmployeService.java` - Surcharge `getEmployesPage(Specification, Pageable)`
  - `EmployeRepository.java` - Extension `JpaSpecificationExecutor<Employe>`
  - `EmployeSpecification.java` - Construction dynamique des filtres JPA
- **Frontend** :
  - `EmployeList.vue` - Pagination, tri et filtres par colonne
  - `api.js` - Paramètres de tri et filtres dans `getEmployesPage()`
- **Tests** :
  - `EmployeControllerIT.java` - Tests pagination, tri et filtres
  - `EmployeServiceTest.java` - Test unitaire `getEmployesPage(Specification, Pageable)`

## Dépendances techniques

### Backend
- Spring Data JPA (inclus dans `spring-boot-starter-data-jpa`) — fournit `Pageable`, `Page`, `JpaSpecificationExecutor`, `Specification`
- Spring Data Web Support pour PagedModel

### Frontend
- Element Plus (composants `el-pagination`, `el-table`, `el-input`)
- Axios pour les requêtes HTTP

## Références

- [Spring Data JPA - Pagination](https://docs.spring.io/spring-data/jpa/docs/current/reference/html/#repositories.special-parameters)
- [Spring Data Web Support](https://docs.spring.io/spring-data/commons/reference/repositories/core-extensions.html#core.web.pageables)
- [Element Plus Pagination](https://element-plus.org/en-US/component/pagination.html)
- [REST API Best Practices - Pagination](https://www.moesif.com/blog/technical/api-design/REST-API-Design-Filtering-Sorting-and-Pagination/)

## Historique des modifications

### Version 3.0.0 - Filtres par colonne côté serveur (12 février 2026)

**Ajout :** Filtres de recherche par colonne sur Prénom, Nom, Email, Adresse

**Nouveautés :**
- Filtrage côté serveur via JPA `Specification` et Criteria API (`LIKE '%terme%'` insensible à la casse)
- Champs de saisie `el-input` dans l'entête de chaque colonne filtrable
- Déclenchement sur touche Entrée et sur bouton clear
- Filtres combinables en AND (intersection des critères)
- Compatible avec la pagination et le tri existants (rétrocompatibilité totale)
- Attributs `data-testid` pour les tests Selenium : `filter-prenom`, `filter-nom`, `filter-mail`, `filter-adresse`
- Sécurité : paramètres injectés via JPA Criteria (pas d'injection SQL)

**Fichiers créés :**
- `EmployeSpecification.java` : Construction dynamique des `Specification<Employe>`

**Fichiers modifiés :**
- `EmployeRepository.java` : Ajout de `JpaSpecificationExecutor<Employe>`
- `EmployeService.java` : Surcharge `getEmployesPage(Specification, Pageable)`
- `EmployeController.java` : 4 nouveaux `@RequestParam` optionnels (filtres)
- `api.js` : Paramètre `filters` dans `getEmployesPage()`
- `EmployeList.vue` : Champs de filtre dans les entêtes de colonnes
- `EmployeControllerIT.java` : 9 nouveaux tests d'intégration (filtres)
- `EmployeServiceTest.java` : 1 nouveau test unitaire (filtrage avec Specification)

### Version 2.1.0 - Tri côté serveur (8 décembre 2025)

**Ajout :** Système de tri global sur l'ensemble de la table

**Nouveautés :**
- Tri côté serveur via Spring Data `Sort` et SQL `ORDER BY`
- Colonnes triables : Prénom, Nom, Email, Adresse
- Interface utilisateur avec `sortable="custom"` sur Element Plus
- 3 modes de tri : ascendant, descendant, annulation
- Tests d'intégration pour le tri

**Fichiers modifiés :**
- `EmployeController.java` : Paramètres `sort` et `order`
- `EmployeList.vue` : Méthode `handleSort()` et état `sortField`/`sortOrder`
- `api.js` : Signature de `getEmployesPage()`
- `EmployeControllerIT.java` : 3 nouveaux tests de tri

### Version 2.0.0 - PagedModel/VIA_DTO (22 novembre 2025)

**Breaking change :** Migration vers PagedModel avec sérialisation VIA_DTO

**Impact :** Les métadonnées de pagination sont désormais dans `response.data.page.*`

---

**Dernière mise à jour** : 12 février 2026
**Version** : 3.0.0 (Filtres par colonne côté serveur)
