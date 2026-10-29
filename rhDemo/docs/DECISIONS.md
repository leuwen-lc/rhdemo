---
statut: actif
verifie_le: 2026-10-29
sources:
  - rhDemo/src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java
  - rhDemo/pom.xml
  - rhDemo/infra/stagingkub/kind-config.yaml
  - rhDemo/infra/stagingkub/rbac/
  - rhDemo/infra/stagingkub/networkpolicies/
---

# Décisions techniques

Raisons des choix structurants du projet. Contexte : preuve de concept DevSecOps, logiciel libre à 100 %, indépendance vis-à-vis des plateformes SaaS, fonctionnement sur un seul PC Linux de 16 Go.

Pour le détail de mise en œuvre, suivre les liens vers les documents thématiques.

## Pourquoi BFF (Backend For Frontend) ?

- **Sécurité** : les tokens OAuth2 ne transitent jamais côté client
- **Session stateful** : cookie `JSESSIONID` avec protection CSRF ([CSRF_GUIDE.md](CSRF_GUIDE.md))
- **Simplicité frontend** : pas de gestion de rafraîchissement de token côté Vue.js

## Pourquoi Keycloak ?

- IAM standard de l'industrie, open source
- SSO inter-applications
- Politiques de mots de passe, MFA, vérification email
- Intégration OIDC native avec Spring Security

## Pourquoi 2 environnements de déploiement ?

- **ephemere** : tests rapides en CI, débogage facile
- **stagingkub** : validation Kubernetes, proche d'une production
- Démontre la portabilité de l'application

## Pourquoi SOPS pour les secrets ?

- Secrets versionnés dans Git (chiffrés)
- Pas besoin d'infrastructure centralisée (Vault) pour démarrer
- Compatible avec les workflows Git (review, audit)
- Migration vers Vault possible sans changer l'applicatif

Mise en œuvre : [SOPS_SETUP.md](SOPS_SETUP.md).

## Pourquoi Maven pour le frontend ?

- Build unique backend + frontend
- Simplifie la CI/CD (une seule commande `mvnw clean package`)
- Frontend copié dans `target/classes/static/` automatiquement
- L'image Docker finale contient l'application complète

## Pourquoi KinD plutôt que Minikube/K3s ?

- Kubernetes-in-Docker : isolation, reproductibilité
- Clusters éphémères faciles à créer/détruire
- Compatible CI/CD (Docker-in-Docker)
- Représentatif d'un vrai cluster Kubernetes
- **extraMounts** pour la persistance des données hors du conteneur ([kind-config.yaml](../infra/stagingkub/kind-config.yaml))

## Pourquoi StatefulSets + CronJobs pour PostgreSQL ?

- **Simplicité** : pas de dépendance à un opérateur externe
- **Ressources limitées** : adapté à un PC de 16 Go
- **Backups automatiques** : CronJobs quotidiens, rétention configurable (7 jours) ([POSTGRESQL_BACKUP_CRONJOBS.md](POSTGRESQL_BACKUP_CRONJOBS.md))
- **Persistance garantie** : les extraMounts KinD survivent aux redémarrages
- **Contrôle total** : configuration PostgreSQL directe, sans abstraction
- **Débogage facile** : `kubectl logs/exec` standards, pas de CRDs

## Pourquoi RBAC pour Jenkins ?

- **Moindre privilège** : Jenkins n'agit que sur le namespace de déploiement
- **Pas d'accès admin** : impossible de générer un kubeconfig admin (CLI `kind` retirée de l'image)
- **Isolation** : aucun accès à `kube-system` ou aux autres namespaces sensibles
- **Audit** : actions traçables via l'API audit Kubernetes
- **Credential sécurisé** : le kubeconfig RBAC est un credential Jenkins chiffré

Détail : [SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md](SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md).

## Pourquoi Network Policies Zero Trust ?

- **Default Deny** : tout trafic est bloqué par défaut, seuls les flux explicites sont autorisés
- **Isolation des données** : les deux PostgreSQL ne communiquent pas entre eux
- **Pas d'exfiltration** : egress vers Internet bloqué (sauf DNS interne)
- **Défense en profondeur** : une application compromise ne se propage pas
- **Conformité** : prépare le terrain pour des audits de sécurité (PCI-DSS, SOC2)

Flux autorisés : [SECURITE_NETWORK_POLICY.md](SECURITE_NETWORK_POLICY.md).

## Pourquoi le merge Renovate est piloté par Jenkins ?

Jenkins n'est pas exposé sur Internet : Forgejo ne peut pas déclencher de webhook entrant et les statuts CI ne remontent jamais vers Forgejo. Le merge se fait donc via l'API Forgejo depuis le pipeline, pas par l'automerge natif de Renovate. Détail : [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md).
