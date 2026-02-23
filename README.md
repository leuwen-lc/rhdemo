# Projet école — preuve de concept

Ce dépôt contient un projet école servant de preuve de concept sur un ensemble de sujets techniques basés sur le développement d'une application web full‑stack (Spring Boot + Vue.js) et son déploiement automatisé (CI/CD) dans un environnement ephemere pour tests selenium/zap puis dans un cluster kubernetes KinD de staging.

## Objectifs

- Expérimenter des outils et méthodes standards et largement adoptés.
- Intégrer de nombreuses considérations de sécurité dès le début du projet (DevSecOps).
- Utiliser des agents IA (Copilot Chat et Claude Code dans VS Code) pour améliorer la productivité et la qualité du code.
- S'appuyer sur Spring Boot et son écosystème pour le back‑end.
- Fournir une IHM riche côté client avec Vue.js et le design system Element Plus.
- Mettre en place une structure solide et évolutive même si le projet reste simple (layers, API, client riche, OIDC, gestion des rôles).
- Inclure une chaine CI/CD évoluée avec test-automatisés, déploiement en containers,....
- Basé à 100% sur du logiciel libre, indépendance maximale avec les grandes plateformes gitlab/github et leurs solutions intégrées.
- Pour garder le coté preuve de concept facile à déployer, tout, y compris l'environnement ephemere, la chaine CI/CD et le cluster Kind doivent pouvoir tourner sur un unique PC récent 16Go sous linux (testé sur Ubuntu)

## Quelques orientations

- Favoriser l'utilisation des composants fournis (Element Plus) plutôt que de sur‑spécifier l'IHM.
- Rendre les tests IHM robustes (usage de marqueurs `data-testid`), tout en vérifiant l'accessibilité d'Element Plus dans le contexte de l'application.
- Mettre en place une solutions éprouvée pour l'authentification et la gestion des identités. La gestion des identités par l'applicatif n'est plus acceptable même sur des petits projets.
- Séparer les responsabilités : Backend For Frontend (BFF), c'est le backend qui obtiens les jetons auprès du fournisseur d'identité et les stocke pour sécuriser les flows d'authentification.
- Montrer le déploiement sur un cluster Kubernetes léger (KinD)
- Mettre en place de l'observabilité avec Loki/Grafana et quelques dashboard (consolidation des logs, métriques Spring Actuator, métriques PostgreSQL) sur l'environnement KinD


## Accent mis sur le DevSecOps

(C'est à dire mettre en place les sécurisations de responsabilité dev dès le début du projet)

- Authentification / Autorisation : délégué à KeyCloak, qui permet de gérer les identités (IAM) de manière centralisée, interapplicative (SSO), application de politiques de mots de passe, MFA (....)
- Contrôles d’accès : RBAC, les roles des utilisateurs sont portés par Keycloak et transmis à Spring Boot dans  l'idtoken OIDC.
- Utilisation de Spring Security : 
  - Inteface Keycloak OIDC custom pour récupérer les roles des utilisateurs dans l'idtoken, 
  - activation de l'anti-CSRF via cookie dédié sur le module principal lié à l'utilisation du pattern BFF. 
  - Filtrage des API au niveau méthode, au niveau url pour les fonctions annexes 
- Secrets applicatifs : choix d'utiliser le chiffrement des valeurs des clés contenant des secrets avec SOPS et de les commiter dans Git. L'utilisation d'un outil centralisé de type Hashicorp Vault demandera une expertise plus spécialisée mais reste possible sans modifier l'applicatif.
- Entêtes CSP réglées au plus strict possible sur l'applicatif : interdiction notamment du javascript inline, puissant moteur d'injections XSS.
- CI
  - Dépendances : Scan par OWASP Dependency‑Check, échec de la chaine si CVSS >=7.
  - Scans des images docker utilisées dans l'environnement CI ephemere avec Trivy
  - Génération d'un SBOM (inventaires des composants) au format CycloneDX dans les artefacts du pipeline;
  - Sonar avec quality gate. Profil plus léger que le standard sauf sur la sécurité (couverture de test >=50%, code Smell uniquement de niveau medium et haut, sécurité toute faille potentielle doit être revue).
  - Activation d'un proxy ZAP pour analyse dynamique intégrée durant le stage de tests en Selenium (analyse fournie dans un artefact du pipeline).
  - Publication du container applicatif dans un registry local en TLS (auto-signé pour l'instant)
  - Signature du container avec Cosign
- CD
  - Utilisation des secrets Kubernetes (chargement des secrets après décodage SOPS)
  - Déploiement basé sur la lecture du digest du container constuit lors du dernier build CI réussi (pas de tag dangereux "Latest)
  - Vérification de signature Cosign
- TLS : activer TLS sur les endpoints publics sur l'environnement ephemere et stagingkub (vérifier le fonctionnement en mode proxifié/sécurisé). Certificats autosignés ou Let's Encrypt (sur mon domaine intra.leuwen-lc.fr).
- Logging / monitoring fourni et déployé sur stagingkub avec Prometheus/Loki/Grafana : succès/échecs d'authentification, erreurs applicatives.
- Compte de service et Role RBAC pour limiter les droits de Jenkins sur Stagingkub.
- Tester des network policies restricitves pour préfigurer la prod et valider que l'applicatif est compatible sur l'environnement Kind grace à l'ajout de Cilium.

## Fonctionnalités

- Application basique CRUD (Create / Read / Update / Delete) sur une base simplifiée d'employés.
- ... Mais architecture prête pour évoluer vers une application métier plus complète (couches métier, persistance, API REST, client riche, gestion des rôles).
- Pagination gérée côté front‑end et back‑end pour démontrer la résolution d'un problème ultra fréquent en informatique de gestion lorsque le jeu de données grossit et les réponses aux requètes deviennent trop lourdes sans pagination.

## Architecture applicative

- Back‑end : Spring Boot, Spring Security
  - Architecture logicielle classique en 3 couches (évolutive en cas de besoin vers DTO ou clean architecture).
   Pattern Backend For Front-end (BFF) :
  - Le front‑end ne récupère pas directement le token auprès du serveur d'auth ; c'est le back‑end qui s'en charge.
  - Le back‑end renvoie un cookie de session (approche stateful) ; la protection CSRF est activée, un gestionnaire de session centralisé (type REDIS) pourra être ajouté pour assurer la scalabilité (TODO)
- Le Back-end fait à la fois BFF et traite directement les différents appels d'API. On pourrait imaginer une évolution avec une délagation du traitement des API à d'autres Back-end partagés au niveau SI. Pour accéder à ces back-end on pourrait se baser sur l'access token JWT signé de keycloak.
- Front‑end : Vue.js + Element Plus (design system) — privilégier les composants HTML/CSS standards pour accélérer le développement et améliorer la qualité de l'IHM.
- Tests d'interface : projet séparé pour les tests Selenium (scénarios de bout en bout). Selenium offre la possibilité d'écrire et bien structurer les tests en Java, ce qui ést cohérent avec le choix du langage backend. Option possible : remplacer par Cypress selon compétences disponibles sur l'automatisation des tests.
- Deux chaines CI/CD séparées :
  - une CI éxécutant le build, tests unitaires, tests d'intégration au sens Spring Boot, toutes les vérifications de qualité et sécurité, déploiement sur un environnement ephemere (Docker Compose) et tests Selenium, publication du l'image applicative sur le dépot Docker local.
  - une CD reprenant l'image applicative pour la déployer sur un cluster kubernetes léger KinD avec Helm

## Tests

- Tests unitaires et tests d'intégration au sens Spring Boot avec base en mémoire H2 pour le back‑end. Tests intégrés dans la chaine de build (Maven).
- Tests de bout en bout : Selenium (projet séparé) avec marqueurs CSS `data-testid` pour améliorer la robustesse. Tests dans un projet indépendant, activés dans la chaine CI.
- Outils Utilisés : Spring Boot, JUnit, Selenium Java (E2E).

## Installation

- Git
- Java 25+
- Pour édition/lancement mode dev :
  - VSCode avec Extension Pack pour Java, Maven Spring Boot Tools, Vue.
  - Possibilité d'utiliser également Spring Tool Suite (Eclipse)
- Pour env de développement : PostgresSQL 18 ou supérieur, Keycloak 26.5 ou supérieur
- Pour chaine CI/CD  Jenkins 2.541.1 avec un Docker Compose et un réseau dédié qui se connecte dynamiquement aux réseaux de ephemere et stagingkub. Uniquement un master pour l'instant (ressources limitées)
- Pour déploiement env de ephemere : Docker Compose avec un réseau dédié.
- Pour déploiement env staginkub : KinD 0.31 ou +

## Limites

- Le fait de déployer via CI/CD dans un premier environnement ephemere puis sur un mini-cluster kubernetes permet de démontrer la portabilité de l'application

- Par contre par nature ce projet n'est pas pret pour la production.
  - Il faut bien sur faire le travail spécifique de conception/réalisation d'un vrai cluster kubernetes redondant et sécurisé (ou conf sur cloud public).
  - Mais il reste aussi un travail de configuration sur certains composants applicatifs en cible production :
    - passage en mode production et durcissement de la configuration Keycloak activation de sécurités d'authentification des utilisateurs (vérification mail, renouvellement et longueur mdp, double authentification,...) qui serait fait probablement dans le cadre d'un projet IAM séparé. Il faudrait aussi réserver l'accès à l'interface d'admin via un réseau dédié.
    - durcissement de la configuration des logiciels de CI/CD, en particulier Jenkins avec ajout d'une instance dédiee production.
    - permettre la mise en place les mécanismes de scalabilité (Redis, etc...)
  -  Ce n'était pas le but mais fonctionnellement le projet même pour du simple n'est absolument pas viable :
  - manque énormément d'informations sur les employes,
  - l'adresse est dans un seul champ, elle devrait être dans une table à part et répondre aux normes internationales,
  - (etc ...)

## Utiliser le projet

- Prérequis : un PC sur Linux avec 16Go de RAM
- Docker et Docker compose installés dans des versions récentes (notamment syntaxe docker compose v2)
- Git dans une version récente avec lequel on va cloner le repository

<pre>git clone https://github.com/leuwen-lc/rhdemo.git</pre>

### En dev ou test local

- Allez dans rhDemo/infra/dev puis suivez les instructions du README.md pour installer Postgresql et Keycloak local via docker compose et initialiser la configuraiton et les données de base.
- Depuis le répertoire rhDemo, lancez la commande ./mvnw spring-boot:run
- Connectez vous (par défaut sur http;//localhost:9000/front)

### Utiliser la chaine CI et déployer dans l'environnement ephemere

- Allez dans rhDemo/infra/jenkins-docker et suivez le QUICKSTART.md et pour en savoir plus le README.md
- Lancez le pipeline rhDemo/Jenkinsfile-CI

### Utliser la chaine CD et déployer dans l'environnement stagingkub

- Installez et utilisez la chaine CI (ci-dessus)
- Installez Kind 0.30 et supérieur et des versions récentes kubectl et helm
- Suivez les documentations fournies dans rhDemo/infra/stagingkub/README.md
- Lancez le pipelne rhDemo/Jenkinsfile-CD

## Changelog

### Version 1.1.6

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


### Version 1.1.5

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


### Version 1.1.4

Environnement de Stagingkub
- Ajout d'un tableau de bord Grafana exposant les métriques Spring Actuator/Micrometer(métriques JVM, Http, Pool de connexion db, ...) exposées sur le end point prometheus (port dédié non exposé en externe).

- Ajout d'un tableau de bord Grafana exposant les métriques PostgreSQL (stats requètes, connexions, cache, ...)  via postgres-exporter pour Prometheus.

- Suppression de la commande kind dans le container Jenkins et passage par un compte de service avec des droits limités par RBAC.

- Ajout d'une network policy stricte pour le namespace rhDemo avec notammentinterdiction de toute sortie Egress.

- Ajout de Cilium a la place du CNI par défaut de Kind pour pouvoir appliquer la Network policiy, ajout d'un script de test des flux autorisés/interdits pour valider.

- Montée de niveau sur Kind 0.31 et Kubernetes 1.35.0

- Changement de nom de domaine des environnements web stagingkub : utilisation de intra.leuwen-lc.fr pour l'applicatif (rhdemo-stagingkub.intra.leuwen-lc.fr), keycloak et grafana. Comme je possède ce nom de domaiene Ceci permet me d'utiliser des certificats Let's Encrypt, les certificats auto-signés peuvent également être utilisés par simple modification de la config Helm.

- Ajout d'un handler spécifique pour le logout OIDC qui ne fonctionnait pas car en standard il utilise issuer-uri qui n'est pas configurable, le pod ne pouvant résoudre l'url externe. On dérive donc l'url de logout de l'authorization-uri

### Version 1.1.3

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

### Version 1.1.2

- Configuration des caches Loki (11Go de mémoire par défaut ce qui compromettait l'exécution locale)

- Fichers values helm déplacés dans rhDemo/infra/stagingkub/helm/observability

- Suppression des définitions de niveau de logs dans applications-stagingkub.yaml pour prioriser la configuration helm dans values.yaml

- Duplication des caches Trivy pour éviter les coflits d'accès lors des scans en parallèle dans la chaine CI.

### Version 1.1.1

- Ajout documenté de Promtail/Loki dans le cluster pour centraliser les logs et de Grafana pour visialiser voir rhDemo/docs/LOKI_STACK_INTEGRATION.md

- Ajout de possibilité de réglage niveaux de logs rhDemo via rhDemo/infra/stagingkub/helm/rhdemo/values.yaml

### Version 1.1.0

- Déploiement sur un deuxième environnement stagingkub basé cette fois sur Kubernetes (Kind) en conservant les données applicatives/keycloack d'un déploiement sur l'autre

- Découpage de la chaine CI/CD en
  - CI (build, tests unitaires et intégration, déploiement éphémère pour test selenium, scans qualité et sécurité, publication de l'image docker sur dépot docker local)
  - CD utilisation de l'image docker publiée pour déploiement sur l'environnement stagingkib

- Suppression du build du container applicatif par Paketo qui générait trop de dépendances externes au build (et le faisait planter quand elles sont busy) et utiliser un build docker classique basé sur l'image OpenJDK21 de Eclipse Temurin.
    Bizarement le build Paketo est également plus volumineux.
  
## Feuille de route

- Evaluer d'autres outils dans la chaine CI :
  - Snyk (sécurité des dépendances coté front-end)
  - Une alternative à Owasp Dependency-check qui a un fonctionnement contraignant (timeouts, clés API..)
- Faire une revue des pipeline CI et CD selon le top10 risques de sécurité owasp <https://owasp.org/www-project-top-10-ci-cd-security-risks/>
- Ajouter un mécanisme de mise à jour du schéma basé sur Liquibase
- Ajouter Redis pour gérer les sessions partagées
- Tester des outils de sécuritation Kubernetes : Kube-Bench, Falco, Kyverno, Popeye sur stagingkub.

## Contribuer

- Ouvrir une issue décrivant la modification souhaitée.
- Créer une branche par feature/bugfix : `feature/ma-feature` ou `fix/ma-correction`.
- Respecter la convention de commits du projet (ex. Conventional Commits).
- Ajouter/mettre à jour les tests si nécessaire.

## Licence

- Licence Apache 2.0
