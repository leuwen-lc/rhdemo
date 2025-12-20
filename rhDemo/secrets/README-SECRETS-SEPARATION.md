# Séparation des Secrets : ephemere vs stagingkub

## 📋 Vue d'ensemble

Les environnements `ephemere` (Docker Compose) et `stagingkub` (Kubernetes) utilisent des fichiers de secrets **complètement séparés** pour permettre une gestion indépendante et éviter les conflits.

## 📁 Fichiers de secrets

| Fichier | Environnement | Utilisation | Chiffrement |
|---------|---------------|-------------|-------------|
| `secrets-ephemere.yml` | **ephemere** (Docker Compose CI) | Environnement éphémère pour tests CI | SOPS/Age |
| `secrets-stagingkub.yml` | **stagingkub** (Kubernetes CD) | Environnement permanent Kubernetes | SOPS/Age |
| `secrets-rhdemo.yml` | Temporaire | Généré depuis secrets-staging*.yml pour l'app | Non chiffré (temporaire) |

## 🔐 Gestion des secrets

### Pour l'environnement ephemere (Docker Compose)

**Fichier source**: `secrets/secrets-ephemere.yml`

**Utilisé par**:
- `Jenkinsfile` (pipeline monolithique)
- `Jenkinsfile-CI` (pipeline CI moderne)
- Tests locaux avec Docker Compose

**Déchiffrement**:
```bash
# Éditer les secrets
SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops secrets-ephemere.yml

# Déchiffrer pour inspection
sops -d secrets-ephemere.yml > secrets-ephemere-decrypted.yml
```

### Pour l'environnement stagingkub (Kubernetes)

**Fichier source**: `secrets/secrets-stagingkub.yml`

**Utilisé par**:
- `Jenkinsfile-CD` (pipeline CD Kubernetes)
- Déploiements manuels vers KinD

**Déchiffrement**:
```bash
# Éditer les secrets
SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops secrets-stagingkub.yml

# Déchiffrer pour inspection
sops -d secrets-stagingkub.yml > secrets-stagingkub-decrypted.yml
```

## 🔄 Migration initiale

Lors de la création de `secrets-stagingkub.yml` :

1. Le fichier a été dupliqué depuis `secrets-ephemere.yml`
2. **Vous devriez changer les secrets** pour stagingkub pour plus de sécurité
3. Notamment :
   - Mots de passe des bases de données
   - Client secret OAuth2 Keycloak
   - Mots de passe admin Keycloak

```bash
# Éditer secrets-stagingkub.yml et générer de nouveaux secrets
SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops secrets-stagingkub.yml
```

## 🎯 Avantages de la séparation

✅ **Sécurité** : Compromission d'un environnement n'affecte pas l'autre
✅ **Isolation** : Pas de conflit entre CI (éphémère) et CD (permanent)
✅ **Flexibilité** : Possibilité d'avoir des configurations différentes
✅ **Auditabilité** : Changements de secrets tracés par environnement

## 📝 Bonnes pratiques

1. **Ne jamais** commiter les fichiers déchiffrés
2. **Toujours** utiliser SOPS pour éditer les secrets
3. **Régénérer** les secrets lors de rotations de sécurité
4. **Documenter** les changements de secrets dans les commits

## 🔗 Références

- [Documentation SOPS](https://github.com/mozilla/sops)
- [Pipeline CI (Jenkinsfile-CI)](../Jenkinsfile-CI)
- [Pipeline CD (Jenkinsfile-CD)](../Jenkinsfile-CD)
- [Environnements](../infra/ENVIRONMENTS.md)
