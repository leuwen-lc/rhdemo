# RHDemo Keycloak Initializer - Migration Spring Boot

## 📝 Résumé de la migration

Ce projet a été migré vers Spring Boot pour simplifier la gestion de configuration et moderniser l'architecture.

### Avant (Java standalone)
- **ConfigLoader.java** : 120 lignes de parsing YAML manuel avec `flattenYaml` récursif
- **Gestion manuelle** : Properties plates, pas de type-safety, pas d'injection de dépendances
- **Complexité** : Conversion manuelle des structures YAML imbriquées

### Après (Spring Boot 3.2.0)
- **@ConfigurationProperties** : Binding automatique YAML → Java objects
- **Type-safe** : Classes internes (Admin, Realm, Client, User) avec validation
- **Injection Spring** : Auto-wiring des services et du client Keycloak
- **Moins de code** : -120 lignes de code manuel, +simplicité

## 🏗️ Architecture

```
rhDemoInitKeycloak/
├── pom.xml                                 # Parent Spring Boot 3.2.0
├── src/main/java/fr/leuwen/keycloak/
│   ├── KeycloakInitializerApplication.java # Point d'entrée Spring Boot
│   ├── config/
│   │   └── KeycloakProperties.java         # @ConfigurationProperties (remplace ConfigLoader)
│   ├── runner/
│   │   └── KeycloakInitializerRunner.java  # CommandLineRunner (logique métier)
│   └── service/
│       ├── RealmService.java               # Gestion des realms
│       ├── ClientService.java              # Gestion des clients
│       ├── ClientRoleService.java          # Gestion des rôles
│       └── UserService.java                # Gestion des utilisateurs
└── src/main/resources/
    ├── application.yml                      # Configuration Keycloak
    ├── application.yml.example              # Exemple de configuration
    └── logback.xml                          # Configuration logs
```

## ⚙️ Configuration

### application.yml

```yaml
keycloak:
  server-url: http://localhost:8080
  admin:
    username: admin
    password: admin
    realm: master
  realm:
    name: LeuwenRealm
    display-name: "Leuwen Realm"
    enabled: true
    # ... autres propriétés
  client:
    client-id: RHDemo
    secret: lmax7TDMmHk5g7ZgCCXK9ILpjHHvHYga
    redirect-uris:
      - http://localhost:9000/*
    roles:
      - admin
      - consult
      - MAJ
  users:
    - username: admil
      password: Faf4zd89Fc
      email: admin@example.com
      roles: [admin, consult, MAJ]
    # ... autres utilisateurs
```

Voir `application.yml.example` pour la configuration complète.

## 🚀 Utilisation

### Build

```bash
mvn clean package
```

Cela produit `target/rhDemoInitKeycloak-1.0.0.jar`

### Exécution

```bash
# Avec application.yml dans resources/
java -jar target/rhDemoInitKeycloak-1.0.0.jar

# Avec fichier de configuration externe
java -jar target/rhDemoInitKeycloak-1.0.0.jar --spring.config.location=file:./my-config.yml

# Avec variables d'environnement
KEYCLOAK_ADMIN_PASSWORD=mypassword java -jar target/rhDemoInitKeycloak-1.0.0.jar
```

### Variables d'environnement

Spring Boot supporte les variables d'environnement automatiquement :

```bash
KEYCLOAK_SERVER_URL=http://keycloak:8080
KEYCLOAK_ADMIN_USERNAME=admin
KEYCLOAK_ADMIN_PASSWORD=secret
KEYCLOAK_REALM_NAME=MyRealm
KEYCLOAK_CLIENT_SECRET=xxx
```

## 📦 Dépendances principales

- **Spring Boot 3.2.0** : Framework principal
  - `spring-boot-starter` : Core Spring Boot
  - `spring-boot-configuration-processor` : Métadonnées pour IDE
- **Keycloak Admin Client 26.0.7** : API Keycloak
- **Resteasy Jackson2 Provider 6.2.4.Final** : Sérialisation JSON
- **Logback 1.5.16** : Logs (via Spring Boot)

## 🔧 Développement

### Logs

Le niveau de logs peut être ajusté dans `application.yml` :

```yaml
logging:
  level:
    root: INFO
    fr.leuwen.keycloak: DEBUG
    org.keycloak: DEBUG
```

### Validation de configuration

Spring Boot valide automatiquement la configuration au démarrage. Les erreurs sont clairement affichées.

### Tests

Le CommandLineRunner s'exécute après le démarrage de l'application. Pour des tests unitaires, désactiver le runner :

```yaml
spring:
  main:
    lazy-initialization: true  # Ne pas exécuter le runner automatiquement
```

## 🎯 Processus d'initialisation

1. **Connexion Keycloak** : Établissement de la connexion admin
2. **Création Realm** : Configuration du realm LeuwenRealm
3. **Création Client** : Configuration du client RHDemo avec protocol mappers
4. **Création Roles** : Création des client roles (admin, consult, MAJ)
5. **Création Users** : Création des utilisateurs avec assignation de rôles
6. **Récapitulatif** : Affichage des informations de configuration

## ✅ Avantages de la migration Spring Boot

1. **Simplicité** : Suppression de 120 lignes de code de parsing manuel
2. **Type-safety** : Validation automatique des types au démarrage
3. **Flexibilité** : Support multi-sources de configuration (YAML, properties, env vars, command-line)
4. **Documentation** : Métadonnées pour auto-complétion dans les IDEs
5. **Modernité** : Architecture standard Spring Boot, facilement maintenable
6. **Injection** : Dépendances gérées par Spring, pas de new manuel
7. **Validation** : Annotations `@Valid`, `@NotNull`, `@Min`, etc. disponibles

## 📚 Documentation

- [Spring Boot Configuration Properties](https://docs.spring.io/spring-boot/docs/3.2.0/reference/htmlsingle/#features.external-config.typesafe-configuration-properties)
- [Keycloak Admin Client](https://www.keycloak.org/docs/latest/server_development/#example-using-java)
- [Spring Boot Command Line Runner](https://docs.spring.io/spring-boot/docs/3.2.0/reference/htmlsingle/#features.spring-application.command-line-runner)
