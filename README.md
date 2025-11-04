Projet école, preuve de concept pour un certain nombre de sujets :
- Utilisaiton d'outils et de méthode les plus standards possibles
- Utilisation d'un agent IA (Copilot Chat dans VSCode) --> bien plus puissant sur la base de standards
- Utilisation de Spring Boot en tirant partie au maximum des outils
- IHM client riche basée sur Vue.js avec le design system element-plus.
  --> On gagne beaucoup à mon avis à s'adapter aux composants déjà fournis plutôt que de surspécifier l'IHM. Element-plus se déclare accessible, ça resterait à vérifier, quelques impasses rares pour positionner les identifiants servants à rendre robustes les tests IHM (voir ci-dessous).
- Uniquement un CRUD, la structure pour faire une application métier plus complexe est présente (Structuration en couches coté Backend, API, Client riche, Gestion de roles....)
  --> Pour autant cas de gestion de la pagination sur un tableau, gestion front end et backend : un des problèmes les plus récurrents dans les application de gestion quand on fait grossir le jeu d'essai et qu'on s'apperçoit que le temps d'affichage devient non uspportable
- Tests Selenium sur un scénario de récupération complet, mis dans un projet à part pour simplifier les build.
  --> Utilisation des marqueurs css data-testid pour plus de robustesse
  --> remplaçable par Cypress, mais venant du Java j'apprécie les possibilités de rendre le code plus lisible et robuste (avis perso bien sur!) y compris pour les tests
- Utilisation d'une solution Backend For Frontend :
  --> Le frontend ne discute pas avec le serveur d'authentification pour obtenir un token, c'est le backend (Spring security) qui le fait pour lui
  --> Contre-partie, le backend envoie un cookie de session (pas stateless) et on doit activer l'anti CSRF (Spring security)
- Objectifs devSECops, intégrer à minima dès le début du projet (liste à affiner) : 
    Authentification / Autorisation : un outil dédié : Keycloak.
    --> A l'heure des politiques de mot de passe, de gestion des identités, voire de la double authentification il faut laisser tomber les password stockés en base, même pour un applicatif limité. 
    Secrets : ne pas committer, utiliser un store (Vault, AWS Secrets Manager, Kubernetes Secrets).
    Dépendances : SCA (OWASP Dependency‑Check, Snyk, Dependabot).
    CI : SAST minimal (EsLint/TSLint + bandit/SpotBugs selon stack) et tests unitaires.
    TLS pour endpoints public/externes (certificat dans staging/prod).
    Logging/monitoring basique (auth success/failures, errors).
    Politique de mots de passe et MFA si le contexte l’impose.
    Contrôles d’accès minimale : RBAC ou scopes simples.
