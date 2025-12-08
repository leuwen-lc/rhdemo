# 📚 rhDemoLib - Bibliothèque de Fonctions Jenkins

Bibliothèque de fonctions réutilisables pour le pipeline Jenkins rhDemo.

## 🚀 Quick Start

```groovy
// Dans votre Jenkinsfile
script {
    def lib = load 'vars/rhDemoLib.groovy'

    // Healthcheck d'un service
    lib.waitForHealthcheck([
        name: 'Mon Service',
        url: 'http://mon-service:8080/health',
        timeout: 60
    ])

    // Scan Trivy
    lib.generateTrivyReport('nginx:1.27-alpine', 'nginx')

    // Publier des rapports HTML
    lib.publishHTMLReports([
        ['target/reports', 'index.html', 'Mon Rapport']
    ])
}
```

## 📖 API Documentation

### Gestion des Secrets

#### `loadSecrets(String secretsPath)`
Charge les secrets depuis un fichier bash.

**Paramètres :**
- `secretsPath` : Chemin vers le fichier (défaut: `rhDemo/secrets/env-vars.sh`)

**Exemple :**
```groovy
lib.loadSecrets('rhDemo/secrets/env-vars.sh')
```

---

### Healthchecks

#### `waitForHealthcheck(Map config)`
Attend qu'un service soit disponible avec retry automatique.

**Configuration requise :**
- `url` : URL du healthcheck

**Configuration optionnelle :**
- `timeout` : Timeout en secondes (défaut: 60)
- `name` : Nom du service (défaut: 'Service')
- `container` : Container Docker pour logs en cas d'échec
- `initialWait` : Attente initiale avant checks (défaut: 0)
- `acceptedCodes` : Codes HTTP acceptés (défaut: [200])
- `insecure` : Ignorer erreurs SSL (défaut: false)

**Exemples :**

```groovy
// Healthcheck simple
lib.waitForHealthcheck([
    name: 'API',
    url: 'http://api:8080/health'
])

// Healthcheck avec attente initiale
lib.waitForHealthcheck([
    name: 'Keycloak',
    url: 'http://keycloak:9000/health/ready',
    timeout: 90,
    initialWait: 45,
    container: 'keycloak-container'
])

// Healthcheck HTTPS avec certificat auto-signé
lib.waitForHealthcheck([
    name: 'Nginx',
    url: 'https://nginx.local/health',
    insecure: true,
    acceptedCodes: [200, 302]
])
```

---

### Sécurité - Trivy

#### `generateTrivyReport(String image, String reportName)`
Génère un rapport Trivy complet (JSON, TXT, HTML) pour une image Docker.

**Paramètres :**
- `image` : Nom complet de l'image (ex: `nginx:1.27-alpine`)
- `reportName` : Nom du rapport (ex: `nginx`)

**Génère :**
- `trivy-reports/${reportName}.json` : Données brutes pour analyse programmatique
- `trivy-reports/${reportName}.txt` : Rapport texte pour lecture humaine
- `trivy-reports/${reportName}.html` : Rapport HTML stylisé

**Exemple :**
```groovy
lib.generateTrivyReport('postgres:16-alpine', 'postgres')
```

#### `aggregateTrivyResults()`
Agrège les résultats de tous les scans Trivy et vérifie les seuils.

**Retourne :**
- `true` : Aucune vulnérabilité CRITICAL
- `false` : Vulnérabilités CRITICAL détectées

**Affiche :**
- Nombre total de vulnérabilités CRITICAL/HIGH/MEDIUM
- Statut de validation (✅ SUCCÈS ou ❌ ÉCHEC)

**Exemple :**
```groovy
// Scanner plusieurs images en parallèle
def images = [
    [image: 'nginx:1.27-alpine', name: 'nginx'],
    [image: 'postgres:16-alpine', name: 'postgres']
]

def scanStages = images.collectEntries { img ->
    ["Scan ${img.name}": {
        lib.generateTrivyReport(img.image, img.name)
    }]
}

parallel(scanStages + [failFast: false])

// Vérifier les seuils
if (!lib.aggregateTrivyResults()) {
    error("Vulnérabilités CRITICAL détectées")
}
```

---

### Réseaux Docker

#### `dockerNetworkConnect(String container, String network)`
Connecte un container à un réseau Docker.

**Exemple :**
```groovy
lib.dockerNetworkConnect('jenkins', 'staging-network')
```

#### `dockerNetworkDisconnect(String container, String network)`
Déconnecte un container d'un réseau Docker.

**Exemple :**
```groovy
lib.dockerNetworkDisconnect('jenkins', 'staging-network')
```

---

### Gestion des Secrets (Nettoyage)

#### `cleanupSecrets(List files)`
Nettoie de manière sécurisée les fichiers contenant des secrets.

**Méthode :**
1. Utilise `shred -vfz -n 3` (écrasement 3 passes)
2. Fallback sur `dd` + `rm` si shred non disponible

**Exemple :**
```groovy
lib.cleanupSecrets([
    'rhDemo/secrets/env-vars.sh',
    'rhDemo/secrets/secrets-decrypted.yml',
    'rhDemo/secrets/secrets-rhdemo.yml'
])
```

---

### Rapports HTML

#### `publishHTMLReport(String reportDir, String reportFile, String reportName)`
Publie un rapport HTML dans Jenkins.

**Exemple :**
```groovy
lib.publishHTMLReport(
    'target/site/jacoco',
    'index.html',
    'Code Coverage'
)
```

#### `publishHTMLReports(List reports)`
Publie plusieurs rapports HTML d'un coup.

**Format :** `[reportDir, reportFile, reportName]`

**Exemple :**
```groovy
def reports = [
    ['target/jacoco', 'index.html', 'Coverage'],
    ['target/trivy', 'nginx.html', 'Trivy - Nginx'],
    ['target/owasp', 'zap-report.html', 'OWASP ZAP']
]

lib.publishHTMLReports(reports)
```

---

### Utilitaires

#### `findJenkinsContainer()`
Trouve le container Jenkins principal (exclut les agents).

**Retourne :**
- Nom du container Jenkins
- `null` si non trouvé

**Exemple :**
```groovy
def jenkinsContainer = lib.findJenkinsContainer()
if (jenkinsContainer) {
    echo "Container Jenkins: ${jenkinsContainer}"
}
```

#### `printSectionHeader(String title)`
Affiche un séparateur visuel dans les logs.

**Exemple :**
```groovy
lib.printSectionHeader('PHASE 1 : PRÉPARATION')
// Affiche :
// ═══════════════════════════════════════════════════════
//   PHASE 1 : PRÉPARATION
// ═══════════════════════════════════════════════════════
```

#### `withSecretsLoaded(String secretsPath, String command)`
Exécute une commande avec les secrets chargés.

**Exemple :**
```groovy
lib.withSecretsLoaded(
    'rhDemo/secrets/env-vars.sh',
    'mvn clean package'
)
```

---

## 🎨 Patterns d'Utilisation

### Pattern 1 : Healthchecks Séquentiels

```groovy
script {
    def lib = load 'vars/rhDemoLib.groovy'

    lib.waitForHealthcheck([
        name: 'Database',
        url: 'http://db:5432/health',
        timeout: 30
    ])

    lib.waitForHealthcheck([
        name: 'API',
        url: 'http://api:8080/health',
        timeout: 60
    ])
}
```

### Pattern 2 : Scans Parallèles

```groovy
script {
    def lib = load 'vars/rhDemoLib.groovy'

    def images = [
        [image: 'nginx:alpine', name: 'nginx'],
        [image: 'postgres:16', name: 'postgres']
    ]

    def scanStages = images.collectEntries { img ->
        ["Scan ${img.name}": {
            lib.generateTrivyReport(img.image, img.name)
        }]
    }

    parallel(scanStages)
}
```

### Pattern 3 : Gestion Complète des Secrets

```groovy
script {
    def lib = load 'vars/rhDemoLib.groovy'

    try {
        // Charger les secrets
        lib.loadSecrets('secrets/env-vars.sh')

        // Utiliser les secrets
        sh 'mvn deploy'

    } finally {
        // Nettoyer les secrets
        lib.cleanupSecrets([
            'secrets/env-vars.sh',
            'secrets/decrypted.yml'
        ])
    }
}
```

---

## 🧪 Tests

### Tester une Fonction Localement

```groovy
// test-healthcheck.groovy
@Library('rhDemoLib') _

node {
    def lib = load 'vars/rhDemoLib.groovy'

    // Test healthcheck
    lib.waitForHealthcheck([
        name: 'Test',
        url: 'http://localhost:8080',
        timeout: 5
    ])
}
```

### Tester Trivy

```bash
# Prérequis : avoir trivy installé
cd rhDemo
mkdir -p trivy-reports

# Tester le scan
groovy -e "
def lib = load('vars/rhDemoLib.groovy')
lib.generateTrivyReport('nginx:alpine', 'test')
"

# Vérifier les rapports générés
ls -lh trivy-reports/
```

---

## 🔧 Débogage

### Activer les Logs Détaillés

```groovy
// Avant un appel de fonction
sh 'set -x'  // Active le mode debug bash

lib.waitForHealthcheck([...])

sh 'set +x'  // Désactive le mode debug
```

### Afficher les Paramètres de Configuration

```groovy
script {
    def config = [
        name: 'API',
        url: 'http://api:8080/health',
        timeout: 60
    ]

    echo "Configuration healthcheck:"
    config.each { key, value ->
        echo "  ${key}: ${value}"
    }

    lib.waitForHealthcheck(config)
}
```

---

## 💡 Best Practices

1. **Toujours charger la bibliothèque dans un bloc `script`**
   ```groovy
   script {
       def lib = load 'vars/rhDemoLib.groovy'
       lib.myFunction()
   }
   ```

2. **Utiliser des configurations déclaratives**
   ```groovy
   // ✅ Bon
   def config = [name: 'API', url: 'http://...', timeout: 60]
   lib.waitForHealthcheck(config)

   // ❌ Éviter
   lib.waitForHealthcheck('API', 'http://...', 60, null, 0, [200], false)
   ```

3. **Gérer les erreurs explicitement**
   ```groovy
   try {
       lib.waitForHealthcheck([...])
   } catch (Exception e) {
       echo "Healthcheck échoué: ${e.message}"
       // Action de récupération
   }
   ```

4. **Nettoyer les ressources dans `finally`**
   ```groovy
   try {
       lib.loadSecrets('secrets.sh')
       // ...
   } finally {
       lib.cleanupSecrets(['secrets.sh'])
   }
   ```

---

## 🔗 Références

- Documentation complète : [JENKINSFILE_REFACTORING.md](../JENKINSFILE_REFACTORING.md)
- Exemples d'utilisation : [Jenkinsfile](../Jenkinsfile)
- Scripts bash : [scripts/jenkins/](../scripts/jenkins/)

---

**Version** : 1.0.0
**Dernière mise à jour** : 2025-12-02
