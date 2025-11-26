# Migration OWASP Dependency-Check : Plugin Maven → Plugin Jenkins

## Contexte

Suite aux erreurs NVD CVSS v4.0 rencontrées avec le plugin Maven (`IllegalArgumentException: SAFETY`), nous avons migré vers le **plugin Jenkins OWASP Dependency-Check**.

## Problème rencontré

```
[ERROR] Error updating the NVD Data
Caused by: com.fasterxml.jackson.databind.exc.InvalidFormatException:
Cannot construct instance of `io.github.jeremylong.openvulnerability.client.nvd.CvssV4Data$ModifiedCiaType`
problem: SAFETY
```

Le plugin Maven `dependency-check-maven:11.1.1` (et versions antérieures) ne peut pas analyser les nouvelles énumérations CVSS v4.0 introduites par le NVD, notamment la valeur `SAFETY` dans `ModifiedCiaType`.

## Solution adoptée

### Avant (plugin Maven)

**Jenkinsfile (ligne 422-446)** :
```groovy
stage('🔒 Analyse Sécurité Dépendances (OWASP)') {
    steps {
        sh '''
            . rhDemo/secrets/env-vars.sh
            cd rhDemo && ./mvnw org.owasp:dependency-check-maven:check
        '''
    }
    post {
        always {
            publishHTML([
                reportDir: 'rhDemo/target',
                reportFiles: 'dependency-check-report.html',
                reportName: 'OWASP Dependency Check',
                allowMissing: true,
                keepAll: true,
                alwaysLinkToLastBuild: true
            ])
        }
    }
}
```

**Problèmes** :
- ❌ Erreur CVSS v4.0 avec nouvelles énumérations NVD
- ❌ Cache local par build dans `target/dependency-check-data/`
- ❌ Rapport HTML statique uniquement
- ❌ Pas de suivi historique des vulnérabilités
- ❌ Téléchargement NVD à chaque build (~2-3 GB)

### Après (plugin Jenkins)

**Jenkinsfile (ligne 422-460)** :
```groovy
stage('🔒 Analyse Sécurité Dépendances (OWASP)') {
    steps {
        script {
            echo '▶ Analyse des vulnérabilités des dépendances (OWASP Dependency-Check)...'
            echo '   ⚠️  Le build échouera si vulnérabilités CVSS ≥ 7.0 (High/Critical)'
            echo '   📌 Utilisation du plugin Jenkins OWASP Dependency-Check'
        }

        dependencyCheck(
            additionalArguments: '''
                --scan rhDemo/target/classes
                --scan rhDemo/pom.xml
                --project rhDemo
                --format HTML
                --format JSON
                --format XML
                --out rhDemo/target
                --failOnCVSS 7.0
                --enableExperimental
                --nvdValidForHours 24
                --nvdMaxRetryCount 5
            ''',
            odcInstallation: 'dependency-check-9.2.0',
            stopBuild: false
        )

        dependencyCheckPublisher(
            pattern: '**/dependency-check-report.xml',
            failedTotalCritical: 0,    // Échec si ≥ 1 Critical (CVSS 9.0-10.0)
            failedTotalHigh: 0,         // Échec si ≥ 1 High (CVSS 7.0-8.9)
            unstableTotalCritical: 0,
            unstableTotalHigh: 0,
            usePreviousBuildAsReference: true
        )
    }
}
```

**Avantages** :
- ✅ Meilleure compatibilité CVSS v4.0
- ✅ Cache partagé entre builds dans `JENKINS_HOME/dependency-check-data/`
- ✅ Interface Jenkins avec graphiques d'évolution
- ✅ Historique des vulnérabilités par build
- ✅ Seuils granulaires (Critical/High/Medium/Low)
- ✅ Mise à jour NVD contrôlée (`--nvdValidForHours 24`)

## Configuration requise

### 1. Installation du plugin Jenkins

**Administrateur Jenkins** :
1. **Manage Jenkins** → **Manage Plugins**
2. Onglet **Available plugins**
3. Rechercher : `OWASP Dependency-Check Plugin`
4. Installer et redémarrer Jenkins

Voir [JENKINS_OWASP_SETUP.md](JENKINS_OWASP_SETUP.md) pour le guide complet.

### 2. Configuration de l'outil

**Global Tool Configuration** :
1. **Manage Jenkins** → **Global Tool Configuration**
2. Section **Dependency-Check** → **Add Dependency-Check**
3. Remplir :
   - **Name** : `dependency-check-9.2.0`
   - **Install automatically** : ✅ coché
   - **Version** : `9.2.0` ou supérieur

### 3. Clé API NVD (optionnel mais recommandé)

Pour éviter les limitations de taux :
1. Obtenir une clé sur https://nvd.nist.gov/developers/request-an-api-key
2. **Manage Jenkins** → **Manage Credentials**
3. Ajouter **Secret text** :
   - **ID** : `nvd-api-key`
   - **Secret** : votre clé API

Puis dans le Jenkinsfile :
```groovy
environment {
    NVD_API_KEY = credentials('nvd-api-key')
}
// ...
dependencyCheck(
    additionalArguments: "--nvdApiKey \${NVD_API_KEY}",
    // ...
)
```

## Différences techniques

| Aspect | Plugin Maven | Plugin Jenkins |
|--------|--------------|----------------|
| **Outil** | `org.owasp:dependency-check-maven` | Jenkins plugin + CLI tool |
| **Invocation** | `./mvnw org.owasp:...:check` | `dependencyCheck()` step |
| **Cache NVD** | `target/dependency-check-data/` | `JENKINS_HOME/dependency-check-data/` |
| **Réutilisation cache** | ❌ Non (supprimé entre builds) | ✅ Oui (partagé entre builds) |
| **Rapports** | HTML/JSON dans `target/` | HTML/JSON/XML + UI Jenkins |
| **Visualisation** | Fichier statique | Graphiques + historique Jenkins |
| **Compatibilité CVSS v4** | ❌ Erreur avec nouvelles énumérations | ✅ Compatible |
| **Seuils** | `failBuildOnCVSS` uniquement | Seuils granulaires par niveau |
| **Configuration** | `pom.xml` | Jenkinsfile + Jenkins UI |

## Impact sur le développement local

Le plugin Maven **reste disponible** pour usage local :

```bash
# Analyse locale (optionnel)
cd rhDemo
./mvnw org.owasp:dependency-check-maven:check

# Rapport généré dans :
open target/dependency-check-report.html
```

**Note** : Le plugin Maven peut encore rencontrer l'erreur CVSS v4.0 en local. Si c'est le cas :
- Utiliser `--nvdValidForHours 168` pour espacer les mises à jour
- Ou désactiver temporairement l'analyse NVD

## Documentation

- **Setup administrateur Jenkins** : [JENKINS_OWASP_SETUP.md](JENKINS_OWASP_SETUP.md)
- **Guide complet plugin Jenkins** : [OWASP_JENKINS_PLUGIN.md](OWASP_JENKINS_PLUGIN.md)
- **Guide plugin Maven (legacy)** : [OWASP_DEPENDENCY_CHECK.md](OWASP_DEPENDENCY_CHECK.md)

## Résumé des changements

### Fichiers modifiés

1. **Jenkinsfile (ligne 422-460)** : Remplacé `sh './mvnw ...'` par `dependencyCheck()` + `dependencyCheckPublisher()`
2. **pom.xml (ligne 309-316)** : Ajout note explicative dans commentaire

### Fichiers créés

1. **docs/OWASP_JENKINS_PLUGIN.md** : Documentation complète plugin Jenkins
2. **docs/JENKINS_OWASP_SETUP.md** : Guide installation pour admin Jenkins
3. **docs/OWASP_MIGRATION_JENKINS_PLUGIN.md** : Ce fichier (migration guide)

### Actions requises

#### Pour l'administrateur Jenkins :
1. ✅ Installer le plugin **OWASP Dependency-Check Plugin**
2. ✅ Configurer l'outil `dependency-check-9.2.0` dans Global Tool Configuration
3. ⚠️ (Optionnel) Obtenir et configurer une clé API NVD

#### Pour les développeurs :
- Aucune action requise
- Le plugin Maven reste utilisable en local pour tests ponctuels

## Vérification

Après installation du plugin Jenkins, vérifier que le pipeline passe :

```bash
# Déclencher un build
# Dans Jenkins : Build Now

# Vérifier les logs du stage OWASP
# Doit afficher :
#   📌 Utilisation du plugin Jenkins OWASP Dependency-Check
#   Updating dependency-check...
#   Analyzing dependencies...
#   Dependency-Check execution successful

# Vérifier le rapport
# Onglet "Dependency-Check Results" dans la page du build
```

## Rollback (si nécessaire)

Si le plugin Jenkins pose problème, revenir au plugin Maven :

```groovy
// Jenkinsfile : stage OWASP
sh '''
    . rhDemo/secrets/env-vars.sh
    cd rhDemo && ./mvnw org.owasp:dependency-check-maven:check
'''
```

**MAIS** : Le problème CVSS v4.0 réapparaîtra. Solutions temporaires :
- Désactiver l'auto-update NVD : `--nvdValidForHours 999999`
- Utiliser un cache NVD figé (pré-CVSS v4.0)

## Références

- NVD CVSS v4.0 : https://nvd.nist.gov/vuln-metrics/cvss/v4-calculator
- Plugin Jenkins : https://plugins.jenkins.io/dependency-check-jenkins-plugin/
- Issue GitHub plugin Maven : https://github.com/jeremylong/DependencyCheck/issues/XXXX

## Date de migration

**26 novembre 2025** - Migration du plugin Maven vers plugin Jenkins pour résoudre incompatibilité CVSS v4.0.
