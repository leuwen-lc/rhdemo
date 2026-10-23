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
