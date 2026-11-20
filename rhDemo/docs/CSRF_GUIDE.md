---
statut: actif
verifie_le: 2026-10-22
sources:
  - rhDemo/src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java
  - rhDemo/frontend/src/services/api.js
---

# 🔒 Guide CSRF - Application RHDemo (Spring Boot + Vue.js)

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Solution implémentée](#solution-implémentée)
3. [Fonctionnement technique](#fonctionnement-technique)
4. [Vérifications et tests](#vérifications-et-tests)
5. [Résolution de problèmes](#résolution-de-problèmes)
6. [Références](#références)

---

## Vue d'ensemble

### Problème initial

```
403 Forbidden - Invalid CSRF token found for http://localhost:9000/api/employe
```

Les requêtes DELETE (et autres mutations) étaient systématiquement rejetées malgré la présence du cookie XSRF-TOKEN.

### Solution finale

Implémentation d'un **`SpaCsrfTokenRequestHandler`** personnalisé qui :
- Force la génération du token CSRF sur **toutes les requêtes** (y compris GET)
- Utilise une validation de token **simple (non XOR-encodé)**
- Compatible avec les applications SPA (Single Page Application)

---

## Solution implémentée

### 1. Configuration Spring Security

**Fichier :** `src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java`

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {
    
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http, LogoutSuccessHandler logoutSuccessHandler) throws Exception {
        http 
        // Active la protection CSRF avec cookie accessible en JavaScript
        .csrf(csrf -> csrf
            .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
            .csrfTokenRequestHandler(new SpaCsrfTokenRequestHandler())
            // Ignorer CSRF pour les endpoints publics et actuator
            .ignoringRequestMatchers("/who", "/error*", "/api-docs", "/actuator/**")
        )
        // ... reste de la configuration
        ;
        return http.build();
    }
}

/**
 * Gestionnaire de requêtes CSRF personnalisé pour les applications SPA.
 * Ce gestionnaire garantit que le token CSRF est toujours chargé et envoyé dans le cookie,
 * ce qui est essentiel pour les SPA qui lisent le token depuis le cookie XSRF-TOKEN.
 * 
 * Comportements clés :
 * 1. Force la création du token sur TOUTES les requêtes (y compris GET) en appelant csrfToken.get()
 * 2. Utilise une validation de token simple (NON encodé en XOR) compatible avec CookieCsrfTokenRepository
 * 3. Rend le token disponible en tant qu'attribut de requête pour le rendu
 */
final class SpaCsrfTokenRequestHandler implements CsrfTokenRequestHandler {
    private final CsrfTokenRequestAttributeHandler delegate = new CsrfTokenRequestAttributeHandler();

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, Supplier<CsrfToken> csrfToken) {
        // CRITIQUE : Force la génération du token en appelant get() explicitement
        // Cela garantit que CookieCsrfTokenRepository crée et envoie le cookie XSRF-TOKEN sur TOUTES les requêtes
        CsrfToken token = csrfToken.get();
        
        // Puis délègue au gestionnaire standard pour rendre le token disponible en tant qu'attribut de requête
        this.delegate.handle(request, response, () -> token);
    }

    @Override
    public String resolveCsrfTokenValue(HttpServletRequest request, CsrfToken csrfToken) {
        // Le client envoie le token depuis le cookie XSRF-TOKEN dans l'en-tête X-XSRF-TOKEN
        // Utilise la résolution standard (comparaison de token simple, pas de décodage XOR)
        return this.delegate.resolveCsrfTokenValue(request, csrfToken);
    }
}
```

### 2. Configuration frontend Axios

**Fichier :** `frontend/src/services/api.js`

```javascript
// Fonction pour extraire le token CSRF depuis les cookies
function getCsrfToken() {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; XSRF-TOKEN=`);
  if (parts.length === 2) {
    return parts.pop().split(';').shift();
  }
  return null;
}

// Intercepteur pour ajouter le token CSRF aux requêtes
api.interceptors.request.use(
  config => {
    // Pour les requêtes qui modifient les données (POST, PUT, DELETE, PATCH)
    if (['post', 'put', 'delete', 'patch'].includes(config.method.toLowerCase())) {
      const csrfToken = getCsrfToken();
      if (csrfToken) {
        config.headers['X-XSRF-TOKEN'] = csrfToken;
      }
    }
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);
```

---

## Fonctionnement technique

### 1. Cycle de vie du token CSRF

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Utilisateur s'authentifie via Keycloak                      │
│    → Session JSESSIONID créée                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Première requête GET (ex: /api/employes)                    │
│    → SpaCsrfTokenRequestHandler force csrfToken.get()          │
│    → CookieCsrfTokenRepository génère UUID                     │
│    → Cookie XSRF-TOKEN envoyé au navigateur                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. JavaScript lit le cookie XSRF-TOKEN                         │
│    → document.cookie accessible (HttpOnly=false)                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Requête DELETE /api/employe                                  │
│    → Intercepteur Axios lit cookie XSRF-TOKEN                  │
│    → Ajoute header X-XSRF-TOKEN                                │
│    → Navigateur envoie aussi cookie XSRF-TOKEN                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Spring Security valide                                       │
│    → Compare cookie XSRF-TOKEN avec header X-XSRF-TOKEN        │
│    → Si identiques → ✅ Requête acceptée                        │
│    → Si différents → ❌ 403 Forbidden                           │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Pourquoi forcer `csrfToken.get()` ?

**Sans l'appel explicite** (comportement par défaut de Spring Security) :

- ❌ **GET requests** : Token CSRF **non généré** automatiquement
- ❌ Cookie XSRF-TOKEN **absent** lors de la première requête
- ❌ Les mutations suivantes échouent avec **403 Forbidden**

**Avec l'appel explicite** :

- ✅ **Toutes les requêtes** : Token CSRF généré systématiquement
- ✅ Cookie XSRF-TOKEN disponible **immédiatement**
- ✅ Les mutations fonctionnent dès la première tentative

### 3. Pourquoi pas d'encodage XOR ?

**Spring Security 6+ utilise XOR encoding par défaut** pour les applications traditionnelles (server-side rendering), mais :

- `CookieCsrfTokenRepository` génère des **UUID simples** (36 caractères)
- L'encodage XOR attend des tokens de **192 bytes** (encodés en Base64)
- Pour les SPA, la validation simple suffit grâce à la **Same-Origin Policy**

**Notre solution** : `CsrfTokenRequestAttributeHandler` (validation simple) au lieu de `XorCsrfTokenRequestAttributeHandler`.

### 4. Structure des cookies

| Cookie | Valeur | HttpOnly | SameSite | Secure | Rôle |
|--------|--------|----------|----------|--------|------|
| **JSESSIONID** | `475C00334D...` | ✅ true | Lax | true | Session authentifiée |
| **XSRF-TOKEN** | `a1b2c3d4-e5f6-...` | ❌ false | Strict | true | Token CSRF |

**⚠️ Important** : `XSRF-TOKEN` doit avoir `HttpOnly=false` pour être lisible par JavaScript.

---

## Vérifications et tests

### 1. Vérifier que l'application démarre

```bash
cd /home/leno-vo/git/repository/rhdemo
./mvnw spring-boot:run
```

Attendez le message :
```
Started RhdemoApplication in X.XXX seconds
```

### 2. Vérifier les cookies dans le navigateur

1. Ouvrir http://localhost:9000
2. S'authentifier via Keycloak
3. Ouvrir DevTools (`F12`) → **Application** → **Cookies** → `http://localhost:9000`

**Vous devez voir :**

```
JSESSIONID    | 475C00334D... | HttpOnly ✓ | SameSite: Lax
XSRF-TOKEN    | a1b2c3d4-... | HttpOnly ✗ | SameSite: Strict
```

### 3. Vérifier la lisibilité JavaScript

Dans la **Console** des DevTools :

```javascript
console.log(document.cookie);
// Résultat attendu : "XSRF-TOKEN=a1b2c3d4-e5f6-...; autres cookies"
```

**⚠️ JSESSIONID n'apparaît pas** (HttpOnly=true) → c'est normal et sécurisé ✅

### 4. Test d'une suppression d'employé

1. **Ouvrir DevTools → Network**
2. Activer "Preserve log"
3. Aller sur "Supprimer un employé"
4. Rechercher un employé
5. Cliquer sur "Supprimer"
6. Observer la requête **DELETE /api/employe**

**Headers de la requête (Request Headers) :**

```http
DELETE /api/employe?id=5 HTTP/1.1
Host: localhost:9000
Cookie: JSESSIONID=475C00334D...; XSRF-TOKEN=a1b2c3d4-e5f6-...
X-XSRF-TOKEN: a1b2c3d4-e5f6-7890-abcd-1234567890ab  ← Ajouté par Axios
```

**Réponse attendue :**

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

### 5. Vérifier les logs Spring Boot

Dans le terminal où l'application tourne :

#### ✅ Succès :

```log
DEBUG ... o.s.security.web.FilterChainProxy : Securing DELETE /api/employe
DEBUG ... o.s.security.web.csrf.CsrfFilter : Validated CSRF token
DEBUG ... f.l.r.controller.EmployeController : deleteEmploye appelée avec id=5
```

#### ❌ Échec :

```log
DEBUG ... o.s.security.web.csrf.CsrfFilter : Invalid CSRF token found
DEBUG ... o.s.s.w.access.AccessDeniedHandlerImpl : Responding with 403 status code
```

### 6. Test de protection CSRF (simulation d'attaque)

Créer un fichier HTML externe :

```html
<!-- attaquant.html -->
<!DOCTYPE html>
<html>
<body>
  <h1>Tentative d'attaque CSRF</h1>
  <form action="http://localhost:9000/api/employe" method="POST">
    <input name="prenom" value="Pirate">
    <input name="nom" value="Malveillant">
    <button>Envoyer</button>
  </form>
</body>
</html>
```

**Ouvrir ce fichier dans un navigateur et cliquer sur "Envoyer".**

**Résultat attendu :**
- ❌ **403 Forbidden**
- Le cookie `JSESSIONID` est envoyé (automatique)
- Le header `X-XSRF-TOKEN` est **ABSENT** (protection réussie ✅)

---

## Résolution de problèmes

### Problème 1 : Cookie XSRF-TOKEN n'apparaît jamais

**Diagnostic :**

```javascript
// Console du navigateur
console.log(document.cookie);
// Si XSRF-TOKEN absent → problème
```

**Solutions :**

1. **Vérifier la configuration Spring**
   ```java
   // Dans SecurityConfig.java
   .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
   // ⚠️ withHttpOnlyFalse() est OBLIGATOIRE
   ```

2. **Forcer une requête GET d'abord**
   - Aller sur "Liste des employés"
   - Le token devrait être créé
   - Vérifier à nouveau les cookies

3. **Vérifier SpaCsrfTokenRequestHandler**
   ```java
   .csrfTokenRequestHandler(new SpaCsrfTokenRequestHandler())
   ```

### Problème 2 : Header X-XSRF-TOKEN non envoyé

**Diagnostic :**

Ouvrir DevTools → Network → Cliquer sur la requête DELETE → **Headers**

Si `X-XSRF-TOKEN` est absent :

**Solutions :**

1. **Vérifier l'intercepteur Axios dans api.js**
   ```javascript
   api.interceptors.request.use(config => {
     if (['post', 'put', 'delete', 'patch'].includes(config.method.toLowerCase())) {
       const csrfToken = getCsrfToken();
       if (csrfToken) {
         config.headers['X-XSRF-TOKEN'] = csrfToken;
       }
     }
     return config;
   });
   ```

2. **Test manuel dans la Console**
   ```javascript
   function getCsrfToken() {
     const value = `; ${document.cookie}`;
     const parts = value.split(`; XSRF-TOKEN=`);
     if (parts.length === 2) {
       return parts.pop().split(';').shift();
     }
     return null;
   }
   console.log('Token:', getCsrfToken());
   ```

### Problème 3 : 403 Forbidden malgré header présent

**Diagnostic :**

Header `X-XSRF-TOKEN` présent mais requête rejetée.

**Solutions :**

1. **Comparer les valeurs**
   ```javascript
   // Console
   const token = getCsrfToken();
   console.log('Cookie:', token);
   // Puis comparer avec la valeur dans DevTools → Network → Headers → X-XSRF-TOKEN
   ```

2. **Vérifier la validation dans SecurityConfig**
   ```java
   // SpaCsrfTokenRequestHandler doit utiliser CsrfTokenRequestAttributeHandler
   // PAS XorCsrfTokenRequestAttributeHandler
   private final CsrfTokenRequestAttributeHandler delegate = new CsrfTokenRequestAttributeHandler();
   ```

3. **Activer les logs TRACE**
   ```properties
   # application.properties
   logging.level.org.springframework.security.web.csrf=TRACE
   ```

### Problème 4 : Tests Selenium échouent

**Diagnostic :**

```
403 Forbidden lors de l'ajout/suppression d'employé dans les tests
```

**Solutions :**

1. **Vérifier l'authentification Keycloak**
   - S'assurer que `authenticateKeycloak()` s'exécute avant les tests
   - La session doit être établie pour créer le token CSRF

2. **Augmenter les timeouts**
   ```java
   // TestConfig.java
   public static final int AUTH_TIMEOUT = 30; // Augmenter si nécessaire
   ```

3. **Mode debug (sans headless)**
   ```java
   // TestConfig.java
   public static final boolean HEADLESS_MODE = false;
   ```
   Puis relancer les tests pour observer le navigateur.

### Problème 5 : Token expiré après un certain temps

**Cause :** Le token CSRF est lié à la session. Si la session expire, le token n'est plus valide.

**Solutions :**

1. **Se reconnecter**
   - Logout puis login
   - Un nouveau token sera généré

2. **Augmenter la durée de session**
   ```properties
   # application.properties
   server.servlet.session.timeout=30m
   ```

---

## Références

### Documentation Spring Security

- [CSRF Protection](https://docs.spring.io/spring-security/reference/servlet/exploits/csrf.html)
- [CSRF for Single Page Applications](https://docs.spring.io/spring-security/reference/servlet/exploits/csrf.html#csrf-integration-javascript-spa)
- [Spring Security 6 Migration Guide](https://docs.spring.io/spring-security/reference/6.0/migration/servlet/exploits.html#_i_am_using_a_single_page_application_with_cookiecsrftokenrepository_and_it_doesn_t_work)
- [CookieCsrfTokenRepository API](https://docs.spring.io/spring-security/site/docs/current/api/org/springframework/security/web/csrf/CookieCsrfTokenRepository.html)

### Standards de sécurité

- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP SameSite Cookie Attribute](https://owasp.org/www-community/SameSite)

### Documentation Axios

- [Axios Request Interceptors](https://axios-http.com/docs/interceptors)

---

## Checklist finale

Cochez au fur et à mesure :

- [ ] Application démarre sans erreur
- [ ] Authentification Keycloak réussie
- [ ] Cookie JSESSIONID présent avec HttpOnly=true
- [ ] Cookie XSRF-TOKEN présent avec HttpOnly=false
- [ ] `document.cookie` montre XSRF-TOKEN (pas JSESSIONID)
- [ ] Network Inspector montre header `X-XSRF-TOKEN` sur DELETE
- [ ] Valeur du cookie XSRF-TOKEN = valeur du header X-XSRF-TOKEN
- [ ] Logs Spring montrent "Validated CSRF token" (pas "Invalid")
- [ ] DELETE `/api/employe` retourne 200 OK
- [ ] Tests Selenium passent

**Si toutes les cases sont cochées :** ✅ CSRF fonctionne parfaitement !

---

## Résumé de la solution

| Aspect | Configuration |
|--------|---------------|
| **Token Repository** | `CookieCsrfTokenRepository.withHttpOnlyFalse()` |
| **Request Handler** | `SpaCsrfTokenRequestHandler` (custom) |
| **Validation** | `CsrfTokenRequestAttributeHandler` (simple, pas XOR) |
| **Cookie** | XSRF-TOKEN (HttpOnly=false, SameSite=Strict) |
| **Header** | X-XSRF-TOKEN (ajouté par intercepteur Axios) |
| **Endpoints exclus** | `/who`, `/error*`, `/api-docs`, `/actuator/**` |
| **Modifications frontend** | 1 fichier (api.js) - intercepteur Axios |
| **Modifications composants Vue** | 0 (automatique via intercepteur) |
| **Impact tests Selenium** | 0 (fonctionne automatiquement) |

---

**Date de création :** 31 octobre 2025  
**Version :** 2.0  
**Projet :** RHDemo (Spring Boot 3.5.5 + Vue.js 3)  
**Statut :** ✅ Solution finale implémentée et validée
