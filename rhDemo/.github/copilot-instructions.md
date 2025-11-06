# RHDemo - Spring Boot + Vue.js Fullstack Application

## Architecture Overview

This is a secure HR employee management system with a **Spring Boot 3.5.5 + Java 21** backend and **Vue.js 3** frontend, integrated via Maven build process.

### Key Components

- **Backend**: Spring Boot REST API (`src/main/java/fr/leuwen/rhdemoAPI/`)
- **Frontend**: Vue.js SPA (`frontend/src/`)  
- **Security**: Keycloak OAuth2/OIDC integration with role-based access
- **Data**: PostgreSQL (prod) / H2 (test) with JPA entities
- **Build**: Maven with frontend-maven-plugin for integrated builds

## Authentication & Authorization

**Critical**: All API endpoints require Keycloak authentication with specific role checks:
- `@PreAuthorize("hasRole('consult')")` - Read operations
- `@PreAuthorize("hasRole('MAJ')")` - Write/delete operations

**Security Config Pattern** (`SecurityConfig.java`):
- Custom `GrantedAuthoritiesKeyCloakMapper` extracts roles from JWT `resource_access.RHDemo.roles`
- OAuth2 login with OIDC logout handling
- Actuator endpoints restricted to `admin` role

**Environment Variables Required**:
- `RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET`
- `RHDEMO_DATASOURCE_PASSWORD_PG` / `RHDEMO_DATASOURCE_PASSWORD_H2`

## Development Workflows

### Backend Development
```bash
# Run Spring Boot (port 9000)
./mvnw spring-boot:run

# Run tests with H2
./mvnw test

# Build with frontend integration
./mvnw clean package
```

### Frontend Development  
```bash
# Standalone Vue development (in frontend/)
npm run serve

# Production build (integrated via Maven)
./mvnw package  # Builds Vue → copies to /static
```

**Important**: Maven automatically installs Node.js v20.10.0 and builds Vue.js during `package` phase.

## Code Patterns

### API Layer Pattern
- Controllers in `controller/` with `@RestController` + security annotations
- Services in `service/` with `@Service` + business logic  
- Repositories extending `CrudRepository<Entity,Long>`
- All REST endpoints prefixed `/api/`

### Frontend Integration
- Vue components communicate via `services/api.js` (Axios)
- API base URL: `/api` (proxied through Spring Boot)
- Router configured in `router/index.js` with path-based routing

### Entity Pattern
```java
@Entity
@Table(name="employes")
public class Employe {
    @Id @GeneratedValue(strategy=GenerationType.IDENTITY)
    private Long id;
    // Use @Column(name="mdp") for database column mapping
}
```

## Monitoring & Documentation

- **Swagger UI**: `/api-docs/swagger-ui/index.html`
- **OpenAPI**: `/api-docs/docs`
- **Actuator**: `/actuator` (admin role required)
- **Prometheus**: `/actuator/prometheus` (micrometer integration)

## Database Configuration

**Dual Database Setup**:
- Production: PostgreSQL (`pgddl.sql` for schema)
- Testing: H2 in-memory (`data.sql` for test data)
- JPA setting: `spring.jpa.hibernate.ddl-auto=validate` (no auto-schema generation)

**Testing Configuration**: Uses `application-test.properties` with H2 database for isolated testing.