# Projet école — preuve de concept

Ce dépôt contient un projet école servant de preuve de concept sur un ensemble de sujets techniques basés sur le développement d'une application web full‑stack (Spring Boot + Vue.js) et son déploiement automatisé (CI/CD) dans un environnement ephemere pour tests selenium/zap puis dans un cluster kubernetes KinD de staging.

## Objectifs

- Expérimenter des outils et méthodes standards et largement adoptés.
- Intégrer de nombreuses considérations de sécurité dès le début du projet (DevSecOps).
- Utiliser des agents IA (GitHub Copilot / Claude Code dans VS Code) pour améliorer la productivité et la qualité du code.
- S'appuyer sur Spring Boot et son écosystème pour le back‑end.
- Fournir une IHM riche côté client avec Vue.js et le design system Element Plus.
- Mettre en place une structure solide et évolutive même si le projet reste simple (couches, API, client riche, OIDC, gestion des rôles).
- Inclure une chaine CI/CD évoluée avec nombreux controles qualité/sécurité, test-automatisés, déploiement en containers,....
- Basé à 100% sur du logiciel libre, dépendance minimale avec GitHub, uniquement hébergement de code et PR, pas de GitHub Actions.
- Pour garder le coté preuve de concept facile à déployer, tout, y compris l'environnement ephemere, la chaine CI/CD et le cluster kubernetes KinD doivent pouvoir tourner sur un unique PC récent 16Go sous linux (testé sur Ubuntu)

## Quelques orientations

- Favoriser l'utilisation des composants fournis (Element Plus) plutôt que de sur‑spécifier l'IHM.
- Rendre les tests IHM robustes (usage de marqueurs `data-testid`), tout en vérifiant l'accessibilité d'Element Plus dans le contexte de l'application.
- Mettre en place une solution éprouvée pour l'authentification et la gestion des identités. La gestion des identités par l'applicatif n'est plus acceptable même sur des petits projets.
- Séparer les responsabilités : Backend For Frontend (BFF), c'est le backend qui obtient les jetons auprès du fournisseur d'identité et les stocke pour sécuriser les flows d'authentification.
- Montrer le déploiement sur un cluster Kubernetes léger (KinD)
- Mettre en place de l'observabilité avec Loki/Prometheus/Grafana et quelques dashboard (consolidation des logs, métriques Spring Actuator, métriques PostgreSQL) sur l'environnement KinD

## Accent mis sur le DevSecOps

(C'est à dire mettre en place les sécurisations de responsabilité dev dès le début du projet)

- Authentification / Autorisation : délégué à KeyCloak, qui permet de gérer les identités (IAM) de manière centralisée, interapplicative (SSO), application de politiques de mots de passe, MFA (....)
- Contrôles d’accès : RBAC, les roles des utilisateurs sont portés par Keycloak et transmis à Spring Boot dans  l'idtoken OIDC.
- Utilisation de Spring Security :
  - Interface Keycloak OIDC custom pour récupérer les roles des utilisateurs dans l'idtoken,
  - activation de l'anti-CSRF via cookie dédié sur le module principal lié à l'utilisation du pattern BFF.
  - Filtrage des API au niveau méthode, au niveau url pour les fonctions annexes
- Secrets applicatifs : choix d'utiliser le chiffrement des valeurs des clés contenant des secrets avec SOPS et de les commiter dans Git. L'utilisation d'un outil centralisé de type Hashicorp Vault demandera une expertise plus spécialisée mais reste possible sans modifier l'applicatif.
- Entêtes CSP réglées au plus strict possible sur l'applicatif : interdiction notamment du javascript inline, puissant moteur d'injections XSS.
- CI
  - Dépendances : Scan par OWASP Dependency‑Check, échec de la chaine si CVSS >=7.
  - Scans des images docker utilisées dans l'environnement CI ephemere avec Trivy
  - Génération d'un SBOM (inventaires des composants) au format CycloneDX dans les artefacts du pipeline;
  - SonarQube avec quality gate plus léger que le standard :
    - couverture de test >=50%,
    - code Smell uniquement de niveau medium ou supérieur,
    - sécurité toute faille potentielle doit être revue.
  - Activation d'un proxy ZAP pour analyse dynamique intégrée durant le stage de tests en Selenium. Vérification que le rapport ne contient aucune alerte sur l'IHM rhDemo (qq alertes résiduelles sur l'IHM Keycloak standard)
  - Publication du container applicatif dans un registry local en TLS
  - Signature du container avec Cosign
- CD
  - Utilisation des secrets Kubernetes (chargement des secrets après décodage SOPS)
  - Déploiement basé sur la lecture du digest du container construit lors du dernier build CI réussi (pas de tag dangereux "Latest")
  - Vérification de signature Cosign
- TLS : activer TLS sur les endpoints publics sur l'environnement ephemere et stagingkub (vérifier le fonctionnement en mode proxifié/sécurisé).
  --> Certificats autosignés ou Let's Encrypt sur stagingkub (généré via DNS01 uniquement si administrateur DNS du domaine leuwen-lc.fr).
- Semi-automatisation de la gestion de versions : utilisation de renovate qui scanne et pousse des PR pour des mises à jour. Délai de 7 jours après publication (Cooldown) : permet de révéler éventuellement une version compromise.
- Logging / monitoring de base fourni et déployé sur stagingkub avec Prometheus/Loki/Grafana :
  - logs : app/keycloak/pg,
  - métriques : système/pg/spring
- Comptes de service et 2 Roles RBAC (un applicatif, un infra) pour limiter les droits de Jenkins sur stagingkub.
- Network policies restricitves pour préfigurer la prod et valider que l'applicatif est compatible sur l'environnement KinD.
  --> ajout du CNI Cilium sur l'environnement KinD pour appliquer ces policies.

## Fonctionnalités

- Application basique CRUD (Create / Read / Update / Delete) sur une base simplifiée d'employés.
- Mais architecture prête pour évoluer vers une application métier plus complète (couches métier, DTO, persistance, API REST, client riche, gestion des rôles).
- Pagination gérée côté front‑end et back‑end pour démontrer la résolution d'un problème ultra fréquent en informatique de gestion lorsque le jeu de données grossit et les réponses aux requètes deviennent trop lourdes sans pagination.

## Architecture applicative

- Back‑end : Spring Boot, Spring Security
  - Architecture logicielle classique en 3 couches avec DTO(facilement évolutive vers clean architecture),
  - pattern Backend For Front-end (BFF) :
    - Le front‑end ne récupère pas directement le token auprès du serveur d'auth ; c'est le back‑end qui s'en charge.
    - Le back‑end renvoie un cookie de session (approche stateful) ; la protection CSRF est activée, un gestionnaire de session centralisé (type REDIS) pourra être ajouté pour assurer la scalabilité (TODO)
  - Le Back-end fait à la fois BFF et traite directement les différents appels d'API. Evolution possible avec une délégation du traitement des API à d'autres Back-end partagés au niveau SI en se basant sur l'access token JWT signé de keycloak ou autre dispositif.
- Front‑end : Vue.js approche composants + Element Plus (design system) — privilégier les composants HTML/CSS standards pour accélérer le développement et améliorer la qualité de l'IHM.
- Tests d'interface : projet séparé pour les tests Selenium (scénarios de bout en bout). Selenium offre la possibilité d'écrire et bien structurer les tests en Java, ce qui ést cohérent avec le choix du langage backend.
- Deux chaines CI/CD séparées :
  - une CI éxécutant le build, tests unitaires, tests d'intégration au sens Spring Boot, toutes les vérifications de qualité et sécurité, déploiement sur un environnement ephemere (Docker Compose) et tests Selenium, publication du l'image applicative sur le dépot Docker local.
  - une CD reprenant l'image applicative pour la déployer sur un cluster kubernetes léger KinD avec Helm
- Chaine Jenkins Renovate Automerge pour mise à jour des versions, et Stagingkub Update Deploy pour application de maj sur l'infra staging
- Chaine Fixcve-auto de remédiation automatique et déterministe (scripts testés, sans IA) des pipelines CI échoués sur les phases Owasp-DC ou Trivy : montée de version corrigée ou suppression temporaire documentée (job Jenkins lancé à la fin de chaque build CI).

## Tests

- Tests unitaires et tests d'intégration au sens Spring Boot avec base en mémoire H2 pour le back‑end. Tests intégrés dans la chaine de build (Maven).
- Tests de bout en bout : Selenium (projet séparé) avec marqueurs CSS `data-testid` pour améliorer la robustesse. Tests dans un projet indépendant, activés dans la chaine CI.
- Outils Utilisés : Spring Boot, JUnit, Selenium Java (E2E).

## Installation

- Git
- Java 25+
- Pour édition/modifications/mode debug :
  - VSCode avec Extension Pack pour Java, Maven Spring Boot Tools, Vue.
  - Possibilité d'utiliser également Spring Tool Suite (Eclipse)
- Pour exécution en env de développement : PostgresSQL 18 ou supérieur, Keycloak 26.5 ou supérieur
- Pour chaine CI/CD  Jenkins 2.555.1 avec un Docker Compose et un réseau dédié qui se connecte dynamiquement aux réseaux de ephemere et stagingkub. Uniquement un master pour l'instant (ressources limitées)
- Pour déploiement env de ephemere (CI) : Docker Compose avec un réseau dédié.
- Pour déploiement env staginkub (CD) : KinD 0.33+, Helm 4.2+, Kubectl v1.31+

## Limites

- Le fait de déployer via CI/CD dans un premier environnement ephemere puis sur un mini-cluster kubernetes permet de démontrer la portabilité de l'application

- Ce qu'il faudrait faire pour atteindre un niveau production .
  - conception/réalisation d'un vrai cluster kubernetes redondant et sécurisé (ou conf sur cloud public).
  - configuration sur certains composants applicatifs en cible production :
    - passage en mode production et durcissement de la configuration Keycloak qui serait fait probablement dans le cadre d'un projet IAM transverse :
            - interface avec un logiciel RH pour gérer les arrivées/départ
            - activation de sécurités d'authentification des utilisateurs (vérification mail, renouvellement et longueur mdp, double authentification,...) .
    - durcissement de la configuration des logiciels de CI/CD, gestion fine des utilisateurs/droits, ajout d'une instance dédiee production.
    - mise en place les mécanismes de scalabilité (Redis, etc...)
  - fonctionnellement le projet n'est pas du tout viable en l'état (ce n'était pas le but) :
    - manque énormément d'informations/transactions de gestion sur les employes,
    - l'adresse est dans un seul champ, el devrait être dans une table à part et répondre aux normes internationales,
  - ...

## Utiliser le projet

Prérequis : un PC sous Linux avec 16 Go de RAM, Docker et Docker Compose v2 récents, Git.

<pre>git clone https://github.com/leuwen-lc/rhdemo.git</pre>

- **Développement ou test local** : [rhDemo/infra/dev/README.md](rhDemo/infra/dev/README.md), puis `./mvnw spring-boot:run` depuis `rhDemo/` (http://localhost:9000/front).
- **Chaîne complète** (Jenkins, OpenBao, CI et environnement ephemere, stagingkub et CD, observabilité, Renovate) : suivre l'ordre d'installation de [rhDemo/docs/INSTALLATION_COMPLETE.md](rhDemo/docs/INSTALLATION_COMPLETE.md), qui renvoie à la documentation de chaque composant.

## Changelog

L'historique des versions est tenu dans [CHANGELOG.md](CHANGELOG.md).

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
