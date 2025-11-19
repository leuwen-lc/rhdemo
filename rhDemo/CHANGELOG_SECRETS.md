# ✅ Migration des secrets : Variables d'environnement → Fichiers YAML

## 🎯 Objectif accompli

Le projet RHDemo utilise maintenant des **fichiers de secrets YAML** au lieu de variables d'environnement pour une gestion plus sécurisée et pratique des secrets.

## 📦 Fichiers créés/modifiés

### Fichiers créés
```
✅ secrets/secrets.yml.template           # Template pour production
✅ SECRETS_MANAGEMENT.md                  # Documentation complète
✅ MIGRATION_SECRETS.md                   # Guide de migration
✅ setup-secrets.sh                       # Script d'initialisation
```

### Fichiers modifiés
```
✅ src/main/resources/application.yml     # Import des secrets
✅ src/test/resources/application-test.yml # Import pour tests
✅ .gitignore                             # Règles pour secrets/
```

### Fichiers existants (inchangés)
```
✅ secrets/secrets.yml                    # Production (NON commité)
✅ secrets/secrets-dev.yml                # Développement (commité, chiffré SOPS)
```

## 🔄 Changements principaux

### 1. Configuration Spring Boot

#### application.yml
```yaml
spring:
  # NOUVEAU : Import automatique des secrets
  config:
    import:
      - optional:file:./secrets/secrets.yml
      - optional:file:./secrets/secrets-dev.yml
  
  datasource:
    # AVANT : ${RHDEMO_DATASOURCE_PASSWORD_PG}
    # APRÈS : ${rhdemo.datasource.password.pg}
    password: ${rhdemo.datasource.password.pg}
  
  security:
    oauth2:
      client:
        registration:
          keycloak:
            # AVANT : ${RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET}
            # APRÈS : ${rhdemo.client.registration.keycloak.client.secret}
            client-secret: ${rhdemo.client.registration.keycloak.client.secret}
```

### 2. Structure des secrets

```yaml
# secrets/secrets.yml (ou secrets-dev.yml)
rhdemo:
  datasource:
    password:
      pg: "mot_de_passe_postgresql"
      h2: "mot_de_passe_h2"
  client:
    registration:
      keycloak:
        client:
          secret: "secret_client_keycloak"
  test:
    user: "utilisateur_test"
    pwd: "password_test"
```

### 3. .gitignore

```gitignore
### Secrets ###
# Production (sensible)
secrets/secrets.yml

# Templates et dev (ok pour commit)
!secrets/secrets.yml.template
!secrets/secrets-dev.yml

# Backups
secrets/*.backup
```

## ✅ Tests effectués

```bash
✅ Compilation réussie : ./mvnw clean compile
✅ Tests unitaires passés : ./mvnw test (2/2)
✅ Application démarre correctement
✅ Secrets chargés depuis fichiers YAML
✅ .gitignore fonctionne correctement
```

## 🚀 Utilisation

### Développement local (immédiat)
```bash
# Aucune action requise - secrets-dev.yml déjà présent
./mvnw spring-boot:run
```

### Nouveau serveur (production)
```bash
# 1. Initialiser le fichier de secrets
./setup-secrets.sh

# 2. Éditer avec les vrais secrets
nano secrets/secrets.yml

# 3. Sécuriser les permissions
chmod 600 secrets/secrets.yml

# 4. Démarrer l'application
./mvnw spring-boot:run
```

## 🔐 Sécurité

### ✅ Avantages de cette approche

1. **Isolation des secrets** : Fichier dédié, pas mélangé avec le code
2. **Permissions granulaires** : `chmod 600` - seul le propriétaire peut lire
3. **Pas d'exposition** : Secrets non visibles dans `ps aux` ou logs système
4. **Gestion simplifiée** : Un fichier YAML vs multiples variables d'env
5. **Chiffrement natif** : Compatible SOPS (déjà utilisé pour secrets-dev.yml)
6. **Audit trail** : Git track les modifications (sauf secrets.yml)
7. **CI/CD friendly** : Facile à injecter depuis secrets managers

### ⚠️ Points d'attention

- ⚠️ **Ne JAMAIS commiter** `secrets/secrets.yml` sur Git
- ⚠️ Toujours vérifier avec `git status` avant de commit
- ⚠️ Changer tous les secrets après un commit accidentel
- ⚠️ Utiliser `chmod 600` sur les fichiers de secrets en production

## 📚 Documentation

| Fichier | Description |
|---------|-------------|
| `SECRETS_MANAGEMENT.md` | Documentation complète de la gestion des secrets |
| `MIGRATION_SECRETS.md` | Guide détaillé de migration depuis variables d'env |
| `secrets.yml.template` | Template pour créer secrets.yml en production |
| `setup-secrets.sh` | Script automatique d'initialisation |

## 🔍 Vérification Git

```bash
# Vérifier que secrets.yml est bien ignoré
git check-ignore -v secrets/secrets.yml
# Résultat attendu : rhDemo/.gitignore:10:secrets/secrets.yml

# Vérifier que les templates seront commitables
git check-ignore -v secrets/secrets.yml.template
# Résultat attendu : rhDemo/.gitignore:12:!secrets/secrets.yml.template

# Vérifier les fichiers à commiter
git status --short
```

## 🎓 Concepts Spring Boot utilisés

1. **`spring.config.import`** : Import de fichiers de configuration externes
2. **`optional:file:`** : Fichier optionnel (pas d'erreur s'il manque)
3. **Order de priorité** : `secrets.yml` > `secrets-dev.yml`
4. **SpEL properties** : `${rhdemo.datasource.password.pg}`
5. **Profile-specific config** : `application-test.yml` pour tests

## 🆘 Dépannage

### Problème : Secrets non chargés

**Solution :**
```bash
# 1. Vérifier que le fichier existe
ls -lah secrets/secrets.yml

# 2. Vérifier les permissions
ls -lah secrets/secrets.yml

# 3. Vérifier la syntaxe YAML
cat secrets/secrets.yml

# 4. Activer les logs de configuration
# Dans application.yml :
logging:
  level:
    org.springframework.boot.context.config: DEBUG
```

### Problème : Application ne démarre pas

**Solution :**
```bash
# Vérifier les logs pour les erreurs de configuration
./mvnw spring-boot:run 2>&1 | grep -i "config\|error\|secret"
```

### Problème : Tests échouent

**Solution :**
```bash
# Les tests utilisent secrets-dev.yml (chiffré SOPS)
# Si nécessaire, déchiffrer :
sops -d secrets/secrets-dev.yml

# Ou créer secrets.yml temporairement pour tests
cp secrets/secrets.yml.template secrets/secrets.yml
# Éditer avec valeurs de test
./mvnw test
```

## 📊 Comparaison : Avant / Après

| Aspect | Avant (Env vars) | Après (Fichiers YAML) |
|--------|------------------|------------------------|
| **Setup** | Export de N variables | 1 fichier YAML |
| **Visibilité** | Visible dans `env` | Fichier protégé (600) |
| **Portabilité** | Export dans chaque shell | Copier 1 fichier |
| **CI/CD** | Variables secrets × N | 1 secret "fichier complet" |
| **Audit** | Aucun historique | Git track (template) |
| **Chiffrement** | Externe (vault, etc.) | SOPS natif |
| **Lisibilité** | Variables séparées | Structure YAML claire |
| **Type safety** | Strings uniquement | Types YAML (bool, int, etc.) |

## ✅ Checklist de déploiement

Production :
- [ ] Créer `secrets/secrets.yml` avec `./setup-secrets.sh`
- [ ] Éditer avec les vrais secrets
- [ ] Vérifier syntaxe YAML : `yamllint secrets/secrets.yml`
- [ ] Définir permissions : `chmod 600 secrets/secrets.yml`
- [ ] Tester l'application : `./mvnw test`
- [ ] Vérifier connexion DB et Keycloak
- [ ] Documenter l'emplacement du fichier pour l'équipe

Développement :
- [ ] Vérifier que `secrets-dev.yml` est présent
- [ ] Tester : `./mvnw test`
- [ ] Vérifier que `secrets.yml` est dans `.gitignore`

## 🎉 Résultat

✅ **Migration réussie !**

- ✅ Application compile et démarre
- ✅ Tests unitaires passent (2/2)
- ✅ Secrets chargés depuis fichiers YAML
- ✅ Documentation complète créée
- ✅ Scripts d'aide disponibles
- ✅ Compatibilité maintenue avec approche existante (SOPS)

**Prochaines étapes suggérées :**
1. Tester en environnement de staging
2. Mettre à jour les pipelines CI/CD
3. Former l'équipe sur la nouvelle approche
4. Supprimer les anciennes variables d'env (après validation complète)

---

📅 **Date de migration** : 7 novembre 2025  
👤 **Auteur** : GitHub Copilot  
📝 **Version** : 1.0.0
