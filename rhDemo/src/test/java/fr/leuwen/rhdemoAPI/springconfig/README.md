# Tests Spring Security - Guide rapide

## 🚀 Lancement des tests

### Tous les tests de sécurité

```bash
cd /home/leno-vo/git/repository/rhDemo
./mvnw test -Dtest="fr.leuwen.rhdemoAPI.springconfig.*Test"
```

### Tests individuels

**Tests du mapper Keycloak :**
```bash
./mvnw test -Dtest=GrantedAuthoritiesKeyCloakMapperTest
```

**Tests de SecurityConfig (intégration) :**
```bash
./mvnw test -Dtest=SecurityConfigIT
```

**Tests de génération CSP dynamique :**
```bash
./mvnw test -Dtest=SecurityConfigCspDynamicTest
```

## 📋 Fichiers de test

| Fichier | Description | Nombre de tests |
|---------|-------------|-----------------|
| `GrantedAuthoritiesKeyCloakMapperTest.java` | Tests unitaires du mapper de rôles | 10 |
| `SecurityConfigIT.java` | Tests d'intégration de la sécurité | 15 |
| `SecurityConfigCspDynamicTest.java` | Tests de génération CSP | 12 |
| `TestSecurityConfig.java` (dans `config/`) | Configuration de sécurité pour tests | N/A |

## ✅ Résultat attendu

```
[INFO] -------------------------------------------------------
[INFO]  T E S T S
[INFO] -------------------------------------------------------
[INFO] Running GrantedAuthoritiesKeyCloakMapper - Tests unitaires
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running SecurityConfig - Tests de génération dynamique CSP
[INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running SecurityConfig - Tests d'intégration
[INFO] Tests run: 15, Failures: 0, Errors: 0, Skipped: 0
[INFO]
[INFO] Results:
[INFO]
[INFO] Tests run: 37, Failures: 0, Errors: 0, Skipped: 0
[INFO]
[INFO] ------------------------------------------------------------------------
[INFO] BUILD SUCCESS
[INFO] ------------------------------------------------------------------------
```

## 📊 Couverture de code

Pour un rapport de couverture avec JaCoCo, voir [TESTS_SECURITE_COUVERTURE.md](../../../../../../../docs/TESTS_SECURITE_COUVERTURE.md).

## 🔧 Configuration

- **Profil actif:** `test`
- **Base de données:** H2 en mémoire (`jdbc:h2:mem:testdb`)
- **Sécurité:** Configuration simplifiée sans OAuth2/Keycloak
- **Configuration:** `src/test/resources/application-test.yml`
