# 🔐 Authentification Keycloak - Guide de configuration

## 📋 Vue d'ensemble

Les tests Selenium s'authentifient **automatiquement** sur Keycloak au démarrage de la suite de tests (une seule fois pour tous les tests).

---

## ⚙️ Configuration

### 1. Fichier de configuration

Les identifiants sont définis dans **deux emplacements** :

#### A. TestConfig.java (configuration en dur)

Fichier : `src/test/java/fr/leuwen/rhdemo/tests/config/TestConfig.java`

```java
// ========== Authentification Keycloak ==========

// URL de la page de login Keycloak
public static final String KEYCLOAK_LOGIN_URL = "http://localhost:6080/realms/LeuwenRealm";

// Identifiants de test
public static final String TEST_USERNAME = "testuser";
public static final String TEST_PASSWORD = "testpassword";

// Timeout pour l'authentification (secondes)
public static final int AUTH_TIMEOUT = 20;
```

#### B. test.properties (configuration externe)

Fichier : `src/test/resources/test.properties`

```properties
# Authentification Keycloak
keycloak.url=http://localhost:6080/realms/LeuwenRealm
keycloak.username=testuser
keycloak.password=testpassword
keycloak.timeout=20
```

---

## 🔑 Modifier les identifiants

### Option 1 : Modifier TestConfig.java

```java
public static final String TEST_USERNAME = "votre-username";
public static final String TEST_PASSWORD = "votre-password";
```

### Option 2 : Modifier test.properties

```properties
keycloak.username=votre-username
keycloak.password=votre-password
```

### Option 3 : Variables d'environnement (pour CI/CD)

```bash
export KEYCLOAK_USERNAME=votre-username
export KEYCLOAK_PASSWORD=votre-password
```

---

## 🚀 Fonctionnement

### Séquence d'authentification

```
1. Lancement du navigateur (Firefox/Chrome)
   ↓
2. Navigation vers http://localhost:9000/front/
   ↓
3. Détection de la redirection Keycloak
   ↓
4. Attente du formulaire de login
   ↓
5. Saisie du username (id="username")
   ↓
6. Saisie du password (id="password")
   ↓
7. Clic sur le bouton "Sign In" (id="kc-login")
   ↓
8. Attente de la redirection vers l'application
   ↓
9. Vérification de l'authentification réussie
   ↓
10. Exécution des tests
```

### Code d'authentification

La méthode `authenticateKeycloak()` dans `BaseSeleniumTest.java` :

```java
private static void authenticateKeycloak() {
    System.out.println("🔐 Authentification Keycloak en cours...");
    
    // 1. Aller sur la page d'accueil
    driver.get(TestConfig.HOME_URL);
    
    // 2. Vérifier si redirection vers Keycloak
    if (driver.getCurrentUrl().contains("keycloak") || 
        driver.getCurrentUrl().contains("realms")) {
        
        // 3. Attendre le formulaire
        authWait.until(ExpectedConditions.visibilityOfElementLocated(usernameField));
        
        // 4. Remplir les champs
        driver.findElement(By.id("username")).sendKeys(TEST_USERNAME);
        driver.findElement(By.id("password")).sendKeys(TEST_PASSWORD);
        
        // 5. Soumettre le formulaire
        driver.findElement(By.id("kc-login")).click();
        
        // 6. Attendre la redirection
        authWait.until(ExpectedConditions.urlContains(BASE_URL));
    }
}
```

---

## 📊 Logs d'authentification

### Authentification réussie

```
🚀 Initialisation du navigateur pour la suite de tests...
✅ Navigateur firefox initialisé avec succès
🔐 Authentification Keycloak en cours...
📋 Page de login Keycloak détectée
✏️ Username saisi: testuser
✏️ Password saisi
🔘 Bouton de connexion cliqué
✅ Authentification Keycloak réussie !
🌐 URL actuelle: http://localhost:9000/front/
```

### Déjà authentifié (cookies présents)

```
🚀 Initialisation du navigateur pour la suite de tests...
✅ Navigateur firefox initialisé avec succès
🔐 Authentification Keycloak en cours...
ℹ️ Déjà authentifié (pas de redirection vers Keycloak)
```

### Erreur d'authentification

```
🚀 Initialisation du navigateur pour la suite de tests...
✅ Navigateur firefox initialisé avec succès
🔐 Authentification Keycloak en cours...
📋 Page de login Keycloak détectée
✏️ Username saisi: testuser
✏️ Password saisi
🔘 Bouton de connexion cliqué
⚠️ Toujours sur la page Keycloak après authentification
URL: http://localhost:6080/realms/LeuwenRealm/login-actions/...
```

---

## 🔍 Éléments Keycloak détectés

D'après la page HTML fournie, les éléments suivants sont utilisés :

### Champs de formulaire

| Élément | ID | Type | Description |
|---------|-----|------|-------------|
| Username | `username` | `text` | Champ de saisie du nom d'utilisateur |
| Password | `password` | `password` | Champ de saisie du mot de passe |
| Submit | `kc-login` | `submit` | Bouton "Sign In" |

### Locators Selenium

```java
By usernameField = By.id("username");
By passwordField = By.id("password");
By loginButton = By.id("kc-login");
```

### Formulaire complet

```html
<form id="kc-form-login" 
      action="http://localhost:6080/realms/LeuwenRealm/login-actions/authenticate?..."
      method="post">
    
    <input id="username" name="username" type="text" />
    <input id="password" name="password" type="password" />
    <input id="kc-login" type="submit" value="Sign In"/>
    
</form>
```

---

## 🧪 Test de l'authentification

### Test manuel

1. **Démarrer Keycloak** (si ce n'est pas déjà fait)
   ```bash
   # Vérifier que Keycloak tourne sur le port 6080
   curl -I http://localhost:6080
   ```

2. **Démarrer l'application RHDemo**
   ```bash
   cd /home/leno-vo/git/repository/rhdemo
   ./mvnw spring-boot:run
   ```

3. **Lancer les tests Selenium**
   ```bash
   cd /home/leno-vo/git/repository/rhDemoAPITestIHM
   ./run-tests.sh
   ```

4. **Observer l'authentification automatique**
   - Le navigateur s'ouvre
   - Navigation vers l'application
   - Redirection vers Keycloak (si pas authentifié)
   - Saisie automatique du username/password
   - Clic automatique sur "Sign In"
   - Retour sur l'application
   - Exécution des tests

---

## ⚠️ Résolution de problèmes

### Problème 1 : Timeout d'authentification

**Symptôme :**
```
❌ Erreur lors de l'authentification Keycloak: TimeoutException
```

**Solutions :**
- Augmenter le timeout dans `TestConfig.java`
  ```java
  public static final int AUTH_TIMEOUT = 30; // Augmenter de 20 à 30
  ```
- Vérifier que Keycloak est démarré : `curl http://localhost:6080`
- Vérifier la connexion réseau

### Problème 2 : Identifiants incorrects

**Symptôme :**
```
⚠️ Toujours sur la page Keycloak après authentification
```

**Solutions :**
- Vérifier les identifiants dans `TestConfig.java`
- Tester manuellement dans un navigateur :
  1. Aller sur http://localhost:9000/front/
  2. Essayer de se connecter avec testuser/testpassword
- Créer/vérifier l'utilisateur dans Keycloak Admin Console

### Problème 3 : Keycloak non démarré

**Symptôme :**
```
java.net.ConnectException: Connection refused
```

**Solution :**
```bash
# Démarrer Keycloak
docker start keycloak
# OU
./keycloak.sh start-dev
```

### Problème 4 : Éléments non trouvés

**Symptôme :**
```
NoSuchElementException: Unable to locate element: {"method":"id","selector":"username"}
```

**Solutions :**
- Vérifier l'URL de Keycloak dans `TestConfig.java`
- Vérifier la structure HTML de la page de login Keycloak
- Augmenter le timeout d'attente

---

## 🔒 Sécurité

### ⚠️ Bonnes pratiques

1. **Ne JAMAIS commiter les vrais identifiants dans Git**
   ```gitignore
   # .gitignore
   test.properties
   ```

2. **Utiliser des utilisateurs de test dédiés**
   - Créer un utilisateur spécifique pour les tests
   - Ne pas utiliser de comptes administrateurs

3. **Variables d'environnement en CI/CD**
   ```yaml
   # .gitlab-ci.yml ou Jenkinsfile
   variables:
     KEYCLOAK_USERNAME: ${CI_KEYCLOAK_USERNAME}
     KEYCLOAK_PASSWORD: ${CI_KEYCLOAK_PASSWORD}
   ```

4. **Rotation régulière des mots de passe de test**

---

## 📋 Checklist de configuration

Avant de lancer les tests :

- [ ] Keycloak est démarré sur http://localhost:6080
- [ ] L'application RHDemo est démarrée sur http://localhost:9000
- [ ] L'utilisateur de test existe dans Keycloak
- [ ] Les identifiants sont configurés dans TestConfig.java
- [ ] Le navigateur (Firefox/Chrome) est installé
- [ ] WebDriverManager peut télécharger les drivers

---

## 🎓 Exemple complet

### 1. Configuration de l'utilisateur Keycloak

```bash
# Dans Keycloak Admin Console
1. Aller sur http://localhost:6080/admin
2. Realm: LeuwenRealm
3. Users > Add User
   - Username: testuser
   - Email: test@example.com
4. Credentials > Set Password
   - Password: testpassword
   - Temporary: OFF
5. Role Mappings
   - Ajouter les rôles : consult, MAJ
```

### 2. Configuration TestConfig.java

```java
public static final String TEST_USERNAME = "testuser";
public static final String TEST_PASSWORD = "testpassword";
```

### 3. Exécution des tests

```bash
cd /home/leno-vo/git/repository/rhDemoAPITestIHM
./run-tests.sh
```

### 4. Résultat attendu

```
🚀 Initialisation du navigateur pour la suite de tests...
✅ Navigateur firefox initialisé avec succès
🔐 Authentification Keycloak en cours...
📋 Page de login Keycloak détectée
✏️ Username saisi: testuser
✏️ Password saisi
🔘 Bouton de connexion cliqué
✅ Authentification Keycloak réussie !
🌐 URL actuelle: http://localhost:9000/front/

[INFO] Running fr.leuwen.rhdemo.tests.EmployeLifecycleTest
🔵 ÉTAPE 1: Ajout d'un nouvel employé
✅ Employé ajouté avec succès
...
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0
```

---

## 📚 Ressources

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Selenium WebDriver Waits](https://www.selenium.dev/documentation/webdriver/waits/)
- [Element Plus Form Documentation](https://element-plus.org/en-US/component/form.html)

---

**Date de création :** 28 octobre 2025  
**Version :** 1.0  
**Projet :** rhDemoAPITestIHM  
**Statut :** ✅ Authentification Keycloak automatisée
