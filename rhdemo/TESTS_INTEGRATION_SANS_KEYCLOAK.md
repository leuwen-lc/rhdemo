# Tests d'Intégration Sans Dépendance Keycloak

## Problème

Les tests d'intégration Spring Boot échouaient car ils dépendaient de la configuration `SecurityConfig` qui nécessite une instance Keycloak en cours d'exécution (`ClientRegistrationRepository`, `GrantedAuthoritiesKeyCloakMapper`, etc.).

## Solution Mise en Place

### 1. Profil de Test dans les Composants OAuth2

Ajout de l'annotation `@Profile("!test")` pour désactiver la configuration OAuth2 pendant les tests :

**`SecurityConfig.java`:**
```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@Profile("!test") // Désactive cette configuration pour le profil "test"
public class SecurityConfig {
    // ... configuration OAuth2/Keycloak
}
```

**`GrantedAuthoritiesKeyCloakMapper.java`:**
```java
@Component
@Profile("!test") // Désactive ce mapper pour les tests
public class GrantedAuthoritiesKeyCloakMapper implements GrantedAuthoritiesMapper {
    // ... extraction des rôles depuis le token Keycloak
}
```

### 2. Configuration de Sécurité Pour Tests

Création de `TestSecurityConfig.java` qui remplace `SecurityConfig` pendant les tests :

**Fichier**: `src/test/java/fr/leuwen/rhdemoAPI/config/TestSecurityConfig.java`

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@Profile("test") // Active uniquement pour le profil "test"
public class TestSecurityConfig {
    @Bean
    public SecurityFilterChain testFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/who", "/error*", "/api-docs", "/actuator/**").permitAll()
                .anyRequest().authenticated()
            )
            .httpBasic(basic -> {});
        return http.build();
    }
}
```

Cette configuration:
- **Désactive CSRF** pour simplifier les tests
- **Désactive OAuth2/Keycloak** - pas besoin de serveur externe
- **Utilise l'authentification basique** - mockée via `@WithMockUser`
- **Préserve `@EnableMethodSecurity`** - permet les annotations `@PreAuthorize` sur les contrôleurs

### 3. Configuration de Test avec H2

**Fichier**: `src/test/resources/application-test.properties`

```properties
# Utilise H2 en mémoire au lieu de PostgreSQL
spring.datasource.url=jdbc:h2:mem:testdb
spring.datasource.driver-class-name=org.h2.Driver
spring.datasource.username=sa
spring.datasource.password=

# Laisse Hibernate créer le schéma
spring.jpa.hibernate.ddl-auto=create-drop

# IMPORTANT: Charge les données APRÈS création du schéma
spring.jpa.defer-datasource-initialization=true
spring.sql.init.mode=always

# CRITIQUE: Désactive complètement l'auto-configuration OAuth2
# Sans cela, Spring tente de se connecter à Keycloak même avec @Profile
spring.autoconfigure.exclude=\
  org.springframework.boot.autoconfigure.security.oauth2.client.servlet.OAuth2ClientAutoConfiguration,\
  org.springframework.boot.autoconfigure.security.oauth2.resource.servlet.OAuth2ResourceServerAutoConfiguration
```

**Données de test**: Utilise `src/main/resources/data.sql` (chargé automatiquement par Spring)

### 4. Annotation des Tests

```java
@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.properties")
@AutoConfigureMockMvc
@ActiveProfiles("test") // Active le profil "test"
public class EmployeControllerTest {
    
    @Autowired
    private MockMvc mockMVC;
    
    @Test
    @WithMockUser(username = "UtilisateurTest", roles = {"consult"})
    public void testGetEmployes() throws Exception {
        mockMVC.perform(get("/api/employes"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].prenom", is("Laurent")));
    }
    
    @Test
    @WithMockUser(username = "UtilisateurTest", roles = {"Mauvais role"})
    public void testGetEmployesRoleErrone() throws Exception {
        mockMVC.perform(get("/api/employes"))
            .andExpect(status().is4xxClientError());
    }
}
```

## Avantages de Cette Approche

✅ **Tests indépendants** - Pas besoin de Keycloak en cours d'exécution  
✅ **Tests plus rapides** - Base H2 en mémoire  
✅ **Sécurité préservée** - `@PreAuthorize` fonctionne toujours avec `@WithMockUser`  
✅ **Production inchangée** - `SecurityConfig` reste actif en production  
✅ **CI/CD friendly** - Tests exécutables sans services externes

## Utilisation

### Exécuter les tests

```bash
# Via Maven
./mvnw test

# Via IDE
# Exécuter EmployeControllerTest.java
```

### Ajouter de nouveaux tests

1. Utiliser `@WithMockUser` pour simuler l'authentification
2. Définir les `roles` selon les besoins (sans préfixe "ROLE_")
3. Les annotations `@PreAuthorize` sur les contrôleurs sont respectées

### Exemple de test avec différents rôles

```java
@Test
@WithMockUser(username = "admin", roles = {"admin"})
public void testActuatorAvecRoleAdmin() throws Exception {
    mockMVC.perform(get("/actuator/health"))
        .andExpect(status().isOk());
}

@Test
@WithMockUser(username = "user", roles = {"consult"})
public void testActuatorSansRoleAdmin() throws Exception {
    mockMVC.perform(get("/actuator/health"))
        .andExpect(status().isForbidden());
}
```

## Fichiers Modifiés/Créés

- ✏️ `src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java` - Ajout `@Profile("!test")`
- ✏️ `src/main/java/fr/leuwen/rhdemoAPI/springconfig/GrantedAuthoritiesKeyCloakMapper.java` - Ajout `@Profile("!test")`
- ✨ `src/test/java/fr/leuwen/rhdemoAPI/config/TestSecurityConfig.java` - Nouvelle configuration de test
- ✨ `src/test/resources/application-test.properties` - Configuration H2, profil test et exclusion OAuth2

- ✏️ `src/test/java/fr/leuwen/rhdemoAPI/EmployeControllerTest.java` - Ajout `@ActiveProfiles("test")`

## Notes Techniques

### Pourquoi Exclure l'Auto-Configuration OAuth2 ?

L'ajout de `@Profile("!test")` sur `SecurityConfig` ne suffit pas. Spring Boot possède des **auto-configurations** qui se chargent automatiquement :

- `OAuth2ClientAutoConfiguration` - Configure le client OAuth2
- `OAuth2ResourceServerAutoConfiguration` - Configure le serveur de ressources

Ces auto-configurations tentent de **se connecter à Keycloak** même si `SecurityConfig` est désactivé, car elles lisent les propriétés `spring.security.oauth2.client.*` depuis `application.properties`.

**Solution**: Exclure explicitement ces auto-configurations dans `application-test.properties` :

```properties
spring.autoconfigure.exclude=\
  org.springframework.boot.autoconfigure.security.oauth2.client.servlet.OAuth2ClientAutoConfiguration,\
  org.springframework.boot.autoconfigure.security.oauth2.resource.servlet.OAuth2ResourceServerAutoConfiguration
```

### Ordre de Chargement des Données

L'ordre est crucial avec H2 et Hibernate :

1. `spring.jpa.hibernate.ddl-auto=create-drop` - Hibernate crée le schéma
2. `spring.jpa.defer-datasource-initialization=true` - Attend que Hibernate termine
3. `spring.sql.init.mode=always` - Charge `data.sql`

Sans `defer-datasource-initialization`, Spring tente de charger `data.sql` avant que Hibernate ne crée les tables → erreur!

### Profils Spring

- **Profil Production** (par défaut) : `SecurityConfig` actif, OAuth2/Keycloak requis
- **Profil Test** (`test`) : `TestSecurityConfig` actif, authentication mockée

Le profil est activé via `@ActiveProfiles("test")` dans les tests.
