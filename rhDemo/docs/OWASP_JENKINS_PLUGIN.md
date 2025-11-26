# OWASP Dependency-Check - Plugin Jenkins

## Contexte

Suite à des problèmes de compatibilité entre le plugin Maven OWASP Dependency-Check (version 11.1.1) et les nouvelles données CVSS v4.0 du NVD (National Vulnerability Database), nous utilisons le **plugin Jenkins OWASP Dependency-Check** qui offre une meilleure stabilité et plus de fonctionnalités.

### Problème rencontré avec le plugin Maven

```
[ERROR] Failed to parse NVD data
Caused by: java.lang.IllegalArgumentException: SAFETY
    at io.github.jeremylong.openvulnerability.client.nvd.CvssV4Data$ModifiedCiaType.fromValue
```

Le plugin Maven ne peut pas analyser les nouvelles énumérations CVSS v4.0 introduites par le NVD (notamment la valeur "SAFETY").

## Installation du plugin Jenkins

### 1. Installer le plugin OWASP Dependency-Check

Via l'interface Jenkins :
1. Naviguer vers **Manage Jenkins** → **Manage Plugins**
2. Onglet **Available plugins**
3. Rechercher : `OWASP Dependency-Check Plugin`
4. Cocher et cliquer sur **Install without restart**

Ou via Jenkins CLI :
```bash
java -jar jenkins-cli.jar -s http://localhost:8080/ install-plugin dependency-check-jenkins-plugin
```

### 2. Configurer le plugin

1. Aller dans **Manage Jenkins** → **Global Tool Configuration**
2. Section **Dependency-Check**
3. Cliquer sur **Add Dependency-Check**
4. Configuration :
   - **Name** : `dependency-check-9.2.0` (ou version désirée)
   - **Install automatically** : cocher
   - **Version** : sélectionner la dernière version stable (9.2.0 recommandée)
   - **Add Installer** : choisir "Install from GitHub"

### 3. Configuration NVD API Key (optionnel mais recommandé)

Pour éviter les limitations de taux d'API NVD :

1. Obtenir une clé API sur https://nvd.nist.gov/developers/request-an-api-key
2. Dans Jenkins : **Manage Jenkins** → **Configure System**
3. Section **Dependency-Check**
4. Ajouter votre clé API NVD

Ou via credentials Jenkins :
1. **Manage Jenkins** → **Manage Credentials**
2. Ajouter **Secret text** avec ID : `nvd-api-key`
3. Référencer dans le pipeline avec `credentialsId: 'nvd-api-key'`

## Utilisation dans le Jenkinsfile

### Configuration de base

```groovy
stage('🔒 Analyse Sécurité Dépendances (OWASP)') {
    steps {
        script {
            echo '▶ Analyse des vulnérabilités des dépendances (OWASP Dependency-Check)...'
            echo '   ⚠️  Le build échouera si vulnérabilités CVSS ≥ 7.0 (High/Critical)'
        }

        // Utiliser le plugin Jenkins au lieu du plugin Maven
        dependencyCheck(
            additionalArguments: '''
                --scan rhDemo/target/classes
                --scan rhDemo/pom.xml
                --project "rhDemo"
                --format HTML
                --format JSON
                --failOnCVSS 7.0
                --enableExperimental
                --nvdApiKey ${NVD_API_KEY}
            ''',
            odcInstallation: 'dependency-check-9.2.0'
        )

        // Publier le rapport
        dependencyCheckPublisher(
            pattern: '**/dependency-check-report.xml',
            failedTotalCritical: 0,
            failedTotalHigh: 0,
            unstableTotalCritical: 0,
            unstableTotalHigh: 0
        )
    }
}
```

### Configuration avancée avec credentials

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
        }

        dependencyCheck(
            additionalArguments: """
                --scan rhDemo/target/classes
                --scan rhDemo/pom.xml
                --project rhDemo
                --format HTML
                --format JSON
                --format XML
                --failOnCVSS 7.0
                --enableExperimental
                --nvdApiKey \${NVD_API_KEY}
                --nvdDatafeedUrl https://nvd.nist.gov/feeds/json/cve/1.1
                --nvdMaxRetryCount 5
                --nvdValidForHours 24
            """,
            odcInstallation: 'dependency-check-9.2.0',
            stopBuild: false  // Ne pas arrêter immédiatement, laisser dependencyCheckPublisher gérer
        )

        dependencyCheckPublisher(
            pattern: '**/dependency-check-report.xml',
            failedTotalCritical: 0,    // Échec si ≥ 1 vulnérabilité Critical (CVSS 9.0-10.0)
            failedTotalHigh: 0,         // Échec si ≥ 1 vulnérabilité High (CVSS 7.0-8.9)
            unstableTotalCritical: 0,
            unstableTotalHigh: 0,
            usePreviousBuildAsReference: true
        )
    }
}
```

## Options du plugin

### Options de scan

| Option | Description |
|--------|-------------|
| `--scan <path>` | Répertoire ou fichier à analyser |
| `--project <name>` | Nom du projet pour le rapport |
| `--format <format>` | Format de sortie : HTML, JSON, XML, CSV, ALL |
| `--out <path>` | Répertoire de sortie des rapports |

### Options de sécurité

| Option | Description | Valeur recommandée |
|--------|-------------|-------------------|
| `--failOnCVSS <score>` | Échec si CVSS ≥ score | `7.0` (High/Critical) |
| `--junitFailOnCVSS <score>` | Score CVSS pour échec JUnit | `7.0` |

### Options NVD

| Option | Description | Valeur recommandée |
|--------|-------------|-------------------|
| `--nvdApiKey <key>` | Clé API NVD | Obligatoire pour éviter rate limiting |
| `--nvdValidForHours <hours>` | Validité cache NVD | `24` (1 jour) |
| `--nvdMaxRetryCount <count>` | Nombre de tentatives max | `5` |
| `--nvdApiDelay <ms>` | Délai entre requêtes API | `1000` (avec clé) / `6000` (sans) |

### Options expérimentales

| Option | Description |
|--------|-------------|
| `--enableExperimental` | Activer analyseurs expérimentaux |
| `--enableRetired` | Activer analyseurs deprecated |

## Configuration dependencyCheckPublisher

Le step `dependencyCheckPublisher` permet de définir des seuils de vulnérabilités :

```groovy
dependencyCheckPublisher(
    pattern: '**/dependency-check-report.xml',

    // Seuils FAILED (build échoue)
    failedTotalCritical: 0,     // Échec si ≥ 1 Critical
    failedTotalHigh: 0,          // Échec si ≥ 1 High
    failedTotalMedium: null,     // Pas de seuil Medium
    failedTotalLow: null,        // Pas de seuil Low

    // Seuils UNSTABLE (build instable)
    unstableTotalCritical: 0,
    unstableTotalHigh: 0,
    unstableTotalMedium: null,
    unstableTotalLow: null,

    // Autres options
    usePreviousBuildAsReference: true,  // Comparer avec build précédent
    shouldDetectModules: false
)
```

## Gestion du cache NVD

Le plugin Jenkins gère automatiquement le cache NVD dans `JENKINS_HOME/dependency-check-data/`.

### Forcer la mise à jour du cache

```groovy
dependencyCheck(
    additionalArguments: '--nvdValidForHours 0',  // Forcer la mise à jour
    odcInstallation: 'dependency-check-9.2.0'
)
```

### Nettoyer le cache

```bash
# Sur le serveur Jenkins
rm -rf $JENKINS_HOME/dependency-check-data/*
```

Ou via script Groovy dans **Manage Jenkins** → **Script Console** :
```groovy
def dataDir = new File(Jenkins.instance.rootDir, 'dependency-check-data')
if (dataDir.exists()) {
    dataDir.deleteDir()
    println "Cache NVD supprimé : ${dataDir}"
}
```

## Lecture des rapports

### Rapport HTML

Le rapport HTML est publié via `dependencyCheckPublisher` et accessible dans l'interface Jenkins :
- Onglet **Dependency-Check** dans la page du build
- Graphiques d'évolution des vulnérabilités

### Rapport JSON

Pour parsing automatique :
```bash
cat dependency-check-report.json | jq '.dependencies[] | select(.vulnerabilities | length > 0)'
```

### Rapport XML

Pour intégration avec d'autres outils :
```bash
xmllint --xpath "//dependency[count(vulnerabilities/vulnerability) > 0]" dependency-check-report.xml
```

## Intégration avec SonarQube

Le plugin Jenkins peut générer un rapport compatible SonarQube :

```groovy
dependencyCheck(
    additionalArguments: '--format JSON',
    odcInstallation: 'dependency-check-9.2.0'
)

// Convertir pour SonarQube
sh '''
    dependency-check-sonar-plugin \
        --input dependency-check-report.json \
        --output dependency-check-sonar.json
'''

// Envoyer à SonarQube
sh '''
    cd rhDemo
    ./mvnw sonar:sonar \
        -Dsonar.dependencyCheck.jsonReportPath=../dependency-check-sonar.json
'''
```

## Troubleshooting

### Erreur : "No tool named dependency-check-9.2.0 found"

**Cause** : Le plugin n'est pas configuré dans Global Tool Configuration.

**Solution** :
1. **Manage Jenkins** → **Global Tool Configuration**
2. Section **Dependency-Check** → **Add Dependency-Check**
3. Name : `dependency-check-9.2.0`
4. Cocher **Install automatically**

### Erreur : "NVD API rate limit exceeded"

**Cause** : Trop de requêtes API sans clé d'authentification.

**Solution** :
1. Obtenir une clé API : https://nvd.nist.gov/developers/request-an-api-key
2. Ajouter dans Jenkins credentials (ID : `nvd-api-key`)
3. Utiliser `--nvdApiKey ${NVD_API_KEY}` dans le pipeline

### Timeout lors du premier scan

**Cause** : Le premier scan télécharge toute la base NVD (~2 GB).

**Solution** :
- Augmenter le timeout Jenkins (Build timeout plugin)
- Ou pré-charger le cache manuellement :
```bash
dependency-check --updateonly --nvdApiKey YOUR_KEY
```

### Build échoue sur des faux positifs

**Cause** : Dependency-Check peut détecter des vulnérabilités non applicables.

**Solution** : Créer un fichier de suppression `suppression.xml` :
```xml
<?xml version="1.0" encoding="UTF-8"?>
<suppressions xmlns="https://jeremylong.github.io/DependencyCheck/dependency-suppression.1.3.xsd">
    <suppress>
        <notes>Faux positif : CVE-2023-XXXXX ne s'applique pas à notre usage</notes>
        <cve>CVE-2023-XXXXX</cve>
    </suppress>
</suppressions>
```

Puis ajouter dans le pipeline :
```groovy
dependencyCheck(
    additionalArguments: '--suppression rhDemo/suppression.xml',
    odcInstallation: 'dependency-check-9.2.0'
)
```

## Comparaison plugin Maven vs plugin Jenkins

| Aspect | Plugin Maven | Plugin Jenkins |
|--------|--------------|----------------|
| **Installation** | Dans pom.xml | Dans Jenkins Global Tools |
| **Configuration** | pom.xml + properties | Jenkinsfile + Jenkins UI |
| **Mise à jour** | Modifier version dans pom.xml | Jenkins UI ou Jenkinsfile |
| **Cache NVD** | `target/dependency-check-data/` | `JENKINS_HOME/dependency-check-data/` |
| **Compatibilité CVSS v4** | ❌ Problèmes avec 11.1.1 | ✅ Mieux géré dans versions récentes |
| **Rapports** | HTML/JSON dans target/ | Intégré UI Jenkins + HTML/JSON |
| **Seuils de sécurité** | `failBuildOnCVSS` uniquement | Seuils granulaires (Critical/High/Medium/Low) |
| **Réutilisation cache** | Par build | Entre tous les builds |
| **Visualisation** | Fichier statique | Graphiques Jenkins + historique |

## Recommandations

1. **Utiliser le plugin Jenkins** pour une meilleure compatibilité CVSS v4.0
2. **Configurer une clé API NVD** pour éviter rate limiting
3. **Définir `--nvdValidForHours 24`** pour limiter les mises à jour quotidiennes
4. **Bloquer sur CVSS ≥ 7.0** (High/Critical) uniquement
5. **Créer un fichier suppression.xml** pour les faux positifs récurrents
6. **Monitorer le cache** : nettoyer si > 5 GB

## Références

- Plugin Jenkins : https://plugins.jenkins.io/dependency-check-jenkins-plugin/
- OWASP Dependency-Check : https://jeremylong.github.io/DependencyCheck/
- NVD API : https://nvd.nist.gov/developers
- CVSS Calculator : https://nvd.nist.gov/vuln-metrics/cvss/v3-calculator
