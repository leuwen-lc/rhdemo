# Gestion des Secrets - RHDemo

## 📁 Structure des fichiers

```
secrets/
├── secrets-dev.yml     # Secrets de développement (COMMITÉ sur Git, chiffré avec SOPS)
└── secrets.yml         # Secrets de production (NON COMMITÉ, dans .gitignore)
```

## 🔐 Fichiers de secrets

### `secrets-dev.yml` (Développement)
- **Commité sur Git** ✅
- Chiffré avec **SOPS/Age**
- Utilisé pour le développement local
- Contient des valeurs de test non sensibles

### `secrets.yml` (Production)
- **NON commité sur Git** ⛔ (dans `.gitignore`)
- Contient les **vrais secrets de production**
- Doit être créé manuellement sur chaque environnement
- Prioritaire sur `secrets-dev.yml` si présent

## 🚀 Configuration Spring Boot

L'application charge automatiquement les secrets via :

```yaml
spring:
  config:
    import:
      - optional:file:./secrets/secrets.yml          # Production (prioritaire)
      - optional:file:./secrets/secrets-dev.yml      # Développement (fallback)
```

### Ordre de priorité
1. `secrets.yml` (si présent) - **Production**
2. `secrets-dev.yml` - **Développement/Test**

## 📝 Structure des secrets

```yaml
rhdemo:
  datasource:
    password:
      pg: "mot_de_passe_postgresql"
      h2: "mot_de_passe_h2_test"
  
  client:
    registration:
      keycloak:
        client:
          secret: "secret_client_keycloak"
  
  test:
    user: "utilisateur_test"
    pwd: "password_test"
```

## 🔧 Utilisation dans application.yml

Les secrets sont référencés via Spring SpEL :

```yaml
spring:
  datasource:
    password: ${rhdemo.datasource.password.pg}
  
  security:
    oauth2:
      client:
        registration:
          keycloak:
            client-secret: ${rhdemo.client.registration.keycloak.client.secret}
```

## 🛠️ Déploiement

### Développement local
1. Le fichier `secrets-dev.yml` (chiffré) est déjà présent
2. Aucune action requise - l'application démarre directement

### Production
1. Créer le fichier `secrets/secrets.yml` sur le serveur :
   ```bash
   cd /chemin/vers/rhDemo
   cp secrets/secrets.yml.template secrets/secrets.yml
   ```

2. Éditer `secrets/secrets.yml` avec les vrais secrets :
   ```bash
   nano secrets/secrets.yml
   ```

3. **Vérifier les permissions** :
   ```bash
   chmod 600 secrets/secrets.yml
   chown app-user:app-group secrets/secrets.yml
   ```

4. Démarrer l'application :
   ```bash
   ./mvnw spring-boot:run
   ```

## 🔒 Sécurité

### ✅ Bonnes pratiques
- ✅ `secrets.yml` dans `.gitignore`
- ✅ `secrets-dev.yml` chiffré avec SOPS
- ✅ Permissions restrictives (600) sur les fichiers de secrets
- ✅ Secrets jamais hardcodés dans le code

### ⚠️ Avertissements
- ⚠️ Ne jamais commiter `secrets.yml` sur Git
- ⚠️ Ne jamais afficher les secrets dans les logs
- ⚠️ Changer tous les secrets après un commit accidentel

## 🔄 Migration depuis variables d'environnement

### Anciennes variables (deprecated)
```bash
export RHDEMO_DATASOURCE_PASSWORD_PG="password"
export RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET="secret"
```

### Nouvelle approche (recommandée)
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

## 📚 Documentation SOPS

Pour déchiffrer/chiffrer `secrets-dev.yml` :

```bash
# Déchiffrer (lecture)
sops -d secrets/secrets-dev.yml

# Éditer (chiffrement automatique)
sops secrets/secrets-dev.yml

# Chiffrer un nouveau fichier
sops -e secrets/secrets-dev.yml > secrets/secrets-dev.yml.enc
```

## 🧪 Tests

Les tests utilisent automatiquement `secrets-dev.yml` (ou `secrets.yml` si présent) :

```bash
./mvnw test
```

Le mot de passe H2 est récupéré via : `${rhdemo.datasource.password.h2:}`

## ❓ FAQ

**Q: Que se passe-t-il si `secrets.yml` n'existe pas ?**  
R: L'application utilise `secrets-dev.yml` en fallback grâce au préfixe `optional:`.

**Q: Puis-je utiliser les deux fichiers simultanément ?**  
R: Oui ! Spring fusionnera les propriétés, avec `secrets.yml` prioritaire.

**Q: Comment vérifier que les secrets sont bien chargés ?**  
R: Activer les logs DEBUG : `logging.level.org.springframework.boot.context.config: DEBUG`

**Q: Dois-je redémarrer l'application après modification ?**  
R: Oui, les fichiers de configuration sont chargés au démarrage uniquement.
