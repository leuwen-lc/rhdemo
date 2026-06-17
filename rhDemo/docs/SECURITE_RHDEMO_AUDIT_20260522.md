# 🔐 Rapport d'Audit de Sécurité — RHDemo

Rapport généré par Claude Code avec les instructions trouvées sur ce projet
https://github.com/Netxeo/skill-file-security/tree/main/instructions

**Date :** 2026-05-22  
**Score :** 58/100 🟠  
**Projet :** RHDemo — Application web full-stack Spring Boot 4 / Vue.js 3 / Keycloak 26  
**Stack :** Java 25 · Spring Boot 4.0.2 · Vue.js 3 · Keycloak 26 · PostgreSQL 18 · Nginx · Docker Compose · Kubernetes KinD  
**Modèle de menace :** Attaquant externe avec compte non privilégié (ROLE_consult) ou accès en lecture à une PR  
**Méthodologie :** Instructions Netxeo skill-file-security (01 → 28)  
**Auditeur :** Claude Sonnet 4.6 / analyse statique manuelle

---

## 📊 Score par Catégorie

| Catégorie | Score | Problèmes |
|---|---|---|
| Secrets & Gestion des clés | 90/100 | 0 critique, 0 haute |
| Réseau & CORS | 60/100 | 0 haute, 1 moyenne |
| Headers HTTP | 72/100 | 0 haute, 1 moyenne, 2 faibles |
| Auth & Sessions | 75/100 | 1 haute, 1 moyenne |
| Cryptographie | 92/100 | 0 |
| JWT (validation côté serveur) | 70/100 | 1 moyenne |
| Sécurité base de données | 80/100 | 1 faible |
| Déploiement & CI/CD | 78/100 | 1 haute, 1 faible |
| Docker & Containers | 82/100 | 1 faible |
| Injections | 95/100 | 0 |
| Attaques avancées (SSRF, IDOR…) | 92/100 | 0 |
| Supply Chain | 90/100 | 0 |
| RGPD / Compliance | 70/100 | 1 moyenne |
| Monitoring & Détection | 72/100 | 1 faible, 1 info |
| Analyse code source | 88/100 | 0 |

```
╔══════════════════════════════════════════════════════════╗
║         SCORE GLOBAL : 58/100  🟠                        ║
╠══════════════════════════════════════════════════════════╣
║  🟢 Secrets & Fichiers             90/100                ║
║  🟠 Réseau & CORS                  60/100                ║
║  🟡 Headers HTTP                   72/100                ║
║  🟡 Auth & Sessions                75/100                ║
║  🟢 Cryptographie                  92/100                ║
║  🟡 Sécurité JWT                   70/100                ║
║  🟡 Sécurité BDD                   80/100                ║
║  🟡 Déploiement & CI/CD            78/100                ║
║  🟡 Docker & Containers            82/100                ║
║  🟢 Injections                     95/100                ║
║  🟢 Attaques avancées              92/100                ║
║  🟢 Supply Chain                   90/100                ║
║  🟡 RGPD / Compliance              70/100                ║
║  🟡 Monitoring & Détection         72/100                ║
║  🟢 Analyse code source            88/100                ║
╚══════════════════════════════════════════════════════════╝
  🔴 0 critique | 🟠 1 haute | 🟡 4 moyennes | 🔵 6 faibles | ℹ️ 3 infos
```

---

## 🟠 Problèmes Hauts — Corriger en Priorité

### H1 — Keycloak `start-dev` en Stagingkub (CWE-1173)

**Fichier :** `rhDemo/infra/stagingkub/helm/rhdemo/templates/keycloak-deployment.yaml` ligne 41  
**Problème :** L'environnement stagingkub, censé être représentatif d'une production Kubernetes, démarre Keycloak avec la commande `start-dev`. Ce mode de développement désactive ou affaiblit plusieurs mécanismes de sécurité :

- Validation stricte du hostname désactivée (`--hostname-strict=false` implicite)
- HTTP activé sans contrainte (pas de redirection HTTPS forcée au niveau Keycloak)
- Politiques de mots de passe par défaut très permissives (longueur minimale = 8, pas de complexité)
- Vérification email non requise
- MFA (TOTP/WebAuthn) non configuré ni imposé
- Politique de brute-force intégrée de Keycloak : non activée par défaut en mode dev

**Risque :** Un attaquant externe avec accès au realm RHDemo peut utiliser des mots de passe faibles, compromettre des comptes via brute-force, et accéder aux ressources protégées. Rend caduque l'objectif "représentatif d'une production" du stagingkub.

**Fix :**
```yaml
# keycloak-deployment.yaml — remplacer start-dev par start
args:
  - start                           # ← Mode production
  - --db=postgres
  - --db-url=jdbc:postgresql://...
  - --db-username={{ ... }}
  - --proxy-headers={{ .Values.keycloak.proxyHeaders }}
  - --http-enabled={{ .Values.keycloak.httpEnabled }}
  - --health-enabled=true
  - --metrics-enabled=true
  - --hostname={{ .Values.keycloak.hostname }}
  - --hostname-strict=true          # ← Validation stricte hostname
```

Puis activer dans la configuration du realm RHDemo (via rhDemoInitKeycloak) :
- Brute-force protection : `failureFactor: 5`, `waitIncrementSeconds: 30`, `maxDeltaTimeSeconds: 43200`
- Politique de mots de passe : longueur ≥ 12, complexité, historique ≥ 5
- Vérification email : activée  
- Session timeout : revoir `sso-session-idle-timeout: 1800` (30 min, acceptable)

**Références :** [Keycloak Production Guide](https://www.keycloak.org/server/configuration-production), OWASP A07:2021

---

## 🟡 Problèmes Moyens

### M1 — JWT `issuer-uri` Absent : Validation de l'Issuer Non Effectuée (CWE-347)

**Fichiers :**  
- `rhDemo/src/main/resources/application-ephemere.yml` lignes 31-33  
- `rhDemo/src/main/resources/application-stagingkub.yml` lignes 39-43

**Problème :** Le Resource Server JWT Spring Boot est configuré uniquement avec `jwk-set-uri` sans `issuer-uri`. Le commentaire indique "Spring utilisera l'issuer présent dans le token JWT pour validation", ce qui est **incorrect** : sans `issuer-uri`, le `NimbusJwtDecoder` de Spring Security ne valide **pas** la claim `iss` du token.

Cela signifie qu'un token issu d'un realm différent (ex : `master`) partageant les mêmes clés de signature serait accepté par l'application. Bien que chaque realm Keycloak utilise ses propres clés en pratique, l'absence de validation explicite de l'issuer constitue une non-conformité ASVS V3.5.

```yaml
# ❌ Configuration actuelle (application-ephemere.yml)
resourceserver:
  jwt:
    jwk-set-uri: http://keycloak-ephemere:8080/realms/RHDemo/protocol/openid-connect/certs
    # Pas d'issuer-uri → le claim 'iss' n'est pas validé
```

**Mécanisme Spring Boot (important pour le fix) :**  
Quand `jwk-set-uri` et `issuer-uri` sont tous deux configurés, Spring Boot :
1. utilise `jwk-set-uri` pour récupérer les clés JWK (aucune discovery OIDC, aucun appel vers `issuer-uri`)
2. configure un `JwtClaimValidator` qui vérifie `token.iss.equals(issuer-uri)` — **pure comparaison de chaîne**

La valeur d'`issuer-uri` doit donc correspondre au claim `iss` présent dans les tokens. Keycloak inscrit dans `iss` la valeur de `KC_HOSTNAME_URL` — c'est-à-dire l'**URL publique**, pas l'URL interne. Utiliser l'URL interne (`http://keycloak-ephemere:8080/...`) provoquerait une régression immédiate (validation `iss` toujours en échec).

```yaml
# ✅ Configuration sécurisée (ephemere)
resourceserver:
  jwt:
    jwk-set-uri: http://keycloak-ephemere:8080/realms/RHDemo/protocol/openid-connect/certs
    issuer-uri: https://keycloak.ephemere.local:58443/realms/RHDemo   # URL publique = valeur du claim iss
```

**Note :** `application-stagingkub.yml` a déjà le bon pattern (public URL en `issuer-uri`, URL interne en `jwk-set-uri`).

**Risque :** Token confusion entre realms — faible si les clés sont bien isolées par realm, mais non-conformité ASVS qui doit être corrigée.

**Références :** CWE-347, OWASP A07:2021, ASVS V3.5.3

---

### M2 — Absence de Rate Limiting sur les Endpoints HTTP (CWE-307, CWE-770)

**Fichiers :**  
- `rhDemo/infra/ephemere/nginx/conf.d/rhdemo.conf` — aucune directive `limit_req`  
- `rhDemo/infra/ephemere/nginx/conf.d/keycloak.conf` — idem  
- `rhDemo/src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java` — aucun rate limiter

**Problème :** Aucune limitation du nombre de requêtes n'est configurée, ni au niveau Nginx (pas de `limit_req_zone`, `limit_req`), ni au niveau Spring Boot (pas de Bucket4j, pas de Resilience4j rate limiter). Les endpoints exposés au réseau ne disposent donc d'aucune protection contre :

- Les attaques par force brute sur Keycloak (endpoint login)  
- La saturation des endpoints REST (pseudo-DoS même authentifié)  
- L'énumération par scan d'endpoints  

**Note :** Keycloak dispose d'une protection brute-force intégrée dans les paramètres du realm (désactivée par défaut en `start-dev` - voir H1). Cette protection couvre le login, mais pas les autres endpoints.

**Fix (Nginx) :**
```nginx
# nginx.conf — section http
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/m;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;

# conf.d/rhdemo.conf — section server
location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    limit_req_status 429;
    proxy_pass http://rhdemo_backend;
    ...
}
```

**Fix (Keycloak Realm) :** Activer la brute-force protection dans le realm RHDemo :
```
Realm Settings → Security Defenses → Brute Force Detection
- Enabled: ON
- Permanent Lockout: OFF
- Max Login Failures: 5
- Wait Increment: 30s
```

**Références :** OWASP A07:2021, CWE-307, NIST SP 800-63B

---

### M3 — Headers COOP / COEP / CORP Absents (CWE-693)

**Fichiers :**  
- `rhDemo/infra/ephemere/nginx/conf.d/rhdemo.conf` lignes 48-54  
- `rhDemo/src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java`

**Problème :** Les headers de mitigation Spectre (attaques de type cross-process side-channel) sont absents :

```
Cross-Origin-Opener-Policy: same-origin        # COOP — manquant
Cross-Origin-Embedder-Policy: require-corp      # COEP — manquant
Cross-Origin-Resource-Policy: same-origin       # CORP — manquant
```

Ces headers isolent le processus du navigateur, empêchent les attaques Spectre qui permettraient à une page malveillante embarquée dans le même contexte de lire la mémoire du navigateur et d'en extraire des tokens de session.

**Fix (Nginx) :**
```nginx
# conf.d/rhdemo.conf
add_header Cross-Origin-Opener-Policy "same-origin" always;
add_header Cross-Origin-Resource-Policy "same-origin" always;
# COEP optionnel si ressources tierces nécessaires, sinon :
# add_header Cross-Origin-Embedder-Policy "require-corp" always;
```

**Références :** CWE-693, OWASP A05:2021

---

### M4 — Swagger/OpenAPI Accessible dans le Profil Ephemere

**Fichier :** `rhDemo/src/main/resources/application-ephemere.yml`

**Problème :** En stagingkub, Swagger est correctement désactivé :
```yaml
springdoc:
  swagger-ui:
    enabled: false
  api-docs:
    enabled: false
```

Cette désactivation est **absente** du profil ephemere. L'interface Swagger est donc accessible sur `/api-docs/swagger-ui` dans l'environnement ephemere. La protection est assurée par le rôle `admin` dans `SecurityConfig.java` (`.requestMatchers("/api-docs/**").hasRole("admin")`), mais cela expose :

- La structure complète de l'API à tout admin connecté
- Les détails des modèles de données (Employe avec tous ses champs)
- Dans les logs ZAP qui scrutent l'environnement ephemere

**Fix :**
```yaml
# application-ephemere.yml — ajouter
springdoc:
  swagger-ui:
    enabled: false
  api-docs:
    enabled: false
```

**Références :** OWASP A05:2021, ASVS V14.3.1

---

## 🔵 Problèmes Faibles

### F1 — Port PostgreSQL Exposé sur l'Hôte en Dev

**Fichier :** `rhDemo/infra/dev/docker-compose.yml` ligne 10

```yaml
ports:
  - "5432:5432"  # ← Accessible depuis l'hôte et le réseau local
```

**Risque :** PostgreSQL est accessible directement depuis l'hôte et potentiellement le réseau local, sans nécessiter de passer par l'application. Un accès non autorisé au réseau du poste de dev permettrait de tenter une connexion directe à la base de données.

**Fix :** Supprimer le port binding ou le restreindre à localhost :
```yaml
ports:
  - "127.0.0.1:5432:5432"  # Localhost uniquement
```
Ou supprimer le bloc `ports` entièrement (accès via `docker exec` ou port-forward).

---

### F2 — HSTS sans Directive `preload`

**Fichiers :** `rhDemo/infra/ephemere/nginx/conf.d/rhdemo.conf` ligne 49, `keycloak.conf` ligne 40

```nginx
# ❌ Actuel
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# ✅ Recommandé
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

**Risque :** Sans `preload`, les navigateurs ne pré-enregistrent pas le domaine dans leur liste HSTS. Pour des domaines internes (`*.intra.leuwen-lc.fr`), cela a un impact limité (pas inscriptible dans la preload list publique), mais la directive `preload` reste une bonne pratique.

**Note :** Non applicable aux domaines `.local` (ephemere) — à corriger surtout en stagingkub.

---

### F3 — `Permissions-Policy` Incomplète

**Fichier :** `rhDemo/infra/ephemere/nginx/conf.d/rhdemo.conf` ligne 54

```nginx
# ❌ Actuel
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

# ✅ Recommandé (2026)
add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=(), usb=(), interest-cohort=(), accelerometer=(), gyroscope=(), magnetometer=()" always;
```

**Risque :** Des APIs navigateur sensibles (payment, USB, capteurs) restent potentiellement activables par des scripts malveillants injectés.

---

### F4 — `readOnlyRootFilesystem` Absent du Déploiement Kubernetes rhdemo-app

**Fichier :** `rhDemo/infra/stagingkub/helm/rhdemo/templates/rhdemo-app-deployment.yaml` lignes 131-135

```yaml
# ❌ Actuel
securityContext:
  runAsUser: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
  # readOnlyRootFilesystem absent

# ✅ Recommandé
securityContext:
  runAsUser: 1000
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
```

**Note :** Le montage du volume secrets est en `readOnly: true` (ligne 109), ce qui est correct. Pour `readOnlyRootFilesystem: true`, vérifier d'abord que Spring Boot ne nécessite pas d'écriture dans le filesystem (logs vers stdout OK, fichiers temporaires JVM via `/tmp` à monter en `tmpfs`).

```yaml
# Ajouter dans le template si readOnlyRootFilesystem est activé
volumes:
  - name: tmp-dir
    emptyDir: {}
volumeMounts:
  - name: tmp-dir
    mountPath: /tmp
```

---

### F5 — Logs DEBUG/TRACE dans le Profil Ephemere

**Fichier :** `rhDemo/src/main/resources/application-ephemere.yml` lignes 50-57

```yaml
logging:
  level:
    org.springframework.web: DEBUG
    org.springframework.security: DEBUG
    org.springframework.security.oauth2: TRACE   # ← TRACE niveau maximum
    org.springframework.web.client: DEBUG
```

**Risque :** Les logs de niveau TRACE pour Spring Security OAuth2 peuvent contenir des informations sensibles : tokens d'accès, codes d'autorisation, claims JWT, paramètres des requêtes OIDC. Ces informations se retrouvent dans les logs Jenkins (archivés en artifacts) et accessibles aux développeurs ayant accès au CI.

**Fix :** Réduire à INFO ou au minimum WARN pour les packages sensibles en ephemere :
```yaml
logging:
  level:
    org.springframework.security: INFO          # Réduire depuis DEBUG
    org.springframework.security.oauth2: INFO   # Réduire depuis TRACE
```

---

### F6 — Mot de Passe Keycloak par Défaut `admin:admin` en Dev si Variable Absente

**Fichier :** `rhDemo/infra/dev/docker-compose.yml` ligne 48

```yaml
KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD:-admin}
#                                                   ^^^^^ valeur par défaut
```

**Risque :** Si l'environnement de dev est démarré sans fichier `.env` ou sans la variable `KEYCLOAK_ADMIN_PASSWORD` définie, Keycloak démarre avec le mot de passe administrateur `admin`. Ce credential par défaut est documenté dans le README (ligne 169 : `admin / admin`) mais constitue une mauvaise pratique même en dev.

**Fix :** Supprimer la valeur par défaut pour forcer une configuration explicite :
```yaml
KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD:?KEYCLOAK_ADMIN_PASSWORD must be set}
```

Ou documenter un `.env.example` avec des credentials de dev non triviaux.

---

## ℹ️ Informations

### I1 — `security.txt` Absent (RFC 9116)

**Chemin attendu :** `/home/leno-vo/git/repository/rhDemo/src/main/resources/static/.well-known/security.txt`

Standard RFC 9116 permettant aux chercheurs en sécurité de signaler des vulnérabilités. Non critique pour un projet interne, mais bonne pratique DevSecOps.

**Exemple à créer :**
```
Contact: mailto:leuwenlc@gmail.com
Expires: 2027-01-01T00:00:00.000Z
Preferred-Languages: fr, en
Policy: https://rhdemo-stagingkub.intra.leuwen-lc.fr/security-policy
```

---

### I2 — `/actuator/prometheus` Accessible sans Authentification en Dev Local

**Fichier :** `rhDemo/src/main/java/fr/leuwen/rhdemoAPI/springconfig/SecurityConfig.java` ligne 64

```java
.requestMatchers("/actuator/prometheus").permitAll()
```

En dev local (profil par défaut, pas de nginx), les métriques Prometheus sont accessibles sans authentification sur `http://localhost:9000/actuator/prometheus`. Cela peut exposer des informations sur les endpoints utilisés, le nombre de requêtes, les classes d'erreur, les performances JVM.

En ephemere et stagingkub, cet endpoint est soit bloqué par nginx (`return 403` sur `/actuator`), soit sur un port management dédié (9001) non exposé via la Gateway. Le risque est donc limité au dev local.

---

### I3 — PostgreSQL `runAsNonRoot: false` dans les StatefulSets Kubernetes

**Fichiers :** `postgresql-rhdemo-statefulset.yaml` et `postgresql-keycloak-statefulset.yaml` ligne 38

```yaml
securityContext:
  runAsNonRoot: false   # ← PostgreSQL nécessite root pour init
  allowPrivilegeEscalation: false
```

Contrainte technique connue : PostgreSQL doit s'exécuter en tant que root lors de l'initialisation du répertoire de données (`chown`), puis passe à l'utilisateur `postgres` (uid 70). L'init-container `chown` est correctement présent dans le template. Ce comportement est attendu et non corrigeable sans changer l'image de base.

---

## ✅ Ce qui est Bien Sécurisé

La liste suivante représente les contrôles de sécurité correctement implémentés, validés lors de cet audit.

### Architecture & Authentification
- **Patron BFF (Backend For Frontend)** : Les tokens OAuth2/OIDC ne transitent jamais côté client. La session est stateful avec `JSESSIONID` HTTPOnly + CSRF double défense.
- **CSRF multi-couche** : `CookieCsrfTokenRepository.withHttpOnlyFalse()` (lecture JS volontaire) + `SameSite=Strict` sur le cookie XSRF-TOKEN + vérification du header `X-XSRF-TOKEN`. Pattern SPA CSRF conforme.
- **RBAC granulaire** : Annotation `@PreAuthorize("hasRole('...')")` sur chaque endpoint critique. Rôles `consult` (lecture) et `MAJ` (écriture) bien séparés.
- **Session SameSite=Lax** : Choix correct pour l'OAuth2/OIDC — Strict bloquerait le retour du redirect Keycloak.

### Headers & CSP
- **CSP stricte sans `unsafe-inline` ni `unsafe-eval`** : `CspPolicyBuilder` génère une CSP dynamique basée sur l'URL Keycloak configurée. Implémentation remarquable.
- **`frame-ancestors 'none'`** : Protège contre le clickjacking.
- **`server_tokens off`** dans nginx : Version masquée.
- **TLS 1.2/1.3 avec ciphers ECDHE uniquement** : Perfect Forward Secrecy garantie.

### Secrets & Supply Chain
- **SOPS + clé AGE** : Secrets versionnés chiffrés dans Git. Déchiffrement dans `/tmp` hors workspace CI. Permissions `chmod 600/400` appliquées.
- **Images Docker épinglées par SHA256** dans tous les Compose et Helm charts (ex: `postgres:18.3-alpine3.22@sha256:5af62d4...`). Protection contre la mutation des tags.
- **Multi-stage build** dans le Dockerfile : Image finale sans outils de compilation.
- **Utilisateur non-root** dans le container Spring Boot (`spring:spring`, uid 1000).
- **SBOM CycloneDX** généré par Trivy à chaque build CI.
- **Signature d'image Cosign** activée dans le pipeline CI.

### Base de Données & Injections
- **JPA Criteria API + `EmployeSpecification`** : Requêtes paramétrées, escape des wildcards (`%`, `_`, `\`) dans les LIKE. Pas de SQL natif concaténé.
- **Bean Validation** sur `EmployeRequestDTO` : `@NotBlank`, `@Email`, `@Size` — validation à la frontière système.
- **`ddl-auto: validate`** : Hibernate ne modifie pas le schéma en production.
- **Utilisateur DB dédié** (pas `root` / superuser).
- **Sanitisation des champs de tri** : Whitelist `SORT_ALLOWED_FIELDS` dans `EmployeController` — protège contre l'injection via paramètre `sort`.

### Kubernetes & Infrastructure
- **RBAC Jenkins** : ServiceAccount `jenkins-deployer` avec permissions limitées au seul namespace `rhdemo-stagingkub`. Pas d'accès `kube-system`.
- **NetworkPolicies Zero Trust** : Default Deny ingress + egress. Flux explicites par pod. Egress Internet bloqué (sauf DNS).
- **SecurityContext Kubernetes** pour rhdemo-app : `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities: drop: ["ALL"]`, `seccompProfile: RuntimeDefault`, `automountServiceAccountToken: false`.
- **Actuator sur port séparé** (9001) en stagingkub, non exposé via la Gateway NGF.

### CI/CD & Qualité
- **OWASP Dependency-Check** : `failBuildOnCVSS: 7.0` — Fail CI si CVSS ≥ 7.
- **Trivy** : Scan de 5 images Docker en parallèle avec fail sur CRITICAL.
- **SonarQube Quality Gate** : Couverture ≥ 50%, aucune issue Medium+.
- **OWASP ZAP** : Tests dynamiques avec clé API générée aléatoirement par build (`/dev/urandom`).
- **Logs de secrets désactivés** via `set +x` dans Jenkins lors du sourcing des secrets.

### Gestion des Erreurs
- **`GlobalExceptionHandler`** : Retourne des messages génériques (`"Une erreur interne s'est produite"`) aux clients tout en loggant le stack trace complet côté serveur. Pas de fuite d'information technique.
- **`EmployeNotFoundException`** : 404 propre sans détail de schéma.

---

## 📋 Risques Documentés / Acceptés

Les points suivants sont des limitations connues, documentées dans le `CLAUDE.md` et acceptées dans le cadre du projet pédagogique :

| Risque | Localisation | Statut |
|---|---|---|
| Keycloak sans vérification email, MFA, politique mdp stricte | `rhDemo/infra/dev/` (dev uniquement) | Accepté — dev local |
| Pas de mécanisme de scalabilité (Redis pour sessions partagées) | Architecture globale | Accepté — hors scope |
| Application non prête pour la production | README.md | Documenté |

**Note :** La présence de `start-dev` dans **stagingkub** n'est en revanche **pas dans cette liste** et constitue le problème H1 à corriger.

---

## 📅 Plan de Remédiation Recommandé

### Priorité 1 — Court terme (avant prochain sprint)

1. **[H1]** Migrer Keycloak stagingkub vers `start` + activer brute-force protection dans le realm
2. **[M1]** Ajouter `issuer-uri` dans `application-ephemere.yml` et `application-stagingkub.yml`
3. **[M2]** Ajouter `limit_req_zone` dans nginx pour les endpoints `/api/` et le passage par Keycloak
4. **[F5]** Réduire les niveaux de log ephemere de DEBUG/TRACE à INFO

### Priorité 2 — Moyen terme

5. **[M3]** Ajouter les headers COOP/COEP/CORP dans nginx
6. **[M4]** Désactiver Swagger/OpenAPI dans le profil ephemere
7. **[F1]** Restreindre le port PostgreSQL à `127.0.0.1:5432:5432` en dev
8. **[F3]** Compléter la `Permissions-Policy` avec `payment=()`, `usb=()`, `interest-cohort=()`

### Priorité 3 — Long terme / Amélioration continue

9. **[F4]** Activer `readOnlyRootFilesystem: true` + `emptyDir` pour `/tmp` dans le déploiement Kubernetes
10. **[F2]** Ajouter `preload` au HSTS dans les configs nginx stagingkub
11. **[F6]** Supprimer la valeur par défaut `:-admin` pour `KEYCLOAK_ADMIN_PASSWORD` en dev
12. **[I1]** Créer `/src/main/resources/static/.well-known/security.txt`

---

## 🔄 Statut de Rotation des Secrets

| Secret | Mécanisme | Statut |
|---|---|---|
| Client secret Keycloak | SOPS + AGE key | ✅ Chiffré dans Git |
| Mots de passe PostgreSQL | SOPS + AGE key | ✅ Chiffrés dans Git |
| Mot de passe admin Keycloak | SOPS (ephemere) / K8s Secret (stagingkub) | ✅ |
| Clé AGE SOPS | Jenkins credential (Secret file) | Pas de rotation automatique — surveiller |
| ZAP API Key | Générée par build (`/dev/urandom`) | ✅ Ephémère par build |

---

## ✅ Ensemble des Findings Remédiés

### H1 — Keycloak `start-dev` en Stagingkub (CWE-1173) — Résolu le 2026-06-17

**Correction apportée :**
- `keycloak-deployment.yaml` ligne 41 : `start-dev` remplacé par `start` (mode production Keycloak)
- `values.yaml` ligne 143 : `hostnameStrict: true` — validation stricte du hostname activée
- Argument `--hostname-strict={{ .Values.keycloak.hostnameStrict }}` transmis au démarrage

**Résultat :** Keycloak stagingkub démarre désormais en mode production. La validation stricte du hostname est active. Les mécanismes de sécurité propres au mode `start` (validation hostname, contraintes TLS, comportements de sécurité par défaut renforcés) sont rétablis.

### M3 — Headers COOP / COEP / CORP Absents (CWE-693) — Résolu le 2026-06-17

**Correction apportée — Ephemere (Nginx) :**
- `rhdemo.conf` : ajout de `Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Embedder-Policy: require-corp`, `Cross-Origin-Resource-Policy: same-origin` — COEP safe car tous les assets Vue.js/Element Plus sont bundlés (aucune ressource cross-origin)
- `keycloak.conf` : ajout de COOP et CORP uniquement — COEP omis car le thème Keycloak peut référencer des ressources internes sans header CORP, ce qui casserait la page de login

**Correction apportée — Stagingkub (NGF) :**
- `httproute.yaml` : headers injectés via `RequestHeaderModifier` (API native Gateway, sans SnippetsFilter) — même distinction rhdemo (COOP+CORP+COEP) / keycloak (COOP+CORP)
- `values.yaml` : section `securityHeaders` par route, COEP conditionnel (`{{- if $route.securityHeaders.coep }}`)

**Répartition documentée :** commentaire ajouté dans `SecurityConfig.java`, `rhdemo.conf`, `keycloak.conf` et `httproute.yaml` expliquant que les headers statiques (valeurs fixes) sont gérés par Nginx/NGF, et les headers dynamiques (CSP avec URL Keycloak variable par environnement) par Spring Security.

---

### M2 — Absence de Rate Limiting (CWE-307, CWE-770) — Résolu le 2026-06-17

**Correction apportée — Ephemere (Nginx) :**
- `nginx.conf` : 3 zones `limit_req_zone` dans le bloc `http`, clé `$binary_remote_addr` — limite **par adresse IP** (chaque IP a son propre compteur, un utilisateur légitime actif ne pénalise pas les autres) :
  - `rhdemo_global` : 60 r/m — navigation SPA complète
  - `rhdemo_api` : 30 r/m — endpoints REST `/api/`
  - `keycloak_login` : 5 r/m — vhost Keycloak (navigateur uniquement, les appels Spring Boot → Keycloak contournent Nginx)
- `rhdemo.conf` : `location /api/` séparée avec `burst=30 nodelay` (valeur volontairement élevée pour absorber les séquences d'appels des tests Selenium CI) ; `location /` avec `burst=20`
- `keycloak.conf` : `limit_req zone=keycloak_login burst=2 nodelay` — rejet immédiat, complète la brute-force protection native du realm Keycloak
- Code de rejet : `limit_req_status 429`

**Correction apportée — Stagingkub (NGF) :**
- Nouveau template `ratelimitpolicy.yaml` utilisant le CRD natif `gateway.nginx.org/v1alpha1` — pas de SnippetsFilter requis
- `rhdemo-rate-limit` cible `rhdemo-route` : 60 r/m, burst=20
- `keycloak-rate-limit` cible `keycloak-route` : 5 r/m, burst=2, noDelay
- Valeurs externalisées dans `gateway.rateLimit` de `values.yaml` (ajustables via `helm upgrade --set`)

**Note :** La brute-force protection native du realm Keycloak (failureFactor, waitIncrementSeconds) relève du finding H1 et n'est pas encore configurée dans `rhDemoInitKeycloak`.

---

### M1 — JWT `issuer-uri` Absent (CWE-347) — Résolu le 2026-06-17

**Correction apportée :**
- `application-ephemere.yml` : ajout de `issuer-uri: https://keycloak.ephemere.local:58443/realms/RHDemo`
- `application-stagingkub.yml` : déjà corrigé antérieurement avec le même pattern (URL publique)

**Point d'attention documenté dans le finding :** l'`issuer-uri` doit impérativement être l'URL **publique** de Keycloak (valeur de `KC_HOSTNAME_URL`), et non l'URL interne. Keycloak inscrit `KC_HOSTNAME_URL` dans le claim `iss` des tokens ; une URL interne causerait un échec systématique de la validation. Spring Boot n'effectue aucun appel HTTP vers `issuer-uri` quand `jwk-set-uri` est également configuré — la valeur sert uniquement de référence pour la comparaison du claim `iss`.

---

*Rapport généré le 2026-05-22 par Claude Sonnet 4.6 — Analyse statique du code source sans exécution*
