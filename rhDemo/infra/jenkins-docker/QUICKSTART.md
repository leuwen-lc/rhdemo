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

# 5. Builder et Démarrer Jenkins (controller + agent)
./start-jenkins.sh

# 6. Configurer le secret de l'agent
#    - Ouvrir http://localhost:8080
#    - Login: admin / (pwd défini dans .env)
#    - Aller dans Manage Jenkins > Nodes > builder
#    - Copier le secret affiché
#    - Mettre à jour JENKINS_SECRET dans .env
#    - Redémarrer l'agent : docker-compose up -d jenkins-agent
```

> **Note** : Les étapes 2-3 (certificats) ne sont nécessaires qu'une seule fois.
> Le script `start-jenkins.sh` vous guidera si les certificats sont manquants.
> L'étape 6 (secret agent) n'est nécessaire qu'au premier démarrage.

## Fichiers de configuration

| Fichier | Description | Action requise |
|---------|-------------|----------------|
| `.env` | Secrets et variables (dont JENKINS_SECRET) | **A configurer** |
| `certs/registry/` | Certificats TLS registry | **A générer** (`./init-registry-certs.sh`) |
| `docker-compose.yml` | Services Docker (controller + agent) | Pret |
| `Dockerfile.jenkins` | Image controller (pilotage) | Pret |
| `Dockerfile.agent` | Image agent (outils de build) | Pret |
| `plugins.txt` | Plugins auto-installés | Pret |
| `jenkins-casc.yaml` | Configuration JCasC (controller + agent) | Pret |

## Configuration minimale du .env

```env
# OBLIGATOIRE
JENKINS_ADMIN_PASSWORD=VotreMotDePasseSecurise

# OBLIGATOIRE - Secret de l'agent (voir étape 6 ci-dessus)
JENKINS_SECRET=<secret-copié-depuis-jenkins-ui>
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