# Guide d'utilisation - Navigation

### 🏠 Page d'Accueil (/)
- Menu principal avec accès à toutes les fonctionnalités
- Interface organisée en sections : Consultation, Gestion, et Modification

### 📋 Consultation
1. **Liste complète** (`/employes`) - Voir tous les employés avec actions rapides
2. **Recherche par ID** (`/recherche`) - Trouver un employé spécifique par son identifiant

### ➕ Gestion
1. **Ajout d'employé** (`/ajout`) - Formulaire pour créer un nouvel employé
2. **Suppression par ID** (`/suppression`) - Interface sécurisée pour supprimer un employé avec confirmation

### ✏️ Modification
1. **Modification par ID** (`/modification`) - Rechercher puis modifier un employé existant

## Navigation

- **Barre de navigation globale** : Toujours visible en haut de page (sauf sur l'accueil)
- **Liens de retour** : Chaque page propose un retour vers l'accueil
- **Navigation contextuelle** : Actions rapides disponibles sur chaque carte d'employé

## Interface

- Design moderne avec cartes et icônes
- Responsive (adapté mobile/tablette)
- Messages d'état (chargement, erreurs, succès)
- Confirmations pour les actions critiques (suppression)

## Accès

Intégré dans Spring Boot sur http://localhost:9000/

## Structure des fichiers

```
frontend/src/components/
├── HomeMenu.vue          # Page d'accueil avec menu principal
├── EmployeSearch.vue     # Recherche d'employé par ID
├── EmployeDelete.vue     # Suppression d'employé avec confirmation
├── EmployeModify.vue     # Sélection d'employé à modifier
└── EmployeList.vue       # Liste améliorée avec design moderne
```

## Routes disponibles

- `/` - Menu principal
- `/employes` - Liste complète des employés
- `/recherche` - Recherche par ID
- `/suppression` - Suppression par ID
- `/modification` - Modification par ID
- `/ajout` - Ajout d'un nouvel employé
- `/employe/:id` - Détails d'un employé
- `/edition/:id` - Édition d'un employé

