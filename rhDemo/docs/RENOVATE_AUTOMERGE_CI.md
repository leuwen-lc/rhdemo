# Intégration automatique des mises à jour Renovate après validation CI Jenkins

## Contexte et solution retenue

Renovate crée chaque nuit (3h) des PRs de mise à jour de dépendances vers `evolutions-post-1.1.9`,
mais ne peut pas les merger lui-même : Jenkins n'est pas exposé sur Internet donc Forgejo ne peut
pas lui envoyer de webhook, et les statuts CI ne sont jamais remontés vers Forgejo
(`prCreation: immediate`) — Renovate attendrait donc indéfiniment un statut qui n'arrive jamais.
Plusieurs pistes ont été écartées : faire remonter les statuts CI à Forgejo pour laisser Renovate
merger lui-même (rejeté — délai d'environ 24h jusqu'au passage nocturne suivant, et nécessite un
pipeline Jenkins multibranch supplémentaire sur `renovate/*`) ; migrer la CI vers Codeberg Actions
pour bénéficier des webhooks natifs (hors scope — refonte complète du pipeline) ; paramétrer le
`Jenkinsfile-CI` existant avec un orchestrateur minimal qui le déclenche pour chaque PR (rejeté —
couple la validation Renovate à la durée et aux évolutions du CI complet, alors que
Selenium/ZAP/SonarQube/publication n'ont pas besoin d'y tourner) ; et factoriser build/tests/OWASP
dans une shared library Jenkins commune aux deux pipelines (rejeté — le `Jenkinsfile-CI` déclaratif
actuel devrait être réécrit en pipeline scripté pour être appelable dynamiquement, un refactoring
risqué pour un gain marginal). La solution retenue est un pipeline Jenkins dédié,
[`Jenkinsfile-Renovate`](../Jenkinsfile-Renovate) : il liste les PRs Renovate ouvertes via l'API
Forgejo, exécute pour chacune un build Maven + tests + OWASP Dependency-Check (sans
Selenium/ZAP/SonarQube, déjà couverts par `RHDemo-CI` sur master après merge), puis merge
automatiquement via l'API Forgejo si la CI est verte, ou commente un échec sinon. Les PRs major
restent bloquées côté Renovate (`dependencyDashboardApproval: true`).

---

## Implémentation

> **Statut** : implémenté — [`Jenkinsfile-Renovate`](../Jenkinsfile-Renovate), job `RHDemo-Renovate`
> dans [`jenkins-casc.yaml`](../infra/jenkins-docker/jenkins-casc.yaml) et fonction
> `postForgejoComment` dans [`rhDemoLib.groovy`](../vars/rhDemoLib.groovy).

### 1. Credential Jenkins : token API Forgejo

**Compte dédié, pas le compte personnel.** Le token qui liste/synchronise/merge les PRs et poste
les commentaires est généré sur un compte Codeberg bot dédié (`rhdemo-ci-bot`), pas sur le compte
personnel `leuwen-lc`. Raisons :
- **Blast radius** : un token hérite de l'identité qui l'a créé, même avec un scope réduit. Une
  fuite du credential Jenkins authentifierait l'attaquant "en tant que vous" sur Codeberg (accès
  aux autres repos/organisations du compte). Un compte bot collaborateur d'un seul repo, avec
  permission "Write" (pas "Admin"), limite les dégâts à ce repo.
- **Audit** : les merges automatiques apparaissent dans l'historique Forgejo sous l'identité
  `rhdemo-ci-bot`, distincts de vos actions manuelles — utile pour distinguer "c'est la CI qui a
  mergé" de "c'est moi qui ai mergé".
- **Cycle de vie découplé** : rotation de mot de passe/2FA sur le compte personnel ne casse pas
  la CI.
- **Séparation des rôles** : ce compte est distinct du bot Renovate (`renovate-forgejo-token`,
  compte qui *propose* les PRs) — c'est une identité différente qui *valide/merge* après CI verte,
  comme une revue à deux acteurs même si le second est entièrement automatisé.

Ce token reste distinct de celui déjà utilisé par `/fixcve-auto`
(`~/.config/rhdemo-fixcve/credentials.sops.yaml`), pour isoler les deux automatisations.

### 2. Fichier `Jenkinsfile-Renovate`

Voir [`Jenkinsfile-Renovate`](../Jenkinsfile-Renovate) pour le script complet — trois stages :
**Scan Renovate** (image officielle `renovate/renovate`, cf. section dédiée plus bas),
**Lister les PRs Renovate** (API Forgejo + filtre `jq` sur `head.ref`/`base.ref`/`head.repo.full_name`),
et **Valider et merger chaque PR** (fetch de la branche, synchronisation avec la base si en retard,
build Maven + OWASP, puis merge API en squash si la CI passe — un seul commit par PR sur
`evolutions-post-1.1.9`, historique linéaire ; nécessite « Allow squash merging » activé côté
réglages du dépôt Codeberg).

Le credential `ci-bot-forgejo-token` (accès Write) est scopé au strict nécessaire dans ce dernier
stage : il n'est jamais exposé en variable d'environnement pendant l'exécution du build
(`mvnw verify`/OWASP), qui ne dispose que de `NVD_API_KEY`/`OSSINDEX_*` — le code de la PR (non
revu) ne doit jamais tourner avec un token à accès Write en environnement, voir section
« Sécurité » ci-dessous.

La fonction `postForgejoComment` (dans `rhDemoLib.groovy`, chargée via `load` comme le reste de la
lib) construit le JSON avec `jq -n --arg` plutôt que par interpolation directe dans une chaîne
`-d '{"body":"..."}'`, pour ne pas casser la requête si un message venait à contenir un guillemet.

### 3. Déclaration dans `jenkins-casc.yaml`

Job `RHDemo-Renovate` ajouté dans le bloc `jobs` du CASC (voir
[`jenkins-casc.yaml`](../infra/jenkins-docker/jenkins-casc.yaml) pour la version exacte), sur le
même modèle que `RHDemo-CI`/`RHDemo-CD` (checkout du repo public sans credentials, `scriptPath`
vers le nouveau Jenkinsfile, `disableConcurrentBuilds`, `buildDiscarder`). Le cron `H 4 * * *` est
déclaré dans le `triggers {}` du job CASC, pas dans le Jenkinsfile lui-même.

Prise en compte : `docker-compose restart jenkins` (mécanisme déjà documenté dans `QUICKSTART.md`)
suffit à recharger la configuration et faire apparaître le nouveau job — aucune étape
supplémentaire nécessaire.

### 4. Ajustements `renovate.json`

Ajouter `automerge: false` explicitement pour les mises à jour **major** (déjà bloquées par `dependencyDashboardApproval`) et confirmer que minor/patch ne bloquent pas sur les statuts :

```json
{
  "packageRules": [
    {
      "matchUpdateTypes": ["patch", "minor"],
      "automerge": false
    }
  ]
}
```

(`prCreation: "immediate"` est déjà défini globalement dans `renovate.json`, pas besoin de le répéter par règle.)

> Note : `automerge: false` ici signifie que Renovate lui-même ne tente pas de merger (c'est Jenkins qui le fait). Cela évite les conflits entre les deux mécanismes.

---

## Aiguillage de la validation selon les fichiers modifiés

Le stage « Valider et merger chaque PR » ne peut pas soumettre toutes les PRs Renovate au même
traitement : un `mvnw verify` + OWASP Dependency-Check ne valide ni un composant d'infrastructure
Kubernetes (Cilium, NGF, kube-prometheus-stack...) ni un simple bump d'image Docker épinglée par
digest (`NGINX_IMAGE`, `POSTGRES_IMAGE`, `global.images.postgresExporter`...) — dans les deux cas
le code Java ne change pas, donc le build/tests Maven passeraient de toute façon sans avoir
exercé le moindre bit du changement réel.

L'aiguillage se fait sur `git diff --name-only origin/${BASE_BRANCH}...HEAD` (calculé une seule
fois par PR, loggé explicitement dans la console Jenkins avant le choix du chemin), avec trois
chemins mutuellement exclusifs, évalués dans cet ordre de priorité :

1. **Composant d'infrastructure stagingkub → Kubernetes dry-run**
2. **Image Docker épinglée par digest → Trivy scan ciblé**
3. **Tout le reste → Maven + OWASP Dependency-Check** (chemin historique, inchangé)

**Pourquoi une extension du pipeline existant plutôt qu'un second job Renovate séparé** : un
second job avec son propre listing Forgejo aurait dupliqué le code de listing/synchronisation/merge
(`postForgejoComment`, boucle de sync, squash-merge) déjà présent dans `rhDemoLib.groovy`/
`Jenkinsfile-Renovate`, et introduit un risque de recouvrement entre les deux jobs sur une même PR.
Un seul listing Forgejo, un seul job qui merge — la classification se fait à l'intérieur de la
boucle existante, PR par PR.

### 1. Composant d'infrastructure stagingkub → Kubernetes dry-run

**Détection** : le diff touche `rhDemo/infra/stagingkub/scripts/components/install-or-upgrade-*.sh`
ou `rhDemo/infra/stagingkub/kind-config.yaml`.

**Pourquoi** : ces fichiers pilotent Cilium/NGF/kube-prometheus-stack/Loki/Alloy/Grafana —
l'infrastructure du cluster elle-même, hors du périmètre applicatif Java. Le détail du RBAC dédié
(`jenkins-infra-upgrader`), du choix « mise à jour en place » plutôt que reconstruction complète, et
du job de déploiement réel post-merge sont documentés dans
[STAGINGKUB_REBUILD_PIPELINE.md](STAGINGKUB_REBUILD_PIPELINE.md) — ce document-ci ne couvre que le
branchement dans `Jenkinsfile-Renovate`.

**Validation** : credential `kubeconfig-stagingkub-infra-upgrader` + `HELM_DRY_RUN=true <script>`
contre le cluster stagingkub réel. Un `--dry-run=server` exige les mêmes autorisations RBAC qu'une
exécution réelle (Kubernetes vérifie l'autorisation avant d'évaluer le drapeau dry-run) — la
garantie de sécurité vient de l'absence de persistance server-side, pas d'un credential moins
privilégié. `FORGEJO_TOKEN` reste absent de ce bloc (même raisonnement supply-chain que pour le
bloc Maven : le script exécuté vient d'une PR non revue).

**Prérequis réseau** : l'agent éphémère `builder` n'est attaché par défaut qu'à
`rhdemo-jenkins-network` (cf. `jenkins-casc.yaml`), pas au réseau Docker `kind` du cluster KinD —
sans connexion explicite, `kubectl`/`helm` échouent à résoudre `rhdemo-control-plane` (« server
misbehaving »). Le stage connecte l'agent au réseau `kind` via `lib.dockerNetworkConnect` avant la
boucle de traitement des PR (déconnexion symétrique dans `post { always {} }`) — même mécanisme
que `Jenkinsfile-CD`/`Jenkinsfile-Stagingkub-Upgrade-Deploy`. **Incident corrigé** : ce bloc a
d'abord été implémenté sans cette connexion, ce qui a fait échouer silencieusement (DNS, pas RBAC)
les premiers dry-run de composants d'infra — les PR concernées étaient restées ouvertes plutôt que
mergées à tort, mais sans jamais avoir réellement validé quoi que ce soit.

**Incident corrigé — test de connectivité `kubectl cluster-info`** : une fois le réseau `kind`
joint, le bloc appelait `kubectl cluster-info` comme simple sanity check avant le dry-run réel.
Cette commande interroge en interne les Services de `kube-system` (label
`kubernetes.io/cluster-service=true`, pour afficher les adresses KubeDNS/etc.) — un `list services`
que `jenkins-infra-upgrader` n'a délibérément pas (cf. `rbac/README.md`). Conséquence observée :
les 3 PR d'infra ouvertes (Cilium, kube-prometheus-stack minor et major) ont échoué avec
`services is forbidden ... in the namespace "kube-system"`, un faux-positif RBAC qui n'avait rien à
voir avec le composant réellement testé. `Jenkinsfile-CD` documentait déjà ce piège pour
`jenkins-deployer` ; remplacé par `kubectl config current-context` (purement local, aucun appel
API), comme le fait déjà `Jenkinsfile-Stagingkub-Upgrade-Deploy`.

**Cas limite** : si le cluster stagingkub n'est pas démarré au moment du scan, la validation
dry-run échoue proprement (message explicite, PR conservée ouverte) plutôt que de bloquer le
traitement des autres PR de la même exécution.

**Après merge** : déclenchement de `RHDemo-Stagingkub-Upgrade-Deploy`
(`build job: ..., wait: false`) — voir [STAGINGKUB_REBUILD_PIPELINE.md](STAGINGKUB_REBUILD_PIPELINE.md)
pour ce que fait ce job.

### 2. Image Docker épinglée par digest → Trivy scan ciblé

**Détection** : le diff ne touche **que** `rhDemo/Jenkinsfile-CI` (variables
`NGINX_IMAGE`/`POSTGRES_IMAGE`/`KEYCLOAK_IMAGE`/`NGF_IMAGE`) et/ou
`rhDemo/infra/stagingkub/helm/rhdemo/values.yaml` (`global.images.*` :
`postgres`/`keycloak`/`busybox`/`postgresExporter`) — les deux familles de fichiers où Renovate
suit des images en chaîne complète `repo:tag@sha256:digest` via un `customManager` (pas un manager
natif Renovate, cf. CLAUDE.md). Si le diff touche l'un de ces fichiers **et** un autre fichier hors
de cette liste, la PR retombe sur le chemin Maven par défaut (chemin 3).

**Pourquoi pas Maven** : ces PR ne touchent ni `pom.xml` ni le code Java — `mvnw verify`/OWASP
passerait quel que soit le contenu réel du bump, sans jamais avoir scanné l'image concernée. Le
seul risque réel introduit par ce type de PR est une vulnérabilité dans la nouvelle image, exactement
ce que `Jenkinsfile-CI` scanne déjà via Trivy après build — la validation avant merge réutilise donc
le même scan, ciblé sur la seule image modifiée, plutôt que d'attendre le prochain passage de
`RHDemo-CI` sur la base pour le découvrir.

**Extraction de l'image modifiée** :
`git diff origin/${BASE_BRANCH}...HEAD -- rhDemo/Jenkinsfile-CI rhDemo/infra/stagingkub/helm/rhdemo/values.yaml`,
lignes ajoutées (`+`) matchant le motif `repo:tag@sha256:digest` — pas besoin de savoir quelle
variable/clé a changé, la valeur ajoutée suffit. Le nom du rapport Trivy est dérivé du dernier
segment du chemin d'image (`ghcr.io/nginx/nginx-gateway-fabric:2.6.1@...` → `nginx-gateway-fabric`).

**Validation** : réutilisation de `lib.generateTrivyReport(image, name)` /
`lib.aggregateTrivyResults()` (déjà utilisées par `Jenkinsfile-CI`, voir `rhDemoLib.groovy`) — même
seuil de blocage (CRITICAL), même mécanisme `.trivyignore.yaml`. `FORGEJO_TOKEN` reste absent de ce
bloc par cohérence avec le principe de moindre privilège appliqué partout ailleurs dans ce pipeline.

**Cas limite** : si aucune image reconnue n'est trouvée dans le diff (format inattendu), la PR
échoue proprement avec un commentaire dédié plutôt que de silencieusement retomber sur Maven.

**Après merge** : pas de déclenchement supplémentaire — ces images ne sont consommées que par
`Jenkinsfile-CI`/`Jenkinsfile-CD` au prochain build normal, comme n'importe quelle autre dépendance
passée par le chemin Maven.

### 3. Tout le reste → Maven + OWASP Dependency-Check (inchangé)

`pom.xml`, `package.json`, code Java/Vue, etc. — chemin historique, décrit en section
« Implémentation » ci-dessus.

### Traçabilité

Chaque itération de la boucle logge explicitement, avant tout choix de chemin : la liste des
fichiers modifiés (`git diff --name-only`) puis une ligne dédiée « chemin retenu = ... » indiquant
le chemin choisi et le motif ayant matché (composant d'infra nommé, fichier(s) d'image épinglée
détecté(s), ou absence de motif reconnu pour le chemin Maven par défaut) — pour diagnostiquer un
aiguillage inattendu directement depuis les logs Jenkins sans avoir à rejouer `git diff` à la main.

---

## Rapatriement du scan Renovate depuis Codeberg Actions

**Statut : implémenté.** Le scan Renovate (précédemment `.forgejo/workflows/renovate.yml` sur
Codeberg Actions) tourne désormais dans le même job Jenkins `RHDemo-Renovate`, en amont des
stages de validation/merge — un seul pipeline, un seul cron (3h), plus de dépendance à
Codeberg Actions pour cette automatisation.

### Pourquoi

Le pool de runners `codeberg-medium` est devenu indisponible de façon récurrente ("plus de
container disponible"), un problème de **capacité** distinct du timeout `codeberg-small`
(~5 min, "context deadline exceeded") déjà documenté dans
[`.forgejo/workflows/README.md`](../../.forgejo/workflows/README.md) — ce dernier a un
fallback (split en deux workflows `codeberg-small`) qui reste disponible en secours, mais ne
règle pas un manque de capacité généralisé côté Codeberg Actions. Rapatrier vers Jenkins
élimine complètement la dépendance à un système de CI externe pour cette automatisation,
cohérent avec la philosophie du projet (indépendance vis-à-vis des grandes plateformes).

### Implémentation

Nouveau stage `🔄 Scan Renovate` dans `Jenkinsfile-Renovate`, avant le listing des PRs :
l'image officielle `renovate/renovate:43.249.5` est lancée en conteneur frère (`docker run`,
via docker-socket-proxy — même mécanisme que pour l'environnement ephemere), avec le même
script d'import GPG et les mêmes variables d'environnement que l'ancien workflow Forgejo.

**Piège Docker-outside-of-Docker évité** : un conteneur frère lancé depuis l'agent Jenkins ne
partage pas le système de fichiers de l'agent — un bind-mount vers un chemin de l'agent ne
pointerait nulle part côté hôte Docker réel (c'est pourquoi l'environnement ephemere utilise
`docker cp` pour ses secrets). La clé GPG est donc passée en base64 via variable
d'environnement (`RENOVATE_GPG_KEY`) et importée à l'intérieur du conteneur Renovate lui-même,
sans jamais toucher le système de fichiers de l'agent — aucun bind-mount nécessaire.

**Pourquoi pas `npm install -g renovate` sur l'image agent** : Renovate 43.x exige une version
de Node récente, alors que le `nodejs`/`npm` installé via `apt` dans `Dockerfile.agent` est une
version Debian probablement ancienne (le build frontend Vue.js utilise sa propre installation
Node 20.10.0 via `frontend-maven-plugin`, jamais le Node système). Utiliser l'image officielle
évite tout problème de version Node à gérer côté agent.

**Piège GPG rencontré** : `GNUPGHOME` a d'abord été mis à un chemin custom (`/tmp/gnupg`), mais
les commits Renovate échouaient avec `gpg: skipped "<KEY_ID>": No secret key` — un nouveau
trousseau vide apparaissait dans `/home/ubuntu/.gnupg`. Renovate sandboxe l'environnement des
sous-processus git qu'il lance pour committer et ne propage pas un `GNUPGHOME` custom vers ces
sous-processus, qui retombent alors sur l'emplacement par défaut (`$HOME/.gnupg`). Fix : utiliser
`GNUPGHOME="${HOME}/.gnupg"` (comme le faisait déjà l'ancien workflow Codeberg Actions) plutôt
qu'un chemin custom, pour que l'import atterrisse là où les sous-processus de Renovate le
chercheront par défaut.

### Credentials Jenkins nécessaires (en plus de `ci-bot-forgejo-token`)

- **`renovate-gpg-key`** (Secret text) : clé GPG privée exportée en base64, même valeur que
  l'ancien secret Codeberg Actions `RENOVATE_GPG_KEY`.
- **`renovate-github-token`** (Secret text) : token GitHub read-only (dépôts publics), pour les
  lookups de changelogs/release notes des dépendances hébergées sur GitHub, même valeur que
  l'ancien secret Codeberg Actions `RENOVATE_GH_TOKEN`.
- **`renovate-forgejo-token`** (Secret text) : même valeur que l'ancien secret Codeberg Actions
  `RENOVATE_TOKEN`, dédié au compte bot Renovate lui-même — distinct du compte `rhdemo-ci-bot`
  (variable `RENOVATE_TOKEN` du stage "Scan Renovate").
  **Distinct de `ci-bot-forgejo-token`** — essayé en premier par souci de simplicité (un secret de
  moins), mais l'initialisation de Renovate échoue avec `"Authentication failure"` avec les
  scopes `repository` + `issue` de `ci-bot-forgejo-token` : elle a besoin d'un scope `user`
  supplémentaire, absent de ce token. Réutiliser le token qui fonctionnait déjà côté Codeberg
  Actions pour Renovate règle le problème sans avoir à déterminer/régénérer le scope exact requis,
  et rejoint au passage l'isolation des responsabilités déjà appliquée pour `/fixcve-auto`. Les deux
  comptes bot (`rhdemo-ci-bot` et celui de Renovate) restent malgré tout des identités distinctes
  — voir section 1 pour le raisonnement (séparation propose/merge).

### Devenir de `.forgejo/workflows/renovate.yml`

Le cron a été retiré (`on: workflow_dispatch` uniquement) — le workflow reste dans le dépôt
comme secours manuel si Jenkins devient indisponible, plutôt que d'être supprimé.

---

## Périmètre d'automerge

| Type de mise à jour | Traitement |
|---|---|
| `patch` (ex: 1.2.3 → 1.2.4) | Automerge Jenkins si CI verte |
| `minor` (ex: 1.2.3 → 1.3.0) | Automerge Jenkins si CI verte |
| `major` (ex: 1.x → 2.x) | Bloqué — `dependencyDashboardApproval: true` — revue manuelle |
| Plugins Jenkins | Exclus — `matchManagers: ["jenkins"]` désactivé |
| Image `rhdemo-api` | Exclue — `matchPackageNames: ["rhdemo-api"]` désactivé |

---

## Sécurité

- Le token Forgejo (`ci-bot-forgejo-token`) appartient au compte bot dédié `rhdemo-ci-bot`, pas au
  compte personnel — voir section 1 pour le raisonnement (blast radius, audit, cycle de vie)
- Le compte `rhdemo-ci-bot` est collaborateur du repo avec la permission **Write** uniquement
  (pas Admin) ; le token n'a que les scopes `repository` + `issue` (pas d'accès admin)
- Le token est stocké comme credential Jenkins chiffré (jamais en clair dans les fichiers)
- Le pipeline vérifie que la PR cible bien `evolutions-post-1.1.9` avant de merger
- Les PRs major ne passent jamais par ce pipeline (bloquées côté Renovate)
- Le listing des PRs (stage « Lister les PRs Renovate ») rejette explicitement les PRs dont la
  branche source vit dans un fork (`select(.head.repo.full_name == $repo)`) — seules les branches
  poussées directement dans `leuwen-lc/rhdemo` (donc par un compte ayant déjà l'accès Write) sont
  éligibles à l'automerge
- `FORGEJO_TOKEN` (accès Write) n'est jamais exposé en variable d'environnement pendant
  l'exécution du build (`mvnw verify`/OWASP) : le code de la PR (dépendance mise à jour, non revu)
  ne dispose que de `NVD_API_KEY`/`OSSINDEX_*` (lecture seule sur des bases de vulnérabilités
  publiques), pour empêcher qu'une dépendance compromise exfiltre le token d'écriture

---

## Limites connues

1. **Durée** : Si Renovate crée 15 PRs en une nuit, le pipeline peut tourner 2-3h (CI séquentielle). Mitigation : paralléliser avec `parallel {}` Jenkins si les ressources le permettent.

2. **Conflits entre PRs** : Si deux PRs modifient le même fichier (rare pour des dépendances), la seconde peut conflictiquer après merge de la première. Le pipeline détecte l'échec du merge API et laisse la PR ouverte.

3. ~~Pas de rebase automatique~~ **Résolu** : le pipeline vérifie désormais (`git merge-base --is-ancestor`) si la branche PR est en retard sur `evolutions-post-X.Y.Z` (branche courante, voir point 6) avant de lancer les tests. Si oui, il fait un `git merge` (classique, pas squash) de la base dans la branche PR, commit, et pousse sur Codeberg avant de lancer la CI — ça évite qu'un correctif déjà mergé sur la base (ex: CVE fixée entre-temps) fasse échouer la CI d'une PR sans rapport avec ce correctif.
   - **Pourquoi pas un squash merge** : essayé initialement, mais un `git merge --squash` ne crée pas de commit de fusion à deux parents — git perd la trace de ce qui a déjà été synchronisé. Chaque sync suivante recalcule alors un merge-base bien plus ancien que le dernier sync réussi, ce qui provoque un faux conflit `add/add` dès qu'un fichier est retouché côté base entre deux cycles (observé en pratique sur `Jenkinsfile-Renovate` lui-même). Un merge classique préserve la filiation avec la base : chaque sync devient incrémentale.
   - En cas de conflit lors du merge, la PR est marquée en échec avec un commentaire dédié ("rebase manuel nécessaire") plutôt que de faire planter le build — **sauf si la PR est détectée comme dépassée** (voir ci-dessous), auquel cas elle est fermée automatiquement au lieu d'être comptée en échec.
   - **Fermeture automatique des PR dépassées (supersession)** : un conflit de sync peut simplement signifier qu'une autre PR Renovate pour la **même dépendance** a déjà mergé une version plus récente pendant que celle-ci attendait (observé en pratique : PR `kube-prometheus-stack` minor entrée en conflit après le merge de la PR major correspondante — la base était passée de `81.5.1` à `87.16.1`, rendant le `81.6.9` proposé obsolète). Marquer systématiquement ce cas en `FAILURE` produisait un signal récurrent sans action possible (Renovate finit toujours par fermer lui-même la PR à un scan ultérieur). Détection, fichier par fichier en conflit (`git diff --name-only --diff-filter=U`) : extraction de la valeur `VAR="X.Y.Z"` (format des scripts `scripts/components/*.sh` trackés par Renovate) des deux côtés du conflit, comparaison via `sort -V` — si la base est déjà à une version égale ou supérieure sur **tous** les fichiers en conflit, la PR est fermée via l'API Forgejo (`PATCH .../pulls/{id}` `{"state":"closed"}`) avec un commentaire explicatif, sans passer par `failures`. Si un seul fichier ne matche pas ce format (valeur vide d'un côté ou de l'autre — cas des images épinglées `repo:tag@sha256:digest`, non couvert par ce format), aucun risque n'est pris : traitement en échec classique, comme avant.
   - Ce commit de synchronisation est indépendant du `rebaseWhen: "behind-base-branch"` de Renovate (qui continue de fonctionner en parallèle, côté nocturne) — les deux mécanismes se recouvrent partiellement mais ne rentrent pas en conflit : si Renovate rebase la branche entre-temps (force-push), le prochain run Jenkins repart d'un état propre.
   - **Incident connu** : la première version (squash) a poussé un commit corrompu (ancêtre commun perdu) sur `renovate/renovate-renovate-43.x` avant d'être corrigée. Cette branche spécifique continuera de conflictuer sur tout fichier déjà présent des deux côtés tant qu'elle n'aura pas été rebasée proprement par Renovate (`@renovate rebase` en commentaire de PR, ou passage nocturne).

4. **Pas de déclenchement CD** : Ce pipeline ne déclenche pas le CD après merge. Le CI principal (`RHDemo-CI`) doit être étendu pour surveiller aussi `evolutions-post-X.Y.Z` (branche courante, voir point 6) (ou un cron nocturne séparé).

5. **Pipeline unique scan + validation** : le scan Renovate et la validation/merge sont dans le même job (choix assumé lors du rapatriement depuis Codeberg Actions). Si le scan Renovate échoue (image indisponible, erreur de config...), toute la validation/merge de ce cycle est également sautée — pas d'isolation entre les deux responsabilités. Alternative possible : scinder en deux jobs (`RHDemo-Renovate-Scan` + `RHDemo-Renovate`) si l'isolation des pannes devient un problème en pratique.

6. **Branche `evolutions-post-X.Y.Z` en dur à 3 endroits** : `BASE_BRANCH` dans `Jenkinsfile-Renovate`, `baseBranchPatterns` dans `renovate.json`, et `branches('*/evolutions-post-X.Y.Z')` dans `jenkins-casc.yaml` (job `RHDemo-Renovate`, comme `RHDemo-CI`/`RHDemo-CD`). Ces trois références sont mises à jour automatiquement par `rhDemo/scripts/release.sh post-merge` (fonctions `bump_casc_branch` et `bump_renovate_branch`) lors du passage à la branche d'évolution suivante — voir [`GIT-PROCEDURE-RELEASE.md`](GIT-PROCEDURE-RELEASE.md). Si la procédure de release change, penser à vérifier que ces trois fichiers restent synchronisés.
