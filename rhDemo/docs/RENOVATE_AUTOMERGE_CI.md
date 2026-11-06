---
statut: actif
verifie_le: 2026-11-06
sources:
  - rhDemo/Jenkinsfile-Renovate
  - renovate.json
  - rhDemo/infra/jenkins-docker/jenkins-casc.yaml
---

# Mises à jour Renovate validées et mergées par Jenkins

Le job Jenkins `RHDemo-Renovate` ([`Jenkinsfile-Renovate`](../Jenkinsfile-Renovate)) exécute Renovate, puis valide et merge lui-même les PR de mise à jour de dépendances qu'il a ouvertes sur la branche d'évolution courante.

## Pourquoi Jenkins merge à la place de Renovate

Jenkins n'est pas exposé sur Internet : Codeberg ne peut pas lui envoyer de webhook, et les statuts CI ne remontent jamais vers Forgejo. Renovate, qui attend ces statuts pour merger, attendrait indéfiniment. Le job liste donc lui-même les PR Renovate par l'API Forgejo, les valide et les merge par la même API ; Renovate ne merge jamais (`automerge: false`).

Pistes écartées : faire remonter les statuts CI vers Forgejo (un passage de plus pour merger et un pipeline multibranche sur `renovate/*`), migrer la CI vers Codeberg Actions (refonte complète), relancer `Jenkinsfile-CI` pour chaque PR (Selenium, ZAP et SonarQube inutiles ici, durée de la CI complète) ou extraire build et tests dans une shared library (réécriture risquée de `Jenkinsfile-CI` en pipeline scripté).

## Déroulement d'un passage

Le job est déclaré dans [`jenkins-casc.yaml`](../infra/jenkins-docker/jenkins-casc.yaml) (job `RHDemo-Renovate`, déclenchement `cron` quotidien, `scriptPath` vers `Jenkinsfile-Renovate`). Ses builds ne se chevauchent pas (`disableConcurrentBuilds`), et Jenkins n'exécute qu'un agent à la fois.

1. **Scan Renovate** : Renovate tourne dans son image officielle et ouvre ou met à jour ses PR (voir [Exécution de Renovate](#exécution-de-renovate-dans-jenkins)).
2. **Liste des PR** : PR ouvertes dont la branche contient `renovate`, qui ciblent `BASE_BRANCH` et dont la branche vit dans le dépôt lui-même, jamais dans un fork.
3. **Pour chaque PR**, dans l'ordre :
   1. **Délai** : une PR dont Renovate n'a pas confirmé le délai de 7 jours ([section dédiée](#délai-des-nouvelles-versions)), ou qui ajoute une image `image:tag@sha256:…` trop récente ([section dédiée](#délai-des-images-docker)), est ignorée pour ce passage.
   2. **Synchronisation** : si la branche est en retard sur la base, merge de la base dans la branche et push (voir [Synchronisation](#synchronisation-avec-la-base)).
   3. **Validation** selon les fichiers modifiés (voir [Aiguillage](#aiguillage-de-la-validation)).
   4. **Merge** si la validation passe, sinon commentaire d'échec et PR laissée ouverte.
4. **Notification** : un mail n'est envoyé qu'en cas d'échec du build. Un succès qui merge déclenche `RHDemo-CI` sur la base, qui envoie son propre mail ; un passage sans PR à merger est le cas normal.

## Comptes et credentials

Deux comptes bot Codeberg distincts, aucun n'étant le compte personnel :

- **Le bot Renovate** *propose* les PR (credential `renovate-forgejo-token`).
- **Le bot CI `cibot-leuwen-lc`** *valide et merge* : il liste, synchronise, merge et commente (credential `ci-bot-forgejo-token`). Collaborateur du dépôt avec le droit Write, pas Admin ; token limité aux portées `repository` et `issue`.

Raisons : un token agit avec l'identité de son compte, même à portée réduite. Une fuite exposerait donc tous les dépôts du compte personnel, alors qu'un bot collaborateur d'un seul dépôt limite les dégâts à ce dépôt. Les merges automatiques restent aussi identifiables dans l'historique, et une rotation du mot de passe personnel ne casse pas la CI. Séparer celui qui propose de celui qui merge reproduit une revue à deux acteurs. Le token de fixcve-auto est encore un autre compte.

| Credential Jenkins | Type | Usage |
| --- | --- | --- |
| `renovate-forgejo-token` | Secret text | Renovate (portées `repository`, `issue` et `user` : sans `user`, l'initialisation de Renovate échoue en « Authentication failure ») |
| `renovate-gpg-key` | Secret text | Clé GPG privée en base64, signature des commits de Renovate |
| `renovate-github-token` | Secret text | Lecture des dépôts publics GitHub : notes de version et releases (dont celles de NGF) |
| `dockerhub-renovate-readonly` | Username with password | Identifiant Docker Hub (Docker ID, pas l'adresse e-mail) et jeton personnel de portée « Public Repo Read-only », avec date d'expiration. Sert uniquement aux dates de publication des images |
| `ci-bot-forgejo-token` | Secret text | Bot CI : liste, synchronisation, merge, commentaires |
| `kubeconfig-stagingkub-infra-upgrader` | Secret file | Dry-run des composants système sur stagingkub |
| `nvd-api-key` | Secret text | OWASP Dependency-Check |
| `notification-email` | Secret text | Destinataire du mail d'échec (adresse hors du dépôt public) |

Création des credentials : commentaires de `jenkins-casc.yaml`, section CREDENTIALS.

## Configuration Renovate

[`renovate.json`](../../renovate.json), à la racine du dépôt. **Renovate le lit sur `master`**, pas sur la branche d'évolution : toute modification doit être reportée sur `master` immédiatement.

| Réglage | Effet |
| --- | --- |
| `baseBranchPatterns` | PR ouvertes vers la branche d'évolution courante |
| `prCreation: "immediate"` | PR créée sans attendre de statut CI, qui n'arrivera jamais |
| `minimumReleaseAge: "7 days"` | Une version n'est proposée que 7 jours après sa publication (`timestamp-required` par défaut : sans date, pas de PR) |
| `matchUpdateTypes: ["major"]` → `dependencyDashboardApproval` | Montée majeure seulement après approbation dans le tableau de bord |
| `matchUpdateTypes: ["patch", "minor"]` → `automerge: false` | Renovate ne merge jamais lui-même |
| `kindest/node` → approbation, pas d'automerge | Changer la version de Kubernetes impose une reconstruction du cluster |
| `rhdemo-api`, manager `jenkins` → `enabled: false` | Image applicative et plugins Jenkins exclus |
| `osvVulnerabilityAlerts`, `rebaseWhen: "behind-base-branch"` | Alertes de vulnérabilité OSV ; rebase par Renovate quand la PR est en retard |

Les `customManagers` suivent ce que les managers natifs ne voient pas : images épinglées dans `Jenkinsfile-CI`, `values.yaml` et `kind-config.yaml` ; charts des composants système (`scripts/components/install-or-upgrade-*.sh`) ; Node et npm de `frontend-maven-plugin` ; Maven, SOPS, Helm et Cosign de `Dockerfile.agent` ; image de Renovate. Format des annotations : [IMAGE_VERSIONS_MANAGEMENT.md](IMAGE_VERSIONS_MANAGEMENT.md).

La branche d'évolution est écrite en dur à trois endroits : `BASE_BRANCH` de `Jenkinsfile-Renovate`, `baseBranchPatterns` de `renovate.json` et les `branches(…)` des jobs de `jenkins-casc.yaml`. `release.sh post-merge` les met à jour au changement de branche ([GIT-PROCEDURE-RELEASE.md](GIT-PROCEDURE-RELEASE.md)).

## Délai des nouvelles versions

Renovate n'applique `minimumReleaseAge` qu'au moment où il crée ou met à jour une branche. Une PR déjà ouverte n'est donc pas protégée si Renovate cesse de la mettre à jour. C'était le cas de #354 (maven 3.10), ouverte le 05/11 quand la règle docker désactivait le délai : Jenkins aurait pu la merger au bout de 55 h, et seul un conflit l'en a empêché.

Renovate publie l'état du délai sur chaque commit qu'il pousse, sous forme d'un statut `renovate/stability-days` (`pending` ou `success`). `Jenkinsfile-Renovate` lit ce statut sur le dernier commit de Renovate dans la PR (`git log --no-merges`, pour écarter les merges de synchronisation du job) et ne poursuit que s'il vaut `success`. Statut absent : PR antérieure à la règle, ignorée jusqu'à ce que Renovate la reprenne ; cocher la case de rebase de la PR force cette reprise.

Exception : une PR qui ne change **que des digests** d'image (lignes retirées et ajoutées identiques une fois les `@sha256:…` effacés). Renovate n'a aucune date pour un digest, son statut reste `pending` indéfiniment ; le contrôle des 48 h de la section suivante prend le relais.

## Délai des images Docker

Le délai `minimumReleaseAge` (7 jours) laisse le temps de détecter une version compromise avant de l'installer. Pour les images, il repose sur deux mécanismes, car Renovate ne retarde que les nouvelles versions, jamais les mises à jour de digest.

**Nouvelles versions : Renovate, avec Docker Hub authentifié.** Renovate a besoin de la date de publication de chaque tag. En anonyme, Docker Hub refuse la pagination au-delà de 1 000 tags (`pagination offset too large for anonymous requests`) : les grosses images (nginx, maven, postgres, eclipse-temurin, jenkins) n'avaient pas de date, et `minimumReleaseAgeBehaviour=timestamp-required` les laissait indéfiniment en « Pending Status Checks ». Aucune PR de tag d'image n'a été créée entre fin juillet et novembre 2026. Le stage « Scan Renovate » se connecte donc à Docker Hub avec `dockerhub-renovate-readonly`. L'API `hub.docker.com` n'accepte qu'un jeton Bearer : il est obtenu à chaque passage par `/v2/auth/token` et transmis à Renovate par `RENOVATE_HOST_RULES` (une authentification Basic est ignorée, même 403 qu'en anonyme ; test du 2026-11-06). La date retenue par Renovate est `tag_last_pushed`, fixée par Docker Hub et non par l'éditeur de l'image. Si la connexion échoue (jeton expiré ou révoqué), le build échoue, ce qui envoie le mail.

**Registres sans date.** Quay et ghcr ne fournissent aucune date. Les images qui en venaient sont désormais prises sur Docker Hub, chez le même éditeur et avec les mêmes digests (vérifié le 2026-11-06) : `keycloak/keycloak`, `prometheuscommunity/postgres-exporter`, `zaproxy/zap-stable`. Le chart NGINX Gateway Fabric, publié seulement en OCI sur ghcr, est suivi par les releases GitHub `nginx/nginx-gateway-fabric`, datées et alignées sur les versions du chart (`extractVersion` dans `renovate.json`).

**Mises à jour de digest : contrôle Jenkins de 48 h.** Renovate ne date pas la republication d'un tag et ne la retarde jamais : en octobre 2026, des PR de digest zaproxy (ghcr) et `inbound-agent` ont été créées et mergées sans aucune date disponible. Avant toute validation, `Jenkinsfile-Renovate` vérifie donc sur l'API publique de Docker Hub chaque référence `image:tag@sha256:…` ajoutée par la PR :

| Résultat | Condition | Effet |
|---|---|---|
| OK | digest identique au digest actuel du tag, publié depuis au moins `IMAGE_MIN_AGE_HOURS` (48 h) | suite du traitement |
| ATTENTE | publié depuis moins de 48 h, ou tag republié depuis (Renovate mettra la PR à jour) | PR ignorée pour ce passage |
| ERREUR | API injoignable, tag inconnu, date illisible | PR ignorée pour ce passage, jamais mergée |
| REFUS | registre hors Docker Hub | PR en échec |

Le contrôle est sans état : aucun commentaire ni fichier que le code non revu d'une PR pourrait antidater. Il s'applique aussi aux PR de version, déjà retardées de 7 jours par Renovate. Les 48 h sont comptées depuis la publication : la PR étant créée au plus un passage (24 h) après la publication, au moins 24 h séparent toujours sa création de son merge.

Limites :

- Renovate date une version par le dernier push de son tag : si le tag est republié pendant les 7 jours, le délai repart. Les rafales de republication observées durent quelques jours.
- `jenkins/inbound-agent` reste sur le tag flottant `latest-jdk25`. Ses tags versionnés (`3395.v6e5377b_0fb_3c-3-jdk25`) ne semblent pas comparables par le versioning `docker` de Renovate, qui cesserait alors de proposer des mises à jour ; à vérifier par un dry-run avant de l'épingler. Une nouvelle version de l'agent arrive donc comme une mise à jour de digest, avec 48 h de délai seulement.
- Une image référencée par tag sans digest (`RENOVATE_IMAGE`, images de SonarQube et du registre local) n'a que le délai de Renovate.
- Le jeton Docker Hub expire. Renouvellement : nouveau jeton personnel (portée « Public Repo Read-only ») sur hub.docker.com, puis mise à jour du credential Jenkins.

Historique : une première version (5 novembre 2026) comptait le délai depuis la première observation de la PR, datée par un commentaire du bot CI. Elle ne se terminait jamais (login du bot erroné) et relançait le délai à chaque nouveau digest ; elle a été remplacée le lendemain.

## Synchronisation avec la base

Une branche Renovate ancienne peut échouer pour une raison sans rapport avec elle, par exemple une CVE déjà corrigée sur la base. Si la base n'est pas un ancêtre de la PR (`git merge-base --is-ancestor`), le job merge la base dans la branche, par un merge classique, puis pousse avant de valider. Un merge `--squash` a été essayé puis abandonné : sans commit de fusion, git perd la trace des synchronisations précédentes et produit de faux conflits aux suivantes.

En cas de conflit :

- **PR dépassée** : si, pour chaque fichier en conflit, la base est déjà à une version supérieure ou égale (première version `"X.Y.Z"` du fichier, comparée par `sort -V`), une autre PR a déjà livré mieux. La PR est alors fermée automatiquement, avec un commentaire. Cas vécu : PR mineure de kube-prometheus-stack en conflit après le merge de la majeure.
- **Sinon**, commentaire « rebase manuel nécessaire » et PR comptée en échec. C'est toujours le cas pour les images épinglées par digest, dont le format n'est pas reconnu par cette comparaison.

Ce mécanisme coexiste avec le `rebaseWhen: "behind-base-branch"` de Renovate.

## Aiguillage de la validation

Un `mvnw verify` ne valide ni un composant Kubernetes ni une image Docker : le code Java ne change pas, les tests passeraient sans avoir exercé le changement. Le chemin de validation est donc choisi à partir de `git diff --name-only` (liste affichée dans la console avec le chemin retenu), parmi quatre chemins exclusifs, dans cet ordre :

| # | Détection | Validation |
| --- | --- | --- |
| 1 | Le diff touche `infra/stagingkub/scripts/components/install-or-upgrade-*.sh` ou `kind-config.yaml` | Dry-run Kubernetes + Trivy sur les images du chart |
| 2 | Le diff ne touche **que** `Jenkinsfile-CI` et/ou `infra/stagingkub/helm/rhdemo/values.yaml` | Trivy sur les images ajoutées |
| 3 | Le diff touche `pom.xml`, `frontend/package.json` ou `frontend/package-lock.json` | Maven (build, tests) + OWASP Dependency-Check |
| 4 | Aucun des cas précédents | Aucune : validation directe |

Un seul job liste, valide et merge : un second job séparé aurait dupliqué le listing, la synchronisation et le merge, avec un risque de traiter deux fois la même PR.

### 1. Composant système de stagingkub

Ces scripts pilotent Cilium, NGF, kube-prometheus-stack, Loki, Alloy et Grafana. Le job exécute le script modifié avec `HELM_DRY_RUN=true` contre le cluster réel, avec le kubeconfig de `jenkins-infra-upgrader`. Un `--dry-run=server` exige les mêmes droits qu'une exécution réelle : la protection vient de l'absence de persistance, pas d'un compte moins privilégié. `FORGEJO_TOKEN` n'est pas exposé à ce bloc, qui exécute un script venu d'une PR non revue.

Pendant le dry-run, `record_chart_images` (`rbac-preflight-check.sh`) écrit dans `CHART_IMAGES_FILE` les images rendues par `helm template`, avec les mêmes options que l'installation. Si le dry-run passe, ces images sont scannées par Trivy (seuil CRITICAL et `.trivyignore.yaml` identiques à `RHDemo-CI`, rapports dans `trivy-reports-pr<N>/`). Comportement fermé : aucune image listée, ou une référence au format inattendu, et la PR est refusée. Seuls les champs `image:` sont lus : une image passée en argument de conteneur (le config-reloader de prometheus-operator par exemple) n'est pas vue, et une image que le chart n'épingle pas par digest (NGF) est scannée sur son tag du moment. `kind-config.yaml` n'a pas de script composant : seul son changement de version déclenche ce chemin, et il exige de toute façon une approbation manuelle.

Après merge, le job déclenche `RHDemo-Stagingkub-Upgrade-Deploy` pour le composant concerné, sans attendre sa fin ([STAGINGKUB_REBUILD_PIPELINE.md](STAGINGKUB_REBUILD_PIPELINE.md)).

**CRDs Gateway API de NGF.** `install-or-upgrade-ngf.sh` applique le manifeste vendoré `gateway-api-crds/v<NGF_VERSION>/crds.yaml` et échoue s'il manque. Renovate le produit lui-même dans la PR de montée : `postUpgradeTasks` de `renovate.json` lance `vendor-gateway-api-crds.sh <nouvelle version>`, qui lit la version de Gateway API épinglée par NGF puis télécharge l'asset `standard-install.yaml` de cette release (sans `kubectl`, absent de l'image Renovate), et supprime le manifeste de l'ancienne version. Renovate n'exécute que les commandes autorisées par l'option globale `allowedCommands`, fixée dans `Jenkinsfile-Renovate` (`RENOVATE_ALLOWED_COMMANDS`) par une expression ancrée qui n'admet que ce script suivi d'un numéro de version ; la commande est lancée sans shell. Si la tâche échoue, Renovate le signale dans la PR et le dry-run échoue faute de manifeste : la PR n'est pas mergée.

Prérequis et incidents passés :

- L'agent n'est relié par défaut qu'au réseau `rhdemo-jenkins-network`. Le stage le connecte au réseau Docker `kind` (`lib.dockerNetworkConnect`) et l'en déconnecte dans `post { always }`, comme `Jenkinsfile-CD`. Les premiers dry-run, lancés sans cette connexion, échouaient sur la résolution DNS de `rhdemo-control-plane`.
- `kubectl cluster-info` liste les Services de `kube-system`, ce que `jenkins-infra-upgrader` n'a pas le droit de faire : trois PR ont échoué sur ce faux problème RBAC. Le test de connexion utilise `kubectl config current-context`, purement local.
- Si le cluster n'est pas démarré, le dry-run échoue avec un message explicite et la PR reste ouverte ; les autres PR du passage sont traitées.

### 2. Image épinglée dans `Jenkinsfile-CI` ou `values.yaml`

Le job extrait les références `repo:tag@sha256:…` ajoutées dans ces deux fichiers et les scanne avec Trivy, avec le même seuil et les mêmes exceptions que `RHDemo-CI`. Le rapport est nommé d'après le dernier segment du nom d'image (`keycloak/keycloak` → `keycloak`). Si aucune référence reconnue n'est trouvée, la PR échoue avec un commentaire dédié.

En pratique, ce chemin ne concerne que `busybox` et `postgres-exporter`, qui ne figurent que dans `values.yaml`. Une PR postgres, keycloak ou nginx touche aussi les fichiers Docker Compose de dev et d'ephemere : elle relève du chemin 4.

### 3. Dépendances Maven ou npm

Build Maven, tests et OWASP Dependency-Check sur la branche de la PR. Ce bloc exécute le code non revu de la mise à jour : il ne dispose que de `NVD_API_KEY`, jamais de `FORGEJO_TOKEN`. Le rapport OWASP est archivé par PR.

### 4. Validation directe

Sans manifeste de dépendances modifié, OWASP scannerait exactement le même arbre que sur la base : une CVE trouvée serait préexistante et sans rapport avec la PR. Exemple vécu, le build #45 : montée du tag de Renovate bloquée par une CVE d'une bibliothèque étrangère au changement. Bloquer serait inutile et injuste ; corriger une CVE existante est le rôle de `/fixcve` et fixcve-auto sur `RHDemo-CI`.

**Ce chemin merge sans scan préalable** les images des Dockerfiles et des fichiers Docker Compose : postgres, keycloak, nginx, base de l'application, builder Maven et images de l'usine logicielle. Le délai avant installation s'applique, et `RHDemo-CI` scanne ensuite sur la base les images qu'il couvre.

## Merge

Merge par l'API Forgejo en **squash** : un seul commit par PR, historique linéaire, branche supprimée. Cela suppose « Allow squash merging » activé dans les réglages du dépôt. L'appel est retenté jusqu'à quatre fois, car Forgejo refuse un merge tant qu'il recalcule l'état de la PR. Si l'API répond en erreur, le job relit l'état réel de la PR avant de conclure : un merge a déjà abouti malgré une réponse 504. Un commentaire indique le résultat sur la PR.

Après merge, `RHDemo-CI`, qui interroge la branche d'évolution toutes les 5 minutes, reconstruit et teste l'application complète, Selenium, ZAP et SonarQube compris.

## Exécution de Renovate dans Jenkins

Renovate tournait sur Codeberg Actions jusqu'à ce que le pool de runners `codeberg-medium` devienne indisponible de façon récurrente. Il tourne désormais dans le stage « Scan Renovate », avant la validation : un seul job et plus de dépendance à une CI externe. Le workflow `.forgejo/workflows/renovate.yml` a été supprimé ; il reste dans l'historique Git.

- **Image officielle** `renovate/renovate` (`RENOVATE_IMAGE`, suivie par Renovate lui-même), lancée en conteneur frère par docker-socket-proxy, et non `npm install -g renovate` sur l'agent : Renovate exige une version de Node récente que l'agent n'a pas.
- **Pas de bind-mount** : un chemin de l'agent n'existe pas forcément sur l'hôte Docker réel (Docker-outside-of-Docker). La clé GPG est passée en base64 par variable d'environnement et importée dans le conteneur.
- **`GNUPGHOME="${HOME}/.gnupg"`** : Renovate ne transmet pas un `GNUPGHOME` personnalisé aux processus git qu'il lance pour committer. Avec `/tmp/gnupg`, les commits échouaient en « No secret key ».
- **Jeton Docker Hub** : obtenu dans le même `sh` que `docker run`, sous `set +x`, et transmis uniquement par l'environnement (`RENOVATE_HOST_RULES`).

## Sécurité

- Seules les branches poussées dans le dépôt lui-même sont éligibles (`select(.head.repo.full_name == $repo)`), donc par un compte qui a déjà le droit Write ; les PR venant d'un fork sont ignorées.
- Le code d'une PR (dépendance mise à jour, non revue) ne s'exécute jamais avec `FORGEJO_TOKEN` en environnement : le token n'est ouvert que pour le push de synchronisation, les commentaires et le merge.
- Les montées majeures n'arrivent pas jusqu'au job sans approbation dans le tableau de bord.
- Délai avant installation : 7 jours pour une version (statut Renovate vérifié avant merge), 48 h pour un digest d'image.
- Renovate ne peut exécuter qu'une commande, le vendoring des CRDs de NGF (`RENOVATE_ALLOWED_COMMANDS`, option globale fixée dans le pipeline et non modifiable par `renovate.json`).
- Tous les tokens sont des credentials Jenkins ; aucun n'est en clair dans le dépôt.

## Limites connues

1. **Durée** : les PR sont validées l'une après l'autre, dans un build limité à 2 heures, avec un seul agent Jenkins pour tous les jobs. Un passage chargé (nombreuses PR Maven) peut atteindre la limite.
2. **Conflits entre PR** : deux PR qui modifient le même fichier peuvent entrer en conflit après le merge de la première ; voir [Synchronisation](#synchronisation-avec-la-base).
3. **Scan et validation liés** : si le scan Renovate échoue (image indisponible, configuration invalide, jeton Docker Hub expiré), la validation et le merge du passage sont sautés. Les séparer en deux jobs reste possible si cela devient gênant.
4. **Images non scannées avant merge** : voir le chemin 4.
