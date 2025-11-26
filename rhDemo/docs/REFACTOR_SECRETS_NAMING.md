# Refactoring - Renommage des fichiers de secrets

## Date
23 novembre 2025

## Objectif

Clarifier la distinction entre les différents fichiers de secrets utilisés dans le projet :
- `secrets-staging.yml` (chiffré SOPS) → Usage Jenkins pour tous les secrets d'infrastructure
- `secrets-rhdemo.yml` (non chiffré) → Usage application rhDemo uniquement

## Problème initial

Le nom générique `secrets.yml` créait une confusion :
- Est-ce le fichier pour Jenkins ou pour l'application ?
- Quel fichier template utiliser pour créer les secrets locaux ?
- Différence peu claire avec `secrets-staging.yml`

## Solution

Renommage systématique : **`secrets.yml` → `secrets-rhdemo.yml`**

Ce nom explicite clairement que le fichier contient uniquement les secrets nécessaires à l'application rhDemo.

## Fichiers modifiés

### 1. Configuration Spring Boot

#### [src/main/resources/application.yml](../src/main/resources/application.yml#L10-L11)
```yaml
config:
  import:
    - optional:file:./secrets/secrets-rhdemo.yml
    - optional:file:/workspace/secrets/secrets-rhdemo.yml
```

#### [src/test/resources/application-test.yml](../src/test/resources/application-test.yml#L8)
```yaml
config:
  import:
    - optional:file:./secrets/secrets-rhdemo.yml
```

### 2. Jenkins Pipeline

#### [Jenkinsfile:186](../Jenkinsfile#L186)
Génération du fichier :
```bash
cat > rhDemo/secrets/secrets-rhdemo.yml <<EOF
```

#### [Jenkinsfile:206](../Jenkinsfile#L206)
Message de confirmation :
```bash
echo "✅ Fichier rhDemo/secrets/secrets-rhdemo.yml créé"
```

#### [Jenkinsfile:706-747](../Jenkinsfile#L706-L747)
Injection du fichier dans le container via `docker cp` :
```bash
stage('🔐 Injection secrets rhDemo dans container') {
    # Créer le répertoire en tant que root (l'utilisateur CNB n'a pas les droits)
    docker exec --user root rhdemo-staging-app mkdir -p /workspace/secrets
    docker exec --user root rhdemo-staging-app chown cnb:cnb /workspace/secrets

    # Copier le fichier
    docker cp secrets-rhdemo.yml rhdemo-staging-app:/workspace/secrets/secrets-rhdemo.yml

    # Définir les permissions (read-only) et le propriétaire
    docker exec --user root rhdemo-staging-app chown cnb:cnb /workspace/secrets/secrets-rhdemo.yml
    docker exec --user root rhdemo-staging-app chmod 400 /workspace/secrets/secrets-rhdemo.yml
}
```

#### [Jenkinsfile:1314-1317](../Jenkinsfile#L1314-L1317)
Nettoyage sécurisé :
```bash
if [ -f "rhDemo/secrets/secrets-rhdemo.yml" ]; then
    shred -vfz -n 3 rhDemo/secrets/secrets-rhdemo.yml
fi
```

### 3. Infrastructure Docker

#### [infra/staging/docker-compose.yml:124-126](../infra/staging/docker-compose.yml#L124-L126)
Note explicative (le fichier est copié via `docker cp` au lieu d'un bind mount) :
```yaml
# Note: secrets-rhdemo.yml est copié via docker cp au lieu de bind mount
# pour éviter les problèmes de layers Docker corrompus et de chemins relatifs
# Le fichier est injecté par Jenkins dans le stage "Injection secrets rhDemo dans container"
```

### 4. Configuration Git

#### [.gitignore:12](../.gitignore#L12)
```gitignore
secrets/secrets-rhdemo.yml
```

### 5. Templates et documentation

#### [secrets/secrets.yml.template:7-8](../secrets/secrets.yml.template#L7-L8)
Instructions mises à jour :
```yaml
# 1. Copier ce fichier : cp secrets.yml.template secrets-rhdemo.yml
# 2. Éditer secrets-rhdemo.yml avec vos vrais secrets
```

#### [docs/SECURITY_LEAST_PRIVILEGE.md](../docs/SECURITY_LEAST_PRIVILEGE.md)
Toutes les références mises à jour pour refléter le nouveau nom.

## Impact

### ✅ Pas d'impact sur le fonctionnement

- L'application continue de fonctionner exactement comme avant
- Spring Boot charge le fichier via `spring.config.import` (ordre : dev local puis Docker staging)
- Les tests d'intégration continuent de fonctionner

### ✅ Amélioration de la clarté

- Distinction claire entre fichiers Jenkins et fichiers applicatifs
- Nom explicite qui reflète le contenu (secrets rhDemo uniquement)
- Cohérence avec les autres noms de fichiers (`secrets-staging.yml`, `secrets-dev.yml`)

### ⚠️ Action requise pour les développeurs

Les développeurs ayant un fichier `secrets/secrets.yml` local doivent le renommer :

```bash
cd rhDemo/secrets
mv secrets.yml secrets-rhdemo.yml
```

Ou recréer depuis le template :
```bash
cp secrets.yml.template secrets-rhdemo.yml
# Éditer avec vos secrets
```

## Structure finale des secrets

```
rhDemo/secrets/
├── secrets.yml.template              ← Template pour dev (commité)
├── secrets-staging.yml.template      ← Template pour staging (commité)
├── secrets-staging.yml               ← Secrets staging chiffrés SOPS (commité)
│
├── secrets-rhdemo.yml                ← Secrets dev local rhDemo (gitignore)
├── secrets-dev.yml                   ← Secrets dev autres composants (gitignore)
│
└── (Fichiers temporaires générés par Jenkins, nettoyés après build)
    ├── secrets-decrypted.yml         ← Déchiffrement temporaire SOPS
    └── env-vars.sh                   ← Variables bash pour Jenkins
```

## Nomenclature clarifiée

| Fichier | Usage | Contenu | Commité Git |
|---------|-------|---------|-------------|
| `secrets.yml.template` | Template dev | Exemples CHANGE_ME | ✅ Oui |
| `secrets-staging.yml.template` | Template staging | Exemples CHANGE_ME | ✅ Oui |
| `secrets-staging.yml` | Jenkins staging | Tous secrets (chiffré SOPS) | ✅ Oui |
| `secrets-rhdemo.yml` | App rhDemo | Secrets rhDemo uniquement | ❌ Non (.gitignore) |
| `secrets-dev.yml` | Autres composants | Secrets autres services | ❌ Non (.gitignore) |

## Avantages du nouveau nommage

1. **Clarté** : Le nom indique immédiatement l'usage (rhDemo applicatif)
2. **Cohérence** : Même pattern que `secrets-staging.yml`, `secrets-dev.yml`
3. **Sécurité** : Évite toute confusion entre secrets d'infra et secrets applicatifs
4. **Maintenabilité** : Plus facile de comprendre la structure du projet

## Références

- [SECURITY_LEAST_PRIVILEGE.md](SECURITY_LEAST_PRIVILEGE.md) - Principe du moindre privilège
- [Jenkinsfile](../Jenkinsfile) - Pipeline CI/CD
- [docker-compose.yml](../infra/staging/docker-compose.yml) - Configuration Docker staging
