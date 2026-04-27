# Guide de Démarrage Rapide - Jenkins CI/CD pour RHDemo

## Démarrage en 5 minutes

```bash
# 1. Aller dans le répertoire jenkins-docker
cd rhDemo/infra/jenkins-docker

# 2. Générer les certificats TLS pour le registry Docker (HTTPS)
./init-registry-certs.sh

# 3. Configurer Docker daemon pour faire confiance au certificat
sudo mkdir -p /etc/docker/certs.d/localhost:5000
sudo cp certs/registry/registry.crt /etc/docker/certs.d/localhost:5000/ca.crt
sudo systemctl restart docker

# 4. Configurer les secrets
cp .env.example .env
nano .env  # Éditer avec vos valeurs

# 5. Builder et Démarrer Jenkins
./start-jenkins.sh
```

> **Note** : Les étapes 2-3 (certificats) ne sont nécessaires qu'une seule fois.
> Le script `start-jenkins.sh` vous guidera si les certificats sont manquants.
> Les agents sont éphémères : créés à la demande par le Docker Plugin, aucun secret agent à configurer.

## Fichiers de configuration

| Fichier | Description | Action requise |
|---------|-------------|----------------|
| `.env` | Secrets et variables | **A configurer** |
| `certs/registry/` | Certificats TLS registry | **A générer** (`./init-registry-certs.sh`) |
| `docker-compose.yml` | Services Docker (controller + agent) | Pret |
| `Dockerfile.jenkins` | Image controller (pilotage) | Pret |
| `Dockerfile.agent` | Image agent (outils de build) | Pret |
| `plugins.txt` | Plugins auto-installés | Pret |
| `jenkins-casc.yaml` | Configuration JCasC (controller + agent) | Pret |

## Configuration minimale du .env

> **⚠️ OBLIGATOIRE avant tout `docker compose up`**  
> Le démarrage échouera si `JENKINS_ADMIN_PASSWORD` ou `JENKINS_CLAUDE_PASSWORD` sont absents ou vides dans `.env`.

```env
# OBLIGATOIRE — Remplacer par des mots de passe forts
JENKINS_ADMIN_PASSWORD=VotreMotDePasseSecurise
JENKINS_CLAUDE_PASSWORD=AutreMotDePasseSecurise
```

## Créer les pipelines RHDemo

Ils sont créés automatiquement par jenkins-casc.yaml si non existants au démarrage de Jenkins.

## Gestion des secrets avec SOPS pour exécuter la chaine Jenkinsfile-CI

- Installez SOPS et une clé age (voir dans rhDemo/docs/SOPS_SETUP.md)
- Fabriquez un fichier de secrets de l'environnement de ephemere à partir du template secrets-ephemere.yml.template
- chiffrez le avec SOPS sous secrets-ephemere.yml (celui stocké sur git nécessiterait ma clé privée pour être déchiffré)

## Secrets à positionner dans les credentials Jenkins pour pouvoir exécuter la chaine Jenkinsfile-CI

Dans l'interface d'administration Jenkins, créez les credentials Jenkins suivants :

- sous l'id "sops-age-key" votre fichier contenant la paire de clés age nécessaire au déchiffrage de secrets-ephemere.yml
- sous l'id "jenkins-sonar-token" la clé d'échange avec sonarQube (à générer préalablement en se connectant à sonarQube http://localhost:9020 My account/security/generate tokens
- sous l'id "nvd-api-key" et "ossindex-credentials" deux clés à obtenir pour accélérer les téléchargement des dépendances et CVE liées à OWASP Dependency Check (voir le README.md)
- (facultatif) sous l'id "mail.credentials" un compte sur un serveur de mails permettant l'envoi SMTP

## Génération des clés Cosign et credentials Jenkins pour la signature d'images

Le pipeline CI signe l'image Docker produite (étape `🔏 Signature Cosign`) et le pipeline CD vérifie cette signature avant tout déploiement.

**1. Générer la paire de clés Cosign (à faire une seule fois sur l'hôte) :**

```bash
# Installer cosign si besoin
# https://docs.sigstore.dev/cosign/system_config/installation/
cosign generate-key-pair
# → Saisir et confirmer un mot de passe (COSIGN_PASSWORD)
# → Produit : cosign.key (clé privée) et cosign.pub (clé publique)
```

**2. Créer les 3 credentials Jenkins** (Manage Jenkins → Manage Credentials → (global) → Add Credentials) :

| ID credential Jenkins   | Kind         | Contenu                          | Pipeline |
|-------------------------|--------------|----------------------------------|---------|
| `cosign-private-key`    | Secret file  | Fichier `cosign.key`             | CI      |
| `cosign-password`       | Secret text  | Mot de passe saisi à la génération | CI    |
| `cosign-public-key`     | Secret file  | Fichier `cosign.pub`             | CD      |

> **Sécurité** : conservez `cosign.key` hors du dépôt Git. Le fichier `cosign.pub` peut être versionné si souhaité.