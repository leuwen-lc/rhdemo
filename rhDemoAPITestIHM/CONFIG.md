# Configuration des Tests Selenium - rhDemoAPITestIHM

## Vue d'ensemble

Le système de configuration a été **unifié** pour simplifier la gestion des paramètres de test. Toute la configuration est centralisée dans la classe `TestConfig.java`.

## Hiérarchie de chargement (ordre de priorité)

```
1. Propriétés Maven (-Dkey=value)     ← Priorité MAXIMALE (Jenkins)
2. Variables d'environnement          ← Fallback
3. Fichiers YAML                      ← Dev local
4. Valeurs par défaut                 ← Derniers recours
```

## Configuration disponible

### URLs et Endpoints

| Propriété | Maven Property | Env Var | YAML Path | Défaut |
|-----------|---------------|---------|-----------|--------|
| URL de l'app | `-Dtest.baseurl` | - | `app.base.url` | `http://localhost:9000` |
| URL Keycloak | `-Dtest.keycloak.url` | - | `keycloak.url` | `http://localhost:6090/realms/RHDemo` |

### Configuration Selenium

| Propriété | Maven Property | Env Var | YAML Path | Défaut |
|-----------|---------------|---------|-----------|--------|
| Mode headless | `-Dselenium.headless` | `SELENIUM_HEADLESS` | `headless.mode` | `false` |
| Navigateur | `-Dselenium.browser` | `SELENIUM_BROWSER` | `browser` | `firefox` |

### Credentials

| Propriété | Maven Property | Env Var | YAML Path | Défaut |
|-----------|---------------|---------|-----------|--------|
| Username | `-Dtest.username` | `RHDEMOTEST_USER` | `credentials.username` | **REQUIS** |
| Password | `-Dtest.password` | `RHDEMOTEST_PWD` | `credentials.password` | **REQUIS** |

### Timeouts (secondes)

| Propriété | YAML Path | Défaut |
|-----------|-----------|--------|
| Implicit wait | `timeout.implicit` | 10 |
| Explicit wait | `timeout.explicit` | 15 |
| Page load timeout | `timeout.page.load` | 30 |
| Auth timeout | `keycloak.timeout` | 20 |

## Utilisation

### 1. Développement local

**Créer les fichiers de configuration :**

```yaml
# src/test/resources/test.yml
app:
  base:
    url: http://localhost:9000

keycloak:
  url: http://localhost:6090/realms/RHDemo

browser: firefox
headless:
  mode: false

timeout:
  implicit: 10
  explicit: 15
  page:
    load: 30
```

```yaml
# src/test/resources/test-credentials.yml
credentials:
  username: manager
  password: your-password-here
```

**Lancer les tests :**

```bash
mvn test
```

### 2. Jenkins / CI

**Passer TOUTES les configs via propriétés Maven :**

```bash
mvn clean test \
  -Dtest.baseurl=https://rhdemo.staging.local \
  -Dtest.keycloak.url=https://rhdemo.staging.local/realms/RHDemo \
  -Dselenium.headless=true \
  -Dtest.username=${TEST_USERNAME} \
  -Dtest.password=${TEST_PASSWORD}
```

**Avantages :**
- ✅ Configuration explicite dans les logs Jenkins
- ✅ Pas de pollution des variables d'environnement
- ✅ Scope limité au processus Maven

### 3. Variables d'environnement (fallback)

**Si vous préférez les env vars :**

```bash
export RHDEMOTEST_USER="manager"
export RHDEMOTEST_PWD="password123"
export SELENIUM_HEADLESS="true"

mvn test -Dtest.baseurl=https://app.example.com
```

## Migration depuis l'ancien système

### Changements effectués

| Avant | Après |
|-------|-------|
| `TestConfig` + `CredentialsLoader` séparés | `TestConfig` unifié |
| Credentials via env vars uniquement | Maven properties > env vars > YAML |
| Jenkins : `export RHDEMOTEST_USER=...` | Jenkins : `-Dtest.username=...` |

### Compatibilité

✅ **Rétrocompatible** : Les variables d'environnement `RHDEMOTEST_USER` et `RHDEMOTEST_PWD` fonctionnent toujours (fallback).

### Fichiers obsolètes

- `CredentialsLoader.java` → **Supprimé** (logique intégrée dans `TestConfig`)

## Exemples

### Exemple 1 : Tests locaux avec YAML

```bash
# Les fichiers test.yml et test-credentials.yml sont chargés automatiquement
mvn test
```

### Exemple 2 : Override partiel avec Maven properties

```bash
# Utilise test.yml mais override l'URL
mvn test -Dtest.baseurl=http://192.168.1.100:9000
```

### Exemple 3 : Configuration complète via Maven (Jenkins)

```bash
mvn clean test \
  -Dtest.baseurl=https://staging.example.com \
  -Dtest.keycloak.url=https://keycloak.example.com/realms/MyRealm \
  -Dselenium.headless=true \
  -Dselenium.browser=chrome \
  -Dtest.username=admin \
  -Dtest.password=secret123
```

### Exemple 4 : Mix Maven + env vars

```bash
# Username/password via env vars (masqués dans logs)
export RHDEMOTEST_USER="testuser"
export RHDEMOTEST_PWD="secret"

# Reste via Maven properties (visible/traçable)
mvn test \
  -Dtest.baseurl=https://app.com \
  -Dselenium.headless=true
```

## Logs de configuration

Au démarrage des tests, `TestConfig` affiche :

```
📋 Configuration TestConfig initialisée
   - Fichier test.yml: ✅ chargé
   - Fichier test-credentials.yml: ✅ chargé

🔐 Credentials configurés:
   - Username: manager
   - Password: ********

   Credential test.username chargé depuis propriété Maven
```

## Dépannage

### Erreur : "Username non configuré"

```
❌ Username non configuré ! Utiliser :
   1. Propriété Maven: -Dtest.username=xxx
   2. Variable env: RHDEMOTEST_USER
   3. Fichier: test-credentials.yml
```

**Solution :** Fournir les credentials via l'une des 3 méthodes ci-dessus.

### Les tests utilisent la mauvaise URL

**Vérifier l'ordre de priorité :**
1. Maven property est-elle définie ? (`-Dtest.baseurl=...`)
2. Sinon, vérifier `test.yml`
3. Sinon, valeur par défaut = `http://localhost:9000`

### Mode headless ne fonctionne pas

```bash
# S'assurer que la propriété est bien passée
mvn test -Dselenium.headless=true

# Ou via env var
export SELENIUM_HEADLESS=true
mvn test
```

## Architecture

```
TestConfig (classe unifiée)
    ├── Chargement YAML (test.yml + test-credentials.yml)
    ├── Méthode getConfigProperty()
    │   └── 1. System.getProperty()  (Maven -D)
    │   └── 2. System.getenv()       (env vars)
    │   └── 3. YAML files
    │   └── 4. Défaut
    ├── Méthode getCredential()
    │   └── Même hiérarchie
    └── Constantes publiques
        ├── BASE_URL
        ├── KEYCLOAK_LOGIN_URL
        ├── USERNAME / PASSWORD
        ├── HEADLESS_MODE
        └── BROWSER
```

## Références

- Classe source : `src/test/java/fr/leuwen/rhdemo/tests/config/TestConfig.java`
- Utilisation : `src/test/java/fr/leuwen/rhdemo/tests/base/BaseSeleniumTest.java`
- Jenkins : `rhDemo/Jenkinsfile` (stage "Tests Selenium IHM")

---

**Date de migration** : 22 novembre 2025
**Version** : 2.0.0 (Configuration unifiée)
