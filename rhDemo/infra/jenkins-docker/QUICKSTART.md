# Démarrage Rapide Jenkins CI/CD — RHDemo

## Installation (à faire une seule fois)

```bash
cd rhDemo/infra/jenkins-docker

# 1. Certificats TLS du registry Docker
./init-registry-certs.sh
sudo mkdir -p /etc/docker/certs.d/localhost:5000
sudo cp certs/registry/registry.crt /etc/docker/certs.d/localhost:5000/ca.crt
sudo systemctl restart docker

# 2. Configurer les mots de passe Jenkins
cp .env.example .env
nano .env   # Définir JENKINS_ADMIN_PASSWORD et JENKINS_CLAUDE_PASSWORD

# 3. Démarrer Jenkins (installation neuve : créer d'abord l'autorité locale et
#    OpenBao, étapes 1 à 5 de docs/OPENBAO.md ; voir docs/INSTALLATION_COMPLETE.md)
./start-jenkins.sh
```

Jenkins est accessible sur **http://localhost:8080**.

---

## Credentials Jenkins pour exécuter Jenkinsfile-CI

À créer dans **Manage Jenkins → Credentials → (global) → Add Credentials**.

### Obligatoires

| ID | Kind | Comment obtenir |
|----|------|-----------------|
| `jenkins-sonar-token` | Secret text | `docker start rhdemo-sonarqube-db rhdemo-sonarqube` (SonarQube est arrêté hors CI), puis http://localhost:9020 → My Account → Security → Generate Token |
| `nvd-api-key` | Secret text | https://nvd.nist.gov/developers/request-an-api-key |
| `openbao-cosign-approle` | Username with password | Créé par `rhDemo/scripts/openbao-setup.py cosign-approle` (signature par la clé Transit d'OpenBao, pipeline CI) |
| `cosign-public-key-transit` | Secret file | Fichier `certs/cosign/cosign-transit.pub` écrit par `openbao/configure-openbao.sh cosign` (pipeline CD) |

### Optionnels

| ID | Kind | Usage |
|----|------|-------|
| `ossindex-credentials` | Username/password | Accélère les téléchargements OWASP Dependency-Check |
| `smtp-credentials` (nom au choix) | **Username with password** (pas Secret text, sinon invisible dans la liste déroulante SMTP) | Notifications email `RHDemo-CI` — plugin email-ext, à configurer entièrement à la main dans Jenkins UI (pas via JCasC), voir `README.md` → section Email |

### Pour Jenkinsfile-Renovate (pipeline `RHDemo-Renovate`, automerge des PRs de dépendances)

Réutilise `nvd-api-key` déjà créé ci-dessus. En plus, à créer :

| ID | Kind | Comment obtenir |
|----|------|-----------------|
| `ci-bot-forgejo-token` | Secret text | Token du compte Codeberg bot dédié `cibot-leuwen-lc` (collaborateur **Write** du repo, pas Admin), scopes `repository` + `issue`. Sert à lister/synchroniser/merger les PRs et poster les commentaires |
| `renovate-forgejo-token` | Secret text | Token du compte bot Renovate lui-même (distinct de `cibot-leuwen-lc`), portées `write:repository`, `write:issue`, **`read:user`** (obligatoire, sinon `renovate` échoue avec `Authentication failure`) et `read:organization` |
| `renovate-gpg-key` | Secret text | Clé GPG privée dédiée à la signature des commits Renovate, exportée en base64 : `gpg --export-secret-keys <KEY_ID> \| base64 -w0` |
| `renovate-github-token` | Secret text | Token GitHub read-only (dépôts publics) pour les lookups de changelogs/release notes des dépendances hébergées sur GitHub |
| `dockerhub-renovate-readonly` | Username with password | Identifiant Docker Hub (Docker ID, pas l'e-mail) et jeton personnel de portée « Public Repo Read-only », avec date d'expiration. Sans lui, Renovate n'a pas les dates de publication des grosses images et le stage de scan échoue |

> Pourquoi deux comptes bot distincts (`cibot-leuwen-lc` et le bot Renovate) et pourquoi `renovate-forgejo-token` ne peut pas être remplacé par `ci-bot-forgejo-token` : voir `docs/RENOVATE_AUTOMERGE_CI.md`, section « Comptes et credentials ».

### Pour fixcve-auto (`RHDemo-FixCVE`)

Réutilise `nvd-api-key`. Credentials `fixcve-forgejo-token` (token du bot `fixcvebot-leuwen-lc`) et `fixcve-jenkins-api` (compte `claude` et son token API), créés en références OpenBao par `rhDemo/scripts/openbao-setup.py jenkins fixcve-forgejo-token fixcve-jenkins-api` : voir `docs/FIXCVE_AUTO.md`, « Installation ».

### Pour la mise à jour en place de l'infra stagingkub (`RHDemo-Stagingkub-Upgrade-Deploy`)

Déclenché par `RHDemo-Renovate` pour les composants Cilium/NGF/kube-prometheus-stack/Loki/Alloy/Grafana. À créer :

| ID | Kind | Comment obtenir |
|----|------|-----------------|
| `kubeconfig-stagingkub-infra-upgrader` | Secret file | Fichier `rhDemo/infra/stagingkub/jenkins-kubeconfig/kubeconfig-jenkins-infra-upgrader-rbac.yaml`, généré automatiquement par `./scripts/init-stagingkub.sh` (ServiceAccount dédié `jenkins-infra-upgrader`, distinct de `kubeconfig-stagingkub`/`jenkins-deployer` utilisé par `RHDemo-CD`) |

> Détail de l'étude et du RBAC : `docs/STAGINGKUB_REBUILD_PIPELINE.md` et `infra/stagingkub/rbac/README.md`.

### Secrets

- **ephemere** : rien à créer, `Jenkinsfile-CI` génère des valeurs aléatoires à chaque build.
- **OpenBao** (Renovate, notifications, Cosign, stagingkub) : suivre `rhDemo/docs/OPENBAO.md`.

---

## Opérations courantes

```bash
# Démarrer
./start-jenkins.sh

# Arrêter
docker compose stop

# Après modification de casc/jenkins-casc.yaml : Manage Jenkins → Configuration as Code
# → « Reload existing configuration », ou à défaut :
docker compose restart jenkins

# Reset complet (perte de données)
docker compose down -v && ./start-jenkins.sh --clean-plugins
```

> Pour l'architecture complète, la configuration détaillée et le dépannage : voir `README.md`
