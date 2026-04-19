# Analyse d'impact : Migration vers la Clean Architecture

## État des lieux — ce que l'architecture actuelle fait déjà bien

Avant de lister les changements, il faut reconnaître que l'architecture en couches actuelle est **déjà bien structurée** :

| Point positif | Détail |
|---|---|
| DTOs complets | `EmployeRequestDTO` / `EmployeResponseDTO` — aucune entité JPA exposée en REST |
| Injection constructeur | Pas de `@Autowired` sur les champs — testabilité correcte |
| Validation aux frontières | Bean Validation dans les DTOs, pas dans les entités |
| Exception centralisée | `GlobalExceptionHandler` — pas de gestion d'erreur dispersée |
| Séparation des rôles | Controller → Service → Repository respectée |

**La distance réelle vers la Clean Architecture est donc modérée**, pas un abîme.

---

## Ce que la Clean Architecture exigerait de changer

### 1. Inversion de dépendance sur le Repository — Impact : FORT

C'est le changement le plus structurant.

**Actuellement** :
```
EmployeService → EmployeRepository (interface Spring Data JPA)
```
`EmployeService` (couche domaine) dépend directement d'une abstraction d'infrastructure (Spring Data). C'est une violation de la règle de dépendance.

**Après migration** :
```
domain/port/EmployeRepositoryPort  ← interface pure Java (domaine)
        ↑ implémentée par
infrastructure/persistence/EmployeRepositoryAdapter  → EmployeJpaRepository (Spring Data)
```

Fichiers créés : `EmployeRepositoryPort.java`, `EmployeRepositoryAdapter.java`, `EmployeJpaRepository.java`

---

### 2. Séparation entité domaine / entité JPA — Impact : FORT

**Actuellement**, `Employe.java` est les deux à la fois : entité métier ET mapping JPA (`@Entity`, `@Table`, `@Column`).

**Après migration** :
- `domain/entity/Employe.java` — POJO pur, aucune dépendance framework
- `infrastructure/persistence/EmployeJpaEntity.java` — avec `@Entity`, `@Table`, etc.
- `infrastructure/persistence/EmployeMapper.java` — conversion entre les deux

C'est du code doublé pour un objet qui a 4 champs (`prenom`, `nom`, `mail`, `adresse`). Le gain concret sur ce projet est faible.

---

### 3. Service → Use Cases — Impact : MOYEN

**Actuellement** : `EmployeService` avec 6 méthodes (getById, getAll, getPage, create, update, delete).

**Après migration** : 6 classes distinctes, une par cas d'utilisation :

```
application/usecase/
├── GetEmployeUseCase.java
├── ListEmployesUseCase.java
├── SearchEmployesUseCase.java
├── CreateEmployeUseCase.java
├── UpdateEmployeUseCase.java
└── DeleteEmployeUseCase.java
```

Chaque use case a une interface d'entrée (`InputPort`) et de sortie (`OutputPort`). La logique métier de `EmployeService` ne change pas — elle se **redistribue** dans ces classes.

---

### 4. Réorganisation complète des packages — Impact : MOYEN

**Structure actuelle** (par type technique) :
```
fr.leuwen.rhdemoAPI/
├── controller/
├── service/
├── repository/
├── model/
├── dto/
├── exception/
└── springconfig/
```

**Structure Clean Architecture** (par couche d'appartenance) :
```
fr.leuwen.rhdemoAPI/
├── domain/
│   ├── entity/Employe.java
│   ├── exception/EmployeNotFoundException.java
│   └── port/EmployeRepositoryPort.java
├── application/
│   └── usecase/
│       ├── CreateEmployeUseCase.java
│       └── ...
└── infrastructure/
    ├── persistence/
    │   ├── EmployeJpaEntity.java
    │   ├── EmployeJpaRepository.java
    │   ├── EmployeRepositoryAdapter.java
    │   ├── EmployeSpecificationJpa.java
    │   └── EmployeMapper.java
    ├── web/
    │   ├── EmployeController.java
    │   ├── dto/EmployeRequestDTO.java
    │   ├── dto/EmployeResponseDTO.java
    │   └── GlobalExceptionHandler.java
    └── security/
        ├── SecurityConfig.java
        ├── GrantedAuthoritiesKeyCloakMapper.java
        └── KeycloakLogoutSuccessHandler.java
```

---

### 5. Ce qui ne change quasiment pas

| Composant | Impact | Pourquoi |
|---|---|---|
| `EmployeController` | Faible | Adapte juste les appels vers les use cases au lieu du service |
| `EmployeRequestDTO` / `EmployeResponseDTO` | Faible | Déplacés en `infrastructure/web/dto/`, contenu inchangé |
| `GlobalExceptionHandler` | Faible | Déplacé en `infrastructure/web/` |
| `SecurityConfig` | Nul | Déjà pur infrastructure, aucun lien avec le domaine |
| `GrantedAuthoritiesKeyCloakMapper` | Nul | Idem |
| `EmployeSpecification` | Faible | Déplacé en `infrastructure/persistence/` |

---

## Tableau de synthèse — effort par composant

| Composant | Effort | Nature du changement |
|---|---|---|
| `Employe.java` | Fort | Scindé en 2 (domaine + JPA) + mapper |
| `EmployeRepository.java` | Fort | Interface port + adapter + Spring Data séparés |
| `EmployeService.java` | Moyen | Redistribué en 6 use cases |
| Package structure | Moyen | Réorganisation complète (git history impactée) |
| `EmployeController.java` | Faible | Injection des use cases au lieu du service |
| DTOs | Faible | Déplacement de package |
| Exception handling | Faible | Déplacement de package |
| Security config | Nul | Aucun changement |

---

## Impact sur les tests (contrainte SonarQube ≥ 50%)

Tout nouveau code doit être couvert à ≥ 50%. La migration génère :
- 6 use cases → 6 nouvelles classes de tests unitaires
- 1 `EmployeRepositoryAdapter` → tests d'intégration ou mock
- 1-2 mappers → tests unitaires simples

**Remarque** : la testabilité unitaire n'est pas un avantage propre à la Clean Architecture. Dans l'architecture en couches actuelle, `EmployeRepository` (Spring Data) peut déjà être mocké avec Mockito (`@Mock` + `@ExtendWith(MockitoExtension.class)`) sans charger de contexte Spring. Le code de test est identique dans les deux cas — seul le nom de l'interface mockée change.

---

## Verdict

**La migration est faisable et pédagogiquement pertinente**, mais coûteuse pour la valeur ajoutée sur un CRUD à une seule entité.

**Recommandation** : si l'objectif est la démonstration des principes, migrer **en priorité** :
1. L'inversion de dépendance sur le repository (le cœur du principe)
2. La séparation entité domaine / JPA entity

Et laisser les use cases granulaires en option — le `EmployeService` actuel avec des méthodes dédiées est une approximation acceptable si on ne cherche pas l'orthodoxie complète.

Le ratio effort/bénéfice devient intéressant si l'application grossit (plusieurs entités, règles métier complexes). Sur un CRUD simple, il est discutable.
