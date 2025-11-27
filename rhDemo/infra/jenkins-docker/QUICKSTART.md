# 🚀 Guide de Démarrage Rapide - Jenkins CI/CD pour RHDemo

## ⚡ Démarrage en 3 minutes

```bash
# 1. Aller dans le répertoire infra
cd rhDemo/infra

# 2. Configurer les secrets
cp .env.example .env
nano .env  # Éditer avec vos valeurs

# 3. Démarrer Jenkins
./start-jenkins.sh

# 4. Accéder à Jenkins
# Ouvrir http://localhost:8080
# Login: admin / admin123 (défini dans .env)
```

## 📋 Fichiers de configuration

| Fichier | Description | Action requise |
|---------|-------------|----------------|
| `.env` | Secrets et variables | ✏️ **À configurer** |
| `docker-compose.yml` | Services Docker | ✅ Prêt |
| `Dockerfile.jenkins` | Image personnalisée | ✅ Prêt |
| `plugins.txt` | Plugins auto-installés | ✅ Prêt |
| `jenkins-casc.yaml` | Configuration JCasC | ✅ Prêt |

## 🔐 Configuration minimale du .env

```env
# OBLIGATOIRE
JENKINS_ADMIN_PASSWORD=VotreMotDePasseSecurise

# Optionnel - SonarQube
SONAR_TOKEN=votre-token-sonarqube
```

**Note** : La clé NVD API pour OWASP Dependency-Check doit être configurée manuellement dans Jenkins (voir README.md section "Configuration NVD API Key")


## 🎯 Créer un pipeline RHDemo

### Option 1 : Interface Web

1. **http://localhost:8080** → New Item
2. **Nom**: `rhdemo-api`
3. **Type**: Pipeline
4. **Pipeline**:
   - Definition: `Pipeline script from SCM`
   - SCM: `Git`
   - Repository: `https://github.com/leuwen-lc/rhdemo.git`
   - Script Path: `Jenkinsfile`
5. **Save** → **Build Now**

### Option 2 : Automatique (JCasC)

Décommenter la section `jobs:` dans `jenkins-casc.yaml` avant de démarrer.

## 🧪 Tester l'installation

```bash
# Test complet
./test-jenkins.sh

# Vérifications manuelles
docker-compose ps                           # Conteneurs actifs
docker-compose logs -f jenkins              # Logs Jenkins
docker-compose exec jenkins docker ps       # Docker-in-Docker
```

## 🔧 Commandes essentielles

```bash
# Démarrer
./start-jenkins.sh
docker-compose up -d

# Arrêter
docker-compose stop
docker-compose down

# Redémarrer
docker-compose restart jenkins

# Logs
docker-compose logs -f jenkins

# Accès shell
docker-compose exec jenkins bash
```

## 📊 Vérifier que tout fonctionne

✅ **Jenkins Web UI** : http://localhost:8080  
✅ **Docker Registry** : http://localhost:5000  
✅ **Healthcheck** : `docker inspect rhdemo-jenkins | grep Health`  
✅ **Plugins** : Jenkins → Manage Jenkins → Manage Plugins  
✅ **Docker-in-Docker** : `docker-compose exec jenkins docker ps`  
✅ **Maven** : `docker-compose exec jenkins mvn -version`  
✅ **Java** : `docker-compose exec jenkins java -version`  

## ⚠️ Problèmes courants

### Port 8080 déjà utilisé

```bash
# Changer le port dans docker-compose.yml
ports:
  - "8081:8080"  # Utiliser 8081
```

### Docker permission denied

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Jenkins ne démarre pas

```bash
# Voir les logs
docker-compose logs jenkins

# Reconstruire l'image
docker-compose build --no-cache jenkins
docker-compose up -d --force-recreate
```

## 🔒 Sécurité

⚠️ **CHANGEZ** le mot de passe admin immédiatement !  
⚠️ **NE COMMITEZ PAS** le fichier `.env`  
⚠️ **UTILISEZ HTTPS** en production (nginx à ajouter)  
⚠️ **SAUVEGARDEZ** régulièrement `/var/jenkins_home`  

## 📚 Documentation complète

- **README.md** : Guide détaillé
- **ARCHITECTURE.txt** : Schéma de l'infrastructure
- **Jenkinsfile** (racine) : Pipeline RHDemo complet

## 🆘 Support

1. Vérifier `docker-compose logs jenkins`
2. Lire `README.md`
3. Tester avec `./test-jenkins.sh`
4. Consulter https://www.jenkins.io/doc/

---

**🎉 C'est tout ! Jenkins est prêt pour exécuter le pipeline RHDemo avec support Docker-in-Docker.**
