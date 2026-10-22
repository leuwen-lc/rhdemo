---
statut: actif
verifie_le: 2026-10-22
sources:
  - rhDemo/secrets/secrets-rhdemo.yml
  - rhDemo/secrets/secrets-ephemere.yml
  - rhDemo/secrets/secrets-stagingkub.yml
---

# Installation et configuration de SOPS/AGE

Guide complet pour installer et configurer SOPS (Secrets OPerationS) avec AGE pour chiffrer/déchiffrer les secrets du projet rhDemo.

## Table des matières

- [Qu'est-ce que SOPS ?](#quest-ce-que-sops-)
- [Installation](#installation)
  - [Linux](#linux)
  - [macOS](#macos)
- [Configuration AGE](#configuration-age)
- [Utilisation avec rhDemo](#utilisation-avec-rhdemo)
- [Commandes courantes](#commandes-courantes)
- [Dépannage](#dépannage)

---

## Qu'est-ce que SOPS ?

**SOPS** (Secrets OPerationS) est un outil de Mozilla permettant de chiffrer des fichiers de configuration (YAML, JSON, ENV, etc.) tout en gardant les clés en clair et seules les valeurs chiffrées.

**AGE** est un outil de chiffrement simple et moderne utilisé comme backend pour SOPS.

### Avantages

- ✅ Fichiers secrets versionnés dans Git (chiffrés)
- ✅ Seules les valeurs sont chiffrées (structure YAML lisible)
- ✅ Plusieurs personnes peuvent avoir accès (multi-clés)
- ✅ Intégration CI/CD facile (Jenkins, GitHub Actions, etc.)

### Exemple

```yaml
# secrets-ephemere.yml (avant chiffrement)
rhdemo:
  datasource:
    password:
      pg: monMotDePasseSecret123

# secrets-ephemere.yml (après chiffrement SOPS)
rhdemo:
  datasource:
    password:
      pg: ENC[AES256_GCM,data:x7k2...,iv:...,tag:...,type:str]
sops:
  kms: []
  gcp_kms: []
  azure_kv: []
  age:
    - recipient: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      enc: |
        -----BEGIN AGE ENCRYPTED FILE-----
        ...
        -----END AGE ENCRYPTED FILE-----
```

---

## Installation

### Linux

#### 1. Installer SOPS

```bash
# Télécharger la dernière version depuis GitHub
SOPS_VERSION="3.9.0"
wget "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.amd64" -O /tmp/sops

# Rendre exécutable et déplacer vers /usr/local/bin
chmod +x /tmp/sops
sudo mv /tmp/sops /usr/local/bin/sops

# Vérifier l'installation
sops --version
```

#### 2. Installer AGE

```bash
# Télécharger la dernière version depuis GitHub
AGE_VERSION="1.1.1"
wget "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-amd64.tar.gz" -O /tmp/age.tar.gz

# Extraire et installer
tar xzf /tmp/age.tar.gz -C /tmp
sudo mv /tmp/age/age /usr/local/bin/
sudo mv /tmp/age/age-keygen /usr/local/bin/

# Vérifier l'installation
age --version
age-keygen --version
```

#### Alternative : Installation via gestionnaire de paquets

**Ubuntu/Debian** :
```bash
# SOPS via snap
sudo snap install sops

# AGE via apt (nécessite ajout du PPA)
sudo apt install age
```

**Arch Linux** :
```bash
# Depuis les dépôts officiels
sudo pacman -S sops age
```

**Fedora/RHEL** :
```bash
# SOPS
sudo dnf install sops

# AGE
sudo dnf install age
```

### macOS

#### Via Homebrew (recommandé)

```bash
# Installer SOPS
brew install sops

# Installer AGE
brew install age

# Vérifier les installations
sops --version
age --version
```

#### Téléchargement manuel

```bash
# SOPS
SOPS_VERSION="3.9.0"
curl -LO "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.darwin.amd64"
chmod +x sops-v${SOPS_VERSION}.darwin.amd64
sudo mv sops-v${SOPS_VERSION}.darwin.amd64 /usr/local/bin/sops

# AGE
AGE_VERSION="1.1.1"
curl -LO "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-darwin-amd64.tar.gz"
tar xzf age-v${AGE_VERSION}-darwin-amd64.tar.gz
sudo mv age/age /usr/local/bin/
sudo mv age/age-keygen /usr/local/bin/
```

---

## Configuration AGE

### 1. Générer une paire de clés AGE

```bash
# Créer le répertoire pour les clés
mkdir -p ~/.config/sops/age

# Générer une nouvelle paire de clés
age-keygen -o ~/.config/sops/age/keys.txt

# Afficher la clé publique (recipient)
cat ~/.config/sops/age/keys.txt | grep "# public key:"
```

**Sortie attendue** :
```
# created: 2025-11-23T18:00:00+01:00
# public key: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AGE-SECRET-KEY-1YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
```

### 2. Configurer les variables d'environnement

Ajouter à votre `~/.bashrc`, `~/.zshrc`, ou `~/.profile` :

```bash
# Configuration SOPS/AGE
export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
```

Recharger le shell :
```bash
source ~/.bashrc  # ou ~/.zshrc
```

### 3. Protéger les clés privées

```bash
# Permissions restrictives sur les clés
chmod 600 ~/.config/sops/age/keys.txt

# Ajouter au .gitignore global si nécessaire
echo ".config/sops/age/keys.txt" >> ~/.gitignore_global
```

### 4. Partager la clé publique (recipient)

Pour permettre à d'autres personnes de chiffrer des secrets accessibles par vous :

```bash
# Récupérer votre clé publique
grep "public key:" ~/.config/sops/age/keys.txt

# Partager cette clé publique (age1...) avec l'équipe
# Elle sera ajoutée au fichier .sops.yaml du projet
```

---

## Utilisation avec rhDemo

### Structure des fichiers secrets

```
rhDemo/
├── secrets/
│   ├── secrets.yml.template           ← Template (commité)
│   ├── secrets-ephemere.yml.template   ← Template ephemere (commité)
│   ├── secrets-ephemere.yml            ← Secrets ephemere chiffrés SOPS (commité)
│   ├── secrets-rhdemo.yml             ← Secrets dev local non chiffrés (gitignore)
│   └── .sops.yaml                     ← Configuration SOPS (commité)
└── .sops.yaml                         ← Configuration SOPS racine (commité)
```

### Configuration SOPS du projet

Le fichier `.sops.yaml` définit les règles de chiffrement :

```yaml
# rhDemo/.sops.yaml
creation_rules:
  - path_regex: secrets/secrets-ephemere\.yml$
    age: >-
      age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx,
      age1yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
```

### Chiffrer un nouveau fichier

```bash
cd rhDemo/secrets

# Créer un fichier depuis le template
cp secrets-ephemere.yml.template secrets-ephemere-new.yml

# Éditer avec vos vrais secrets
vim secrets-ephemere-new.yml

# Chiffrer avec SOPS
sops --encrypt secrets-ephemere-new.yml > secrets-ephemere.yml

# Ou directement éditer et chiffrer
sops secrets-ephemere.yml
```

### Déchiffrer un fichier

```bash
cd rhDemo/secrets

# Déchiffrer et afficher (sans écrire sur disque)
sops --decrypt secrets-ephemere.yml

# Déchiffrer vers un fichier temporaire
sops --decrypt secrets-ephemere.yml > secrets-ephemere-decrypted.yml

# ⚠️ Ne jamais commiter le fichier déchiffré !
```

### Modifier un fichier chiffré

```bash
cd rhDemo/secrets

# SOPS ouvre l'éditeur avec le contenu déchiffré
# À la sauvegarde, re-chiffre automatiquement
sops secrets-ephemere.yml
```

### Ajouter un nouveau recipient (membre d'équipe)

```bash
cd rhDemo/secrets

# Méthode 1 : Éditer .sops.yaml et ajouter la nouvelle clé publique
vim ../.sops.yaml

# Méthode 2 : Utiliser updatekeys pour ajouter automatiquement
sops updatekeys secrets-ephemere.yml
```

---

## Commandes courantes

### Chiffrement/déchiffrement

```bash
# Chiffrer un fichier
sops --encrypt fichier.yml > fichier-encrypted.yml

# Déchiffrer un fichier
sops --decrypt fichier-encrypted.yml > fichier.yml

# Éditer un fichier chiffré (déchiffre → édite → re-chiffre)
sops fichier-encrypted.yml
```

### Extraction de valeurs spécifiques

```bash
# Extraire une valeur spécifique (avec yq intégré)
sops --decrypt secrets-ephemere.yml | yq eval '.rhdemo.datasource.password.pg' -

# Ou directement avec SOPS
sops --decrypt --extract '["rhdemo"]["datasource"]["password"]["pg"]' secrets-ephemere.yml
```

### Rotation des clés

```bash
# Ajouter un nouveau recipient et retirer l'ancien
sops rotate --add-age age1newkeyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
            --rm-age age1oldkeyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
            secrets-ephemere.yml
```

### Validation

```bash
# Vérifier qu'un fichier est bien chiffré
sops --decrypt secrets-ephemere.yml > /dev/null && echo "✅ Déchiffrement réussi"

# Afficher les métadonnées SOPS
sops --decrypt --extract '["sops"]' secrets-ephemere.yml
```

---

## Dépannage

### Erreur : "Failed to get the data key"

**Problème** : SOPS ne trouve pas la clé privée AGE.

**Solutions** :
```bash
# Vérifier que la variable d'environnement est définie
echo $SOPS_AGE_KEY_FILE

# Vérifier que le fichier existe
ls -lh ~/.config/sops/age/keys.txt

# Définir manuellement la variable
export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
```

### Erreur : "no valid age identity found"

**Problème** : La clé privée ne correspond pas au recipient du fichier chiffré.

**Solutions** :
```bash
# Vérifier votre clé publique
grep "public key:" ~/.config/sops/age/keys.txt

# Vérifier les recipients du fichier
sops --decrypt --extract '["sops"]["age"]' secrets-ephemere.yml

# Si votre clé n'est pas dans la liste, demander à quelqu'un qui a accès d'ajouter votre clé
```

### Erreur : "MAC mismatch"

**Problème** : Le fichier a été modifié manuellement (corruption).

**Solutions** :
```bash
# Restaurer depuis Git
git checkout secrets-ephemere.yml

# Ou re-chiffrer depuis le template
cp secrets-ephemere.yml.template secrets-ephemere-new.yml
vim secrets-ephemere-new.yml  # Éditer avec les vrais secrets
sops --encrypt secrets-ephemere-new.yml > secrets-ephemere.yml
```

### Performances lentes

**Problème** : SOPS est lent à chiffrer/déchiffrer.

**Solutions** :
```bash
# Utiliser AGE au lieu de PGP (déjà le cas dans rhDemo)
# AGE est beaucoup plus rapide que PGP

# Vérifier que vous utilisez bien AGE
sops --decrypt --extract '["sops"]' secrets-ephemere.yml | grep age
```

### Permission denied sur les clés

**Problème** : Les permissions du fichier de clés sont trop ouvertes.

**Solution** :
```bash
# Restreindre les permissions
chmod 600 ~/.config/sops/age/keys.txt
```

---

## Workflow recommandé

### Pour un nouveau membre d'équipe

1. **Installer SOPS et AGE** (voir section Installation)

2. **Générer sa paire de clés** :
   ```bash
   mkdir -p ~/.config/sops/age
   age-keygen -o ~/.config/sops/age/keys.txt
   export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
   ```

3. **Partager sa clé publique** avec un membre ayant déjà accès :
   ```bash
   grep "public key:" ~/.config/sops/age/keys.txt
   # Envoyer : age1xxxxxx... (via canal sécurisé)
   ```

4. **Le membre existant ajoute la nouvelle clé** :
   ```bash
   cd rhDemo
   # Éditer .sops.yaml pour ajouter le nouveau recipient
   vim .sops.yaml

   # Mettre à jour le fichier chiffré pour inclure la nouvelle clé
   cd secrets
   sops updatekeys secrets-ephemere.yml

   # Commiter
   git add ../.sops.yaml secrets-ephemere.yml
   git commit -m "security: add new team member AGE key"
   git push
   ```

5. **Le nouveau membre peut maintenant déchiffrer** :
   ```bash
   git pull
   cd rhDemo/secrets
   sops --decrypt secrets-ephemere.yml
   ```

### Pour retirer l'accès d'un membre

```bash
cd rhDemo

# Éditer .sops.yaml pour retirer la clé publique du membre
vim .sops.yaml

# Rotation : retirer l'ancien recipient
cd secrets
sops rotate --rm-age age1oldkeyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
            secrets-ephemere.yml

# Commiter
git add ../.sops.yaml secrets-ephemere.yml
git commit -m "security: revoke access for former team member"
git push
```

---

## Intégration CI/CD (Jenkins)

Dans le [Jenkinsfile-CI](../Jenkinsfile-CI), SOPS est utilisé pour déchiffrer les secrets :

```groovy
stage('🔓 Déchiffrement SOPS des secrets') {
    environment {
        // Clé privée AGE stockée dans Jenkins credentials
        SOPS_AGE_KEY = credentials('sops-age-key-ephemere')
    }
    steps {
        sh '''
            # Export de la clé AGE pour SOPS
            export SOPS_AGE_KEY_FILE=/tmp/age-key.txt
            echo "${SOPS_AGE_KEY}" > ${SOPS_AGE_KEY_FILE}
            chmod 600 ${SOPS_AGE_KEY_FILE}

            # Déchiffrer le fichier
            sops --decrypt rhDemo/secrets/secrets-ephemere.yml > rhDemo/secrets/secrets-decrypted.yml

            # Nettoyer la clé temporaire
            shred -vfz -n 3 ${SOPS_AGE_KEY_FILE}
        '''
    }
}
```

**Configuration Jenkins** :
1. Aller dans Jenkins → Credentials → Add Credentials
2. Type : Secret file
3. ID : `sops-age-key-ephemere`
4. Uploader le fichier `~/.config/sops/age/keys.txt` du compte autorisé

---

## Bonnes pratiques

### ✅ À faire

- ✅ Utiliser des clés AGE différentes pour ephemere et production
- ✅ Sauvegarder votre clé privée AGE dans un gestionnaire de mots de passe
- ✅ Restreindre les permissions du fichier de clés (chmod 600)
- ✅ Ajouter plusieurs recipients au cas où (redondance)
- ✅ Documenter qui a accès à quels secrets
- ✅ Auditer régulièrement les accès

### ❌ À éviter

- ❌ Commiter des fichiers déchiffrés dans Git
- ❌ Partager sa clé privée AGE
- ❌ Stocker la clé privée en clair dans des fichiers non protégés
- ❌ Utiliser la même clé pour tous les environnements
- ❌ Oublier de retirer l'accès des anciens membres
- ❌ Éditer manuellement les fichiers chiffrés (toujours utiliser `sops`)

---

## Références

- **SOPS GitHub** : https://github.com/getsops/sops
- **AGE GitHub** : https://github.com/FiloSottile/age
- **Documentation SOPS** : https://github.com/getsops/sops#usage
- **AGE Specification** : https://age-encryption.org/

## Voir aussi

- [ENVIRONMENTS.md](../infra/ENVIRONMENTS.md) - Environnements rhDemo
