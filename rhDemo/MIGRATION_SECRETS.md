# 🔄 Migration : Variables d'environnement → Fichiers de secrets

## Résumé du changement

L'application RHDemo utilise maintenant des **fichiers de secrets YAML** au lieu de variables d'environnement pour gérer les secrets.

## ⚡ Ce qui a changé

### Avant (Variables d'environnement)
```bash
# Configuration via variables d'environnement
export RHDEMO_DATASOURCE_PASSWORD_PG="password"
export RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET="secret"

./mvnw spring-boot:run
```

### Après (Fichiers de secrets)
```yaml
# secrets/secrets.yml
rhdemo:
  datasource:
    password:
      pg: "password"
  client:
    registration:
      keycloak:
        client:
          secret: "secret"
```

```bash
# Plus besoin d'export - l'application charge automatiquement secrets.yml
./mvnw spring-boot:run
```

## 📋 Changements dans les fichiers

### 1. `application.yml`

**Avant :**
```yaml
spring:
  datasource:
    password: ${RHDEMO_DATASOURCE_PASSWORD_PG}
  security:
    oauth2:
      client:
        registration:
          keycloak:
            client-secret: ${RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET}
```

**Après :**
```yaml
spring:
  config:
    import:
      - optional:file:./secrets/secrets.yml
      - optional:file:./secrets/secrets-dev.yml
  
  datasource:
    password: ${rhdemo.datasource.password.pg}
  security:
    oauth2:
      client:
        registration:
          keycloak:
            client-secret: ${rhdemo.client.registration.keycloak.client.secret}
```

### 2. `.gitignore`

**Ajouté :**
```
### Secrets ###
secrets/secrets.yml
!secrets/secrets.yml.template
!secrets/secrets-dev.yml
secrets/*.backup
```

### 3. Nouveaux fichiers

```
secrets/
├── secrets.yml               # Production (non commité)
├── secrets.yml.template      # Template (commité)
└── secrets-dev.yml          # Développement (commité, chiffré SOPS)
```

## 🚀 Guide de migration

### Pour le développement local

**Aucune action requise !** ✅

Le fichier `secrets-dev.yml` (chiffré avec SOPS) est déjà présent et sera utilisé automatiquement.

### Pour les serveurs de production

1. **Sur le serveur**, créer le fichier de secrets :
   ```bash
   cd /path/to/rhDemo
   ./setup-secrets.sh
   ```

2. **Éditer** `secrets/secrets.yml` avec les vrais secrets :
   ```bash
   nano secrets/secrets.yml
   ```

3. **Définir les permissions** restrictives :
   ```bash
   chmod 600 secrets/secrets.yml
   chown app-user:app-group secrets/secrets.yml
   ```

4. **Tester** l'application :
   ```bash
   ./mvnw spring-boot:run
   ```

### Pour les pipelines CI/CD

#### Option 1 : Secrets Manager (recommandé)

Utiliser le gestionnaire de secrets de votre plateforme CI/CD pour injecter `secrets.yml` au déploiement.

**GitHub Actions :**
```yaml
- name: Create secrets file
  run: |
    mkdir -p secrets
    echo "${{ secrets.RHDEMO_SECRETS_YML }}" > secrets/secrets.yml
    chmod 600 secrets/secrets.yml
```

**GitLab CI :**
```yaml
deploy:
  script:
    - mkdir -p secrets
    - echo "$RHDEMO_SECRETS_YML" > secrets/secrets.yml
    - chmod 600 secrets/secrets.yml
```

#### Option 2 : Variables d'environnement (rétrocompatible)

Si vous devez conserver les variables d'environnement, créez un script de conversion :

```bash
#!/bin/bash
# convert-env-to-secrets.sh

cat > secrets/secrets.yml <<EOF
rhdemo:
  datasource:
    password:
      pg: "${RHDEMO_DATASOURCE_PASSWORD_PG}"
      h2: "${RHDEMO_DATASOURCE_PASSWORD_H2}"
  client:
    registration:
      keycloak:
        client:
          secret: "${RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET}"
EOF

chmod 600 secrets/secrets.yml
```

Puis dans votre pipeline :
```yaml
- name: Convert env vars to secrets.yml
  run: ./convert-env-to-secrets.sh
```

## 🔍 Vérification

### Vérifier que les secrets sont chargés

1. **Activer les logs de configuration Spring :**
   ```yaml
   # application.yml
   logging:
     level:
       org.springframework.boot.context.config: DEBUG
   ```

2. **Démarrer l'application et rechercher :**
   ```
   Loaded config file 'file:./secrets/secrets.yml'
   ```

### Tester la connexion

```bash
# Test PostgreSQL
./mvnw test

# Test Keycloak (nécessite Keycloak démarré)
curl http://localhost:9000/login
```

## ❓ FAQ

### Q: Dois-je supprimer les variables d'environnement ?

**R:** Non, ce n'est pas obligatoire. Les fichiers de secrets ont la priorité, mais les variables d'environnement fonctionnent toujours comme fallback.

### Q: Comment gérer plusieurs environnements ?

**R:** Créez plusieurs fichiers de secrets :
```
secrets/
├── secrets-dev.yml      # Développement (commité, chiffré)
├── secrets-staging.yml  # Staging (déployer manuellement)
├── secrets-prod.yml     # Production (déployer manuellement)
```

Puis dans `application.yml` :
```yaml
spring:
  config:
    import:
      - optional:file:./secrets/secrets-${spring.profiles.active:dev}.yml
```

### Q: Puis-je utiliser SOPS pour chiffrer secrets.yml ?

**R:** Oui ! Chiffrez `secrets.yml` avec SOPS :
```bash
sops -e secrets/secrets.yml > secrets/secrets.yml.enc
```

Puis déchiffrez au déploiement :
```bash
sops -d secrets/secrets.yml.enc > secrets/secrets.yml
```

### Q: Les tests fonctionnent-ils toujours ?

**R:** Oui ! Les tests utilisent automatiquement `secrets-dev.yml` (ou `secrets.yml` si présent).

### Q: Que faire en cas de problème ?

**R:** Consultez les logs au démarrage :
```bash
./mvnw spring-boot:run | grep -i "config\|secret"
```

Si les secrets ne se chargent pas, vérifiez :
- ✅ Le fichier `secrets/secrets.yml` existe
- ✅ Les permissions sont correctes (`chmod 600`)
- ✅ La syntaxe YAML est valide (indentation, pas de tabs)
- ✅ Le chemin relatif est correct (lancer depuis la racine du projet)

## 📚 Documentation

- **Guide complet** : [SECRETS_MANAGEMENT.md](./SECRETS_MANAGEMENT.md)
- **Spring Boot Config Import** : https://docs.spring.io/spring-boot/docs/current/reference/html/features.html#features.external-config.files.importing

## ✅ Avantages de cette approche

1. **🔒 Sécurité améliorée** : Permissions fichiers (600), pas d'exposition dans env
2. **📝 Gestion simplifiée** : Un seul fichier YAML vs multiples variables
3. **🔄 Portabilité** : Copier un fichier vs exporter N variables
4. **🔐 Chiffrement natif** : Compatible SOPS, Vault, etc.
5. **👀 Lisibilité** : Structure YAML claire et commentée
6. **🚀 CI/CD friendly** : Facile à injecter depuis secrets managers

## 🆘 Support

En cas de problème, consulter :
- Logs Spring Boot : `./mvnw spring-boot:run`
- Tests : `./mvnw test`
- Documentation : `SECRETS_MANAGEMENT.md`
