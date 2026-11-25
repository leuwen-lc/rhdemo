---
statut: historique
verifie_le: 2026-11-06
sources:
  - rhDemo/frontend/package.json
  - rhDemo/frontend/vite.config.js
  - rhDemo/frontend/index.html
  - rhDemo/pom.xml
---

# Migration de Vue CLI vers Vite

> **Réalisée le 2026-11-06** sur la branche `evolutions-post-1.1.10` (Vite 8, `@vitejs/plugin-vue` 6). Convention Vite retenue : les assets sont dans `assets/` (pas de `assetsDir`). Ce document est figé : il garde l'étude préalable. Les sections ci-dessous décrivent l'état avant migration. Le résultat tient dans `frontend/vite.config.js`.

**Bilan** : build du bundle en moins d'une seconde (`vite build`), arbre npm ramené de 746 à 151 paquets, `npm audit` sans alerte, 21 suppressions ODC devenues sans objet retirées de `owasp-suppressions.xml` (restent DOMPurify et deux entrées Spring Security), avis correspondants de `SECURITY_ADVISORIES.md` clos, `overrides` `nanoid` et pin `source-map-js` supprimés, `BROWSERSLIST_IGNORE_OLD_DATA` retiré du POM. `/assets/**` est servi par le gestionnaire statique par défaut de Spring Boot (aucune modification de `WebMvcConfig`). Reste à valider sur ephemere : parcours Selenium, ZAP et console CSP.

## 1. Constat

Le frontend est construit par `@vue/cli-service` 5 (webpack 5), en maintenance seule : le projet Vue recommande Vite. L'application est petite (7 composants, aucun `require`, aucune variable `VUE_APP_*`), donc la migration est peu risquée.

| Élément actuel | Fichier |
| --- | --- |
| Scripts `serve` et `build` via `vue-cli-service` | `frontend/package.json` |
| Dev server port 8081, proxy `/api` vers `localhost:9000`, pas de source map, titre de page | `frontend/vue.config.js` |
| Template HTML avec `<script src="/js/error-handler.js">` et `/css/loading.css` (externalisés pour la CSP) | `frontend/public/index.html` |
| `npm ci` puis `npm run build` dans `frontend-maven-plugin`, puis copie de `frontend/dist` vers `static` par `maven-resources-plugin` | `pom.xml` |
| `BROWSERSLIST_IGNORE_OLD_DATA=1` (silence caniuse-lite sous `mvn -q`) | `pom.xml` |

Le module Maven ne dépend de Vue CLI que par deux choses : la commande `npm run build` et le dossier de sortie `frontend/dist`. Ces deux contrats peuvent rester identiques.

## 2. Impact sur le build Maven

**Ce qui ne change pas** : `frontend-maven-plugin` (Node et npm épinglés, `npm ci`, `npm run build`), la copie `frontend/dist` vers `static`, le `Dockerfile` (il copie `frontend/` et lance Maven), l'agent Jenkins, `Jenkinsfile-Renovate` (qui surveille `package.json` et `package-lock.json`). Node 24 satisfait l'exigence de Vite (Node 20.19+ ou 22.12+ pour les versions récentes).

**Ce qui change dans `pom.xml`** : uniquement la suppression de la variable `BROWSERSLIST_IGNORE_OLD_DATA` et de son commentaire. Vite n'utilise ni autoprefixer ni browserslist par défaut (cible esbuild).

**Gains attendus** :

- Build plus rapide (esbuild/Rollup au lieu de webpack et babel), donc `mvnw verify` plus court en CI.
- Arbre npm réduit : environ 746 paquets aujourd'hui (`INVENTAIRE_COMPOSANTS_OPEN_SOURCE.md`), dont l'essentiel est l'outillage webpack, babel et `webpack-dev-server`. Vite en apporte quelques dizaines.
- Sécurité : disparition de la source récurrente de CVE devDependencies relevées dans `fixcve-audit.md` (`webpack-dev-server`, `webpack-dev-middleware`, `serialize-javascript`, `minimatch`, `braces`, `proxy-addr` via express, `postcss` 7, `webpack-chain`, `rimraf`, `glob`). Les entrées correspondantes de `owasp-suppressions.xml` et les `overrides` de `package.json` (`nanoid`) deviennent à réévaluer.
- Dépendance directe en moins à surveiller : `source-map-js` (pin de contournement).

## 3. Travaux nécessaires

1. **Dépendances** : retirer `@vue/cli-service` et `source-map-js`, ajouter `vite` et `@vitejs/plugin-vue` (devDependencies). Ajouter `"type": "module"` si on veut un `vite.config.js` en ESM.
2. **Scripts** : `"serve"` devient `vite` (garder un alias `serve` pour la doc et `.github/copilot-instructions.md`), `"build"` devient `vite build`.
3. **`vite.config.js`** (remplace `vue.config.js`) :
   - plugin `vue()` ;
   - `server.port: 8081` et `server.proxy['/api']` vers `http://localhost:9000` avec `changeOrigin: true` ;
   - `build.outDir: 'dist'` (valeur par défaut, à ne pas changer pour ne pas toucher le POM) ;
   - `build.sourcemap: false` (défaut) ;
   - `build.chunkSizeWarningLimit` relevé, ou `manualChunks` pour isoler `element-plus` (l'import global `app.use(ElementPlus)` produit un gros bundle).
4. **`index.html`** : le déplacer de `frontend/public/` à la racine `frontend/`, remplacer `<title>` (le titre venait de `pages.index.title`, il est déjà en dur dans le fichier) et ajouter `<script type="module" src="/src/main.js"></script>`. Vite injecte lui-même le script en production.
5. **Fichiers de `public/`** : `js/error-handler.js`, `css/loading.css` et les favicons restent dans `public/` et sont copiés tels quels dans `dist/`. Vite avertit que `error-handler.js` (script classique) n'est pas traité : sans conséquence, c'est voulu pour la CSP.
6. **Imports** : aucun alias `@/` ni `require` dans `src/`, rien à convertir. Les imports `.vue` ont déjà leur extension, ce que Vite exige.
7. **Documentation** : `GUIDE_NAVIGATION.md`, `INVENTAIRE_COMPOSANTS_OPEN_SOURCE.md` (ligne « Vue CLI »), `PIPELINES_CI_CD.md` si elle cite webpack, `.github/copilot-instructions.md`, puis `index.md` et `log.md`.

## 4. Points d'attention

| Sujet | Risque | Vérification |
| --- | --- | --- |
| **CSP** (`script-src 'self'`, voir `CspPolicyBuilder.java`) | Faible : Vite produit des `<script type="module" src>` et du CSS extrait, sans inline. Le polyfill `modulepreload` est dans le JS, pas dans le HTML | Charger l'application derrière la CSP réelle (ephemere) et lire la console |
| **Répertoire de sortie des assets** | Vite écrit dans `dist/assets/` (webpack écrivait `dist/js` et `dist/css`). `WebMvcConfig` ne mappe que `/js`, `/css`, `/img`, `/fonts`, mais le gestionnaire statique par défaut de Spring Boot sert `classpath:/static/**`, donc `/assets/**` doit passer. Collision avec `public/js` exclue (dossiers distincts) | `curl` sur `/assets/*.js` en profil dev et dans l'image. Sinon fixer `build.assetsDir: 'js'` (rend les chemins identiques à aujourd'hui) |
| **Noms de fichiers hachés** | `chunk-vendors.<hash>.js` devient `assets/index-<hash>.js` | Chercher `chunk-vendors` dans `rhDemoAPITestIHM/`, la config ZAP, Nginx et Helm |
| **Dev local** | Le proxy `/api` couvre l'API, mais le flux OAuth2 (BFF, redirections Keycloak, cookie de session, CSRF) doit être revérifié depuis le port 8081 | Parcours de connexion complet en `dev` |
| **Cible navigateurs** | Vite 5+ vise des navigateurs récents (ES modules natifs). Acceptable pour une application interne | `build.target` si besoin |
| **Version de Vite** | La dernière majeure de Vite et son compagnon `@vitejs/plugin-vue` doivent être compatibles avec `vue` 3 et la version de Node épinglée | Lire les notes de version au moment du chantier |
| **Renovate** | Les montées de Vite arrivent par PR npm ; pas de nouvelle règle nécessaire | Aucune |
| **Tests Selenium** | Les `data-testid` ne bougent pas, donc pas d'impact attendu | Lancer la suite `rhDemoAPITestIHM` sur ephemere |

## 5. Lien avec les tests unitaires frontend

[TESTS_FRONTEND_UNITAIRES.md](TESTS_FRONTEND_UNITAIRES.md) étudie des tests unitaires. Après la migration, **Vitest** (même configuration que Vite, aucun transformeur supplémentaire) devient le choix naturel, ce qui simplifie cette étude : il est préférable de migrer vers Vite avant d'introduire les tests.

## 6. Plan et effort

Effort estimé : une demi-journée de travail, sur une branche dédiée.

1. Branche, remplacement des dépendances, `vite.config.js`, `index.html`, scripts.
2. `./mvnw clean package` en local, contrôle du contenu de `target/classes/static`.
3. `npm run serve` : parcours complet (connexion, CRUD, recherche, suppression).
4. Pipeline CI complet sur ephemere : Selenium, ZAP, scan CSP.
5. Nettoyage de `owasp-suppressions.xml` et des `overrides`, après un `fixcve` ou un scan ODC propre.
6. Mise à jour de la documentation, puis reclassement de ce document en `historique`.

**Retour arrière** : trivial, tout tient dans `frontend/` et une ligne du POM.

## 7. Recommandation

Migrer. Le gain de sécurité (suppression de la chaîne webpack, source de la plupart des CVE devDependencies traitées par fixcve) et de maintenance justifie le chantier ; le risque est borné par des contrats Maven inchangés (`npm run build`, `frontend/dist`). La décision à prendre est secondaire : conserver `dist/js` et `dist/css` via `assetsDir` (changement minimal) ou accepter `assets/` (convention Vite).
