---
statut: historique
verifie_le: 2026-11-24
sources:
  - rhDemo/scripts/fixcve-auto-poll.sh
  - rhDemo/scripts/fixcve-detect.py
  - rhDemo/scripts/fixcve_lib/verify.py
  - rhDemo/scripts/fixcve-install.sh
  - rhDemo/infra/jenkins-docker/casc/jenkins-casc.yaml
  - rhDemo/Jenkinsfile-CI
  - rhDemo/Jenkinsfile-Renovate
  - rhDemo/secrets/inventory.yaml
---

# Étude : exécuter fixcve-auto dans Jenkins

Objectif : ne plus lancer fixcve-auto par un cron du poste, mais par un pipeline Jenkins. Cette étude évalue la faisabilité, liste les points durs et les décisions prises le 2026-11-22 (§4). **Mise en œuvre le 2026-11-22** (§8), **validée le 2026-11-24** par de vrais cycles dans Jenkins (remédiation complète des builds #1110 et #1111 : correctif poussé par le bot, validé par la CI). Document historique : il n'est plus mis à jour. Le fonctionnement actuel est décrit dans [FIXCVE_AUTO.md](FIXCVE_AUTO.md), qui envisageait déjà cette évolution (section « Évolution future »).

## 1. Conclusion

**Faisable, effort moyen (de l'ordre de 3 à 4 jours).** Trois faits rendent l'évolution plus simple qu'elle ne l'aurait été il y a deux mois :

- la procédure est **déterministe, sans LLM** : rien à installer ni à authentifier côté Claude dans l'agent ;
- le poller accepte déjà ses chemins et adresses en **variables d'environnement** (`FIXCVE_REPO_DIR`, `FIXCVE_STATE_DIR`, `FIXCVE_JENKINS_URL`, `FIXCVE_BAO_ADDR`…) : il peut tourner tel quel dans un agent, sans réécriture de la machine à états ;
- les secrets sont dans **OpenBao**, que Jenkins sait déjà lire.

Les scripts Python (`fixcve-detect.py` à `fixcve-verify.py`) ne changent presque pas. Le travail porte sur le cadre d'exécution : état persistant, déclenchement, racine de confiance, credentials.

Le point le plus délicat n'était pas technique : c'était la **racine de confiance** (§3.1). Aujourd'hui, un push seul ne peut pas changer ce que fait le bot. Décision : cette garantie est abandonnée, le bot s'aligne sur les autres pipelines Jenkins.

## 2. Ce qui se transpose directement

| Aujourd'hui (poste) | Dans Jenkins | Commentaire |
| --- | --- | --- |
| cron toutes les 15 min | Job `RHDemo-FixCVE` déclenché par la fin de `RHDemo-CI` (§3.3) | Réaction immédiate au lieu de 0 à 15 min |
| `flock` sur `poll.lock` | `disableConcurrentBuilds()` | Plus le plafond d'un agent à la fois (`instanceCapStr: "1"`) |
| Clone isolé `~/fixcve-worktrees/rhdemo`, maintenu à la main | Checkout neuf dans l'agent éphémère | Disparaît : plus de clone à provisionner ni à resynchroniser |
| Branche suivie : celle de la copie de travail principale | Branche du build CI (paramètre) | Plus de lecture de la copie principale |
| Rapports lus par l'API REST avec le token du compte `claude` | Inchangé, depuis le réseau des agents (`http://jenkins:8080`) | T5 révisée (§4) : `copyArtifacts` ne suffisait pas |
| Amorçage du cache NVD de l'hôte depuis le volume Jenkins (`seed_odc_cache`) | L'agent monte déjà `rhdemo-maven-repository` | L'amorçage devient inutile : même base que la CI, jamais en concurrence grâce au plafond d'un agent |
| Outils : `jq`, `npm`, Maven, Python, `git` | Image `rhdemo-jenkins-agent` | Tous présents (Python 3.13 et node 20 constatés dans l'image le 2026-11-22) ; le frontend utilise son propre `node` installé par Maven |
| `poll.log` + `logrotate` | Console du build + `buildDiscarder` | Lisible depuis Jenkins |
| Lignes `ALERTE` dans `poll.log` seulement | Build `UNSTABLE` ou `FAILURE` + mail | Gain : aujourd'hui une alerte passe inaperçue tant qu'on ne lit pas `poll.log` |
| Accès réseau : OSV.dev, registres npm, Maven, quay.io, Docker Hub, ghcr.io, NVD, Codeberg | Agents sur `rhdemo-jenkins-network`, sortie Internet comme pour Renovate | Pas de nouveau flux à ouvrir |

## 3. Points durs

### 3.1 Racine de confiance (épinglage des scripts)

Aujourd'hui, le poller part de la copie de travail principale et vérifie les empreintes SHA-256 des scripts du clone contre `~/.config/rhdemo-fixcve/trusted.sha256`. Seul l'utilisateur approuve un changement (`fixcve-install.sh --trust`). Un compte qui pousse sur la branche (Renovate, ci-bot, fixcve lui-même, ou un token volé) ne peut donc pas modifier le comportement du bot.

Dans Jenkins, un job « Pipeline script from SCM » lit son Jenkinsfile sur la branche. Un push malveillant pourrait retirer la vérification et faire tourner son code avec le token d'écriture du bot fixcve.

Ce risque existe déjà pour les autres pipelines : `Jenkinsfile-CI` et `Jenkinsfile-Renovate` viennent de la branche et utilisent des credentials (dont `ci-bot-forgejo-token`, qui a lui aussi le droit d'écriture). Garder un épinglage pour fixcve serait donc plus strict que le reste de Jenkins.

**Décision (T1)** : épinglage abandonné. `Jenkinsfile-FixCVE` est lu sur la branche comme les autres Jenkinsfiles ; `trusted.sha256` et `fixcve-install.sh --trust` disparaissent. Risque accepté : un compte qui pousse sur la branche peut modifier le bot et utiliser son token Codeberg, comme il peut déjà le faire avec `Jenkinsfile-Renovate` et `ci-bot-forgejo-token`.

### 3.2 État persistant avec des agents éphémères

`state.json` (statut, dernier build traité, compteurs de rollbacks et d'échecs, blocages confirmés, correctif en attente de validation) et les archives de cycle doivent survivre d'un build à l'autre. L'agent est détruit à la fin du build et son espace de travail avec. Il faut un stockage qui survive aux redémarrages de Jenkins et reste éditable pour les reprises (halte, rejeu).

**Sensibilité de l'état : faible, avec une exception.** Ce fichier ne contient aucun secret. Le plus souvent, une altération ne fait que bloquer ou retarder le bot : halte forcée, builds sautés, blocage prolongé. La CI reste rouge et la panne se voit. L'exception est `pending.fix_commit_sha` : en cas de rollback, le poller fait `git revert` de ce commit puis pousse. Un état altéré pourrait donc faire annuler par le bot un commit quelconque, un correctif de sécurité par exemple. Un garde-fou peu coûteux supprime ce cas : ne revertir qu'un commit dont l'auteur est `RHDemo FixCVE Bot` et qui est présent sur la branche. Avec lui, l'état n'a plus d'enjeu d'intégrité.

**Isoler l'état de la CI est de toute façon illusoire.** Chaque agent monte `/var/run/docker.sock` de l'hôte : un build CI, donc du code venu de la branche, peut lancer `docker run -v <n'importe quel volume>` et lire ou modifier tous les volumes, y compris celui de Jenkins. Un second modèle d'agent avec un volume « privé » n'apporte donc pas d'isolation de sécurité ; son intérêt est le rangement : le volume d'état n'apparaît pas dans le système de fichiers des autres jobs, ce qui écarte une altération accidentelle.

Volumes et montages de l'agent actuel (modèle `builder`, `jenkins-casc.yaml`) :

| Montage | Destination | Contenu |
| --- | --- | --- |
| `/var/run/docker.sock` et `/usr/bin/docker` de l'hôte | idem | Accès complet au démon Docker de l'hôte |
| Volume `rhdemo-maven-repository` | `/home/jenkins/.m2` | Dépôt Maven local, base NVD de Dependency-Check (`dependency-check-data/`) |
| Volume `rhdemo-trivy-cache` | `/home/jenkins/.cache/trivy` | Base de vulnérabilités de Trivy |
| Volume `rhdemo-wdm-cache` | `/home/jenkins/.cache/selenium` | Pilotes de navigateur de Selenium |
| `registry.crt`, `root-ca.crt` du dépôt | `/etc/ssl/certs/`, lecture seule | Certificats du registre et de l'autorité locale |

**Décision (T2)** : modèle d'agent dédié `fixcve`, seul à monter le volume `rhdemo-fixcve-state`. `instanceCapStr` valant par modèle, le nuage Docker est plafonné à un conteneur (`containerCap: 1`) pour garder « un seul build à la fois ». Garde-fou sur l'auteur du commit reverti retenu.

### 3.3 Déclenchement et phase B

Le bot a deux moments d'action :

- **phase A** : un build CI échoue sur Trivy ou Dependency-Check ;
- **phase B** : le build CI qui contient le correctif se termine, **quel que soit son résultat** (succès : validé ; échec : validation partielle ou rollback).

Un simple `post { failure }` ne suffit donc pas : il faut déclencher le job à la fin de **chaque** build CI (`post { always }`, `wait: false`), le poller décidant s'il y a quelque chose à faire. Coût : un démarrage d'agent (de l'ordre de la minute) après chaque CI, même quand il n'y a rien à faire. On peut l'éviter en ne déclenchant que sur échec, ou quand un correctif attend sa validation. Cela demande que la CI connaisse l'état du bot, ce qu'il vaut mieux éviter. **Décision (T3)** : `post { always }`.

Un déclenchement perdu (Jenkins redémarré pendant que le job est en file) doit être rattrapé. Le poller sait déjà reprendre depuis `last_processed_build` : un cron de secours du job suffit.

### 3.4 File d'attente unique

Avec un seul agent à la fois, fixcve passe après la CI qui l'a déclenché, puis bloque le build suivant pendant son cycle. La recherche, `mvnw dependency:list` et le rescan Dependency-Check prennent de quelques dizaines de secondes à quelques minutes, une fois le cache NVD à jour (19 s pour le build #970). C'est acceptable, mais un cycle bloqué retient toute la file. Le job a donc besoin d'un `timeout` (proposition : 30 min), avec remise du worktree dans un état propre, ce que fait déjà `discard_unapplied_changes`.

Pas de boucle nouvelle : le push du bot déclenche la CI par le `pollSCM` habituel, et les garde-fous anti-boucle du poller restent inchangés.

### 3.5 Credentials

| Secret | Aujourd'hui | Dans Jenkins |
| --- | --- | --- |
| Token Codeberg du bot fixcve | `kv/fixcve/codeberg`, lu par l'AppRole `fixcve` | `kv/jenkins/fixcve-forgejo-token` lu par l'AppRole `jenkins`, ou AppRole dédié (T4) |
| Clé NVD | `kv/fixcve/nvd` | Credential `nvd-api-key`, déjà utilisé par la CI : `kv/fixcve/nvd` disparaît |
| Token API Jenkins du compte `claude` | `kv/fixcve/jenkins` | Inutile pour le bot (`copyArtifacts`) ; reste pour le skill `/fixcve` en local |
| `secret_id` AppRole `fixcve` (fichier mode 600 sur le poste) | `rotate-secrets.py openbao-approle-fixcve` | Disparaît si T4 retient l'AppRole `jenkins` |

Conséquence sur le rayon d'action : une compromission de Jenkins donnera aussi le token du bot fixcve. Le gain pour l'attaquant est faible, puisque Jenkins détient déjà `ci-bot-forgejo-token` avec les mêmes droits sur le dépôt. En contrepartie, un secret quitte le poste.

**Push sans exposer le token** : `Jenkinsfile-Renovate` pousse avec le token dans l'URL (`https://${FORGEJO_TOKEN}@codeberg.org/…`). L'URL est visible dans `ps` le temps du `git push`, contraire à l'invariant « jamais en argument de commande ». Le bot doit garder son `GIT_ASKPASS` actuel ; la correction de Renovate est à traiter à part.

### 3.6 Exploitation

Les opérations faites aujourd'hui à la main par `jq` sur `state.json`, sous `flock`, doivent trouver un équivalent :

| Opération | Proposition |
| --- | --- |
| Pause | Désactiver le job (bouton Jenkins ou `disabled(true)` dans JCasC) |
| Reprise après halte, revérifier un blocage, rejouer un build | Paramètre `ACTION` du job (`poll` par défaut, `resume`, `clear-blocked`, `replay`) avec `BUILD_TO_REPLAY` ; exécuté sous le même `disableConcurrentBuilds()` |
| Consulter l'état | `state.json` archivé à chaque build (artefact) |
| Indicateur `fixcve-stats.py` | Inchangé : il lit `fixcve-audit.jsonl`, versionné |

### 3.7 Tests et bascule

**Décision (T7)** : plus d'exécution locale du poller. Le cron, le clone isolé, `poll-sandbox.sh` et le faux Jenkins (`tests/fake_jenkins.py`) sont supprimés ; `fixcve-install.sh` ne garde que l'installation du skill interactif `/fixcve`. Les tests unitaires hors réseau (`tests/run-all.sh`, incidents rejoués) restent. Les essais du poller se font dans Jenkins : paramètre `DRY_RUN` du job (cycle complet, sans commit ni push, état non modifié), à lancer sur un build CI en échec réel ou rejoué.

**Jamais deux bots en même temps** : ils se disputeraient l'état et les pushes. Bascule en une fois : arrêt du cron, copie de `state.json` et des archives dans le volume `rhdemo-fixcve-state`, essai en `DRY_RUN`, activation du job. Retour arrière : désactiver le job ; sans mode local, la remédiation se fait alors avec le skill `/fixcve` en attendant la correction.

## 4. Décisions (2026-11-22)

| # | Question | Options étudiées | Décision |
| --- | --- | --- | --- |
| T1 | Racine de confiance | (a) Aucune : Jenkinsfile depuis la branche, comme CI et Renovate. (b) Pipeline écrit **dans JCasC** (`script` en ligne, rechargé seulement par l'admin) qui vérifie les empreintes des scripts contre un credential Jenkins `fixcve-trusted-sha256` (Secret file) avant tout `withCredentials`. (c) Job construit sur un commit approuvé (SHA ou tag) mis à jour à chaque approbation | **(a) Aucune**, comme CI et Renovate (§3.1). Recommandation initiale (b) non retenue |
| T2 | Stockage de l'état | (a) Volume dédié `rhdemo-fixcve-state` ajouté au modèle d'agent existant. (b) Sous-répertoire d'un volume existant (`rhdemo-maven-repository`). (c) Artefact du dernier build fixcve (`copyArtifacts` de `lastCompletedBuild`), archives de cycle en artefacts. (d) Branche git dédiée. (e) OpenBao KV | **Modèle d'agent dédié `fixcve`** avec le volume `rhdemo-fixcve-state`, nuage plafonné à un conteneur ; garde-fou sur l'auteur du commit reverti (§3.2) |
| T3 | Déclenchement | (a) `post { always }` de la CI + cron de secours horaire. (b) `post { failure }` seulement + cron pour la phase B. (c) cron Jenkins toutes les 15 min, poller inchangé | **(a)** `post { always }` + cron de secours horaire |
| T4 | Credential Codeberg du bot | (a) `kv/jenkins/fixcve-forgejo-token`, AppRole `jenkins`, comme les autres bots. (b) AppRole dédié, comme Cosign | **(a)** `kv/jenkins/fixcve-forgejo-token`, AppRole `jenkins` |
| T5 | Lecture des rapports | (a) `copyArtifacts` + option `--reports-dir` de `fixcve-detect.py`. (b) API REST avec un token Jenkins | **(b), révisée à la mise en œuvre** (initialement (a)) : le bot lit aussi dans Jenkins le stage en échec (`wfapi`), l'extrait de console (cause d'un rollback, cas #972), le commit construit et le dernier build terminé (cron de secours) ; le rapport OWASP est publié par `publishHTML`, invisible de `copyArtifacts`. Token lecture seule du compte `claude` en credential `fixcve-jenkins-api` (`kv/jenkins/`) |
| T6 | Publication par branche de validation (proposition J de [FIXCVE_AUTO_REFONTE.md](FIXCVE_AUTO_REFONTE.md)) | Avec cette évolution, ou après | **Après**, évolution séparée |
| T7 | Exécution locale | (a) Garder le poller lançable sur le poste (tests, secours). (b) Retirer le mode local | **(b) Mode local retiré**, essais dans Jenkins par `DRY_RUN` (§3.7) |
| T8 | Notifications | Mail sur halte, `ALERTE`, blocage confirmé (CVSS ≥ 9), rollback ; rien sur un passage à vide | **Retenu** : mail sur halte, `ALERTE`, blocage confirmé, rollback ; rien sur un passage à vide |

## 5. Architecture cible

```text
RHDemo-CI  ── post { always } ──> build job: 'RHDemo-FixCVE' (wait: false)
                                    paramètres : CI_BUILD_NUMBER, CI_RESULT, FAILED_STAGE, BRANCH
RHDemo-FixCVE (Jenkinsfile-FixCVE lu sur la branche, agent « fixcve », cron de secours horaire,
               paramètres ACTION et DRY_RUN, timeout 30 min, disableConcurrentBuilds)
  1. checkout de BRANCH
  2. copyArtifacts(RHDemo-CI, CI_BUILD_NUMBER) : trivy-reports/, dependency-check-report.html
  3. withCredentials(fixcve-forgejo-token, nvd-api-key) → fixcve-auto-poll.sh
       état : volume rhdemo-fixcve-state ; push par GIT_ASKPASS (aucun en DRY_RUN)
  4. archive de state.json ; UNSTABLE + mail si halte, ALERTE, blocage ou rollback
```

## 6. Plan de mise en œuvre

| Étape | Contenu | Effort |
| --- | --- | --- |
| 1 | Poller adapté à Jenkins : rapports locaux (`--reports-dir`), branche et build en paramètres, `DRY_RUN`, actions d'exploitation ; retrait du mode local (épinglage, clone isolé, lecture de la copie principale, API Jenkins, amorçage NVD, lecture d'OpenBao par AppRole) ; revert limité aux commits du bot ; tests unitaires | 1 j |
| 2 | `Jenkinsfile-FixCVE` ; JCasC : modèle d'agent `fixcve` et volume `rhdemo-fixcve-state`, `containerCap: 1`, job `RHDemo-FixCVE` (paramètres, cron de secours) | 1 j |
| 3 | `Jenkinsfile-CI` : déclenchement en `post { always }` avec le stage en échec | 0,5 j |
| 4 | Credentials : `kv/jenkins/fixcve-forgejo-token` (`openbao-setup.py`, inventaire, `rotate-secrets.py`), suppression de `kv/fixcve/*` et de l'AppRole `fixcve` ; `fixcve-install.sh` réduit au skill ; `poll-sandbox.sh` et `fake_jenkins.py` supprimés | 0,5 j |
| 5 | Bascule (§3.7) avec essai en `DRY_RUN`, observation sur quelques cycles réels, docs (FIXCVE_AUTO.md, OPENBAO.md, ROTATION_SECRETS.md, INSTALLATION_COMPLETE.md) | 0,5 j |

## 7. Constat annexe

`Jenkinsfile-Renovate` met le token `ci-bot-forgejo-token` dans l'URL du `git push` (§3.5). L'URL est visible dans la liste des processus de l'agent pendant le push. Correction indépendante de cette étude : `GIT_ASKPASS` ou en-tête `http.extraHeader` passé par l'environnement.

## 8. Mise en œuvre (2026-11-22)

- `Jenkinsfile-FixCVE` et job `RHDemo-FixCVE` (JCasC : paramètres `ACTION`, `BUILD_TO_REPLAY`, `DRY_RUN`, `CI_BUILD_NUMBER`, cron de secours horaire) ; déclenchement best-effort dans le `post { always }` de `Jenkinsfile-CI`.
- Modèle d'agent `fixcve` : volumes `rhdemo-maven-repository` et `rhdemo-fixcve-state`, **sans socket Docker** ni certificats locaux ; `containerCap: 1` sur le nuage ; répertoire du volume créé dans `Dockerfile.agent`.
- `fixcve-state.sh`, point d'entrée : actions d'exploitation sous le verrou, `DRY_RUN` sur une copie jetable de l'état.
- `fixcve-auto-poll.sh` : credentials par variables d'environnement, checkout neuf placé sur `origin/<branche>`, attente du build CI déclencheur, push avec rejeu sur origin s'il est refusé (état mis à jour seulement après un push réussi), notifications. Retirés : clone isolé, lecture de la copie principale, épinglage, AppRole `fixcve`, arbre sale, amorçage NVD (`verify.py`).
- `fixcve-git-sync.sh` : revert limité aux commits du bot présents sur la branche (tests ajoutés).
- Credentials `fixcve-forgejo-token` et `fixcve-jenkins-api` dans `openbao-setup.py jenkins` ; commandes `fixcve`, `fixcve-nvd`, policy et AppRole `fixcve` supprimés ; inventaire mis à jour.
- Supprimés : `poll-sandbox.sh`, `fake_jenkins.py` ; `fixcve-install.sh` réduit au skill `/fixcve`.
- Constat : un agent inactif garde sa place `containerCap` pendant son `idleMinutes` (5 min pour `builder`) ; le passage fixcve démarre donc jusqu'à 5 min après la fin du build CI (contre 0 à 15 min avec le cron). L'agent `fixcve` est rendu après 1 min.
- Vérifié avant suppression du faux Jenkins, sur un origin local : passage hors périmètre, validation en `DRY_RUN` (état et origin intacts) puis réelle, `replay`, revert refusé sur un commit humain avec notification. Reste à valider dans Jenkins : JCasC (`containerCap`, modèle `fixcve`), droits du volume, push réel, mails.
