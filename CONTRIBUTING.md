# Contribuer à RHDemo

Merci de votre intérêt ! Ce dépôt est un projet école servant de support à une démarche DevSecOps complète. Les contributions (corrections, documentation, idées) sont bienvenues, dans le respect du [code de conduite](CODE_OF_CONDUCT.md).

## Avant de commencer

- Lire le [README](README.md), puis `rhDemo/docs/index.md` (catalogue de la documentation) et `rhDemo/docs/DECISIONS.md` (raisons des choix techniques).
- Pour un changement important, **ouvrir d'abord un ticket** afin d'en discuter.
- Les failles de sécurité se signalent en privé : voir [SECURITY.md](SECURITY.md).

## Principes du projet

- Logiciel libre à 100 %, pas de dépendance à une plateforme SaaS (pas de GitHub Actions).
- Sécurité dès la conception. Invariants à respecter : tokens OAuth2 côté backend (BFF) avec CSRF actif, CSP stricte (aucun JavaScript inline, jamais `unsafe-inline` ni `unsafe-eval`), secrets uniquement chiffrés par SOPS, NetworkPolicies en Default Deny, images Docker épinglées par digest.
- L'application métier reste volontairement simple.

## Mise en place

Depuis `rhDemo/` (Java 25, Maven wrapper fourni) :

```bash
./mvnw spring-boot:run      # développement local (voir infra/dev)
./mvnw test                 # tests unitaires
./mvnw verify               # tests d'intégration
```

Environnements et ports : `rhDemo/infra/ENVIRONMENTS.md`.

## Conventions

- **Backend** : `Controller → Service → Repository`, package `fr.leuwen.rhdemoAPI`, tests d'intégration en `*IT.java`.
- **Frontend** : composants Vue en PascalCase, appels HTTP dans `services/`, attribut `data-testid` sur tout élément interactif.
- **Qualité (SonarQube, nouveau code)** : couverture ≥ 50 %, aucune issue Medium ou supérieure, aucun security hotspot.
- **Documentation** en français ; contrôle avec `python3 -I rhDemo/scripts/docs-lint.py`.
- **Commits en français**, avec préfixe conventionnel : `feat`, `fix`, `docs`, `chore`, etc. Exemple : `fix(csrf): corriger le cookie XSRF-TOKEN en environnement éphémère`.

## Proposer une modification

1. Forker le dépôt et créer une branche à partir de la branche d'évolution en cours.
2. Faire des commits petits et ciblés.
3. Vérifier que `./mvnw verify` passe et que la documentation concernée est à jour.
4. Ouvrir une demande de fusion en remplissant le modèle fourni.

## Licence

En contribuant, vous acceptez que votre contribution soit publiée sous la licence du projet (Apache 2.0, voir [LICENSE](LICENSE)).
