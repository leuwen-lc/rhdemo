---
statut: actif
verifie_le: 2026-11-22
sources:
  - rhDemo/scripts/rotate-secrets.py
  - rhDemo/scripts/rotation_lib/
  - rhDemo/secrets/inventory.yaml
  - rhDemo/infra/jenkins-docker/openbao/lib.sh
  - rhDemo/infra/jenkins-docker/openbao/init-local-ca.sh
  - rhDemo/infra/stagingkub/external-secrets/observability.yaml
  - rhDemo/infra/ephemere/docker-compose.yml
---

# Secrets au quotidien : rotation, tâches récurrentes, accès

Ce guide couvre l'exploitation courante des secrets : ce qu'il faut faire régulièrement, comment se servir de `rotate-secrets.py`, quoi faire en cas de fuite, et où retrouver un mot de passe pour se connecter. Il complète :

- [OPENBAO.md](OPENBAO.md) : installation, déverrouillage, sauvegarde, jeton root, et détail de chaque rotation automatisée (section « Rotation ») ;
- `rhDemo/secrets/inventory.yaml` : liste de référence de tous les secrets, sans valeur, avec leur méthode ou procédure de rotation ;
- [ETUDE_ROTATION_SECRETS.md](ETUDE_ROTATION_SECRETS.md) : raisons des choix (criticité, exposition, ordre d'urgence) et ce qui reste à automatiser.

## Où vivent les secrets

| Où | Quoi |
| --- | --- |
| OpenBao (`kv/`) | Tokens et clés des pipelines (`kv/jenkins/*`), secrets de stagingkub (`kv/stagingkub/*`, `kv/stagingkub-tests/users`), admin de Grafana (`kv/observability/grafana`) ; clé Cosign (Transit, non exportable) |
| KeePassXC | Racines de confiance : clé de déverrouillage et mot de passe `admin` d'OpenBao, clé et phrase de passe de la racine de l'autorité locale, mots de passe des comptes bots Codeberg |
| Credentials Jenkins | Ce qui n'est pas dans OpenBao : <br>• `secret_id` AppRole (`openbao-approle`, `openbao-cosign-approle`) : le « mot de passe » avec lequel Jenkins se connecte à OpenBao, couplé à un `role_id` (l'identifiant). Il ne peut pas être dans OpenBao puisqu'il sert à y entrer ; il expire à 100 jours ; <br>• kubeconfigs (`kubeconfig-stagingkub`…) : fichiers de connexion au cluster stagingkub (adresse de l'API, certificat, jeton du ServiceAccount de Jenkins aux droits limités) ; <br>• SMTP, token SonarQube |
| Fichiers locaux non versionnés (mode 600) | `rhDemo/infra/jenkins-docker/.env` (comptes Jenkins, base SonarQube : gardés hors d'OpenBao par choix, pour que Jenkins démarre sans OpenBao déverrouillé ; copie dans KeePassXC) |
| Nulle part | Ephemere : valeurs tirées au hasard à chaque build, perdues avec l'environnement |

## Tâches récurrentes

| Quand | Tâche | Comment |
| --- | --- | --- |
| Après chaque redémarrage du poste ou d'OpenBao | Déverrouiller OpenBao | [OPENBAO.md](OPENBAO.md), « Déverrouillage » |
| Chaque semaine (ou par cron) | Repérer les secrets à renouveler | `rhDemo/scripts/rotate-secrets.py --check`, puis renouveler ce qui est signalé (section suivante) |
| Tous les 90 jours au plus | `secret_id` AppRole de Jenkins et Cosign : **ils expirent à 100 jours**, après quoi les pipelines (dont fixcve-auto) perdent l'accès à OpenBao | `rotate-secrets.py openbao-approle-jenkins openbao-approle-cosign` |
| Avant l'échéance annuelle | Certificat TLS d'OpenBao (1 an) | Échéance : `openssl x509 -enddate -noout -in rhDemo/infra/jenkins-docker/certs/openbao/openbao.crt` ; renouvellement : `openbao/init-local-ca.sh openbao`, `docker compose restart openbao`, déverrouillage |
| Tous les 5 ans (racine : 10 ans) | Certificat de l'intermédiaire de l'autorité locale | Pas de commande dédiée : signer un nouvel intermédiaire avec la clé racine sortie de KeePassXC (mêmes commandes `openssl` que `init-local-ca.sh ca`), puis réémettre le certificat d'OpenBao |
| Avant leur expiration | Clé GPG de Renovate (2 ans), token SonarQube (date choisie à sa création) | `rotate-secrets.py renovate-gpg-key`, `rotate-secrets.py jenkins-sonar-token` |
| Après une série de rotations | Instantané d'OpenBao | [OPENBAO.md](OPENBAO.md), « Sauvegarde et restauration » |

Rappel automatique : `--check` ne lit que le journal local et ne demande rien, il peut tourner en cron (code retour 1 si un secret est en retard ou jamais tracé), par exemple chaque lundi :

```bash
0 9 * * 1  ~/git/repository/rhDemo/scripts/rotate-secrets.py --check >/dev/null || notify-send "RHDemo : secrets à renouveler"
```

Périodes cibles, par criticité (`periods` de l'inventaire) : C 90 jours, H 180 jours, M 1 an.

## Utiliser `rotate-secrets.py`

Le script tourne sur le poste, jamais dans Jenkins (il doit pouvoir réparer un Jenkins compromis). Depuis `rhDemo/scripts/` :

```bash
./rotate-secrets.py --list                 # chaque secret, sa méthode ou sa procédure
./rotate-secrets.py --check                # âge des secrets, retards
./rotate-secrets.py --preflight            # accès Jenkins, cibles, outils, sans rien modifier
./rotate-secrets.py --dry-run <id>         # lectures seulement : affiche ce qui serait créé et révoqué
./rotate-secrets.py <id> [<id>...]         # renouveler
./rotate-secrets.py --level C              # tous les secrets automatisés de criticité C
./rotate-secrets.py --record <id>          # tracer une rotation faite à la main
```

Trois sortes de secrets, selon la méthode affichée par `--list` :

- **automatisés** (tokens et clé GPG Codeberg, `secret_id` AppRole, mots de passe PostgreSQL, secrets Keycloak de stagingkub, admin Grafana) : le script crée la nouvelle valeur, la vérifie, la propage puis révoque l'ancienne. Ce que fait chaque méthode : [OPENBAO.md](OPENBAO.md), « Rotation » ;
- **semi-manuels** (`manual-value` : SMTP, token SonarQube) : la valeur est créée à la main chez le fournisseur, collée quand le script la demande, testée si possible, puis propagée ;
- **manuels** (`manual` : mots de passe des comptes Jenkins, clé Cosign, kubeconfigs, mot de passe `admin` et clé de déverrouillage d'OpenBao…) : `--list` affiche la procédure ; une fois faite, `--record <id>` la trace pour `--check`.

Saisies demandées selon les secrets choisis, puis oubliées à la fin : mot de passe `admin` de Jenkins, mot de passe `admin` d'OpenBao, mot de passe et code TOTP du bot Codeberg concerné, valeur créée à la main. Aucune valeur n'est affichée, écrite sur le disque ni passée en argument de commande ; le journal (`~/.config/rhdemo-rotation/journal.jsonl`) ne contient que des dates et des identifiants.

Conseils : `--dry-run` d'abord, un secret à la fois pour une première rotation, OpenBao déverrouillé et, pour stagingkub, le cluster démarré (contexte `kind-rhdemo`). En cas d'échec, le script annule ce qu'il a déjà fait et le dit ; s'il n'y parvient pas, son message indique quoi comparer.

**Ajouter un secret** : une entrée dans `inventory.yaml` (méthode et cibles existantes, ou procédure manuelle), la valeur dans OpenBao, puis `./rotate-secrets.py --dry-run <id>`.

## Rotation d'urgence (fuite supposée)

Pas encore de mode `--emergency` : enchaîner à la main, dans cet ordre (raisons : [ETUDE_ROTATION_SECRETS.md](ETUDE_ROTATION_SECRETS.md), §3.3). En urgence, révoquer l'ancien avant de vérifier le nouveau : mieux vaut une CI cassée qu'un attaquant actif.

1. **Si Jenkins ou le poste sont compromis**, d'abord : mot de passe `admin` de Jenkins (`jenkins-admin-password`, redémarrage du conteneur pour couper les sessions), puis `rotate-secrets.py openbao-approle-jenkins`.
2. Exposés sur Internet : `rotate-secrets.py ci-bot-forgejo-token renovate-forgejo-token fixcve-forgejo-token renovate-gpg-key`, mots de passe des bots et contrôle du compte personnel (procédures `codeberg-bot-passwords`, `codeberg-personal`), SMTP (`smtp-infomaniak`), session Claude (`claude-subscription`).
3. Exposés sur le réseau local : `rotate-secrets.py stagingkub-oidc-client stagingkub-keycloak-admin stagingkub-test-users stagingkub-rhdemo-db stagingkub-keycloak-db grafana-admin`, clés TLS.
4. Locaux : `secret_id` AppRole restants, mot de passe `admin` d'OpenBao, clé de déverrouillage si elle a pu fuir, clé Cosign, kubeconfigs, compte Jenkins `claude`, token SonarQube.

## Retrouver un secret

### Lire une valeur dans OpenBao

OpenBao déverrouillé, mot de passe `admin` demandé ; la valeur s'affiche dans le terminal : la copier, puis effacer l'écran.

Une valeur se désigne par un **chemin** et une **clé** : `openbao_kv_get <chemin> <clé>`. Dans le tableau ci-dessous, `kv/stagingkub/keycloak` `admin_password` se lit donc `openbao_kv_get stagingkub/keycloak admin_password` (sans le préfixe `kv/`, qui est le point de montage).

Exemple, console d'administration de Keycloak :

```bash
source rhDemo/infra/jenkins-docker/openbao/lib.sh
openbao_admin_login                                   # jeton d'une heure
openbao_kv_get stagingkub/keycloak admin_user; echo
openbao_kv_get stagingkub/keycloak admin_password; echo
openbao_admin_logout                                  # révoque le jeton
```

Exemple, utilisateurs de test de l'application : profil admin, puis profil consultation et mise à jour (même chemin `stagingkub-tests/users`, une paire de clés par profil) :

```bash
source rhDemo/infra/jenkins-docker/openbao/lib.sh
openbao_admin_login
openbao_kv_get stagingkub-tests/users iduseradmin; echo    # identifiant, profil admin
openbao_kv_get stagingkub-tests/users pwduseradmin; echo   # mot de passe, profil admin
openbao_kv_get stagingkub-tests/users idusermaj; echo      # identifiant, profil MAJ
openbao_kv_get stagingkub-tests/users pwdusermaj; echo     # mot de passe, profil MAJ
openbao_admin_logout
```

Exemple, compte administrateur de Grafana :

```bash
source rhDemo/infra/jenkins-docker/openbao/lib.sh
openbao_admin_login
openbao_kv_get observability/grafana admin_user; echo
openbao_kv_get observability/grafana admin_password; echo
openbao_admin_logout
```

Liste de tous les champs d'un chemin : `docker exec -e BAO_TOKEN rhdemo-openbao bao kv get -mount=kv <chemin>` (entre login et logout).

### Où trouver quoi

Notation : chemin OpenBao puis clé, à passer à `openbao_kv_get` sans le préfixe `kv/`.

| Pour se connecter à… | Identifiant | Mot de passe |
| --- | --- | --- |
| Keycloak de stagingkub, console d'administration (https://keycloak-stagingkub.intra.leuwen-lc.fr, realm `master`) | `kv/stagingkub/keycloak` `admin_user` | `kv/stagingkub/keycloak` `admin_password` |
| Application stagingkub (https://rhdemo-stagingkub.intra.leuwen-lc.fr), profil **admin** (`ROLE_admin`) | `kv/stagingkub-tests/users` `iduseradmin` | `kv/stagingkub-tests/users` `pwduseradmin` |
| Application stagingkub, profil **consultation et mise à jour** (`ROLE_consult`, `ROLE_MAJ`) | `kv/stagingkub-tests/users` `idusermaj` | `kv/stagingkub-tests/users` `pwdusermaj` |
| Application stagingkub, profil **consultation** (`ROLE_consult`) | `kv/stagingkub-tests/users` `iduserconsult` | `kv/stagingkub-tests/users` `pwduserconsult` |
| Grafana (https://grafana-stagingkub.intra.leuwen-lc.fr) | `kv/observability/grafana` `admin_user` | `kv/observability/grafana` `admin_password`, ou `kubectl get secret grafana-admin -n loki-stack -o jsonpath='{.data.admin-password}' \| base64 -d` |
| Jenkins (http://localhost:8080) | `admin` (ou `claude`, lecture seule) | `JENKINS_ADMIN_PASSWORD` (ou `JENKINS_CLAUDE_PASSWORD`) de `rhDemo/infra/jenkins-docker/.env` |
| OpenBao, utilisateur `admin` | `admin` | KeePassXC |
| Ephemere gardé après un build (option `KEEP_EPHEMERE_ENV`), console Keycloak (https://keycloak.ephemere.local:58443) | `admin` | `docker exec keycloak-ephemere printenv KEYCLOAK_ADMIN_PASSWORD` ; les mots de passe des utilisateurs de test ne sont pas conservés : les réinitialiser depuis cette console |
| Poste de développement | voir [infra/dev/README.md](../infra/dev/README.md) | `rhDemo/infra/dev/.env`, `rhDemo/secrets/secrets-rhdemo.yml` |

Les valeurs lues par les pipelines (tokens Codeberg, GitHub, Docker Hub…) sont dans `kv/jenkins/<identifiant du credential>`, y compris celles de fixcve-auto (`fixcve-forgejo-token`, `fixcve-jenkins-api` : token API du compte Jenkins `claude`, aussi demandé par le skill `/fixcve`). Une valeur renouvelée par le script se relit de la même façon.
