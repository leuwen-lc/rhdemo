# 🎉 Projet de Tests Selenium - Démarrage Rapide

## ✅ Le projet a été créé avec succès !

Vous disposez maintenant d'un projet complet de tests Selenium pour l'application RH Demo.

## 📝 Ce qui a été créé

✅ **Projet Maven** avec toutes les dépendances nécessaires  
✅ **Tests JUnit 5** avec Selenium WebDriver  
✅ **Pattern Page Object Model** pour une maintenance facilitée  
✅ **Test du cycle complet** : Ajout → Vérification → Suppression  
✅ **Tests additionnels** : Adresse optionnelle, navigation, comptage  
✅ **Scripts de lancement** automatisés  
✅ **Documentation** complète

## 🚀 Lancement rapide (3 étapes)

### 1️⃣ Démarrer l'application RH Demo

```bash
cd /home/leno-vo/git/repository/rhdemo
./mvnw spring-boot:run
```

**Attendez** que le message "Started RhdemoApplication" apparaisse.

### 2️⃣ Dans un nouveau terminal, lancer les tests

```bash
cd /home/leno-vo/git/repository/rhDemoAPITestIHM
./run-tests.sh
```

OU manuellement :

```bash
cd /home/leno-vo/git/repository/rhDemoAPITestIHM
/home/leno-vo/git/repository/rhDemo/mvnw clean test
```

### 3️⃣ Observer les tests s'exécuter ! 👀

Les tests vont :
1. Ouvrir Chrome automatiquement
2. Ajouter un employé de test
3. Vérifier sa présence dans la liste
4. Le supprimer
5. Vérifier qu'il n'est plus dans la liste

## 📊 Résultats attendus

```
[INFO] -------------------------------------------------------
[INFO]  T E S T S
[INFO] -------------------------------------------------------
[INFO] Running fr.leuwen.rhdemo.tests.EmployeLifecycleTest
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
[INFO] Tests run: 4, Failures: 0, Errors: 0, Skipped: 0
[INFO] 
[INFO] Results:
[INFO] 
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0
[INFO]
[INFO] BUILD SUCCESS
```

## 📁 Structure du projet

```
rhDemoAPITestIHM/
├── src/test/java/fr/leuwen/rhdemo/tests/
│   ├── base/BaseSeleniumTest.java          # Classe de base
│   ├── config/TestConfig.java               # Configuration
│   ├── pages/                               # Page Objects
│   │   ├── EmployeAddPage.java
│   │   ├── EmployeListPage.java
│   │   └── EmployeDeletePage.java
│   ├── EmployeLifecycleTest.java           # Test principal ⭐
│   └── EmployeAdditionalTest.java          # Tests supplémentaires
├── pom.xml                                  # Configuration Maven
├── README.md                                # Documentation détaillée
├── PROJET_INFO.md                           # Guide complet
├── QUICKSTART.md                            # Ce fichier
└── run-tests.sh                             # Script de lancement
```

## ⚙️ Configuration

### Changer de navigateur

Éditez `src/test/java/fr/leuwen/rhdemo/tests/config/TestConfig.java` :

```java
public static final String BROWSER = "firefox";  // ou "chrome"
```

### Mode headless (sans interface)

Pour les tests en CI/CD :

```java
public static final boolean HEADLESS_MODE = true;
```

## 🔧 Commandes utiles

### Lancer un test spécifique

```bash
/home/leno-vo/git/repository/rhDemo/mvnw test -Dtest=EmployeLifecycleTest
```

### Lancer seulement les tests additionnels

```bash
/home/leno-vo/git/repository/rhDemo/mvnw test -Dtest=EmployeAdditionalTest
```

### Voir les logs détaillés

```bash
/home/leno-vo/git/repository/rhDemo/mvnw test -X
```

## 🐛 Dépannage

### Erreur : "Application not accessible"

➡️ **Solution** : Vérifiez que l'application RH Demo est démarrée sur http://localhost:9000

### Erreur : "Chrome not found"

➡️ **Solution** : Installez Chrome ou changez le navigateur dans TestConfig.java

### Tests qui échouent de manière aléatoire

➡️ **Solution** : Augmentez les timeouts dans TestConfig.java :

```java
public static final int EXPLICIT_WAIT = 20;  // au lieu de 15
```

## 📚 Documentation complète

- **README.md** : Documentation technique détaillée
- **PROJET_INFO.md** : Informations sur la structure et l'extension des tests
- **test.properties** : Configuration externalisée

## 🎓 Pour aller plus loin

### Ajouter un nouveau test

1. Créez une nouvelle classe de test dans `src/test/java/fr/leuwen/rhdemo/tests/`
2. Héritez de `BaseSeleniumTest`
3. Utilisez les Page Objects existants
4. Lancez avec `mvnw test`

### Créer un nouveau Page Object

1. Créez une classe dans `src/test/java/fr/leuwen/rhdemo/tests/pages/`
2. Définissez les locators (By)
3. Créez des méthodes pour interagir avec la page
4. Utilisez-le dans vos tests

## 💡 Bonnes pratiques

✅ Les tests nettoient après eux (suppression des données de test)  
✅ Utilisation de WebDriverWait pour les attentes explicites  
✅ Assertions expressives avec AssertJ  
✅ Pattern Page Object Model pour la maintenabilité  
✅ Configuration centralisée et personnalisable

## 🎯 Tests implémentés

### EmployeLifecycleTest (Test principal)
- ✅ Test 1 : Ajout d'un employé
- ✅ Test 2 : Vérification dans la liste
- ✅ Test 3 : Suppression
- ✅ Test 4 : Vérification de l'absence

### EmployeAdditionalTest
- ✅ Test de l'adresse optionnelle
- ✅ Test du comptage des employés
- ✅ Test de la présence des employés par défaut
- ✅ Test de navigation

## 🚨 Important

- ⚠️ Ce projet est **séparé** du projet rhdemo
- ⚠️ L'application RH Demo **doit être démarrée** avant les tests
- ⚠️ Les tests créent et suppriment des données de test
- ⚠️ Pensez à installer Chrome ou Firefox

## ✨ Succès !

Votre environnement de tests Selenium est prêt ! 🎉

Bon testing ! 🧪
