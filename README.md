# Projet école — preuve de concept

Ce dépôt contient un projet école servant de preuve de concept visant sur un ensemble de sujets techniques basés sur le développement d'une application web full‑stack (Spring Boot + Vue.js) et son déploiement automatisé (CI/CD) dans un environnement de staging.

## Objectifs
- Expérimenter des outils et méthodes standards et largement adoptés.
- Utiliser des agents IA (Copilot Chat et Claude Code dans VS Code) pour améliorer la productivité et la qualité du code.
- S'appuyer sur Spring Boot et son écosystème pour le back‑end.
- Fournir une IHM riche côté client avec Vue.js et le design system Element Plus.
- Mettre en place une structure solide et évolutive même si le projet reste simple (layers, API, client riche, OIDC, gestion des rôles)
- Inclure une chaine CI/CD évoluée avec test-automatisés, déploiement en containers,....
- Intégrer de nombreuses considérations de sécurité dès le début du projet (DevSecOps).
- Basé à 100% sur du logiciel libre, indépendance avec les grandes plateformes gitlab/github et leurs solutions intégrées.
- Pour garder le coté preuve de concept facile à déployer, tout, y compris le staging et la chaine CI/CD doit pouvoir tourner sur un unique PC récent 16Go sous linux (testé sur Ubuntu)

## Quelques orientations
- Favoriser l'utilisation des composants fournis (Element Plus) plutôt que de sur‑spécifier l'IHM.
- Rendre les tests IHM robustes (usage de marqueurs `data-testid`), tout en vérifiant l'accessibilité d'Element Plus dans le contexte de l'application.
- Mettre en place une solutions éprouvées pour l'authentification et la gestion des identités. La gestion des identités par l'applicatif n'est plus acceptable même sur des petits projets.
- Séparer les responsabilités : Backend For Frontend (BFF), c'est le backend qui obtiens les jetons auprès du fournisseur d'identité et les stocke pour sécuriser les flows d'authentification.

## Fonctionnalités
- Application basique CRUD (Create / Read / Update / Delete)....
- ... Mais architecture prête pour évoluer vers une application métier plus complète (couches métier, persistance, API REST, client riche, gestion des rôles).
- Pagination gérée côté front‑end et back‑end pour démontrer la résolution d'un problème ultra fréquent en informatique de gestion lorsque le jeu de données grossit.

## Architecture
- Back‑end : Spring Boot, Spring Security 
   Pattern Backend For Front-end (BFF) :
  - Le front‑end ne récupère pas directement le token auprès du serveur d'auth ; c'est le back‑end qui s'en charge.
  - Architecture logicielle classique en 3 couches (évolutive en cas de besoin vers DTO ou Architecture hexagonale)
  - Le back‑end renvoie un cookie de session (approche stateful) ; la protection CSRF sera activée, un gestionnaire de session centralisé (type REDIS) pourra être ajouté pour assurer la scalabilité (TODO)
- Front‑end : Vue.js + Element Plus (design system) — privilégier les composants HTML/CSS standards pour accélérer le développement.
- Tests d'interface : projet séparé pour les tests Selenium (scénarios de bout en bout). Selenium offre la possibilité d'écrire et bien structurer les tests en Java, ce qui ést cohérent avec le choix du langage backend. Option possible : remplacer par Cypress selon compétences disponibles sur l'automatisation des tests.

## Tests
- Tests d'intégration (avec base H2) pour le back‑end intégré dans la chaine de build (Maven).
- Tests de bout en bout : Selenium (projet séparé) avec marqueurs CSS `data-testid` pour améliorer la robustesse.
- Outils Utilisés : Spring Boot, JUnit, Selenium Java (E2E).

## DevSecOps — checklist
- Authentification / Autorisation : délégué à KeyCloak, qui permet de gérer les identités (IAM) de manière centralisée, interapplicative (SSO)
- Utilisation de Spring Security : Inteface Keycloak OIDC (custom pour récupérer les roles des utilisateurs dans l'idtoken), activation de l'anti-CSRF (via cookie spécialisé) sur le module principal lié à l'utilisation du pattern BFF. Filtrage des API au niveau méthode, au niveau url pour les fonctions annexes (Spring actuator, documentation Open API/swagger, etc...)
- Secrets applicatifs : choix d'utiliser le chiffrement des valeurs des clés contenant des secrets avec SOPS et de les commiter dans Git. L'utilisaiton d'un outil centralisé de type Hashicorp Vault demande une expertise plus spécialisée mais reste possible sans modifier l'applicatif (TODO).
- Dépendances : Scan par OWASP Dependency‑Check, échec de la chaine si CVSS >=7.
- Scans des images docker utilisées dans le stagign avec Trivy et/ou vérifications qu'il s'agit d'images officielles (TODO)
- CI : Sonar avec quality gate mais profil plus léger que le standard sauf sur la sécurité (couverture de test >=50%, Code Smell uniquement de niveau medium et haut).
- Activation d'un proxy ZAP pour pentest intégré au CI/CD durant les tests Selenium (TODO).
- TLS : activer TLS sur les endpoints publics sur le staging (certificats auto-signés sur cet env).
- Logging / monitoring basique : succès/échecs d'authentification, erreurs applicatives, métriques de disponibilité (TODO).
- Politique de mots de passe et MFA (TODO en mettant en oeuvre les fonctionnalités plus avancées de Keycloak).
- Contrôles d’accès : RBAC, les roles des utilisateurs sont portés par Keycloak et transmis à Spring Boot dans  l'idtoken OIDC.

## Installation 
- Git
- Java 21+ (ou version définie par le projet)
- Pour édition/lancement mode dev : VSCode avec Extension Pack pour Java, Maven Spring Boot Tools, Vue. Possibilité d'utiliser également Spring Tool Suite (Eclipse)
- Pour env de développement : PostgresSQL 16 ou supérieur, Keycloak 26.4 ou supérieur
- Pour chaine CI/CD  Jenkins 2.528.1 avec un Docker Compose et un réseau dédié qui se connecte dynamiquement au réseau de staging.
- Pour déploiement env de staging : Docker Compose avec un réseau dédié dans un premier temps. Evolution possible sur un Kubernetes light  

## Utiliser le projet
- En dev ou test local : 
   - Allez dans rhDemo/infra/dev et installez a minima un Postgresql et un Keycloak local
   - Initialisez Keycloak en lançant le projet rhDemoInitKeycloak depuis l'ide ou via mvnw clean spring-boot:run
   - Initialisez la base de données DBRHDemo, par exemple en vous connectant via le client psql. 
      sudo -u postgres psql
      CREATE ROLE dbrhdemo WITH LOGIN ENCRYPTED PASSWORD 'My_password';
      CREATE DATABASE dbrhdemo OWNER dbrhdemo ENCODING 'UTF8' TEMPLATE template0;
   - Se connecter sur la base de données créer
      psql -U dbrhdemo -d dbrhdemo -W
      utiliser le contenu du fichier rhDemo\pgddl pour créer le schéma et alimenter la base.
   - Créer un fichier rhDemo/secrets-rhdemo.yml à partir du template fourni.
   - Mettre à jour le cas échéant les autres paramètres dans le fichier rhDemo/src/main/ressources/application.yml
   - Lancer le projet mvnw clean spring-boot:run
   - Connectez vous (par défaut sur http;//localhost:9000)

- Utiliser la chaine CI/CD et déployer l'environnement de staging :
   - Allez dans rhDemo/infra/jenkisn-docker et suivez la doc d'install Jenkins avec le docker-compose et les procédures d'initialisation (plugin et conf) fournis
   - Installez SOPS et une clé age 
   - Fabriquez un fichier de secrets de l'environnement de staging à partir du template secrets-staging.yml.template puis chiffrez le avec SOPS sous secrets-staging.yml (celui stocké sur git nécessiterait ma clé privée pour être déchiffré)
   - Référencez au niveau des credentials Jenkins : 
      - sous l'id "sops-age-key" votre fichier contenant la paire de clés age nécessaire au déchiffrage de secrets-staging.yml
      - sous l'id "jenkins-sonar-token" la clé d'échange avec sonarQube (à générer sur sonarQube)
      - (facultatif) sous l'id "mail.credentials" un compte sur un serveur de mails permettant l'envoi SMTP
   - Lancez le pipeline rhDemo/Jenkinsfile

- Lancer directement l'environnement de staging en chargeant le conteneur applicatif depuis docker-hub (TODO)


## Contribuer
- Ouvrir une issue décrivant la modification souhaitée.
- Créer une branche par feature/bugfix : `feature/ma-feature` ou `fix/ma-correction`.
- Respecter la convention de commits du projet (ex. Conventional Commits).
- Ajouter/mettre à jour les tests si nécessaire.

## Licence
- Licence Apache 2.0
