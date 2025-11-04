# Projet école — preuve de concept

Ce dépôt est une preuve de concept visant à explorer un ensemble de sujets techniques et de bonnes pratiques pour une application web full‑stack (Spring Boot + Vue.js).

## Objectifs
- Expérimenter des outils et méthodes standards et largement adoptés.
- Utiliser un agent IA (Copilot Chat dans VS Code) pour améliorer la productivité et la qualité du code.
- S'appuyer sur Spring Boot et son écosystème pour le back‑end.
- Fournir une IHM riche côté client avec Vue.js et le design system Element Plus.
- Mettre en place une structure évolutive (layers, API, client riche, gestion des rôles).
- Intégrer des considérations DevSecOps dès le début du projet.

## Principes généraux
- Favoriser l'utilisation des composants fournis (Element Plus) plutôt que de sur‑spécifier l'IHM.
- Rendre les tests IHM robustes (usage de marqueurs `data-testid`), tout en vérifiant l'accessibilité d'Element Plus dans le contexte de l'application.
- Préférer les solutions éprouvées pour l'authentification et la gestion des identités (Keycloak).
- Séparer les responsabilités : Backend For Frontend (BFF) pour simplifier les flows d'authentification côté client.

## Fonctionnalités
- Application basique CRUD (Create / Read / Update / Delete).
- Architecture prête pour évoluer vers une application métier plus complète (couches métier, persistance, API REST, client riche, gestion des rôles).
- Pagination gérée côté front‑end et back‑end (attention à l'impact perf lorsque le jeu de données grossit).

## Architecture
- Back‑end : Spring Boot, Spring Security (BFF pour déléguer l'authentification).
  - Le front‑end ne récupère pas directement le token auprès du serveur d'auth ; c'est le back‑end qui s'en charge.
  - Le back‑end renvoie un cookie de session (approche stateful) ; il faut activer la protection CSRF.
- Front‑end : Vue.js + Element Plus (design system) — privilégier les composants standards pour accélérer le développement.
- Tests d'interface : projet séparé pour les tests Selenium (scénarios de bout en bout). Option possible : remplacer par Cypress selon préférence.

## Tests
- Tests unitaires pour le back‑end et le front‑end.
- Tests d'intégration / bout en bout :
  - Selenium (projet séparé) avec marqueurs CSS `data-testid` pour améliorer la robustesse.
  - Possibilité de migration vers Cypress si souhaité.
- Outils recommandés : JUnit, Mockito (backend), Jest / Vue Test Utils (frontend), Selenium / Cypress (E2E).

## DevSecOps — checklist (à intégrer dès le début)
- Authentification / Autorisation : Keycloak (ou équivalent).
  - Ne pas stocker de mots de passe en clair dans la base ; externaliser la gestion d'identités.
- Secrets : ne pas committer. Utiliser Vault, AWS Secrets Manager, Kubernetes Secrets ou équivalent.
- Dépendances : SCA (OWASP Dependency‑Check, Snyk, Dependabot).
- CI : SAST minimal (ESLint/TSLint pour frontend, SpotBugs/Bandit selon la stack) + tests unitaires.
- TLS : activer TLS sur les endpoints publics (certificats en staging/production).
- Logging / monitoring basique : succès/échecs d'authentification, erreurs applicatives, métriques de disponibilité.
- Politique de mots de passe et MFA (si le contexte l'impose).
- Contrôles d’accès : RBAC ou scopes simples selon les besoins.

## Installation (prérequis)
- Java 11+ (ou version définie par le projet)
- Maven (ou Gradle selon le projet)
- Node.js 14+ et npm/yarn
- Docker (optionnel, pour Keycloak, base de données, etc.)

## Lancer le projet (exemples)
1. Démarrer les services dépendants (Keycloak, base de données) — exemple avec Docker Compose :
   ```bash
   docker compose up -d
   ```
2. Lancer le back‑end (depuis le répertoire `backend`) :
   ```bash
   mvn clean spring-boot:run
   ```
3. Lancer le front‑end (depuis le répertoire `frontend`) :
   ```bash
   npm install
   npm run dev
   ```
4. Lancer les tests E2E (projet séparé `e2e-tests`) :
   ```bash
   # Exemple pour Selenium (via Maven ou script dédié)
   mvn -f e2e-tests clean test
   ```

Remplace les commandes ci‑dessous par celles correspondant à ton projet (Gradle, Yarn, etc.).

## Bonnes pratiques et conseils
- Utiliser `data-testid` pour les éléments critiques testés en E2E.
- Ne pas sur‑spécifier l'IHM : s'adapter aux composants Element Plus facilite la maintenance.
- Documenter les flows d'authentification (schémas, cookies, CSRF) pour les nouveaux arrivants.
- Gérer la pagination côté API avec des limites et des offsets/cursors pour garder de bonnes performances.
- Mettre en place des règles de protection sur les branches et automatiser les scans de sécurité dans la CI.

## Contribuer
- Ouvrir une issue décrivant la modification souhaitée.
- Créer une branche par feature/bugfix : `feature/ma-feature` ou `fix/ma-correction`.
- Respecter la convention de commits du projet (ex. Conventional Commits).
- Ajouter/mettre à jour les tests si nécessaire.

## Licence
- Licence Apache 2.0
