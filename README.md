# Projet école — preuve de concept

Ce dépôt contient un projet école servant de preuve de concept visant sur un ensemble de sujets techniques basés sur le développement d'une application web full‑stack (Spring Boot + Vue.js) et son déploiement automatisé (CI/CD) dans un environnement de ephemere.

## Objectifs
- Expérimenter des outils et méthodes standards et largement adoptés.
- Intégrer de nombreuses considérations de sécurité dès le début du projet (DevSecOps).
- Utiliser des agents IA (Copilot Chat et Claude Code dans VS Code) pour améliorer la productivité et la qualité du code.
- S'appuyer sur Spring Boot et son écosystème pour le back‑end.
- Fournir une IHM riche côté client avec Vue.js et le design system Element Plus.
- Mettre en place une structure solide et évolutive même si le projet reste simple (layers, API, client riche, OIDC, gestion des rôles)
- Inclure une chaine CI/CD évoluée avec test-automatisés, déploiement en containers,....
- Basé à 100% sur du logiciel libre, indépendance avec les grandes plateformes gitlab/github et leurs solutions intégrées.
- Pour garder le coté preuve de concept facile à déployer, tout, y compris l'environnement ephemere et la chaine CI/CD doit pouvoir tourner sur un unique PC récent 16Go sous linux (testé sur Ubuntu)

## Quelques orientations
- Favoriser l'utilisation des composants fournis (Element Plus) plutôt que de sur‑spécifier l'IHM.
- Rendre les tests IHM robustes (usage de marqueurs `data-testid`), tout en vérifiant l'accessibilité d'Element Plus dans le contexte de l'application.
- Mettre en place une solutions éprouvées pour l'authentification et la gestion des identités. La gestion des identités par l'applicatif n'est plus acceptable même sur des petits projets.
- Séparer les responsabilités : Backend For Frontend (BFF), c'est le backend qui obtiens les jetons auprès du fournisseur d'identité et les stocke pour sécuriser les flows d'authentification.
- Montrer le déploiement sur un cluster Kubernetes léger (KinD)

## Fonctionnalités
- Application basique CRUD (Create / Read / Update / Delete) sur une base simplifiée d'employés.
- ... Mais architecture prête pour évoluer vers une application métier plus complète (couches métier, persistance, API REST, client riche, gestion des rôles).
- Pagination gérée côté front‑end et back‑end pour démontrer la résolution d'un problème ultra fréquent en informatique de gestion lorsque le jeu de données grossit.

## Architecture
- Back‑end : Spring Boot, Spring Security
  - Architecture logicielle classique en 3 couches (évolutive en cas de besoin vers DTO ou Architecture hexagonale).
   Pattern Backend For Front-end (BFF) :
  - Le front‑end ne récupère pas directement le token auprès du serveur d'auth ; c'est le back‑end qui s'en charge.
  - Le back‑end renvoie un cookie de session (approche stateful) ; la protection CSRF sera activée, un gestionnaire de session centralisé (type REDIS) pourra être ajouté pour assurer la scalabilité (TODO)
- Front‑end : Vue.js + Element Plus (design system) — privilégier les composants HTML/CSS standards pour accélérer le développement et améliorer la qualité de l'IHM.
- Tests d'interface : projet séparé pour les tests Selenium (scénarios de bout en bout). Selenium offre la possibilité d'écrire et bien structurer les tests en Java, ce qui ést cohérent avec le choix du langage backend. Option possible : remplacer par Cypress selon compétences disponibles sur l'automatisation des tests.

## Tests
- Tests d'intégration (avec base H2) pour le back‑end intégré dans la chaine de build (Maven).
- Tests de bout en bout : Selenium (projet séparé) avec marqueurs CSS `data-testid` pour améliorer la robustesse.
- Outils Utilisés : Spring Boot, JUnit, Selenium Java (E2E).

## Accent mis sur le DevSecOps 
- Authentification / Autorisation : délégué à KeyCloak, qui permet de gérer les identités (IAM) de manière centralisée, interapplicative (SSO), application de politiques de mots de passe, MFA (....)
- Utilisation de Spring Security : Inteface Keycloak OIDC (custom pour récupérer les roles des utilisateurs dans l'idtoken), activation de l'anti-CSRF (via cookie spécialisé) sur le module principal lié à l'utilisation du pattern BFF. Filtrage des API au niveau méthode, au niveau url pour les fonctions annexes (Spring actuator, documentation Open API/swagger, etc...)
- Secrets applicatifs : choix d'utiliser le chiffrement des valeurs des clés contenant des secrets avec SOPS et de les commiter dans Git. L'utilisaiton d'un outil centralisé de type Hashicorp Vault demande une expertise plus spécialisée mais reste possible sans modifier l'applicatif (TODO).
- Entêtes CSP mis au plus strict possible sur l'applicatif : interdiction notamment du javascript inline, puissant moteur d'injections XSS.
- Dépendances : Scan par OWASP Dependency‑Check, échec de la chaine si CVSS >=7.
- Scans des images docker utilisées dans l'environnement CI ephemere avec Trivy 
- CI : Sonar avec quality gate mais profil plus léger que le standard sauf sur la sécurité (couverture de test >=50%, Code Smell uniquement de niveau medium et haut, sécurité toute faille potentielle doit être revue).
- Activation d'un proxy ZAP pour analyse dynamique intégrée au CI/CD durant le stage de tests en Selenium.
- TLS : activer TLS sur les endpoints publics sur le staging (certificats auto-signés sur cet env).
- TLS : activer TLS sur les endpoints publics sur l'environnement ephemere et stagingkub (certificats auto-signés pour l'instant).
- Logging / monitoring basique : succès/échecs d'authentification, erreurs applicatives, métriques de disponibilité (TODO).
- Contrôles d’accès : RBAC, les roles des utilisateurs sont portés par Keycloak et transmis à Spring Boot dans  l'idtoken OIDC.

## Installation 
- Git
- Java 21+ 
- Pour édition/lancement mode dev : VSCode avec Extension Pack pour Java, Maven Spring Boot Tools, Vue. Possibilité d'utiliser également Spring Tool Suite (Eclipse)
- Pour env de développement : PostgresSQL 16 ou supérieur, Keycloak 26.4 ou supérieur
- Pour chaine CI/CD  Jenkins 2.528.1 avec un Docker Compose et un réseau dédié qui se connecte dynamiquement au réseau de staging.
- Pour déploiement env de staging : Docker Compose avec un réseau dédié dans un premier temps. 
- Pour chaine CI/CD  Jenkins 2.528.1 avec un Docker Compose et un réseau dédié qui se connecte dynamiquement au réseau de ephemere.
- Pour déploiement env de ephemere : Docker Compose avec un réseau dédié dans un premier temps.
- Pour déploiement env staginkub : KinD 0.30 ou + 

## Limites 
- Le fait de déployer via CI/CD dans un premier environnement ephemere puis sur un mini-cluster kubernetes permet de démontrer la portabilité de l'application
- Par contre par nature ce projet n'est pas pret pour la production. il resterait un travail important de configuration de tous les composants en cible production : 
   - élimination des modules périphériques de l'application (comme le module de documentation et test openapi voir http://localhost:9000 sur l'application)
   - passage en mode production et durcissement de la configuration Keycloak activation de sécurités d'authentification des utilisateurs (vérification mail, renouvellement et longueur mdp, double authentification,...)
   - réduire la verbosité de l'applicatif par configuration (niveau de log info par défaut)
   - mettre en place un système de collecte de métriques et logs complet avec tableau de bord et seuils d'alertes
   - durcissement de la configuration des logiciels de CI/CD, en particulier Jenkins et utilisation d'un deuxième Jenkins dédié production.
   - mettre en place les mécanismes de scalabilité (Redis, etc...)

## Utiliser le projet
- Prérequis : un PC sur Linux avec 16Go de RAM
- Docker et Docker compose installés dans des versions récentes (notamment syntaxe docker compose v2)
- Git dans une version récente avec lequel on va cloner le repository 
<pre>git clone https://github.com/leuwen-lc/rhdemo.git</pre>

### En dev ou test local : 
   - Allez dans rhDemo/infra/dev puis suivez les instructions du README.md pour installer Postgresql et Keycloak local via docker compose et initialiser la configuraiton et les données de base. 
   - Connectez vous (par défaut sur http;//localhost:9000/front)

### Utiliser la chaine CI et déployer dans l'environnement ephemere :
   - Allez dans rhDemo/infra/jenkins-docker et suivez le QUICKSTART.md et pour en savoir plus le README.md 
   - Lancez le pipeline rhDemo/Jenkinsfile-CI

## Utliser la chaine CD et déployer dans l'environnement stagingkub
    - Installez Jenkins et déroulez la chaine Jenkins-CI (étape ci-dessus)
    - Installez Kind 0.30 et supérieur et des versions récentes kubectl et helm
    - suivez les documentations fournies dans rhDemo/infra/stagingkub
    - lancez le pipelne rhDemo/Jenkinsfile-CD

## Changelog 
  Version 1.1
  - Déployer sur un deuxième environnement stagingkub basé cette fois sur Kubernetes (kind) en gardant les données applicatives/keycloack d'un déploiement sur l'autre
  - Découper la chaine CI/CD actuelle en
      - CI (build, tests unitaires et intégration, déploiement éphémère pour test selenium, scans qualité et sécurité, publication de l'image docker sur dépot docker local)
      - CD utilisation de l'image docker publiée pour déploiement sur l'environnement stagingkib 
  - Supprimer le build du container applicatif par Paketo qui génére trop de dépendances externes au build (et le fait planter quand elles sont busy) et utiliser un build docker classique basé sur l'image OpenJDK21 de Ecilse Temurin.
    Bizarement le build Paketo est également plus volumineux.

## Feuille de route
  Version 1.2
  - Transformer le champ adresse en champs d'adresse normalisés. Je n'avais pas prévu du tout de fonctionnel au départ mais l'adresse sur un seul chammp fait trop mal aux yeux.
  - Ajouter un filtre sur le tableau des employes (en principe standard avec Element Plus/Spring Boot)
 
  Versions ultérieures 
  - Faire une revue des pipeline CI et CD selon le top10 risques de sécurité owasp https://owasp.org/www-project-top-10-ci-cd-security-risks/
  - Ajouter une collecte centralisée de logs et de métriques sur l'environnement stagingkub
  - Ajouter un mécanisme de mise à jour du schéma basé sur Liquibase
  - Ajouter Redis pour gérer les sessions partagées
  - Ajouter l'opérateur cloudnativePG sur stagingkub
  - Ajouter une Network Politcy de niveau prod.
    

## Contribuer
- Ouvrir une issue décrivant la modification souhaitée.
- Créer une branche par feature/bugfix : `feature/ma-feature` ou `fix/ma-correction`.
- Respecter la convention de commits du projet (ex. Conventional Commits).
- Ajouter/mettre à jour les tests si nécessaire.

## Licence
- Licence Apache 2.0
