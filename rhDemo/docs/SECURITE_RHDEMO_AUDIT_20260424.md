# Revue de sécurité — RHDemo — 2026-04-24

## Périmètre et modèle de menace

- **Mode d'analyse** : Complet (Full)
- **Modèle de menace** : Attaquant externe, compte Keycloak non privilégié (sans rôle `admin`, `MAJ` ou `consult` élevé) ou lecture du code source via PR
- **Fichiers analysés** :
  - `rhDemo/src/main/java/fr/leuwen/rhdemoAPI/` (18 fichiers Java)
  - `rhDemo/frontend/src/` (12 fichiers Vue.js / JS)
  - `rhDemo/src/main/resources/` (5 fichiers de configuration YAML + templates)
- **Exclusions justifiées** :
  - Accès direct à PostgreSQL : non exposé en dehors du réseau interne + NetworkPolicy
  - Administration Keycloak : port admin non exposé + hors modèle de menace
  - Accès SSH / filesystem serveur : isolation conteneur
  - Accès au noeud Kubernetes : RBAC ServiceAccount limité

---

## Résumé exécutif

| Sévérité | Nombre |
|---|---|
| Critique | 0 |
| Élevée | 1 |
| Moyenne | 3 |
| Faible | 3 |
| Informationnel | 2 |

---

## Findings

### F-01 — `management.endpoint.env.show-values: ALWAYS` dans tous les profils de production

- **Sévérité** : Élevée
- **Catégorie** : C2 — Divulgation d'information via Actuator env
- **Fichier(s)** :
  - `rhDemo/src/main/resources/application.yml:117`
  - `rhDemo/src/main/resources/application-ephemere.yml:66`
  - `rhDemo/src/main/resources/application-stagingkub.yml:77`
- **Description** : La propriété `management.endpoint.env.show-values` est positionnée à `ALWAYS` dans les trois fichiers de configuration, y compris les profils ephemere et stagingkub. Cette valeur expose en clair toutes les variables d'environnement accessibles par l'endpoint `/actuator/env`, notamment les valeurs résolues des propriétés Spring Boot (mot de passe base de données, secret client OAuth2, etc.), même si ces valeurs proviennent de fichiers de secrets chiffrés.
- **Scénario d'attaque** :
  1. Un attaquant obtient ou compromet un compte Keycloak avec le rôle `admin` (par exemple via force brute ou phishing).
  2. Il accède à `https://rhdemo-stagingkub.intra.leuwen-lc.fr/actuator/env`.
  3. Il lit en clair les valeurs de `rhdemo.datasource.password.pg` et `rhdemo.client.registration.keycloak.client.secret` telles que résolues à l'exécution.

  Scénario alternatif sans compte admin : si une autre vulnérabilité permet d'accéder à l'endpoint env (erreur de configuration, bug Spring, élévation de privilège Keycloak), toutes les secrets sont exposés.
- **Preuve** :
  ```yaml
  # application.yml:117 et application-ephemere.yml:66 et application-stagingkub.yml:77
  management:
    endpoint:
      env:
        show-values: ALWAYS  # Options: NEVER, WHEN_AUTHORIZED, ALWAYS
  ```
- **Pourquoi ce n'est pas un faux positif** :
  - L'endpoint `/actuator/env` est accessible aux rôles `admin` (via la règle `hasRole("admin")` dans SecurityConfig).
  - `ALWAYS` signifie que même les valeurs marquées comme sensibles par Spring (mots de passe, secrets) sont exposées en clair, contrairement à `WHEN_AUTHORIZED` qui masque les propriétés sensitives.
  - Cela constitue un risque réel si un compte admin est compromis : tous les secrets opérationnels sont lisibles en une seule requête HTTP.
  - `WHEN_AUTHORIZED` fournirait le même niveau d'accès aux admins légitimes tout en masquant les valeurs des propriétés classées "sensitive" par Spring.
- **Remédiation appliquée** :
  `ALWAYS` remplacé par `WHEN_AUTHORIZED` dans les trois fichiers de configuration (`application.yml:117`, `application-ephemere.yml:66`, `application-stagingkub.yml:77`). Les valeurs sensibles (mots de passe, secrets) sont désormais masquées même pour un admin authentifié, contrairement à `ALWAYS` qui les exposait en clair.

---

### F-02 — Absence d'allowlist sur le paramètre `sort` (énumération de champs JPA)

- **Sévérité** : Moyenne
- **Catégorie** : B1 / E1 — Injection via paramètre sort / Absence de validation
- **Fichier(s)** :
  - `rhDemo/src/main/java/fr/leuwen/rhdemoAPI/controller/EmployeController.java:88`
- **Description** : Le paramètre `sort` reçu depuis la requête HTTP est passé directement à `Sort.by(direction, sort)` sans validation préalable. Bien que Spring Data JPA ne génère pas de SQL dynamique vulnérable à une injection SQL classique (il paramètre les requêtes), un attaquant authentifié peut énumérer les noms de champs de l'entité `Employe` en injectant des valeurs arbitraires et en observant les différences de comportement (erreur 500 vs résultats).
- **Scénario d'attaque** :
  Un utilisateur avec le rôle `consult` envoie successivement :
  - `GET /api/employes/page?sort=id` → 200 OK
  - `GET /api/employes/page?sort=champInexistant` → 500 Internal Server Error (ou 400 si géré)

  En observant les réponses, il peut cartographier tous les noms de colonnes de la table `employes`, ce qui facilite d'éventuelles attaques futures.
- **Preuve** :
  ```java
  // EmployeController.java:86-89
  if (sort != null && !sort.isEmpty()) {
      Sort.Direction direction = "DESC".equalsIgnoreCase(order) ? Sort.Direction.DESC : Sort.Direction.ASC;
      pageable = PageRequest.of(page, size, Sort.by(direction, sort));
  }
  ```
- **Pourquoi ce n'est pas un faux positif** :
  - L'attaquant dispose du rôle `consult` (compte non privilégié valide dans le modèle de menace).
  - La validation se fait au niveau JPA (pas de SQL injection) mais pas au niveau applicatif : n'importe quelle chaîne de caractères est acceptée comme nom de colonne.
  - Cela constitue un information disclosure actif sur la structure du schéma de données.
- **Remédiation appliquée** :
  Constante `SORT_ALLOWED_FIELDS = Set.of("prenom", "nom", "mail", "adresse")` ajoutée dans `EmployeController`. Si le paramètre `sort` n'appartient pas à cet ensemble, une `ResponseStatusException(BAD_REQUEST)` est levée. Un handler dédié `@ExceptionHandler(ResponseStatusException.class)` a été ajouté dans `GlobalExceptionHandler` pour retourner un 400 formaté (le handler générique `Exception.class` existant aurait retourné 500). Tests : `testGetEmployesPage_WithInvalidSort_ShouldReturn400` ajouté dans `EmployeControllerIT`.

---

### F-03 — Pagination sans limite maximale sur `size`

- **Sévérité** : Moyenne
- **Catégorie** : E2 — Logique métier, absence de plafond sur la taille de page
- **Fichier(s)** :
  - `rhDemo/src/main/java/fr/leuwen/rhdemoAPI/controller/EmployeController.java:77`
- **Description** : Le paramètre `size` dans la pagination accepte n'importe quelle valeur entière positive sans limite maximale. Un utilisateur authentifié peut envoyer `?size=1000000` et déclencher une requête chargeant potentiellement l'intégralité de la table en mémoire, saturant la mémoire JVM et/ou le pool de connexions HikariCP.
- **Scénario d'attaque** :
  Un utilisateur avec le rôle `consult` envoie :
  ```
  GET /api/employes/page?size=1000000
  ```
  Spring Data crée un objet `Pageable` avec `size=1000000` et exécute `SELECT * FROM employes LIMIT 1000000`. Si la table contient 50 000 enregistrements, tous sont chargés en mémoire, créant un pic de consommation mémoire significatif. En envoyant cette requête en boucle, un seul utilisateur authentifié peut dégrader la disponibilité du service (DoS applicatif).
- **Preuve** :
  ```java
  // EmployeController.java:77 — aucun @Max ou validation de plafond
  @RequestParam(defaultValue = "20") int size,
  ```
- **Pourquoi ce n'est pas un faux positif** :
  - Le rôle `consult` est le rôle minimal valide dans le modèle de menace.
  - Il n'existe aucune contrainte `@Max`, aucun plafond hard-codé, aucune logique de clamping dans le service.
  - NetworkPolicy ne protège pas contre les requêtes HTTP légitimes.
- **Remédiation appliquée** :
  Clamping appliqué dans `EmployeController.getEmployesPage()` : `int effectiveSize = Math.min(size, PAGE_SIZE_MAX)` (constante `PAGE_SIZE_MAX = 200`). Toutes les constructions `PageRequest.of(page, size, ...)` utilisent désormais `effectiveSize`. L'approche `@Validated + @Max` a été écartée car `GlobalExceptionHandler` ne gérait pas `ConstraintViolationException` et aurait retourné 500. Tests : `testGetEmployesPage_WithOversizedPage_ShouldClampToMax` ajouté dans `EmployeControllerIT` (vérifie que `$.page.size` vaut 200 pour `size=1000000`).

---

### F-04 — `/api/userinfo` sans `@PreAuthorize` (rôle minimal non contrôlé)

- **Sévérité** : Faible
- **Catégorie** : A1/A2 — Endpoint sans `@PreAuthorize` explicite, rôle trop permissif
- **Fichier(s)** :
  - `rhDemo/src/main/java/fr/leuwen/rhdemoAPI/controller/AccueilController.java:14`
- **Description** : L'endpoint `GET /api/userinfo` retourne le nom d'utilisateur et la liste des rôles de l'utilisateur connecté. Il n'a pas d'annotation `@PreAuthorize` et n'est couvert que par la règle générique `anyRequest().authenticated()` dans SecurityConfig. Ainsi, tout utilisateur authentifié (même sans rôle `consult` ou `MAJ`) peut accéder à cet endpoint et lire ses propres informations de rôle.

  Ce n'est pas une élévation de privilège mais cela expose la liste des rôles du token à n'importe quel compte authentifié, y compris des comptes sans aucun rôle applicatif.
- **Scénario d'attaque** :
  Un attaquant avec un compte Keycloak valide mais sans rôle (`consult` ou `MAJ`) peut appeler `GET /api/userinfo` et confirmer l'existence du compte, son nom d'utilisateur, et la liste de ses rôles. Information limitée mais utile pour la reconnaissance.
- **Preuve** :
  ```java
  // AccueilController.java:14-21 — pas de @PreAuthorize
  @GetMapping("/api/userinfo")
  public Map<String, Object> getUserInfo(Authentication auth) {
      String username = auth.getName();
      List<String> roles = auth.getAuthorities().stream()
              .map(GrantedAuthority::getAuthority)
              .toList();
      return Map.of("username", username, "roles", roles);
  }
  ```
- **Pourquoi ce n'est pas un faux positif** :
  - L'attaquant dispose d'un compte Keycloak valide (modèle de menace inclut "compte non privilégié").
  - La règle `anyRequest().authenticated()` laisse passer tout utilisateur authentifié quelle que soit sa liste de rôles.
  - Ce point est faible car les données renvoyées concernent l'utilisateur lui-même (pas d'autres utilisateurs). La sévérité est donc faible.
- **Remédiation appliquée** :
  `@PreAuthorize("hasAnyRole('consult', 'MAJ', 'admin')")` ajouté sur `AccueilController.getUserInfo()`. Un utilisateur Keycloak authentifié sans rôle applicatif reçoit désormais 403. Test : `testUserInfo_WithNoApplicableRole_ShouldReturn403` ajouté dans `AccueilControllerIT`.

---

### F-05 — `/api/userinfo` retourne la liste complète des rôles internes

- **Sévérité** : Faible
- **Catégorie** : C3 — Divulgation d'information sur la structure interne
- **Fichier(s)** :
  - `rhDemo/src/main/java/fr/leuwen/rhdemoAPI/controller/AccueilController.java:17-19`
- **Description** : L'endpoint `/api/userinfo` retourne la liste brute des `GrantedAuthority` de l'utilisateur, incluant les noms de rôles internes Spring (`ROLE_consult`, `ROLE_MAJ`, `ROLE_admin`). Ces informations permettent à un attaquant de cartographier l'ensemble des rôles applicatifs définis dans le système, ce qui facilite les tentatives d'escalade de privilège ou d'ingénierie sociale.
- **Scénario d'attaque** :
  Un attaquant authentifié voit dans la réponse `{"roles": ["ROLE_consult"]}` et déduit l'existence d'autres rôles (`ROLE_MAJ`, `ROLE_admin`) par inférence sur le code ou par observation du comportement de l'interface.
- **Preuve** :
  ```java
  List<String> roles = auth.getAuthorities().stream()
          .map(GrantedAuthority::getAuthority)
          .toList();
  return Map.of("username", username, "roles", roles);
  ```
- **Pourquoi ce n'est pas un faux positif** :
  - Le frontend utilise cet endpoint pour adapter l'affichage des boutons (`hasRole('MAJ')`). Le retour des rôles est donc fonctionnel.
  - L'impact est limité : les noms de rôles sont déjà visibles via l'interface Keycloak pour l'administrateur. Pour un attaquant externe, cette information est de valeur modérée.
  - Sévérité faible car l'impact direct est limité.
- **Remédiation appliquée** :
  Le stream de `AccueilController.getUserInfo()` filtre désormais les autorités non préfixées `ROLE_` et supprime le préfixe avant de retourner les noms en minuscules (`consult`, `maj`, `admin`). La préfixation `ROLE_` interne à Spring n'est plus exposée côté client.

  Le frontend a été mis à jour en conséquence : `userStore.js` utilise `role.toLowerCase()` au lieu de `'ROLE_' + role` dans la fonction `hasRole()`, ce qui assure la cohérence avec le nouveau format.

  Les tests `AccueilControllerTest` et `AccueilControllerIT` ont été mis à jour pour valider le nouveau format (`"consult"` au lieu de `"ROLE_consult"`, `"maj"` au lieu de `"ROLE_MAJ"`).

---

### F-06 — `forward-headers-strategy: framework` sans validation des headers X-Forwarded-* côté Nginx

- **Sévérité** : Faible
- **Catégorie** : D3 — Configuration, confiance aveugle aux headers de proxy
- **Fichier(s)** :
  - `rhDemo/src/main/resources/application.yml:93`
  - `rhDemo/src/main/resources/application-ephemere.yml:40`
  - `rhDemo/src/main/resources/application-stagingkub.yml:47`
  - `rhDemo/src/main/java/fr/leuwen/rhdemoAPI/springconfig/KeycloakLogoutSuccessHandler.java:176-192`
- **Description** : La stratégie `forward-headers-strategy: framework` fait confiance aux headers `X-Forwarded-Proto`, `X-Forwarded-Host`, et `X-Forwarded-Port` pour construire les URLs utilisées dans les redirections OAuth2 et post-logout. Si Nginx ne filtre pas et ne réécrit pas ces headers avant de les transmettre au backend, un attaquant qui peut injecter ces headers (typiquement depuis le réseau interne, ou si Nginx expose directement les headers du client) pourrait forger des URLs de redirection.

  Le `KeycloakLogoutSuccessHandler` lit directement `request.getHeader("X-Forwarded-Proto")` sans passer par l'abstraction Spring `ForwardedHeaderFilter` qui normalise et valide ces valeurs.
- **Scénario d'attaque** :
  Un attaquant dans un contexte où il peut contrôler les headers HTTP (rare en production derrière Nginx, mais possible en dev ou si Nginx est mal configuré) injecte `X-Forwarded-Host: evil.com` dans une requête de logout. Le `KeycloakLogoutSuccessHandler` construit alors `post_logout_redirect_uri=http://evil.com/` et Keycloak redirige l'utilisateur vers ce domaine après le logout. Impact : phishing post-logout.
- **Preuve** :
  ```java
  // KeycloakLogoutSuccessHandler.java:178-192
  String forwardedProto = request.getHeader("X-Forwarded-Proto");
  String forwardedHost = request.getHeader("X-Forwarded-Host");
  String forwardedPort = request.getHeader("X-Forwarded-Port");

  if (forwardedProto != null && forwardedHost != null) {
      scheme = forwardedProto;
      host = forwardedHost;  // Valeur non validée
      port = forwardedPort != null ? Integer.parseInt(forwardedPort) : -1;
  }
  ```
- **Pourquoi ce n'est pas un faux positif** :
  - En production (ephemere, stagingkub), Nginx devrait théoriquement supprimer ou réécrire ces headers côté client. Cependant, la configuration Nginx n'a pas été analysée dans ce périmètre, et le risque subsiste si Nginx transmet les headers clients sans filtrage.
  - Même en supposant Nginx correctement configuré, le code applicatif lit les headers bruts sans passer par une couche de validation dédiée, ce qui est une mauvaise pratique défensive.
  - Sévérité faible car l'exploitation nécessite une configuration Nginx insuffisante.
- **Remédiation appliquée** :
  Trois corrections complémentaires ont été appliquées selon un principe de défense en profondeur.

  **1. Code Java — `KeycloakLogoutSuccessHandler.buildBaseUrl()`** :
  `ForwardedHeaderFilter` (activé par `forward-headers-strategy: framework`) retire les headers `X-Forwarded-*` du wrapper de requête avant d'appeler les handlers aval, et corrige automatiquement `request.getScheme()`, `request.getServerName()` et `request.getServerPort()` avec les valeurs du proxy. La lecture directe via `request.getHeader("X-Forwarded-*")` était donc du code mort qui devenait une vraie vulnérabilité si le filtre était modifié. La méthode a été simplifiée pour s'appuyer uniquement sur le wrapper :

  ```java
  String buildBaseUrl(HttpServletRequest request) {
      // ForwardedHeaderFilter a déjà résolu getScheme(), getServerName(), getServerPort()
      // avec les valeurs du proxy, et supprimé les headers X-Forwarded-* bruts.
      String scheme = request.getScheme();
      String host = request.getServerName();
      int port = request.getServerPort();
      // ...
  }
  ```

  Un test de sécurité vérifie que `getHeader("X-Forwarded-*")` n'est jamais appelé directement.

  **2. Nginx ephemere — suppression du header `Forwarded` RFC 7239** (`rhdemo.conf`, `keycloak.conf`, `localhost.conf`) :
  Nginx écrasait correctement `X-Forwarded-Host` et `X-Forwarded-Proto`, mais transmettait sans filtre le header `Forwarded` (RFC 7239) envoyé par le client. `ForwardedHeaderFilter` traite ce header en priorité sur `X-Forwarded-*` : un client pouvait injecter `Forwarded: host=evil.com; proto=https` pour forger l'URL de base malgré les overrides Nginx. Deux corrections ont été appliquées dans toutes les sections `location /` :

  ```nginx
  # Supprimer le header Forwarded RFC 7239 client (traité en priorité par Spring)
  proxy_set_header Forwarded "";
  # Seule l'IP vue par Nginx (pas les valeurs injectées par le client)
  proxy_set_header X-Forwarded-For $remote_addr;
  ```

  **3. NGF stagingkub — `RequestHeaderModifier` dans les HTTPRoutes** (`httproute.yaml`) :
  Même vecteur que pour Nginx ephemere. Un filtre Gateway API standard a été ajouté à toutes les HTTPRoutes pour supprimer le header `Forwarded` avant qu'il atteigne le backend. NGF continue d'injecter ses propres headers `X-Forwarded-*` à la couche Nginx, indépendamment de ce filtre applicatif :

  ```yaml
  filters:
  - type: RequestHeaderModifier
    requestHeaderModifier:
      remove:
      - Forwarded
  ```

  Compatibilité par environnement :
  - **Dev local** : non affecté (pas de proxy, `ForwardedHeaderFilter` ne traite aucun header X-Forwarded-*)
  - **Ephemere** : Nginx supprime `Forwarded` client, Spring ne voit que les headers contrôlés par Nginx ✓
  - **Stagingkub** : NGF supprime `Forwarded` client via HTTPRoute filter, Spring ne voit que les headers contrôlés par NGF ✓

---

### F-07 — `console.log` de debug laissé en production (frontend)

- **Sévérité** : Informationnel
- **Catégorie** : C3 — Divulgation d'information dans la console navigateur
- **Fichier(s)** :
  - `rhDemo/frontend/src/main.js:19`
  - `rhDemo/frontend/src/services/api.js:43-45`
- **Description** : Le fichier `main.js` contient un `console.log('[DEBUG] Vue.js application montée avec succès')` actif en production. Le fichier `api.js` contient un bloc de debug CSRF commenté (lignes 22-26) qui, s'il était décommenté, afficherait tous les cookies en console (`console.log('🔐 [CSRF] Tous les cookies:', document.cookie)`). Les `console.error` actifs (lignes 43-45) exposent la méthode HTTP, l'URL et le début du token CSRF en cas d'erreur 403.
- **Scénario d'attaque** :
  Un attaquant avec accès physique à la machine d'un utilisateur ou exploitant une autre vulnérabilité pour accéder aux logs navigateur peut voir les messages de debug. Risque très faible, mais constitue une mauvaise pratique.
- **Preuve** :
  ```javascript
  // main.js:19
  console.log('[DEBUG] Vue.js application montée avec succès');

  // api.js:43-45 (actif en production)
  console.error('❌ [CSRF] Erreur 403 - Token CSRF invalide ou expiré');
  console.error('❌ [CSRF] Requête:', error.config.method.toUpperCase(), error.config.url);
  console.error('❌ [CSRF] Header envoyé:', error.config.headers['X-XSRF-TOKEN']?.substring(0, 20) + '...');
  ```
- **Pourquoi ce n'est pas un faux positif** :
  - Ces logs sont effectivement envoyés à la console du navigateur en production. Informationnel car l'impact direct est très limité.
- **Remédiation appliquée** :
  `console.log('[DEBUG] Vue.js application montée avec succès')` supprimé de `main.js` (le flag programmatique `window.__VUE_APP_MOUNTED__ = true` utilisé par les tests Selenium est conservé). Dans `api.js`, les trois lignes `console.error` qui exposaient la méthode HTTP, l'URL et un fragment du token CSRF ont été remplacées par un message générique : `console.error('Erreur CSRF - veuillez recharger la page')`. Le bloc de debug CSRF commenté (lignes 22-26) était déjà inactif et n'a pas été modifié.

---

### F-08 — OpenAPI/Swagger accessible sans authentification en dev/ephemere

- **Sévérité** : Informationnel
- **Catégorie** : C4 — Divulgation d'information via documentation API
- **Fichier(s)** :
  - `rhDemo/src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java:178`
  - `rhDemo/src/main/resources/application-stagingkub.yml:59-63`
- **Description** : L'endpoint `/api-docs` est déclaré `permitAll()` dans SecurityConfig. La documentation Swagger UI complète est accessible sans authentification en environnement `dev` et `ephemere`. En `stagingkub`, SpringDoc est correctement désactivé via `springdoc.swagger-ui.enabled: false` et `springdoc.api-docs.enabled: false`.

  La documentation expose la liste complète des endpoints, leurs paramètres, les schémas de données (champs des DTO), et les codes de réponse.
- **Scénario d'attaque** :
  En environnement CI (ephemere), un observateur réseau ou un attaquant ayant accès au réseau `58443` peut consulter `https://rhdemo.ephemere.local:58443/api-docs/swagger-ui/index.html` sans compte Keycloak et obtenir une cartographie complète de l'API.
- **Pourquoi ce n'est pas un faux positif** :
  - En stagingkub (proche production), la documentation est désactivée — le risque est donc confiné à ephemere (environnement CI non exposé au réseau public).
  - En dev local, c'est intentionnel (usage développeur).
  - Informationnel car l'exposition de l'environnement ephemere au réseau public n'est pas dans le modèle de menace standard.
- **Remédiation appliquée** :
  `/api-docs` retiré de `permitAll()` dans `SecurityConfig` et `TestSecurityConfig`. Une règle explicite `.requestMatchers("/api-docs/**").hasRole("admin")` a été ajoutée pour couvrir l'ensemble des chemins SpringDoc (UI et OpenAPI JSON). La documentation reste accessible aux admins authentifiés en dev/ephemere et est désactivée en stagingkub via la configuration SpringDoc existante.

  `TestSecurityConfig` a été mis en conformité avec `SecurityConfig` sur ce point ainsi que sur l'exposition publique de `/actuator/health` et `/actuator/prometheus` (règles `permitAll()` manquantes qui existaient en production mais pas dans la config de test). Les tests `SecurityConfigIT` ont été ajustés en conséquence.

---

## Composants vérifiés et non vulnérables

| Check | Résultat |
|---|---|
| **A1** — Tous les endpoints REST ont `@PreAuthorize` ou règle SecurityConfig | PASS — `EmployeController` : toutes les méthodes ont `@PreAuthorize`. `AccueilController` : couvert par `anyRequest().authenticated()` (voir F-04 pour nuance). `FrontendController` : couvert par `hasAnyRole('consult','MAJ')` via rule `/front`. |
| **A2** — `@PreAuthorize` cohérent avec la sensibilité de l'opération | PASS — Lecture : `hasRole('consult')`. Écriture/MAJ/suppression : `hasRole('MAJ')`. Actuator admin : `hasRole('admin')`. |
| **A3** — `redirect_uri` OIDC sans wildcard | PASS — `redirect-uri: "{baseUrl}/login/oauth2/code/{registrationId}"` dans tous les profils, pas de wildcard. |
| **A4** — CSRF — exclusions justifiées | PASS — Seuls `/error*`, `/api-docs` et `/actuator/**` sont exclus. Les endpoints `/actuator/**` mutants (shutdown, loggers) nécessiteraient une attention, mais leur accès est limité à `hasRole('admin')` et le risque de CSRF sur admin est faible dans le modèle de menace. |
| **A5** — Flags cookies (JSESSIONID)** | PASS en prod — `secure: true`, `http-only: true`, `same-site: lax` dans les profils ephemere et stagingkub. En dev local, `secure: false` est acceptable (HTTP). Cookie CSRF (`XSRF-TOKEN`) : correctement configuré `HttpOnly=false` (requis pour SPA), `SameSite=Strict`, `Secure` selon le profil. |
| **B2** — XSS Vue.js (`v-html`, `innerHTML`) | PASS — Aucun usage de `v-html` ou `.innerHTML` dans les 7 composants Vue.js. Toutes les données sont interpolées via `{{ }}` (auto-échappées par Vue). |
| **B3** — EL/SpEL Injection | PASS — Les `@Value` utilisés ne contiennent pas de données utilisateur ; ils référencent uniquement des propriétés de configuration statiques. |
| **B4** — Open redirect via paramètre utilisateur | PASS — Aucun endpoint ne construit une URL de redirection à partir d'un paramètre HTTP contrôlable par l'utilisateur. Le `KeycloakLogoutSuccessHandler` utilise l'`authorization-uri` de configuration, pas un paramètre de requête. (Voir F-06 pour le risque lié aux headers X-Forwarded.) |
| **C1** — Actuator Prometheus sans authentification | Accepté par conception — `/actuator/prometheus` est `permitAll()` mais protégé par NetworkPolicy en Kubernetes (seul Prometheus interne peut atteindre le pod). En dev local, cela expose les métriques au réseau local uniquement. |
| **C5** — IDOR / Enumération d'IDs | Accepté par conception — Les IDs sont séquentiels et tous les employés sont partagés (pas de notion de propriété par utilisateur). Le rôle `consult` peut lire tous les employés — c'est le comportement attendu d'une application RH CRUD. |
| **D1** — CORS | PASS — Pas de `@CrossOrigin` dans les contrôleurs. Pas de configuration CORS permissive dans `WebMvcConfig`. L'application fonctionne en mode same-origin (frontend servi par le même backend). |
| **D2** — Headers de sécurité / CSP | PASS — CSP stricte sans `unsafe-inline` ni `unsafe-eval`. Scripts et styles externalisés. `frame-ancestors 'none'`. `object-src 'none'`. `base-uri 'self'`. |
| **E3** — IDOR entre utilisateurs | PASS / Accepté — Les données employés sont partagées par design dans ce contexte RH. Pas de notion de propriété par utilisateur à protéger. |

---

## Conclusion

L'application RHDemo présente un niveau de sécurité globalement satisfaisant pour un PoC académique à visée DevSecOps. Les couches de protection fondamentales sont correctement mises en place : CSRF avec cookie SameSite Strict, CSP stricte sans `unsafe-inline`, RBAC Keycloak cohérent avec les opérations exposées, isolation réseau Kubernetes Zero Trust, et absence de patterns dangereux comme `v-html` ou SQL dynamique.

**Ensemble des findings remédiés** (2026-04-27). Les corrections appliquées couvrent les 8 findings (F-01 à F-08, F-06 inclus) :

- **F-01 (Élevée)** : `show-values: WHEN_AUTHORIZED` dans les 3 profils — secrets masqués à l'endpoint `/actuator/env`.
- **F-02 (Moyenne)** : Allowlist sur le paramètre `sort` — énumération de colonnes JPA impossible, 400 retourné pour valeur invalide.
- **F-03 (Moyenne)** : Clamping de `size` à 200 — le DoS par pagination massive est neutralisé.
- **F-04 (Faible)** : `@PreAuthorize` sur `/api/userinfo` — un compte Keycloak sans rôle applicatif reçoit 403.
- **F-05 (Faible)** : Rôles retournés sans préfixe `ROLE_` et en minuscules — la nomenclature interne Spring n'est plus exposée. Frontend mis à jour en conséquence.
- **F-06 (Faible)** : Headers `Forwarded` RFC 7239 supprimés par Nginx (ephemere) et NGF (stagingkub) ; `buildBaseUrl()` s'appuie uniquement sur le wrapper `ForwardedHeaderFilter`.
- **F-07 (Informationnel)** : `console.log` de debug et fragments de token CSRF supprimés de la console navigateur.
- **F-08 (Informationnel)** : Swagger/OpenAPI restreint au rôle `admin` dans tous les environnements ; `TestSecurityConfig` aligné sur `SecurityConfig`.
