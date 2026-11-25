# Navigation du frontend

## Préfixe `/front`

Toutes les routes Vue.js sont sous `/front/`, ce qui sépare le frontend (`/front/*`) de l'API backend (`/api/*`) et simplifie les règles du reverse proxy et de Spring Security. La racine `/` redirige vers `/front/`.

La liste des routes et des composants associés fait foi dans [`src/router/index.js`](src/router/index.js) ; elle n'est pas recopiée ici.

## Organisation des écrans

- **Accueil** (`HomeMenu`) : menu principal, en trois sections : consultation (liste, recherche par identifiant), gestion (ajout, suppression) et modification.
- **En-tête** (`App.vue`) : nom et profil de l'utilisateur connecté, bouton de déconnexion.
- **Écrans métier** : un composant par action dans [`src/components/`](src/components/). Chaque écran propose un retour vers l'accueil, et la suppression demande confirmation.

Les appels HTTP passent par [`src/services/`](src/services/), et tout élément interactif porte un `data-testid` ([DATA_TESTID_GUIDE.md](../docs/DATA_TESTID_GUIDE.md)).

## Accès

Ports et URLs selon l'environnement : [ENVIRONMENTS.md](../infra/ENVIRONMENTS.md). Le serveur de développement Vite est configuré dans [`vite.config.js`](vite.config.js).
