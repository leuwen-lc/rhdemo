# fixcve-auto — plan d'évolutions

Plan détaillé issu de la revue complète du 2026-09-28, à reprendre au fil de l'eau. Il complète [FIXCVE_AUTO.md](FIXCVE_AUTO.md) (fonctionnement actuel) sans le remplacer.

**Principe directeur** : simplifier et harmoniser **sans perdre** ce que la mise au point incrémentale a construit (chaque garde-fou existe à cause d'un incident réel) ni le modèle de sécurité contre l'injection de prompt. Chaque étape est donc livrée avec un test qui rejoue l'incident d'origine.

---

## 1. État au 2026-09-28

| Élément | État |
| --- | --- |
| Proposition **A** (environnement épuré, plafonds de durée et de coût des phases LLM) | **Faite et testée, non committée** : `fixcve-auto-poll.sh` (fonction `run_llm_phase`), `tests/fixcve-run-llm-phase.test.sh`, ligne de garde-fou dans `FIXCVE_AUTO.md`. Active dès maintenant car le cron lance le script depuis la copie de travail principale. |
| Propositions B à I | À faire (sections 4 et 5). |
| Modifications de skills faites pendant la revue | **Locales uniquement** (`.claude/` est dans `.gitignore`) : recherche npm hors du skill de lookup, wrapper Maven à 3 arguments, garde des jars embarqués dans une image. Voir la proposition C. |

## 2. Invariants à conserver

Ces propriétés ne doivent régresser à aucune étape ; chacune a déjà servi.

- Séparation en 3 phases à permissions disjointes ; phase 1 (détection) **sans LLM**.
- Validation de schéma stricte entre chaque phase (`fixcve-validate-json.py`), jamais par un LLM.
- Clone git isolé, jamais la copie de travail principale ; garde-fou « arbre non propre ».
- Un push ne peut pas, à lui seul, modifier ce que le bot est autorisé à faire (voir C : c'est le point le plus fragile).
- Validation d'un correctif par SHA (ancêtre du build), pas par numéro de build.
- Validation locale avant push, rollback automatique, halte après rollbacks répétés.
- Anti-boucles : blocage confirmé, no_action, échecs pré-push, hors périmètre jamais tracé en git.
- Journal d'audit append-only, versionné.
- Critères A/B objectifs pour toute suppression ; jamais de `--force` npm.

## 3. Faits vérifiés pendant la revue

| Constat | Preuve |
| --- | --- |
| Les tokens `JENKINS_TOKEN` et `CODEBERG_TOKEN` étaient visibles du tool Bash de `claude -p` | `printenv` avec valeurs factices, phases 2 et 3 (corrigé par A pour Jenkins et pour la phase 2) |
| Aucun `timeout` ni plafond de coût sur `claude -p` | lecture du script (corrigé par A) |
| Le cron, les scripts et les skills viennent de trois sources différentes | cron : copie principale ; scripts, permissions, détecteurs : clone (donc `origin`) ; skills : copie principale via lien symbolique |
| La politique (critères A/B, règles de lookup) est écrite en 4 endroits et a déjà dérivé | le skill interactif `/fixcve` utilise encore l'API de recherche `rows=5` qui a causé le problème Maven |
| Le motif « journal, `git add`, `commit`, `push`, état » est copié une quinzaine de fois | `grep` dans `fixcve-auto-poll.sh` |
| Six mémoires ou compteurs avec des logiques différentes | `consecutive_rollbacks`, `consecutive_prepush_failures`, `consecutive_no_action_pushes`, `blocked_confirmed`, `no_action_confirmed`, `dirty_tree_cycles` |
| Journal bruyant | 16 types d'événements ; 33 `blocked_needs_human`, dont 7 pour le seul build #886 |
| Un crash (Jenkins, `detect`, `claude -p`) ou un `git push` en échec ne fait pas avancer l'état | `exit 1` sous `set -e` : nouvel essai, avec appels LLM, toutes les 15 min sans limite (déduit du code, non observé) |
| Pas de test des scripts avant cette revue | seul le test de A existe |

Résiduels de sécurité connus et **assumés pour l'instant** (déjà documentés dans `FIXCVE_AUTO.md`) : la phase 3 garde `CODEBERG_TOKEN` et `GIT_ASKPASS` dans son environnement tant que `git push` est fait par le modèle ; `Bash(python3:*)` reste un joker complet ; les fichiers de `$HOME` (clé AGE, credentials chiffrés) sont lisibles par l'utilisateur unix du cron ; le champ `title` d'une CVE (texte libre d'origine externe) atteint les phases LLM.

---

## 4. Propositions

Ordre suggéré en section 6. Effort : S (< 2 h), M (une demi-journée), L (plusieurs sessions).

### A. Environnement épuré et plafonds des phases LLM — FAIT (à committer)

Phase 2 sans aucun credential ; phase 3 sans les credentials Jenkins ; `timeout` et `--max-budget-usd` sur les deux. `--max-turns` volontairement écarté (accepté par la CLI mais absent de son aide, donc non garanti). Reste à committer et pousser.

### B. Sortir `git commit` et `git push` de la phase 3 — effort M

- **But** : la phase 3 ne fait que modifier des fichiers ; le script committe et pousse. Plus aucun credential ni droit git pour le modèle (supprime le résiduel de A).
- **Étapes** :
  1. Retirer `git add/commit/push/restore` de `fixcve-auto-apply-permissions.json` ; retirer `CODEBERG_*` et `GIT_ASKPASS` de `LLM_SCRUB_APPLY`.
  2. Après la phase 3, le script lit `git diff --name-only` et **refuse** tout fichier hors liste autorisée (`pom.xml`, `owasp-suppressions.xml`, `.trivyignore.yaml`, `frontend/package*.json`, fichiers d'image listés dans le skill, `SECURITY_ADVISORIES.md`, journal).
  3. Validation syntaxique (XML, YAML, JSON) puis commit et push déterministes ; message construit par le script à partir de `lookup.json`.
  4. Résultat déterminé par le diff (`APPLIED` ssi diff non vide et poussé) et non par la ligne finale que le modèle doit écrire.
- **Supprime** : les événements `claude_invocation_no_result` (3 au journal), la classe « journal non committé » (#882), la dépendance à la consigne « jamais de `Co-Authored-By` ».
- **Points d'attention** : le message de commit change de main ; le skill garde la rédaction des justifications (dans `SECURITY_ADVISORIES.md`) ; conserver la validation locale `./mvnw dependency-check` avant commit, ce qui la place côté script ou la laisse au modèle avec `Bash(./mvnw:*)`.
- **Test** : diff contenant un fichier interdit → rejeté et annulé ; diff vide → `NO_ACTION` ; les fixtures des builds #882 et #886.

### C. Épinglage local de confiance — effort M

- **But** : pouvoir **versionner les skills** sans qu'un push puisse modifier le comportement du bot, et exécuter tout depuis un seul arbre.
- **Principe** : un fichier local `~/.config/rhdemo-fixcve/trusted.sha256` liste les hash des fichiers qui définissent ce que le bot a le droit de faire : skills, fichiers de permissions, scripts de détection, de validation et de lookup. Le script de polling recalcule ces hash à chaque cycle et **refuse d'agir** si l'un diffère, avec une alerte. Une commande `fixcve-install.sh --trust` affiche le diff, demande confirmation, puis met à jour les hash.
- **Étapes** :
  1. Décider de l'emplacement versionné des skills (proposé : `rhDemo/scripts/fixcve-skills/`), `.claude/skills` devenant une copie installée par `fixcve-install.sh`.
  2. Faire lire au script de polling **tout** depuis un seul arbre (le clone, à un commit approuvé) ; le script de polling lui-même reste dans la copie principale (racine de confiance).
  3. Fichier de hash, vérification, commande d'approbation.
- **Résout** : la dérive « skill à jour, script pas encore » ; l'absence de sauvegarde et d'historique des skills (aujourd'hui seulement sur cette machine) ; le fait que les permissions du bot soient aujourd'hui lues depuis `origin`.
- **Test** : modifier un fichier de confiance sans approbation, le cycle refuse ; approuver, le cycle reprend.
- **Question ouverte** : protection de branche de la forge (revue obligatoire sur ce dossier) — non connue.

### D. Décisions et recherches déterministes — effort L

- **D1. Table de décision** (`fixcve-classify.py`) : à partir de `detected.json` et `lookup.json` (avec `npm_dev_only`, scope Maven, vecteur `AV`), produit pour chaque finding `upgrade`, `suppress_permanent` (critère A), `suppress_temporary` (critère B) ou `blocked`. La phase 3 exécute cette décision au lieu de l'interpréter ; le script vérifie ensuite que le diff correspond.
- **D2. Lookup Maven** en script (dernière version stable de la même branche mineure, sans pré-release), comme `fixcve-npm-lookup.py`. Garder le garde-fou de cohérence sur la version installée.
- **D3. Lookup Docker** en script (tags du registre, `docker manifest inspect` pour le digest).
- **D4. Retirer `title`** (texte libre externe) des fichiers lus par les phases LLM ; ne le garder que dans le journal. Réduit le vecteur d'injection à zéro champ libre.
- **Résultat attendu** : la phase 2 devient inutile (elle ne lit plus que des listes de versions) ; la phase 3 se réduit à des éditions.
- **Points d'attention** : l'ordre choisi de la version Maven est un pari (le rapport OWASP ne dit pas quelle version corrige) : c'est la phase B qui tranche. Le cas `fixAvailable: true` de `fixcve-npm-lookup.py` n'a été testé que sur données synthétiques.
- **Migration incrémentale** : D2 puis D3 (une étape par écosystème, chacune avec son test), D1 en dernier.

### E. Tests issus des incidents réels — effort M

- **Constat** : les archives de cycle (`~/.config/rhdemo-fixcve/cycle/archive`) sont de vraies fixtures, mais hors dépôt.
- **Étapes** : committer des fixtures réduites sous `rhDemo/scripts/tests/fixtures/` ; un test par incident (tableau en section 7) ; un lanceur `tests/run-all.sh`. Les récits d'incident quittent les commentaires du code (près de la moitié du script de polling) pour un registre `docs/FIXCVE_AUTO_INCIDENTS.md` (incident, cause, garde-fou, test).
- **Exécution** : voir section 8.

### F. Outil `fixcve-ctl` — effort S à M

- **But** : remplacer les éditions manuelles de `state.json` (une dizaine pendant la revue, toujours sous `flock`).
- **Commandes** : `status`, `pause`, `resume` (remet `idle` et les compteurs à zéro), `rewind <build>`, `unblock`, `replay-phase2 <build>` et `replay-phase3 <build>` (rejeu sur les fichiers archivés, sans push).
- **Test** : sur une copie de `state.json`, chaque commande produit l'état attendu ; le verrou est bien pris.

### G. Harmonisation du script de polling — effort M à L

- **Fonctions communes** : `audit_event` (écrit, committe, pousse ; remplace ~15 blocs), `end_cycle` (un seul endroit qui écrit l'état), `source_sha` (3 copies aujourd'hui), `stage_of` (3 reconnaissances de stage) avec table d'ordre du pipeline.
- **Une seule mémoire « même cause »** : `{clé de cause, sha source, depuis, durée de vie, tentatives}`, qui remplace `blocked_confirmed` et `no_action_confirmed`. Elle intègre le **blocage transitoire** non traité : quand la cause est un `lookup_failed`, fenêtre de 1 h et 3 tentatives au maximum, puis 48 h avec alerte. Sans ce plafond, supprimer le blocage relancerait le cycle en boucle (pousser le journal relance un build).
- **Bloc de constantes** unique (48 h, 2 rollbacks, 2 échecs pré-push, 8 cycles d'alerte, plafonds LLM).
- **Retentatives bornées** : un crash de Jenkins, de `detect` ou de `claude -p`, et un `git push` en échec, incrémentent un compteur au lieu de recommencer sans limite.
- **`notify()` central** (journal seul par défaut) appelé sur `blocked_needs_human`, halte, arbre non propre, validation partielle ; branchable ensuite sur mail ou ntfy.
- **Découpage** du fichier (~950 lignes) en bibliothèques (`state`, `audit`, `jenkins`, phases A et B). Un portage en Python est possible mais n'est pas nécessaire : le gain vient des fonctions communes et des tests, pas du langage.
- **Test** : les scénarios de la section 7 sur la machine à états.

### H. Journal simplifié — effort S

- 16 types d'événements réduits à environ 8 : `cycle_failed{phase, raison}` (fusionne `detect_phase_failed`, `lookup_phase_failed`, `claude_invocation_no_result`), `findings_blocked` (**un événement par cycle** avec liste, au lieu d'une ligne par finding), `remediation_applied`, `risk_accepted`, `validation{résultat}` (fusionne succès, partielle, stage propre, rollback), `automation_halted`, `skipped`.
- Le rendu (`fixcve-audit-render.sh`) est générique : pas de changement. Prévoir la lecture des anciens événements (le fichier est append-only).

### I. Skill interactif `/fixcve` — effort S

- Le faire appeler `fixcve-detect.py` et les scripts de lookup au lieu de refaire la recherche à la main, puis demander la validation. Supprime la copie de la politique (dérive déjà constatée).

---

## 5. Petites dettes repérées

- Le `fixAvailable: true` du lookup npm n'a jamais été exercé sur un cas réel.
- `fixcve-auto-lookup` : le wrapper Docker et le wrapper OSV n'ont pas de garde de cohérence comparable à celui de Maven ; harmoniser leurs codes de sortie et leur sortie JSON.
- Le pin de `pending_reverified` des jars embarqués dans une image repose sur une **consigne** du skill (testée une fois) : la rendre déterministe en faisant rejeter par le validateur tout `pending_reverified` dont le paquet correspond à une entrée `.trivyignore.yaml` « embarqué dans ».
- Vérifier si `Bash(python3:*)` peut être restreint à des scripts précis une fois D en place.
- Sandbox OS (utilisateur dédié, `bubblewrap`) pour les phases LLM : seul moyen de traiter les résiduels de `$HOME`.

---

## 6. Ordre suggéré

1. **A** : committer et pousser (petit, déjà testé).
2. **E + F** : filet de sécurité et outil de reprise avant de refondre.
3. **B** : phase 3 sans credential.
4. **C** : épinglage de confiance, puis versionnement des skills.
5. **D** : par écosystème (D2, D3), puis D1, D4.
6. **G**, **H**, **I** : harmonisation, après que les tests couvrent la machine à états.

Dépendances : E avant B, G et D ; C avant de versionner les skills ; D1 après D2 et D3.

## 7. Incidents à rejouer en tests

| Incident | Cause | Fixture ou test attendu |
| --- | --- | --- |
| Builds #878 et #882 | un finding ≥ 9 bloquait 19 autres ; `lookup_failed` npm | lookup et détection du #882 → décision par finding |
| #882 | journal non committé, clone sale, cycles bloqués 9 h | après phase 3, journal committé par le script ; arbre propre |
| #884 et #886 | API de recherche Maven en `rows=5` | wrapper : version installée absente → code 4 |
| #890 | rollback à tort : OWASP propre, Trivy en échec | verdict `next_stage` ; stage suspect → rollback |
| #894 | doublon Trivy (même jar à deux emplacements) | détection : un seul finding par paire |
| #849 puis #850 | suppressions documentées, rollback si CVE non couverte | cas `keep` et rollback |
| #718, #734 | rollback d'un bon correctif à cause d'autres CVE | `validation_partial` |
| #735 à #744, #799 à #802 | boucles de journal | anti-boucles : aucun push au deuxième passage |
| Tokens visibles du modèle | environnement hérité | test de A (faux et vrai `claude`) |

## 8. Exécution des tests

Décision **reportée** : pour l'instant les tests se lancent à la main.

- **Local** : `rhDemo/scripts/tests/fixcve-run-llm-phase.test.sh` ; option `REAL_CLAUDE=1` pour un essai de bout en bout avec le vrai `claude` (valeurs factices, quelques centimes) — à lancer avant de modifier la façon dont `claude -p` est invoqué. Prévoir un lanceur `run-all.sh` et, éventuellement, un hook git `pre-push` installé par `fixcve-install.sh` (non versionné).
- **Jenkins** (vérifié) : l'agent `builder` est une image Debian avec `bash`, `git`, `curl`, `jq` ; `python3` n'y est pas installé explicitement. Le test actuel n'a besoin que de `bash` et des outils de base. Les tests suivants demandent `python3` et des fixtures committées. `REAL_CLAUDE=1` reste local.
- **Deux voies possibles en CI**, à trancher plus tard : une étape dans `Jenkinsfile-CI` (déconseillée : pipeline sensible, déjà long ; une étape `UNSTABLE` n'envoie aucun mail car les blocs `post` ne couvrent que succès et échec) ou un **job dédié** `RHDemo-FixcveTests` (`Jenkinsfile-FixcveTests`, filtre de chemin sur `rhDemo/scripts/**`, déclaré dans JCasC, mail dédié). Un échec de test en CI ne provoque pas de boucle : il tomberait dans un stage hors périmètre, que le bot ignore.

## 9. Reprise

- État du bot : `~/.config/rhdemo-fixcve/state.json` ; toute édition à la main se fait sous le verrou `~/.config/rhdemo-fixcve/poll.lock` (`flock`). Reprise, pause et remise en arrière sont décrites dans [FIXCVE_AUTO.md](FIXCVE_AUTO.md) ; l'outil F les automatisera.
- Journal des cycles : `poll.log` (local) et `docs/fixcve-audit.md` (versionné).
- Pour rejouer une phase sans rien pousser, il faut aujourd'hui copier le fichier de cycle archivé dans `.fixcve-cycle/` du clone, sous le verrou, puis lancer `claude -p` avec le fichier de permissions de la phase : F remplacera cette procédure manuelle.
