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

# 3. Démarrer Jenkins
./start-jenkins.sh
```

Jenkins est accessible sur **http://localhost:8080**.

---

## Credentials Jenkins pour exécuter Jenkinsfile-CI

À créer dans **Manage Jenkins → Credentials → (global) → Add Credentials**.

### Obligatoires

| ID | Kind | Comment obtenir |
|----|------|-----------------|
| `sops-age-key` | Secret file | Clé age pour déchiffrer `secrets-ephemere.yml` — voir `rhDemo/docs/SOPS_SETUP.md` |
| `jenkins-sonar-token` | Secret text | http://localhost:9020 → My Account → Security → Generate Token |
| `nvd-api-key` | Secret text | https://nvd.nist.gov/developers/request-an-api-key |
| `cosign-private-key` | Secret file | Fichier `cosign.key` généré ci-dessous (pipeline CI) |
| `cosign-password` | Secret text | Mot de passe saisi lors de la génération Cosign (pipeline CI) |
| `cosign-public-key` | Secret file | Fichier `cosign.pub` généré ci-dessous (pipeline CD) |

### Optionnels

| ID | Kind | Usage |
|----|------|-------|
| `ossindex-credentials` | Username/password | Accélère les téléchargements OWASP Dependency-Check |
| `smtp-credentials` (nom au choix) | **Username with password** (pas Secret text, sinon invisible dans la liste déroulante SMTP) | Notifications email `RHDemo-CI` — plugin email-ext, à configurer entièrement à la main dans Jenkins UI (pas via JCasC), voir `README.md` → section Email |

### Pour Jenkinsfile-Renovate (pipeline `RHDemo-Renovate`, automerge des PRs de dépendances)

Réutilise `nvd-api-key` et `ossindex-credentials` déjà créés ci-dessus. En plus, à créer :

| ID | Kind | Comment obtenir |
|----|------|-----------------|
| `ci-bot-forgejo-token` | Secret text | Token du compte Codeberg bot dédié `rhdemo-ci-bot` (collaborateur **Write** du repo, pas Admin), scopes `repository` + `issue`. Sert à lister/synchroniser/merger les PRs et poster les commentaires |
| `renovate-forgejo-token` | Secret text | Token du compte bot Renovate lui-même (distinct de `rhdemo-ci-bot`), scopes `repository` + `issue` + **`user`** (obligatoire, sinon `renovate` échoue avec `Authentication failure`) |
| `renovate-gpg-key` | Secret text | Clé GPG privée dédiée à la signature des commits Renovate, exportée en base64 : `gpg --export-secret-keys <KEY_ID> \| base64 -w0` |
| `renovate-github-token` | Secret text | Token GitHub read-only (dépôts publics) pour les lookups de changelogs/release notes des dépendances hébergées sur GitHub |

> Pourquoi deux comptes bot distincts (`rhdemo-ci-bot` et le bot Renovate) et pourquoi `renovate-forgejo-token` ne peut pas être remplacé par `ci-bot-forgejo-token` : voir `docs/RENOVATE_AUTOMERGE_CI.md` sections 1 et « Credentials Jenkins nécessaires ».

### Pour la mise à jour en place de l'infra stagingkub (`RHDemo-Stagingkub-Upgrade-Deploy`)

Déclenché par `RHDemo-Renovate` pour les composants Cilium/NGF/kube-prometheus-stack/Loki/Promtail/Grafana. À créer :

| ID | Kind | Comment obtenir |
|----|------|-----------------|
| `kubeconfig-stagingkub-infra-upgrader` | Secret file | Fichier `rhDemo/infra/stagingkub/jenkins-kubeconfig/kubeconfig-jenkins-infra-upgrader-rbac.yaml`, généré automatiquement par `./scripts/init-stagingkub.sh` (ServiceAccount dédié `jenkins-infra-upgrader`, distinct de `kubeconfig-stagingkub`/`jenkins-deployer` utilisé par `RHDemo-CD`) |

> Détail de l'étude et du RBAC : `docs/STAGINGKUB_REBUILD_PIPELINE.md` et `infra/stagingkub/rbac/README.md`.

### Secrets SOPS (environnement ephemere)

1. Installez SOPS et créez une clé age (voir `rhDemo/docs/SOPS_SETUP.md`)
2. Créez `secrets-ephemere.yml` depuis le template `secrets-ephemere.yml.template`
3. Chiffrez-le avec SOPS

### Clés Cosign (à générer une seule fois)

```bash
cosign generate-key-pair
# → cosign.key  (clé privée — ne pas commiter)
# → cosign.pub  (clé publique)
```

---

## Opérations courantes

```bash
# Démarrer
./start-jenkins.sh

# Arrêter
docker compose stop

# Relancer après modification de jenkins-casc.yaml
docker compose restart jenkins

# Reset complet (perte de données)
docker compose down -v && ./start-jenkins.sh --clean-plugins
```

> Pour l'architecture complète, la configuration détaillée et le dépannage : voir `README.md`
