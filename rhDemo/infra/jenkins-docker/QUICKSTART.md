# 🚀 Guide de Démarrage Rapide - Jenkins CI/CD pour RHDemo

## ⚡ Démarrage en 5 minutes

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

# 6. Accéder à Jenkins
# Ouvrir http://localhost:8080
# Login: admin / admin123 (défini dans .env)
```

> **Note** : Les étapes 2-3 (certificats) ne sont nécessaires qu'une seule fois.
> Le script `start-jenkins.sh` vous guidera si les certificats sont manquants.

## 📋 Fichiers de configuration

| Fichier | Description | Action requise |
|---------|-------------|----------------|
| `.env` | Secrets et variables | ✏️ **À configurer** |
| `certs/registry/` | Certificats TLS registry | ✏️ **À générer** (`./init-registry-certs.sh`) |
| `docker-compose.yml` | Services Docker | ✅ Prêt |
| `Dockerfile.jenkins` | Image personnalisée | ✅ Prêt |
| `plugins.txt` | Plugins auto-installés | ✅ Prêt |
| `jenkins-casc.yaml` | Configuration JCasC | ✅ Prêt |

## 🔐 Configuration minimale du .env

```env
# OBLIGATOIRE
JENKINS_ADMIN_PASSWORD=VotreMotDePasseSecurise

## 🎯 Créer les pipeline RHDemo
Ils sont créés automatiquement par jenkins-casc.yaml si non existants au démarrage de Jenkins

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