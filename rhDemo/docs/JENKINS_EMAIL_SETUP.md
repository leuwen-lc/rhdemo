# Configuration des notifications email Jenkins

Guide complet pour configurer et diagnostiquer les notifications email dans le pipeline Jenkins rhDemo.

## Table des matières

- [Prérequis](#prérequis)
- [Configuration Jenkins (Global)](#configuration-jenkins-global)
- [Configuration du pipeline](#configuration-du-pipeline)
- [Diagnostic](#diagnostic)
- [Tests](#tests)
- [Dépannage](#dépannage)

---

## Prérequis

### Plugins Jenkins requis

1. **Email Extension Plugin** (Extended E-mail Notification)
   - Vérifier : Jenkins → Manage Jenkins → Manage Plugins
   - Installer si absent : Onglet "Available" → Rechercher "Email Extension"

2. **Mailer Plugin** (de base, normalement déjà installé)

### Serveur SMTP

Avoir accès à un serveur SMTP. Options courantes :

| Fournisseur | Serveur SMTP | Port | TLS/SSL |
|-------------|--------------|------|---------|
| Gmail | smtp.gmail.com | 587 | TLS |
| Outlook/Office365 | smtp.office365.com | 587 | TLS |
| Yahoo | smtp.mail.yahoo.com | 587 | TLS |
| SendGrid | smtp.sendgrid.net | 587 | TLS |
| Amazon SES | email-smtp.region.amazonaws.com | 587 | TLS |
| Serveur local | localhost ou IP | 25 | Aucun |

---

## Configuration Jenkins (Global)

### 1. Configuration SMTP de base

**Jenkins → Manage Jenkins → Configure System**

Descendre jusqu'à la section **"E-mail Notification"** :

```
┌─────────────────────────────────────────────┐
│ E-mail Notification                         │
├─────────────────────────────────────────────┤
│ SMTP server: smtp.gmail.com                 │
│ Default user e-mail suffix: @example.com    │
│                                             │
│ [x] Use SMTP Authentication                 │
│     User Name: jenkins@example.com          │
│     Password: ****************              │
│                                             │
│ [x] Use SSL                                 │
│ SMTP Port: 465                              │
│                                             │
│ Charset: UTF-8                              │
│                                             │
│ [ Test configuration by sending test e-mail]│
│ Test e-mail recipient: admin@example.com    │
│                                             │
└─────────────────────────────────────────────┘
```

#### Exemple : Configuration Gmail

```
SMTP server: smtp.gmail.com
[x] Use SMTP Authentication
    User Name: votre.compte@gmail.com
    Password: mot-de-passe-application (voir note ci-dessous)
[x] Use SSL
SMTP Port: 465
```

**⚠️ Note Gmail** : Utiliser un "App Password" (mot de passe d'application) :
1. Aller sur https://myaccount.google.com/security
2. Activer la validation en 2 étapes
3. Générer un mot de passe d'application
4. Utiliser ce mot de passe dans Jenkins (pas votre mot de passe Gmail principal)

#### Exemple : Configuration Outlook/Office365

```
SMTP server: smtp.office365.com
[x] Use SMTP Authentication
    User Name: votre.compte@outlook.com
    Password: votre-mot-de-passe
[x] Use TLS
SMTP Port: 587
```

### 2. Configuration Email Extension Plugin

**Jenkins → Manage Jenkins → Configure System**

Descendre jusqu'à la section **"Extended E-mail Notification"** :

```
┌─────────────────────────────────────────────┐
│ Extended E-mail Notification                │
├─────────────────────────────────────────────┤
│ SMTP server: smtp.gmail.com                 │
│ SMTP Port: 587                              │
│ Advanced...                                 │
│   [x] Use SMTP Authentication               │
│       User Name: jenkins@example.com        │
│       Password: ****************            │
│   [x] Use TLS                               │
│   Charset: UTF-8                            │
│                                             │
│ Default user e-mail suffix: @example.com    │
│                                             │
│ Default Content Type: HTML (text/html)      │
│                                             │
│ Default Recipients: team@example.com        │
│                                             │
│ Reply To List: noreply@example.com          │
│ Emergency reroute: admin@example.com        │
│                                             │
│ Precedence: bulk                            │
│                                             │
└─────────────────────────────────────────────┘
```

**Important** : Cliquer sur **"Advanced..."** pour voir toutes les options d'authentification.

### 3. Test de configuration

Dans la section "E-mail Notification" :

```
[ Test configuration by sending test e-mail ]
Test e-mail recipient: votre.email@example.com
[Envoyer]
```

Vérifier la réception de l'email de test.

---

## Configuration du pipeline

### 1. Ajouter la variable NOTIFICATION_EMAIL

Éditer [Jenkinsfile](../Jenkinsfile#L9-L40), dans la section `environment` :

```groovy
environment {
    // ... autres variables ...

    // Configuration notifications
    NOTIFICATION_EMAIL = 'team@example.com'  // ← AJOUTER CETTE LIGNE
}
```

**Ou** utiliser un paramètre Jenkins Credential :

```groovy
environment {
    // ... autres variables ...

    // Configuration notifications (depuis Jenkins credentials)
    NOTIFICATION_EMAIL = credentials('notification-email')
}
```

Pour créer le credential :
1. Jenkins → Manage Jenkins → Manage Credentials
2. (global) → Add Credentials
3. Kind : **Secret text**
4. Secret : `team@example.com`
5. ID : `notification-email`
6. Description : Email pour notifications build

### 2. Configuration actuelle du pipeline

Le Jenkinsfile utilise déjà `emailext` dans les sections `post` :

#### Success (ligne 1359-1371)

```groovy
success {
    emailext(
        subject: "✅ BUILD SUCCESS - RHDemo API #${env.BUILD_NUMBER}",
        body: """
            Le build de RHDemo API a réussi !

            Branch: ${env.BRANCH_NAME}
            Commit: ${env.GIT_COMMIT}
            Déploiement: ${params.DEPLOY_ENV}

            Voir les détails: ${env.BUILD_URL}
        """,
        to: "${env.NOTIFICATION_EMAIL}"
    )
}
```

#### Failure (ligne 1380-1392)

```groovy
failure {
    emailext(
        subject: "❌ BUILD FAILED - RHDemo API #${env.BUILD_NUMBER}",
        body: """
            ⚠️ Le build de RHDemo API a échoué !

            Branch: ${env.BRANCH_NAME}
            Stage: ${env.STAGE_NAME}

            Voir les logs: ${env.BUILD_URL}console
        """,
        to: "${env.NOTIFICATION_EMAIL}",
        attachLog: true  // Attache les logs du build
    )
}
```

---

## Diagnostic

### Vérifier les logs Jenkins

1. **Console du build** :
   - Aller dans le build → Console Output
   - Rechercher "email" ou "notification"

2. **Logs système Jenkins** :
   - Jenkins → Manage Jenkins → System Log
   - Chercher les erreurs SMTP

### Commandes de diagnostic

```groovy
// Ajouter temporairement dans le Jenkinsfile pour débug
script {
    echo "NOTIFICATION_EMAIL = ${env.NOTIFICATION_EMAIL}"
    echo "Build URL = ${env.BUILD_URL}"
}
```

### Problèmes courants

#### 1. `NOTIFICATION_EMAIL` est `null` ou vide

**Symptôme** : Email non envoyé, aucune erreur visible

**Cause** : Variable `NOTIFICATION_EMAIL` non définie

**Solution** :
```groovy
environment {
    NOTIFICATION_EMAIL = 'votre.email@example.com'
}
```

#### 2. "Authentication failed"

**Symptôme** : Erreur SMTP dans les logs
```
javax.mail.AuthenticationFailedException: 535-5.7.8 Username and Password not accepted
```

**Causes possibles** :
- Mauvais identifiants SMTP
- Gmail : nécessite un "App Password" au lieu du mot de passe principal
- Outlook : 2FA activé, nécessite un mot de passe d'application

**Solution** :
- Vérifier les identifiants dans Jenkins → Configure System
- Gmail : créer un App Password
- Outlook : désactiver 2FA ou créer un mot de passe d'application

#### 3. "Connection timed out"

**Symptôme** :
```
javax.mail.MessagingException: Could not connect to SMTP host: smtp.gmail.com, port: 587
```

**Causes possibles** :
- Firewall bloque le port SMTP
- Mauvais port configuré
- Proxy non configuré

**Solution** :
```bash
# Tester la connectivité depuis Jenkins
telnet smtp.gmail.com 587

# Si timeout, vérifier le firewall
# Si refusé, vérifier le port
```

#### 4. "Must issue a STARTTLS command first"

**Symptôme** :
```
530 5.7.0 Must issue a STARTTLS command first
```

**Cause** : TLS/SSL mal configuré

**Solution** :
- Utiliser port 587 avec "Use TLS"
- OU port 465 avec "Use SSL"
- Ne PAS utiliser port 25 avec TLS

#### 5. Email envoyé mais non reçu

**Causes possibles** :
- Email dans spam/courrier indésirable
- Serveur SMTP nécessite validation du domaine (SPF/DKIM)
- Rate limiting SMTP

**Solution** :
- Vérifier le dossier spam
- Ajouter `noreply@jenkins.local` à la liste blanche
- Vérifier les quotas SMTP du serveur

---

## Tests

### Test manuel dans Jenkins Script Console

**Jenkins → Manage Jenkins → Script Console**

```groovy
import javax.mail.*
import javax.mail.internet.*

def sendTestEmail(String to) {
    def props = new Properties()
    props.put("mail.smtp.host", "smtp.gmail.com")
    props.put("mail.smtp.port", "587")
    props.put("mail.smtp.auth", "true")
    props.put("mail.smtp.starttls.enable", "true")

    def auth = new Authenticator() {
        protected PasswordAuthentication getPasswordAuthentication() {
            return new PasswordAuthentication("jenkins@example.com", "mot-de-passe-app")
        }
    }

    def session = Session.getInstance(props, auth)

    def message = new MimeMessage(session)
    message.setFrom(new InternetAddress("jenkins@example.com"))
    message.addRecipient(Message.RecipientType.TO, new InternetAddress(to))
    message.setSubject("Test email depuis Jenkins")
    message.setText("Ceci est un test depuis la console Jenkins")

    Transport.send(message)
    println("✅ Email envoyé avec succès à ${to}")
}

// Exécuter le test
sendTestEmail("votre.email@example.com")
```

### Test avec un pipeline simple

Créer un pipeline de test :

```groovy
pipeline {
    agent any

    environment {
        NOTIFICATION_EMAIL = 'votre.email@example.com'
    }

    stages {
        stage('Test') {
            steps {
                echo "Test email notification"
            }
        }
    }

    post {
        always {
            emailext(
                subject: "Test email Jenkins",
                body: "Ceci est un email de test",
                to: "${env.NOTIFICATION_EMAIL}"
            )
        }
    }
}
```

---

## Recommandations

### Pour un environnement de production

1. **Utiliser Jenkins Credentials** pour stocker les mots de passe SMTP
2. **Configurer plusieurs destinataires** :
   ```groovy
   to: "team@example.com, admin@example.com"
   ```
3. **Ajouter des triggers conditionnels** :
   ```groovy
   post {
       failure {
           emailext(
               subject: "❌ BUILD FAILED",
               body: "...",
               to: "${env.NOTIFICATION_EMAIL}",
               recipientProviders: [
                   [$class: 'DevelopersRecipientProvider'],
                   [$class: 'CulpritsRecipientProvider']
               ]
           )
       }
   }
   ```
4. **Utiliser des templates HTML** pour des emails plus riches
5. **Configurer Reply-To** pour faciliter les réponses

### Sécurité

- ❌ Ne jamais hardcoder de mots de passe dans le Jenkinsfile
- ✅ Utiliser Jenkins Credentials pour les secrets
- ✅ Utiliser des App Passwords au lieu de mots de passe principaux
- ✅ Limiter les permissions des comptes email de service

---

## Checklist de configuration

- [ ] Email Extension Plugin installé
- [ ] SMTP configuré dans Jenkins → Configure System
- [ ] Test email envoyé depuis Jenkins (configuration de base)
- [ ] Variable `NOTIFICATION_EMAIL` définie dans le Jenkinsfile
- [ ] Build test exécuté pour vérifier l'envoi
- [ ] Email reçu (vérifier spam si nécessaire)
- [ ] Credentials SMTP stockés de manière sécurisée

---

## Ressources

- **Email Extension Plugin** : https://plugins.jenkins.io/email-ext/
- **Gmail App Passwords** : https://support.google.com/accounts/answer/185833
- **Outlook App Passwords** : https://support.microsoft.com/account-billing/manage-app-passwords
- **Jenkins Email Notification** : https://www.jenkins.io/doc/book/pipeline/jenkinsfile/#post

## Voir aussi

- [Jenkinsfile](../Jenkinsfile) - Configuration du pipeline
