# Politique de sécurité

Ce projet est une **preuve de concept école**, non destinée à la production, mais la sécurité y est traitée sérieusement (BFF, CSP stricte, secrets chiffrés SOPS, NetworkPolicies, scans Trivy et OWASP Dependency-Check en CI).

## Versions prises en charge

Seule la dernière version publiée (et la branche `master`) reçoit des correctifs de sécurité.

## Signaler une vulnérabilité

**Ne pas ouvrir de ticket public** pour une vulnérabilité : Codeberg n'offre pas de signalement privé.

Écrire à **leuwenlc@gmail.com** (objet : « Sécurité RHDemo ») avec :

- une description de la faille et de son impact ;
- les étapes de reproduction (version, environnement, requête ou code) ;
- si possible, une piste de correction.

## Délais indicatifs

Projet maintenu sur le temps libre, sans engagement contractuel :

- accusé de réception sous 7 jours ;
- première évaluation sous 14 jours ;
- correctif ou contournement documenté dès que possible, puis divulgation coordonnée avec la personne qui a signalé.

## Périmètre

Dans le périmètre : le code du dépôt (backend, frontend, scripts, Jenkinsfile, manifestes Kubernetes et Helm).

Hors périmètre : les vulnérabilités des dépendances amont déjà suivies par la CI (voir `rhDemo/docs/SECURITY_ADVISORIES.md` et `rhDemo/docs/TRIVY_SECURITY_SCAN.md`), les secrets de démonstration, et les attaques nécessitant un accès administrateur à l'hôte.

## Pour en savoir plus

Voir `rhDemo/docs/` (notamment `CSRF_GUIDE.md`, `SECURITE_WEB_CSP.md`, `SECURITE_NETWORK_POLICY.md`, `SOPS_SETUP.md`).
