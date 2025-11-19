# 🌐 Navigation unique - Firefox lancé une seule fois

## 📋 Problème résolu

**Avant** : Firefox était lancé à chaque test (`@BeforeEach`), nécessitant une **authentification Keycloak à chaque fois**.

**Maintenant** : Firefox est lancé **une seule fois** au début de la suite de tests (`@BeforeAll`), l'authentification n'est requise **qu'une seule fois**.

---

## 🔧 Modifications apportées

### 1. BaseSeleniumTest.java

**Changements :**
- ✅ `@BeforeEach` → `@BeforeAll` (méthode statique)
- ✅ `@AfterEach` → `@AfterAll` (méthode statique)
- ✅ `driver` et `wait` sont maintenant **statiques**
- ✅ Le navigateur reste ouvert pendant toute la suite de tests

**Avant :**
```java
protected WebDriver driver;
protected WebDriverWait wait;

@BeforeEach
public void setUp() {
    // Lancement du navigateur
}

@AfterEach
public void tearDown() {
    driver.quit(); // Fermeture après CHAQUE test
}
```

**Après :**
```java
protected static WebDriver driver;
protected static WebDriverWait wait;

@BeforeAll
public static void setUpClass() {
    // Lancement du navigateur UNE SEULE FOIS
}

@AfterAll
public static void tearDownClass() {
    driver.quit(); // Fermeture après TOUS les tests
}
```

---

### 2. EmployeLifecycleTest.java

**Changements :**
- ✅ `addPage`, `listPage`, `deletePage` sont maintenant **statiques**
- ✅ `@BeforeEach setUp()` → `@BeforeAll setUpTests()` (méthode statique)
- ✅ Suppression de `@AfterEach logTestResult()`

**Avant :**
```java
private EmployeAddPage addPage;
private EmployeListPage listPage;
private EmployeDeletePage deletePage;

@BeforeEach
@Override
public void setUp() {
    super.setUp();
    addPage = new EmployeAddPage(driver);
    // ...
}
```

**Après :**
```java
private static EmployeAddPage addPage;
private static EmployeListPage listPage;
private static EmployeDeletePage deletePage;

@BeforeAll
public static void setUpTests() {
    // Initialisation APRÈS le setup du driver
    addPage = new EmployeAddPage(driver);
    // ...
}
```

---

### 3. EmployeAdditionalTest.java

**Mêmes modifications que EmployeLifecycleTest.java**

---

## ✨ Avantages

### 1. **Authentification unique**
- 🔐 Connexion Keycloak **une seule fois** au début
- ⏱️ Gain de temps considérable (pas de reconnexion entre tests)
- 🎯 Session maintenue pendant toute la suite de tests

### 2. **Performance améliorée**
- 🚀 **Pas de restart du navigateur** entre chaque test
- ⚡ Tests beaucoup plus rapides
- 📉 Réduction de la charge système

### 3. **Meilleure expérience**
- 👀 Plus facile d'observer les tests en action
- 🔄 Moins de fenêtres Firefox qui s'ouvrent/ferment
- 💻 Moins de ressources consommées

---

## 📊 Comparaison

### Avant (authentification multiple)

```
🚀 Lancement Firefox → 🔐 Authentification
✅ Test 1
🛑 Fermeture Firefox

🚀 Lancement Firefox → 🔐 Authentification  ← Répétition !
✅ Test 2
🛑 Fermeture Firefox

🚀 Lancement Firefox → 🔐 Authentification  ← Répétition !
✅ Test 3
🛑 Fermeture Firefox

...
```

### Après (authentification unique)

```
🚀 Lancement Firefox → 🔐 Authentification (UNE FOIS)
✅ Test 1
✅ Test 2
✅ Test 3
✅ Test 4
✅ Test 5
✅ Test 6
✅ Test 7
✅ Test 8
🛑 Fermeture Firefox
```

---

## ⚠️ Points d'attention

### 1. État du navigateur partagé

Les tests **partagent la même instance** du navigateur :
- ✅ Session Keycloak maintenue
- ⚠️ Cookies partagés entre tests
- ⚠️ LocalStorage partagé entre tests

**Recommandation** : Si un test modifie l'état de l'application, pensez à nettoyer après.

### 2. Ordre des tests important

Avec `@TestMethodOrder(MethodOrderer.OrderAnnotation.class)`, l'ordre est respecté :
1. Test 1 : Ajout employé
2. Test 2 : Vérification présence
3. Test 3 : Suppression
4. Test 4 : Vérification absence

### 3. Isolation des tests

**EmployeLifecycleTest** :
- Tests ordonnés et dépendants (OK pour un scénario complet)
- Utilise `@Order(1)`, `@Order(2)`, etc.

**EmployeAdditionalTest** :
- Tests **indépendants** (chaque test nettoie ses données)
- Chaque test crée et supprime son propre employé de test

---

## 🧪 Cycle de vie des tests

```
┌─────────────────────────────────────────┐
│  @BeforeAll setUpClass()                │
│  ↓                                       │
│  🚀 Lancement Firefox                   │
│  🔐 Authentification Keycloak (1 fois)  │
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│  @BeforeAll setUpTests()                │
│  ↓                                       │
│  Initialisation des Page Objects        │
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│  @Test test1()                          │
│  @Test test2()                          │
│  @Test test3()                          │
│  ...                                     │
│  (Tous les tests s'exécutent)           │
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│  @AfterAll tearDownClass()              │
│  ↓                                       │
│  🛑 Fermeture Firefox                   │
└─────────────────────────────────────────┘
```

---

## 🚀 Exécution des tests

### Commande inchangée

```bash
cd /home/leno-vo/git/repository/rhDemoAPITestIHM
./run-tests.sh
```

ou

```bash
/home/leno-vo/git/repository/rhDemo/mvnw test
```

### Sortie attendue

```
[INFO] Running fr.leuwen.rhdemo.tests.EmployeLifecycleTest
🚀 Initialisation du navigateur pour la suite de tests...
✅ Navigateur firefox initialisé avec succès

🔵 ÉTAPE 1: Ajout d'un nouvel employé
✅ Employé ajouté avec succès

🔵 ÉTAPE 2: Vérification de la présence dans la liste
✅ Employé trouvé dans la liste avec l'ID: 5
✅ Toutes les données de l'employé sont correctes

🔵 ÉTAPE 3: Suppression de l'employé
✅ Employé trouvé, lancement de la suppression...
✅ Employé supprimé avec succès

🔵 ÉTAPE 4: Vérification de l'absence
✅ Employé bien supprimé de la liste
🎉 Test complet du cycle de vie terminé avec succès!

🛑 Fermeture du navigateur...
✅ Navigateur fermé

[INFO] Tests run: 4, Failures: 0, Errors: 0, Skipped: 0
```

---

## 🔄 Retour en arrière (si nécessaire)

Si vous souhaitez revenir à l'ancien comportement (navigateur relancé à chaque test) :

### BaseSeleniumTest.java
```java
// Remplacer @BeforeAll par @BeforeEach
// Remplacer @AfterAll par @AfterEach
// Retirer 'static' de driver et wait
```

### Tests
```java
// Remplacer @BeforeAll par @BeforeEach
// Retirer 'static' des Page Objects
```

---

## 📚 Références JUnit 5

- **@BeforeAll** : Exécuté **UNE FOIS** avant tous les tests de la classe
- **@AfterAll** : Exécuté **UNE FOIS** après tous les tests de la classe
- **@BeforeEach** : Exécuté **AVANT CHAQUE** test
- **@AfterEach** : Exécuté **APRÈS CHAQUE** test

**Important** : Les méthodes `@BeforeAll` et `@AfterAll` doivent être **statiques**.

---

## ✅ Résumé

| Aspect | Avant | Après |
|--------|-------|-------|
| **Lancement Firefox** | À chaque test | Une seule fois |
| **Authentification** | À chaque test | Une seule fois |
| **Performance** | Lente | Rapide ⚡ |
| **Ressources** | Élevées | Optimisées |
| **Experience** | Fenêtres multiples | Fenêtre unique |
| **Session Keycloak** | Perdue entre tests | Maintenue |

---

**Date de modification :** 28 octobre 2025  
**Fichiers modifiés :** 3 (BaseSeleniumTest.java, EmployeLifecycleTest.java, EmployeAdditionalTest.java)  
**Impact :** Authentification unique + meilleure performance
