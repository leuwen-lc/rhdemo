# Projet rhDemoAPITestIHM - Tests Selenium

## 📦 Contenu du projet

### Structure complète
```
rhDemoAPITestIHM/
├── src/test/java/fr/leuwen/rhdemo/tests/
│   ├── base/
│   │   └── BaseSeleniumTest.java           # Classe de base avec setup/teardown
│   ├── config/
│   │   └── TestConfig.java                 # Configuration centralisée
│   ├── pages/
│   │   ├── EmployeAddPage.java            # Page Object: Formulaire d'ajout
│   │   ├── EmployeListPage.java           # Page Object: Liste des employés
│   │   └── EmployeDeletePage.java         # Page Object: Suppression
│   ├── EmployeLifecycleTest.java          # TEST PRINCIPAL (cycle complet)
│   └── EmployeAdditionalTest.java         # Tests supplémentaires
├── src/test/resources/
│   └── test.properties                     # Propriétés de configuration
├── pom.xml                                 # Configuration Maven
├── README.md                               # Documentation
├── .gitignore                              # Fichiers à ignorer
└── run-tests.sh                            # Script de lancement

## 🎯 Test Principal: EmployeLifecycleTest

Ce test valide le cycle complet de gestion d'un employé:

### Étape 1: Ajout d'un employé
- Navigate vers /front/ajout
- Remplit le formulaire (prénom, nom, email, adresse)
- Soumet le formulaire
- Vérifie le message de succès
- Vérifie la redirection vers la liste

### Étape 2: Vérification dans la liste
- Navigate vers /front/employes
- Attend le chargement de la table
- Recherche l'employé par email
- Recherche l'employé par nom
- Récupère l'ID pour la suppression
- Vérifie toutes les données affichées

### Étape 3: Suppression
- Navigate vers /front/suppression
- Recherche l'employé par ID
- Vérifie l'affichage des détails
- Clique sur Supprimer
- Confirme la suppression
- Vérifie le message de succès

### Étape 4: Vérification finale
- Retourne sur la liste
- Actualise la liste
- Vérifie que l'employé n'est plus présent

## 🧪 Tests Additionnels: EmployeAdditionalTest

1. **Test adresse optionnelle**: Vérifie qu'on peut créer un employé sans adresse
2. **Test nombre d'employés**: Vérifie le comptage des employés
3. **Test employés par défaut**: Vérifie la présence de Laurent, Sophie, Agathe
4. **Test navigation**: Vérifie la navigation entre les pages

## ⚙️ Configuration

### TestConfig.java
- BASE_URL: http://localhost:9000
- BROWSER: chrome (changeable en firefox)
- HEADLESS_MODE: false (mettre true pour CI/CD)
- TIMEOUTS: 10s implicit, 15s explicit, 30s page load

### test.properties
Configuration externe pour personnaliser les tests

## 🚀 Commandes rapides

### Lancer tous les tests
```bash
cd /home/leno-vo/git/repository/rhDemoAPITestIHM
mvn clean test
```

### Lancer le test principal uniquement
```bash
mvn test -Dtest=EmployeLifecycleTest
```

### Lancer les tests additionnels uniquement
```bash
mvn test -Dtest=EmployeAdditionalTest
```

### Utiliser le script
```bash
./run-tests.sh
```

## 📊 Dépendances Maven

- selenium-java: 4.15.0
- webdrivermanager: 5.6.2
- junit-jupiter: 5.10.1
- assertj-core: 3.24.2

## 🔍 Pattern utilisé: Page Object Model (POM)

Avantages:
✅ Séparation des préoccupations
✅ Code réutilisable
✅ Facilité de maintenance
✅ Tests plus lisibles

## ⚠️ Prérequis avant de lancer les tests

1. Java 21 installé
2. Maven 3.6+ installé
3. Chrome ou Firefox installé
4. **APPLICATION RHDEMO DÉMARRÉE** sur http://localhost:9000

## 💡 Notes importantes

- Les tests sont ordonnés (@Order) pour le test du cycle de vie
- WebDriverManager gère automatiquement les drivers
- Le mode headless est désactivé par défaut pour voir les tests
- Les tests nettoient après eux (suppression des données de test)

## 🎓 Pour étendre les tests

1. Créer un nouveau Page Object dans pages/
2. Créer une nouvelle classe de test héritant de BaseSeleniumTest
3. Utiliser les Page Objects pour interagir avec l'application
4. Utiliser AssertJ pour les assertions

Exemple:
```java
@Test
public void myNewTest() {
    driver.get(TestConfig.EMPLOYE_ADD_URL);
    addPage.fillEmployeForm(...);
    assertThat(addPage.isSuccessMessageDisplayed()).isTrue();
}
```
