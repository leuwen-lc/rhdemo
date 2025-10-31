# 🔧 Configuration Jenkins pour RHDemo API

## 📋 Table des matières

1. [Prérequis Jenkins](#prérequis-jenkins)
2. [Configuration des outils](#configuration-des-outils)
3. [Configuration des credentials](#configuration-des-credentials)
4. [Plugins requis](#plugins-requis)
5. [Création du job](#création-du-job)
6. [Variables d'environnement](#variables-denvironnement)
7. [Configuration des notifications](#configuration-des-notifications)
8. [Troubleshooting](#troubleshooting)

---

## 🛠️ Prérequis Jenkins

### Version Jenkins recommandée
- **Jenkins 2.400+** (LTS)
- **Java 21** installé sur les agents Jenkins
- **Maven 3.9+** (ou utilisation du wrapper Maven)
- **Git 2.30+**

---

## ⚙️ Configuration des outils

### 1. Configuration Java 21

**Navigate to:** `Manage Jenkins` → `Global Tool Configuration` → `JDK`

```
Nom: JDK21
JAVA_HOME: /usr/lib/jvm/java-21-openjdk-amd64
ou
Installer automatiquement: OpenJDK 21
```

### 2. Configuration Maven

**Navigate to:** `Manage Jenkins` → `Global Tool Configuration` → `Maven`

```
Nom: Maven3
MAVEN_HOME: /usr/share/maven
ou
Installer automatiquement: Apache Maven 3.9.5
```

### 3. Configuration Git

**Navigate to:** `Manage Jenkins` → `Global Tool Configuration` → `Git`

```
Nom: Default
Path to Git executable: git
ou
/usr/bin/git
```

---

## 🔐 Configuration des credentials

### 1. Secrets Keycloak

**Navigate to:** `Manage Jenkins` → `Credentials` → `System` → `Global credentials`

**Ajouter un credential de type "Secret text":**

```
ID: keycloak-client-secret
Secret: <votre-client-secret-keycloak>
Description: Keycloak Client Secret for RHDemo
```

### 2. Mot de passe base de données H2

```
ID: h2-db-password
Secret: <mot-de-passe-h2>
Description: H2 Database Password
```

### 3. Mot de passe base de données PostgreSQL

```
ID: postgres-db-password
Secret: <mot-de-passe-postgres>
Description: PostgreSQL Database Password
```

### 4. URL des serveurs

```
ID: staging-server-url
Secret: staging.example.com
Description: Staging Server URL
```

```
ID: prod-server-url
Secret: prod.example.com
Description: Production Server URL
```

### 5. Credentials SSH (pour déploiement)

**Type:** SSH Username with private key

```
ID: deployment-ssh-key
Username: deploy
Private Key: <votre-clé-privée-ssh>
Description: SSH Key for deployment
```

### 6. Credentials Git (si dépôt privé)

**Type:** Username with password

```
ID: github-credentials
Username: leuwen-lc
Password: <token-github>
Description: GitHub Access Token
```

---

## 🔌 Plugins requis

### Plugins essentiels

**Navigate to:** `Manage Jenkins` → `Manage Plugins` → `Available`

#### Build & Test
- ✅ **Pipeline** (Pipeline Plugin)
- ✅ **Git** (Git Plugin)
- ✅ **Maven Integration** (Maven Integration Plugin)
- ✅ **JUnit** (JUnit Plugin)
- ✅ **JaCoCo** (JaCoCo Plugin)

#### Qualité du code
- ✅ **SonarQube Scanner** (SonarQube Scanner Plugin)
- ✅ **OWASP Dependency-Check** (OWASP Dependency-Check Plugin)

#### Notifications
- ✅ **Email Extension** (Email Extension Plugin)
- ✅ **Slack Notification** (Slack Notification Plugin)

#### Rapports
- ✅ **HTML Publisher** (HTML Publisher Plugin)
- ✅ **Workspace Cleanup** (Workspace Cleanup Plugin)

#### Selenium/Tests UI
- ✅ **Xvfb** (Xvfb Plugin) - Pour exécuter Selenium en headless

### Installation des plugins

```bash
# Via Jenkins CLI (optionnel)
java -jar jenkins-cli.jar -s http://localhost:8080/ install-plugin \
  pipeline-model-definition \
  git \
  maven-plugin \
  junit \
  jacoco \
  sonar \
  dependency-check-jenkins-plugin \
  email-ext \
  slack \
  htmlpublisher \
  ws-cleanup \
  xvfb
```

---

## 🚀 Création du job Jenkins

### 1. Créer un nouveau Pipeline

**Navigate to:** `Jenkins Dashboard` → `New Item`

```
Nom: RHDemo-API-Pipeline
Type: Pipeline
Description: Pipeline CI/CD pour l'application RHDemo API
```

### 2. Configuration du Pipeline

#### General
- ✅ **GitHub project:** `https://github.com/leuwen-lc/rhdemo`
- ✅ **Discard old builds:** Garder 10 builds max
- ✅ **This project is parameterized:** (géré dans le Jenkinsfile)

#### Build Triggers
- ✅ **GitHub hook trigger for GITScm polling**
- ✅ **Poll SCM:** `H/5 * * * *` (vérifier toutes les 5 minutes)

#### Pipeline
```
Definition: Pipeline script from SCM
SCM: Git
Repository URL: https://github.com/leuwen-lc/rhdemo.git
Credentials: github-credentials (si privé)
Branch Specifier: */master
Script Path: Jenkinsfile
```

### 3. Webhook GitHub (optionnel)

**Sur GitHub:**
`Settings` → `Webhooks` → `Add webhook`

```
Payload URL: http://<jenkins-url>/github-webhook/
Content type: application/json
Events: Just the push event
Active: ✅
```

---

## 🌍 Variables d'environnement

### Variables systèmes Jenkins

**Navigate to:** `Manage Jenkins` → `Configure System` → `Global properties` → `Environment variables`

```
SELENIUM_HEADLESS=true
CHROME_BIN=/usr/bin/google-chrome
GECKODRIVER_PATH=/usr/local/bin/geckodriver
```

### Variables dans le Jenkinsfile

Les variables suivantes sont configurées dans le `Jenkinsfile`:

```groovy
environment {
    APP_NAME = 'rhdemo-api'
    APP_VERSION = '0.0.1-SNAPSHOT'
    TEST_PORT = '9000'
    TEST_PROJECT_PATH = '../rhDemoAPITestIHM'
}
```

---

## 📧 Configuration des notifications

### 1. Configuration Email

**Navigate to:** `Manage Jenkins` → `Configure System` → `Extended E-mail Notification`

```
SMTP server: smtp.gmail.com
SMTP Port: 587
Use SSL/TLS: ✅
Credentials: <email-credentials>
Default user e-mail suffix: @example.com
```

**Test de la configuration:**
```
Default Recipients: team@example.com
```

### 2. Configuration Slack

**Navigate to:** `Manage Jenkins` → `Configure System` → `Slack`

#### Étape 1: Créer une app Slack
1. Aller sur https://api.slack.com/apps
2. Créer une nouvelle app "Jenkins RHDemo"
3. Activer "Incoming Webhooks"
4. Créer un webhook pour le channel `#rhdemo-ci`
5. Copier le webhook URL

#### Étape 2: Configurer Jenkins
```
Workspace: <votre-workspace-slack>
Credential: <slack-token>
Default channel: #rhdemo-ci
Test Connection: ✅
```

#### Étape 3: Ajouter le credential Slack

**Type:** Secret text
```
ID: slack-token
Secret: <votre-webhook-url>
Description: Slack Webhook for RHDemo CI
```

---

## 🔧 Configuration SonarQube (optionnel)

### 1. Configuration du serveur SonarQube

**Navigate to:** `Manage Jenkins` → `Configure System` → `SonarQube servers`

```
Nom: SonarQube
Server URL: http://localhost:9001
Server authentication token: <token-sonarqube>
```

### 2. Créer un token SonarQube

**Sur SonarQube:**
`Administration` → `Security` → `Users` → `Generate Token`

```
Token name: jenkins-rhdemo
Type: Global Analysis Token
```

### 3. Ajouter le credential dans Jenkins

**Type:** Secret text
```
ID: sonarqube-token
Secret: <token-généré>
Description: SonarQube Token
```

---

## 🎭 Configuration des agents Jenkins (optionnel)

### Agent pour tests Selenium

Si vous utilisez un agent dédié pour les tests Selenium:

**Navigate to:** `Manage Jenkins` → `Manage Nodes and Clouds` → `New Node`

```
Node name: selenium-agent
Number of executors: 2
Remote root directory: /home/jenkins
Labels: selenium linux
Launch method: Launch agent via SSH
```

**Modifier le Jenkinsfile:**
```groovy
pipeline {
    agent {
        label 'selenium'
    }
    // ...
}
```

---

## 🐳 Configuration Docker (alternative)

### Option 1: Pipeline avec agent Docker

**Jenkinsfile avec Docker:**
```groovy
pipeline {
    agent {
        docker {
            image 'maven:3.9-eclipse-temurin-21'
            args '-v $HOME/.m2:/root/.m2'
        }
    }
    // ...
}
```

### Option 2: Build de l'image Docker

**Ajouter au Jenkinsfile:**
```groovy
stage('🐳 Build Docker Image') {
    steps {
        sh '''
            docker build -t rhdemo-api:${APP_VERSION} .
            docker tag rhdemo-api:${APP_VERSION} rhdemo-api:latest
        '''
    }
}

stage('📤 Push Docker Image') {
    steps {
        withDockerRegistry([credentialsId: 'docker-hub', url: '']) {
            sh 'docker push rhdemo-api:${APP_VERSION}'
        }
    }
}
```

---

## 📊 Configuration des rapports

### 1. JaCoCo Coverage

**Navigate to:** Job → `Configure` → `Post-build Actions` → `Record JaCoCo coverage report`

```
Path to exec files: **/target/jacoco.exec
Path to class directories: **/target/classes
Path to source directories: **/src/main/java
```

### 2. HTML Reports

Les rapports HTML sont publiés automatiquement via le plugin HTML Publisher dans le Jenkinsfile:

```groovy
publishHTML([
    reportDir: 'target/site/jacoco',
    reportFiles: 'index.html',
    reportName: 'Code Coverage'
])
```

---

## 🚨 Troubleshooting

### Problème 1: Java version incorrecte

**Erreur:**
```
Error: Could not find or load main class
Caused by: java.lang.UnsupportedClassVersionError
```

**Solution:**
- Vérifier que JDK 21 est configuré dans `Global Tool Configuration`
- Vérifier la variable `JAVA_HOME` sur l'agent Jenkins

### Problème 2: Selenium ne démarre pas

**Erreur:**
```
WebDriverException: Chrome not reachable
```

**Solution:**
```bash
# Installer Chrome sur l'agent Jenkins
sudo apt-get update
sudo apt-get install -y google-chrome-stable

# Ou utiliser le mode headless
export SELENIUM_HEADLESS=true
```

### Problème 3: Application test ne démarre pas

**Erreur:**
```
Port 9000 already in use
```

**Solution:**
- Vérifier qu'aucun processus n'utilise le port 9000
- Nettoyer les processus zombies:
```bash
pkill -f rhdemo
lsof -ti:9000 | xargs kill -9
```

### Problème 4: Tests Selenium échouent

**Erreur:**
```
Element not found
```

**Solution:**
- Augmenter les timeouts dans `TestConfig.java`
- Vérifier que l'application est bien démarrée avant les tests
- Activer les screenshots pour déboguer

### Problème 5: Maven download lent

**Solution:**
- Configurer un mirror Maven local:
```xml
<!-- Dans settings.xml -->
<mirrors>
    <mirror>
        <id>nexus</id>
        <mirrorOf>*</mirrorOf>
        <url>http://nexus.local:8081/repository/maven-public/</url>
    </mirror>
</mirrors>
```

### Problème 6: Credentials non trouvés

**Erreur:**
```
groovy.lang.MissingPropertyException: No such property: credentials
```

**Solution:**
- Vérifier que les credentials sont créés dans Jenkins
- Vérifier les IDs des credentials dans le Jenkinsfile
- Les IDs sont sensibles à la casse

---

## 📝 Checklist de configuration

### Avant le premier build

- [ ] Java 21 installé et configuré
- [ ] Maven configuré (ou wrapper présent)
- [ ] Git configuré
- [ ] Tous les plugins installés
- [ ] Credentials Keycloak créés
- [ ] Credentials base de données créés
- [ ] Credentials serveurs créés
- [ ] SonarQube configuré (optionnel)
- [ ] Notifications email configurées
- [ ] Notifications Slack configurées (optionnel)
- [ ] Job Pipeline créé
- [ ] Webhook GitHub configuré (optionnel)
- [ ] Chrome/Firefox installé sur agent
- [ ] Projet rhDemoAPITestIHM cloné à côté de rhdemo

### Après le premier build

- [ ] Build réussi
- [ ] Tests unitaires passent
- [ ] Tests Selenium passent
- [ ] Rapports JaCoCo générés
- [ ] Notifications reçues
- [ ] JAR archivé
- [ ] Pas de processus zombie

---

## 🎓 Exemples de commandes Jenkins CLI

### Déclencher un build

```bash
java -jar jenkins-cli.jar -s http://localhost:8080/ build RHDemo-API-Pipeline \
  -p DEPLOY_ENV=staging \
  -p RUN_SELENIUM_TESTS=true
```

### Récupérer les logs

```bash
java -jar jenkins-cli.jar -s http://localhost:8080/ console RHDemo-API-Pipeline
```

### Lister les jobs

```bash
java -jar jenkins-cli.jar -s http://localhost:8080/ list-jobs
```

---

## 📚 Ressources supplémentaires

- [Documentation Jenkins Pipeline](https://www.jenkins.io/doc/book/pipeline/)
- [Jenkins Best Practices](https://www.jenkins.io/doc/book/pipeline/jenkinsfile/#best-practices)
- [SonarQube Integration](https://docs.sonarqube.org/latest/analysis/scan/sonarscanner-for-jenkins/)
- [Selenium Grid avec Jenkins](https://www.selenium.dev/documentation/grid/)

---

**Date de création:** 27 octobre 2025  
**Version:** 1.0  
**Projet:** RHDemo API CI/CD
