# Étude — Tests unitaires frontend pour sécuriser les montées de version Renovate

## 1. Contexte et problème

Le frontend Vue.js (`rhDemo/frontend/`) n'a aujourd'hui **aucun test isolé** : la seule validation fonctionnelle vient des tests Selenium (`rhDemoAPITestIHM/`), qui s'exécutent tard dans le pipeline CI, contre l'environnement `ephemere` complet (Keycloak, PostgreSQL, backend réel).

Renovate met à jour `vue`, `vue-router`, `element-plus`, `axios` et `@vue/cli-service` de façon autonome (patch/minor auto-mergés, major derrière le Dependency Dashboard — voir [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md)). Un exemple concret de risque déjà survenu : le commit `283ac00` (`fix(deps): update dependency vue-router to v5 (#172)`) a fait passer `vue-router` en version majeure 5 sans qu'aucun test ne valide le comportement du routage après coup — seule la CI Selenium a servi de filet, plusieurs minutes après le build et sur un périmètre large.

**Objectif de cette étude** : proposer une couche de tests qui détecte les régressions introduites par ces montées de version, sans les deux écueils identifiés :
- **fragilité** : un test qui casse à chaque changement mineur de libellé/style (typiquement un snapshot test ou une assertion sur une classe CSS interne d'Element Plus) génère du bruit et finit ignoré ;
- **duplication** : un test qui revalide ce que Selenium vérifie déjà (parcours OIDC complet, CSRF réel, persistance en base) coûte du temps de maintenance sans apporter d'information supplémentaire.

---

## 2. Ce que chaque couche doit couvrir (répartition des responsabilités)

| Couche | Ce qu'elle valide | Ce qu'elle NE valide PAS |
|---|---|---|
| **Tests unitaires frontend (proposés ici)** | Comportement d'un composant Vue isolé : rendu conditionnel, validation de formulaire, appel du bon endpoint Axios avec les bons paramètres, émission d'événements, navigation router déclenchée | L'authentification Keycloak réelle, le CSRF réel, la persistance BDD, le rendu visuel dans un vrai navigateur |
| **Selenium (`rhDemoAPITestIHM/`)** | Le parcours utilisateur de bout en bout à travers Nginx, Keycloak, le backend et PostgreSQL | Les cas limites de validation ou les branches d'erreur d'un composant pris isolément (trop coûteux à multiplier en E2E) |

La couche unitaire proposée se positionne donc **avant** Selenium dans la pyramide de tests : rapide (secondes), sans navigateur, sans backend — exécutable sur *chaque* PR Renovate touchant le frontend, avant même de déployer `ephemere`.

---

## 3. Choix d'outillage

| Critère | Vitest + @vue/test-utils | Jest + @vue/test-utils |
|---|---|---|
| Compatibilité Vue 3 / Composition API | Native | Nécessite `babel-jest` + config ESM supplémentaire |
| Vitesse | Très rapide (esbuild) | Plus lent (transform Babel) |
| Conflit avec Vue CLI Service 5 (webpack) | Aucun — Vitest exécute les tests indépendamment du build webpack, il n'a pas besoin de `vue.config.js` | Aucun non plus, mais configuration ESM plus verbeuse pour Vue 3 |
| Maintenance | Activement maintenu, écosystème Vite/Vitest = standard actuel Vue 3 | Toujours maintenu mais plus de friction sur ce stack |

**Recommandation : Vitest + `@vue/test-utils` v2**, complété par `@testing-library/vue` pour interroger le DOM par rôle/texte/`data-testid` plutôt que par structure interne des composants — cohérent avec la logique déjà en place pour Selenium (voir [DATA_TESTID_GUIDE.md](DATA_TESTID_GUIDE.md)).

Vitest n'entre pas en conflit avec `vue-cli-service` : c'est un outil de test autonome, il ne remplace ni la commande `serve` ni `build`.

---

## 4. Ce qu'on teste, ce qu'on NE teste PAS

### À tester (comportement observable, stable dans le temps)
- Rendu conditionnel important : message d'erreur affiché si l'API échoue, bouton désactivé si `hasRole()` retourne `false`.
- Règles de validation de formulaire (`rules` d'Element Plus) : champ requis, format email.
- Le bon appel Axios est déclenché avec les bons paramètres (`createEmploye` vs `updateEmploye` selon `isEditing`).
- Navigation déclenchée après une action (`this.$router.push(...)`).
- Émission d'événements personnalisés entre composants.

### À ne PAS tester (source de fragilité ou de duplication)
- **Pas de snapshot tests** : un simple changement de libellé Element Plus après montée de version ferait tout casser sans qu'il y ait de régression réelle.
- **Pas d'assertions sur les classes CSS ou la structure DOM interne** d'Element Plus (`el-form-item__error`, etc.) — cibler les `data-testid` existants.
- **Pas de re-test du parcours Keycloak/CSRF réel** : c'est le rôle de Selenium et des tests d'intégration backend (voir [TESTS_INTEGRATION_SANS_KEYCLOAK.md](TESTS_INTEGRATION_SANS_KEYCLOAK.md)).
- **Pas de test des internes d'Element Plus lui-même** (ce n'est pas notre code).

---

## 5. Stratégie de mock

Le module `services/api.js` centralise tous les appels Axios (voir [frontend/src/services/api.js](../frontend/src/services/api.js)). Dans les tests, ce module est mocké avec `vi.mock('@/services/api')` : on n'appelle jamais un backend réel, on vérifie uniquement que le composant appelle la bonne fonction avec les bons arguments et réagit correctement à la réponse (succès) ou au rejet (erreur) simulés.

Ce point est important vis-à-vis de Renovate : une montée de version d'Axios peut changer la forme des objets d'erreur (`error.response` vs `error.cause`, etc.). Le mock doit reproduire fidèlement la forme réelle des erreurs Axios actuelles pour que le test reste pertinent après upgrade.

---

## 6. Structure de fichiers proposée

```
rhDemo/frontend/
├── src/
│   └── components/...
├── tests/
│   └── unit/
│       ├── EmployeForm.spec.js
│       ├── EmployeList.spec.js
│       ├── EmployeDelete.spec.js
│       ├── EmployeSearch.spec.js
│       └── services/
│           └── api.spec.js
├── vitest.config.js
└── package.json
```

Convention de nommage : `<Composant>.spec.js`, à côté d'un dossier `tests/unit/` séparé de `src/` pour ne pas polluer le build webpack (aucun fichier de test n'est jamais embarqué dans `target/classes/static/`).

---

## 7. Exemple illustratif (EmployeForm.vue)

`EmployeForm.vue` (voir [frontend/src/components/EmployeForm.vue](../frontend/src/components/EmployeForm.vue)) est un bon candidat prioritaire : validation de formulaire, deux branches API (création/modification), gestion d'erreur, navigation différée. Extrait de la forme attendue d'un test (le fichier complet contiendrait plusieurs `it(...)` de ce type) :

```js
it("appelle createEmploye avec les données saisies", async () => {
  const wrapper = mount(EmployeForm, { global: { plugins: [router] } });
  await wrapper.find('[data-testid="employe-prenom-input"] input').setValue("Jean");
  // ... nom, mail
  await wrapper.find('[data-testid="employe-submit-button"]').trigger("click");
  expect(createEmploye).toHaveBeenCalledWith(expect.objectContaining({ prenom: "Jean" }));
});
```

Ce test survivrait à une montée de version d'Element Plus (il ne dépend que du `data-testid` et de l'API du composant), et à une montée de version d'Axios (il vérifie l'appel à la fonction du service, pas la forme interne d'Axios).

---

## 8. Périmètre prioritaire (ordre de mise en œuvre)

| Ordre | Composant / module | Justification | Effort estimé |
|---|---|---|---|
| 1 | `services/api.js` | Point de passage unique de tous les appels réseau ; casse ici = casse partout | Faible |
| 2 | `EmployeForm.vue` | Logique la plus riche (validation, deux branches API, navigation différée) | Moyen |
| 3 | `EmployeList.vue` | Pagination, tri, filtres — logique la plus exposée à une régression `vue-router`/Element Plus table | Moyen |
| 4 | `EmployeDelete.vue` | Confirmation + appel API destructif, criticité métier | Faible |
| 5 | `stores/userStore.js` (`hasRole`) | Utilisé par plusieurs composants pour le contrôle d'accès UI | Faible |
| 6 | `EmployeSearch.vue`, `EmployeModify.vue`, `EmployeDetail.vue`, `HomeMenu.vue`, `router/index.js` | Complète la couverture une fois le socle en place | Variable |

Une v1 limitée aux points 1 à 3 couvre déjà la majorité de la surface de risque réelle (Axios, formulaire, liste/pagination) pour un effort limité.

---

## 9. Intégration technique

### 9.1 Dépendances à ajouter (`frontend/package.json`, `devDependencies`)
`vitest`, `@vue/test-utils`, `@testing-library/vue`, `jsdom` (environnement DOM pour Vitest), `@vitejs/plugin-vue` (nécessaire à Vitest pour compiler les fichiers `.vue`, indépendamment de webpack/Vue CLI Service).

### 9.2 Script npm
Ajouter dans `frontend/package.json` :
```json
"test:unit": "vitest run --reporter=verbose --reporter=junit --outputFile=test-results.xml"
```
Le reporter `junit` produit un rapport exploitable par Jenkins (`junit` step), au même format que Surefire/Failsafe côté backend.

### 9.3 Intégration Maven (`frontend-maven-plugin`)
Dans `pom.xml`, ajouter une exécution `npm run test:unit` entre `npm install` et `npm run build` (bloc `frontend-maven-plugin`, voir configuration actuelle autour de la ligne 261). Un échec de test fait échouer le build Maven au même titre qu'un échec Surefire — cohérent avec le comportement déjà appliqué au backend.

### 9.4 Intégration `Jenkinsfile-CI`
Ajouter une étape (ou un `sh` supplémentaire dans l'étape Build existante, puisque le build Maven inclut déjà npm) qui publie `frontend/test-results.xml` via le step `junit` de Jenkins, à côté des rapports Surefire/Failsafe. Impact temps estimé : quelques secondes à ~1 minute selon le nombre de tests — négligeable sur le budget de 2h du pipeline CI.

### 9.5 Articulation avec le pipeline Renovate
`Jenkinsfile-Renovate` construit déjà chaque PR (build + tests + OWASP Dependency-Check) avant merge automatique (voir [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md)). Comme les tests unitaires frontend seraient exécutés au sein du build Maven standard, ils bénéficient automatiquement du même circuit d'automerge sans modification supplémentaire du pipeline Renovate — c'est le point qui répond directement au besoin initial : une PR Renovate qui casse le comportement d'`EmployeForm.vue` ou de `services/api.js` échouera la CI et restera bloquée en l'état, comme n'importe quelle régression backend aujourd'hui.

---

## 10. Ce que cette couche ne règle pas

- Elle ne couvre pas la couverture SonarQube (le quality gate ≥50 % du projet porte sur le code backend mesuré par JaCoCo — les tests frontend n'y contribuent pas actuellement, une intégration ultérieure d'un rapport de couverture JS dans Sonar resterait à étudier séparément si souhaité).
- Elle ne remplace aucun test Selenium existant : les deux couches restent complémentaires et aucun test Selenium n'a besoin d'être retiré suite à cette mise en place.
- Elle ne teste pas le rendu visuel réel (CSS, responsive) — hors périmètre volontairement, car source de fragilité et déjà hors périmètre de Selenium également.

---

## 11. Synthèse

| Critère demandé | Réponse apportée |
|---|---|
| Peu fragile aux changements mineurs | Ciblage `data-testid` + comportement observable, pas de snapshot, pas d'assertion sur structure interne Element Plus |
| Ne duplique pas Selenium | Mocks Axios, pas de Keycloak/CSRF/BDD réels — périmètre strictement composant isolé |
| Détecte les régressions Renovate | Exécuté sur chaque PR Renovate frontend, avant même le déploiement `ephemere` |
| Compatible avec l'outillage existant | Vitest indépendant de Vue CLI Service/webpack, intégration `frontend-maven-plugin` + `Jenkinsfile-CI` sans changement structurel |
