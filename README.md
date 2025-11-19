# Projet école — preuve de concept

Ce dépôt est une preuve de concept visant à explorer un ensemble de sujets techniques et de bonnes pratiques pour une application web full‑stack (Spring Boot + Vue.js).

## Objectifs
- Expérimenter des outils et méthodes standards et largement adoptés.
- Utiliser un agent IA (Copilot Chat dans VS Code) pour améliorer la productivité et la qualité du code.
- S'appuyer sur Spring Boot et son écosystème pour le back‑end.
- Fournir une IHM riche côté client avec Vue.js et le design system Element Plus.
- Mettre en place une structure solide et évolutive même si le projet reste simple (layers, API, client riche, OIDC, gestion des rôles, CI/CD, test-automatisés, déploiement en containers,...).
- Intégrer des considérations DevSecOps dès le début du projet.

## Principes généraux
- Favoriser l'utilisation des composants fournis (Element Plus) plutôt que de sur‑spécifier l'IHM.
- Rendre les tests IHM robustes (usage de marqueurs `data-testid`), tout en vérifiant l'accessibilité d'Element Plus dans le contexte de l'application.
- Mettre en place une solutions éprouvées pour l'authentification et la gestion des identités. La gestion des identités par l'applicatif n'est plus acceptable même sur des petits projets.
- Séparer les responsabilités : Backend For Frontend (BFF), c'est le backend qui obtiens les jetons auprès du fournisseur d'identité et les stocke pour sécuriser les flows d'authentification.

## Fonctionnalités
- Application basique CRUD (Create / Read / Update / Delete)....
- ... Mais architecture prête pour évoluer vers une application métier plus complète (couches métier, persistance, API REST, client riche, gestion des rôles).
- Pagination gérée côté front‑end et back‑end pour démontrer la résolution d'un problème ultra fréquent en informatique de gestion lorsque le jeu de données grossit.

## Architecture
- Back‑end : Spring Boot, Spring Security (BFF pour déléguer l'authentification).
  - Le front‑end ne récupère pas directement le token auprès du serveur d'auth ; c'est le back‑end qui s'en charge.
  - Le back‑end renvoie un cookie de session (approche stateful) ; la protection CSRF sera activée, un gestionnaire de session centralisé (type REDIS) pourra être ajouté (TODO).
- Front‑end : Vue.js + Element Plus (design system) — privilégier les composants standards pour accélérer le développement.
- Tests d'interface : projet séparé pour les tests Selenium (scénarios de bout en bout). Selenium offre la possibilité d'écrire et bien structurer les tests en Java, ce qui ést cohérent avec le choix du langage backend. Option possible : remplacer par Cypress selon compétences disponibles sur l'automatisation des tests.

## Tests
- Tests d'intégration (avec base H2) pour le back‑end intégré dans la chaine de build (Maven).
- Tests de bout en bout : Selenium (projet séparé) avec marqueurs CSS `data-testid` pour améliorer la robustesse.
- Outils Utilisés : Spring Boot, JUnit, Selenium Java (E2E).

## DevSecOps — checklist (à afiner)
- Authentification / Autorisation : Keycloak (ou équivalent).
  - Ne pas stocker de mots de passe en clair dans la base ; externaliser la gestion d'identités.
- Secrets : ne pas committer. Utiliser Vault, AWS Secrets Manager, Kubernetes Secrets ou équivalent (TODO).
- Dépendances : SCA (OWASP Dependency‑Check, Snyk, Dependabot) (TODO dans la chaine CI/CD).
- CI : SAST minimal (ESLint/TSLint pour frontend, SpotBugs/Bandit selon la stack) + tests unitaires.
- TLS : activer TLS sur les endpoints publics (certificats en staging/production).
- Logging / monitoring basique : succès/échecs d'authentification, erreurs applicatives, métriques de disponibilité.
- Politique de mots de passe et MFA (si le contexte l'impose).
- Contrôles d’accès : RBAC ou scopes simples selon les besoins.

## Installation (TODO)
- Java 21+ (ou version définie par le projet)
- Pour édition/lancement mode dev : VSCode avec Extension Pack pour Java, Maven Spring Boot Tools, Vue ou Spring Tool Suite (Eclipse)
- Pour chaine CI/CD  Jenkins 2.528.1 ou + (TODO)
- Pour déploiement env de test : Docker Compose (TODO)

## Lancer le projet (TODO)
1. Démarrer les services dépendants (Keycloak, base de données) — exemple avec Docker Compose :
   ```bash
   docker compose up -d
   ```
2. Lancer le back‑end et le front-end
   ```bash
   mvn clean spring-boot:run
   ```
3. Lancer les tests E2E (projet séparé `rhDemoAPITestIHM`) :
   ```bash
   # Exemple pour Selenium (via Maven ou script dédié)
   mvn -f rhDemoAPITestIHM clean test
   ```

## Bonnes pratiques et conseils
- Utiliser `data-testid` pour les éléments critiques testés en E2E.
- Ne pas sur‑spécifier l'IHM : s'adapter aux composants Element Plus facilite la maintenance même si il peut y avoir dans certains cas des problèmes pour insérer le 'data-testid'.
- Documenter particulièrement les flows d'authentification (schémas, cookies, CSRF) et l'interface avec KeyCloak .
- Gérer la pagination côté API avec des limites et des offsets/cursors pour garder de bonnes performances.
- Automatiser les scans de sécurité dans la CI (TODO).

## Contribuer
- Ouvrir une issue décrivant la modification souhaitée.
- Créer une branche par feature/bugfix : `feature/ma-feature` ou `fix/ma-correction`.
- Respecter la convention de commits du projet (ex. Conventional Commits).
- Ajouter/mettre à jour les tests si nécessaire.

## Licence
- Licence Apache 2.0
