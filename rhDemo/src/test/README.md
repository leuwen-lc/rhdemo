# Tests RHDemo API

## Structure des tests

### Tests d'intégration (@SpringBootTest)
Ces tests démarrent le contexte Spring complet et testent l'application de bout en bout.

- **EmployeControllerIntegrationTest** - Tests des endpoints REST avec authentification
  - GET /api/employes - Liste complète avec autorisations
  - GET /api/employes/page - Pagination
  - GET /api/employe?id=X - Récupération d'un employé
  - POST /api/employe - Création/modification avec validation
  - DELETE /api/employe?id=X - Suppression

- **AccueilControllerIntegrationTest** - Tests des endpoints d'information
  - GET / - Page d'accueil
  - GET /who - Informations utilisateur connecté

- **GlobalExceptionHandlerTest** - Tests de gestion d'erreurs
  - 404 - EmployeNotFoundException
  - 400 - Validation errors
  - 400 - Type mismatch errors
  - 403 - Security exceptions (non interceptées)

### Tests unitaires (@ExtendWith(MockitoExtension))
Ces tests isolent la logique métier en mockant les dépendances.

- **EmployeServiceTest** - Tests de la couche service
  - getEmploye() - Cas nominal et exceptions
  - getEmployes() - Liste vide et avec données
  - getEmployesPage() - Pagination
  - deleteEmploye() - Suppression et exceptions
  - saveEmploye() - Création et modification

- **EmployeValidationTest** - Tests des contraintes de validation
  - @NotBlank sur prenom, nom, mail, adresse
  - @Email sur mail
  - @Size(max=100) sur prenom, nom, mail
  - @Size(max=200) sur adresse
  - Edge cases (longueurs exactes)

### Configuration de test

- **TestSecurityConfig** - Configuration de sécurité allégée pour les tests
- **application-test.yml** - Configuration Spring pour environnement de test (H2)

## Exécution des tests

### Tests unitaires seulement
```bash
./mvnw test
```

### Tests unitaires + intégration
```bash
./mvnw verify
```

### Avec couverture JaCoCo
```bash
./mvnw verify
# Rapport HTML: target/site/jacoco/index.html
```

### Tests spécifiques
```bash
./mvnw test -Dtest=EmployeServiceTest
./mvnw test -Dtest=EmployeControllerIntegrationTest#testGetEmployes_WithConsultRole_ShouldReturnList
```

## Couverture de code

Les tests couvrent :
- ✅ Tous les endpoints REST (EmployeController + AccueilController)
- ✅ Toute la logique métier (EmployeService)
- ✅ Gestion des exceptions (GlobalExceptionHandler)
- ✅ Validation du modèle (Employe)
- ✅ Autorisations (rôles consult et MAJ)

**Cibles de couverture :**
- Lignes : > 80%
- Branches : > 70%
- Méthodes : > 80%

## Bonnes pratiques

1. **Nommage des tests** : `testMethodName_Condition_ExpectedResult`
2. **Arrange-Act-Assert** : Structure claire des tests
3. **Tests indépendants** : Pas de dépendances entre tests
4. **Données de test** : Utiliser data.sql pour les tests d'intégration
5. **Mocks** : Utiliser Mockito pour isoler les dépendances

## Données de test

Le fichier `src/test/resources/data.sql` contient 4 employés de test :
- ID 1 : Laurent Olivier
- ID 2 : Patrick Linder
- ID 3 : Paul Atreides
- ID 4 : Henri Martin
