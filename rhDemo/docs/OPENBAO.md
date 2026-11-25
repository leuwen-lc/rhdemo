---
statut: actif
verifie_le: 2026-11-25
sources:
  - rhDemo/infra/jenkins-docker/openbao/
  - rhDemo/infra/jenkins-docker/docker-compose.yml
  - rhDemo/infra/jenkins-docker/Dockerfile.jenkins
  - rhDemo/infra/jenkins-docker/casc/jenkins-casc.yaml
  - rhDemo/infra/stagingkub/external-secrets/
  - rhDemo/infra/stagingkub/scripts/components/install-external-secrets.sh
  - rhDemo/infra/stagingkub/scripts/init-stagingkub.sh
  - rhDemo/infra/stagingkub/scripts/repair-cluster-after-restart.sh
  - rhDemo/scripts/openbao-setup.py
  - rhDemo/scripts/rotation_lib/
  - rhDemo/Jenkinsfile-FixCVE
  - rhDemo/secrets/inventory.yaml
  - rhDemo/Jenkinsfile-CI
  - rhDemo/Jenkinsfile-CD
---

# OpenBao : exploitation

Mise en œuvre de [ETUDE_OPENBAO.md](etudes/ETUDE_OPENBAO.md), qui en donne les raisons. Ce guide décrit l'installation à blanc, l'alimentation initiale des secrets, le déverrouillage et la rotation.

**État** : en service. La migration depuis SOPS est terminée (novembre 2026) : fichiers chiffrés supprimés, valeurs renouvelées, outils de migration retirés (trace dans [log.md](log.md)). Ce qui a été vérifié, et ce qui reste à valider, est listé en fin de document.

## Architecture

```text
 POSTE (utilisateur)                                    KeePassXC : clé de déverrouillage, mot de passe
 ┌──────────────────────────────────────────────┐        admin, clé racine de l'autorité locale
 │ unseal.sh            déverrouillage manuel   │
 │ configure-openbao.sh moteurs, politiques     │  127.0.0.1:8200 (HTTPS, boucle locale seulement)
 │ openbao-setup.py     alimentation initiale   │──────────────────────────────┐
 │ rotate-secrets.py    rotations               │  utilisateur admin           │
 │ rotate-audit.sh      cron hebdomadaire       │  (jeton d'une heure)         │
 └──────────────────────────────────────────────┘                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│  OPENBAO  rhdemo-openbao (docker-compose.yml de jenkins-docker)                           │
│  Raft un nœud (volume rhdemo-openbao-data), TLS par l'autorité locale, scellé au départ   │
│  Journal d'audit (volume rhdemo-openbao-audit, valeurs en HMAC)                           │
│                                                                                           │
│  Données                                  Authentification → politique                    │
│  • kv/jenkins/<credential>                • userpass admin        → admin                 │
│  • kv/stagingkub/{rhdemo,keycloak}        • AppRole jenkins       → lecture kv/jenkins/*  │
│  • kv/stagingkub-tests/users              • AppRole jenkins-cosign→ signature Transit     │
│  • kv/observability/grafana               • Kubernetes eso-stagingkub   → kv/stagingkub/* │
│  • Transit cosign (clé non exportable)    • Kubernetes eso-observability→ kv/observ.../*  │
└───────────────┬───────────────────────────────────────┬───────────────────────────────────┘
                │ https://openbao:8200                  │ https://<IP fixe>:8200
                │ réseau rhdemo-jenkins-network         │ réseau kind (raccordé par
                ▼                                       ▼ repair-cluster-after-restart.sh)
┌──────────────────────────────────────────┐  ┌──────────────────────────────────────────┐
│ JENKINS                                  │  │ CLUSTER KinD stagingkub                  │
│ Contrôleur : plugin HashiCorp Vault,     │  │ External Secrets Operator                │
│  credential openbao-approle ; les        │  │ • SecretStore rhdemo-stagingkub          │
│  credentials « Vault » pointent vers     │  │   → 4 Secrets applicatifs                │
│  kv/jenkins/<id> (CI, Renovate, FixCVE)  │  │ • SecretStore loki-stack                 │
│ Agent, stage de signature (CI) :         │  │   → Secret grafana-admin                 │
│  cosign openbao://cosign (AppRole        │  │ NetworkPolicy : sortie vers l'IP         │
│  jenkins-cosign)                         │  │  d'OpenBao seulement                     │
└──────────────────────────────────────────┘  └──────────────────────────────────────────┘
```

Ephemere ne lit rien dans OpenBao : ses secrets sont tirés au hasard à chaque build (section « Ephemere »).

| Élément | Où | Rôle |
| --- | --- | --- |
| Conteneur `rhdemo-openbao` | `infra/jenkins-docker/docker-compose.yml` | Raft sur un nœud, TLS, journal d'audit ; port publié sur `127.0.0.1:8200` seulement |
| Autorité locale | `infra/jenkins-docker/certs/ca/` (non versionné) | Racine hors ligne (clé chiffrée, rangée dans KeePassXC), intermédiaire qui signe le certificat d'OpenBao (1 an). *Name Constraints* sur les deux : seuls `openbao`, `localhost`, `kind-registry`, `intra.leuwen-lc.fr` (et sous-domaines), `127.0.0.0/8` et `172.16.0.0/12` peuvent être signés |
| Configuration | `openbao/configure-openbao.sh` et `openbao/policies/` | Moteurs, politiques, AppRole, utilisateur `admin`, authentification Kubernetes |
| Jenkins | plugin `hashicorp-vault-plugin`, bloc `unclassified.hashicorpVault` de `jenkins-casc.yaml` | Credentials « Vault » qui pointent vers `kv/jenkins/<id>` : les pipelines les lisent par `withCredentials` comme des credentials ordinaires |
| stagingkub | External Secrets Operator (namespace `external-secrets`), `infra/stagingkub/external-secrets/` | Crée les 4 Secrets applicatifs depuis `kv/stagingkub/*` (rôle `eso-stagingkub`) et le Secret `grafana-admin` de `loki-stack` depuis `kv/observability/grafana` (rôle `eso-observability`, limité à `kv/observability/*`) |
| Poste | `openbao-setup.py`, `rotate-secrets.py` | Alimentation initiale, rotation |

Données (KV v2 monté sur `kv/`) :

| Chemin | Contenu | Lecteur |
| --- | --- | --- |
| `kv/jenkins/<credential>` | `value`, ou `username`/`password` ; dont `fixcve-forgejo-token` et `fixcve-jenkins-api` pour le job `RHDemo-FixCVE` | Jenkins (AppRole `jenkins`) |
| `kv/stagingkub/rhdemo` | `db_password`, `oidc_client_secret` | ESO (rôle Kubernetes `eso-stagingkub`) |
| `kv/stagingkub/keycloak` | `db_password`, `admin_user`, `admin_password` | ESO |
| `kv/stagingkub-tests/users` | utilisateurs de test Keycloak | `init-keycloak-stagingkub.sh` (admin) |
| `kv/observability/grafana` | `admin_user`, `admin_password` de Grafana | ESO de `loki-stack` (rôle Kubernetes `eso-observability`) |
| Transit `cosign-transit/keys/cosign` | clé de signature ECDSA P-256, non exportable | stage de signature (AppRole `jenkins-cosign`) |

Identités et droits : un fichier de politique par identité dans `infra/jenkins-docker/openbao/policies/`. Le jeton root est révoqué après l'installation ; l'administration passe par l'utilisateur `admin` (jeton d'une heure).

## Installation à blanc (dans cet ordre)

Les agents Jenkins montent `certs/ca/root-ca.crt` : **créer l'autorité avant de recharger JCasC ou de redémarrer Jenkins**, sinon les agents ne démarrent plus.

Depuis `rhDemo/infra/jenkins-docker/` :

1. `openbao/init-local-ca.sh ca` : racine et intermédiaire, avec leurs *Name Constraints* (ajouter un nom interne plus tard impose de recréer l'autorité). Ranger `certs/ca/root-ca.key` (chiffrée) et sa phrase de passe dans KeePassXC, puis `shred -u` la clé.
2. `openbao/init-local-ca.sh openbao` : certificat d'OpenBao. L'IP fixe d'OpenBao sur le réseau Docker `kind` doit y figurer : si le cluster KinD n'existe pas encore, refaire cette étape après l'étape 10 et redémarrer OpenBao (`install-external-secrets.sh` le signale).
3. `docker compose up -d openbao`
4. `openbao/configure-openbao.sh init` : copier la clé de déverrouillage et le jeton root dans KeePassXC (et la clé sur papier). Rien n'est écrit sur le disque. Le jeton root n'y reste que le temps de l'installation : il est révoqué à l'étape 11.
5. `openbao/unseal.sh`, puis `openbao/configure-openbao.sh base` (jeton root ; choisir le mot de passe de l'utilisateur `admin`, à ranger dans KeePassXC).
6. `./start-jenkins.sh` : construit le contrôleur (plugin, autorité dans le truststore Java). Recharger JCasC.
7. Credentials Jenkins, depuis `rhDemo/scripts/` :
   - `./openbao-setup.py jenkins-approle` : credential `openbao-approle`, seul accès de Jenkins à OpenBao ;
   - `./openbao-setup.py jenkins` : pour chaque credential de Renovate, de fixcve-auto et des notifications, valeur écrite dans `kv/jenkins/<id>` et credential Jenkins de même identifiant créé en référence OpenBao. Les tokens Codeberg et la clé GPG sont émis directement sur Codeberg (mot de passe et TOTP des bots demandés) ; les autres valeurs sont demandées (token GitHub, Docker Hub, adresse de notification, token API du compte Jenkins `claude` pour `fixcve-jenkins-api`).
   - Critère : un cycle `RHDemo-Renovate` vert, lectures visibles dans le journal d'audit.
8. Cosign : `openbao/configure-openbao.sh cosign` (écrit la clé publique dans `certs/cosign/cosign-transit.pub`), créer le credential **Secret file** `cosign-public-key-transit` avec ce fichier (un Secret text tient sur une ligne et casserait le PEM), puis `./openbao-setup.py cosign-approle`.
9. fixcve-auto : rien de plus côté OpenBao, ses deux credentials propres sont créés à l'étape 7 (`nvd-api-key`, `ossindex-credentials` et `notification-email` sont partagés avec la CI) ; job `RHDemo-FixCVE` dans JCasC ([FIXCVE_AUTO.md](FIXCVE_AUTO.md), « Installation »).
10. stagingkub : `./openbao-setup.py stagingkub` **avant le premier déploiement** (PostgreSQL ne prend son mot de passe qu'à l'initialisation de sa base, Keycloak son administrateur au premier démarrage). Les valeurs sont générées, jamais saisies. Puis `infra/stagingkub/scripts/init-stagingkub.sh` (authentification Kubernetes d'OpenBao, ESO, `ExternalSecret`), le premier déploiement, et `init-keycloak-stagingkub.sh`. Sur un cluster existant : `openbao/configure-openbao.sh kubernetes` suivi de `infra/stagingkub/scripts/components/install-external-secrets.sh`. La CD lit les `ExternalSecret` grâce à `infra/stagingkub/rbac/jenkins-role.yaml`. Pour l'observabilité, `./openbao-setup.py observability` (admin de Grafana) avant `install-external-secrets.sh`, qui crée aussi le Secret `grafana-admin` de `loki-stack`.
11. `openbao/configure-openbao.sh revoke-root`, puis supprimer le jeton root de KeePassXC : révoqué, il ne sert plus, et `generate-root` en recrée un depuis la clé de déverrouillage (« Jeton root ponctuel »).

Toutes les commandes de `openbao-setup.py` sont idempotentes : une valeur déjà présente dans OpenBao n'est jamais écrasée (la renouveler : `rotate-secrets.py`).

## Déverrouillage

OpenBao redémarre **scellé** après un redémarrage du poste, du démon Docker ou du conteneur (dont un `docker compose up` après une mise à jour d'image). Tant qu'il l'est, les pipelines qui lisent un credential OpenBao (dont `RHDemo-FixCVE`), la signature Cosign et ESO échouent ou attendent.

```bash
rhDemo/infra/jenkins-docker/openbao/unseal.sh   # coller la clé depuis KeePassXC
```

La clé n'est jamais passée en argument (visible dans `ps`). `unseal.sh` raccorde ensuite OpenBao au réseau `kind` avec son IP fixe s'il l'a perdu (conteneur recréé, par exemple au redémarrage de la stack Jenkins) ; dans ce cas, il force aussi la revalidation des `SecretStore` d'ESO et la resynchronisation des `ExternalSecret`, sans quoi la CD refuse de déployer jusqu'à ce qu'ESO réessaie de lui-même. `repair-cluster-after-restart.sh` fait le même raccordement et rappelle l'état scellé, mais ne déverrouille jamais. Le healthcheck Docker du conteneur est `unhealthy` tant qu'il est scellé. Raisons du choix manuel : [ETUDE_OPENBAO.md](etudes/ETUDE_OPENBAO.md) §5.

## Journal d'audit

Chaque requête à OpenBao est journalisée (bloc `audit` de `openbao/config.hcl`) dans `/openbao/logs/audit.log`, volume `rhdemo-openbao-audit` : une ligne JSON par requête et par réponse, avec l'heure (UTC), le chemin, l'identité (`approle` et nom du rôle, `userpass-admin`, `kubernetes`…) et l'erreur éventuelle. Les valeurs lues et les jetons sont remplacés par des HMAC : le journal ne contient aucun secret en clair. Lecture depuis le poste (pas besoin d'OpenBao déverrouillé) :

```bash
# Lectures de kv/jenkins/* depuis une heure donnée : heure, chemin, identité, résultat
docker exec rhdemo-openbao cat /openbao/logs/audit.log | jq -r 'select(.type=="response"
  and (.request.path|startswith("kv/data/jenkins/")) and .time > "2026-11-22T12:45")
  | [.time[0:19], .request.path, .auth.display_name, (.error // "ok")] | @tsv'
# Connexions refusées ou en erreur
docker exec rhdemo-openbao cat /openbao/logs/audit.log | jq -r 'select(.type=="response" and .error)
  | [.time[0:19], .request.path, .error] | @tsv' | tail -20
```

Adapter le préfixe (`kv/data/stagingkub/`, `auth/approle/login`, `cosign-transit/`) et l'heure. Les semaines précédentes sont dans les archives : remplacer `cat /openbao/logs/audit.log` par `sh -c 'zcat /openbao/logs/audit-*.log.gz'`.

**Rotation** (une dizaine de Mo par jour d'activité des pipelines) : `openbao/rotate-audit.sh`, chaque dimanche à 3 h 30 par la crontab de l'utilisateur du poste :

```cron
30 3 * * 0 ~/git/repository/rhDemo/infra/jenkins-docker/openbao/rotate-audit.sh >> ~/.cache/rhdemo-openbao-audit-rotate.log 2>&1
```

Le script renomme `audit.log` en `audit-<horodatage>.log`, envoie SIGHUP à OpenBao, qui rouvre un fichier neuf (aucune ligne perdue), compresse l'archive (12 Mo deviennent 0,6 Mo) et en garde 12 dans le même volume (`KEEP`) ; rien en dessous de 1 Mo (`MIN_BYTES`). Il ne demande ni jeton ni déverrouillage. Si OpenBao ne rouvre pas le fichier, l'archive reste non compressée et le script le signale dans son journal.

## Rotation

Tout passe par `rotate-secrets.py` (inventaire `secrets/inventory.yaml`). Tâches récurrentes, usage du script, rotation d'urgence et accès aux secrets : [ROTATION_SECRETS.md](ROTATION_SECRETS.md). Ce que fait chaque méthode automatisée :

| Secret | Commande | Effet |
| --- | --- | --- |
| Tokens Codeberg, clé GPG Renovate | `rotate-secrets.py <id>` | nouvelle valeur écrite dans `kv/jenkins/…` |
| `secret_id` AppRole (Jenkins, Cosign) | `rotate-secrets.py openbao-approle-jenkins` (etc.) | nouveau `secret_id` vérifié par une connexion, propagé, anciens détruits ; validité 100 jours, période 90 jours |
| Mots de passe PostgreSQL de stagingkub | `rotate-secrets.py stagingkub-rhdemo-db stagingkub-keycloak-db` | KV, synchronisation ESO forcée, `ALTER ROLE` dans le pod (mot de passe sur l'entrée standard de `psql`), redémarrage des pods ; retour arrière automatique si l'`ALTER ROLE` échoue |
| Secret du client OIDC `RHDemo` | `rotate-secrets.py stagingkub-oidc-client` | KV, synchronisation ESO forcée (le Secret est un fichier généré par gabarit), valeur imposée dans Keycloak par l'API d'administration, redémarrage de `rhdemo-app` ; retour arrière dans Keycloak et le KV en cas d'échec |
| Administrateur Keycloak, utilisateurs de test | `rotate-secrets.py stagingkub-keycloak-admin stagingkub-test-users` | KV d'abord, puis API Keycloak et connexion de vérification avec la nouvelle valeur ; sinon retour à l'ancienne des deux côtés. `KEYCLOAK_ADMIN_PASSWORD` ne servant qu'au premier démarrage, le changer dans OpenBao seul ne suffirait pas. Utilisateurs de test : 12 caractères saisissables (lettres, chiffres, `-_.!@%+=?`), longueur réglable dans l'inventaire |
| Admin de Grafana | `rotate-secrets.py grafana-admin` | KV, synchronisation ESO forcée, redémarrage de Grafana (sans stockage persistant, il reprend le mot de passe du Secret), connexion de vérification par son API ; retour à l'ancien mot de passe en cas d'échec |
| Clé Cosign | procédure manuelle de `cosign-key` | nouvelle version de la clé Transit, nouvelle clé publique dans `cosign-public-key-transit` ; les images signées avant la rotation ne sont plus déployables (relancer la CI) |

`rotate-secrets.py --check` signale un `secret_id` dont la période est dépassée, avant son expiration.

Les rotations Keycloak passent par un `kubectl port-forward` vers le pod Keycloak (comme `init-keycloak-stagingkub.sh`), avec les identifiants d'administration lus dans `kv/stagingkub/keycloak`. Aucune valeur n'est saisie, et aucune ne passe en argument de commande. Les nouvelles valeurs se relisent dans OpenBao (`bao kv get`).

## Sauvegarde et restauration

- Instantané : `docker exec -e BAO_TOKEN rhdemo-openbao bao operator raft snapshot save /openbao/logs/snapshot.snap` puis `docker cp` hors du conteneur. L'instantané reste chiffré : sans la clé de déverrouillage, il est inutilisable.
- Restauration (à tester une fois) : `bao operator raft snapshot restore -force`, sur un OpenBao initialisé, puis déverrouillage avec la clé correspondant à l'instantané.
- Journal des rotations : à chaque instantané, copier aussi `~/.config/rhdemo-rotation/journal.jsonl` à côté (`install -m 600 ~/.config/rhdemo-rotation/journal.jsonl <dossier>/journal-$(date +%F).jsonl`). C'est la seule trace des dates de rotation lue par `rotate-secrets.py --check` (la plupart des rotations ne passent pas par OpenBao, et l'audit n'est gardé qu'environ 12 semaines). Il ne contient aucune valeur, seulement des dates et des identifiants. Restauration : le remettre en place (répertoire en 700, fichier en 600) sans écraser un journal plus récent, puis retracer par `--record` les rotations postérieures à la copie.

## Ephemere

Plus de secrets stockés : le stage « Génération Secrets ephemere » de `Jenkinsfile-CI` tire des valeurs aléatoires à chaque build (environnement détruit en fin de build) et les écrit dans un fichier de variables lu par Docker Compose, `rhDemoInitKeycloak`, Selenium et ZAP. Les identifiants des utilisateurs de test sont fixes (`rhdemo-admin`, `rhdemo-maj`, `rhdemo-consult`), leurs mots de passe aléatoires.

## Jeton root ponctuel

Le jeton root est révoqué en fin d'installation. Seul `configure-openbao.sh base` l'exige (il crée l'utilisateur `admin`) : il ne sert que pour réinstaller ou modifier ce socle, par exemple la politique `admin`.

```bash
rhDemo/infra/jenkins-docker/openbao/configure-openbao.sh generate-root   # clé de déverrouillage
rhDemo/infra/jenkins-docker/openbao/configure-openbao.sh revoke-root     # après l'opération
```

`generate-root` enchaîne les étapes de `bao operator generate-root` et déchiffre le jeton lui-même : l'OTP n'apparaît ni à l'écran ni en argument. La clé de déverrouillage permet donc de recréer un jeton root : la protéger au même niveau (KeePassXC et papier).

## Vérifié et à valider

Vérifié le 2026-11-21 sur un OpenBao 2.7.2 et un Jenkins jetables (supprimés ensuite) :

- démarrage avec la configuration du dépôt (Raft, TLS par l'autorité locale, audit, capacités Docker réduites) ; `configure-openbao.sh` `init`, `base`, `cosign`, `secret-id` ; connexion `admin` ;
- connexion AppRole par `curl`, droits limités (lecture de `kv/jenkins/*` refusée à `fixcve`, export de la clé Transit refusé à `jenkins-cosign`) ; signature et vérification cosign par `openbao://cosign` (cosign lit l'autorité dans `VAULT_CACERT`, pas `BAO_CACERT`) ;
- bloc JCasC, autorité dans le truststore Java, création et **remplacement en place** des credentials par l'API (le type peut changer ; une relecture de `config.xml` masque les secrets, d'où l'absence de sauvegarde par ce moyen), pipeline qui lit des valeurs OpenBao par `withCredentials` (masquées), rotation du `secret_id` de Jenkins puis pipeline toujours vert ;
- lecture des credentials de fixcve-auto, et passage sauté proprement quand OpenBao est scellé ;
- *Name Constraints* de l'autorité : certificats d'OpenBao, de la Gateway et du registry acceptés ; certificats émis pour `codeberg.org`, `intra.leuwen-lc.fr.evil.com` ou une IP publique refusés par OpenSSL, Java (JDK de l'image Jenkins) et Go (client `bao`). Sans elles, la clé de l'intermédiaire, sur le disque jusqu'à l'étape 5, permettrait d'intercepter toute connexion des clients qui font confiance à la racine (dont le contrôleur Jenkins vers Codeberg) ;
- `configure-openbao.sh generate-root` (OpenBao jetable en mode dev) : jeton de politique `root` obtenu, clé fausse refusée et génération annulée ;
- tests unitaires : `scripts/tests/test_openbao.py`, `scripts/tests/test_keycloak_rotation.py`.

Vérifié le 2026-11-22 sur le vrai Jenkins (étape 7, faite ce jour-là sur ce poste : jusque-là, seuls Cosign et fixcve lisaient OpenBao, les credentials des pipelines étaient restés des credentials Jenkins ordinaires) :

- `openbao-setup.py jenkins-approle` puis `openbao-setup.py jenkins` : `openbao-approle` créé, les 8 credentials de `kv/jenkins/*` remplacés par des références OpenBao ;
- `RHDemo-Renovate` #181 vert, journal d'audit : lectures de `ci-bot-forgejo-token`, `renovate-forgejo-token`, `renovate-gpg-key`, `renovate-github-token`, `dockerhub-renovate-readonly` et `notification-email` par l'AppRole `jenkins`, sans erreur ; `RHDemo-FixCVE` (`status`, `DRY_RUN`) : lectures de `fixcve-forgejo-token` et `fixcve-jenkins-api`.

Vérifié le 2026-11-21 sur le vrai cluster stagingkub (installation de l'étape 10) :

- ESO 2.15.0 installé par `install-external-secrets.sh` ; authentification Kubernetes (JWT du client, `system:auth-delegator`) acceptée par OpenBao ; `SecretStore` prêt ;
- NetworkPolicy de sortie d'ESO vers l'IP fixe d'OpenBao (`ipBlock`) fonctionnelle avec Cilium ;
- les 4 Secrets recréés par ESO, avec ESO pour propriétaire, aux valeurs identiques aux anciennes (gabarit de `rhdemo-app-secrets` compris) ; pods applicatifs inchangés.

Vérifié le 2026-11-21 par les pipelines de la branche :

- `RHDemo-CI` verte : secrets d'ephemere générés à chaque build (sans SOPS), image signée par la clé Transit (`openbao://cosign`, AppRole `jenkins-cosign`) ;
- `RHDemo-CD` verte : signature vérifiée avec `cosign-public-key-transit`, `ExternalSecret` prêts.

Vérifié le 2026-11-21 sur le vrai cluster : rotations PostgreSQL (`ALTER ROLE` dans le pod) et Keycloak (client OIDC, administrateur, utilisateurs de test) des valeurs héritées de SOPS.

À valider au premier déploiement :

- entrée du webhook d'ESO depuis l'API Server (`allow-apiserver-to-webhook`) : sollicitée seulement à la création ou modification d'un `ExternalSecret`/`SecretStore`, passée sans erreur à l'installation ;
- installation à blanc complète : `openbao-setup.py stagingkub` et `fixcve` ne sont couverts que par les tests unitaires (l'instance en service avait déjà ses valeurs).
