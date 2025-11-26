# Installation du plugin OWASP Dependency-Check sur Jenkins

Guide d'installation et de configuration du plugin Jenkins OWASP Dependency-Check pour l'administrateur Jenkins.

## Prérequis

- Jenkins 2.361.4 ou supérieur
- Java 11 ou supérieur installé sur Jenkins
- Accès administrateur à Jenkins

## Étape 1 : Installer le plugin

### Option A : Via l'interface Jenkins (recommandé)

1. Se connecter à Jenkins avec un compte administrateur
2. Naviguer vers **Manage Jenkins** → **Manage Plugins**
3. Cliquer sur l'onglet **Available plugins**
4. Dans la barre de recherche, taper : `OWASP Dependency-Check Plugin`
5. Cocher la case du plugin **OWASP Dependency-Check Plugin**
6. Cliquer sur **Install without restart** (ou **Download now and install after restart**)

### Option B : Via Jenkins CLI

```bash
# Télécharger Jenkins CLI
wget http://localhost:8080/jnlpJars/jenkins-cli.jar

# Installer le plugin
java -jar jenkins-cli.jar -s http://localhost:8080/ \
    -auth admin:admin_password \
    install-plugin dependency-check-jenkins-plugin

# Redémarrer Jenkins
java -jar jenkins-cli.jar -s http://localhost:8080/ \
    -auth admin:admin_password \
    safe-restart
```

### Option C : Via Docker (si Jenkins en container)

```bash
# Se connecter au container Jenkins
docker exec -it jenkins bash

# Installer le plugin
jenkins-plugin-cli --plugins dependency-check-jenkins-plugin

# Redémarrer Jenkins
exit
docker restart jenkins
```

## Étape 2 : Configurer l'outil Dependency-Check

### 2.1 Accéder à la configuration des outils

1. **Manage Jenkins** → **Global Tool Configuration**
2. Descendre jusqu'à la section **Dependency-Check**
3. Cliquer sur **Add Dependency-Check**

### 2.2 Configuration de l'installation

Remplir les champs suivants :

- **Name** : `dependency-check-9.2.0` (ce nom doit correspondre à celui utilisé dans le Jenkinsfile)
- **Install automatically** : ✅ Cocher cette case
- **Install from** : Sélectionner **Install from GitHub.com**
- **Version** : Sélectionner la dernière version stable (recommandé : **9.2.0** ou supérieur)

![Configuration Global Tool](screenshots/jenkins-global-tool-config.png)

Cliquer sur **Save** en bas de la page.

## Étape 3 : Obtenir une clé API NVD (optionnel mais recommandé)

### Pourquoi une clé API ?

Sans clé API, les requêtes vers NVD sont limitées à :
- **10 requêtes par 30 secondes**
- **Risque de timeout** lors du premier scan

Avec une clé API :
- **50 requêtes par 30 secondes**
- **Scans plus rapides et fiables**
- **Gratuit**

### Obtenir la clé API

1. Aller sur : https://nvd.nist.gov/developers/request-an-api-key
2. Renseigner votre **email professionnel**
3. Cocher **"I am not a robot"**
4. Cliquer sur **Request an API Key**
5. Vérifier votre boîte mail et confirmer la demande
6. Vous recevrez la clé API dans un second email (format : `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

### Stocker la clé dans Jenkins Credentials

1. **Manage Jenkins** → **Manage Credentials**
2. Cliquer sur **(global)** sous **Stores scoped to Jenkins**
3. Cliquer sur **Add Credentials**
4. Remplir le formulaire :
   - **Kind** : Secret text
   - **Scope** : Global
   - **Secret** : Coller votre clé API NVD (ex: `12345678-1234-1234-1234-123456789abc`)
   - **ID** : `nvd-api-key` (IMPORTANT : ce nom doit correspondre au Jenkinsfile)
   - **Description** : `NVD API Key for OWASP Dependency-Check`
5. Cliquer sur **Create**

![Credentials Configuration](screenshots/jenkins-credentials-nvd.png)

## Étape 4 : Configurer les permissions de répertoire

Le plugin télécharge la base NVD dans `JENKINS_HOME/dependency-check-data/`.

### Vérifier l'espace disque disponible

```bash
# Se connecter au serveur Jenkins
ssh jenkins-server

# Vérifier l'espace disque
df -h /var/jenkins_home

# La base NVD complète fait environ 2-3 GB
# Recommandé : au moins 5 GB d'espace libre
```

### Créer le répertoire de cache (optionnel)

```bash
# Se connecter au serveur Jenkins
cd /var/jenkins_home

# Créer le répertoire
mkdir -p dependency-check-data

# Définir les permissions (utilisateur jenkins)
chown -R jenkins:jenkins dependency-check-data
chmod 755 dependency-check-data
```

## Étape 5 : Modifier le Jenkinsfile pour utiliser la clé API

Si vous avez configuré une clé API NVD, modifiez le Jenkinsfile :

```groovy
stage('🔒 Analyse Sécurité Dépendances (OWASP)') {
    environment {
        // Charger la clé API NVD depuis les credentials Jenkins
        NVD_API_KEY = credentials('nvd-api-key')
    }
    steps {
        script {
            echo '▶ Analyse des vulnérabilités des dépendances (OWASP Dependency-Check)...'
            echo '   ⚠️  Le build échouera si vulnérabilités CVSS ≥ 7.0 (High/Critical)'
            echo '   📌 Utilisation du plugin Jenkins OWASP Dependency-Check'
        }

        dependencyCheck(
            additionalArguments: """
                --scan rhDemo/target/classes
                --scan rhDemo/pom.xml
                --project rhDemo
                --format HTML
                --format JSON
                --format XML
                --out rhDemo/target
                --failOnCVSS 7.0
                --enableExperimental
                --nvdApiKey \${NVD_API_KEY}
                --nvdValidForHours 24
                --nvdMaxRetryCount 5
            """,
            odcInstallation: 'dependency-check-9.2.0',
            stopBuild: false
        )

        dependencyCheckPublisher(
            pattern: '**/dependency-check-report.xml',
            failedTotalCritical: 0,
            failedTotalHigh: 0,
            unstableTotalCritical: 0,
            unstableTotalHigh: 0,
            usePreviousBuildAsReference: true
        )
    }
}
```

## Étape 6 : Tester l'installation

### 6.1 Lancer un build de test

1. Aller dans le pipeline **rhdemo-pipeline**
2. Cliquer sur **Build Now**
3. Suivre les logs du build
4. Vérifier que le stage **🔒 Analyse Sécurité Dépendances (OWASP)** s'exécute

### 6.2 Vérifier les logs

Dans les logs du build, vous devriez voir :

```
[Pipeline] dependencyCheck
Updating dependency-check...
Downloading NVD data feeds...
Analyzing dependencies...
Dependency-Check execution successful
```

### 6.3 Vérifier le rapport

1. Aller dans la page du build
2. Cliquer sur l'onglet **Dependency-Check Results**
3. Vérifier que le rapport s'affiche correctement

## Troubleshooting

### Erreur : "No tool named dependency-check-9.2.0 found"

**Cause** : L'outil n'est pas configuré dans Global Tool Configuration.

**Solution** :
1. **Manage Jenkins** → **Global Tool Configuration**
2. Section **Dependency-Check** → **Add Dependency-Check**
3. Name : `dependency-check-9.2.0` (exactement comme dans le Jenkinsfile)
4. Cocher **Install automatically**

### Erreur : "NVD API rate limit exceeded"

**Cause** : Trop de requêtes vers NVD sans clé API.

**Solutions** :
1. Configurer une clé API NVD (voir Étape 3)
2. Ou augmenter `--nvdValidForHours` pour espacer les mises à jour :
   ```groovy
   --nvdValidForHours 168  // 1 semaine au lieu de 24h
   ```

### Timeout au premier build

**Cause** : Le premier scan télécharge toute la base NVD (~2-3 GB).

**Solutions** :

**Option 1 : Augmenter le timeout Jenkins**

Dans le Jenkinsfile, ajouter au début du stage :
```groovy
stage('🔒 Analyse Sécurité Dépendances (OWASP)') {
    options {
        timeout(time: 60, unit: 'MINUTES')
    }
    // ...
}
```

**Option 2 : Pré-charger le cache manuellement**

```bash
# Se connecter au serveur Jenkins
ssh jenkins-server

# Devenir l'utilisateur jenkins
sudo su - jenkins

# Télécharger la base NVD
cd /var/jenkins_home/tools/dependency-check-9.2.0/bin
./dependency-check.sh --updateonly --nvdApiKey YOUR_API_KEY
```

### Erreur : "Failed to parse NVD data - SAFETY"

**Cause** : Ancienne version du plugin incompatible avec CVSS v4.0.

**Solution** :
1. **Manage Jenkins** → **Manage Plugins**
2. Onglet **Installed plugins**
3. Rechercher **OWASP Dependency-Check Plugin**
4. Cliquer sur **Update** si disponible
5. Ou mettre à jour vers version 9.2.0+ dans Global Tool Configuration

### Le rapport ne s'affiche pas

**Cause** : Le fichier XML de rapport n'est pas trouvé.

**Solution** :
Vérifier le pattern dans `dependencyCheckPublisher` :
```groovy
dependencyCheckPublisher(
    pattern: '**/dependency-check-report.xml',  // Vérifier que ce fichier existe
    // ...
)
```

Vérifier dans les logs :
```bash
# Dans les logs du build
ls -la rhDemo/target/dependency-check-report.xml
```

### Espace disque insuffisant

**Cause** : Le cache NVD prend beaucoup d'espace.

**Solution** :
```bash
# Nettoyer le cache ancien
rm -rf /var/jenkins_home/dependency-check-data/*

# Ou limiter la taille du cache
cd /var/jenkins_home/dependency-check-data
find . -type f -mtime +30 -delete  # Supprimer fichiers > 30 jours
```

## Maintenance

### Mise à jour du plugin

1. **Manage Jenkins** → **Manage Plugins**
2. Onglet **Updates**
3. Rechercher **OWASP Dependency-Check Plugin**
4. Cocher et cliquer sur **Download now and install after restart**

### Mise à jour de l'outil

1. **Manage Jenkins** → **Global Tool Configuration**
2. Section **Dependency-Check**
3. Modifier la **Version** vers une version plus récente
4. Sauvegarder

### Nettoyage du cache NVD

**Manuel** :
```bash
rm -rf /var/jenkins_home/dependency-check-data/*
```

**Automatique (via script Groovy)** :

1. **Manage Jenkins** → **Script Console**
2. Exécuter :
```groovy
def dataDir = new File(Jenkins.instance.rootDir, 'dependency-check-data')
if (dataDir.exists()) {
    dataDir.deleteDir()
    println "Cache NVD supprimé : ${dataDir}"
} else {
    println "Répertoire non trouvé : ${dataDir}"
}
```

## Sécurité

### Protéger la clé API NVD

- ✅ **OUI** : Stocker dans Jenkins Credentials
- ❌ **NON** : Hard-coder dans le Jenkinsfile
- ❌ **NON** : Stocker en clair dans un fichier

### Permissions Jenkins

Seuls les administrateurs doivent avoir accès à :
- **Manage Jenkins** → **Manage Credentials** (lecture des secrets)
- **Manage Jenkins** → **Global Tool Configuration** (modification des outils)

## Références

- Plugin Jenkins : https://plugins.jenkins.io/dependency-check-jenkins-plugin/
- Documentation OWASP : https://jeremylong.github.io/DependencyCheck/
- NVD API : https://nvd.nist.gov/developers
- CVSS Calculator : https://nvd.nist.gov/vuln-metrics/cvss

## Support

En cas de problème :
1. Consulter les logs Jenkins : **Manage Jenkins** → **System Log**
2. Activer les logs de debug dans le Jenkinsfile :
   ```groovy
   dependencyCheck(
       additionalArguments: '''
           --log /tmp/dependency-check.log
           --verbose
       ''',
       // ...
   )
   ```
3. Consulter la documentation complète : [OWASP_JENKINS_PLUGIN.md](OWASP_JENKINS_PLUGIN.md)
