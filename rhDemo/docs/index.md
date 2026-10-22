---
statut: actif
verifie_le: 2026-10-22
sources:
  - rhDemo/docs/
---

# Index de la documentation RHDemo

Catalogue des documents du projet : une ligne par page, classée par catégorie. Point d'entrée à lire en premier pour retrouver un document. Les modifications de ce catalogue sont tracées dans [log.md](log.md).

**Statuts** (champ `statut` du frontmatter de chaque document) :

| Statut | Signification | Règle de maintenance |
| --- | --- | --- |
| `actif` | Décrit l'état courant du code ou de la config | À garder aligné sur ses `sources` ; à corriger si elles divergent |
| `historique` | Trace d'une migration ou d'une refonte terminée | Figé : ne pas réécrire pour suivre l'état courant |
| `proposition` | Évolution étudiée, non validée | À reclasser (`historique` ou suppression) quand une décision est prise |
| `journal` | Audit, registre ou avis, en ajout seul | Immuable, sauf ajout d'entrées |

Les chemins du champ `sources` sont relatifs à la racine du dépôt. Un document sans frontmatter (`fixcve-audit.md`, `SECURITY_ADVISORIES.md`) est modifié automatiquement par `fixcve-auto` : son statut est donné ici.

---

## Vue d'ensemble et environnements

| Document | Statut | Résumé |
| --- | --- | --- |
| [README.md](../../README.md) | actif | Présentation du projet, feuille de route et changelog |
| [ENVIRONMENTS.md](../infra/ENVIRONMENTS.md) | actif | Comparaison des environnements dev, ephemere, stagingkub et Jenkins |
| [infra/dev/README.md](../infra/dev/README.md) | actif | Développement local avec PostgreSQL et Keycloak via Docker Compose |
| [infra/ephemere/README.md](../infra/ephemere/README.md) | actif | Environnement CI jetable en Docker Compose (Selenium, ZAP) |
| [infra/stagingkub/README.md](../infra/stagingkub/README.md) | actif | Environnement Kubernetes KinD : installation, déploiement, dépannage |
| [infra/jenkins-docker/README.md](../infra/jenkins-docker/README.md) | actif | Configuration de Jenkins CI/CD |
| [infra/jenkins-docker/QUICKSTART.md](../infra/jenkins-docker/QUICKSTART.md) | actif | Démarrage rapide de Jenkins |

## Pipelines CI/CD et chaîne d'outils

| Document | Statut | Résumé |
| --- | --- | --- |
| [PIPELINES_CI_CD.md](PIPELINES_CI_CD.md) | actif | Architecture des pipelines CI, CD et Renovate |
| [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md) | actif | Merge automatique des PR Renovate piloté par Jenkins |
| [GIT-PROCEDURE-RELEASE.md](GIT-PROCEDURE-RELEASE.md) | actif | Procédure de release : PR vers master, tag, retour en SNAPSHOT |
| [IMAGE_VERSIONS_MANAGEMENT.md](IMAGE_VERSIONS_MANAGEMENT.md) | actif | Épinglage des images Docker par digest et mises à jour Renovate |
| [REGISTRY.md](REGISTRY.md) | actif | Registry Docker local utilisé par stagingkub |
| [FIXCVE_AUTO.md](FIXCVE_AUTO.md) | actif | Remédiation CVE automatisée et déterministe (fixcve-auto) |
| [INVENTAIRE_COMPOSANTS_OPEN_SOURCE.md](INVENTAIRE_COMPOSANTS_OPEN_SOURCE.md) | actif | Inventaire des composants open source du projet |

## Sécurité

| Document | Statut | Résumé |
| --- | --- | --- |
| [SECURITE_WEB_CSP.md](SECURITE_WEB_CSP.md) | actif | Content Security Policy stricte et corrections ZAP |
| [CSRF_GUIDE.md](CSRF_GUIDE.md) | actif | Protection CSRF (cookie, Spring Security, Vue.js) |
| [SECURITE_NETWORK_POLICY.md](SECURITE_NETWORK_POLICY.md) | actif | Flux réseau légitimes et NetworkPolicies Zero Trust |
| [SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md](SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md) | actif | RBAC du ServiceAccount Jenkins (moindre privilège) |
| [SOPS_SETUP.md](SOPS_SETUP.md) | actif | Installation et usage de SOPS/AGE pour les secrets |
| [CERTIFICATS_WEB.md](CERTIFICATS_WEB.md) | actif | Certificats TLS stagingkub : auto-signés ou Let's Encrypt |
| [OWASP_DEPENDENCY_CHECK.md](OWASP_DEPENDENCY_CHECK.md) | actif | Scan des dépendances Maven et npm, seuils de blocage |
| [TRIVY_SECURITY_SCAN.md](TRIVY_SECURITY_SCAN.md) | actif | Scan des images Docker avec Trivy |
| [secrets/README-SECRETS-SEPARATION.md](../secrets/README-SECRETS-SEPARATION.md) | actif | Séparation des secrets entre ephemere et stagingkub |
| [SECURITY_ADVISORIES.md](SECURITY_ADVISORIES.md) | journal | Avis de sécurité et remédiations (alimenté par fixcve-auto) |
| [SECURITE_RHDEMO_AUDIT_20260424_REMEDIE.md](SECURITE_RHDEMO_AUDIT_20260424_REMEDIE.md) | journal | Revue de sécurité du 2026-04-24 et remédiations |
| [SECURITE_RHDEMO_AUDIT_20260522_REMEDIE.md](SECURITE_RHDEMO_AUDIT_20260522_REMEDIE.md) | journal | Audit de sécurité du 2026-05-22 (score 58/100) et remédiations |
| [FIXCVE_AUTO_INCIDENTS.md](FIXCVE_AUTO_INCIDENTS.md) | journal | Registre des incidents de fixcve-auto et des tests qui les rejouent |
| [fixcve-audit.md](fixcve-audit.md) | journal | Journal d'audit de fixcve-auto, généré depuis `fixcve-audit.jsonl` (ne pas éditer) |

## Application : backend, frontend, données

| Document | Statut | Résumé |
| --- | --- | --- |
| [DATABASE.md](DATABASE.md) | actif | Fichiers SQL de schéma et de données de test |
| [PAGINATION.md](PAGINATION.md) | actif | Pagination côté serveur et côté Vue.js |
| [PARAMETRAGE-APPLICATIF-AVEC-KUB.md](PARAMETRAGE-APPLICATIF-AVEC-KUB.md) | actif | Trois niveaux de paramétrage de l'application dans Kubernetes |
| [frontend/ROUTES_CONFIGURATION.md](../frontend/ROUTES_CONFIGURATION.md) | actif | Routes Vue.js avec préfixe `/front` |
| [frontend/GUIDE_NAVIGATION.md](../frontend/GUIDE_NAVIGATION.md) | actif | Menu de navigation du frontend |

## Tests

| Document | Statut | Résumé |
| --- | --- | --- |
| [TESTS_SECURITE_COUVERTURE.md](TESTS_SECURITE_COUVERTURE.md) | actif | Stratégie de tests et couverture des composants Spring Security |
| [TESTS_INTEGRATION_SANS_KEYCLOAK.md](TESTS_INTEGRATION_SANS_KEYCLOAK.md) | actif | Tests d'intégration sans dépendance à Keycloak (profil test) |
| [TESTS_MUTATION.md](TESTS_MUTATION.md) | actif | Tests de mutation avec PIT |
| [DATA_TESTID_GUIDE.md](DATA_TESTID_GUIDE.md) | actif | Attributs `data-testid` pour des tests Selenium robustes |
| [src/test/README.md](../src/test/README.md) | actif | Organisation des tests backend |
| [rhDemoAPITestIHM/README.md](../../rhDemoAPITestIHM/README.md) | actif | Tests IHM Selenium (projet séparé) |
| [rhDemoAPITestIHM/CONFIG.md](../../rhDemoAPITestIHM/CONFIG.md) | actif | Configuration des tests Selenium |
| [rhDemoAPITestIHM/KEYCLOAK_AUTH.md](../../rhDemoAPITestIHM/KEYCLOAK_AUTH.md) | actif | Authentification Keycloak pour les tests |

## Kubernetes et observabilité (stagingkub)

| Document | Statut | Résumé |
| --- | --- | --- |
| [OBSERVABILITY_STACK_INTEGRATION.md](OBSERVABILITY_STACK_INTEGRATION.md) | actif | Prometheus, Loki, Alloy et Grafana, dashboards |
| [POSTGRESQL_BACKUP_CRONJOBS.md](POSTGRESQL_BACKUP_CRONJOBS.md) | actif | Sauvegardes PostgreSQL par CronJobs, rétention 7 jours |
| [infra/stagingkub/rbac/README.md](../infra/stagingkub/rbac/README.md) | actif | RBAC Jenkins : `jenkins-deployer` et `jenkins-infra-upgrader` |
| [infra/stagingkub/networkpolicies/README.md](../infra/stagingkub/networkpolicies/README.md) | actif | NetworkPolicies des namespaces externes |
| [infra/stagingkub/helm/rhdemo/README.md](../infra/stagingkub/helm/rhdemo/README.md) | actif | Documentation du chart Helm rhdemo |
| [infra/stagingkub/jenkins-kubeconfig/README.md](../infra/stagingkub/jenkins-kubeconfig/README.md) | actif | Kubeconfigs RBAC de Jenkins |
| [infra/stagingkub/scripts/README-INIT-KEYCLOAK.md](../infra/stagingkub/scripts/README-INIT-KEYCLOAK.md) | actif | Initialisation de Keycloak sur stagingkub |
| [infra/stagingkub/scripts/README-helm-unlock.md](../infra/stagingkub/scripts/README-helm-unlock.md) | actif | Déblocage d'une release Helm en échec |
| [rhDemoInitKeycloak/README.md](../../rhDemoInitKeycloak/README.md) | actif | Outil de chargement initial des données Keycloak |

## Traces de migration (historique)

| Document | Statut | Résumé |
| --- | --- | --- |
| [SPRING_BOOT_4_MIGRATION.md](SPRING_BOOT_4_MIGRATION.md) | historique | Migration vers Spring Boot 4 et Spring Security 7 (livrée en 1.1.5) |
| [MIGRATION_HELM4_KUB1.36.md](MIGRATION_HELM4_KUB1.36.md) | historique | Migration Helm 3 vers 4 et Kubernetes 1.35 vers 1.36 (livrée en 1.1.10) |
| [NGINX_GATEWAY_FABRIC_MIGRATION.md](NGINX_GATEWAY_FABRIC_MIGRATION.md) | historique | Passage à NGINX Gateway Fabric et au Shared Gateway |
| [STAGINGKUB_REBUILD_PIPELINE.md](STAGINGKUB_REBUILD_PIPELINE.md) | historique | Mise à jour en place de l'infrastructure stagingkub |
| [ALLOY_MIGRATION.md](ALLOY_MIGRATION.md) | historique | Remplacement de Promtail par Grafana Alloy |
| [PAKETO-DOCKERFILE-MIGRATION.md](PAKETO-DOCKERFILE-MIGRATION.md) | historique | Abandon de Paketo pour un Dockerfile classique |
| [SONAQUBE_MIGRATION_PG18.md](SONAQUBE_MIGRATION_PG18.md) | historique | Migration de la base SonarQube vers PostgreSQL 18 |
| [JENKINS_AGENTS_EPHEMERES.md](JENKINS_AGENTS_EPHEMERES.md) | historique | Étude et plan de passage aux agents Jenkins éphémères |
| [JENKINS-NETWORK-ANALYSIS.md](JENKINS-NETWORK-ANALYSIS.md) | historique | Analyse des problèmes d'accès Jenkins vers stagingkub |
| [NULL_REFONTE.md](NULL_REFONTE.md) | historique | Refonte de la gestion des null (Java 25) |
| [TESTS_REFONTE.md](TESTS_REFONTE.md) | historique | Refonte du parc de tests backend |
| [API_REST_NORMALISATION.md](API_REST_NORMALISATION.md) | historique | Normalisation REST de l'API Employé |
| [FIXCVE_AUTO_TODO.md](FIXCVE_AUTO_TODO.md) | historique | Plan d'évolutions de fixcve-auto, essentiellement appliqué (voir le bilan en tête) |

## Propositions (non validées)

| Document | Statut | Résumé |
| --- | --- | --- |
| [IMPACT_CLEAN_ARCHITECTURE.md](IMPACT_CLEAN_ARCHITECTURE.md) | proposition | Analyse d'impact d'une migration vers la Clean Architecture |
| [CICD_JENKINS_VS_FORGEJO_ACTIONS.md](CICD_JENKINS_VS_FORGEJO_ACTIONS.md) | proposition | Comparaison Jenkins, Forgejo Actions et Woodpecker CI |
| [TESTS_FRONTEND_UNITAIRES.md](TESTS_FRONTEND_UNITAIRES.md) | proposition | Étude de tests unitaires frontend pour sécuriser les montées Renovate |

---

## Pour le LLM qui maintient ce wiki

- **Contrôler la cohérence** : `python3 -I rhDemo/scripts/docs-lint.py` (lecture seule) ou le skill `/docs-lint` (source : `rhDemo/scripts/docs-skills/docs-lint/SKILL.md`). Rapport d'abord, corrections après accord, entrée `lint` dans [log.md](log.md).
- **Ajouter un document** : poser le frontmatter (`statut`, `verifie_le`, `sources`), ajouter une ligne dans la bonne catégorie ci-dessus, journaliser dans [log.md](log.md).
- **Changer le statut d'un document** : modifier son frontmatter **et** la colonne Statut de cet index, puis journaliser.
- **Ne jamais réécrire** un document `historique` ou `journal` pour l'aligner sur l'état courant. Une divergence se signale, elle ne se corrige pas dans ces fichiers.
- **Ne pas copier** plus de 10 lignes de code : renvoyer au fichier (règle de `CLAUDE.md`).
- **Ne pas ajouter de frontmatter** à `fixcve-audit.md` (généré) ni à `SECURITY_ADVISORIES.md` (modifié par `fixcve-auto`, qui insère ses entrées après le premier `---`).
