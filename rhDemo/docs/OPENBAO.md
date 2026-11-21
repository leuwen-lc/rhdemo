---
statut: actif
verifie_le: 2026-11-21
sources:
  - rhDemo/infra/jenkins-docker/openbao/
  - rhDemo/infra/jenkins-docker/docker-compose.yml
  - rhDemo/infra/jenkins-docker/Dockerfile.jenkins
  - rhDemo/infra/jenkins-docker/casc/jenkins-casc.yaml
  - rhDemo/infra/stagingkub/external-secrets/
  - rhDemo/infra/stagingkub/scripts/components/install-external-secrets.sh
  - rhDemo/infra/stagingkub/scripts/init-stagingkub.sh
  - rhDemo/infra/stagingkub/scripts/repair-cluster-after-restart.sh
  - rhDemo/scripts/openbao-migrate.py
  - rhDemo/scripts/rotation_lib/
  - rhDemo/scripts/fixcve-auto-poll.sh
  - rhDemo/secrets/inventory.yaml
  - rhDemo/Jenkinsfile-CI
  - rhDemo/Jenkinsfile-CD
---

# OpenBao : exploitation

Mise en œuvre des étapes 1 à 4 de [ETUDE_OPENBAO.md](ETUDE_OPENBAO.md), qui en donne les raisons. Ce guide décrit l'installation, le déverrouillage, la migration et la rotation.

**État** : code en place sur la branche `evolution_openbao`. Ce qui a été vérifié sur un OpenBao et un Jenkins jetables, et ce qui reste à valider au premier déploiement, est listé en fin de document.

## Architecture

| Élément | Où | Rôle |
| --- | --- | --- |
| Conteneur `rhdemo-openbao` | `infra/jenkins-docker/docker-compose.yml` | Raft sur un nœud, TLS, journal d'audit ; port publié sur `127.0.0.1:8200` seulement |
| Autorité locale | `infra/jenkins-docker/certs/ca/` (non versionné) | Racine hors ligne (clé chiffrée, rangée dans KeePassXC), intermédiaire qui signe le certificat d'OpenBao (1 an). *Name Constraints* sur les deux : seuls `openbao`, `localhost`, `kind-registry`, `intra.leuwen-lc.fr` (et sous-domaines), `127.0.0.0/8` et `172.16.0.0/12` peuvent être signés |
| Configuration | `openbao/configure-openbao.sh` et `openbao/policies/` | Moteurs, politiques, AppRole, utilisateur `admin`, authentification Kubernetes |
| Jenkins | plugin `hashicorp-vault-plugin`, bloc `unclassified.hashicorpVault` de `jenkins-casc.yaml` | Credentials « Vault » du même identifiant que les anciens : `withCredentials` inchangé |
| stagingkub | External Secrets Operator (namespace `external-secrets`), `infra/stagingkub/external-secrets/` | Crée les 4 Secrets applicatifs depuis `kv/stagingkub/*` |
| Poste | `openbao-migrate.py`, `rotate-secrets.py`, `fixcve-auto-poll.sh` | Migration, rotation, lecture des secrets de fixcve-auto |

Données (KV v2 monté sur `kv/`) :

| Chemin | Contenu | Lecteur |
| --- | --- | --- |
| `kv/jenkins/<credential>` | `value`, ou `username`/`password` | Jenkins (AppRole `jenkins`) |
| `kv/fixcve/{jenkins,codeberg,nvd}` | tokens de fixcve-auto, clé NVD | poller (AppRole `fixcve`) |
| `kv/stagingkub/rhdemo` | `db_password`, `oidc_client_secret` | ESO (rôle Kubernetes `eso-stagingkub`) |
| `kv/stagingkub/keycloak` | `db_password`, `admin_user`, `admin_password` | ESO |
| `kv/stagingkub-tests/users` | utilisateurs de test Keycloak | `init-keycloak-stagingkub.sh` (admin) |
| Transit `cosign-transit/keys/cosign` | clé de signature ECDSA P-256, non exportable | stage de signature (AppRole `jenkins-cosign`) |

Identités et droits : un fichier de politique par identité dans `infra/jenkins-docker/openbao/policies/`. Le jeton root est révoqué après l'installation ; l'administration passe par l'utilisateur `admin` (jeton d'une heure).

## Installation (dans cet ordre)

Les agents Jenkins montent `certs/ca/root-ca.crt` : **créer l'autorité avant de recharger JCasC ou de redémarrer Jenkins depuis cette branche**, sinon les agents ne démarrent plus.

Depuis `rhDemo/infra/jenkins-docker/` :

1. `openbao/init-local-ca.sh ca` : racine et intermédiaire, avec leurs *Name Constraints* (ajouter un nom interne plus tard impose de recréer l'autorité). Ranger `certs/ca/root-ca.key` (chiffrée) et sa phrase de passe dans KeePassXC, puis `shred -u` la clé.
2. `openbao/init-local-ca.sh openbao` : certificat d'OpenBao. Le lancer **après** la création du cluster KinD pour que l'IP fixe d'OpenBao sur le réseau `kind` figure dans le certificat (sinon le refaire plus tard et redémarrer OpenBao).
3. `docker compose up -d openbao`
4. `openbao/configure-openbao.sh init` : copier la clé de déverrouillage et le jeton root dans KeePassXC (et la clé sur papier). Rien n'est écrit sur le disque.
5. `openbao/unseal.sh`, puis `openbao/configure-openbao.sh base` (jeton root ; choisir le mot de passe de l'utilisateur `admin`, à ranger dans KeePassXC).
6. `./start-jenkins.sh` : reconstruit le contrôleur (plugin, autorité dans le truststore Java). Recharger JCasC.
7. Migration Jenkins (étape 1), depuis `rhDemo/scripts/` :
   - `./openbao-migrate.py jenkins-approle` : crée le credential `openbao-approle` ;
   - `./openbao-migrate.py jenkins` : pour chaque credential de Renovate et des notifications, écrit la valeur dans `kv/jenkins/<id>` puis remplace le credential par une référence OpenBao du même identifiant. Les tokens Codeberg et la clé GPG ne sont pas recopiés : ils sont renouvelés directement vers OpenBao. Les autres valeurs sont demandées (copier depuis leur source : GitHub, Docker Hub, adresse de notification).
   - Critère : un cycle `RHDemo-Renovate` vert, lectures visibles dans le journal d'audit.
8. fixcve-auto (étape 1 bis) : `./openbao-migrate.py fixcve`, puis `./fixcve-install.sh --trust` (scripts modifiés). Après un cycle réussi, supprimer `~/.config/rhdemo-fixcve/credentials.sops.yaml`.
9. Cosign (étape 2) : `openbao/configure-openbao.sh cosign` (écrit la clé publique dans `certs/cosign/cosign-transit.pub`), créer le credential **Secret file** `cosign-public-key-transit` avec ce fichier (un Secret text tient sur une ligne et casserait le PEM), puis `./openbao-migrate.py cosign-approle`. Après une CD verte sur une image signée par Transit, supprimer `cosign-private-key` et `cosign-password` ; garder `cosign-public-key` tant que des images signées par l'ancienne clé restent déployables.
10. stagingkub (étape 3) : `./openbao-migrate.py stagingkub` (copie depuis `secrets-stagingkub.yml`), puis `infra/stagingkub/scripts/init-stagingkub.sh` ou, sur un cluster existant, `openbao/configure-openbao.sh kubernetes` suivi de `infra/stagingkub/scripts/components/install-external-secrets.sh`. Appliquer aussi `infra/stagingkub/rbac/jenkins-role.yaml` (lecture des `ExternalSecret` par la CD).
11. Renouveler les valeurs copiées depuis SOPS, présentes chiffrées dans l'historique Git public (étape 4) : `./rotate-secrets.py stagingkub-rhdemo-db stagingkub-keycloak-db stagingkub-oidc-client stagingkub-keycloak-admin stagingkub-test-users` (`--dry-run` d'abord pour contrôler l'accès).
12. `openbao/configure-openbao.sh revoke-root`.

## Déverrouillage

OpenBao redémarre **scellé** après un redémarrage du poste, du démon Docker ou du conteneur (dont un `docker compose up` après une mise à jour d'image). Tant qu'il l'est, les pipelines qui lisent un credential OpenBao, la signature Cosign, ESO et fixcve-auto échouent ou attendent.

```bash
rhDemo/infra/jenkins-docker/openbao/unseal.sh   # coller la clé depuis KeePassXC
```

La clé n'est jamais passée en argument (visible dans `ps`). `repair-cluster-after-restart.sh` rappelle l'état scellé et raccorde OpenBao au réseau `kind`, mais ne déverrouille jamais. Le healthcheck Docker du conteneur est `unhealthy` tant qu'il est scellé. Raisons du choix manuel : [ETUDE_OPENBAO.md](ETUDE_OPENBAO.md) §5.

## Rotation

Tout passe par `rotate-secrets.py` (inventaire `secrets/inventory.yaml`) :

| Secret | Commande | Effet |
| --- | --- | --- |
| Tokens Codeberg, clé GPG Renovate | `rotate-secrets.py <id>` | nouvelle valeur écrite dans `kv/jenkins/…` ou `kv/fixcve/codeberg` |
| `secret_id` AppRole (Jenkins, Cosign, fixcve) | `rotate-secrets.py openbao-approle-jenkins` (etc.) | nouveau `secret_id` vérifié par une connexion, propagé, anciens détruits ; validité 100 jours, période 90 jours |
| Mots de passe PostgreSQL de stagingkub | `rotate-secrets.py stagingkub-rhdemo-db stagingkub-keycloak-db` | KV, synchronisation ESO forcée, `ALTER ROLE` dans le pod (mot de passe sur l'entrée standard de `psql`), redémarrage des pods ; retour arrière automatique si l'`ALTER ROLE` échoue |
| Secret du client OIDC `RHDemo` | `rotate-secrets.py stagingkub-oidc-client` | KV, synchronisation ESO forcée (le Secret est un fichier généré par gabarit), valeur imposée dans Keycloak par l'API d'administration, redémarrage de `rhdemo-app` ; retour arrière dans Keycloak et le KV en cas d'échec |
| Administrateur Keycloak, utilisateurs de test | `rotate-secrets.py stagingkub-keycloak-admin stagingkub-test-users` | KV d'abord, puis API Keycloak et connexion de vérification avec la nouvelle valeur ; sinon retour à l'ancienne des deux côtés. `KEYCLOAK_ADMIN_PASSWORD` ne servant qu'au premier démarrage, le changer dans OpenBao seul ne suffirait pas. Utilisateurs de test : 12 caractères saisissables (lettres, chiffres, `-_.!@%+=?`), longueur réglable dans l'inventaire |
| Clé Cosign | procédure manuelle de `cosign-key` | nouvelle version de la clé Transit, nouvelle clé publique dans `cosign-public-key-transit` |

`rotate-secrets.py --check` signale un `secret_id` dont la période est dépassée, avant son expiration.

Les rotations Keycloak passent par un `kubectl port-forward` vers le pod Keycloak (comme `init-keycloak-stagingkub.sh`), avec les identifiants d'administration lus dans `kv/stagingkub/keycloak`. Aucune valeur n'est saisie, et aucune ne passe en argument de commande. Les nouvelles valeurs se relisent dans OpenBao (`bao kv get`).

## Sauvegarde et restauration

- Instantané : `docker exec -e BAO_TOKEN rhdemo-openbao bao operator raft snapshot save /openbao/logs/snapshot.snap` puis `docker cp` hors du conteneur. L'instantané reste chiffré : sans la clé de déverrouillage, il est inutilisable.
- Restauration (à tester une fois) : `bao operator raft snapshot restore -force`, sur un OpenBao initialisé, puis déverrouillage avec la clé correspondant à l'instantané.

## Ephemere

Plus de secrets stockés : le stage « Génération Secrets ephemere » de `Jenkinsfile-CI` tire des valeurs aléatoires à chaque build (environnement détruit en fin de build) et les écrit dans le même fichier de variables qu'avant, lu par Docker Compose, `rhDemoInitKeycloak`, Selenium et ZAP. Les identifiants des utilisateurs de test sont fixes (`rhdemo-admin`, `rhdemo-maj`, `rhdemo-consult`), leurs mots de passe aléatoires. `secrets-ephemere.yml` et le credential `sops-age-key` ne servent plus et seront supprimés à l'abandon de SOPS.

## Retour arrière

Chaque étape se défait seule :

- **Jenkins** : recréer le credential d'origine (même identifiant, type « Secret text »…) dans l'interface ; les pipelines n'ont pas changé.
- **fixcve-auto** : supprimer `openbao-approle.json` ; le poller revient à `credentials.sops.yaml` s'il existe encore.
- **Cosign** : revenir à la version précédente du stage de signature de `Jenkinsfile-CI` (Git) ; la CD vérifie toujours avec `cosign-public-key`.
- **ephemere** : revenir à la version précédente du stage de secrets de `Jenkinsfile-CI` (Git) ; `secrets-ephemere.yml` et `sops-age-key` sont encore là.
- **stagingkub** : supprimer les `ExternalSecret` (les Secrets sont supprimés avec eux), recréer les Secrets à la main et revenir à la version précédente de la CD.

## Vérifié et à valider

Vérifié le 2026-11-21 sur un OpenBao 2.7.2 et un Jenkins jetables (supprimés ensuite) :

- démarrage avec la configuration du dépôt (Raft, TLS par l'autorité locale, audit, capacités Docker réduites) ; `configure-openbao.sh` `init`, `base`, `cosign`, `secret-id` ; connexion `admin` ;
- connexion AppRole par `curl`, droits limités (lecture de `kv/jenkins/*` refusée à `fixcve`, export de la clé Transit refusé à `jenkins-cosign`) ; signature et vérification cosign par `openbao://cosign` (cosign lit l'autorité dans `VAULT_CACERT`, pas `BAO_CACERT`) ;
- bloc JCasC, autorité dans le truststore Java, création et **remplacement en place** des credentials par l'API (le type peut changer ; une relecture de `config.xml` masque les secrets, d'où l'absence de sauvegarde par ce moyen), pipeline qui lit des valeurs OpenBao par `withCredentials` (masquées), rotation du `secret_id` de Jenkins puis pipeline toujours vert ;
- lecture des credentials de fixcve-auto, et passage sauté proprement quand OpenBao est scellé ;
- *Name Constraints* de l'autorité : certificats d'OpenBao, de la Gateway et du registry acceptés ; certificats émis pour `codeberg.org`, `intra.leuwen-lc.fr.evil.com` ou une IP publique refusés par OpenSSL, Java (JDK de l'image Jenkins) et Go (client `bao`). Sans elles, la clé de l'intermédiaire, sur le disque jusqu'à l'étape 5, permettrait d'intercepter toute connexion des clients qui font confiance à la racine (dont le contrôleur Jenkins vers Codeberg) ;
- tests unitaires : `scripts/tests/test_openbao.py`.

Vérifié le 2026-11-21 sur le vrai cluster stagingkub (installation de l'étape 10) :

- ESO 2.15.0 installé par `install-external-secrets.sh` ; authentification Kubernetes (JWT du client, `system:auth-delegator`) acceptée par OpenBao ; `SecretStore` prêt ;
- NetworkPolicy de sortie d'ESO vers l'IP fixe d'OpenBao (`ipBlock`) fonctionnelle avec Cilium ;
- les 4 Secrets recréés par ESO, avec ESO pour propriétaire, aux valeurs identiques aux anciennes (gabarit de `rhdemo-app-secrets` compris) ; pods applicatifs inchangés.

Vérifié le 2026-11-21 par les pipelines de la branche :

- `RHDemo-CI` verte : secrets d'ephemere générés à chaque build (sans SOPS), image signée par la clé Transit (`openbao://cosign`, AppRole `jenkins-cosign`) ;
- `RHDemo-CD` verte : signature vérifiée avec `cosign-public-key-transit` (repli sur l'ancienne clé non sollicité), `ExternalSecret` prêts.

À valider au premier déploiement :

- entrée du webhook d'ESO depuis l'API Server (`allow-apiserver-to-webhook`) : sollicitée seulement à la création ou modification d'un `ExternalSecret`/`SecretStore`, passée sans erreur à l'installation ;
- rotation PostgreSQL sur le vrai cluster (authentification locale de `psql` dans le pod) ;
- rotations Keycloak sur le vrai cluster (seul le port-forward et l'accès aux realms `master` et `RHDemo` ont été vérifiés).
