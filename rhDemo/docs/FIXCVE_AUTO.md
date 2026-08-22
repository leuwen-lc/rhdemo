# Remédiation CVE automatisée (fixcve-auto)

Automatisation complète de la remédiation des CVE bloquantes détectées par Trivy ou OWASP Dependency-Check dans le pipeline `RHDemo-CI`, **sans validation humaine**. Complète le skill interactif `/fixcve` (`.claude/skills/fixcve/SKILL.md`) qui reste disponible pour un usage manuel.

---

## Architecture

```text
crontab (toutes les 15 min)
   └─> rhDemo/scripts/fixcve-auto-poll.sh   (bash + jq + curl + python3, PAS de LLM)
         │
         ├─ Phase A (idle) : détecte un nouveau build Jenkins en échec Trivy/OWASP,
         │     puis enchaîne 3 étapes à privilèges disjoints (voir "Séparation
         │     en 3 phases" ci-dessous) :
         │       1. fixcve-detect.py      -> detected.json   (script déterministe, PAS de LLM)
         │       2. /fixcve-auto-lookup   -> lookup.json     (Claude)
         │       3. /fixcve-auto-apply    -> commit + push   (Claude)
         │     un validateur de schéma déterministe (fixcve-validate-json.py)
         │     s'exécute entre chaque étape ; tout échec (schéma invalide,
         │     pas de résultat exploitable) arrête le cycle sans invoquer la
         │     phase suivante ni toucher git — voir "Traçabilité et échecs".
         │
         └─ Phase B (pending_validation) : vérifie le build CI suivant
               ├─ SUCCESS  → marque résolu
               └─ FAILURE  → git revert automatique + halte après 2 rollbacks consécutifs
```

Le polling lui-même ne fait **aucun appel LLM** — Claude Code n'est invoqué que
pour les étapes qui demandent une vraie recherche/décision (recherche de
correctif, rédaction de suppression, édition de fichiers), pas pour
l'extraction mécanique des CVE bloquantes (phase 1), qui est un script pur.

---

## Séparation en 3 phases

Motivation : dans la conception initiale (une seule invocation `claude -p`), le
même contexte LLM cumulait à la fois l'accès à du contenu externe non fiable
(rapports Trivy/OWASP, réponses Maven Central/npm — descriptions de CVE dont
la source ultime est publique et non maîtrisée), les credentials Jenkins, et
les droits git push. C'est la combinaison classique dite du « lethal trifecta »
(contenu non fiable + accès privé + capacité d'action externe) : une injection
de prompt réussie via une description de CVE forgée aurait pu, en un seul
contexte, exfiltrer un credential ou pousser du code malveillant.

Le pipeline est donc scindé en 3 étapes à permissions disjointes, chacune
n'ayant accès qu'à ce qui est strictement nécessaire à son rôle :

| Phase | Implémentation | Détient | Ne détient pas | Touche du contenu externe non fiable |
| --- | --- | --- | --- | --- |
| 1. Détection | [`rhDemo/scripts/fixcve-detect.py`](../scripts/fixcve-detect.py) — **script déterministe, aucun LLM** | Accès Jenkins (lecture, via `fixcve-jenkins-fetch.sh`) | git, npm/Maven/Docker, aucun credential | Oui (rapports Trivy/OWASP) — **sans conséquence : pas de LLM, donc aucune cible pour une injection de prompt** |
| 2. Recherche de correctif | `.claude/skills/fixcve-auto-lookup/SKILL.md` (Claude) | Accès Maven Central (`fixcve-maven-lookup.sh`), `npm audit --json`, `docker manifest inspect` | Jenkins, git, Edit | Oui — **seule phase à la fois exposée à un LLM et sans aucun secret** |
| 3. Application | `.claude/skills/fixcve-auto-apply/SKILL.md` (Claude) | git add/commit/push, Edit des fichiers de remédiation | Jenkins, Maven Central/npm/Docker en direct (digest déjà résolu en phase 2) | Non — ne lit que les fichiers structurés déjà validés |

### Pourquoi la phase 1 est un script plutôt qu'un skill Claude

Contrairement aux phases 2 et 3, la détection ne demande aucun jugement : un
seuil CVSS fixe (≥ 7 pour OWASP DC, sévérité `CRITICAL` pour Trivy), une
extraction de champs mécanique, aucune décision de remédiation. C'est
exactement le type de tâche que ce projet confie déjà à du code déterministe
ailleurs (`fixcve-auto-poll.sh` lui-même, `fixcve-audit-render.sh`) plutôt qu'à
un LLM. Bénéfice direct : **sans LLM, il n'y a plus de cible pour une
injection de prompt** — toute la question de savoir si le contenu Jenkins
(lui-même bâti à partir de bases de vulnérabilités publiques via Trivy/OWASP
DC) est sûr à lire devient sans objet, puisque personne ne le "lit" au sens
où un LLM pourrait être influencé par son contenu. Les schémas d'extraction
(Trivy JSON, HTML OWASP DC) ont été construits et vérifiés contre des
rapports réels de ce projet (builds Jenkins #783 et #789), pas devinés —
voir les commentaires du script pour le détail des cas réels rencontrés
(identifiants GHSA en plus des CVE, `CVSS` multi-sources, `FixedVersion`
multi-valeurs, avisories ne portant qu'un score CVSS v4...).

Propriété clé : même si la phase 2 (la seule exposée à de l'injection) était
compromise, elle ne peut produire qu'un fichier de sortie erroné — ni
exfiltrer un secret (elle n'en détient aucun), ni pousser du code (elle n'a
aucun droit git).

### Wrappers réseau dédiés (pas de `curl` générique)

Plutôt qu'un `curl` restreint par liste blanche d'hôtes ou par verbe HTTP (un
filtrage de flags curl est contournable — `-d`, `-K`/`--config`, `--upload-file`
peuvent faire basculer une requête en écriture sans que ce soit visible dans un
simple filtre de préfixe), chaque accès externe passe par un wrapper à usage
unique qui construit lui-même l'URL et n'accepte que des paramètres typés,
jamais une URL ou des flags curl :

- [`rhDemo/scripts/fixcve-jenkins-fetch.sh`](../scripts/fixcve-jenkins-fetch.sh) : hôte et netrc figés, chemin restreint par regex aux seuls endpoints Jenkins utilisés par la détection.
- [`rhDemo/scripts/fixcve-maven-lookup.sh`](../scripts/fixcve-maven-lookup.sh) : hôte `search.maven.org` figé, `groupId`/`artifactId` validés par regex avant construction de l'URL — aucun SSRF possible.

### Fichiers intermédiaires et validateur de schéma

⚠️ **Contrainte du moteur de permissions découverte à l'usage** : sous
`--permission-mode dontAsk`, l'outil `Write` est **toujours refusé**, quel que
soit le chemin ou les règles `permissions.allow` (vérifié empiriquement — un
chemin absolu qui matche pourtant exactement la règle, `--add-dir` inclus, ne
change rien). Seul `Edit` fonctionne, et uniquement sur un fichier **déjà
existant**, à l'intérieur de l'arborescence du `cwd` de lancement (`--add-dir`
n'étend que la lecture, jamais l'écriture/édition). Conséquence directe : les
fichiers intermédiaires ne peuvent **pas** vivre hors de l'arbre du clone
isolé comme prévu initialement — ils doivent être pré-créés par
`fixcve-auto-poll.sh` (avec le contenu placeholder `{}`) avant chaque
invocation, puis remplis par les skills via `Edit`, jamais `Write`.

Les deux fichiers échangés entre phases vivent donc **dans** l'arborescence du
clone isolé, mais gitignorés (`rhDemo/.fixcve-cycle/`, voir `rhDemo/.gitignore`)
pour ne jamais déclencher le garde-fou « arbre de travail non propre » ni être
committés par erreur :

- `.fixcve-cycle/detected.json` (phase 1 → 2 → 3)
- `.fixcve-cycle/lookup.json` (phase 2 → 3)

Entre chaque phase, [`rhDemo/scripts/fixcve-validate-json.py`](../scripts/fixcve-validate-json.py) — **déterministe, jamais un LLM** — valide strictement le schéma (clés exactes, aucun champ inconnu toléré, valeurs contraintes par regex/enum, champs texte libre bornés à 200 caractères ASCII imprimable sans retour à la ligne, référence croisée des `finding_id` entre les deux fichiers). Un placeholder `{}` jamais édité par une phase en échec échoue de toute façon cette validation (clés requises absentes) — pas besoin d'un contrôle de présence de fichier séparé. La garantie de sécurité ne doit jamais reposer sur le bon vouloir du skill qui a produit le fichier — c'est le même principe déjà appliqué à l'étape de validation locale avant push (voir plus bas, garde-fou « Validation locale obligatoire avant push »).

Un échec de validation arrête le cycle **avant tout push** : aucune remédiation n'est appliquée, aucune phase suivante n'est invoquée. Voir « Traçabilité et échecs » ci-dessous.

---

## Garde-fous

| Garde-fou | Détail |
| --- | --- |
| **Working tree propre requis** | Si des modifications locales non committées existent, le script ne touche à rien (évite d'interférer avec un travail en cours). |
| **Branche à jour requise** | Si la branche locale est en retard/divergente par rapport à `origin`, le script s'arrête (pas de merge/rebase automatique). |
| **Rollback automatique** | Si le build Jenkins déclenché par un correctif automatique échoue à nouveau, `git revert` immédiat + push. |
| **Halte après rollbacks répétés** | Après `MAX_CONSECUTIVE_ROLLBACKS` (2) rollbacks consécutifs **post-push**, le statut passe à `halted` : plus aucune action tant qu'un humain ne réinitialise pas `~/.config/rhdemo-fixcve/state.json`. |
| **Halte après échecs pré-push répétés (symétrique)** | Après `MAX_CONSECUTIVE_PREPUSH_FAILURES` (2) échecs consécutifs **avant** tout push (schéma invalide en sortie de phase 1/2, ou absence de ligne de résultat exploitable pour une des 3 phases), même halte `status="halted"`, avec `reason:"max_consecutive_prepush_failures"` et `failing_stage` (`detect`/`lookup`/`apply`) dans l'événement `automation_halted`. Distinct du rollback : rien n'a été poussé, donc rien à `git revert`, juste un arrêt du pipeline. Le compteur `consecutive_prepush_failures` (`state.json`) est remis à zéro dès qu'un cycle va au bout proprement (correctif appliqué, ou `NO_ACTION` légitime) — voir « Traçabilité et échecs » ci-dessous. |
| **Critères objectifs pour toute suppression/acceptation de risque** | **Critère A (permanent)** : scope `test`/`provided`, OU RetireJS sur une lib JS non utilisée dans `frontend/src`, OU vecteur d'attaque `AV:L`/`AV:P` (accès physique/local), OU devDependency npm. **Critère B (temporaire)** : aucun correctif disponible et CVSS < 9.0 — suppression marquée `[PENDING_UPSTREAM_FIX]`, revérifiée à chaque cycle par `/fixcve-auto-lookup` (phase 2), remplacée par le vrai correctif dès qu'il sort. **CVSS ≥ 9.0 sans correctif** : seule exception restant hors périmètre — blocage documenté, `FIXCVE_AUTO_RESULT: NO_ACTION`, intervention manuelle requise. |
| **Revérification des exclusions temporaires (Critère B)** | À chaque cycle atteignant la phase 2, `/fixcve-auto-lookup` (étape 1 de son `SKILL.md`) scanne `owasp-suppressions.xml`/`.trivyignore.yaml` pour le jeton `[PENDING_UPSTREAM_FIX]` et revérifie Maven Central/npm pour chacune ; si un correctif est sorti, l'entrée est ajoutée à `pending_reverified` dans `lookup.json` et `/fixcve-auto-apply` (phase 3) applique le vrai correctif et retire l'exclusion. Ce mécanisme ne se déclenche que si le pipeline est réinvoqué (un build vert sur une CVE désormais supprimée ne relance plus le pipeline tant qu'aucune autre CVE ne fait échouer le build) — jugé suffisant vu la fréquence d'activation réelle sur ce projet (surface OWASP Dependency-Check large). |
| **Journal d'audit append-only** | `rhDemo/docs/fixcve-audit.jsonl`, versionné, une ligne JSON par événement (détection, échec de phase, application, validation, rollback, halte). |
| **Verrou anti-chevauchement** | `flock` sur `~/.config/rhdemo-fixcve/poll.lock` — un cycle CI (~2h max) ne peut pas se chevaucher avec le suivant. |
| **Anti-boucle blocage confirmé** | Après un `blocked_needs_human` (CVE bloquante sans correctif dispo), le script mémorise `blocked_confirmed.{since,source_sha}` dans `state.json`. Tant que le code source n'a pas changé (SHA du dernier commit hors `fixcve-audit.jsonl` identique) et que `BLOCKED_RECHECK_INTERVAL_SECONDS` (48h) n'est pas écoulé, les cycles suivants n'appellent pas Claude et ne committent/poussent rien — évite la boucle auto-entretenue commit→build Jenkins→nouveau commit observée sur les builds #735-#744 (aucune information nouvelle à chaque cycle, seul le push relançait le build suivant). |
| **Validation de schéma inter-phases** | Entre chaque invocation Claude, `fixcve-validate-json.py` (déterministe, aucun LLM) rejette tout fichier intermédiaire hors schéma strict (clés inconnues, valeurs hors regex/enum, référence croisée invalide) — voir « Séparation en 3 phases » ci-dessus. Aucune phase suivante n'est invoquée si la précédente échoue cette validation. |
| **Validation par SHA, pas par numéro de build** | Phase B (`pending_validation`) vérifie que `fix_commit_sha` est un ancêtre (ou égal) du commit réellement bâti par le build suivant (`git merge-base --is-ancestor`), pas seulement que son numéro est supérieur à `trigger_build_seen`. Jenkins déclenche un build sur **chaque** push (webhook/poll SCM) — un push sans rapport intercalé entre la publication du correctif et le cycle cron suivant (commit de documentation, PR Renovate...) produit un build qui n'est pas celui du correctif ; sans cette vérification, ce build intercalé est pris pour la validation et peut faire annuler un correctif jamais réellement testé. Incident constaté build #749→#750 (`ee1061c` poussé, mais le build examiné était bâti sur un commit de documentation poussé entre-temps — rollback d'un correctif jamais validé, 2e rollback consécutif → halte automatique). |
| **Validation locale obligatoire avant push** | `fixcve-auto-apply/SKILL.md` étape 3 : parse XML/YAML du fichier de suppression modifié (module `xml`/`yaml` Python) puis rejeu local de `./mvnw org.owasp:dependency-check-maven:check`, comparé à la liste consolidée de `detected.json`, avant tout `git commit`/`git push`. Incident constaté builds #759→#760 puis #761→#762 : un premier correctif (build #759) traitait des CVE DOMPurify déjà suppressées sans traiter le CVE réellement bloquant (`postcss:7.0.39`/CVE-2026-45623) ; le correctif suivant (build #761) a introduit un commentaire XML contenant `--` (interdit par la spec XML sauf en clôture `-->`) dans `owasp-suppressions.xml`, rendant tout le fichier illisible par `dependency-check-maven` et faisant réapparaître en échec toutes les suppressions déjà validées — 2 rollbacks consécutifs → halte automatique. Un simple parse local (quelques secondes) aurait détecté les deux avant push, sans attendre un cycle Jenkins complet (~15+ min) suivi d'un rollback. Ce rejeu utilise le cache NVD de l'hôte (`~/.m2/dependency-check-data`, `pom.xml` : `<dataDirectory>${user.home}/.m2/dependency-check-data</dataDirectory>`) — **distinct** de celui de Jenkins (volume Docker `rhdemo-jenkins-home`, non partagé, avec clé API NVD injectée que l'hôte n'a pas) : fiable pour confirmer que le correctif couvre les CVE visées et ne casse rien, mais pas une simulation identique au scan Jenkins seconde près ; la validation Phase B (Jenkins) reste le filet de sécurité final. |
| **Aucun commentaire XML `<!-- -->` libre pour les suppressions** | Toute justification, même longue, va dans `<notes>` (contenu XML normal, jamais interprété comme commentaire) — jamais dans un bloc `<!-- ... -->` séparé, où un `--` littéral (ex. une commande `npm ... --force` citée dans le texte) casse le parsing de tout le fichier. Voir incident ci-dessus. |
| **Journalisation de la cause réelle d'un rollback** | Phase B enrichit l'événement `validation_failed_rollback` avec `failure_stage` (premier stage Jenkins en échec) et `failure_detail` (extrait des lignes `[ERROR]` de `consoleText`), au lieu de se limiter à `commit`/`revert_commit`. Avant ce garde-fou, un post-mortem devait ressortir les logs Jenkins bruts à la main (constaté lors de l'analyse des rollbacks builds #760/#762). |

---

## Points d'attention

⚠️ Ce document décrit une automatisation qui **committe et pousse du code sur la branche courante sans revue humaine**, y compris des décisions d'acceptation de risque (suppression de CVE). C'est un choix assumé en échange des garde-fous ci-dessus — à désactiver si ces garde-fous ne sont plus jugés suffisants pour le contexte du moment (ex: montée en criticité du projet).

⚠️ **Surface d'injection de prompt** : les phases 2 et 3 parsent du contenu externe non fiable (réponses Maven Central/npm pour la phase 2 ; fichiers déjà structurés et validés pour la phase 3). La phase 1 (détection) est un script déterministe sans LLM (voir « Séparation en 3 phases » ci-dessus) : elle parse aussi du contenu externe (rapports Trivy/OWASP), mais aucune injection de prompt n'y a de prise puisqu'aucun modèle n'y "lit" quoi que ce soit. Pour les phases 2/3, ce contenu n'est jamais lu par la même invocation Claude que celle qui détient les credentials git — chaque phase a son propre fichier `permissions.allow` versionné ([`fixcve-auto-lookup-permissions.json`](../scripts/fixcve-auto-lookup-permissions.json), [`fixcve-auto-apply-permissions.json`](../scripts/fixcve-auto-apply-permissions.json)), strictement plus étroit que l'ancien fichier unique. Toute commande ou fichier hors de la liste de la phase courante est refusé sans prompt (`--permission-mode dontAsk`). Ce scoping s'ajoute aux garde-fous **git** ci-dessus (working tree propre, rollback automatique, halte après rollbacks) et à la validation de schéma inter-phases, qui restent la protection de dernier recours si une commande scoping-compatible était malgré tout détournée.

⚠️ **`Bash(python3:*)` reste un joker complet dans les phases 2 et 3** (celles qui invoquent Claude) : c'est la limite la plus sérieuse du modèle de permissions actuel. Le moteur de permissions de Claude Code ne matche que le *texte* de la commande Bash (`python3 ...`) — il ne regarde jamais ce que le script fait une fois lancé. Un script Python peut donc faire des appels réseau vers n'importe quel hôte (contournant entièrement les wrappers dédiés à `curl`), ou lire n'importe quel fichier accessible à l'utilisateur Unix qui exécute le cron — y compris `~/.config/rhdemo-fixcve/jenkins.netrc` — sans passer par l'outil `Read` de Claude Code ni par aucune règle `permissions.allow`. Sans objet pour la phase 1 : `python3` y est bien utilisé, mais dans un script versionné qu'on a écrit et relu nous-mêmes, jamais composé à la volée par un LLM potentiellement influencé par du contenu externe.

Ce point a été comparé à dessein à l'option inverse (autoriser `Read` sur le rapport brut plutôt que de forcer un parsing Python complet) : **`python3` sans restriction est le facteur dominant, pas `Read`**. Le champ le plus sensible à l'injection (titre/description de CVE) atteint de toute façon le contexte du modèle via la sortie du script Python qu'il écrit lui-même pour l'extraire — bloquer `Read` réduit l'exposition au reste du document (les dizaines de milliers de lignes non pertinentes) et améliore la fiabilité du parsing (évite l'exploration ad hoc par lignes ciblées, source d'oublis), mais ne change pas le plafond de dégâts en cas d'injection réussie. Ce plafond est fixé par ce que peut faire l'utilisateur Unix du cron, pas par les outils Claude Code explicitement autorisés — un script Python malveillant a le même pouvoir que `Bash(curl:*)` aurait eu avant l'introduction des wrappers dédiés, voire plus (accès fichier en plus du réseau).

**Limite assumée pour l'instant** : réduire ce risque demanderait un confinement au niveau OS (utilisateur dédié sans droits sur les credentials, absence d'accès réseau sortant pour ce process, sandbox `bubblewrap`/`firejail`/seccomp autour de l'invocation Python) — hors de portée du moteur de permissions de Claude Code lui-même, qui ne peut pas inspecter l'intérieur d'un interpréteur qu'il lance. C'est le même compromis que celui déjà accepté pour le clone isolé (voir plus bas : « aucun confinement réseau ni noyau, contrairement à une microVM, option plus lourde restée hors scope »). La séparation en 3 phases et les wrappers dédiés ferment les vecteurs d'injection les plus simples et structurés (curl vers un hôte arbitraire, push git) mais ne ferment pas celui-ci, qui n'a jamais été fermé avant comme après ce refactor — python3 étant indispensable au parsing JSON/HTML des rapports.

⚠️ **Limite du scoping par préfixe** : la règle `Bash(frontend/node/npm --prefix frontend audit:*)` (phase 3, `fixcve-auto-apply`) autorise aussi bien `npm audit fix --package-lock-only` (voulu) que `npm audit fix --force` (interdit par consigne dans `SKILL.md`, jamais par le moteur de permissions lui-même — un préfixe `allow` ne peut pas exclure un flag précis). Le blocage de `--force` repose donc uniquement sur le respect de la consigne par le modèle, pas sur une barrière technique. Ce risque reste présent en phase 3 mais son exposition a diminué : la phase 3 ne lit plus de contenu externe brut (seulement les fichiers structurés déjà validés des phases 1/2), donc une description de CVE malveillante ne peut plus l'atteindre directement — il faudrait qu'elle passe d'abord par la phase 2 puis survive à la validation de schéma stricte (aucun champ texte libre exploitable dans `lookup.json`, voir « Séparation en 3 phases »). La phase 2, elle, utilise volontairement la règle plus étroite `Bash(frontend/node/npm --prefix frontend audit --json:*)` (lecture seule, ne matche pas `audit fix`). Les garde-fous git (rollback automatique après échec du build suivant) restent la protection de dernier recours si ça arrivait malgré tout.

⚠️ **`npm` absent du `PATH` sous cron** : constaté sur le build #715 (`npm : commande introuvable`, `blocked_needs_human` sur 39 CVE). Le `PATH` minimal de cron ne source aucun profil shell, donc un `npm` installé via nvm (disponible en session interactive) n'est pas résolu par les skills. Les `SKILL.md` et les fichiers `fixcve-auto-*-permissions.json` utilisent donc le binaire `frontend/node/npm` (téléchargé par `frontend-maven-plugin`, chemin littéral dans le dépôt, indépendant du `PATH`) plutôt qu'un `npm` nu.

⚠️ **Exception assumée — npm et Docker gardent un accès réseau natif en phase 3** : contrairement à Maven (où la phase 3 se contente d'écrire une version déjà résolue par la phase 2 dans `pom.xml`, sans appel réseau), `npm audit fix --package-lock-only`/`npm install ... --package-lock-only` doivent recalculer eux-mêmes les hachages d'intégrité du lockfile au moment de l'application — impossible à pré-résoudre hors ligne en phase 2. Le digest Docker, lui, **est** entièrement pré-résolu par la phase 2 (`target_digest` dans `lookup.json`) : la phase 3 n'appelle plus `docker manifest inspect`. Le risque résiduel de l'appel npm en phase 3 est jugé acceptable : c'est un outil natif qui fait sa propre I/O réseau, et le LLM ne lit jamais la réponse brute du registre npm (seulement un diff de fichier ou un message de succès/échec), contrairement à un `curl` dont la réponse serait lue comme texte dans le contexte du modèle — la différence de risque n'est pas « réseau ou pas », mais « le LLM lit-il du texte non maîtrisé dans son contexte ».

⚠️ **`Bash(git restore:*)`** : ajouté après le build #718, où un `npm install <package>@<version>` sans `--save-dev` a ajouté à tort une dépendance transitive (`brace-expansion`, saut de version majeure 1.x→5.x) dans `dependencies` de production. Le skill a correctement voulu annuler sa propre erreur (`git restore`) mais n'en avait pas le droit, laissant l'arbre de travail sale — ce qui aurait bloqué tous les cycles cron suivants (garde-fou « arbre non propre ») jusqu'à intervention manuelle. `git restore` ne peut annuler que des modifications non committées (jamais l'historique), scope volontairement plus étroit que `git checkout`.

⚠️ **`packageUrl` trop étroit sur une CVE à CPE générique** : constaté build #746 → #748. `CVE-2026-66299` (Tomcat) était identifiée par OWASP DC via une CPE générique vendor/produit (`cpe:2.3:a:apache:tomcat:...`), pas un Package URL exact. La suppression du build #746 l'a scopée à `tomcat-embed-core` (seul jar visible dans le rapport à ce moment) ; au scan suivant, la même CVE s'est réattachée à un jar frère, `tomcat-embed-websocket` (même `groupId` `org.apache.tomcat.embed`), faisant échouer le build #748 et déclenchant un rollback qui a annulé l'intégralité du commit #746 — y compris les correctifs sans rapport (springdoc, jackson-databind, log4j-api, autres suppressions Critère A), tous corrects. `SKILL.md` (Priorité 2, format de suppression) demande désormais de scoper `<packageUrl regex="true">` au `groupId` Maven entier plutôt qu'à l'`artifactId` observé, quand la CVE provient d'une correspondance CPE générique.

⚠️ **Pin npm manuel sans être passé par le lot d'abord** : constaté build #752 → #753. Correctif de `CVE-2026-69152` (`brace-expansion`) via un pin manuel isolé (`frontend/package.json`) plutôt que `npm audit fix --package-lock-only` en lot. Une CVE `fast-uri` (HIGH), publiée entre le scan du build #752 et celui du #753, n'a donc pas été couverte — alors que le lot `audit fix` la corrige collatéralement (constaté aussi bien au build #744 qu'au #754). Rollback du build #753 (correctif jamais fautif en lui-même, juste incomplet). `SKILL.md` (Priorité 1, remédiation npm) rend désormais l'exécution du lot `audit fix` **obligatoire** avant tout pin manuel, même quand une seule CVE npm semble concernée sur le rapport analysé.

Historique : la conception initiale utilisait déjà `dontAsk` + `permissions.allow`, mais ce mode refusait alors *toute* commande Bash réseau même avec une règle d'autorisation explicite (bug observé et documenté sur Claude Code `2.1.205`), forçant un contournement temporaire via `--dangerously-skip-permissions` (aucun scoping). Ce bug a été vérifié empiriquement comme résolu sur Claude Code `2.1.220` — le scoping normal a été rétabli.

⚠️ **Clone git isolé (depuis le 2026-08-20)** : `fixcve-auto` opère sur un clone git séparé
(`~/fixcve-worktrees/rhdemo`, `chmod 700`), **jamais** sur la copie de travail principale — voir
section « Clone isolé » ci-dessous (prérequis d'installation). Objectif : si une commande
échappait malgré tout au scope `permissions.allow` (bug du moteur `dontAsk` comme ci-dessus, ou
injection de prompt via un rapport CVE/Trivy malveillant — voir « Surface d'injection de prompt »
plus haut dans ce chapitre), le rayon d'action reste confiné au code RHDemo plutôt que d'atteindre
tout `$HOME` (clés SSH, autres dépôts, historique shell...). Le clone suit dynamiquement la
branche active de la copie de travail principale à chaque cycle (jamais une branche figée), donc
aucune resynchronisation manuelle n'est nécessaire à une coupure de release.

Deux limites à connaître : (1) les commits automatiques (remédiation, rollback, halte)
n'apparaissent plus instantanément dans `git log`/`git status` de votre session interactive —
faire `git fetch`/`git pull` dans la copie principale pour les voir ; (2) ce clone ne protège
**pas** les credentials du mécanisme (`~/.config/rhdemo-fixcve/`), volontairement partagés avec
le clone car nécessaires à son fonctionnement — ils restent atteignables de la même façon
qu'avant en cas d'évasion. Aucun confinement réseau ni noyau non plus (contrairement à une
microVM, option plus lourde restée hors scope pour l'instant).

⚠️ **Comportement à connaître (toujours vrai sur `2.1.220`, distinct du bug ci-dessus)** : sous `dontAsk`, une commande Bash contenant une expansion de variable shell (`${VAR}`) est refusée **même si son préfixe correspond à une règle `allow`** — ex. `Bash(curl:*)` ne matche pas `curl -sf -u "${JENKINS_USER}:${JENKINS_TOKEN}" ...`, alors que la même commande avec des valeurs littérales passe. Vérifié empiriquement le 2026-07-29 (build Jenkins #709/#710, `permission_denials` dans la sortie `--output-format json`) : c'est ce qui bloquait le premier appel curl de chaque exécution du pipeline, quelle que soit la commande. Contournement retenu : `rhDemo/scripts/fixcve-auto-poll.sh` régénère à chaque cycle `/home/leno-vo/.config/rhdemo-fixcve/jenkins.netrc` (chemin littéral, `chmod 600`) à partir des identifiants déchiffrés, et le wrapper [`fixcve-jenkins-fetch.sh`](../scripts/fixcve-jenkins-fetch.sh) utilise en interne `curl --netrc-file /home/leno-vo/.config/rhdemo-fixcve/jenkins.netrc` (chemin statique, aucune variable dans le texte de la commande vue par le modèle — celui-ci ne fournit qu'un chemin Jenkins, jamais le netrc lui-même) au lieu de `-u "${JENKINS_USER}:${JENKINS_TOKEN}"`. Le mécanisme `GIT_ASKPASS` pour `git push` n'est pas concerné : la substitution s'y fait à l'intérieur du script `git-askpass.sh`, jamais dans le texte de la commande vue par Claude.

---

## Prérequis d'installation

### 1. Outils

`jq`, `sops`, `yq`, `flock`, `curl`, `git`, `claude` (Claude Code CLI) disponibles dans le `PATH` de l'utilisateur cron.

### 2. Clé AGE personnelle

Doit déjà exister (utilisée par ailleurs pour les secrets du projet) :

```bash
ls -la ~/.config/sops/age/keys.txt
```

### 3. Credentials chiffrés : `~/.config/rhdemo-fixcve/credentials.sops.yaml`

Ce fichier vit **hors du dépôt git**, chiffré avec votre clé AGE personnelle (donc lisible uniquement sur cette machine, avec cette clé). Il contient :

- le compte Jenkins dédié à l'automatisation (`claude`, **pas** `admin` — voir `.claude/skills/fixcve/SKILL.md`),
- un token Codeberg **dédié et restreint à ce seul dépôt** (fine-grained access token, scope écriture sur `rhdemo` uniquement — ne pas réutiliser un token à portée large).

À chaque cycle, `fixcve-auto-poll.sh` régénère à partir de ce fichier `~/.config/rhdemo-fixcve/jenkins.netrc` (`chmod 600`, jamais versionné) — c'est ce fichier, pas les identifiants Jenkins directement, que `curl --netrc-file` utilise dans le skill (voir l'encadré sur `dontAsk` et les expansions de variable ci-dessus).

**Compte Codeberg dédié (`fixcvebot-leuwen-lc`), pas le compte personnel.** Le token doit provenir
d'un compte bot séparé, ajouté comme collaborateur **Write** (pas Admin) sur `leuwen-lc/rhdemo` —
pas du compte personnel `leuwen-lc`, même avec un token scope-limité. Raisons, plus marquées ici
que pour les autres automatisations du projet :
- `fixcve-auto` parse du contenu externe non fiable (descriptions de CVE, rapports Trivy/OWASP)
  — voir « Surface d'injection de prompt » dans « Points d'attention » ci-dessus. Le scope d'outils
  (`permissions.allow`) limite déjà `git push` à ce dépôt, mais le scope du token reste une
  deuxième limite indépendante si une commande `git push` malveillante était malgré tout exécutée.
- **Distinct aussi de `rhdemo-ci-bot`** (compte bot dédié au merge des PRs Renovate — voir
  [`RENOVATE_AUTOMERGE_CI.md`](RENOVATE_AUTOMERGE_CI.md)). Les deux ont le même niveau d'accès
  (write sur `rhdemo`), mais un profil de risque très différent : appels curl/git déterministes
  d'un côté, agent LLM à outils scopés sur du contenu non fiable de l'autre. En cas de commit
  suspect, distinguer immédiatement "quelle automatisation" accélère le triage d'incident.
- Email du compte bot : un alias Gmail `+` (ex. `leuwenlc+fixcvebot@gmail.com`) fonctionne pour
  l'inscription (Codeberg n'exige qu'une adresse unique par compte, pas un domaine distinct), au
  prix d'une récupération de compte qui reste liée à la même boîte mail que le compte personnel.

**Prérequis avant de générer le token :**
1. Créer le compte `fixcvebot-leuwen-lc` sur `https://codeberg.org` (email dédié ou alias `+`).
2. L'ajouter comme collaborateur de `leuwen-lc/rhdemo` avec la permission **Write** (Settings >
   Collaborators) — jamais Admin.
3. Se connecter avec ce compte et générer un fine-grained access token sur
   `https://codeberg.org/user/settings/applications`, scope écriture restreint à `rhdemo`.
4. Si la branche cible est protégée (Settings > Branches), ajouter `fixcvebot-leuwen-lc` à la
   whitelist de push de la règle correspondante — sinon `git push` est rejeté.

Création :

```bash
mkdir -p ~/.config/rhdemo-fixcve && chmod 700 ~/.config/rhdemo-fixcve

cat > /tmp/fixcve-creds-plain.yaml <<'EOF'
jenkins:
  user: claude
  token: METTRE_LE_VRAI_TOKEN_JENKINS_ICI
codeberg:
  user: fixcvebot-leuwen-lc
  token: METTRE_LE_VRAI_TOKEN_CODEBERG_ICI
EOF

RECIPIENT=$(grep "public key:" ~/.config/sops/age/keys.txt | awk '{print $NF}')
SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops --encrypt --age "${RECIPIENT}" \
  /tmp/fixcve-creds-plain.yaml > ~/.config/rhdemo-fixcve/credentials.sops.yaml

shred -u /tmp/fixcve-creds-plain.yaml   # ne jamais laisser le clair sur disque

chmod 600 ~/.config/rhdemo-fixcve/credentials.sops.yaml
```

Vérification (affiche le déchiffré sans rien écrire sur disque) :

```bash
SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops -d ~/.config/rhdemo-fixcve/credentials.sops.yaml
```

Le token Jenkins doit être un token **régénéré** si une ancienne valeur a pu fuiter (ex: fichier de config local en clair) — révoquer l'ancien dans Jenkins avant de créer le nouveau.

**Migration depuis l'ancien token personnel** : si `credentials.sops.yaml` contient encore
`codeberg.user: leuwen-lc`, régénérer le fichier avec la commande ci-dessus une fois le compte
`fixcvebot-leuwen-lc` créé, puis révoquer l'ancien token sur
`https://codeberg.org/user/settings/applications` (compte personnel).

### 4. `GIT_ASKPASS`

Déjà en place : `~/.config/rhdemo-fixcve/git-askpass.sh` (aucun secret dedans, lit `CODEBERG_USER`/`CODEBERG_TOKEN` depuis l'environnement au moment du push).

### 5. Clone git isolé

`fixcve-auto` opère sur un clone séparé de la copie de travail principale (`REPO_DIR` dans
`fixcve-auto-poll.sh`), jamais celle-ci directement — voir l'encadré dans « Points d'attention » ci-dessus.
Création, une seule fois :

```bash
mkdir -p ~/fixcve-worktrees
git clone "$(git -C /home/leno-vo/git/repository remote get-url origin)" ~/fixcve-worktrees/rhdemo
chmod 700 ~/fixcve-worktrees/rhdemo

cd ~/fixcve-worktrees/rhdemo
git checkout "$(git -C /home/leno-vo/git/repository rev-parse --abbrev-ref HEAD)"
```

`.claude/` (skills, dont `fixcve-auto-lookup`/`fixcve-auto-apply` — la phase 1
n'en a plus besoin, c'est un script déterministe) est **volontairement
gitignored** dans ce dépôt (`.gitignore` : « peut être vecteur d'injections »,
resté local plutôt que versionné) — un `git clone` classique ne le copie donc
pas. Sans lui, l'invocation `claude -p` de la phase 2 échouerait dès le
premier cycle (skill introuvable). Un symlink vers la copie principale garde
le clone isolé automatiquement à jour de toute évolution des skills, sans
étape de resynchronisation manuelle :

```bash
ln -s /home/leno-vo/git/repository/.claude ~/fixcve-worktrees/rhdemo/.claude
```

⚠️ Le pattern `.claude/` du `.gitignore` (avec `/` final) ne matche que les **répertoires réels**,
pas un symlink pointant vers un répertoire — sans correction, ce symlink apparaîtrait comme
fichier non suivi (`?? .claude` dans `git status --porcelain`) et déclencherait à tort le
garde-fou « arbre de travail non propre » à chaque cycle, bloquant l'automatisation en
permanence. Correction locale au clone (`.git/info/exclude`, jamais versionné, sans impact sur
la copie principale ni sur le dépôt distant) :

```bash
echo ".claude" >> ~/fixcve-worktrees/rhdemo/.git/info/exclude
```

Vérification : `git -C ~/fixcve-worktrees/rhdemo status --porcelain` ne doit rien afficher.

Provisionnement de `frontend/node`/`node_modules` (téléchargé par `frontend-maven-plugin`, requis
par `SKILL.md` Priorité 1 — un clone git frais ne les contient pas, contrairement à un cache
global) :

```bash
cd ~/fixcve-worktrees/rhdemo/rhDemo
./mvnw -q generate-resources
```

Vérification :

```bash
~/fixcve-worktrees/rhdemo/rhDemo/frontend/node/npm --version
```

Le clone suit ensuite automatiquement la branche active de la copie de travail principale à
chaque cycle (`fixcve-auto-poll.sh` lit `git -C REPO_DIR_MAIN rev-parse --abbrev-ref HEAD` et
bascule le clone dessus si besoin, y compris à une coupure de release) — pas de resynchronisation
manuelle nécessaire, sauf reprovisionnement npm/node si un futur `package.json` introduit des
dépendances significativement différentes (rare).

### 6. Identité des commits automatiques (`GIT_AUTHOR_*`/`GIT_COMMITTER_*`)

`REPO_DIR` (`fixcve-auto-poll.sh`) pointe sur le clone isolé ci-dessus, pas sur la copie de
travail principale — un `git config user.name/email` local à ce clone n'affecterait donc plus vos
commits manuels de toute façon. `fixcve-auto-poll.sh` exporte quand même `GIT_AUTHOR_NAME`,
`GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` plutôt que `git config` — aucun
inconvénient, et ça reste sûr par construction si `REPO_DIR` redevenait un jour la copie
principale. Ces variables d'environnement ne s'appliquent qu'aux commits faits par ce process (et
par le sous-processus `claude -p` qu'il invoke, qui les hérite). Résultat : les commits de
`fixcve-auto-poll.sh` et ceux appliqués par `/fixcve-auto` (upgrade de version, suppression de
CVE) apparaissent sous l'identité `RHDemo FixCVE Bot`, distincte de vos commits manuels et de
`RHDemo CI Bot` (Renovate).

### 7. Installation du cron

**Ne pas installer sans avoir relu `rhDemo/scripts/fixcve-auto-poll.sh` et compris les garde-fous ci-dessus.**

```bash
crontab -e
```

Ajouter :

```cron
*/15 * * * * /home/leno-vo/git/repository/rhDemo/scripts/fixcve-auto-poll.sh >> /home/leno-vo/.config/rhdemo-fixcve/poll.log 2>&1
```

### 8. Rotation de `poll.log`

`poll.log` est alimenté à chaque cycle (toutes les 15 min) et grossirait indéfiniment sans rotation. Config `logrotate` en espace utilisateur (pas de `sudo` requis), déjà en place : `~/.config/rhdemo-fixcve/logrotate.conf` (hebdomadaire, 4 générations conservées compressées, taille max 10 Mo).

Ligne cron associée (exécution quotidienne à 3h) :

```cron
0 3 * * * /usr/sbin/logrotate --state /home/leno-vo/.config/rhdemo-fixcve/logrotate.state /home/leno-vo/.config/rhdemo-fixcve/logrotate.conf
```

---

## Désactivation / pause

```bash
crontab -e   # supprimer ou commenter la ligne fixcve-auto-poll.sh
```

Ou, sans toucher au cron, forcer une halte immédiate :

```bash
jq '.status="halted"' ~/.config/rhdemo-fixcve/state.json > /tmp/s.json && mv /tmp/s.json ~/.config/rhdemo-fixcve/state.json
```

## Reprise après une halte manuelle

Après avoir traité manuellement la cause des rollbacks ou des échecs pré-push répétés (visible dans `rhDemo/docs/fixcve-audit.jsonl`, événements `automation_halted` — le champ `reason` distingue `max_consecutive_rollbacks` de `max_consecutive_prepush_failures`, et `failing_stage` indique la phase en cause pour ce second cas) :

```bash
jq '.status="idle" | .consecutive_rollbacks=0 | .consecutive_prepush_failures=0' ~/.config/rhdemo-fixcve/state.json > /tmp/s.json && mv /tmp/s.json ~/.config/rhdemo-fixcve/state.json
```

## Forcer une revérification immédiate d'un blocage confirmé

Un `blocked_needs_human` (CVE sans correctif dispo) n'est réévalué qu'après `BLOCKED_RECHECK_INTERVAL_SECONDS`
(48h) tant que le code source n'a pas changé (voir garde-fou « Anti-boucle blocage confirmé »
ci-dessus). Pour forcer une revérification dès le prochain cycle cron (ex : vous savez qu'un
correctif upstream vient de sortir, sans avoir encore touché au code) :

```bash
jq '.blocked_confirmed=null' ~/.config/rhdemo-fixcve/state.json > /tmp/s.json && mv /tmp/s.json ~/.config/rhdemo-fixcve/state.json
```

Inutile après un vrai changement de code (upgrade manuel, suppression ajoutée à
`owasp-suppressions.xml`...) : le SHA source ne correspond alors plus à `blocked_confirmed.source_sha`,
la revérification est automatique dès le cycle suivant.

## Lecture des logs

Deux fichiers distincts, deux usages différents :

- **`~/.config/rhdemo-fixcve/poll.log`** — sortie brute (stdout/stderr) de **chaque** exécution du cron, toutes les 15 min, y compris les cycles où rien ne se passe. Utile pour vérifier que le cron tourne bien :

  ```bash
  tail -f ~/.config/rhdemo-fixcve/poll.log
  ```

- **`rhDemo/docs/fixcve-audit.jsonl`** — uniquement les événements notables (remédiation appliquée, build hors périmètre, validation, rollback, halte). Versionné dans git, source de vérité append-only.
- **`rhDemo/docs/fixcve-audit.md`** — vue lisible pour un humain, régénérée automatiquement à partir du `.jsonl` par `rhDemo/scripts/fixcve-audit-render.sh` (déterministe, pas de LLM) à chaque nouvel événement, entrée la plus récente en tête. Ne pas éditer à la main — toute modification est écrasée au prochain cycle.

## Lecture du journal d'audit

Pour un humain, ouvrir directement `rhDemo/docs/fixcve-audit.md`. Pour un traitement programmatique, la source de vérité reste le `.jsonl` :

```bash
cat rhDemo/docs/fixcve-audit.jsonl | jq .
# Uniquement les rollbacks :
jq 'select(.event == "validation_failed_rollback")' rhDemo/docs/fixcve-audit.jsonl
# Uniquement les acceptations de risque temporaires (Critère B, en attente de correctif) :
jq 'select(.event == "risk_accepted_pending_upstream_fix")' rhDemo/docs/fixcve-audit.jsonl
```

Régénérer manuellement la vue lisible si besoin (ex: après une modification directe du `.jsonl`) :

```bash
rhDemo/scripts/fixcve-audit-render.sh
```

## Traçabilité et échecs du pipeline 3 phases

Principe : c'est toujours `fixcve-auto-poll.sh` (déterministe) qui journalise un
échec de phase — jamais le skill en échec lui-même, qui pourrait être celui
compromis. Seule la phase 3 (`fixcve-auto-apply`, qui détient les droits git)
journalise elle-même ses événements de remédiation substantielle
(`remediation_applied`, `risk_accepted_pending_upstream_fix`,
`pending_fix_resolved`, `blocked_needs_human`), exactement comme dans l'ancien
skill monolithique.

**Nouveaux événements** (en plus de ceux déjà existants avant la séparation en
3 phases) :

| Événement | Écrit par | Quand |
| --- | --- | --- |
| `detect_phase_failed` | `fixcve-auto-poll.sh` | Phase 1 (`fixcve-detect.py`) : pas de ligne `FIXCVE_DETECT_RESULT` exploitable, ou `detected.json` rejeté par le validateur de schéma — y compris le cas où le script plante avant d'écrire quoi que ce soit et laisse le placeholder `{}` intact (`reason` : `no_result_line`, `schema_invalid` avec `detail` tronqué à ~1200 caractères) |
| `lookup_phase_failed` | `fixcve-auto-poll.sh` | Phase 2 : même logique, sur `lookup.json` (`reason` inclut aussi une référence croisée invalide vers `detected.json`) |
| `automation_halted` (`reason:"max_consecutive_prepush_failures"`) | `fixcve-auto-poll.sh` | `MAX_CONSECUTIVE_PREPUSH_FAILURES` échecs pré-push consécutifs (sur des builds distincts) — voir « Halte après échecs pré-push répétés » dans les garde-fous |

Un échec en phase 1 ou 2 (ou une validation de schéma ratée) survient
**avant tout commit de correctif** : il n'y a donc rien à `git revert`, juste
un cycle qui s'arrête et se journalise (`last_processed_build` est quand même
avancé — pas de nouvelle tentative automatique sur le même build, un échec de
schéma systématique n'a aucune raison de disparaître 15 minutes plus tard). Le
mécanisme de rollback (`consecutive_rollbacks`) reste exclusivement pour la
Phase B, après un vrai push de correctif.

Un crash pur du process `claude -p` (réseau, API — distinct d'un résultat
produit mais invalide) n'incrémente aucun des deux compteurs et n'avance pas
`last_processed_build` : nouvelle tentative complète au cycle cron suivant.

**Fichiers de cycle conservés pour le post-mortem** : `detected.json` et
`lookup.json` ne sont jamais écrasés silencieusement en cas d'échec — ils sont
copiés dans `~/.config/rhdemo-fixcve/cycle/archive/<build>-{detected,lookup}[-invalid].json`
avant d'être nettoyés pour le cycle suivant (purge automatique au-delà des
`CYCLE_ARCHIVE_RETENTION` fichiers les plus récents — ce répertoire n'est pas
versionné, contrairement à `fixcve-audit.jsonl`). C'est le fichier exact que le
validateur a rejeté, utile pour comprendre pourquoi sans attendre de
reproduire le cycle.

**`poll.log`** reste la seule trace des 3 invocations `claude -p` en texte
brut (stdout/stderr complet) — avec 3 appels par cycle au lieu d'un seul, `log
"..."` précède chaque invocation pour distinguer facilement quelle phase a
produit quelle sortie lors d'un `grep`/`tail -f`.

## Évolution future : exécution via Jenkins plutôt que cron local

Alternative envisageable si le besoin se présente (plusieurs machines, survie à l'arrêt du PC de dev) : héberger l'automatisation dans Jenkins plutôt que sur un cron local. Ce n'est **pas un simple portage**, à évaluer avant de s'engager :

- **Installer Claude Code (+ Node.js) dans l'image `infra/jenkins-docker/`** — dépendance absente aujourd'hui, à maintenir sur un système pensé pour rester léger (1 PC, 16 Go).
- **Migrer les credentials de SOPS/AGE local vers le Credentials Store Jenkins** — gain réel : réutilise le pattern déjà en place dans `Jenkinsfile-CI` (`SOPS_AGE_KEY = credentials('sops-age-key-ephemere')`), plus cohérent que le fichier chiffré local actuel.
- **Remplacer le polling par un `post { failure { ... } }` dans `Jenkinsfile-CI`**, déclenchant un job dédié (`RHDemo-fixcve-auto`) avec build number + type de stage en paramètres. Gain principal : Jenkins sait *nativement* quel stage a échoué, ce qui élimine la détection fragile par `wfapi/describe` (cause du bug de classification trivy/owasp rencontré lors de la mise en service — un échec précoce faisait passer des stages en aval, dont un nommé "Trivy", en non-SUCCESS).
- **Réécrire la machine à états (idle/pending_validation/halted)** — pas d'équivalent trivial à `state.json` local ; nécessiterait un fichier d'état sur volume persistant Jenkins, ou un marqueur dans les commits automatiques (ex: trailer `Fixcve-Auto: true`) pour détecter la validation au build suivant.

Coût principal : toucher `Jenkinsfile-CI` (pipeline critique déjà volumineux) et réimplémenter en Groovy une logique aujourd'hui simple et auditable en bash. À ne migrer que si un besoin concret l'exige, pas par principe.

## Voir aussi

- [`.claude/skills/fixcve/SKILL.md`](../../.claude/skills/fixcve/SKILL.md) — version interactive avec validation humaine
- [`fixcve-detect.py`](../scripts/fixcve-detect.py) — phase 1/3, détection (script déterministe, aucun LLM)
- [`.claude/skills/fixcve-auto-lookup/SKILL.md`](../../.claude/skills/fixcve-auto-lookup/SKILL.md) — phase 2/3, recherche de correctif
- [`.claude/skills/fixcve-auto-apply/SKILL.md`](../../.claude/skills/fixcve-auto-apply/SKILL.md) — phase 3/3, application/commit/push
- [`fixcve-validate-json.py`](../scripts/fixcve-validate-json.py) — validateur de schéma déterministe entre les phases
- [SECURITY_ADVISORIES.md](SECURITY_ADVISORIES.md) — historique des CVE traitées (manuel et automatique)
- [SOPS_SETUP.md](SOPS_SETUP.md) — installation SOPS/AGE
