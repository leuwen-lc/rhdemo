---
statut: proposition
verifie_le: 2026-11-25
sources:
  - rhDemo/scripts/fixcve_lib/
  - rhDemo/scripts/fixcve-auto-poll.sh
  - rhDemo/scripts/fixcve-detect.py
  - rhDemo/scripts/fixcve-validate-json.py
---

# fixcve-auto : isoler les règles métier

Étude du 2026-11-25. Elle fait suite à [FIXCVE_AUTO_REFONTE.md](FIXCVE_AUTO_REFONTE.md), dont les éléments F, G et H ne sont pas faits. Fonctionnement actuel : [FIXCVE_AUTO.md](../FIXCVE_AUTO.md). Incidents à l'origine des garde-fous : [FIXCVE_AUTO_INCIDENTS.md](../FIXCVE_AUTO_INCIDENTS.md).

**Constat en une phrase** : la *décision* sur un finding est déjà isolée (`fixcve_lib/policy.py`, testée par `tests/test_policy.py`). Ce qui s'est dispersé au fil des incidents, ce sont **les notions qui alimentent cette décision** (de quel type de composant s'agit-il ?) et **les règles de cycle** (quand réessayer, quand s'arrêter), écrites en Bash.

## 1. Inventaire des règles métier et de leur emplacement

| Règle | Où elle vit aujourd'hui | Problème |
| --- | --- | --- |
| Table de décision (upgrade, critère A, critère B, blocage, transitoire) | `policy.py` `classify()` | Aucun : bien isolée, à garder comme modèle |
| Seuil CVSS 9.0 | `policy.py` (`CVSS_BLOCKING`), puis en dur dans `fixcve-validate-json.py`, `outcomes.py`, `advisories.py` (texte) | 4 copies ; changer le seuil oublierait le validateur |
| Liste des images surveillées | `fixcve-detect.py` (`TRIVY_IMAGES`), `fixcve-validate-json.py` (`IMAGES`, avec un commentaire « doit rester synchronisé »), `registry.py` (dépôts) | Synchronisation manuelle |
| **Type de composant** (dépendance Maven du projet, dépendance npm du projet, paquet système d'une image tierce, jar embarqué dans une image tierce, lib JS embarquée dans un jar) | Recalculé partout par combinaison de `image != "rhdemo-app"` et `ecosystem == ...` : `resolve.py`, `apply.py` (4 fois), `verify.py`, `fixcve-validate-json.py`, `suppressions.py` (détection de « embarqu » dans un commentaire), `policy.py` | Notion centrale jamais nommée ; c'est elle qui a produit l'incident du build #812 (jar keycloak classé « maven du projet ») |
| Où et comment corriger (pom, package.json/overrides, digest d'image, `.trivyignore.yaml`, suppressions ODC) | `apply.py` + `edits.py` | Le choix de la cible dépend du type de composant, recalculé localement |
| Qui peut être réévalué automatiquement (suppressions temporaires) | `resolve.py` `reverify_pending` | Exclusions (jar embarqué, lib JS dans un jar) codées en `continue` |
| Repli après une montée impossible | `policy.py` `downgrade_failed_upgrade()` | Bien placé, mais reconstruit un finding à la main |
| Règles de cycle : 2 rollbacks, 2 échecs pré-push, 2 push « no action » → halte ; blocage revu toutes les 48 h ; transitoire 1 h × 3 | `fixcve-auto-poll.sh` (constantes en tête, logique répartie sur ~1 000 lignes, trois mémoires `blocked_confirmed`, `no_action_confirmed`, compteurs) | Non testable unitairement, trois variantes du même mécanisme « même cause, même source » |

## 2. Propositions

### P1. Nommer le type de composant — effort S à M, gain le plus fort

Calculer **une seule fois**, dans `fixcve-detect.py`, un champ `component_kind` porté par chaque finding :

| Valeur | Aujourd'hui |
| --- | --- |
| `project_maven` | `image == "rhdemo-app"` et `ecosystem == "maven"` |
| `project_npm` | `image == "rhdemo-app"` et `ecosystem == "npm"` |
| `image_os` | image tierce, paquet système |
| `image_embedded_jar` | image tierce, `ecosystem == "maven"` |
| `jar_embedded_js` | `pkg:javascript` (RetireJS) |

Puis remplacer chaque test `image != "rhdemo-app"` / `ecosystem ==` par un test sur ce champ, ou mieux par une table de capacités unique :

```python
KINDS = {
    "project_maven":      Kind(fix_target="pom",          reverifiable=True,  criterion_a="maven_scope"),
    "image_embedded_jar": Kind(fix_target="image_digest", reverifiable=False, criterion_a=None),
    ...
}
```

Le validateur (`fixcve-validate-json.py`) vérifie la cohérence `component_kind` / `ecosystem` / `image` : c'est le garde-fou qui aurait arrêté le build #812 à la source. Les anciens fichiers de cycle archivés n'ont pas le champ : le calculer à la lecture s'il manque.

### P2. Un module de configuration unique — effort S

`fixcve_lib/rules.py` (ou un `fixcve-rules.yaml` lu par Python) regroupe : seuil CVSS, liste des images et leurs dépôts (fusion de `TRIVY_IMAGES`, `IMAGES` et `registry.IMAGES`), table `KINDS` de P1, constantes de cycle. Tous les autres modules importent ; plus aucun littéral `9.0` ni `"rhdemo-app"` ailleurs. Un test vérifie l'absence de ces littéraux hors du module (simple `grep` dans `run-all.sh`).

Choix recommandé : **module Python** plutôt que YAML. Les règles contiennent des prédicats (critère A) qu'un YAML exprimerait mal, et un module évite un analyseur de plus.

### P3. Sortir les règles de cycle du Bash — effort M

C'est l'élément G de l'étude précédente, recentré sur les règles. Créer `fixcve_lib/cycle.py` avec une **fonction pure** :

```text
decide_cycle(state, observation, now) -> (actions, new_state)
```

- `observation` : résultat du build observé (succès, stage en échec, résultat de detect/classify, sha source) ;
- `actions` : liste déclarative (`skip`, `run_remediation`, `rollback`, `halt{raison}`, `notify{texte}`, `audit{événement}`) ;
- une seule mémoire « même cause » `{clé, source_sha, depuis, recheck, tentatives}` remplace `blocked_confirmed`, `no_action_confirmed` et le compteur transitoire.

Le Bash ne fait plus qu'**exécuter** : appels Jenkins, git, écriture d'état, sous `flock`. Il appelle `fixcve-cycle.py decide` et applique les actions. Chaque incident du registre lié à la boucle (#772/#774, #796/#797, #799-#802, #752/#753) devient un test unitaire de `decide_cycle`, sans Jenkins. Aujourd'hui, le poller n'est contrôlé que par `bash -n` (`tests/run-all.sh`) et par le paramètre DRY_RUN du job `RHDemo-FixCVE` : il n'a aucun test de comportement.

L'outil `fixcve-ctl` (élément F) devient alors trivial : il manipule le même `state` par les mêmes fonctions.

### P4. Rendre `classify()` indépendant de la forme des fichiers — effort S

`downgrade_failed_upgrade()` reconstruit un faux finding et un faux lookup pour rappeler `classify()`. Séparer `classify()` en deux : une fonction `decide(kind, fix_status, cvss, vector, scopes, dev_only) -> (action, critère)` sans dictionnaires, et l'habillage actuel. Le repli appelle directement `decide(..., fix_status="no_fix_available")`. Les tests de politique deviennent une table (paramètres → décision attendue), lisible comme la table de décision de la doc.

### P5. Ce qu'on ne propose pas

- **Moteur de règles** (Drools, json-logic, etc.) : disproportionné pour une dizaine de règles, et ajoute une dépendance à la chaîne de remédiation de sécurité.
- **Portage complet du poller en Python** comme préalable : le gain principal vient de P3. L'option est évaluée à la section 3.
- **Fusion du journal** (élément H) : indépendante de l'isolation des règles, à traiter séparément.

## 3. Option : réécriture complète en Python

Variante de P3 : remplacer aussi l'exécution, donc `fixcve-auto-poll.sh` (~1 000 lignes), `fixcve-state.sh` et `fixcve-git-sync.sh`, par un programme Python unique (`fixcve-auto.py`) qui s'appuie sur `fixcve_lib`.

### 3.1 Périmètre

| Partie Bash actuelle | Équivalent Python | Difficulté |
| --- | --- | --- |
| Lecture et écriture de `state.json` (~40 appels `jq`, `state_set`) | dataclass `State` + écriture atomique (fichier temporaire puis `os.replace`) | Faible ; gain net de lisibilité |
| Verrou `flock` sur le descripteur 9 | `fcntl.flock` | Faible |
| API Jenkins (`curl_jenkins`, `fetch_jenkins_json`, `--globoff`, retentatives) | `urllib.request` (bibliothèque standard, pas de nouvelle dépendance), retentatives explicites | Moyenne : refaire les garde-fous de l'incident #752/#753 |
| Git : commit, push, `GIT_ASKPASS`, synchronisation (~37 commandes) | `subprocess.run([...])` avec liste d'arguments, `GIT_ASKPASS` conservé | Moyenne : c'est la partie la plus sensible (push automatique sur le dépôt) |
| Appels des étapes `fixcve-detect.py`, `-resolve`, `-classify`, `-apply`, `-verify` et lecture de leurs lignes `FIXCVE_*_RESULT` | Appels de fonctions directs ; les scripts CLI restent pour le skill `/fixcve` | Faible ; supprime l'analyse de texte (`result_line`) |
| Machine à états (halte, rollback, no action, blocage, transitoire) | `decide_cycle()` de P3 | Déjà couvert par P3 |
| Journal `fixcve-audit.jsonl`, notifications | module `audit` unique (élément G : `audit_event`) | Faible |

### 3.2 Bénéfices

- **Testabilité complète** : avec des faux pour Jenkins et git, un cycle entier se rejoue dans `run-all.sh`, ce qui couvre l'exécution (ordre commit, push, écriture d'état), pas seulement la décision. C'est le seul moyen d'obtenir des tests de comportement du poller.
- **Un seul langage** pour toute la procédure : plus de frontière texte entre Bash et Python, plus de valeurs JSON relues par `jq` avec un défaut différent à chaque endroit.
- **Erreurs explicites** : exceptions typées au lieu de `set -e` combiné à des `|| true`, une cause fréquente des comportements silencieux relevés dans le registre d'incidents.
- **Sécurité** : `subprocess` avec liste d'arguments supprime les risques de découpage et d'expansion du shell ; les secrets restent en variables d'environnement, jamais en arguments (invariant du projet) : à vérifier par un test.
- Rend triviaux F (`fixcve-ctl`), G et H.

### 3.3 Coûts et risques

- **Effort L** (estimation : 1 500 à 2 000 lignes Python avec tests, contre ~1 150 lignes Bash remplacées). Environ deux à trois fois P3 seul.
- **Perte de la mise au point** : chaque bloc Bash encode un incident (commentaires #752, #772, #796, #799, #812…). Une réécriture peut en perdre un. Parade : chaque entrée de [FIXCVE_AUTO_INCIDENTS.md](../FIXCVE_AUTO_INCIDENTS.md) qui concerne le poller devient un test **avant** la réécriture.
- **Bascule** : le job pousse sur le dépôt sans validation humaine. Il faut une période en parallèle : l'ancien poller reste en production, le nouveau tourne en DRY_RUN sur les mêmes builds et l'on compare décisions et états. On bascule une fois les résultats identiques sur une série de builds réels (proposition : 2 semaines ou 20 cycles).
- **Format de `state.json`** : conserver le format actuel ou fournir une migration lue au démarrage ; même chose pour les anciens événements du journal (append-only).
- **Environnement** : l'agent Jenkins `fixcve` a déjà Python 3 (les étapes y tournent) ; aucune dépendance externe n'est nécessaire, donc pas de nouvelle surface de chaîne d'approvisionnement ni de ligne Renovate.
- **Points de contact inchangés à conserver** : `Jenkinsfile-FixCVE` appelle `fixcve-state.sh` (garder ce nom comme simple lanceur, ou modifier le Jenkinsfile), paramètres `ACTION` / `REPLAY` / `DRY_RUN`, `trusted.sha256` de `fixcve-install.sh` à mettre à jour avec les nouveaux fichiers.
- **Quality gate SonarQube** : `rhDemo/scripts/` n'est pas dans le périmètre de `sonar-project.properties` ; le nouveau code n'y est donc pas soumis, sauf décision de l'y ajouter.

### 3.4 Recommandation

La réécriture complète n'est pas un préalable, mais devient raisonnable **après P3** : une fois les règles de cycle sorties et testées, ce qui reste en Bash n'est que de l'exécution (Jenkins, git, état), et le portage se fait module par module, au risque le plus faible. La faire d'emblée cumule deux changements risqués (règles et exécution) sur un composant qui pousse seul sur le dépôt.

Ordre proposé si elle est retenue : P2, P1, P4, P3, puis portage par étapes : état et verrou, puis audit et notifications, puis Jenkins, puis git en dernier ; enfin fonctionnement en parallèle en DRY_RUN avant la bascule.

## 4. Option : réécriture complète en Java

Hypothèse : réécrire **toute** la procédure en Java 25, comme le backend. Pour harmoniser vraiment, il faut remplacer les deux langages actuels : le Bash du poller et tout le Python (`fixcve-*.py` et `fixcve_lib/`, ~3 500 lignes, plus ~1 300 lignes de tests). Ne réécrire que le poller en Java donnerait trois langages au lieu de deux.

### 4.1 Forme possible

- **Module Maven séparé** (`rhDemo/fixcve/` ou un projet à part comme `rhDemoInitKeycloak/`), **hors du jar de l'application** : l'outil ne doit pas finir dans l'image `rhdemo-app`, ni ajouter de surface à l'application.
- Exécutable `fixcve.jar` avec des sous-commandes (`poll`, `detect`, `resolve`, `classify`, `apply`, `verify`, `ctl`), appelé par `Jenkinsfile-FixCVE` et par le skill `/fixcve`.
- Règles : `sealed interface ComponentKind` + `record` par nature de composant, `switch` exhaustif vérifié par le compilateur. C'est la forme la plus solide de P1 : oublier un cas devient une erreur de compilation.
- L'agent Jenkins `fixcve` a déjà Temurin 25 (`infra/jenkins-docker/Dockerfile.agent`) et Maven : rien à installer.

### 4.2 Bénéfices

- **Un seul langage dans le projet** pour le code maintenu, et les mêmes outils : JUnit, Maven, SonarQube, revue `/code-review` habituelle.
- **Typage statique** des fichiers de cycle (`detected.json`, `lookup.json`, `plan.json`) par des `record` : une partie des contrôles de `fixcve-validate-json.py` (362 lignes) devient structurelle.
- **Quality gate** : le module peut entrer dans le périmètre SonarQube (aujourd'hui `sonar.sources=src/main/java` seulement), avec couverture mesurée.
- Mêmes gains de testabilité que la réécriture Python (section 3.2).

### 4.3 Coûts et risques propres à Java

- **Effort XL** : ~6 000 à 8 000 lignes Java avec tests (Bash + Python + tests actuels, en Java plus verbeux), environ 2 à 3 fois la réécriture Python. Aucun code existant n'est réutilisé, contrairement à Python où `fixcve_lib` reste.
- **Dépendances** : la bibliothèque standard Java ne lit pas le JSON. Il faut Jackson (déjà connu du backend), et sans doute SnakeYAML pour `.trivyignore.yaml` et une bibliothèque XML ou le DOM du JDK pour `pom.xml` et les suppressions Dependency-Check. Le Python actuel n'a **aucune** dépendance externe.
- **Circularité** : ces dépendances seront elles-mêmes scannées. Une CVE critique dans Jackson ou SnakeYAML pourrait bloquer la CI que l'outil est censé réparer, et l'outil devrait alors se corriger lui-même. Parade : versions gérées par Renovate, et un test qui vérifie que fixcve sait monter ses propres dépendances.
- **Fidélité des éditions** : `edits.py` modifie `pom.xml`, `package.json` et `.trivyignore.yaml` **en place**, en préservant la mise en forme et les commentaires (diff minimal dans le commit). Un parseur Java qui relit puis réécrit le fichier perd cette mise en forme ; il faudrait garder des éditions textuelles ciblées, comme aujourd'hui, ce qui réduit l'intérêt du typage pour cette partie.
- **Démarrage** : la JVM ajoute ~0,5 à 1 s par appel ; négligeable pour un job déclenché à chaque fin de CI, mais le skill interactif `/fixcve` enchaîne plusieurs appels : prévoir une seule invocation.
- **Chaîne de confiance** : `trusted.sha256` épingle aujourd'hui des scripts lisibles. Avec un jar, il faut épingler le jar construit (ou le construire depuis les sources dans le job), et un incident se diagnostique moins vite qu'en lisant un script sur l'agent.
- **Bascule et compatibilité** : mêmes exigences qu'en section 3.3 (incidents en tests d'abord, fonctionnement en parallèle en DRY_RUN, formats de `state.json` et du journal conservés), sur un périmètre beaucoup plus large puisque tout change à la fois.

### 4.4 Comparaison

| Critère | P1-P4 seuls | Réécriture Python | Réécriture Java |
| --- | --- | --- | --- |
| Effort | M | L | XL |
| Code existant réutilisé | Tout | `fixcve_lib` | Rien |
| Dépendances externes ajoutées | 0 | 0 | 2 à 3 |
| Tests du poller | Décision seulement | Cycle complet | Cycle complet |
| Harmonisation avec l'application | Non | Non | Oui |
| Analyse SonarQube possible | Non | Non (hors périmètre) | Oui |
| Risque de bascule | Faible | Moyen | Élevé |

### 4.5 Recommandation

L'harmonisation avec l'application est un vrai argument pour un projet école (une seule pile à présenter, quality gate commun), mais elle ne justifie pas à elle seule de jeter ~3 500 lignes Python testées et sans dépendance, pour un outil qui pousse seul sur le dépôt. Si elle est retenue, la faire **après** P1-P4, quand les règles sont isolées et décrites par des tests de table : ces tables servent alors de spécification à la réécriture, et le portage peut commencer par les règles (`policy`, `cycle`) dans un module Java appelé depuis le Python existant, avant de remplacer le reste.

## 5. Ordre suggéré et invariants

1. **P2 puis P1** : une branche, sans changement de comportement ; preuve par `tests/run-all.sh` inchangé + nouveau test de cohérence `component_kind`.
2. **P4** : petit, sécurise P1.
3. **P3** : le plus gros ; commencer par écrire les tests de `decide_cycle` à partir du registre d'incidents, puis migrer une règle à la fois (halte rollbacks, halte pré-push, no action, blocage 48 h, transitoire).

À conserver dans chaque étape (repris de l'étude précédente) : aucune décision par LLM, chaque garde-fou garde son test d'incident, le skill `/fixcve` continue d'utiliser les mêmes scripts, l'état reste écrit sous verrou.

## 6. Décisions à prendre

- Adopter P1 à P4, ou seulement P1/P2 (gain rapide, risque faible) ?
- Pour P3, exécuter les tests `run-all.sh` en CI (question laissée ouverte par la section 8 de l'étude précédente) : la refonte du poller en serait mieux protégée.
