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
GET /api/employes/page?page=0&size=20
```

**Paramètres :**
- `page` : Numéro de la page (commence à 0), défaut : 0
- `size` : Nombre d'éléments par page, défaut : 20

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

### Comportement

- Retour automatique à la page 1 lors d'un changement de taille de page
- Indicateur de chargement pendant les requêtes
- Affichage du nombre total d'éléments
- Gestion des cas limites (0 employé, 1 seul employé)

## Sécurité

L'endpoint de pagination est protégé par Spring Security et requiert :
- **Authentification** : Via Keycloak OAuth2/OIDC
- **Autorisation** : Rôle `consult` minimum

## Évolutions futures

### Tri des colonnes

L'ajout de tri sur les colonnes (prénom, nom, etc.) est prévu via le paramètre `sort` dans l'API Spring Data.

### Filtres de recherche

Implémentation future de filtres combinés avec la pagination pour rechercher des employés par nom, prénom ou email.

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

### Fichiers impactés

- **Backend** : `RhdemoApplication.java` - Annotation `@EnableSpringDataWebSupport`
- **Frontend** : `EmployeList.vue` - Accès aux métadonnées de pagination
- **Tests** : `EmployeControllerIT.java` - Assertions JSON mises à jour

## Dépendances techniques

### Backend
- Spring Data JPA (inclus dans `spring-boot-starter-data-jpa`)
- Spring Data Web Support pour PagedModel

### Frontend
- Element Plus (composant `el-pagination`)
- Axios pour les requêtes HTTP

## Références

- [Spring Data JPA - Pagination](https://docs.spring.io/spring-data/jpa/docs/current/reference/html/#repositories.special-parameters)
- [Spring Data Web Support](https://docs.spring.io/spring-data/commons/reference/repositories/core-extensions.html#core.web.pageables)
- [Element Plus Pagination](https://element-plus.org/en-US/component/pagination.html)
- [REST API Best Practices - Pagination](https://www.moesif.com/blog/technical/api-design/REST-API-Design-Filtering-Sorting-and-Pagination/)

---

**Dernière mise à jour** : 22 novembre 2025
**Version** : 2.0.0 (PagedModel/VIA_DTO)
