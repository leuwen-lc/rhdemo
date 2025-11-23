# Principe du moindre privilège - Gestion des secrets

## Problématique initiale

Avant cette amélioration, l'application `rhDemo` en staging avait accès à **tous** les secrets du fichier `secrets-staging.yml`, incluant :
- ✅ Ses propres secrets (mot de passe PostgreSQL, secret client Keycloak)
- ❌ Secrets admin Keycloak (`KEYCLOAK_ADMIN_PASSWORD`)
- ❌ Mot de passe base de données Keycloak (`KEYCLOAK_DB_PASSWORD`)
- ❌ Mots de passe des utilisateurs de test
- ❌ URLs des serveurs de staging/production

**Risque** : En cas de compromission du container `rhdemo-staging-app`, un attaquant aurait accès aux secrets administrateurs de Keycloak et pourrait :
- Se connecter à l'Admin Console Keycloak
- Modifier la configuration des realms, clients et utilisateurs
- Compromettre l'ensemble de la plateforme

## Solution implémentée

### Architecture

```
secrets-staging.yml (chiffré SOPS)
         ↓
   Jenkins déchiffre
         ↓
    ┌────────────────────────────┐
    │  env-vars.sh               │  ← Tous les secrets (pour Keycloak, PostgreSQL, etc.)
    │  (utilisé par Jenkins)     │
    └────────────────────────────┘
         ↓
    ┌────────────────────────────┐
    │  secrets-rhdemo.yml        │  ← Secrets filtrés pour rhDemo uniquement
    │  (monté dans container)    │
    └────────────────────────────┘
         ↓
    Container rhdemo-staging-app
    (accès limité aux secrets rhDemo)
```

### Secrets accessibles par rhDemo

Le fichier `rhDemo/secrets/secrets-rhdemo.yml` généré par Jenkins contient **uniquement** :

```yaml
rhdemo:
  datasource:
    password:
      pg: <password>         # Mot de passe PostgreSQL pour rhDemo
      h2: <password>         # Mot de passe H2 (tests uniquement)
  client:
    registration:
      keycloak:
        client:
          secret: <secret>   # Secret client Keycloak pour OAuth2
```

### Secrets exclus (non accessibles par rhDemo)

Les secrets suivants sont **exclus** du fichier monté dans le container :
- ❌ `keycloak.admin.password` - Mot de passe admin Keycloak
- ❌ `keycloak.admin.user` - Utilisateur admin Keycloak
- ❌ `keycloak.db.password` - Mot de passe base de données Keycloak
- ❌ `rhdemo.test.pwduseradmin` - Mots de passe utilisateurs de test
- ❌ `rhdemo.servers.staging` - URLs des serveurs
- ❌ `rhdemo.servers.production` - URLs des serveurs

## Implémentation technique

### 1. Jenkinsfile - Stage d'extraction

Nouveau stage ajouté après le déchiffrement SOPS :

```groovy
stage('🔐 Extraction secrets rhDemo (moindre privilège)') {
    sh '''
        . rhDemo/secrets/env-vars.sh

        cat > rhDemo/secrets/secrets-rhdemo.yml <<EOF
rhdemo:
  datasource:
    password:
      pg: ${RHDEMO_DATASOURCE_PASSWORD_PG}
      h2: ${RHDEMO_DATASOURCE_PASSWORD_H2}
  client:
    registration:
      keycloak:
        client:
          secret: ${RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET}
EOF
    '''
}
```

### 2. Injection du fichier dans le container

Jenkins copie le fichier dans le container avec `docker cp` au lieu d'utiliser un bind mount :

```bash
# Créer le répertoire en tant que root (l'utilisateur CNB n'a pas les droits)
docker exec --user root rhdemo-staging-app mkdir -p /workspace/secrets
docker exec --user root rhdemo-staging-app chown cnb:cnb /workspace/secrets

# Copier le fichier
docker cp secrets-rhdemo.yml rhdemo-staging-app:/workspace/secrets/secrets-rhdemo.yml

# Définir les permissions (read-only) et le propriétaire
docker exec --user root rhdemo-staging-app chown cnb:cnb /workspace/secrets/secrets-rhdemo.yml
docker exec --user root rhdemo-staging-app chmod 400 /workspace/secrets/secrets-rhdemo.yml
```

**Pourquoi `docker cp` au lieu de volume mount ?**
- Évite les problèmes de chemins relatifs entre Jenkins container et Docker host
- Cohérent avec les autres fichiers (nginx.conf, pgddl.sql)
- Évite les problèmes de layers Docker corrompus

**Note sur les permissions Paketo** :
- L'image Paketo utilise l'utilisateur `cnb` (Cloud Native Buildpacks) non-root
- Les opérations sur `/workspace` nécessitent `--user root` puis `chown cnb:cnb`

### 3. Spring Boot - Configuration

```yaml
# application.yml
spring:
  config:
    import:
      - optional:file:./secrets/secrets-rhdemo.yml           # Dev local
      - optional:file:/workspace/secrets/secrets-rhdemo.yml  # Docker staging
```

### 4. Nettoyage sécurisé

Le fichier `secrets-rhdemo.yml` est supprimé de manière sécurisée à la fin du pipeline :

```bash
if [ -f "rhDemo/secrets/secrets-rhdemo.yml" ]; then
    shred -vfz -n 3 rhDemo/secrets/secrets-rhdemo.yml
fi
```

## Bénéfices de sécurité

### 1. **Réduction de la surface d'attaque**
- Compromission du container `rhdemo-staging-app` → accès limité aux secrets rhDemo
- Impossibilité d'accéder aux secrets admin Keycloak

### 2. **Principe du moindre privilège**
- Chaque composant n'a accès qu'aux secrets strictement nécessaires
- Conformité avec les bonnes pratiques de sécurité (OWASP, NIST)

### 3. **Audit et traçabilité**
- Logs Jenkins explicites sur les secrets inclus/exclus
- Facile de vérifier quel composant a accès à quels secrets

### 4. **Évolutivité**
- Ajout facile de nouveaux secrets pour rhDemo sans exposer d'autres secrets
- Séparation claire entre secrets applicatifs et secrets d'infrastructure

## Vérification

### En développement

```bash
# Créer le fichier secrets-rhdemo.yml à partir du template
cp secrets/secrets.yml.template secrets/secrets-rhdemo.yml

# Éditer avec vos secrets
vim secrets/secrets-rhdemo.yml
```

### En staging (Jenkins)

Le pipeline affiche :

```
✅ Fichier rhDemo/secrets/secrets-rhdemo.yml créé (secrets limités à rhDemo uniquement)
   - datasource.password.pg: ✅
   - datasource.password.h2: ✅
   - client.registration.keycloak.client.secret: ✅
   - Keycloak admin password: ❌ (non inclus - sécurité)
   - Keycloak DB password: ❌ (non inclus - sécurité)
```

### Vérification dans le container

```bash
# Se connecter au container
docker exec -it rhdemo-staging-app sh

# Vérifier que le fichier secrets-rhdemo.yml existe et contient uniquement les secrets rhDemo
cat /workspace/secrets/secrets-rhdemo.yml

# Vérifier que les variables d'environnement admin Keycloak sont absentes
env | grep KEYCLOAK_ADMIN  # Doit être vide
```

## Références

- **OWASP Top 10** - A02:2021 – Cryptographic Failures
- **NIST SP 800-53** - AC-6: Least Privilege
- **CIS Docker Benchmark** - 5.7: Do not share the host's network namespace

## Date de mise en œuvre

**23 novembre 2025** - Implémenté dans le cadre de l'amélioration de la sécurité du pipeline CI/CD.
