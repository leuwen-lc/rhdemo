# Projet école — preuve de concept

rhDemo est le module principal du projet école - preuve de concept décrit dans le README à la racine du repository GIT, merci de vous y reporter.

Vous pouvez également consulter de la documentation sur divers sujets ayant nécessité un travail spécifique dans le sous-répertoire [docs](docs/).

## 📚 Documentation

### Pipelines CI/CD

**IMPORTANT** : Le projet utilise désormais **deux pipelines Jenkins séparés** :

- **[Jenkinsfile-CI](Jenkinsfile-CI)** : Pipeline d'Intégration Continue (build, tests, publish)
- **[Jenkinsfile-CD](Jenkinsfile-CD)** : Pipeline de Déploiement Continu (deploy to stagingkub)

📖 **Consultez la documentation complète** : [docs/PIPELINES_CI_CD.md](docs/PIPELINES_CI_CD.md)

⚠️ **Note** : Le fichier `Jenkinsfile` original est déprécié et sera supprimé prochainement.

### Autres documentations

- [Base de données](DATABASE.md) - Schéma et gestion de la base PostgreSQL
- [Configuration Jenkins](bin/JENKINS_SETUP.md) - Installation et configuration de Jenkins
- Voir le répertoire [docs/](docs/) pour plus de documentation

## Licence
- Licence Apache 2.0
