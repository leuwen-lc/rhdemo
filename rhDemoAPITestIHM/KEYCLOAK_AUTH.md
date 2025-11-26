# 🔐 Authentification Keycloak - Guide de configuration

## 📋 Vue d'ensemble

Les tests Selenium s'authentifient **automatiquement** sur Keycloak au démarrage de la suite de tests (une seule fois pour tous les tests).

## ⚙️ Paramétrage

### 1. Fichiers de configuration

#### test.yml
#### test-credentils.yml (à créer à partir du template fourni)

### Paramètres initialisables également par variables d'environnement (pour CI/CD)

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

## 🧪 Test de l'authentification

### Test manuel

1. **Démarrer Keycloak** (si ce n'est pas déjà fait)
   ```bash
   # Vérifier que Keycloak tourne sur le port prévu
   par exemple curl -I http://localhost:6080
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
- Vérifier les identifiants dans les paramètres
- Tester manuellement dans un navigateur :
  1. Aller sur http://localhost:9000/front/
  2. Essayer de se connecter avec user/password
- Créer/vérifier l'utilisateur dans Keycloak Admin Console

### Problème 3 : Keycloak non démarré

**Symptôme :**
```
java.net.ConnectException: Connection refused
```

### Problème 4 : Éléments non trouvés

**Symptôme :**
```
NoSuchElementException: Unable to locate element: {"method":"id","selector":"username"}
```

**Solutions :**
- Vérifier l'URL de Keycloak dans le paramétrage
- Vérifier la structure HTML de la page de login Keycloak
- Augmenter le timeout d'attente

---

## 🔒 Sécurité

### ⚠️ Bonnes pratiques

1. **Ne JAMAIS commiter les vrais identifiants dans Git**
   ```gitignore
   # .gitignore
   test-credentials.yaml
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

- [ ] Keycloak est démarré par exemple sur http://localhost:6090
- [ ] L'application RHDemo est démarrée par exemple sur http://localhost:9000
- [ ] L'utilisateur de test existe dans Keycloak
- [ ] Les identifiants sont configurés dans test-credentials.yml
- [ ] Le navigateur (Firefox/Chrome) est installé
- [ ] WebDriverManager peut télécharger les drivers

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
