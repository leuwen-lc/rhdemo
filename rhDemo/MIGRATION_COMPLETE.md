# Migration SOPS - Fichiers Créés et Modifiés

## ✅ Migration Terminée

La migration du Jenkinsfile pour utiliser SOPS au lieu des credentials Jenkins est **complète**.

## 📝 Fichiers Modifiés

### 1. Jenkinsfile (racine du projet)
**Modifications** :
- ✅ Section `environment` : Suppression de 5+ credentials, ajout de `SOPS_AGE_KEY_FILE`
- ✅ Nouveau stage `🔐 Déchiffrement Secrets SOPS` (après Checkout)
- ✅ 13 stages modifiés avec `source secrets/env-vars.sh`
- ✅ Support des URLs de serveurs depuis secrets.yml
- ✅ Post-actions avec nettoyage des fichiers sensibles

**Lignes modifiées** : ~50 modifications sur ~690 lignes

### 2. .gitignore
**Ajouts** :
- `secrets/*-decrypted.yml` (fichiers déchiffrés)
- `secrets/env-vars.sh` (variables exportées)
- `secrets/*.txt` et `*.age-key` (clés privées)
- Exception pour `secrets/secrets-staging.yml` (fichier chiffré autorisé)

### 3. infra/README.md
**Ajouts** :
- Section "Gestion des secrets avec SOPS"
- Instructions pour configurer la clé Age dans Jenkins
- Liens vers la documentation SOPS

## 📄 Nouveaux Fichiers Créés

### Documentation

| Fichier | Description | Taille |
|---------|-------------|--------|
| `JENKINS_SOPS_GUIDE.md` | Guide complet d'intégration SOPS avec Jenkins | ~10KB |
| `JENKINSFILE_SOPS_MIGRATION.md` | Résumé détaillé des modifications apportées | ~8KB |
| `secrets/secrets-example.yml` | Template de fichier de secrets (non chiffré) | ~1KB |

### Scripts

| Fichier | Description | Permissions |
|---------|-------------|-------------|
| `manage-secrets.sh` | Script de gestion des secrets SOPS | `chmod +x` |

**Commandes disponibles** :
```bash
./manage-secrets.sh create-key    # Créer une clé Age
./manage-secrets.sh encrypt        # Chiffrer un fichier
./manage-secrets.sh edit          # Éditer secrets-staging.yml
./manage-secrets.sh view          # Afficher le contenu déchiffré
./manage-secrets.sh extract       # Extraire vers env-vars.sh
./manage-secrets.sh validate      # Valider la structure
./manage-secrets.sh rotate        # Rotation de clé
```

## 🔧 Configuration Requise

### 1. Installer SOPS et Age (si pas déjà fait)

```bash
# Installation SOPS
wget https://github.com/mozilla/sops/releases/download/v3.8.1/sops-v3.8.1.linux.amd64
chmod +x sops-v3.8.1.linux.amd64
sudo mv sops-v3.8.1.linux.amd64 /usr/local/bin/sops

# Installation Age
wget https://github.com/FiloSottile/age/releases/latest/download/age-v1.1.1-linux-amd64.tar.gz
tar xzf age-v1.1.1-linux-amd64.tar.gz
sudo mv age/age /usr/local/bin/
sudo mv age/age-keygen /usr/local/bin/

# Vérification
sops --version
age --version
```

### 2. Générer une clé Age (si pas déjà fait)

```bash
./manage-secrets.sh create-key
```

**Résultat** :
- Clé privée : `~/.config/sops/age/keys.txt`
- Clé publique (recipient) : Affiché dans la console

**⚠️ IMPORTANT** : Sauvegardez la clé privée dans un endroit sécurisé !

### 3. Ajouter les URLs de serveurs (optionnel)

```bash
# Éditer le fichier de secrets
./manage-secrets.sh edit secrets/secrets-staging.yml
```

Ajoutez cette section :
```yaml
rhdemo:
    # ... sections existantes ...
    servers:
        staging: staging.votredomaine.com
        production: prod.votredomaine.com
```

Enregistrez et fermez (SOPS rechiffrera automatiquement).

### 4. Configurer Jenkins

#### A. Ajouter le credential sops-age-key

1. Aller dans **Jenkins → Manage Jenkins → Credentials**
2. Cliquer sur **Add Credentials**
3. Configurer :
   - **Kind**: Secret file
   - **File**: Téléverser `~/.config/sops/age/keys.txt`
   - **ID**: `sops-age-key` (exactement ce nom)
   - **Description**: "SOPS Age Private Key for decrypting secrets"

#### B. Démarrer Jenkins (si pas déjà fait)

```bash
cd infra
./start-jenkins.sh
```

Accès : http://localhost:8080
- Utilisateur : `admin`
- Mot de passe : Défini dans `infra/.env` (défaut: `admin123`)

## 🧪 Tests

### 1. Valider le fichier de secrets

```bash
./manage-secrets.sh validate secrets/secrets-staging.yml
```

**Attendu** :
```
✅ Fichier valide ✓
✅ Déchiffrement réussi ✓
✅ Structure YAML valide ✓
✅ Tous les champs requis présents ✓
```

### 2. Tester l'extraction locale

```bash
./manage-secrets.sh extract secrets/secrets-staging.yml
source secrets/env-vars.sh
echo "PG Password présent: ${RHDEMO_DATASOURCE_PASSWORD_PG:+OUI}"
rm secrets/env-vars.sh
```

### 3. Lancer un build Jenkins

1. Aller dans Jenkins : http://localhost:8080
2. Créer un nouveau Pipeline
3. Pointer vers le Jenkinsfile du projet
4. Lancer un build

**Vérifications** :
- ✅ Stage `🔐 Déchiffrement Secrets SOPS` réussit
- ✅ Installation de SOPS et yq réussie
- ✅ Fichier `env-vars.sh` créé
- ✅ Stages suivants ont accès aux variables
- ✅ Nettoyage des fichiers sensibles dans les post-actions

## 📖 Documentation Complète

| Document | Contenu |
|----------|---------|
| [JENKINS_SOPS_GUIDE.md](JENKINS_SOPS_GUIDE.md) | Guide complet d'intégration SOPS |
| [JENKINSFILE_SOPS_MIGRATION.md](JENKINSFILE_SOPS_MIGRATION.md) | Résumé des modifications |
| [infra/README.md](infra/README.md#gestion-des-secrets-avec-sops) | Configuration Jenkins + SOPS |
| [manage-secrets.sh](manage-secrets.sh) --help | Aide du script de gestion |

## 🔒 Sécurité

### Fichiers à NE JAMAIS commiter

❌ `secrets/*-decrypted.yml` (fichiers déchiffrés)  
❌ `secrets/env-vars.sh` (variables exportées)  
❌ `~/.config/sops/age/keys.txt` (clé privée Age)  
❌ Tout fichier `*.age-key`  

### Fichiers sûrs à commiter

✅ `secrets/secrets-staging.yml` (fichier chiffré SOPS)  
✅ `secrets/secrets-example.yml` (template non chiffré)  
✅ `Jenkinsfile` (pas de secrets en clair)  
✅ `manage-secrets.sh` (script de gestion)  

## 🎯 Prochaines Étapes

1. **Tester le pipeline complet** avec un build Jenkins
2. **Ajouter les URLs de serveurs** si nécessaire (voir section 3 ci-dessus)
3. **Configurer les environnements multiples** (dev, staging, prod) si besoin :
   - Créer `secrets/secrets-dev.yml`
   - Créer `secrets/secrets-prod.yml`
   - Modifier le Jenkinsfile : `SECRETS_FILE = "secrets/secrets-${params.DEPLOY_ENV}.yml"`
4. **Rotation des secrets** : Utiliser `./manage-secrets.sh rotate`
5. **Supprimer les anciens credentials Jenkins** une fois la migration validée

## ❓ Aide

### Commandes utiles

```bash
# Afficher l'aide du script
./manage-secrets.sh help

# Voir le contenu déchiffré
./manage-secrets.sh view secrets/secrets-staging.yml

# Éditer le fichier
./manage-secrets.sh edit secrets/secrets-staging.yml

# Valider la structure
./manage-secrets.sh validate secrets/secrets-staging.yml
```

### Dépannage

**Erreur "Failed to get the data key"** :
- Vérifier que la clé Age est correcte
- Vérifier le credential Jenkins `sops-age-key`

**Variables vides dans le pipeline** :
- Vérifier les logs du stage de déchiffrement
- Valider localement : `./manage-secrets.sh extract`

**SOPS ou yq non trouvés** :
- Installer manuellement (voir section Configuration)
- Ou pré-installer dans l'image Docker Jenkins (voir JENKINS_SOPS_GUIDE.md)

Pour plus de détails : [JENKINS_SOPS_GUIDE.md#dépannage](JENKINS_SOPS_GUIDE.md)

## 📞 Support

En cas de problème, consulter dans l'ordre :
1. Les logs Jenkins du stage de déchiffrement
2. [JENKINS_SOPS_GUIDE.md](JENKINS_SOPS_GUIDE.md) - Section dépannage
3. Tester localement avec `./manage-secrets.sh`
4. Vérifier le credential Jenkins `sops-age-key`

---

**Migration effectuée le** : 2025-01-07  
**Jenkinsfile version** : 1.0.0-sops  
**SOPS version** : 3.8.1  
**Age encryption** : Activé  
