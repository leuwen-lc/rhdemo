# Remédiation CVE automatisée (fixcve-auto)

Automatisation complète de la remédiation des CVE bloquantes détectées par Trivy ou OWASP Dependency-Check dans le pipeline `RHDemo-CI`, **sans validation humaine**. Complète le skill interactif `/fixcve` (`.claude/skills/fixcve/SKILL.md`) qui reste disponible pour un usage manuel.

---

## Architecture

```text
crontab (toutes les 15 min)
   └─> rhDemo/scripts/fixcve-auto-poll.sh   (bash + jq + curl, PAS de LLM)
         │
         ├─ Phase A (idle) : détecte un nouveau build Jenkins en échec Trivy/OWASP
         │     └─ invoque : claude -p "/fixcve-auto <build> <trivy|owasp>"
         │           (.claude/skills/fixcve-auto/SKILL.md — remédiation + commit + push)
         │
         └─ Phase B (pending_validation) : vérifie le build CI suivant
               ├─ SUCCESS  → marque résolu
               └─ FAILURE  → git revert automatique + halte après 2 rollbacks consécutifs
```

Le polling lui-même ne fait **aucun appel LLM** — Claude Code n'est invoqué que pour la remédiation proprement dite (parsing des rapports, recherche de correctif, rédaction de suppression, édition de fichiers).

---

## Garde-fous

| Garde-fou | Détail |
| --- | --- |
| **Working tree propre requis** | Si des modifications locales non committées existent, le script ne touche à rien (évite d'interférer avec un travail en cours). |
| **Branche à jour requise** | Si la branche locale est en retard/divergente par rapport à `origin`, le script s'arrête (pas de merge/rebase automatique). |
| **Rollback automatique** | Si le build Jenkins déclenché par un correctif automatique échoue à nouveau, `git revert` immédiat + push. |
| **Halte après rollbacks répétés** | Après `MAX_CONSECUTIVE_ROLLBACKS` (2) rollbacks consécutifs, le statut passe à `halted` : plus aucune action tant qu'un humain ne réinitialise pas `~/.config/rhdemo-fixcve/state.json`. |
| **Critères objectifs pour toute suppression/acceptation de risque** | **Critère A (permanent)** : scope `test`/`provided`, OU RetireJS sur une lib JS non utilisée dans `frontend/src`, OU vecteur d'attaque `AV:L`/`AV:P` (accès physique/local), OU devDependency npm. **Critère B (temporaire)** : aucun correctif disponible et CVSS < 9.0 — suppression marquée `[PENDING_UPSTREAM_FIX]`, revérifiée à chaque activation du skill (étape 0 de `SKILL.md`), remplacée par le vrai correctif dès qu'il sort. **CVSS ≥ 9.0 sans correctif** : seule exception restant hors périmètre — blocage documenté, `FIXCVE_AUTO_RESULT: NO_ACTION`, intervention manuelle requise. |
| **Revérification des exclusions temporaires (Critère B)** | À chaque activation du skill (quel que soit le build/stage déclencheur), `SKILL.md` étape 0 scanne `owasp-suppressions.xml`/`.trivyignore.yaml` pour le jeton `[PENDING_UPSTREAM_FIX]` et revérifie Maven Central/npm pour chacune ; si un correctif est sorti, applique le vrai correctif et retire l'exclusion. Ce mécanisme ne se déclenche que si le skill est réinvoqué (un build vert sur une CVE désormais supprimée n'invoque plus le skill tant qu'aucune autre CVE ne fait échouer le build) — jugé suffisant vu la fréquence d'activation réelle du skill sur ce projet (surface OWASP Dependency-Check large). |
| **Journal d'audit append-only** | `rhDemo/docs/fixcve-audit.jsonl`, versionné, une ligne JSON par événement (détection, application, validation, rollback, halte). |
| **Verrou anti-chevauchement** | `flock` sur `~/.config/rhdemo-fixcve/poll.lock` — un cycle CI (~2h max) ne peut pas se chevaucher avec le suivant. |
| **Anti-boucle blocage confirmé** | Après un `blocked_needs_human` (CVE bloquante sans correctif dispo), le script mémorise `blocked_confirmed.{since,source_sha}` dans `state.json`. Tant que le code source n'a pas changé (SHA du dernier commit hors `fixcve-audit.jsonl` identique) et que `BLOCKED_RECHECK_INTERVAL_SECONDS` (48h) n'est pas écoulé, les cycles suivants n'appellent pas Claude et ne committent/poussent rien — évite la boucle auto-entretenue commit→build Jenkins→nouveau commit observée sur les builds #735-#744 (aucune information nouvelle à chaque cycle, seul le push relançait le build suivant). |
| **Validation par SHA, pas par numéro de build** | Phase B (`pending_validation`) vérifie que `fix_commit_sha` est un ancêtre (ou égal) du commit réellement bâti par le build suivant (`git merge-base --is-ancestor`), pas seulement que son numéro est supérieur à `trigger_build_seen`. Jenkins déclenche un build sur **chaque** push (webhook/poll SCM) — un push sans rapport intercalé entre la publication du correctif et le cycle cron suivant (commit de documentation, PR Renovate...) produit un build qui n'est pas celui du correctif ; sans cette vérification, ce build intercalé est pris pour la validation et peut faire annuler un correctif jamais réellement testé. Incident constaté build #749→#750 (`ee1061c` poussé, mais le build examiné était bâti sur un commit de documentation poussé entre-temps — rollback d'un correctif jamais validé, 2e rollback consécutif → halte automatique). |
| **Validation locale obligatoire avant push** | `SKILL.md` étape 5bis : parse XML/YAML du fichier de suppression modifié (module `xml`/`yaml` Python) puis rejeu local de `./mvnw org.owasp:dependency-check-maven:check`, comparé à la liste consolidée de l'étape 3, avant tout `git commit`/`git push`. Incident constaté builds #759→#760 puis #761→#762 : un premier correctif (build #759) traitait des CVE DOMPurify déjà suppressées sans traiter le CVE réellement bloquant (`postcss:7.0.39`/CVE-2026-45623) ; le correctif suivant (build #761) a introduit un commentaire XML contenant `--` (interdit par la spec XML sauf en clôture `-->`) dans `owasp-suppressions.xml`, rendant tout le fichier illisible par `dependency-check-maven` et faisant réapparaître en échec toutes les suppressions déjà validées — 2 rollbacks consécutifs → halte automatique. Un simple parse local (quelques secondes) aurait détecté les deux avant push, sans attendre un cycle Jenkins complet (~15+ min) suivi d'un rollback. Ce rejeu utilise le cache NVD de l'hôte (`~/.m2/dependency-check-data`, `pom.xml` : `<dataDirectory>${user.home}/.m2/dependency-check-data</dataDirectory>`) — **distinct** de celui de Jenkins (volume Docker `rhdemo-jenkins-home`, non partagé, avec clé API NVD injectée que l'hôte n'a pas) : fiable pour confirmer que le correctif couvre les CVE visées et ne casse rien, mais pas une simulation identique au scan Jenkins seconde près ; la validation Phase B (Jenkins) reste le filet de sécurité final. |
| **Aucun commentaire XML `<!-- -->` libre pour les suppressions** | Toute justification, même longue, va dans `<notes>` (contenu XML normal, jamais interprété comme commentaire) — jamais dans un bloc `<!-- ... -->` séparé, où un `--` littéral (ex. une commande `npm ... --force` citée dans le texte) casse le parsing de tout le fichier. Voir incident ci-dessus. |
| **Journalisation de la cause réelle d'un rollback** | Phase B enrichit l'événement `validation_failed_rollback` avec `failure_stage` (premier stage Jenkins en échec) et `failure_detail` (extrait des lignes `[ERROR]` de `consoleText`), au lieu de se limiter à `commit`/`revert_commit`. Avant ce garde-fou, un post-mortem devait ressortir les logs Jenkins bruts à la main (constaté lors de l'analyse des rollbacks builds #760/#762). |

---

## Points d'attention

⚠️ Ce document décrit une automatisation qui **committe et pousse du code sur la branche courante sans revue humaine**, y compris des décisions d'acceptation de risque (suppression de CVE). C'est un choix assumé en échange des garde-fous ci-dessus — à désactiver si ces garde-fous ne sont plus jugés suffisants pour le contexte du moment (ex: montée en criticité du projet).

⚠️ **Surface d'injection de prompt** : `/fixcve-auto` parse du contenu externe non fiable (descriptions de CVE, rapport HTML OWASP, JSON Trivy). Le scope d'outils est restreint via `--permission-mode dontAsk` + règles `permissions.allow` (fichier versionné [`fixcve-auto-permissions.json`](../scripts/fixcve-auto-permissions.json)) : Claude n'a accès qu'aux commandes prévues (curl Jenkins/Maven Central, `npm audit`/`view`/`install` scopés à `frontend/`, `docker manifest inspect`, `git add`/`commit`/`push`) et aux fichiers de remédiation attendus (`pom.xml`, `Jenkinsfile-CI`, `frontend/package.json`, `frontend/package-lock.json`, `owasp-suppressions.xml`, `.trivyignore.yaml`, `docs/SECURITY_ADVISORIES.md`, `docs/fixcve-audit.jsonl`, les manifests de déploiement des images externes). Toute autre commande ou fichier est refusé sans prompt (mode non interactif). Ce scoping s'ajoute aux garde-fous **git** ci-dessus (working tree propre, rollback automatique, halte après rollbacks), qui restent la protection de dernier recours si une commande scoping-compatible était malgré tout détournée.

⚠️ **Limite du scoping par préfixe** : la règle `Bash(frontend/node/npm --prefix frontend audit:*)` autorise aussi bien `npm audit fix --package-lock-only` (voulu) que `npm audit fix --force` (interdit par consigne dans `SKILL.md`, jamais par le moteur de permissions lui-même — un préfixe `allow` ne peut pas exclure un flag précis). Le blocage de `--force` repose donc uniquement sur le respect de la consigne par le modèle, pas sur une barrière technique — à garder en tête vu la surface d'injection de prompt ci-dessus (une description de CVE malveillante pourrait tenter d'inciter à l'usage de `--force`). Les garde-fous git (rollback automatique après échec du build suivant) restent la protection de dernier recours si ça arrivait malgré tout.

⚠️ **`npm` absent du `PATH` sous cron** : constaté sur le build #715 (`npm : commande introuvable`, `blocked_needs_human` sur 39 CVE). Le `PATH` minimal de cron ne source aucun profil shell, donc un `npm` installé via nvm (disponible en session interactive) n'est pas résolu par le skill. `SKILL.md` et `fixcve-auto-permissions.json` utilisent donc le binaire `frontend/node/npm` (téléchargé par `frontend-maven-plugin`, chemin littéral dans le dépôt, indépendant du `PATH`) plutôt qu'un `npm` nu.

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

⚠️ **Comportement à connaître (toujours vrai sur `2.1.220`, distinct du bug ci-dessus)** : sous `dontAsk`, une commande Bash contenant une expansion de variable shell (`${VAR}`) est refusée **même si son préfixe correspond à une règle `allow`** — ex. `Bash(curl:*)` ne matche pas `curl -sf -u "${JENKINS_USER}:${JENKINS_TOKEN}" ...`, alors que la même commande avec des valeurs littérales passe. Vérifié empiriquement le 2026-07-29 (build Jenkins #709/#710, `permission_denials` dans la sortie `--output-format json`) : c'est ce qui bloquait le premier appel curl de chaque exécution de `/fixcve-auto`, quelle que soit la commande. Contournement retenu : `rhDemo/scripts/fixcve-auto-poll.sh` régénère à chaque cycle `/home/leno-vo/.config/rhdemo-fixcve/jenkins.netrc` (chemin littéral, `chmod 600`) à partir des identifiants déchiffrés, et le skill utilise `curl --netrc-file /home/leno-vo/.config/rhdemo-fixcve/jenkins.netrc` (chemin statique, aucune variable dans le texte de la commande) au lieu de `-u "${JENKINS_USER}:${JENKINS_TOKEN}"`. Le mécanisme `GIT_ASKPASS` pour `git push` n'est pas concerné : la substitution s'y fait à l'intérieur du script `git-askpass.sh`, jamais dans le texte de la commande vue par Claude.

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

`.claude/` (skills, dont `fixcve-auto`) est **volontairement gitignored** dans ce dépôt
(`.gitignore` : « peut être vecteur d'injections », resté local plutôt que versionné) — un
`git clone` classique ne le copie donc pas. Sans lui, `claude -p "/fixcve-auto ..."` échouerait
dès le premier cycle (skill introuvable). Un symlink vers la copie principale garde le clone
isolé automatiquement à jour de toute évolution du skill, sans étape de resynchronisation
manuelle :

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

Après avoir traité manuellement la cause des rollbacks répétés (visible dans `rhDemo/docs/fixcve-audit.jsonl`, événements `automation_halted`) :

```bash
jq '.status="idle" | .consecutive_rollbacks=0' ~/.config/rhdemo-fixcve/state.json > /tmp/s.json && mv /tmp/s.json ~/.config/rhdemo-fixcve/state.json
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

## Évolution future : exécution via Jenkins plutôt que cron local

Alternative envisageable si le besoin se présente (plusieurs machines, survie à l'arrêt du PC de dev) : héberger l'automatisation dans Jenkins plutôt que sur un cron local. Ce n'est **pas un simple portage**, à évaluer avant de s'engager :

- **Installer Claude Code (+ Node.js) dans l'image `infra/jenkins-docker/`** — dépendance absente aujourd'hui, à maintenir sur un système pensé pour rester léger (1 PC, 16 Go).
- **Migrer les credentials de SOPS/AGE local vers le Credentials Store Jenkins** — gain réel : réutilise le pattern déjà en place dans `Jenkinsfile-CI` (`SOPS_AGE_KEY = credentials('sops-age-key-ephemere')`), plus cohérent que le fichier chiffré local actuel.
- **Remplacer le polling par un `post { failure { ... } }` dans `Jenkinsfile-CI`**, déclenchant un job dédié (`RHDemo-fixcve-auto`) avec build number + type de stage en paramètres. Gain principal : Jenkins sait *nativement* quel stage a échoué, ce qui élimine la détection fragile par `wfapi/describe` (cause du bug de classification trivy/owasp rencontré lors de la mise en service — un échec précoce faisait passer des stages en aval, dont un nommé "Trivy", en non-SUCCESS).
- **Réécrire la machine à états (idle/pending_validation/halted)** — pas d'équivalent trivial à `state.json` local ; nécessiterait un fichier d'état sur volume persistant Jenkins, ou un marqueur dans les commits automatiques (ex: trailer `Fixcve-Auto: true`) pour détecter la validation au build suivant.

Coût principal : toucher `Jenkinsfile-CI` (pipeline critique déjà volumineux) et réimplémenter en Groovy une logique aujourd'hui simple et auditable en bash. À ne migrer que si un besoin concret l'exige, pas par principe.

## Voir aussi

- [`.claude/skills/fixcve/SKILL.md`](../../.claude/skills/fixcve/SKILL.md) — version interactive avec validation humaine
- [`.claude/skills/fixcve-auto/SKILL.md`](../../.claude/skills/fixcve-auto/SKILL.md) — instructions détaillées de la remédiation automatique
- [SECURITY_ADVISORIES.md](SECURITY_ADVISORIES.md) — historique des CVE traitées (manuel et automatique)
- [SOPS_SETUP.md](SOPS_SETUP.md) — installation SOPS/AGE
