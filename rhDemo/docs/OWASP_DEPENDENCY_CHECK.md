# OWASP Dependency-Check - Analyse des vulnérabilités

Guide de configuration et d'utilisation de l'analyse de sécurité des dépendances avec OWASP Dependency-Check.

> **⚠️ IMPORTANT** : Le pipeline Jenkins utilise le **plugin Jenkins OWASP Dependency-Check** au lieu du plugin Maven pour une meilleure compatibilité avec CVSS v4.0. Voir [OWASP_JENKINS_PLUGIN.md](OWASP_JENKINS_PLUGIN.md) pour la documentation complète du plugin Jenkins.

## Table des matières

- [Qu'est-ce que OWASP Dependency-Check ?](#quest-ce-que-owasp-dependency-check-)
- [Configuration actuelle](#configuration-actuelle)
- [Seuils de blocage](#seuils-de-blocage)
- [Exécution locale](#exécution-locale)
- [Gestion des faux positifs](#gestion-des-faux-positifs)
- [Intégration CI/CD](#intégration-cicd)
- [Performance et cache](#performance-et-cache)

---

## Qu'est-ce que OWASP Dependency-Check ?

**OWASP Dependency-Check** est un outil qui analyse les dépendances d'un projet et identifie les **vulnérabilités de sécurité connues** (CVE - Common Vulnerabilities and Exposures).

Il compare les dépendances Maven/npm avec la base de données **NVD** (National Vulnerability Database) du NIST.

### Score CVSS

Le **CVSS** (Common Vulnerability Scoring System) évalue la gravité des vulnérabilités sur une échelle de 0 à 10 :

| Score CVSS | Niveau | Couleur | Action recommandée |
|------------|--------|---------|-------------------|
| 0.0 - 3.9 | **Low** | 🟢 Vert | Surveiller |
| 4.0 - 6.9 | **Medium** | 🟡 Jaune | Corriger prochainement |
| 7.0 - 8.9 | **High** | 🟠 Orange | **Corriger rapidement** |
| 9.0 - 10.0 | **Critical** | 🔴 Rouge | **Corriger immédiatement** |

---

## Configuration actuelle

### Couverture npm (frontend Vue.js)

Le plugin Maven n'analyse par défaut que les dépendances résolues par Maven (jars). Un `scanSet` a été ajouté ([pom.xml](../pom.xml)) pour inclure `frontend/package.json` et `frontend/package-lock.json` dans l'analyse (Node Package/Audit Analyzer + Retire.js, activés par défaut dans dependency-check), afin de couvrir aussi les CVE des dépendances npm (Vue, Element Plus, Axios...). `node_modules/` et `dist/` sont exclus du scan (déjà couverts via les fichiers de lock, inutile de les parcourir).

### [pom.xml:309-345](../pom.xml#L309-L345)

```xml
<plugin>
    <groupId>org.owasp</groupId>
    <artifactId>dependency-check-maven</artifactId>
    <version>11.1.1</version>
    <configuration>
        <!-- Échouer le build si CVSS ≥ 7.0 -->
        <failBuildOnCVSS>7.0</failBuildOnCVSS>

        <!-- Format des rapports -->
        <formats>
            <format>HTML</format>
            <format>JSON</format>
        </formats>

        <!-- Configuration NVD API -->
        <nvdApiServerId>nvd-api</nvdApiServerId>
        <nvdApiKeyEnvironmentVariable>NVD_API_KEY</nvdApiKeyEnvironmentVariable>

        <!-- Cache pour améliorer les performances -->
        <dataDirectory>${project.build.directory}/dependency-check-data</dataDirectory>
    </configuration>
</plugin>
```

### Paramètres clés

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| `failBuildOnCVSS` | **7.0** | Le build échoue si une vulnérabilité ≥ 7.0 est détectée |
| `failOnError` | `true` | Le build échoue en cas d'erreur du plugin |
| `skipTestScope` | `false` | Analyse aussi les dépendances de test |
| `connectionTimeout` | `30000` | Timeout de connexion à NVD (30s) |

---

## Seuils de blocage

### Configuration actuelle : CVSS ≥ 7.0 (High/Critical)

Le projet est configuré pour **bloquer le build** si des vulnérabilités **High** ou **Critical** sont détectées.

### Modifier le seuil

Pour changer le niveau de sévérité qui bloque le build, modifier `<failBuildOnCVSS>` dans [pom.xml](../pom.xml#L316) :

```xml
<!-- Bloquer uniquement sur Critical (≥ 9.0) -->
<failBuildOnCVSS>9.0</failBuildOnCVSS>

<!-- Bloquer sur Medium et supérieur (≥ 4.0) -->
<failBuildOnCVSS>4.0</failBuildOnCVSS>

<!-- Ne jamais bloquer (désactivé) -->
<failBuildOnCVSS>11.0</failBuildOnCVSS>
```

### Recommandations par environnement

| Environnement | Seuil recommandé | Justification |
|---------------|------------------|---------------|
| **Dev local** | 11.0 (pas de blocage) | Développement rapide, rapport informatif |
| **Staging** | **7.0** (High+) | Détection précoce des vulnérabilités critiques |
| **Production** | **4.0** (Medium+) | Sécurité maximale |

---

## Exécution locale

### Analyse complète

```bash
cd rhDemo

# Exécuter l'analyse OWASP
./mvnw dependency-check:check

# Le rapport HTML est généré dans :
open target/dependency-check-report.html  # macOS
xdg-open target/dependency-check-report.html  # Linux
```

### Mise à jour de la base de données NVD

La première exécution télécharge la base de données NVD (~500 Mo) :

```bash
# Forcer la mise à jour de la base NVD
./mvnw dependency-check:update-only

# Analyse sans mise à jour (plus rapide si base récente)
./mvnw dependency-check:check -DskipUpdate=true
```

### Rapports générés

| Fichier | Format | Usage |
|---------|--------|-------|
| `dependency-check-report.html` | HTML | Consultation humaine |
| `dependency-check-report.json` | JSON | Intégration outils/scripts |

---

## Gestion des faux positifs

### Qu'est-ce qu'un faux positif ?

Un **faux positif** se produit quand Dependency-Check signale une vulnérabilité qui :
- Ne s'applique pas à l'usage réel de la dépendance
- A été corrigée mais pas encore enregistrée dans NVD
- Concerne une classe/méthode non utilisée dans le projet

### Créer un fichier de suppression

1. **Créer le fichier** `owasp-suppressions.xml` à la racine du projet :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<suppressions xmlns="https://jeremylong.github.io/DependencyCheck/dependency-suppression.1.3.xsd">

    <!-- Exemple : Supprimer CVE-2024-12345 pour spring-boot-starter-web -->
    <suppress>
        <notes>
            <![CDATA[
            Faux positif : Cette vulnérabilité concerne une fonctionnalité non utilisée.
            Référence : https://github.com/spring-projects/spring-boot/issues/xxxxx
            ]]>
        </notes>
        <packageUrl regex="true">^pkg:maven/org\.springframework\.boot/spring\-boot\-starter\-web@.*$</packageUrl>
        <cve>CVE-2024-12345</cve>
    </suppress>

    <!-- Exemple : Supprimer toutes les vulnérabilités d'une dépendance de test -->
    <suppress>
        <notes>
            <![CDATA[
            Dépendance utilisée uniquement en test, risque acceptable.
            ]]>
        </notes>
        <packageUrl regex="true">^pkg:maven/com\.example/test\-library@.*$</packageUrl>
        <cvssBelow>10.0</cvssBelow>
    </suppress>

</suppressions>
```

2. **Activer dans pom.xml** (décommenter la ligne 328) :

```xml
<suppressionFile>${project.basedir}/owasp-suppressions.xml</suppressionFile>
```

3. **Ajouter au .gitignore si nécessaire** :

```bash
# Si le fichier contient des informations sensibles
echo "owasp-suppressions.xml" >> .gitignore
```

### Structure d'une suppression

```xml
<suppress>
    <notes>Explication détaillée du pourquoi</notes>

    <!-- Identifier la dépendance -->
    <packageUrl regex="true">^pkg:maven/group/artifact@version$</packageUrl>
    <!-- OU -->
    <gav regex="true">group:artifact:version</gav>

    <!-- Identifier la vulnérabilité -->
    <cve>CVE-2024-12345</cve>
    <!-- OU -->
    <cvssBelow>5.0</cvssBelow>

    <!-- Optionnel : Expiration de la suppression -->
    <until>2025-12-31</until>
</suppress>
```

### Bonnes pratiques

- ✅ **Toujours documenter** : Expliquer pourquoi c'est un faux positif
- ✅ **Ajouter des références** : URL issue GitHub, ticket Jira, etc.
- ✅ **Définir une expiration** : `<until>` pour réévaluer périodiquement
- ✅ **Être spécifique** : Supprimer une CVE précise, pas toutes les vulnérabilités
- ❌ **Ne pas abuser** : Supprimer uniquement les vrais faux positifs

---

## Intégration CI/CD

### Jenkinsfile - Stage actuel

**[Jenkinsfile:1121-1142](../Jenkinsfile#L1121-L1142)**

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

### Comportement en cas de vulnérabilité détectée

1. **CVSS < 7.0** : Build continue, rapport généré
2. **CVSS ≥ 7.0** : **Build échoue**, rapport généré, email envoyé

### Configuration Jenkins (optionnelle)

Pour améliorer les performances, configurer une **clé API NVD** :

1. Obtenir une clé API gratuite : https://nvd.nist.gov/developers/request-an-api-key
2. Ajouter dans Jenkins Credentials :
   - Type : Secret text
   - ID : `nvd-api-key`
   - Secret : Votre clé API
3. Modifier le Jenkinsfile :

```groovy
environment {
    NVD_API_KEY = credentials('nvd-api-key')
}
```

**Avantage** : Limite de requêtes plus élevée (5000/10 min vs 5/30 sec)

---

## Performance et cache

### Temps d'exécution

| Situation | Temps estimé |
|-----------|--------------|
| Première exécution (téléchargement NVD) | 5-10 minutes |
| Exécutions suivantes (cache local) | 30-60 secondes |
| Avec clé API NVD | 20-40 secondes |

### Cache local

Le cache NVD est stocké dans :
- **Local** : `target/dependency-check-data/`
- **Jenkins** : `/var/jenkins_home/.m2/repository/`

### Optimisations

```xml
<!-- Mise à jour quotidienne au lieu de chaque build -->
<autoUpdate>true</autoUpdate>
<cveValidForHours>24</cveValidForHours>

<!-- Activer le cache local -->
<dataDirectory>${user.home}/.m2/dependency-check-data</dataDirectory>

<!-- Analyser uniquement les dépendances principales -->
<skipTestScope>true</skipTestScope>
```

---

## Corriger les vulnérabilités

### 1. Identifier la vulnérabilité

Consulter le rapport HTML :
```
📊 OWASP Dependency Check Report
├── Summary : X vulnérabilités détectées
├── Dependencies : Liste des dépendances
└── Vulnerabilities : Détails CVE
```

### 2. Mettre à jour la dépendance

```bash
# Vérifier les versions disponibles
./mvnw versions:display-dependency-updates

# Mettre à jour une dépendance spécifique dans pom.xml
<dependency>
    <groupId>org.example</groupId>
    <artifactId>vulnerable-lib</artifactId>
    <version>2.5.1</version> <!-- Ancienne version vulnérable -->
    <!-- Mettre à jour vers -->
    <version>2.6.0</version> <!-- Version corrigée -->
</dependency>

# Re-tester
./mvnw dependency-check:check
```

### 3. Si mise à jour impossible

- Vérifier si un **patch backport** existe
- Contacter le mainteneur du projet
- Remplacer par une dépendance alternative
- En dernier recours : Supprimer comme faux positif (documenté)

---

## Exemples de commandes

```bash
# Analyse complète
./mvnw dependency-check:check

# Analyse sans mise à jour de la base NVD
./mvnw dependency-check:check -DskipUpdate=true

# Purger le cache et re-télécharger
./mvnw dependency-check:purge
./mvnw dependency-check:update-only

# Ignorer temporairement les échecs (développement)
./mvnw dependency-check:check -Ddependency-check.failBuild=false

# Générer uniquement le rapport JSON
./mvnw dependency-check:check -Dformat=JSON

# Analyser avec un seuil différent
./mvnw dependency-check:check -DfailBuildOnCVSS=9.0
```

---

## Troubleshooting

### Erreur : "Failed to connect to NVD"

**Cause** : Problème réseau ou limite de requêtes NVD

**Solutions** :
1. Utiliser une clé API NVD (voir Configuration Jenkins)
2. Augmenter le timeout : `<connectionTimeout>60000</connectionTimeout>`
3. Réessayer plus tard

### Erreur : "Unable to download NVD data feeds"

**Cause** : Proxy ou firewall bloque l'accès

**Solution** :
```bash
# Configurer le proxy Maven
./mvnw -Dhttps.proxyHost=proxy.example.com -Dhttps.proxyPort=8080 dependency-check:check
```

### Build échoue sur des vulnérabilités connues

**Solutions** :
1. Mettre à jour les dépendances
2. Supprimer les faux positifs (avec justification)
3. Augmenter temporairement le seuil pour débloquer

---

## Ressources

- **Documentation officielle** : https://jeremylong.github.io/DependencyCheck/
- **NVD Database** : https://nvd.nist.gov/
- **CVE Details** : https://www.cvedetails.com/
- **OWASP Top 10** : https://owasp.org/www-project-top-ten/

## Voir aussi

- [SECURITY_LEAST_PRIVILEGE.md](SECURITY_LEAST_PRIVILEGE.md) - Principe du moindre privilège
- [Jenkinsfile](../Jenkinsfile) - Pipeline CI/CD
