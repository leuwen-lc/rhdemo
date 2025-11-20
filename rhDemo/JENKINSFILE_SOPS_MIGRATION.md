# Migration SOPS - Résumé des Modifications

## Vue d'ensemble

Le Jenkinsfile a été migré pour utiliser **SOPS (Secrets OPerationS)** au lieu des credentials Jenkins pour la gestion des secrets. Cette approche offre plusieurs avantages :

✅ **Secrets versionnés chiffrés** dans Git  
✅ **Auditabilité complète** des modifications de secrets  
✅ **Déchiffrement à la demande** pendant le pipeline  
✅ **Rotation facile** des clés et secrets  
✅ **Pas de dépendance** aux credentials Jenkins manuels  

## Modifications apportées

### 1. Section `environment` (lignes 7-23)

#### Avant
```groovy
environment {
    RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET = credentials('keycloak-client-secret')
    RHDEMO_DATASOURCE_PASSWORD_H2 = credentials('h2-db-password')
    RHDEMO_DATASOURCE_PASSWORD_PG = credentials('postgres-db-password')
    STAGING_SERVER = credentials('staging-server-url')
    PROD_SERVER = credentials('production-server-url')
}
```

#### Après
```groovy
environment {
    SECRETS_FILE = 'secrets/secrets-staging.yml'
    SECRETS_DECRYPTED = 'secrets/secrets-decrypted.yml'
    SOPS_AGE_KEY_FILE = credentials('sops-age-key')
}
```

**Impact** : Un seul credential Jenkins requis (`sops-age-key`) au lieu de 5+

### 2. Nouveau stage : `🔐 Déchiffrement Secrets SOPS` (après Checkout)

Un nouveau stage a été ajouté pour gérer le déchiffrement des secrets :

```groovy
stage('🔐 Déchiffrement Secrets SOPS') {
    steps {
        // 1. Installation SOPS 3.8.1
        // 2. Installation yq (YAML parser)
        // 3. Déchiffrement du fichier de secrets
        // 4. Extraction des valeurs avec yq
        // 5. Export vers secrets/env-vars.sh
    }
    post {
        always {
            // Suppression du fichier déchiffré pour sécurité
            sh 'rm -f ${SECRETS_DECRYPTED} || true'
        }
    }
}
```

**Fonctionnalités** :
- Installation automatique de SOPS et yq si absents
- Déchiffrement sécurisé avec clé Age
- Extraction des valeurs vers un fichier shell
- Nettoyage automatique du fichier déchiffré

### 3. Stages modifiés (ajout de `source secrets/env-vars.sh`)

Tous les stages utilisant des secrets ont été modifiés pour charger le fichier d'environnement :

#### Stages concernés :

1. **🔍 Vérification Environnement** (ligne ~130)
2. **📦 Compilation Backend** (ligne ~150)
3. **📦 Package Complet** (ligne ~175)
4. **🧪 Tests Unitaires** (ligne ~195)
5. **🔍 Analyse SonarQube** (ligne ~220)
6. **📈 Couverture de Code** (ligne ~245)
7. **🚀 Démarrage App Test** (ligne ~270)
8. **🔒 Scan Vulnérabilités** (ligne ~365)
9. **🎭 Déploiement Staging** (ligne ~425)
10. **💨 Tests de Fumée Staging** (ligne ~450)
11. **💾 Backup Base de Données** (ligne ~500)
12. **🌐 Déploiement Production** (ligne ~520)
13. **✅ Vérification Post-Déploiement** (ligne ~550)

#### Pattern appliqué :

**Avant** :
```groovy
sh './mvnw test'
```

**Après** :
```groovy
sh '''
    # Charger les secrets
    source secrets/env-vars.sh
    ./mvnw test
'''
```

### 4. Support des URLs de serveurs (lignes ~105-115)

Ajout de l'extraction conditionnelle des URLs de serveurs depuis le fichier de secrets :

```groovy
# Exporter les URLs des serveurs si elles existent
if yq eval '.rhdemo.servers.staging' ${SECRETS_DECRYPTED} > /dev/null 2>&1; then
    echo "export STAGING_SERVER=$(yq eval '.rhdemo.servers.staging' ${SECRETS_DECRYPTED})" >> secrets/env-vars.sh
fi

if yq eval '.rhdemo.servers.production' ${SECRETS_DECRYPTED} > /dev/null 2>&1; then
    echo "export PROD_SERVER=$(yq eval '.rhdemo.servers.production' ${SECRETS_DECRYPTED})" >> secrets/env-vars.sh
fi
```

**Impact** : Les URLs de serveurs peuvent maintenant être gérées dans le fichier de secrets chiffré

### 5. Post-actions améliorées (lignes ~575-590)

Ajout du nettoyage des fichiers sensibles :

**Avant** :
```groovy
sh '''
    # Arrêt de l'application test
    if [ -f app-test.pid ]; then
        kill $(cat app-test.pid) 2>/dev/null || true
        rm app-test.pid
    fi
    rm -f app-test.log
'''
```

**Après** :
```groovy
sh '''
    # Supprimer les fichiers de secrets déchiffrés
    rm -f secrets/env-vars.sh secrets/secrets-decrypted.yml || true
    
    # Arrêt de l'application test
    if [ -f app-test.pid ]; then
        kill $(cat app-test.pid) 2>/dev/null || true
        rm app-test.pid
    fi
    rm -f app-test.log
'''
```

## Variables d'environnement disponibles

Après le stage de déchiffrement, les variables suivantes sont disponibles dans `secrets/env-vars.sh` :

| Variable | Source dans secrets-staging.yml |
|----------|--------------------------------|
| `RHDEMO_DATASOURCE_PASSWORD_PG` | `.rhdemo.datasource.password.pg` |
| `RHDEMO_DATASOURCE_PASSWORD_H2` | `.rhdemo.datasource.password.h2` |
| `RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET` | `.rhdemo.client.registration.keycloak.client.secret` |
| `KEYCLOAK_DB_PASSWORD` | `.keycloak.db.password` |
| `KEYCLOAK_ADMIN_PASSWORD` | `.keycloak.admin.password` |
| `KEYCLOAK_ADMIN_USER` | `.keycloak.admin.user` |
| `RHDEMO_TEST_PWD_USER_ADMIN` | `.rhdemo.test.pwduseradmin` |
| `RHDEMO_TEST_PWD_USER_MAJ` | `.rhdemo.test.pwdusermaj` |
| `RHDEMO_TEST_PWD_USER_CONSULT` | `.rhdemo.test.pwduserconsult` |
| `STAGING_SERVER` | `.rhdemo.servers.staging` (si présent) |
| `PROD_SERVER` | `.rhdemo.servers.production` (si présent) |

## Structure du fichier secrets-staging.yml

```yaml
rhdemo:
    datasource:
        password:
            pg: ENC[AES256_GCM,...] # Chiffré par SOPS
            h2: ENC[AES256_GCM,...] # Chiffré par SOPS
    client:
        registration:
            keycloak:
                client:
                    secret: ENC[AES256_GCM,...] # Chiffré par SOPS
    servers:
        staging: staging.example.com # Peut être chiffré ou en clair
        production: prod.example.com # Peut être chiffré ou en clair
    test:
        # Mots de passe des utilisateurs de test Keycloak (staging)
        pwduseradmin: ENC[AES256_GCM,...] # admin (ROLE_admin)
        pwdusermaj: ENC[AES256_GCM,...] # manager (ROLE_consult + ROLE_MAJ)
        pwduserconsult: ENC[AES256_GCM,...] # consultant (ROLE_consult)

keycloak:
    db:
        password: ENC[AES256_GCM,...] # Mot de passe PostgreSQL Keycloak
    admin:
        user: ENC[AES256_GCM,...] # Utilisateur admin Keycloak
        password: ENC[AES256_GCM,...] # Mot de passe admin Keycloak
```

## Credentials Jenkins requis

### Avant la migration
- `keycloak-client-secret` (Secret text)
- `h2-db-password` (Secret text)
- `postgres-db-password` (Secret text)
- `staging-server-url` (Secret text)
- `production-server-url` (Secret text)

**Total : 5+ credentials**

### Après la migration
- `sops-age-key` (Secret file)

**Total : 1 credential**

## Sécurité renforcée

### Mécanismes de protection

1. **Chiffrement au repos** : Secrets chiffrés avec Age encryption dans Git
2. **Déchiffrement éphémère** : Fichier déchiffré supprimé immédiatement après extraction
3. **Nettoyage automatique** : `env-vars.sh` supprimé dans les post-actions
4. **Accès contrôlé** : Seule la clé Age privée permet le déchiffrement
5. **Auditabilité** : Toutes les modifications de secrets sont versionnées dans Git

### Cycle de vie des secrets

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Secrets chiffrés dans Git (secrets-staging.yml)         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Stage: Déchiffrement SOPS                               │
│    └─> Fichier temporaire déchiffré (30 secondes max)     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Extraction vers env-vars.sh                             │
│    └─> Variables disponibles pour les stages               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Utilisation dans les stages                             │
│    └─> source secrets/env-vars.sh                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Post-actions: Nettoyage complet                         │
│    └─> Suppression env-vars.sh + fichier déchiffré        │
└─────────────────────────────────────────────────────────────┘
```

## Migration des credentials existants

Si vous avez déjà des credentials Jenkins configurés :

1. **Récupérer les valeurs** depuis Jenkins (Credentials → cliquer sur chaque credential)
2. **Ajouter au fichier de secrets** :
   ```bash
   ./manage-secrets.sh edit secrets/secrets-staging.yml
   ```
3. **Vérifier la structure** :
   ```bash
   ./manage-secrets.sh validate secrets/secrets-staging.yml
   ```
4. **Créer le credential sops-age-key** dans Jenkins (voir JENKINS_SOPS_GUIDE.md)
5. **Tester le pipeline** avec un build de test
6. **Supprimer les anciens credentials** Jenkins une fois validé

## Compatibilité

### Version SOPS
- **Installée automatiquement** : 3.8.1
- **Format de chiffrement** : AES256_GCM

### Version yq
- **Installée automatiquement** : latest
- **Utilisateur** : mikefarah/yq (YAML parser en Go)

### Prérequis Jenkins
- **Credential** : `sops-age-key` (Secret file contenant la clé Age privée)
- **Plugins** : Aucun plugin supplémentaire requis (utilise binaires standalone)

## Rollback (retour en arrière)

En cas de problème, pour revenir à l'ancienne version avec credentials Jenkins :

1. **Restaurer l'ancienne section environment** :
   ```groovy
   environment {
       RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET = credentials('keycloak-client-secret')
       // ... autres credentials
   }
   ```

2. **Supprimer le stage de déchiffrement SOPS**

3. **Retirer `source secrets/env-vars.sh`** de tous les stages

4. **Reconfigurer les credentials Jenkins** manuellement

**Note** : Un backup du Jenkinsfile original est recommandé avant migration.

## Tests recommandés

Après la migration, tester les scénarios suivants :

1. ✅ **Build complet** : `mvnw package`
2. ✅ **Tests unitaires** : Vérifier accès base H2
3. ✅ **Tests Selenium** : Vérifier démarrage app test
4. ✅ **Analyse SonarQube** : Si activé
5. ✅ **Déploiement staging** : Si configuré
6. ✅ **Scan sécurité** : OWASP dependency check

## Documentation associée

- **Guide complet SOPS + Jenkins** : [JENKINS_SOPS_GUIDE.md](JENKINS_SOPS_GUIDE.md)
- **Script de gestion des secrets** : [manage-secrets.sh](manage-secrets.sh)
- **Exemple de fichier secrets** : [secrets/secrets-example.yml](secrets/secrets-example.yml)
- **Infrastructure Jenkins** : [infra/README.md](infra/README.md)

## Support

En cas de problème avec la migration SOPS :

1. Vérifier les logs du stage `🔐 Déchiffrement Secrets SOPS`
2. Valider le fichier de secrets localement : `./manage-secrets.sh validate`
3. Vérifier le credential Jenkins `sops-age-key`
4. Consulter le guide de dépannage : [JENKINS_SOPS_GUIDE.md#dépannage](JENKINS_SOPS_GUIDE.md)

## Migration des mots de passe utilisateurs de test

### Contexte

Les mots de passe des utilisateurs Keycloak de test étaient auparavant **codés en dur** dans le Jenkinsfile :
- `admin123` pour l'utilisateur admin
- `manager123` pour l'utilisateur manager
- `consult123` pour l'utilisateur consultant

Ces mots de passe sont désormais **chiffrés dans SOPS** et injectés dynamiquement.

### Utilisateurs créés par rhDemoInitKeycloak

| Utilisateur | Variable | Rôles | Usage |
|-------------|----------|-------|-------|
| admin | `RHDEMO_TEST_PWD_USER_ADMIN` | ROLE_admin | Administration complète |
| manager | `RHDEMO_TEST_PWD_USER_MAJ` | ROLE_consult, ROLE_MAJ | **Tests Selenium (CRUD)** |
| consultant | `RHDEMO_TEST_PWD_USER_CONSULT` | ROLE_consult | Lecture seule |

### Injection dans rhDemoAPITestIHM

Le mot de passe de l'utilisateur `manager` est injecté dans les tests Selenium ([Jenkinsfile:943](Jenkinsfile#L943)) :

```bash
export RHDEMOTEST_USER="manager"
export RHDEMOTEST_PWD="${RHDEMO_TEST_PWD_USER_MAJ}"
```

**Pourquoi manager ?**
Cet utilisateur possède les deux rôles nécessaires pour tester toutes les opérations CRUD :
- `ROLE_consult` : lecture des employés
- `ROLE_MAJ` : création, modification, suppression

### Comment mettre à jour les mots de passe

```bash
# 1. Éditer le fichier chiffré
cd rhDemo
sops secrets/secrets-staging.yml

# 2. Modifier les valeurs
# rhdemo:
#   test:
#     pwdusermaj: nouveau_mot_de_passe

# 3. Sauvegarder (SOPS re-chiffre automatiquement)

# 4. Commiter
git add secrets/secrets-staging.yml
git commit -m "chore: rotation mot de passe utilisateur manager"
git push

# 5. Le prochain build Jenkins utilisera le nouveau mot de passe
```

### Sécurité

✅ **Mots de passe chiffrés** : Plus de mots de passe en clair dans le code
✅ **Rotation facilitée** : Modifier secrets-staging.yml et re-chiffrer
✅ **Audit trail** : Modifications tracées dans Git (fichier chiffré)
✅ **Protection logs** : Mots de passe non affichés grâce à `set +x` ([SECURITY_JENKINS_LOGS.md](SECURITY_JENKINS_LOGS.md))

## Changelog

| Date | Version | Modifications |
|------|---------|--------------|
| 2025-11-20 | 1.1.0 | Migration mots de passe utilisateurs test |
|  |  | - Ajout rhdemo.test.pwduseradmin/maj/consult |
|  |  | - Injection dans rhDemoInitKeycloak |
|  |  | - Injection dans rhDemoAPITestIHM (manager) |
|  |  | - Mise à jour secrets.yml.template |
|  |  | - Fix erreurs stage "Arrêt App Test" |
| 2025-01-07 | 1.0.0 | Migration initiale vers SOPS |
|  |  | - Suppression des 5+ credentials Jenkins |
|  |  | - Ajout stage déchiffrement SOPS |
|  |  | - Modification de 13 stages |
|  |  | - Support URLs serveurs |
|  |  | - Nettoyage automatique des secrets |
