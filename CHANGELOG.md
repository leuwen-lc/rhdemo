# Changelog

Toutes les évolutions notables du projet RHDemo, de la plus récente à la plus ancienne. Le format s'inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ; les numéros de version correspondent aux tags Git `X.Y.Z-RELEASE`. Le détail de chaque changement figure dans l'historique Git et dans le journal de la documentation ([rhDemo/docs/log.md](rhDemo/docs/log.md)).

## Version 1.1.11 (en cours)

Sécurité :
- Compromission des autorités de certification eMudhra (CVE-2026-111943) : ca-certificates à jour dans les images Jenkins et sur le nœud KinD, image applicative sur Temurin 25.0.5 (racines emSign retirées) épinglée par digest, contrôleur Jenkins 2.580.2-lts-jdk25, builder Maven 3.10.0 et SonarQube 26.11 sur Temurin 25.0.5 ; incident clos (voir rhDemo/docs/SECURITE_CA_EMUDHRA_PLAN.md)
- Contournement de Java4Shell (CVE-2026-114938, intrinsèque Base64 AVX-512, aucun JDK corrigé publié) par `-XX:-UseBASE64Intrinsics` sur Keycloak, l'application et Jenkins
- Durcissement de jenkins-docker : ports Jenkins, SonarQube et registry publiés sur 127.0.0.1 uniquement, port ZAP non publié et API ZAP restreinte, suppression des secrets par défaut (`sonar123` pour SonarQube, `changeme` pour ZAP), mot de passe admin Grafana d'au moins 16 caractères
- Étude de renouvellement rapide des secrets puis script `rotate-secrets.py` (phase 1) : inventaire sans valeur, rotation automatisée des tokens des bots Codeberg et de la clé GPG de Renovate, mot de passe SMTP vérifié avant propagation, révocation de l'ancien secret et rollback en cas d'échec (voir rhDemo/docs/ETUDE_ROTATION_SECRETS.md) ; étude d'OpenBao comme gestionnaire de secrets (voir rhDemo/docs/ETUDE_OPENBAO.md)
- Adresse de notification des pipelines sortie du code vers un credential Jenkins (dépôt public)
- Trivy : revue des exceptions (Keycloak 26.8.1, nginx 1.31.8-alpine-slim sans brotli-libs), stage en échec si la base de vulnérabilités est périmée, signalement des exclusions `.trivyignore.yaml` devenues obsolètes ; CI recentrée sur l'applicatif, composants système scannés avant le merge des PR Renovate
- OWASP Dependency-Check : tokens NVD et OSS Index passés par `settings.xml`, OSS Index réservé à RHDemo-CI avec cache de 7 jours (quota Sonatype), configuration alignée entre CI et Renovate
- CVE corrigées ou acceptées au fil de l'eau, majoritairement par fixcve-auto : jackson-databind, hibernate-core, hibernate-validator, qs, body-parser, follow-redirects, joi, node-forge, brace-expansion, shell-quote, netty, bcprov et freemarker embarqués dans Keycloak... (cf rhDemo/docs/SECURITY_ADVISORIES.md)

fixcve-auto :
- Procédure de remédiation entièrement déterministe, sans LLM : scripts testés `fixcve-resolve.py` (version corrigée lue dans l'avis OSV et confirmée par le registre), `fixcve-classify.py` (table de décision), `fixcve-apply.py` et `fixcve-verify.py` (vérification locale avant push) ; le skill /fixcve utilise les mêmes scripts (voir rhDemo/docs/FIXCVE_AUTO.md)
- Fiabilisation au fil des incidents : identité d'un finding = paire (CVE, paquet), CVE bloquées traitées sans bloquer le reste du cycle, validation par non-régression au lieu d'un rollback systématique, parser OWASP DC étendu (OSS Index, CVSS v4, RetireJS, Node Audit sans score), cache NVD amorcé depuis Jenkins, rejeu des commits du bot en cas de divergence ; registre des incidents et plan d'évolutions (voir rhDemo/docs/FIXCVE_AUTO_INCIDENTS.md et rhDemo/docs/FIXCVE_AUTO_TODO.md)
- Alerte quand une distribution publie le correctif d'une CVE supprimée temporairement dans Trivy

Frontend :
- Migration de Vue CLI (webpack) vers Vite 8 : 746 → 151 paquets npm, `npm audit` sans alerte, suppressions OWASP de la chaîne webpack retirées (voir rhDemo/docs/MIGRATION_VITE.md)

CI/CD :
- Renovate : délai de quarantaine des images (minimumReleaseAge de 7 jours grâce à un accès Docker Hub authentifié, digest publié depuis 48 h vérifié par `Jenkinsfile-Renovate`, statut `renovate/stability-days` exigé avant merge), images Quay et ghcr basculées sur Docker Hub à digest identique, CRDs Gateway API embarquées dans la PR de montée de NGF (`postUpgradeTasks`), suppression du workflow Forgejo Actions de secours (voir rhDemo/docs/RENOVATE_AUTOMERGE_CI.md)
- SonarQube démarré seulement pendant l'analyse et la Quality Gate (environ 1,3 Go libérés au repos), webhook Jenkins réparé pour SonarQube 26.10
- Signature cosign 3.x sans envoi au journal public Rekor
- Jenkins : contrôleur et agent en JDK 25, image du contrôleur épinglée par digest, un seul agent à la fois, nettoyage des volumes anonymes et des conteneurs d'agents orphelins (watchdog à 30 s), CI quotidienne à 5h00 et automerge Renovate à 6h00, mail d'échec pour `Jenkinsfile-Renovate`
- Contexte de build Docker réduit, logs Maven/npm allégés, couverture JaCoCo de nouveau affichée dans Jenkins

Infrastructure stagingkub :
- Keycloak déployé en `Recreate` avec cache local (la montée 26.8 restait bloquée en split-brain en RollingUpdate), stratégies de mise à jour déclarées explicitement dans le chart
- Script `repair-cluster-after-restart.sh` après un redémarrage du poste : IP du nœud KinD, raccordement du registry, conteneurs arrêtés, pods en ImagePullBackOff
- NGINX Gateway Fabric 2.8 : droits RBAC de `jenkins-infra-upgrader` pour les hooks et le rollback Helm, NetworkPolicy du hook cert-generator
- Observabilité : rétention Loki de 7 jours réellement appliquée (compactor), datasource Prometheus unique, suppression de grafana-gateway

Tests :
- Profil Maven `mutation` (PIT) pour un usage occasionnel hors CI, tests renforcés sur les mutants survivants (cookie CSRF, handler SPA, ports limites) (voir rhDemo/docs/TESTS_MUTATION.md)

Documentation :
- Frontmatter (statut, date de vérification, sources) sur les documents de rhDemo/docs, index et journal de la documentation, contrôle de cohérence `docs-lint.py` et skill /docs-lint (voir rhDemo/docs/index.md)
- Création de rhDemo/docs/DECISIONS.md (raisons des choix techniques, sorties de CLAUDE.md)
- Standards communautaires : code de conduite, guide de contribution, politique de sécurité, modèles de tickets et de PR
- Changelog extrait du README.md dans ce fichier CHANGELOG.md

Versions :
- Spring Boot 4.1.1 → 4.1.2, SpringDoc OpenAPI 3.1.0 → 3.2.0, Keycloak 26.7.2 → 26.8.1, nginx 1.31.3-alpine → 1.31.8-alpine-slim, SonarQube 26.8 → 26.11, Maven 3.10.1
- Diverses mises à jour Renovate : Vue 3.5.45, vue-router 5.4.0, Element Plus 2.14.8, Axios 1.21.1, Vite 8.3.8, Node.js 24.22.3, npm 12.2.2, Selenium 4.52.0, RESTEasy 7.0.6, Helm 4.3.2, cosign 3.1.4, NGINX Gateway Fabric 2.8.1, Cilium 1.20.4, kube-prometheus-stack 88.6.5, Loki 18.17.1, Alloy 1.15.0

## Version 1.1.10

Infrastructure :
- Migration Helm 3 → Helm 4 (agent Jenkins `HELM_VERSION=4.2.4`) et montée stagingkub Kubernetes 1.35 → 1.36.4 (`kindest/node`, KinD CLI 0.33+) livrées ensemble lors d'une reconstruction de cluster : renommage `--atomic` → `--rollback-on-failure` dans les 6 scripts `install-or-upgrade-*.sh`, `--dry-run=client` explicité dans `test-deploy-helm.sh`, point de vigilance server-side apply par défaut à l'installation neuve ; K8s 1.36 débloqué par Cilium 1.20 (matrice officielle K8s 1.33→1.36 ; 1.37 écarté) (voir rhDemo/docs/MIGRATION_HELM4_KUB1.36.md)
- Nouveau pipeline `Jenkinsfile-Stagingkub-Upgrade-Deploy` : application réelle (post-merge) des montées de version en place des composants d'infra stagingkub (Cilium, NGINX Gateway Fabric, kube-prometheus-stack, Loki, Alloy, Grafana) via des scripts idempotents `scripts/components/install-or-upgrade-<composant>.sh` avec rollback automatique ; la validation avant merge reste un `helm/kubectl --dry-run=server` sans mutation du cluster dans la boucle étendue de `Jenkinsfile-Renovate` (voir rhDemo/docs/STAGINGKUB_REBUILD_PIPELINE.md)
- ServiceAccount Kubernetes dédié `jenkins-infra-upgrader` (RBAC moindre privilège, credential distinct de `jenkins-deployer`) pour ces upgrades d'infra
- Cilium déplacé dans un namespace `cilium-system` dédié, stockage des releases Helm isolé
- Montées kube-prometheus-stack 87 → 88.5.4 (Prometheus Operator v0.93.1), Loki chart → v18, Cilium 1.19.5 → 1.20.1, NGINX Gateway Fabric 2.6.x (NodePorts via `nginx.service.nodePorts`, extraction CRDs compatible Helm 4)
- Routage de `/actuator/health` via le Gateway vers le port management de rhdemo-app (network policy egress `nginx-gateway` ajustée)

Observabilité :
- Migration Promtail → Grafana Alloy (Promtail EOL 02/03/2026), chart `grafana/alloy` (Alloy v1.18.0), licence Apache-2.0 (voir rhDemo/docs/ALLOY_MIGRATION.md)
- Bascule de Loki vers le fork communautaire OSS (chart v7 puis v18) pour éviter la licence AGPLv3
- Retrait du plugin Grafana déprécié `grafana-piechart-panel` ; autorisation du sidecar Grafana à joindre l'API server

CI/CD :
- Notifications email (email-ext) sur les pipelines RHDemo-CI, RHDemo-CD et RHDemo-Stagingkub-Upgrade-Deploy (succès/échec)
- PR Renovate mergées en squash pour un historique linéaire ; fermeture automatique des PR supersédées (supersession)
- Durcissement du pipeline Renovate contre une PR malveillante ; scope élargi aux images pré-épinglées (tag+digest) de stagingkub et `Jenkinsfile-CI`, `customManagers` pour les versions d'outils non détectées nativement, alertes de vulnérabilité OSV activées
- Comptes Codeberg bot dédiés pour le merge des PR Renovate et pour fixcve-auto
- Migration de la base SonarQube vers PostgreSQL 18
- Build frontend via `npm ci` (au lieu de `npm install`), version Node épinglée pour `frontend-maven-plugin` ; étude de tests unitaires frontend pour sécuriser les montées Renovate (voir rhDemo/docs/TESTS_FRONTEND_UNITAIRES.md)

Sécurité :
- Refonte de fixcve-auto en 3 phases à privilèges disjoints : détection déterministe (script Python `fixcve-detect.py`, remplace le skill), lookup sans credential exposé au contenu Internet, apply isolé sur un clone git dédié ; périmètre étendu aux dépendances npm du frontend, revalidation des CVE OS (Alpine/Debian/Ubuntu) via OSV.dev, suppression temporaire documentée autorisée pour CVSS < 9 sans correctif disponible (voir rhDemo/docs/FIXCVE_AUTO.md)
- OWASP Dependency-Check étendu aux dépendances npm du frontend (non déclenché sur les PR Renovate hors périmètre Maven/npm)
- CVE corrigées au fil de l'eau : CVE-2026-18963 (image Keycloak), CVE-2026-22184 (zlib dans nginx:alpine), CVE-2026-66299 (tomcat-embed-core), CVE-2026-69152 (brace-expansion), lot DOMPurify/swagger-ui via SpringDoc 3.1.0, nanoid 3.3.18 → 6.0.1 via overrides npm (CVE-2026-67214) (cf rhDemo/docs/SECURITY_ADVISORIES.md)

Versions :
- Spring Boot 4.1.0 → 4.1.1, SpringDoc OpenAPI 3.0.3 → 3.1.0, Tomcat embarqué 11.0.24 → 11.0.25, frontend-maven-plugin 2.0.1 → 2.0.2
- Diverses mises à jour Renovate : Vue 3.5.41, vue-router 5.2.0, Element Plus 2.14.5, Axios 1.19.0, Selenium 4.47.0, JUnit 6.1.3, Keycloak admin client 26.0.12, PostgreSQL 18.4, nginx 1.31.3, Temurin 25.0.4+7, SonarQube 26.8.0

## Version 1.1.9

Sécurité :
- Automatisation complète de remédiation CVE (fixcve-auto) : un script de polling détecte les échecs Trivy/OWASP-DC sur le pipeline CI et invoque Claude Code pour appliquer, committer et pousser un correctif sans validation humaine, avec rollback automatique et journal d'audit (voir rhDemo/docs/FIXCVE_AUTO.md)
- Remédiations de l'audit du 22/05 : PostgreSQL dev limité à localhost, HSTS avec preload, Permissions-Policy étendue, readOnlyRootFilesystem sur rhdemo-app, security.txt, validation du claim iss JWT en ephemere (voir rhDemo/docs/SECURITE_RHDEMO_AUDIT_20260522_REMEDIE.md)
- Rate limiting Nginx (ephemere) et NGF RateLimitPolicy (stagingkub) sur l'API et le login Keycloak, avec page d'erreur 429 personnalisée et notification Axios côté frontend
- Ajout des headers COOP/CORP/COEP
- Diverses CVE corrigées au fil de l'eau (postgresql-jdbc, Apache Tomcat, Spring Security, Spring Framework) (cf rhDemo/docs/SECURITY_ADVISORIES.md)

CI/CD :
- Automerge des PRs Renovate (patch/minor) : pipeline Jenkins dédié qui liste les PRs, resynchronise la branche avec la base si elle est en retard, build/teste/scanne OWASP, puis merge automatiquement si la CI passe (voir rhDemo/docs/RENOVATE_AUTOMERGE_CI.md)
- Rapatriement du scan Renovate lui-même depuis Codeberg Actions vers Jenkins, suite à l'indisponibilité récurrente du pool de runners codeberg-medium

Versions :
- Montée de version Spring Boot 4.0.6 → 4.1.0
- Diverses mises à jour au fil des CVE et des PR Renovate (Keycloak, PostgreSQL, Selenium, Vue.js, Jenkins et ses plugins...)

## Version 1.1.8

Architecture logicielle :
- Etude sur le passage à Clean Architecture (non appliqué voir rhDemo/docs/IMPACT_CLEAN_ARCHITECTURE.md)

Code Backend :
- Amélioration de la gestion des Null (voir rhDemo/docs/NULL_REFONTE.md)

CI/CD : 
- Passage à des agents jenkins ephemeres (voir rhDemo/docs/JENKINS_AGENTS_EPHEMERES.md)
- Ajout du plugin Jenkins matrix-auth pour gestion fine des droits (notamment pour user Claude Code)
- Verouillage des versions de plugin Jenkins dans un lockfile mis à jour par un script (sécurisation en remplacement des versions latest)

Tests : 
- Refonte des tests unitaires pour améliorer leur maintenabilité : suppression des tests triviaux et en doublon unitaires/intégration (voir rhDemo/docs/TESTS_REFONTE.md)
- ajout d'un test "property based" avec le framework jqwik

Sécurité :
- Diverses remédiations suite à un audit Claude Code (rhDemo/docs/SECURITE_RHDEMO_AUDIT_20260424.md)


## Version 1.1.7

Architecture logicielle : 
- Amélioration de la conformité REST de l'API Employe (voir rhDemo/docs/API_REST_NORMALISATION.md)
- Ajout d'une couche data transfer object (DTO) immutable (record) seule connue du Controller API pour stabiliser et sécuriser le contrat REST.

Sécurité :
- Tous les secrets manipulés temporairement au sein des chaines CI/CD positionnés dans un sous répertoire de /TMP avec des droits restreints
- Meilleure conformité IHM par rapport au rapport ZAP (certaines réponses ne comprenaient pas les entêtes CSP, samesite=strict sur le cookie anti-CSRF)

Versions : 
- Diverses mises à jour au fil des CVE levées par OWASP-DC et TRIVY
(cf rhDemo/docs/SECURITY_ADVISORIES.md )
- Utilisation de Renovate qui propose automatiquement des PR de mise à jour de version sur la branche en cours (commits laissés en anglais)

## Version 1.1.6

Fonctionnalités front :

- Ajout d'un bouton de logout OIDC (déjà implémenté sur /logout)
- Ajout de champs filtres sur la liste des employés, interfacé avec la pagination coté back
- Transmission et application des roles sur le front : boutons de maj grisés si profil consult (avant : erreur coté back uniquement)

Sécurité rhDemo :

- Ajout de security context sur les déploiement helm (runAsNonRoot: true) contournement pour Postgres qui nécessite un démarrage root
- Ajout de Pod Security Admission en mode audit/warn (enforce difficile avec Postgres)
- Activation de PKCE S256 (paramétrage Keycloak) pour sécuriser le dialogue OIDC (recommandé même en BFF)

Seleniumn amélioration des diagnostics

- Screenshot en cas d'erreur
- retry "flaky" une fois en cas d'echec sur timeout
- assertions enrichies avec des éléments de contexte

Versions

- Passage à PostgreSQL 18.2 (CVE) et Postgres_exporter en 0.19.0 (Compat)
- généralisation du suffixage des versions de container avec le digest sha256 (pinning)

## Version 1.1.5

Outillage CI-CD (infra/jenkins-docker)

- Séparation de Jenkins en une instance master de pilotage et un agent spécialisé pour le build (recommandations sécurité)
- Remplacement plugin Jacoco obsolète par Coverage Plugin
- Montée de niveau SonarQube (26.2.0.119303)

Applicatif rhDemo

- Montées de version (cf rhDemo/docs/SPRING_BOOT_4_MIGRATION.md):
  - Java 25, Spring Boot 4.0.2, PostgreSQL 18.1, Keycloack 26.5.0
  - Junit 6.0.2, Selenium 4.40,
  - Frontend : Actualisation des versions par NPM update (cf package-lock.json)

Environnement stagingkub

- Passage de Ingress Nginx (fin de vie mars 2026) à Nginx Gateway Fabric 2.4 (cf rhDemo/docs/NGINX_GATEWAY_FABRIC_MIGRATION.md)
- Adaptation des network policies
- "Pin" des versions des outils d'observabilité (prometheus, loki, grafana,...) pour éviter l'instabilité liée aux versions "latest"

## Version 1.1.4

Environnement de Stagingkub

- Ajout d'un tableau de bord Grafana exposant les métriques Spring Actuator/Micrometer(métriques JVM, Http, Pool de connexion db, ...) exposées sur le end point prometheus (port dédié non exposé en externe).

- Ajout d'un tableau de bord Grafana exposant les métriques PostgreSQL (stats requètes, connexions, cache, ...)  via postgres-exporter pour Prometheus.

- Suppression de la commande kind dans le container Jenkins et passage par un compte de service avec des droits limités par RBAC.

- Ajout d'une network policy stricte pour le namespace rhDemo avec notammentinterdiction de toute sortie Egress.

- Ajout de Cilium a la place du CNI par défaut de Kind pour pouvoir appliquer la Network policiy, ajout d'un script de test des flux autorisés/interdits pour valider.

- Montée de niveau sur Kind 0.31 et Kubernetes 1.35.0

- Changement de nom de domaine des environnements web stagingkub : utilisation de intra.leuwen-lc.fr pour l'applicatif (rhdemo-stagingkub.intra.leuwen-lc.fr), keycloak et grafana. Comme je possède ce nom de domaiene Ceci permet me d'utiliser des certificats Let's Encrypt, les certificats auto-signés peuvent également être utilisés par simple modification de la config Helm.

- Ajout d'un handler spécifique pour le logout OIDC qui ne fonctionnait pas car en standard il utilise issuer-uri qui n'est pas configurable, le pod ne pouvant résoudre l'url externe. On dérive donc l'url de logout de l'authorization-uri

## Version 1.1.3

Environnement stagingkub

- Amélioration de la config Spring Boot et Keycloak pour suppression de warnings sur l'env stagingkub

- Ajout de sauvegardes quotidiennes des bases postgresql applicative et keycloak via cronjob. Invalidation de CloudNativePG qui nécessite un stockage évolué (CNI ou S3) trop lourd pour un environnement sur PC.

- Ajout d'extramounts Kind (volumes pointant sur l'hote) et de PV créés manuellement, en remplacement de la création dynamique de PVC par volumeClaimTemplate pour éviter la perte des volumes postgresql/backup lors de la recréation du cluster KinD.

- Ajout de Prometheus et d'un dashboard grafana générique sur les VM applicatives

CI/CD

- Passage du registry docker en https

- Ajout d'une signature de l'image applicative produite par la CI avec Cosign

- Signature vérifiée par la CD, transmission de la version à déployer via artefact Jenkins (pas de Tag "latest")

- Ajout de la génération d'un SBOM au format CycloneDX généré par Trivy dans les artefacts du build.

Sécurité applicative

- Amélioration du score du rapport ZAP : Suppression des numéros de version NGINX dans la réponse http, élimination des doublons dans l'éntête HSTS (gérée désormais uniquement par NGINX, pas par Spring Boot), durcissement de la configuration CSP rhDemo.

## Version 1.1.2

- Configuration des caches Loki (11Go de mémoire par défaut ce qui compromettait l'exécution locale)

- Fichers values helm déplacés dans rhDemo/infra/stagingkub/helm/observability

- Suppression des définitions de niveau de logs dans applications-stagingkub.yaml pour prioriser la configuration helm dans values.yaml

- Duplication des caches Trivy pour éviter les coflits d'accès lors des scans en parallèle dans la chaine CI.

## Version 1.1.1

- Ajout documenté de Promtail/Loki dans le cluster pour centraliser les logs et de Grafana pour visialiser voir rhDemo/docs/OBSERVABILITY_STACK_INTEGRATION.md

- Ajout de possibilité de réglage niveaux de logs rhDemo via rhDemo/infra/stagingkub/helm/rhdemo/values.yaml

## Version 1.1.0

- Déploiement sur un deuxième environnement stagingkub basé cette fois sur Kubernetes (Kind) en conservant les données applicatives/keycloack d'un déploiement sur l'autre

- Découpage de la chaine CI/CD en
  - CI (build, tests unitaires et intégration, déploiement éphémère pour test selenium, scans qualité et sécurité, publication de l'image docker sur dépot docker local)
  - CD utilisation de l'image docker publiée pour déploiement sur l'environnement stagingkib

- Suppression du build du container applicatif par Paketo qui générait trop de dépendances externes au build (et le faisait planter quand elles sont busy) et utiliser un build docker classique basé sur l'image OpenJDK21 de Eclipse Temurin.
    Bizarement le build Paketo est également plus volumineux.
