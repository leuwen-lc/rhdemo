# Guide d'Intégration SOPS avec Jenkins

## Vue d'ensemble

Ce guide explique comment utiliser SOPS (Secrets OPerationS) avec le Jenkinsfile pour gérer de manière sécurisée les secrets de l'application RHDemo.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     JENKINS PIPELINE                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Stage: Déchiffrement Secrets SOPS                      │
│     ├─ Installation SOPS 3.8.1                             │
│     ├─ Installation yq (YAML parser)                       │
│     ├─ Chargement clé Age depuis credential Jenkins        │
│     ├─ Déchiffrement secrets-staging.yml                   │
│     ├─ Extraction valeurs avec yq                          │
│     └─ Export vers secrets/env-vars.sh                     │
│                                                             │
│  2. Stages suivants                                        │
│     └─ source secrets/env-vars.sh avant chaque commande    │
│                                                             │
│  3. Post-Actions                                           │
│     └─ Nettoyage env-vars.sh et fichier déchiffré          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Prérequis

### 1. Clé Age pour SOPS

Vous devez avoir la clé privée Age correspondant au recipient configuré dans `secrets-staging.yml` :

```
age1fky4w0d9dq4yyvfcl2tdetnl24ryugsfvdu6g886ljaqm9z5y34s4wcnps
```

**Format de la clé privée** :
```
AGE-SECRET-KEY-1...votre_clé_privée...
```

### 2. Configuration Jenkins

#### A. Créer le credential pour la clé Age

1. Aller dans **Jenkins → Manage Jenkins → Credentials**
2. Sélectionner le domaine global (ou créer un domaine spécifique)
3. Cliquer sur **Add Credentials**
4. Configurer :
   - **Kind**: Secret file
   - **File**: Téléverser un fichier contenant la clé Age privée
   - **ID**: `sops-age-key`
   - **Description**: "SOPS Age Private Key for decrypting secrets"

**Exemple de fichier à téléverser** (`age-key.txt`) :
```
AGE-SECRET-KEY-1XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

#### B. Alternative : Secret text

Si vous préférez utiliser Secret text :

1. **Kind**: Secret text
2. **Secret**: Coller directement la clé Age
3. **ID**: `sops-age-key`

**Important** : Dans ce cas, modifier le Jenkinsfile pour écrire le secret dans un fichier :

```groovy
sh '''
    echo "${SOPS_AGE_KEY_FILE}" > /tmp/age-key.txt
    export SOPS_AGE_KEY_FILE="/tmp/age-key.txt"
    sops -d ${SECRETS_FILE} > ${SECRETS_DECRYPTED}
    rm -f /tmp/age-key.txt
'''
```

## Structure du fichier secrets-staging.yml

### Format actuel

```yaml
rhdemo:
    datasource:
        password:
            pg: ENC[...]
            h2: ENC[...]
    client:
        registration:
            keycloak:
                client:
                    secret: ENC[...]
    test:
        user: ENC[...]
        pwd: ENC[...]
```

### Ajout des URLs de serveurs

Pour utiliser les URLs de serveurs dans les stages de déploiement, ajoutez :

```yaml
rhdemo:
    datasource:
        password:
            pg: ENC[...]
            h2: ENC[...]
    client:
        registration:
            keycloak:
                client:
                    secret: ENC[...]
    servers:
        staging: staging.example.com
        production: prod.example.com
    test:
        user: ENC[...]
        pwd: ENC[...]
```

**Pour chiffrer les nouvelles valeurs** :

```bash
# Déchiffrer le fichier
sops secrets/secrets-staging.yml

# Ajouter les nouvelles sections (l'éditeur s'ouvrira)
# Enregistrer et fermer

# SOPS rechiffrera automatiquement les nouvelles valeurs
```

## Variables d'environnement exportées

Le stage de déchiffrement crée le fichier `secrets/env-vars.sh` avec :

```bash
export RHDEMO_DATASOURCE_PASSWORD_PG="valeur_déchiffrée"
export RHDEMO_DATASOURCE_PASSWORD_H2="valeur_déchiffrée"
export RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET="valeur_déchiffrée"

# Si présentes dans secrets-staging.yml
export STAGING_SERVER="valeur_déchiffrée_ou_claire"
export PROD_SERVER="valeur_déchiffrée_ou_claire"
```

## Utilisation dans les stages

Chaque stage nécessitant les secrets doit charger le fichier :

```groovy
stage('Exemple') {
    steps {
        sh '''
            # Charger les secrets
            source secrets/env-vars.sh
            
            # Utiliser les variables
            ./mvnw test
            # Ou
            curl http://${STAGING_SERVER}/health
        '''
    }
}
```

## Sécurité

### Fichiers nettoyés automatiquement

Le Jenkinsfile nettoie automatiquement les fichiers sensibles :

1. **Après déchiffrement** : `secrets/secrets-decrypted.yml` supprimé immédiatement
2. **Post-actions always** : `secrets/env-vars.sh` supprimé à la fin du pipeline

### Bonnes pratiques

✅ **À FAIRE** :
- Utiliser SOPS pour chiffrer tous les secrets
- Versionner `secrets-staging.yml` chiffré dans Git
- Rotation régulière des secrets
- Limiter l'accès au credential Jenkins `sops-age-key`
- Utiliser des clés Age différentes par environnement

❌ **À ÉVITER** :
- Commit de fichiers déchiffrés
- Affichage des secrets dans les logs (`echo $SECRET`)
- Partage de la clé Age par email/chat
- Réutilisation de la même clé pour tous les environnements

## Ajout d'un nouveau secret

### 1. Déchiffrer le fichier

```bash
cd /home/leno-vo/git/repository/rhDemo
export SOPS_AGE_KEY_FILE=/path/to/your/age-key.txt
sops secrets/secrets-staging.yml
```

### 2. Ajouter la nouvelle valeur

L'éditeur s'ouvre. Ajoutez votre nouvelle section :

```yaml
rhdemo:
    # ... sections existantes ...
    new_section:
        api_key: ma-nouvelle-cle-secrete
```

### 3. Enregistrer et fermer

SOPS chiffrera automatiquement la nouvelle valeur.

### 4. Mettre à jour le Jenkinsfile

Dans le stage `🔐 Déchiffrement Secrets SOPS`, ajoutez l'extraction :

```groovy
echo "export NEW_API_KEY=$(yq eval '.rhdemo.new_section.api_key' ${SECRETS_DECRYPTED})" >> secrets/env-vars.sh
```

### 5. Utiliser dans un stage

```groovy
sh '''
    source secrets/env-vars.sh
    curl -H "X-API-Key: ${NEW_API_KEY}" https://api.example.com
'''
```

## Dépannage

### Erreur : "Failed to get the data key required to decrypt the SOPS file"

**Cause** : Clé Age incorrecte ou non trouvée

**Solution** :
1. Vérifier que le credential Jenkins `sops-age-key` existe
2. Vérifier que la clé correspond au recipient dans `sops.age.recipient`
3. Vérifier le format de la clé (doit commencer par `AGE-SECRET-KEY-1`)

### Erreur : "command not found: yq"

**Cause** : Installation de yq a échoué

**Solution** :
1. Vérifier l'accès réseau depuis Jenkins
2. Installer yq manuellement sur l'agent Jenkins :
   ```bash
   wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
   sudo mv yq_linux_amd64 /usr/local/bin/yq
   sudo chmod +x /usr/local/bin/yq
   ```

### Variables d'environnement vides

**Cause** : Fichier `env-vars.sh` non sourcé ou mal généré

**Solution** :
1. Vérifier les logs du stage de déchiffrement
2. Vérifier que `source secrets/env-vars.sh` est bien présent dans le stage
3. Déboguer avec :
   ```groovy
   sh '''
       source secrets/env-vars.sh
       echo "PG Password présent: ${RHDEMO_DATASOURCE_PASSWORD_PG:+OUI}"
   '''
   ```

### Permissions insuffisantes pour installer SOPS/yq

**Cause** : L'utilisateur Jenkins n'a pas les droits sudo

**Solution** : Pré-installer SOPS et yq dans l'image Docker Jenkins

Dans `infra/Dockerfile.jenkins`, ajouter :

```dockerfile
# Installation SOPS
RUN wget -q https://github.com/mozilla/sops/releases/download/v3.8.1/sops-v3.8.1.linux.amd64 \
    && mv sops-v3.8.1.linux.amd64 /usr/local/bin/sops \
    && chmod +x /usr/local/bin/sops

# Installation yq
RUN wget -q https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
    && mv yq_linux_amd64 /usr/local/bin/yq \
    && chmod +x /usr/local/bin/yq
```

Puis reconstruire l'image Jenkins.

## Migration depuis credentials Jenkins

### Avant (credentials Jenkins)

```groovy
environment {
    KEYCLOAK_SECRET = credentials('keycloak-client-secret')
}
```

### Après (SOPS)

1. Ajouter le secret dans `secrets-staging.yml` :
   ```bash
   sops secrets/secrets-staging.yml
   # Ajouter la valeur dans l'éditeur
   ```

2. Extraire dans le stage de déchiffrement :
   ```groovy
   echo "export KEYCLOAK_SECRET=$(yq eval '.rhdemo.client.registration.keycloak.client.secret' ${SECRETS_DECRYPTED})" >> secrets/env-vars.sh
   ```

3. Utiliser dans les stages :
   ```groovy
   sh '''
       source secrets/env-vars.sh
       echo "Secret chargé"
   '''
   ```

4. Supprimer le credential Jenkins obsolète

## Environnements multiples

Pour gérer plusieurs environnements, créer plusieurs fichiers :

```
secrets/
├── secrets-dev.yml       (chiffré)
├── secrets-staging.yml   (chiffré)
└── secrets-prod.yml      (chiffré)
```

Modifier l'environment dans le Jenkinsfile :

```groovy
environment {
    SECRETS_FILE = "secrets/secrets-${params.DEPLOY_ENV}.yml"
}
```

Utiliser des clés Age différentes par environnement pour une meilleure sécurité.

## Ressources

- **SOPS Documentation** : https://github.com/mozilla/sops
- **Age Encryption** : https://github.com/FiloSottile/age
- **yq Documentation** : https://github.com/mikefarah/yq
- **Jenkins Credentials** : https://www.jenkins.io/doc/book/using/using-credentials/

## Support

En cas de problème :
1. Vérifier les logs Jenkins du stage de déchiffrement
2. Valider manuellement le déchiffrement : `sops -d secrets/secrets-staging.yml`
3. Vérifier les permissions sur les fichiers de secrets
4. Consulter les sections de dépannage ci-dessus
