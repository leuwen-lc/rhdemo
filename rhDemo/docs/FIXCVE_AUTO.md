---
statut: actif
verifie_le: 2026-11-25
sources:
  - rhDemo/Jenkinsfile-FixCVE
  - rhDemo/scripts/fixcve-auto.py
  - rhDemo/scripts/fixcve-classify.py
  - rhDemo/scripts/fixcve-detect.py
  - rhDemo/scripts/fixcve-apply.py
  - rhDemo/scripts/fixcve_lib/
---

# Remédiation CVE automatisée (fixcve-auto)

Automatisation complète de la remédiation des CVE bloquantes détectées par Trivy ou OWASP Dependency-Check dans le pipeline `RHDemo-CI`, **sans validation humaine**. Elle tourne dans Jenkins (job `RHDemo-FixCVE`, choix expliqués dans [ETUDE_FIXCVE_DANS_JENKINS.md](etudes/ETUDE_FIXCVE_DANS_JENKINS.md)). La procédure est **entièrement déterministe** (aucun LLM) depuis la refonte du 2026-10-09 (voir [FIXCVE_AUTO_REFONTE.md](etudes/FIXCVE_AUTO_REFONTE.md), section 10). Le skill interactif `/fixcve` réutilise les mêmes scripts avec validation humaine.

**Objectif mesuré** : un cycle n'échoue que face à une CVE **sans correctif publié, CVSS ≥ 9 et sans critère A** (« échec conforme »). Tout autre échec est un défaut de la procédure, compté par l'indicateur `fixcve-stats.py` (voir « Indicateur »).

---

## Architecture

```text
RHDemo-CI ── post { always } ──> job RHDemo-FixCVE (Jenkinsfile-FixCVE, agent « fixcve »)
cron de secours horaire ────────┘   └─> fixcve-auto.py (action d'exploitation)
                                          └─> fixcve_lib/poller.py (checkout neuf, branche du job)
         │
         ├─ Phase A (idle) : nouveau build Jenkins en échec sur un stage Trivy/OWASP
         │     1. fixcve-detect.py    -> detected.json   rapports Jenkins -> findings
         │     2. fixcve-resolve.py   -> lookup.json     avis OSV + registres -> version corrigée
         │     3. fixcve-classify.py  -> plan.json       politique : upgrade / A / B / blocage
         │     5. fixcve-apply.py     -> fichiers modifiés + événements d'audit préparés
         │     6. fixcve-verify.py    -> vérification locale (syntaxe, npm, Dependency-Check)
         │     7. commit du correctif, commit du journal, push
         │     (validation de schéma entre 1, 2 et 3 ; tout échec arrête le cycle avant push)
         │
         └─ Phase B (pending_validation) : build CI suivant, bâti sur le correctif
               ├─ SUCCESS → validé
               ├─ FAILURE, findings traités disparus, aucun nouveau → validation partielle
               ├─ FAILURE, stage d'origine propre, échec sur le scan suivant → validé, stage suivant traité
               └─ sinon → git revert du correctif + halte après 2 rollbacks consécutifs
```

Tout le code est dans [`rhDemo/scripts/`](../scripts/) : les points d'entrée `fixcve-*.py` et la bibliothèque [`fixcve_lib/`](../scripts/fixcve_lib/__init__.py) (un module par responsabilité, décrits dans son `__init__.py`).

Les règles métier sont isolées (choix expliqués dans [FIXCVE_REGLES_METIER.md](etudes/FIXCVE_REGLES_METIER.md)) :

- **`fixcve_lib/rules.py`** : seuils CVSS, images surveillées et remédiables, constantes de cycle (haltes, délais), et la **nature du composant** (`component_kind` : `project_maven`, `project_npm`, `jar_embedded_js`, `image_os`, `image_embedded_jar`), calculée une fois à la détection et qui dit où se fait la montée et quels critères A s'appliquent. Aucune de ces valeurs n'est recopiée ailleurs (contrôlé par `tests/test_rules.py`).
- **`fixcve_lib/policy.py`** : table de décision par finding (`decide`, sur des valeurs simples).
- **`fixcve_lib/cycle.py`** : règles de cycle du poller (haltes, mémoire « même cause », verdict de la validation), fonctions pures. Le poller (`fixcve_lib/poller.py`, avec `jenkins.py` et `gitops.py`) n'exécute que les effets (Jenkins, git, journal) puis installe le nouvel état calculé ; un push en échec laisse l'état inchangé. Il lance les étapes `fixcve-*.py` en sous-processus, comme le skill `/fixcve`, et les lit par leur ligne de résultat. Le jeton Jenkins passe dans un en-tête HTTP et le jeton Codeberg par `GIT_ASKPASS`, jamais en argument de commande.

### Étapes et sources de vérité

| Étape | Script | Source de vérité | Sortie |
| --- | --- | --- | --- |
| 1. Détection | `fixcve-detect.py` | Rapports Jenkins (HTML OWASP DC, JSON Trivy) | `detected.json` |
| 2. Recherche | `fixcve-resolve.py` (`fixcve_lib/resolve.py`) | **Avis OSV.dev** (plage corrigée par branche, alias CVE ↔ GHSA), confirmé par le registre (Maven Central, npm, quay.io / Docker Hub / ghcr.io) ; `npm audit`, `package-lock.json`, `mvnw dependency:list` | `lookup.json` |
| 3. Classification | `fixcve-classify.py` (`fixcve_lib/policy.py`) | Table de décision ci-dessous | `plan.json` |
| 5. Application | `fixcve-apply.py` (`apply.py`, `edits.py`, `suppressions.py`, `advisories.py`) | Plan validé | fichiers de remédiation, `apply-result.json` |
| 6. Vérification | `fixcve-verify.py` (`verify.py`) | Parseurs XML/YAML/JSON, lockfile, `npm audit`, rescan Dependency-Check local | `verify.json` |

Les fichiers de cycle vivent dans `rhDemo/.fixcve-cycle/` de l'espace de travail et sont archivés dans le volume d'état, `cycle/archive/<build>-<étape>.json` (post-mortem, rejeu en test).

### Table de décision (étape 3)

| Situation | Action | Résultat |
| --- | --- | --- |
| Version corrigée publiée dans la **même branche majeure** | `upgrade` | `fixed` |
| Recherche en panne (OSV et registre injoignables) | `transient` : rien n'est supprimé, nouvel essai dans 1 h (3 fois, puis 48 h et alerte) | `transient` |
| Sans correctif, **critère A** vérifié | `suppress_permanent` | `accepted_permanent` |
| Sans correctif, CVSS < 9.0 | `suppress_temporary` (**critère B**, jeton `[PENDING_UPSTREAM_FIX]`) | `accepted_temporary` |
| Sans correctif, CVSS ≥ 9.0, sans critère A | `blocked`, journalisé, revue humaine | `blocked_no_fix_ge9` (échec conforme) |

**Critère A** (inexposition objective, prime sur le CVSS) : paquet npm dont toutes les copies sont `dev` dans `package-lock.json` ; dépendance Maven du projet dont toutes les portées sont `test`/`provided` ; vecteur CVSS `AV:L`/`AV:P`. Un jugement contextuel (code vulnérable non atteint dans notre configuration) n'est **jamais** automatique : c'est une décision humaine (skill `/fixcve`, critère `A:decision_humaine`).

Une montée qui ne peut pas être appliquée ou que la vérification ne confirme pas retombe **une fois** dans la branche « sans correctif » de la table (A, B ou blocage) ; le plan est réappliqué et revérifié. La raison reste au journal (« correctif X publié mais montée impossible (cause) »). Un blocage qui en résulte alors qu'un correctif est publié compte comme défaut (`tooling`), jamais comme échec conforme : `blocked_no_fix_ge9` suppose qu'aucun correctif n'existe (incident du build #1097, 2026-11-24).

### Montées de version (étape 5)

- **npm** : `npm update <paquet> --package-lock-only` ; à défaut `npm install` exact (dépendance directe) ou `overrides` (transitive). Retenue seulement si **toutes** les copies du lockfile atteignent la cible ; sinon fichiers restaurés (incident #845/#847, montée sans effet).
- **Maven** (`edits.maven_upgrade`), selon ce que le BOM Spring Boot (`spring-boot-dependencies` de `~/.m2`, sinon Maven Central) impose pour l'artefact, commentaire `<!-- Fix ... -->` dans tous les cas :
  - **module de Spring Boot** (version écrite en dur, celle du parent, ex. `spring-boot-security`) : version de `spring-boot-starter-parent`, même branche mineure, parent publié. Ces montées passent en premier dans le cycle : elles changent le BOM que lisent les suivantes ;
  - **propriété du BOM** (`tomcat.version`) ou d'un **BOM importé** (`spring-framework.version`, `jackson-bom.version`), retenu seulement s'il publie la version cible et la liste réellement (pom du BOM lu sur Maven Central). Le rattachement par simple préfixe de groupe a été abandonné : il rattachait `org.springframework.boot` au BOM de Spring Framework (build #1097). Propriété non surchargée dans `pom.xml` et valeur par défaut du BOM déjà au moins égale à la cible (rapport plus ancien que HEAD, parent monté depuis) : `already`, rien n'est posé (replay DRY_RUN du build #1097) ;
  - **sinon** (dépendance hors BOM, ou version cible absente du BOM importé) : version de la dépendance directe si `pom.xml` la porte par une propriété (version écrite en dur : montée manuelle), à défaut **épinglage** dans `<dependencyManagement>`, qui impose la version même à une dépendance transitive. Jamais de changement de version majeure.
- **Nettoyage des surcharges périmées** (`edits.cleanup_stale_overrides`), dans tout cycle qui modifie déjà `pom.xml` (validé avec la remédiation, jamais poussé seul) : retrait des propriétés « Fix » dont le BOM Spring Boot fournit une version au moins égale, et des épinglages « Fix » dont Maven résout sans eux une version au moins égale (`mvnw dependency:list` sur un pom temporaire sans épinglages), ou dont l'artefact a quitté l'arbre. La version effective ne baisse jamais ; résolution impossible : épinglages conservés. Événement `stale_overrides_removed`. Motif : après une montée du parent, une surcharge restée en place devient une rétrogradation silencieuse (Tomcat, PostgreSQL, Hibernate, Hibernate Validator constatés avec Spring Boot 4.1.3).
- **Image tierce** (jar embarqué : Keycloak, nginx, postgres, NGF) : tag candidat issu des versions corrigées annoncées par Trivy, avec le suffixe de variante du tag courant, plus récent que lui, digest lu sur le registre ; référence `dépôt:tag@digest` remplacée dans `Jenkinsfile-CI`, les deux `docker-compose.yml`, `values.yaml` et `init-stagingkub.sh`. Un numéro de bibliothèque (bcprov 1.85) n'est jamais un tag : décision humaine.
- **Paquet système d'image** : aucun tag corrigé déductible sans scanner l'image ; suppression A/B ou blocage selon la table.

### Suppressions (étape 5, `suppressions.py`)

Générées, jamais rédigées : toutes les formes connues de la faille (`<cve>` pour un CVE, `<vulnerabilityName>` pour un GHSA : OSS Index nomme par CVE, Node Audit par GHSA, voir [OWASP_DEPENDENCY_CHECK.md](OWASP_DEPENDENCY_CHECK.md)) ; formes manquantes ajoutées au bloc existant ; portée `groupId` entier pour les groupes à CPE générique (tomcat, log4j, spring-security, jackson...) ; justification dans `<notes>`, jamais en commentaire XML. Trivy : entrée `.trivyignore.yaml` avec jeton `[OSV:<DISTRO>:<branche>]` pour un paquet système.

**Clôture automatique** des suppressions temporaires : à chaque cycle, les blocs `[PENDING_UPSTREAM_FIX]` npm et Maven sont revérifiés (avis OSV + registre) ; si un correctif est publié, toutes les formes de la faille sont retirées et la montée appliquée (événement `pending_fix_resolved`). Les suppressions Trivy (composants d'images tierces) restent à revérifier manuellement (la console du job les liste) ; pour un paquet système portant le jeton `[OSV:<DISTRO>:<branche>]`, l'avis de distribution OSV (`ALPINE-<CVE>`, `DEBIAN-<CVE>`, `UBUNTU-<CVE>`) est lu et une ligne `ALERTE` est écrite si la branche installée a un correctif, dans la console du job, avec un mail (build `UNSTABLE`), à chaque cycle tant que la suppression reste en place ; rien dans le journal d'audit. Aucune action automatique : un correctif de distribution ne prouve pas qu'une image tierce l'embarque. Cette revérification n'a lieu que dans un cycle déclenché par un build en échec.

---

## Garde-fous

| Garde-fou | Détail |
| --- | --- |
| **Aucun LLM** | Plus aucune surface d'injection de prompt : les rapports et avis externes ne sont lus que par du code ; aucun secret n'est exposé à un modèle. Les textes libres externes (titres de CVE) ne sont jamais recopiés dans un fichier versionné. |
| **Pas d'épinglage des scripts** | Comme `Jenkinsfile-CI` et `Jenkinsfile-Renovate`, `Jenkinsfile-FixCVE` et les scripts sont lus sur la branche : un compte qui pousse peut modifier le bot (risque accepté le 2026-11-22, [ETUDE_FIXCVE_DANS_JENKINS.md](etudes/ETUDE_FIXCVE_DANS_JENKINS.md), T1). |
| **Checkout neuf à chaque passage** | Espace de travail jetable de l'agent, placé sur `origin/<branche du job>` à jour : jamais d'arbre sale hérité d'un cycle interrompu. |
| **Push refusé** | origin a avancé pendant le cycle (merge Renovate) : si tous les commits locaux sont ceux du bot, rebase sur origin puis push (`fixcve_lib/gitops.py`) ; sinon ou en cas de conflit, échec du passage sans mise à jour de l'état, le suivant recommence. |
| **Revert limité aux commits du bot** | Le rollback n'annule qu'un commit dont l'auteur est `RHDemo FixCVE Bot` et présent sur la branche : un état altéré ne peut pas faire annuler un commit quelconque. |
| **Validation de schéma** | `fixcve-validate-json.py` entre chaque étape (`detect`, `lookup`, `plan`) : clés exactes, regex/enum, référence croisée, une action et une seule par finding, critère B interdit à partir du seuil bloquant (`CVSS_BLOCKING`), version Trivy imposée pour une image, `component_kind` cohérent avec l'écosystème et l'image (un jar d'image tierce ne passe jamais pour une dépendance du pom.xml, #812). |
| **Vérification locale avant push** | Syntaxe de chaque fichier modifié ; npm : copies du lockfile et `npm audit` ; OWASP : rescan Dependency-Check local (clé NVD lue dans l'environnement par le plugin, OSS Index activé comme en CI avec le credential `ossindex-credentials`, cache de 7 jours partagé : sans lui, une faille que seul OSS Index relie à la version passait jusqu'à la CI, builds #1102 à #1107) — aucun finding traité ne doit subsister. Une CVE nouvelle (≥ 7, sur n'importe quel paquet : une montée du parent ou un nettoyage change des versions par ricochet) n'est plus ignorée : elle est ajoutée aux findings du cycle, recherchée, classée et le plan réappliqué **une fois** avant le push (build #1102 : Tomcat 11.0.27 amené par Spring Boot 4.1.3, CVE-2026-116830, que la CI avait fait annuler) ; si le rescan en trouve encore, le cycle échoue avant le push. La base NVD est celle de `RHDemo-CI` (volume Maven partagé, voir [Cache NVD](#cache-nvd)) ; tout rapport antérieur est supprimé avant le scan : un scan interrompu ne relit jamais un vieux rapport. Sans clé NVD : événement `local_validation_incomplete`, la preuve revient au build CI. Trivy : pas de scan local, preuve par le build CI. |
| **Deux commits** | Le correctif, puis le journal : un rollback (`git revert` du seul correctif) ne touche jamais au journal append-only. |
| **Validation par SHA** | La phase B ne juge que le build dont le commit contient le correctif (`git merge-base --is-ancestor`), jamais un build intercalé (#749/#750). |
| **Validation par non-régression** | Build rouge après correctif : conservé si les findings traités ont disparu sans nouveau finding (`validation_partial`), ou si le stage d'origine est propre et l'échec porte sur le scan suivant (`validation_stage_cleared`, #890), ou si le détecteur ne voit rien alors que le build échoue sur ce même stage sans citer aucun finding du correctif (#972), ou si le correctif se réduit à des suppressions/documentation, que tous ses findings ont disparu et qu'une CVE nouvelle apparaît (cause indépendante, #975 ; fonction `fix_commit_only_suppressions`) ; sinon rollback. Un `git revert` en conflit est abandonné (`revert_fix_commit`) : le correctif est conservé, événement `rollback_conflict`, attente humaine (#975). Cause réelle du rollback journalisée (`failure_stage`, `failure_detail`, #819). |
| **Haltes** | 2 rollbacks consécutifs, 2 échecs pré-push consécutifs (étape en échec, schéma invalide, vérification locale), 2 pushes « sans finding » consécutifs. |
| **Anti-boucles** | Une seule mémoire « même cause » dans `state.json` (`same_cause` : nature, SHA du code source, depuis, délai, essais) : blocage confirmé, silence 48 h sur le même code source ; recherche en panne, 1 h, 3 essais, sans commit ; stage Trivy/OWASP sans CVE exploitable, notifié une fois par code source. Hors périmètre (ni Trivy ni OWASP) : jamais committé ; « déjà corrigé sur HEAD » : aucun commit. L'ancien format (`blocked_confirmed`, `no_action_confirmed`) est relu et converti au premier passage. |
| **Un passage à la fois** | `disableConcurrentBuilds()` du job, `flock` sur `poll.lock` du volume d'état, un seul conteneur d'agent pour tout le nuage Docker (jamais en même temps qu'un build CI). Durée maximale d'un passage : 30 min. |
| **Journal d'audit append-only** | `rhDemo/docs/fixcve-audit.jsonl` (vue `fixcve-audit.md` générée), un `outcome_code` par événement. |

---

## Machine à états

```mermaid
flowchart TD
    IDLE["idle"]
    PEND["pending_validation"]
    HALT["halted"]

    IDLE -- "correctif poussé" --> PEND
    PEND -- "validé / partiel / stage suivant / rollback" --> IDLE
    IDLE -- "seuil d'échecs pré-push" --> HALT
    PEND -- "rollback, seuil" --> HALT
    HALT -- "reprise manuelle" --> IDLE
```

Phase A (`idle`, build en échec sur Trivy/OWASP) :

```mermaid
flowchart TD
    A[Build en échec] --> B{Blocage déjà constaté,\nmême code, délai non écoulé ?}
    B -- oui --> Z[Silence]
    B -- non --> C[Détection] --> D{Findings ?}
    D -- non --> E[Journal une fois par code source\nhalte au 2e push]
    D -- oui --> F[Recherche → Plan → Application → Vérification]
    F -- "fichiers modifiés et vérifiés" --> G[2 commits + push\npending_validation]
    F -- "montée non confirmée" --> H[Bascule sans correctif\nréapplication une fois]
    H --> F
    F -- "tout bloqué (CVSS ≥ 9)" --> I[Journal + silence 48h]
    F -- "recherche en panne" --> J[Nouvel essai 1h, 3 fois]
    F -- "erreur d'une étape" --> K[Journal, compteur pré-push]
```

---

## Indicateur

```bash
rhDemo/scripts/fixcve-stats.py          # tableau par mois
rhDemo/scripts/fixcve-stats.py --json
```

Par mois : cycles, succès, échecs conformes, pannes d'infrastructure (hors taux), défauts par code (`lookup_gap`, `policy`, `bad_fix`, `tooling`, `transient`, `needs_reasoning`) et taux d'échec. Les événements antérieurs au champ `outcome_code` sont classés approximativement (voir `fixcve_lib/outcomes.py`).

---

## Tests

- `rhDemo/scripts/tests/run-all.sh` : tests hors réseau (OSV, registres, npm injectés), dont les incidents réels rejoués à partir des archives de cycle (`tests/fixtures/`) — registre dans [FIXCVE_AUTO_INCIDENTS.md](FIXCVE_AUTO_INCIDENTS.md). Lancé par le job `RHDemo-Scripts` ([PIPELINES_CI_CD.md](PIPELINES_CI_CD.md)), hors de la CI de l'application, à chaque changement de `rhDemo/scripts/` : c'est la protection du poller contre une régression.
- `tests/test_cycle.py` : règles de cycle rejouées sur les incidents. `tests/test_poller.py` : poller exécuté de bout en bout par `fixcve-auto.py`, avec un faux Jenkins HTTP local, un dépôt local servant d'origin et des étapes simulées (phases A et B, haltes, rollback, rejeu sur origin, DRY_RUN, aucun secret en argument). Ces tests de caractérisation ont été validés sur l'ancien poller Bash avant la réécriture. `tests/test_gitops.py` et `tests/test_jenkins.py` : opérations git du bot et cause réelle d'un échec (#819).
- Poller complet : dans Jenkins, job `RHDemo-FixCVE` avec `DRY_RUN` coché (cycle réel sur une copie de l'état, sans push), éventuellement avec `ACTION=replay` sur un build en échec.

---

## Points d'attention

⚠️ L'automatisation **committe et pousse sur la branche courante sans revue humaine**, y compris des acceptations de risque. Choix assumé en échange des garde-fous ci-dessus, à désactiver si le contexte l'exige.

⚠️ **Heuristique Maven** : quand OSV ne relie pas la faille à l'artefact, la cible est la dernière version stable de la même branche mineure (`proof: heuristic`), non prouvée. La vérification locale (avec clé NVD) puis le build CI tranchent.

⚠️ **npm audit hors ligne** renvoie un rapport vide d'apparence valide : une conclusion « sans correctif » exige donc que l'avis OSV ait répondu ; sinon `lookup_failed` (transitoire).

⚠️ **Images tierces** : un composant interne vulnérable sans tag corrigé (CVSS ≥ 9) est un échec conforme ; l'acceptation documentée reste une décision humaine (exemples : bcprov, freemarker, netty dans Keycloak, voir [SECURITY_ADVISORIES.md](SECURITY_ADVISORIES.md)).

⚠️ **Écart CI / local** : le rescan local interroge OSS Index comme la CI (credential `ossindex-credentials`). Sans ce compte, il tourne sans OSS Index (message `rescan local sans OSS Index`) et une faille connue d'OSS Index seul n'est vue que par le build CI (phase B).

⚠️ **Credentials** : credentials Jenkins références OpenBao (`kv/jenkins/fixcve-forgejo-token`, `kv/jenkins/fixcve-jenkins-api`), plus `nvd-api-key` et `ossindex-credentials` partagés avec la CI, passés au poller par variables d'environnement le temps du passage ([OPENBAO.md](OPENBAO.md)). Une compromission de Jenkins donne aussi le token du bot, avec les mêmes droits que `ci-bot-forgejo-token` déjà présent. L'agent `fixcve` n'a pas le socket Docker de l'hôte, mais les agents de la CI l'ont et peuvent lire tous les volumes.

---

## Installation

### 1. Comptes externes

- **Jenkins** : un compte dédié (`claude`, **pas** `admin`), lecture seule, dont le token API sert au bot (et au skill `/fixcve`).
- **Codeberg** : un compte bot séparé (`fixcvebot-leuwen-lc`), jamais le compte personnel ; distinct de `cibot-leuwen-lc` (bot CI de Renovate, voir [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md)).
  1. Créer le compte sur `https://codeberg.org`.
  2. L'ajouter comme collaborateur **Write** (pas Admin) de `leuwen-lc/rhdemo`.
  3. Si la branche est protégée, l'ajouter à la liste autorisée en push.
- **Clé API NVD** : celle de la CI (credential `nvd-api-key`). Sans elle, pas de rescan local, la preuve revient au build CI.

### 2. Credentials (OpenBao déverrouillé)

```bash
rhDemo/scripts/openbao-setup.py jenkins fixcve-forgejo-token fixcve-jenkins-api
```

Le token Codeberg est émis directement sur le compte bot (mot de passe et code TOTP demandés) ; pour `fixcve-jenkins-api`, saisir `claude` et un token API créé en se connectant avec ce compte. Les deux deviennent des credentials Jenkins références OpenBao.

### 3. Jenkins

Agent `fixcve` (volume `rhdemo-fixcve-state`), plafond d'un conteneur et job `RHDemo-FixCVE` sont dans [`jenkins-casc.yaml`](../infra/jenkins-docker/casc/jenkins-casc.yaml) ; le répertoire du volume est créé par l'image agent (`Dockerfile.agent`, reconstruite par `start-jenkins.sh` quand elle change), qui fournit aussi `python3-yaml` (contrôle de syntaxe de `.trivyignore.yaml` par la vérification locale) et `python3-coverage` (job `RHDemo-Scripts`). Après un changement : reconstruire l'image si besoin, puis recharger JCasC. Le déclenchement vient du `post { always }` de `Jenkinsfile-CI`.

Les commits automatiques portent l'identité `RHDemo FixCVE Bot`. Le skill interactif `/fixcve` reste sur le poste : `rhDemo/scripts/fixcve-install.sh` l'installe dans `.claude/skills`.

---

## Exploitation

Paramètres du job `RHDemo-FixCVE` (« Lancer un build avec des paramètres ») :

| Besoin | Paramètres |
| --- | --- |
| Pause | Désactiver le job ; la remédiation se fait alors avec le skill `/fixcve` |
| Consulter l'état | `ACTION=status` ; l'état est aussi archivé à chaque passage (`fixcve-state.json`) |
| Reprise après halte | `ACTION=resume` (compteurs remis à zéro, puis passage) |
| Revérifier tout de suite un blocage | `ACTION=clear-blocked` (inutile après un changement de code : le SHA source change) |
| Rejouer un build | `ACTION=replay`, `BUILD_TO_REPLAY=<build>` (numéro seul, sans `#`). En mode réel, le build doit être le dernier terminé. Avec `DRY_RUN`, n'importe quel build encore conservé par Jenkins est traité : son rapport ancien est rejoué contre le code actuel, sans push ni modification de l'état. Jenkins ne conserve que les 30 derniers builds CI : un build plus ancien est signalé absent de l'historique (HTTP 404) et le rejeu s'arrête. |
| Essai sans effet | `DRY_RUN` coché, avec n'importe quelle action |

- **Notifications** : mail si le passage échoue (Jenkins ou Codeberg injoignable, push refusé, erreur d'une étape) ou s'il est `UNSTABLE` (halte, rollback, blocage sans correctif, ligne `ALERTE`), détail dans `fixcve-notify.txt` archivé. Rien sur un passage à vide.
- **Journaux** : console du job (chaque passage, y compris hors périmètre et blocages transitoires) ; `rhDemo/docs/fixcve-audit.jsonl` (événements à valeur sécurité, versionné) et sa vue `fixcve-audit.md` ; archives de cycle dans `cycle/archive/` du volume d'état.
- **Délai** : un agent inactif de la CI garde sa place 5 min (`idleMinutes`) ; le passage fixcve démarre donc jusqu'à 5 min après la fin du build CI.

### Cache NVD

La vérification locale utilise la base NVD de `RHDemo-CI` (`~/.m2/dependency-check-data/`, volume `rhdemo-maven-repository`), tenue à jour par chaque build CI : le rescan ne télécharge que le delta depuis le dernier build (19 s pour le build #970). Le plafond d'un conteneur d'agent garantit qu'aucun scan CI n'écrit dans la base en même temps.

Interrompre un passage bloqué : l'arrêter dans Jenkins (le `timeout` de 30 min le fait sinon). L'espace de travail est jeté avec l'agent ; l'état n'est mis à jour qu'après un push réussi.

## Voir aussi

- [ETUDE_FIXCVE_DANS_JENKINS.md](etudes/ETUDE_FIXCVE_DANS_JENKINS.md) — exécution dans Jenkins (décisions du 2026-11-22)
- [FIXCVE_AUTO_REFONTE.md](etudes/FIXCVE_AUTO_REFONTE.md) — plan d'évolutions et revue du 2026-10-09
- [FIXCVE_AUTO_INCIDENTS.md](FIXCVE_AUTO_INCIDENTS.md) — incidents, garde-fous et tests associés
- [OWASP_DEPENDENCY_CHECK.md](OWASP_DEPENDENCY_CHECK.md) — parité CI / Renovate, double inscription CVE + GHSA
- [SECURITY_ADVISORIES.md](SECURITY_ADVISORIES.md) — historique des CVE traitées
