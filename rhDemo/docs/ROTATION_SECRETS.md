---
statut: actif
verifie_le: 2026-11-25
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
- [ETUDE_ROTATION_SECRETS.md](etudes/ETUDE_ROTATION_SECRETS.md) : raisons des choix (criticité, exposition, ordre d'urgence) et ce qui reste à automatiser.

## Où vivent les secrets

| Où | Quoi |
| --- | --- |
| OpenBao (`kv/`) | Tokens et clés des pipelines (`kv/jenkins/*` : tokens des bots Codeberg, clé GPG et tokens de Renovate, Docker Hub, adresse de notification, credentials de fixcve-auto), secrets de stagingkub (`kv/stagingkub/*`, `kv/stagingkub-tests/users`), admin de Grafana (`kv/observability/grafana`) ; clé Cosign (Transit, non exportable) |
| KeePassXC | Racines de confiance : clé de déverrouillage (avec une copie papier) et mot de passe `admin` d'OpenBao, clé et phrase de passe de la racine de l'autorité locale. Comptes en ligne : mots de passe des comptes bots Codeberg, codes de récupération 2FA des bots et du compte personnel (la graine TOTP n'est que sur le téléphone). Mot de passe de l'interface admin de SonarQube. Copie de `.env` (ligne suivante). Pas de jeton root d'OpenBao : révoqué après l'installation ([OPENBAO.md](OPENBAO.md), « Jeton root ponctuel ») |
| Credentials Jenkins | Ce qui n'est pas dans OpenBao : <br>• `secret_id` AppRole (`openbao-approle`, `openbao-cosign-approle`) : le « mot de passe » avec lequel Jenkins se connecte à OpenBao, couplé à un `role_id` (l'identifiant). Il ne peut pas être dans OpenBao puisqu'il sert à y entrer ; il expire à 100 jours ; <br>• kubeconfigs (`kubeconfig-stagingkub`…) : fichiers de connexion au cluster stagingkub (adresse de l'API, certificat, jeton du ServiceAccount de Jenkins aux droits limités) ; <br>• SMTP, token SonarQube, clé API NVD et compte OSS Index (Dependency-Check), clé publique Cosign (non secrète) |
| Fichiers locaux non versionnés (mode 600) | `rhDemo/infra/jenkins-docker/.env` (comptes Jenkins, base SonarQube : gardés hors d'OpenBao par choix, pour que Jenkins démarre sans OpenBao déverrouillé ; copie dans KeePassXC) |
| Nulle part | Ephemere : valeurs tirées au hasard à chaque build, perdues avec l'environnement |

Dans la console Jenkins (Administrer Jenkins > Credentials), les secrets de `kv/jenkins/*` restent visibles sous leur identifiant habituel, avec le type « Vault Secret Text Credential » ou « Vault Username-Password Credential » : ce sont des **références** (chemin `kv/jenkins/<id>` et clé), la valeur n'est pas stockée dans Jenkins mais lue dans OpenBao à chaque utilisation. Les modifier dans la console (chemin, clé, ou remplacement par un credential ordinaire) casse la lecture ou détache le credential d'OpenBao, et les rotations ne s'y propagent plus. Pour changer une valeur : `rotate-secrets.py <id>`, ou `bao kv put` sur `kv/jenkins/<id>` ([OPENBAO.md](OPENBAO.md)) ; pour recréer une référence : `openbao-setup.py jenkins <id>`.

## Tâches récurrentes

| Quand | Tâche | Comment |
| --- | --- | --- |
| Après chaque redémarrage du poste ou d'OpenBao | Déverrouiller OpenBao | [OPENBAO.md](OPENBAO.md), « Déverrouillage » |
| Chaque semaine (ou par cron) | Repérer les secrets à renouveler | `rhDemo/scripts/rotate-secrets.py --check`, puis renouveler ce qui est signalé (section suivante) |
| Tous les 90 jours au plus | `secret_id` AppRole de Jenkins et Cosign : **ils expirent à 100 jours**, après quoi les pipelines (dont fixcve-auto) perdent l'accès à OpenBao | `rotate-secrets.py openbao-approle-jenkins openbao-approle-cosign` |
| Avant l'échéance annuelle | Certificat TLS d'OpenBao (1 an) | Échéance : `openssl x509 -enddate -noout -in rhDemo/infra/jenkins-docker/certs/openbao/openbao.crt` ; renouvellement : `openbao/init-local-ca.sh openbao`, `docker compose restart openbao`, déverrouillage |
| Tous les 5 ans (racine : 10 ans) | Certificat de l'intermédiaire de l'autorité locale | Pas de commande dédiée : signer un nouvel intermédiaire avec la clé racine sortie de KeePassXC (mêmes commandes `openssl` que `init-local-ca.sh ca`), puis réémettre le certificat d'OpenBao |
| Avant leur expiration | Clé GPG de Renovate (2 ans), token SonarQube, tokens GitHub et Docker Hub de Renovate (1 an, fixé à leur création) | `rotate-secrets.py renovate-gpg-key`, `rotate-secrets.py jenkins-sonar-token`, `rotate-secrets.py renovate-github-token` (expiré : 401 sur github.com dans le dashboard Renovate), `rotate-secrets.py dockerhub-renovate-readonly` (expiré : échec du stage « Scan Renovate ») |
| En cas de clé refusée ou compromise | Clé API NVD, jeton OSS Index (sans expiration) | `rotate-secrets.py nvd-api-key`, `rotate-secrets.py ossindex-credentials` |
| Après une série de rotations | Instantané d'OpenBao et copie du journal des rotations (`journal.jsonl`) | [OPENBAO.md](OPENBAO.md), « Sauvegarde et restauration » |
| Chaque dimanche (cron, automatique) | Rotation du journal d'audit d'OpenBao, 12 archives compressées gardées | `openbao/rotate-audit.sh` ; vérifier de temps en temps `~/.cache/rhdemo-openbao-audit-rotate.log` ([OPENBAO.md](OPENBAO.md), « Journal d'audit ») |

Rappel automatique : `--check` ne lit que le journal local et ne demande rien, il peut tourner en cron (code retour 1 si un secret est en retard ou si aucune rotation n'est journalisée pour lui), par exemple chaque lundi :

```bash
0 9 * * 1  ~/git/repository/rhDemo/scripts/rotate-secrets.py --check >/dev/null || DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus notify-send "RHDemo : secrets à renouveler"
```

Lancé par cron, `notify-send` ne trouve pas la session de bureau sans `DBUS_SESSION_BUS_ADDRESS` (`1000` : remplacer par la valeur de `id -u`) ; la notification n'apparaît que si la session graphique est ouverte au moment du passage.

Périodes cibles, par criticité (`periods` de l'inventaire) : C 90 jours, H 180 jours, M 1 an.

## Utiliser `rotate-secrets.py`

Le script tourne sur le poste, jamais dans Jenkins (il doit pouvoir réparer un Jenkins compromis). Depuis `rhDemo/scripts/` :

```bash
./rotate-secrets.py --list                 # chaque secret, sa criticité, sa sorte de rotation et sa méthode
./rotate-secrets.py --check                # âge des secrets, retards
./rotate-secrets.py --preflight            # accès Jenkins, cibles, outils, sans rien modifier
./rotate-secrets.py --dry-run <id>         # lectures seulement : affiche ce qui serait créé et révoqué
./rotate-secrets.py <id> [<id>...]         # renouveler
./rotate-secrets.py --level C              # tous les secrets à rotation automatique de criticité C
./rotate-secrets.py --record <id>          # tracer une rotation faite à la main
./rotate-secrets.py --emergency            # rotation d'urgence de tout le périmètre (section dédiée)
```

Quatre sortes de rotation, affichées par `--list` (colonne « rotation », méthode de l'inventaire entre parenthèses) :

- **automatique** (tokens et clé GPG Codeberg, `secret_id` AppRole, mots de passe PostgreSQL, secrets Keycloak de stagingkub, admin Grafana, kubeconfigs de Jenkins) : le script crée la nouvelle valeur, la vérifie, la propage puis révoque l'ancienne. Ce que fait chaque méthode : [OPENBAO.md](OPENBAO.md), « Rotation » ;
- **semi-manuelle** (`manual-value` : SMTP, token SonarQube) : la valeur est créée à la main chez le fournisseur, collée quand le script la demande, testée si possible, puis propagée ;
- **manuelle** (`manual` : mots de passe des comptes Jenkins, clé Cosign, clés TLS, mot de passe `admin` et clé de déverrouillage d'OpenBao…) : `rotate-secrets.py <id>` affiche la procédure, sans rien modifier ; une fois faite, `--record <id>` la trace pour `--check` ;
- **à chaque build** (`per-build` : secrets d'ephemere) : rien à renouveler. `--check` les affiche (« régénéré à chaque build ») sans les compter en retard ; la rotation et `--record` les refusent, pour que le journal ne contienne pas de fausse trace.

« (bloquant) » à la fin de l'état dans `--check` (« , bloquant » après la méthode dans `--list`) marque un secret qui **cesse de fonctionner** s'il n'est pas renouvelé à temps : `secret_id` AppRole (100 jours), clé GPG de Renovate (2 ans), token SonarQube et token GitHub de Renovate (1 an). Les autres secrets en retard ne posent qu'une question d'hygiène. Pour un secret bloquant de durée de vie connue (`blocking` et `lifetime_days` dans l'inventaire), les jours restants sont comptés jusqu'à 14 jours avant l'expiration si cette échéance précède la période de sa criticité (`secret_id` AppRole : 86 jours) ; au-delà, l'état devient « EN RETARD (expire dans N j) », puis « EXPIRÉ ». La dernière ligne compte les secrets bloquants parmi ceux en retard.

« aucune rotation journalisée » dans `--check` signifie seulement que le journal local n'a pas d'entrée pour ce secret (par exemple une rotation antérieure à la création du journal) : renouveler le secret, ou le tracer par `--record` s'il vient d'être renouvelé à la main.

Saisies demandées selon les secrets choisis, puis oubliées à la fin : mot de passe `admin` de Jenkins, mot de passe `admin` d'OpenBao, mot de passe et code TOTP du bot Codeberg concerné, valeur créée à la main. Aucune valeur n'est affichée, écrite sur le disque ni passée en argument de commande ; le journal (`~/.config/rhdemo-rotation/journal.jsonl`) ne contient que des dates et des identifiants.

Conseils : `--dry-run` d'abord, un secret à la fois pour une première rotation, OpenBao déverrouillé et, pour stagingkub, le cluster démarré (contexte `kind-rhdemo`). En cas d'échec, le script annule ce qu'il a déjà fait et le dit ; s'il n'y parvient pas, son message indique quoi comparer.

**Ajouter un secret** : une entrée dans `inventory.yaml` (méthode et cibles existantes, ou procédure manuelle), la valeur dans OpenBao, puis `./rotate-secrets.py --dry-run <id>`.

### Kubeconfigs et certificats

Les deux kubeconfigs de Jenkins sont à rotation automatique (méthode `k8s-sa-token`), sans interruption de la CD : nouveau token créé et vérifié (identité, droits attendus), poussé dans le credential Jenkins, puis anciens tokens supprimés. Cluster démarré et contexte `kind-rhdemo` exigés ; aucun kubeconfig n'est écrit sur le disque. Détail : [SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md](SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md), « Token et kubeconfig ».

```bash
rhDemo/scripts/rotate-secrets.py kubeconfig-stagingkub kubeconfig-stagingkub-infra-upgrader
```

Après la première rotation, supprimer les anciens fichiers `rhDemo/infra/stagingkub/jenkins-kubeconfig/*.yaml` (écrits par les anciennes versions d'`init-stagingkub.sh`, leurs tokens sont alors invalides).

Certificat du Gateway de stagingkub (moitié de `tls-keys`) : le script réutilise un certificat existant, d'où la suppression préalable. Depuis `rhDemo/` :

```bash
rm infra/stagingkub/certs/tls.crt infra/stagingkub/certs/tls.key
infra/stagingkub/scripts/init-stagingkub.sh     # cluster réutilisé : recrée shared-tls-cert
```

Le navigateur redemande une exception (certificat auto-signé, voir [CERTIFICATS_WEB.md](CERTIFICATS_WEB.md)).

Certificat du registry (10 ans, l'autre moitié de `tls-keys`), *procédure non encore éprouvée* :

1. `infra/jenkins-docker/init-registry-certs.sh`, répondre `y` à la régénération ;
2. `sudo cp infra/jenkins-docker/certs/registry/registry.crt /etc/docker/certs.d/localhost:5000/ca.crt` (le démon Docker de l'hôte, utilisé par la CI, s'y fie pour pousser) ; le script conseille ensuite `sudo systemctl restart docker`, qui redémarre tous les conteneurs et **rescelle OpenBao** (déverrouillage à refaire) ;
3. `docker compose restart registry` depuis `infra/jenkins-docker/` (nouvelle clé servie) ;
4. `infra/stagingkub/scripts/init-stagingkub.sh` : recopie le certificat dans le nœud kind, pour que containerd tire les images.

Les agents Jenkins montent `registry.crt` à leur création : rien à faire pour eux. Ne tracer `tls-keys` par `--record` qu'une fois les deux certificats renouvelés.

## Rotation d'urgence (fuite supposée)

Depuis `rhDemo/scripts/`, OpenBao déverrouillé et le cluster stagingkub démarré :

```bash
./rotate-secrets.py --emergency --dry-run      # plan : ordre, tokens et clés qui seraient révoqués
./rotate-secrets.py --emergency                # fuite supposée
./rotate-secrets.py --emergency --compromised  # Jenkins ou le poste compromis
```

Ce que fait le mode urgence, par rapport à une rotation ordinaire :

- **tout le périmètre**, dans l'ordre ci-dessous (exposition Internet, réseau local, puis local, et par criticité ; raisons : [ETUDE_ROTATION_SECRETS.md](etudes/ETUDE_ROTATION_SECRETS.md), §3.3), après une confirmation unique ;
- **révocation avant création** pour les secrets qui se révoquent à part (tokens et clé GPG Codeberg, `secret_id` AppRole, tokens Kubernetes) : mieux vaut une CI cassée qu'un attaquant actif. Sur les comptes bots, **tous** les tokens sont révoqués, y compris ceux qui n'ont pas été créés par le script, sans question. Les mots de passe changés en place (PostgreSQL, Keycloak, Grafana) invalident l'ancien dès le changement ; si l'étape échoue, l'ancien est rétabli et le bilan le signale ;
- **procédures manuelles une à une** : le script affiche la procédure et attend. Répondre `o` une fois faite (elle est tracée), sinon elle part dans les « restent à faire » du bilan. Après le mot de passe `admin` de Jenkins, le script redemande le nouveau ;
- **bilan final** : renouvelés, en échec (à relancer par `rotate-secrets.py <id>`), restant à faire. Code retour 1 s'il reste un échec ou une procédure.

`--compromised` place d'abord les secrets de `emergency_first` de l'inventaire : mot de passe `admin` de Jenkins (redémarrer le conteneur pour couper les sessions, pas seulement recharger JCasC), puis `secret_id` AppRole de Jenkins. Ils donnent accès aux secrets Internet que Jenkins lit dans OpenBao ; sans cela, l'attaquant relirait les nouveaux tokens au fur et à mesure.

Ordre suivi (`--dry-run` affiche la liste exacte) :

1. **Si Jenkins ou le poste sont compromis** (`--compromised`), d'abord : mot de passe `admin` de Jenkins (`jenkins-admin-password`, redémarrage du conteneur pour couper les sessions), puis `rotate-secrets.py openbao-approle-jenkins`.
2. Exposés sur Internet : `rotate-secrets.py ci-bot-forgejo-token renovate-forgejo-token fixcve-forgejo-token renovate-gpg-key`, mots de passe des bots et contrôle du compte personnel (procédures `codeberg-bot-passwords`, `codeberg-personal`), SMTP (`smtp-infomaniak`), session Claude (`claude-subscription`).
3. Exposés sur le réseau local : `rotate-secrets.py stagingkub-oidc-client stagingkub-keycloak-admin stagingkub-test-users stagingkub-rhdemo-db stagingkub-keycloak-db grafana-admin`, clés TLS.
4. Locaux : `secret_id` AppRole restants, mot de passe `admin` d'OpenBao, clé de déverrouillage si elle a pu fuir, clé Cosign, kubeconfigs (`rotate-secrets.py kubeconfig-stagingkub kubeconfig-stagingkub-infra-upgrader`), compte Jenkins `claude`, token SonarQube.

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
