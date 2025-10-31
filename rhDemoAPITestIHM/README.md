# RH Demo API - Tests IHM Selenium

Projet de tests d'interface utilisateur (IHM) pour l'application RH Demo utilisant Selenium WebDriver et JUnit 5.

## 📋 Description

Ce projet contient des tests automatisés end-to-end qui testent l'interface utilisateur de l'application RH Demo. Les tests utilisent le pattern Page Object Model (POM) pour une meilleure maintenabilité.

## 🎯 Tests couverts

### Test principal : `EmployeLifecycleTest`
Test du cycle complet de gestion d'un employé :

1. **Ajout d'un employé** : Création d'un nouvel employé via le formulaire
2. **Vérification dans la liste** : Confirmation que l'employé apparaît dans la liste
3. **Suppression** : Suppression de l'employé par son ID
4. **Vérification de suppression** : Confirmation que l'employé n'est plus dans la liste

## 🛠️ Technologies utilisées

- **Java 21** : Langage de programmation
- **JUnit 5** : Framework de tests
- **Selenium WebDriver 4.15** : Automation du navigateur
- **WebDriverManager** : Gestion automatique des drivers
- **AssertJ** : Assertions fluides et expressives
- **Maven** : Gestion de projet et dépendances

## 📁 Structure du projet

```
rhDemoAPITestIHM/
├── src/test/java/fr/leuwen/rhdemo/tests/
│   ├── base/
│   │   └── BaseSeleniumTest.java       # Classe de base pour tous les tests
│   ├── config/
│   │   └── TestConfig.java             # Configuration centralisée
│   ├── pages/
│   │   ├── EmployeAddPage.java         # Page Object: Ajout employé
│   │   ├── EmployeListPage.java        # Page Object: Liste employés
│   │   └── EmployeDeletePage.java      # Page Object: Suppression employé
│   └── EmployeLifecycleTest.java       # Test principal du cycle de vie
├── pom.xml                              # Configuration Maven
└── README.md                            # Ce fichier
```

## ⚙️ Prérequis

1. **Java 21** installé
2. **Maven 3.6+** installé
3. **Chrome** ou **Firefox** installé
4. **Application RH Demo** en cours d'exécution sur `http://localhost:9000`

## 🚀 Lancement des tests

### 1. Démarrer l'application RH Demo

Depuis le projet `rhdemo` :
```bash
cd /home/leno-vo/git/repository/rhdemo
./mvnw spring-boot:run
```

### 2. Lancer les tests Selenium

Depuis ce projet :
```bash
cd /home/leno-vo/git/repository/rhDemoAPITestIHM
mvn clean test
```

### 3. Lancer un test spécifique

```bash
mvn test -Dtest=EmployeLifecycleTest
```

## ⚙️ Configuration

La configuration des tests se trouve dans `TestConfig.java` :

- **BASE_URL** : URL de l'application (par défaut : `http://localhost:9000`)
- **BROWSER** : Navigateur à utiliser (`chrome` ou `firefox`)
- **HEADLESS_MODE** : Mode sans interface graphique (`false` par défaut)
- **TIMEOUTS** : Timeouts pour les attentes implicites et explicites

### Mode Headless

Pour exécuter les tests sans interface graphique (utile pour CI/CD) :

```java
// Dans TestConfig.java
public static final boolean HEADLESS_MODE = true;
```

## 📊 Résultats des tests

Les résultats sont affichés dans la console avec des logs détaillés :
- 🔵 Indique le début d'une étape
- ✅ Indique une étape réussie
- 🎉 Indique la fin du test complet

Exemple de sortie :
```
🔵 ÉTAPE 1: Ajout d'un nouvel employé
✅ Employé ajouté avec succès
🔵 ÉTAPE 2: Vérification de la présence dans la liste
✅ Employé trouvé dans la liste avec l'ID: 5
✅ Toutes les données de l'employé sont correctes
🔵 ÉTAPE 3: Suppression de l'employé
✅ Employé trouvé, lancement de la suppression...
✅ Employé supprimé avec succès
🔵 ÉTAPE 4: Vérification de l'absence de l'employé dans la liste
✅ Employé bien supprimé de la liste
🎉 Test complet du cycle de vie terminé avec succès!
```

## 📝 Bonnes pratiques

### Page Object Model (POM)
Les tests utilisent le pattern POM qui :
- Sépare la logique de test de la structure des pages
- Facilite la maintenance
- Améliore la réutilisabilité du code

### Attentes explicites
Utilisation de `WebDriverWait` pour attendre les éléments :
```java
wait.until(ExpectedConditions.visibilityOfElementLocated(locator));
```

### Assertions expressives
Utilisation d'AssertJ pour des assertions claires :
```java
assertThat(listPage.isEmployePresentByEmail(email))
    .as("L'employé devrait être présent dans la liste")
    .isTrue();
```

## 🔧 Dépannage

### Le navigateur ne se lance pas
- Vérifiez que Chrome ou Firefox est installé
- WebDriverManager télécharge automatiquement les drivers

### L'application n'est pas accessible
- Vérifiez que l'application RH Demo est démarrée
- Vérifiez l'URL dans `TestConfig.java`

### Tests qui échouent de manière intermittente
- Augmentez les timeouts dans `TestConfig.java`
- Vérifiez la stabilité de l'application

## 📚 Ressources

- [Selenium Documentation](https://www.selenium.dev/documentation/)
- [JUnit 5 User Guide](https://junit.org/junit5/docs/current/user-guide/)
- [AssertJ Documentation](https://assertj.github.io/doc/)

## 👤 Auteur

Projet créé pour tester l'application RH Demo

## 📄 Licence

Ce projet est un outil de test pour l'application RH Demo.
