---
statut: journal
verifie_le: 2026-10-22
sources:
  - rhDemo/docs/index.md
---

# Journal de la documentation

Journal chronologique en ajout seul : ingestions, contrôles (lint) et réorganisations de la documentation. Les entrées les plus récentes sont **en bas**. Chaque entrée commence par `## [date] opération | titre`, ce qui permet de les lister avec `grep "^## \[" rhDemo/docs/log.md`.

Opérations : `ingest` (nouveau document ou mise à jour après un changement du code), `lint` (contrôle de cohérence), `restructure` (classement, renommage), `query` (réponse conservée comme page).

---

## [2026-10-22] lint | liens cassés vers des documents renommés

Six liens de `CLAUDE.md` pointaient vers des fichiers inexistants (`NETWORK_SECURITY_POLICY`, `CERTIFICATS-WEB`, `TESTS_SECURITY_COVERAGE`, `REGISTRY_SETUP`, `LOKI_STACK_INTEGRATION`, `GRAFANA_DASHBOARD`). Les mêmes noms étaient cités dans `README.md`, `Jenkinsfile-CI`, `Jenkinsfile-CD`, `values.yaml`, `networkpolicy-keycloak.yaml` et le README des tests Spring Security : corrigés (commit `5046868`).

Reste non traité : `OBSERVABILITY_STACK_INTEGRATION.md` renvoie trois fois vers `../infra/stagingkub/GRAFANA_DASHBOARD.md`, qui n'existe pas.

## [2026-10-22] lint | dérive du README stagingkub

`infra/stagingkub/README.md` corrigé : PostgreSQL 18.4 (au lieu de 16), Keycloak 26.7.2, Cilium 1.20.2, Helm 4.x, `ProxySettingsPolicy` et `RateLimitPolicy` (au lieu de `SnippetsFilter`), étapes réelles de `Jenkinsfile-CD`. `values.yaml` : références NGF 2.4.0 corrigées en 2.6.0 (commit `293dad4`).

## [2026-10-22] restructure | statuts et sources

Frontmatter (`statut`, `verifie_le`, `sources`) ajouté aux 43 documents de `rhDemo/docs/` (commit `7b90bed`) : 24 actifs, 13 historiques, 3 propositions, 3 journaux. Sans frontmatter : `fixcve-audit.md` (généré) et `SECURITY_ADVISORIES.md` (modifié par `fixcve-auto`).

Reclassements décidés : `STAGINGKUB_REBUILD_PIPELINE` et `NGINX_GATEWAY_FABRIC_MIGRATION` en historique ; `FIXCVE_AUTO_TODO` en historique avec un bilan des éléments non appliqués (F, G, H, J, tests en CI) ; `FIXCVE_AUTO_INCIDENTS` en journal ; `ALLOY_MIGRATION` : statut corrigé, la migration est réalisée.

Anomalie signalée, non corrigée : `TESTS_REFONTE.md` affirme qu'un socle Vitest a été introduit, mais `frontend/package.json` ne contient ni Vitest ni test unitaire.

## [2026-10-22] ingest | création de l'index et du journal

Création de [index.md](index.md) (catalogue des 45 documents de `rhDemo/docs/` et des README dispersés dans le dépôt, par catégorie) et de ce journal.

## [2026-10-22] lint | premier passage de docs-lint

Création du contrôle `rhDemo/scripts/docs-lint.py` (lecture seule, tests dans `scripts/tests/test_docs_lint.py`) et du skill `/docs-lint`. Premier passage : frontmatter, index et journal conformes ; liens et références à corriger, **non corrigés à ce stade** :

- `OBSERVABILITY_STACK_INTEGRATION.md` : 3 liens vers `../infra/stagingkub/GRAFANA_DASHBOARD.md` (inexistant).
- `OWASP_DEPENDENCY_CHECK.md` : liens vers `OWASP_JENKINS_PLUGIN.md`, `SECURITY_LEAST_PRIVILEGE.md`, `../renovate.json` (le fichier est à la racine du dépôt), `../Jenkinsfile` (devenu `Jenkinsfile-CI`).
- `SOPS_SETUP.md` : liens vers `../Jenkinsfile`, `SECURITY_LEAST_PRIVILEGE.md`, `REFACTOR_SECRETS_NAMING.md`, `ENVIRONMENTS.md` (désormais `../infra/ENVIRONMENTS.md`).
- `RENOVATE_AUTOMERGE_CI.md` : lien vers `../../.forgejo/workflows/README.md` (inexistant).
- `PAKETO-DOCKERFILE-MIGRATION.md` (historique, laissé tel quel) : liens vers `../Jenkinsfile`, `CHANGELOG-JENKINS-STAGINGKUB.md`, `JENKINS-NETWORK-ANALYSIS.md` (qui se trouve dans `docs/`).

## [2026-10-22] lint | correction des liens morts

Liens rétablis : `../Jenkinsfile` vers `../Jenkinsfile-CI` (`OWASP_DEPENDENCY_CHECK`, `SOPS_SETUP`, `PAKETO-DOCKERFILE-MIGRATION`, l'ancre de numéros de ligne étant retirée car périmée), `../renovate.json` vers `../../renovate.json`, `ENVIRONMENTS.md` vers `../infra/ENVIRONMENTS.md`, `JENKINS-NETWORK-ANALYSIS.md` vers le dossier `docs/`.

Liens retirés faute d'équivalent : `GRAFANA_DASHBOARD.md` (3 renvois dans `OBSERVABILITY_STACK_INTEGRATION`), `OWASP_JENKINS_PLUGIN.md`, `SECURITY_LEAST_PRIVILEGE.md` (`OWASP_DEPENDENCY_CHECK`, `SOPS_SETUP`), `REFACTOR_SECRETS_NAMING.md`, `CHANGELOG-JENKINS-STAGINGKUB.md`. Dans `RENOVATE_AUTOMERGE_CI`, `.forgejo/workflows/README.md` est conservé comme simple mention « supprimé du dépôt ». Résultat de `docs-lint.py` : 0 erreur, 0 avertissement.

## [2026-10-22] lint | reformulation de la mention de Vitest

`TESTS_REFONTE.md` affirmait qu'un socle Vitest avait été introduit alors que `frontend/package.json` n'en contient pas : reformulé en « pourrait être ajouté, si cela s'avère pertinent », avec renvoi vers l'étude `TESTS_FRONTEND_UNITAIRES.md` (qui reste une proposition).


## [2026-10-23] ingest | SECURITE_CA_EMUDHRA_PLAN

Nouveau document de suivi de l'analyse d'impact CVE-2026-111943 (CA intermédiaires eMudhra) : contexte, évaluation de l'exposition, résultats de la phase 0 (mesure des trust stores de 10 images et de l'hôte) et plan d'action en 3 phases. Ajouté à `index.md` (section Sécurité).

## [2026-10-23] ingest | correctif OpenJDK dans SECURITE_CA_EMUDHRA_PLAN

Ajout de la section « Correctif OpenJDK / Temurin » : le correctif Java est le build 25.0.5.0.2 (blocked.certs), absent de 25.0.5+8 et pas encore publié en image Temurin. Plan ajusté (contournement par vérification de révocation, test de contrôle).

## [2026-10-23] ingest | test de contrôle dans SECURITE_CA_EMUDHRA_PLAN

Ajout de la section 3 ter : résultats du test de contrôle (hôtes we-have-a-problem.com) sur 7 JDK et sur les magasins système (agent, nœud KinD, Alpine, hôte), avec et sans vérification de révocation.

## [2026-10-23] ingest | phase 1 dans SECURITE_CA_EMUDHRA_PLAN

États de la phase 1 mis à jour (nœud KinD corrigé, agent et contrôleur reconstruits, digests épinglés) et ajout de la mesure d'impact de la vérification de révocation (non viable globalement).

## [2026-10-23] ingest | acceptations fixcve-auto dans SECURITE_CA_EMUDHRA_PLAN

Ajout de la section 3 quinquies (CVE-2026-114406 et CVE-2026-91403 acceptées temporairement par fixcve-auto sur l'image Keycloak) et de l'action 1.9 (suivi du correctif Red Hat).

## [2026-10-23] lint | relecture de CERTIFICATS_WEB, REGISTRY, SECURITE_JENKINS_SERVICEACCOUNT_RBAC, TRIVY_SECURITY_SCAN

Avertissements de `docs-lint.py` (sources modifiées : `init-stagingkub.sh`, `.trivyignore.yaml`). `CERTIFICATS_WEB` et `SECURITE_JENKINS_SERVICEACCOUNT_RBAC` relus, contenu inchangé, `verifie_le` mis à jour. `REGISTRY` corrigé : le registry est celui de Jenkins (`registry:3`, TLS autosigné) et le nœud KinD est configuré en HTTPS par `hosts.toml` (et non par un mirror HTTP) ; ajout de l'étape de mise à jour de `ca-certificates` du nœud. `TRIVY_SECURITY_SCAN` : ajout d'une section sur `.trivyignore.yaml` (CVE acceptées temporairement), absente jusque-là.

## [2026-10-23] lint | durées des pipelines dans PIPELINES_CI_CD

Les durées « ~2 h max » (CI) et « ~30 min max » (CD) étaient les `timeout` des Jenkinsfile, pas les durées normales : remplacées par ~8 min (CI) et ~2 min (CD) hors contention, avec les timeouts indiqués à part. Même correction dans `CLAUDE.md`. Valeurs fournies par le mainteneur, non mesurées.

## [2026-10-29] lint | SECURITE_CA_EMUDHRA_PLAN : réécriture autour de l'état courant

Mesure : Temurin 25.0.5+8 (agent Jenkins reconstruit sur `inbound-agent:latest-jdk25`, contrôleur sur `jenkins:2.580.2-lts-jdk25`) retire les racines emSign G3, C3 et C1 de `cacerts` et rejette la chaîne eMudhra, alors que `blocked.certs` reste à 39 lignes ; les images Ubuntu et Alpine de `eclipse-temurin` et `maven` (25.0.4.1) ne sont pas encore corrigées. Le document est réécrit en tableau d'état par composant, actions réalisées / restantes, durcissement, process : suppression de l'historique des actions palliatives (contournement par vérification de révocation CRL, mesures intermédiaires par phase, alternative `blocked.certs`). `verifie_le` mis à jour. `index.md` inchangé.

## [2026-10-29] ingest | cache NVD de l'hôte dans FIXCVE_AUTO et OWASP_DEPENDENCY_CHECK

Le rescan Dependency-Check de fixcve-auto est resté bloqué 52 min (build #967) sur un cache NVD de l'hôte vieux de 20 jours. Ajout de la section « Cache NVD de l'hôte » à `FIXCVE_AUTO.md` (amorçage depuis le volume Jenkins, suppression du rapport périmé, interruption d'un cycle, réamorçage manuel) et d'une ligne à `FIXCVE_AUTO_INCIDENTS.md`. `OWASP_DEPENDENCY_CHECK.md` : section « Cache local » corrigée (emplacement réel `~/.m2/dependency-check-data` et volume `rhdemo-maven-repository`, les chemins `target/` et `/var/jenkins_home` étaient faux), durées de rattrapage mesurées, usage par fixcve. Les descriptions valent une fois la modification de `verify.py` approuvée (`fixcve-install.sh --trust`). `index.md` inchangé.

## [2026-10-29] restructure | DECISIONS.md et allègement de CLAUDE.md

Création de `DECISIONS.md` : les sections « Pourquoi… ? » de `CLAUDE.md` y sont déplacées, avec ajout de la décision sur le merge Renovate piloté par Jenkins. `CLAUDE.md` réécrit de 526 lignes à environ 110 : suppression des sections redondantes avec les docs (sécurité détaillée, pipelines, dépendances, composants Vue, liste de liens), ajout d'un tableau « si tu touches à X, lis Y », des commandes essentielles et d'une règle « une information volatile = un seul fichier source ». Corrige au passage la mention erronée « Dockerfile OpenJDK 21 ». `index.md` : ligne ajoutée.

## [2026-10-29] ingest | écosystème javascript (RetireJS) dans fixcve-auto

Le rollback du build #972 venait d'un trou du détecteur : les findings RetireJS (`pkg:javascript/`, ici DOMPurify 3.4.13 dans swagger-ui) étaient ignorés en silence, le stage OWASP paraissait propre et le correctif valide du build #970 était annulé. Ajout de l'écosystème `javascript` (détection, schéma, suppression par `packageUrl`, bloqué si CVSS ≥ 9 sans correctif, pas de revérification automatique) et d'un garde-fou de validation (stage en échec identique au stage d'origine sans détection : correctif conservé tant que ses findings ne sont pas cités dans l'échec). Suppression temporaire de CVE-2026-116803 et CVE-2026-116804 (aucun swagger-ui publié avec DOMPurify ≥ 3.4.17). `FIXCVE_AUTO.md` et `FIXCVE_AUTO_INCIDENTS.md` mis à jour, `index.md` inchangé. Les modifications de `fixcve-auto-poll.sh` et `fixcve-detect.py` valent une fois approuvées (`fixcve-install.sh --trust`).

## [2026-10-29] ingest | rollback fixcve-auto : suppressions préservées et revert en conflit abandonné

Le build #975 a fait annuler à tort l'acceptation de risque du #974 (CVE DOMPurify nouvelle, sans lien), puis le `git revert` est entré en conflit avec un commit voisin et a laissé le clone isolé en revert inachevé : fixcve-auto est resté bloqué 9 cycles. Deux garde-fous : un correctif réduit à des suppressions/documentation n'est plus annulé pour une CVE nouvelle (verdict `next_stage`, le build est rejoué comme une nouvelle panne), et un revert en conflit est abandonné (`rollback_conflict`, correctif conservé, attente humaine). `FIXCVE_AUTO.md` et `FIXCVE_AUTO_INCIDENTS.md` mis à jour, `index.md` inchangé. À approuver avec `fixcve-install.sh --trust` (modification de `fixcve-auto-poll.sh`).

## [2026-10-29] ingest | webhook SonarQube bloqué et healthcheck sans wget

Timeout de l'étape Quality Gate (builds #978+) : SonarQube 26.10 refuse les webhooks vers une adresse privée (`jenkins:8080`), `waitForQualityGate` n'est jamais notifié. Ajout de `SONAR_VALIDATEWEBHOOKS=false` au service `sonarqube`. Healthcheck réécrit avec `curl` (l'image n'a plus `wget`, conteneur `unhealthy` en continu). `infra/jenkins-docker/README.md` : section SonarQube complétée. `index.md` inchangé.

## [2026-11-05] ingest | fixcve-auto : alerte sur les correctifs de distribution des suppressions Trivy

La suppression temporaire de CVE-2026-111497 (brotli-libs, image nginx éphémère) n'était jamais revérifiée : les entrées Trivy `[PENDING_UPSTREAM_FIX]` étaient seulement listées dans `poll.log`. fixcve lit désormais l'avis OSV de distribution (`<DISTRO>-<CVE>`, sans dépendre du nom de sous-paquet) pour les entrées portant le jeton `[OSV:…]` et écrit une ligne `ALERTE` si un correctif est publié dans la branche installée (constaté : brotli 1.2.1-r0 dans Alpine v3.24). Pas de montée automatique. `FIXCVE_AUTO.md` mis à jour, `index.md` inchangé. À approuver avec `fixcve-install.sh --trust` (modification de `fixcve_lib/osv.py` et `resolve.py`).

## [2026-11-05] ingest | revue des exceptions Trivy : montées Keycloak 26.8.1 et nginx alpine-slim

Revue des 8 exceptions de `.trivyignore.yaml` par scan Trivy (base du jour) des images actuelles et candidates. Keycloak 26.7.2 → 26.8.1 corrige netty-handler (CVE-2026-75595), bcprov (CVE-2026-8763), freemarker (CVE-2026-84939) et ca-certificates (CVE-2026-114406). nginx 1.31.3-alpine → 1.31.8-alpine-slim : aucun tag `alpine` ne corrige brotli-libs (CVE-2026-111497), la variante slim ne l'embarque pas (config éphémère limitée aux modules du cœur). libexpat (CVE-2026-32767) absent de l'image nginx actuelle : exception obsolète. Restent : gosu (permanente, non corrigée dans postgres 18.6) et java-21-openjdk (CVE-2026-91403, sans correctif dans Keycloak 26.8.1). `SECURITE_CA_EMUDHRA_PLAN.md`, `TRIVY_SECURITY_SCAN.md` et `infra/stagingkub/README.md` mis à jour, `index.md` inchangé. `SECURITY_ADVISORIES.md` : section de revue en tête et résolution notée dans les sections concernées (édition manuelle demandée).

## [2026-11-05] ingest | eMudhra : image de l'application sur Temurin 25.0.5

`rhDemo/Dockerfile` : base d'exécution montée de `eclipse-temurin:25.0.3_9-jre-noble` (non épinglée) à `25.0.5_8-jre-noble`, épinglée par digest. Racines emSign G3, C3 et C1 absentes de `cacerts`, `ca-certificates` 20260816 ; test de contrôle (section 3 ter) : chaîne G3 rejetée par le nouveau JRE, acceptée par l'ancien. Le builder `maven:3.9-eclipse-temurin-25-noble` reste en 25.0.4.1 avec G3 (aucune image Maven corrigée). `SECURITE_CA_EMUDHRA_PLAN.md` mis à jour, `index.md` inchangé.

## [2026-11-05] ingest | contrôle de fraîcheur de la base Trivy en CI

Le téléchargement de la base Trivy dans `Jenkinsfile-CI` est masqué par `|| true`, et les scans tournent en `--skip-db-update` : un échec de téléchargement laissait scanner sur une base périmée sans alerte. Ajout d'un contrôle après le téléchargement : échec du stage si la base `vuln` a plus de 72 h (`UpdatedAt`) ou si la Java DB a dépassé sa date `NextUpdate`. Vérifié le 2026-11-05 : la base réellement utilisée (volume `rhdemo-trivy-cache`) était à jour ; la base de janvier 2026 trouvée dans `/var/jenkins_home/.cache/trivy` n'est utilisée par aucun build. `TRIVY_SECURITY_SCAN.md` mis à jour, `index.md` inchangé.

## [2026-11-05] ingest | Renovate : quarantaine des images Docker par Jenkins

Diagnostic : aucune PR de tag d'image tierce depuis fin juillet. Renovate ne trouve aucune date de publication pour les images (Docker Hub : 403 « pagination offset too large for anonymous requests » au-delà de 1 000 tags ; Quay et ghcr : pas de date) et `minimumReleaseAgeBehaviour=timestamp-required` les laisse indéfiniment en « Pending Status Checks » (dry-run debug, même résultat avec Renovate 43.249.5 et 43.288.0). Correction en conservant le délai : `minimumReleaseAge: null` et trailer `Quarantaine-Image: oui` pour la source docker dans `renovate.json` ; `Jenkinsfile-Renovate` applique la quarantaine (durée = `minimumReleaseAge` global lu sur `master`, comptée depuis la date serveur du premier commentaire du bot CI). Builder `maven:3.9-eclipse-temurin-25-noble` épinglé par digest. `RENOVATE_AUTOMERGE_CI.md` et `SECURITE_CA_EMUDHRA_PLAN.md` mis à jour, `index.md` inchangé.

## [2026-11-05] ingest | stagingkub : déploiement Keycloak 26.8.1 bloqué par un split-brain

Montée de Keycloak 26.7.2 → 26.8.1 bloquée (release Helm 98 en `pending-upgrade`). Le Deployment, en `RollingUpdate` (surge 1, indisponibilité 0), fait coexister l'ancien et le nouveau pod sur la même base. La découverte `JDBC_PING` les met en relation, mais `keycloak-netpol` bloque JGroups (7800, 57800) : le nouveau pod se déclare en split-brain, partition perdante, et depuis la 26.8 sa readiness reste DOWN. L'ancien pod n'est donc jamais supprimé. Correctif du chart : `keycloak.strategy: Recreate` (deux versions ne tournent plus sur le même schéma) et `keycloak.cache: local` (instance unique, plus de clustering), sans ouvrir de nouveaux flux réseau. Section de dépannage ajoutée dans `infra/stagingkub/README.md`, `index.md` inchangé.

## [2026-11-05] ingest | stagingkub : passage de Keycloak en Recreate refusé par le server-side apply

Le CD suivant (révision Helm 99) échoue avec `spec.strategy.rollingUpdate: Forbidden`. Helm 4 applique en server-side apply et ne peut pas supprimer `rollingUpdate`, une valeur par défaut sans propriétaire ; `rollingUpdate: null` est refusé de la même façon (dry-run serveur). Correction faite une seule fois sur le cluster : patch JSON de `spec.strategy` en `{type: Recreate}`, puis dry-run du manifeste Helm accepté. Procédure ajoutée dans la section de dépannage de `infra/stagingkub/README.md`, `index.md` inchangé.

## [2026-11-05] ingest | stagingkub : stratégies de mise à jour déclarées explicitement

`rhdemo-app` (`strategy` RollingUpdate, `maxSurge: 1`, `maxUnavailable: 0`) et les StatefulSets `postgresql-rhdemo` et `postgresql-keycloak` (`updateStrategy` RollingUpdate, `partition: 0`) déclarent désormais leur stratégie dans le chart, paramétrée dans `values.yaml`. Helm devient propriétaire de ces champs : un futur changement de stratégie s'appliquera sans le patch manuel nécessaire pour Keycloak. Dry-run serveur en server-side apply (gestionnaire `helm`) : manifestes acceptés et Helm propriétaire de `type` et `rollingUpdate`. Aucun redémarrage de pod, le template des pods ne change pas. `index.md` inchangé.

## [2026-11-05] ingest | Renovate : login du bot CI déclaré en constante

Le premier passage du pipeline avec la quarantaine des images échoue : « Identité du bot CI introuvable (GET /user) ». `GET /user` exige le scope `read:user`, absent de `ci-bot-forgejo-token` (scopes `repository` + `issue`). Plutôt que d'élargir le token, `Jenkinsfile-Renovate` déclare `CI_BOT_LOGIN = 'rhdemo-ci-bot'` dans son bloc `environment`. `RENOVATE_AUTOMERGE_CI.md` mis à jour, `index.md` inchangé.

## [2026-11-05] ingest | périmètre Trivy : applicatif en CI, composants système avant merge Renovate

`Jenkinsfile-CI` scannait `NGF_IMAGE` (2.6.7) alors que le chart installé sur stagingkub (`NGF_VERSION`, 2.6.0) déploie une autre image, et ne scannait aucun autre composant système. `NGF_IMAGE` est supprimé ; la CI scanne en plus les images de `global.images` du chart `rhdemo` lues dans `values.yaml` (busybox et postgres-exporter n'étaient pas scannés). Dans `Jenkinsfile-Renovate`, le chemin « composant d'infra » scanne avec Trivy les images rendues par le chart (`record_chart_images` dans `rbac-preflight-check.sh`, activée par `CHART_IMAGES_FILE`), fail-closed. Listes d'images de fixcve alignées (`TRIVY_IMAGES`, `fixcve-validate-json.py`, `registry.py`). Nouvelle entrée dans `DECISIONS.md` ; `TRIVY_SECURITY_SCAN.md`, `RENOVATE_AUTOMERGE_CI.md` et `IMAGE_VERSIONS_MANAGEMENT.md` mis à jour, `index.md` inchangé.

## [2026-11-05] ingest | Jenkins : un seul agent à la fois

`instanceCapStr` du template Docker Cloud `builder` passé de 2 à 1 dans `jenkins-casc.yaml` : tous les jobs sont sérialisés. Motif : le job Renovate s'allonge avec le scan Trivy des images des composants système, et la CI (polling `H/5`) pouvait démarrer au milieu de ses merges ; CD et Stagingkub-Upgrade-Deploy pouvaient aussi agir en même temps sur stagingkub. Pas de blocage mutuel : les déclenchements entre jobs sont en `wait: false`. `infra/jenkins-docker/README.md` mis à jour ; `JENKINS_AGENTS_EPHEMERES.md` (historique) et `CICD_JENKINS_VS_FORGEJO_ACTIONS.md` (proposition) laissés en l'état. `index.md` inchangé.

## [2026-11-06] ingest | Renovate : délai des images Docker par Docker Hub authentifié

La quarantaine Jenkins du 2026-11-05 ne se terminait jamais : le login du bot déclaré en constante (`rhdemo-ci-bot`) ne correspond pas à l'auteur réel des commentaires (`cibot-leuwen-lc`), si bien que chaque passage repartait de zéro (PR #352, trois commentaires « première observation » portant la même clé). Plutôt que de la corriger, elle est remplacée. Un dry-run Renovate (Replay Jenkins, `RENOVATE_DRY_RUN=lookup`) montre qu'avec un jeton Docker Hub en Bearer (`/v2/auth/token` ; Basic ignoré) Renovate obtient les dates des grosses images (maven, renovate, sonarqube), mais n'en associe aucune aux mises à jour de digest, qu'il ne retarde jamais. Mise en œuvre : `minimumReleaseAge` natif pour les versions (règle docker `minimumReleaseAge: null` et trailer supprimés de `renovate.json`, credential `dockerhub-renovate-readonly`) ; contrôle sans état dans `Jenkinsfile-Renovate` : digest actuel du tag sur Docker Hub et publié depuis 48 h. Images de Quay et ghcr basculées sur Docker Hub, à digest identique : `keycloak/keycloak`, `prometheuscommunity/postgres-exporter`, `zaproxy/zap-stable:2.17.0` ; chart NGF suivi par les releases GitHub. Tags flottants remplacés par des tags versionnés de même digest : `maven:3.9.16-eclipse-temurin-25-noble`, `docker-socket-proxy:v0.5.0` (`inbound-agent:latest-jdk25` conservé). fixcve (`registry.py`, tests) aligné. Nouvelle entrée dans `DECISIONS.md` ; `RENOVATE_AUTOMERGE_CI.md`, `IMAGE_VERSIONS_MANAGEMENT.md`, `OBSERVABILITY_STACK_INTEGRATION.md`, `SECURITE_CA_EMUDHRA_PLAN.md` et le README du chart mis à jour, `index.md` inchangé.

## [2026-11-06] lint | images, observabilité et Renovate réalignés sur les sources

`IMAGE_VERSIONS_MANAGEMENT.md`, `OBSERVABILITY_STACK_INTEGRATION.md` et `RENOVATE_AUTOMERGE_CI.md` réécrits et vérifiés le 2026-11-06. Images : inventaire réel (Dockerfile, usine logicielle, `kindest/node`, images épinglées par tag seul), procédure manuelle sur le digest de l'index et non plus celui d'une plateforme, plus de versions recopiées. Observabilité : document de 1 985 lignes ramené à l'architecture et au mode opératoire, sans blocs YAML recopiés ; points ouverts relevés (rétention Loki sans `retention_enabled` à vérifier, datasource Prometheus déclarée deux fois, `grafana-gateway.yaml` inutilisé, Alertmanager sans destinataire, métriques Keycloak non collectées). Renovate : bot CI `cibot-leuwen-lc` (le compte `rhdemo-ci-bot` cité partout n'existe pas), déclenchement quotidien, branche d'évolution non recopiée, OSS Index non exposé au build, `RHDemo-CI` qui reconstruit après merge ; correction de l'aiguillage : une PR d'image qui touche aussi un fichier Compose ou un Dockerfile est validée sans scan (chemin 4), et non par Maven. Nom du bot et credential `dockerhub-renovate-readonly` alignés dans `jenkins-casc.yaml`, le README et le QUICKSTART de Jenkins, `FIXCVE_AUTO.md` et un commentaire de `Jenkinsfile-Renovate`. `index.md` inchangé.

## [2026-11-06] ingest | Renovate : statut de délai vérifié avant merge, CRDs NGF produites par Renovate

Premier passage du nouveau pipeline (build #159) : délai et Docker Hub conformes, mais deux échecs. #354 (maven 3.10), ouverte le 05/11 sous l'ancienne règle, n'a jamais eu le délai de 7 jours : Jenkins l'aurait mergée à 55 h sans un conflit. `Jenkinsfile-Renovate` exige désormais le statut `renovate/stability-days` = `success` sur le dernier commit de Renovate, sauf pour une PR de digest seul (statut toujours `pending`, couverte par les 48 h). #358 (NGF 2.8.0) échouait faute de CRDs vendorées : `postUpgradeTasks` de `renovate.json` lance `vendor-gateway-api-crds.sh`, réécrit sans `kubectl` (asset `standard-install.yaml` de Gateway API, mêmes objets que `kubectl kustomize`, vérifié pour NGF 2.6.0 et 2.8.0), seule commande autorisée par `RENOVATE_ALLOWED_COMMANDS`. Entrée précédente : opération corrigée en `lint`. `RENOVATE_AUTOMERGE_CI.md`, `IMAGE_VERSIONS_MANAGEMENT.md` et le README de stagingkub mis à jour, `index.md` inchangé.

## [2026-11-06] ingest | RBAC de jenkins-infra-upgrader pour NGF 2.8.0

Build #160 : le vendoring des CRDs par `postUpgradeTasks` fonctionne, mais le dry-run de #358 échoue sur le RBAC. Cinq nouvelles CRDs (`tcproutes`, `udproutes` de Gateway API v1.6, `accesspolicies`, `externalloadbalancers`, `payloadprocessors` de NGF) ajoutées à la liste `update`/`patch` ; bloc miroir du `ClusterRole` `ngf-nginx-gateway-fabric` ajouté, ce garde-fou anti-élévation ne s'étant jamais déclenché pour NGF avant que le chart modifie ce `ClusterRole`. Liste établie par un dry-run serveur sous l'identité du compte, puis vérifiée règle par règle contre `helm template` du chart 2.8.0. `rbac/README.md` de stagingkub mis à jour, `index.md` inchangé.
