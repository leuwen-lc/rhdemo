# Avis de Sécurité et Remédiations

Ce document trace les vulnérabilités critiques détectées et les actions de remédiation appliquées.

---

## CVE-2025-49794 & CVE-2025-49796 - Vulnérabilités libxml2

### Détection

- **Date de détection** : 2025-11-27
- **Outil** : Trivy Security Scanner
- **Sévérité** : CRITICAL (Score CVSS: 9.1)

### Description

Deux vulnérabilités critiques découvertes dans la bibliothèque libxml2 par Nikita Sveshnikov (Positive Technologies) :

**CVE-2025-49794** - Use-After-Free et Type Confusion

- **Impact** : Corruption mémoire lors du parsing XPath avec XML schematron
- **Vecteur d'attaque** : Fichier XML malveillant
- **Conséquences** : Déni de service (crash), exécution de code potentielle

**CVE-2025-49796** - Type Confusion dans module Schematron

- **Impact** : Corruption mémoire lors du traitement d'éléments sch:name
- **Vecteur d'attaque** : Fichier XML malveillant
- **Conséquences** : Déni de service, comportement indéfini

### Images affectées

| Image | Version vulnérable | Status |
| --- | --- | --- |
| nginx | 1.27-alpine (Alpine 3.20) | ❌ VULNÉRABLE |
| postgres | 16-alpine (Alpine 3.20) | ✅ Non affecté |
| keycloak | 26.4.2 | ✅ Non affecté |
| rhdemo-api | build-* (Paketo) | ✅ Non affecté |

**Seule l'image Nginx** était affectée car elle utilise Alpine Linux 3.20 qui contient une version vulnérable de libxml2.

### Remédiation appliquée

**Action** : Mise à jour de l'image Nginx vers une version avec Alpine 3.21

**Changements** :

```yaml
# Avant (vulnérable)
nginx:
  image: nginx:1.27-alpine

# Après (corrigé)
nginx:
  image: nginx:1.27.3-alpine3.21
```

**Fichiers modifiés** :

- `infra/ephemere/docker-compose.yml` (ligne 148)
- `Jenkinsfile` (lignes 1078, 1129) - Mise à jour du stage Trivy

**Version du correctif** :

- Alpine Linux 3.21 inclut libxml2 2.13.6 qui corrige CVE-2025-49794 et CVE-2025-49796
- Nginx 1.27.3 (dernière version stable au 2025-11-27)

### Validation

**Test de non-régression** :

```bash
# Vérifier que la nouvelle image fonctionne
docker pull nginx:1.27.3-alpine3.21
docker run --rm nginx:1.27.3-alpine3.21 nginx -v

# Scanner avec Trivy
trivy image --severity CRITICAL nginx:1.27.3-alpine3.21
```

**Résultat attendu** : 0 vulnérabilités CRITICAL

### Timeline

| Date | Action |
| --- | --- |
| 2025-06-03 | Découverte des CVE par Positive Technologies |
| 2025-06-11 | Attribution des numéros CVE officiels |
| 2025-11-12 | Alpine 3.21.2 publiée avec correctif libxml2 |
| 2025-11-27 | Détection par Trivy dans notre pipeline |
| 2025-11-27 | Remédiation appliquée (nginx:1.27.3-alpine3.21) |

### Références

- [CVE-2025-49794 - NVD](https://nvd.nist.gov/vuln/detail/cve-2025-49794)
- [CVE-2025-49796 - NVD](https://nvd.nist.gov/vuln/detail/cve-2025-49796)
- [Seal Security Blog - Analyse détaillée](https://www.seal.security/blog/zero-day-vulnerabilities-in-libxml2-cve-2025-49794-cve-2025-49796-a-deep-dive-and-seal-securitys-proactive-solution)
- [Ubuntu Security Advisory](https://ubuntu.com/security/CVE-2025-49796)
- [RedHat CVE Database](https://access.redhat.com/security/cve/cve-2025-49796)

### Leçons apprises

1. **Scan automatique efficace** : Le stage Trivy a détecté les CVE dès leur intégration au pipeline
2. **Réactivité** : Remédiation appliquée le jour même de la détection
3. **Images Alpine** : Préférer les tags explicites (ex: `alpine3.21`) plutôt que génériques (`alpine`)
4. **Versions fixes** : Utiliser des versions précises pour garantir la reproductibilité

### Actions futures

- [ ] Vérifier mensuellement les nouvelles versions de Nginx
- [ ] Mettre en place des alertes automatiques pour les nouvelles CVE (GitHub Dependabot)
- [ ] Considérer l'utilisation d'images distroless pour réduire la surface d'attaque

---

## 2025-11-28 — Nouvelles CVE CRITICAL détectées dans nginx:1.27.3-alpine3.21

### Détection supplémentaire

- **Date** : 2025-11-28
- **Contexte** : Après migration vers nginx:1.27.3-alpine3.21, Trivy détecte encore 2 CVE CRITICAL

**Résultats du scan** :

```text
🔍 Scan: nginx:1.27.3-alpine3.21
   ├─ CRITICAL:   2
   ├─ HIGH:       4
   └─ MEDIUM:    18
```

### Nouvelle remédiation

**Action** : Mise à jour vers Nginx 1.29.3 (dernière version stable au 2025-11-28)

**Changements** :

```yaml
# Version précédente (encore vulnérable)
nginx:
  image: nginx:1.27.3-alpine3.21

# Nouvelle version (correctif appliqué)
nginx:
  image: nginx:1.29.3-alpine
```

**Fichiers modifiés** :

- `infra/ephemere/docker-compose.yml` (ligne 148)
- `Jenkinsfile` (lignes 1081, 1143)

**Justification** :

- Nginx 1.29.3 publié le 19 novembre 2025
- Inclut Alpine Linux avec les derniers correctifs de sécurité
- Contient libxml2 >= 2.13.6 et autres packages à jour

**Référence** : [Nginx Docker Hub](https://hub.docker.com/_/nginx)

### Timeline mise à jour

| Date | Action |
| --- | --- |
| 2025-11-27 | Première migration : nginx:1.27-alpine → nginx:1.27.3-alpine3.21 |
| 2025-11-28 | Détection de 2 CVE CRITICAL supplémentaires |
| 2025-11-28 | Seconde migration : nginx:1.27.3-alpine3.21 → nginx:1.29.3-alpine |

### Note importante

Cette situation démontre l'importance du **scan continu** avec Trivy :

- ✅ Les CVE libxml2 (CVE-2025-49794, CVE-2025-49796) ont été corrigées
- ⚠️ De **nouvelles** vulnérabilités ont été détectées dans d'autres packages
- 🔄 La mise à jour vers la dernière version stable (1.29.3) devrait résoudre ces nouvelles CVE

**Action de suivi** : Vérifier le prochain scan Trivy après déploiement de nginx:1.29.3-alpine

---

## CVE-2025-68121 - Go crypto/tls TLS Session Resumption Auth Bypass (gosu)

### Détection

- **Date de détection** : 2026-02-12
- **Outil** : Trivy Security Scanner
- **Sévérité** : CRITICAL
- **Composant affecté** : `usr/local/bin/gosu` dans `postgres:18-alpine`

### Description

CVE-2025-68121 est une vulnérabilité dans le package `crypto/tls` de la bibliothèque standard Go. Lors d'une reprise de session TLS, si les champs `ClientCAs` ou `RootCAs` de la configuration sont modifiés entre le handshake initial et la reprise, la session peut être rétablie alors qu'elle aurait dû échouer. Cela permet un contournement potentiel des restrictions de certificats.

**Versions Go affectées** : Go < 1.24.13 et Go 1.25.0 à 1.25.6

L'outil `gosu` (v1.19), utilisé par l'image officielle PostgreSQL pour changer d'utilisateur au démarrage du conteneur, est compilé avec **Go 1.24.6** et embarque donc le code vulnérable de `crypto/tls`.

### Analyse de risque

#### Risque réel — NUL (faux positif fonctionnel)

`gosu` est un utilitaire de type `setuid+setgid+exec` dont le rôle unique est de changer d'utilisateur Unix puis d'exécuter une commande. Il **n'effectue aucune connexion réseau** et **n'utilise jamais** le package `crypto/tls` à l'exécution. Le code vulnérable est inclus dans le binaire Go par le compilateur mais n'est jamais appelé.

Cette position est confirmée par :

- Le mainteneur de gosu via [`govulncheck`](https://github.com/tianon/gosu/issues/144) qui vérifie que les chemins de code vulnérables ne sont pas atteignables
- La discussion upstream [docker-library/postgres#1324](https://github.com/docker-library/postgres/issues/1324)

### Images affectées

| Image | Composant | Status |
| --- | --- | --- |
| postgres:18-alpine | gosu 1.19 (Go 1.24.6) | ⚠️ CVE présente mais non exploitable |
| rhdemo-api | N/A | ✅ Non affecté |
| nginx | N/A | ✅ Non affecté |
| keycloak | N/A | ✅ Non affecté |

### Remédiation appliquée

**Action** : Exclusion de la CVE dans Trivy via `.trivyignore` (risque accepté - faux positif fonctionnel)

**Fichier créé** : `rhDemo/.trivyignore`

```text
# CVE-2025-68121 - Go crypto/tls TLS Session Resumption Auth Bypass
# Affecte : gosu (compilé en Go 1.24.6) dans postgres:18-alpine
# Risque réel : NUL - gosu n'effectue aucune connexion TLS
CVE-2025-68121
```

**Fichier modifié** : `rhDemo/vars/rhDemoLib.groovy`

- Ajout de `--ignorefile rhDemo/.trivyignore` aux commandes `trivy image` (scans JSON et table)

### Condition de retrait de l'exclusion

L'exclusion dans `.trivyignore` devra être **retirée** lorsque l'une de ces conditions sera remplie :

- Nouvelle release de gosu compilée avec Go >= 1.24.13 ou >= 1.25.7
- Mise à jour de l'image `postgres:18-alpine` intégrant un gosu corrigé

### Validation

```bash
# Vérifier que Trivy ignore bien la CVE
trivy image --ignorefile rhDemo/.trivyignore --severity CRITICAL postgres:18-alpine

# Vérifier que gosu n'utilise pas crypto/tls (nécessite govulncheck)
# govulncheck -mode binary /usr/local/bin/gosu
```

### Références

- [NVD - CVE-2025-68121](https://nvd.nist.gov/vuln/detail/CVE-2025-68121)
- [SentinelOne - CVE-2025-68121](https://www.sentinelone.com/vulnerability-database/cve-2025-68121/)
- [docker-library/postgres#1324 - gosu CVE discussion](https://github.com/docker-library/postgres/issues/1324)
- [gosu security policy](https://github.com/tianon/gosu/issues/144)
- [gosu releases](https://github.com/tianon/gosu/releases) - v1.19 (Go 1.24.6)
- [Go 1.24.13 release notes](https://go.dev/doc/devel/release) - inclut le fix crypto/tls

---

## CVE-2026-24400

### Détection

- **Date** : 2026-03-10
- **Outil** : OWASP
- **Sévérité** : HIGH

### Description

Starting in version 1.4.0 and prior to version 3.27.7, an XML External Entity (XXE) vulnerability exists in `org.assertj.core.util.xml.XmlStringPrettyFormatter`: the `toXmlDocument(String)` method initializes `DocumentBuilderFactory` with default settings, without disabling DTDs or external entities.

### Images affectées

POM uniquement

### Remédiation

Passage à la version Spring Boot 4.03

---

## CVE-2026-0540

### Détection

- **Date** : 2026-03-10
- **Outil** : OWASP
- **Sévérité** : MEDIUM (faux positif)

### Description

DOMPurify 3.1.3 through 3.3.1 and 2.5.3 through 2.5.8, fixed in commit 729097f, contain a cross-site scripting vulnerability that allows attackers to bypass attribute sanitization by exploiting five missing rawtext elements (noscript, xmp, noembed, noframes, iframe) in the SAFE_FOR_XML regex.

### Images affectées

POM uniquement

### Remédiation

Passage à la version springdoc-openapi 3.0.1

---

## CVE-2026-22184 — zlib untgz buffer overflow (nginx alpine)

### Détection

- **Date** : 2026-03-10
- **Outil** : Trivy Security Scanner
- **Sévérité** : CRITICAL (CVSS v3.1 : 9.8) / MEDIUM (CVSS v4.0 : 4.6)
- **Composant affecté** : `zlib-1.3.1-r2` (paquet Alpine) — utilitaire `contrib/untgz`
- **Statut** : Risque accepté — exclusion `.trivyignore` en attente de patch Alpine

### Description

CVE-2026-22184 est un dépassement de buffer global (`CWE-787 — Out-of-bounds Write`) dans
la fonction `TGZfname()` de l'utilitaire `contrib/untgz` de zlib (versions ≤ 1.3.1.2).
Cette fonction copie un nom d'archive fourni en ligne de commande dans un buffer statique
de 1024 octets via `strcpy()` sans validation de longueur.

**Point important** : la vulnérabilité est dans un utilitaire de démonstration autonome
(`untgz`) **non utilisé par nginx en tant que serveur web**. Le vecteur d'exploitation
nécessite une exécution locale avec un argument contrôlé par l'attaquant. Trivy signale
CRITICAL car le score CVSS v3.1 (9.8) utilisait un vecteur réseau (`AV:N`) surévalué —
CVSS v4.0 corrige à 4.6 MEDIUM avec vecteur local.

### Analyse de risque

| Critère | Valeur |
| --- | --- |
| Vecteur d'exploitation | Local (argument ligne de commande) |
| nginx exposé ? | Non — `untgz` n'est pas exécuté par nginx web server |
| Risque réel en production | Faible |
| Patch upstream disponible ? | Non — Alpine 3.23.3 livre toujours `zlib-1.3.1-r2` |
| Décision | Risque accepté + exclusion `.trivyignore` documentée |

### Chronologie de la remédiation

**Phase 1 — 2026-03-10** : mise à jour `nginx:1.29.4-alpine` → `nginx:1.29.5-alpine`.

Cette action a corrigé CVE-2026-1642 (Medium, nginx versions 1.3.0–1.29.4). En revanche
CVE-2026-22184 persiste car les deux images embarquent le même paquet Alpine `zlib-1.3.1-r2`
(Alpine 3.23.3) non encore patché par Alpine.

**Phase 2 — 2026-03-10** : exclusion Trivy documentée dans `.trivyignore`.

**Phase 3 — 2026-03-19** : mise à jour `nginx:1.29.5-alpine` → `nginx:1.29.6-alpine` (correctif CVE-2026-32767).

CVE-2026-22184 persiste dans 1.29.6 (Alpine 3.23.3 embarque toujours `zlib-1.3.1-r2`) — exclusion `.trivyignore` maintenue.

```text
nginx:1.29.4-alpine  →  Alpine 3.22   zlib-1.3.1-r2  ← CVE-2026-22184 présente
nginx:1.29.5-alpine  →  Alpine 3.23.3 zlib-1.3.1-r2  ← CVE-2026-22184 toujours présente
nginx:1.29.6-alpine  →  Alpine 3.23.3 zlib-1.3.1-r2  ← CVE-2026-22184 toujours présente
```

Aucune image nginx:alpine disponible ne contient un `zlib` patché à la date du 2026-03-19.

### Fichiers modifiés

- `Jenkinsfile-CI` (variable `NGINX_IMAGE`, phases 1 et 3)
- `infra/ephemere/docker-compose.yml` (valeur de repli `NGINX_IMAGE`, phases 1 et 3)
- `.trivyignore` (exclusion CVE-2026-22184 avec justification, phase 2)

### Validation

```bash
# Confirmer la version zlib dans l'image courante
docker run --rm --entrypoint sh nginx:1.29.6-alpine \
  -c "apk info zlib | head -1 && cat /etc/alpine-release"
# Résultat : zlib-1.3.1-r2 / 3.23.3

# Vérifier que le scan CI passe (CVE exclue via .trivyignore)
trivy image --ignorefile rhDemo/.trivyignore --severity CRITICAL nginx:1.29.6-alpine
```

### Condition de clôture

Retirer `CVE-2026-22184` du `.trivyignore` quand Alpine publie `zlib-1.3.1-r3` ou
supérieur avec le correctif intégré, et qu'une image `nginx:*-alpine` basée sur ce paquet
est disponible.

### Timeline

| Date | Action |
| --- | --- |
| 2026-01-07 | Publication CVE-2026-22184 (NVD) |
| 2026-03-10 | Détection par Trivy dans le pipeline CI (nginx:1.29.4-alpine) |
| 2026-03-10 | Mise à jour nginx:1.29.4 → 1.29.5 (corrige CVE-2026-1642, pas CVE-2026-22184) |
| 2026-03-10 | Analyse : Alpine 3.23.3 embarque toujours `zlib-1.3.1-r2` non patché |
| 2026-03-10 | Exclusion `.trivyignore` avec justification documentée |
| 2026-03-19 | Mise à jour nginx:1.29.5 → 1.29.6 (correctif CVE-2026-32767) — CVE-2026-22184 toujours présente |

### Références

- [NVD — CVE-2026-22184](https://nvd.nist.gov/vuln/detail/CVE-2026-22184)
- [nginx security advisories](https://nginx.org/en/security_advisories.html)
- [Alpine Linux security tracker](https://security.alpinelinux.org/)

---

## Alerte sécurité Jackson — tools.jackson.core 3.0.4 → 3.1.0

### Détection

- **Date** : 2026-03-14
- **Outil** : OWASP Dependency-Check
- **Sévérité** : HIGH
- **Composants affectés** :
  - `tools.jackson.core:jackson-core:3.0.4`
  - `tools.jackson.core:jackson-databind:3.0.4`

### Description

Alerte de sécurité détectée sur les artefacts Jackson 3.0.4, dépendances transitives de Spring Boot 4.0.3. La version 3.1.0 corrige les vulnérabilités signalées.

**Note sur le groupId** : Jackson 3.x a migré le groupId de `com.fasterxml.jackson.core` vers `tools.jackson.core`.

### Composants affectés

| Composant | Version vulnérable | Version corrective |
| --- | --- | --- |
| `tools.jackson.core:jackson-core` | 3.0.4 | 3.1.0 |
| `tools.jackson.core:jackson-databind` | 3.0.4 | 3.1.0 |
| `tools.jackson.core:jackson-annotations` | 3.0.4 | 3.1.0 |

### Remédiation appliquée

**Action** : Import du Jackson BOM 3.1.0 dans `<dependencyManagement>` du `pom.xml`

Spring Boot 4.0.3 importe `tools.jackson:jackson-bom:3.0.4` via son parent POM. L'entrée
`dependencyManagement` du projet enfant prend priorité sur celle du parent, ce qui permet
d'imposer une version différente du BOM Jackson.

**Approche initiale (abandonnée)** : forcer les 3 artefacts core individuellement
(`jackson-core`, `jackson-databind`, `jackson-annotations`). Cette approche a provoqué un
crash au démarrage :
```
NoClassDefFoundError: com/fasterxml/jackson/annotation/JsonSerializeAs
```
`jackson-databind:3.1.0` requiert `@JsonSerializeAs` (nouvelle dans `jackson-annotations:3.1.0`),
mais aussi une version cohérente de `jackson-dataformat-yaml` (utilisé par Spring Boot pour
parser `application.yml`), `jackson-datatype-jsr310`, `jackson-module-parameter-names`, etc.
Un mélange de versions entre modules Jackson est fatal au démarrage.

**Approche correcte** : importer le Jackson BOM complet qui aligne TOUS les modules à 3.1.0 :

```xml
<dependencyManagement>
  <dependencies>
    <!--
      Upgrade Jackson BOM 3.0.4 → 3.1.0.
      Le child POM prend priorité sur le BOM de spring-boot-starter-parent.
      Aligne tous les modules Jackson simultanément.
    -->
    <dependency>
      <groupId>tools.jackson</groupId>
      <artifactId>jackson-bom</artifactId>
      <version>3.1.0</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

**Fichier modifié** : `pom.xml` (section `<dependencyManagement>`)

### Validation

```bash
# Vérifier les versions résolues par Maven (tous les modules Jackson doivent être 3.1.0)
cd rhDemo && ./mvnw dependency:tree | grep tools.jackson

# Résultat attendu : TOUS les modules Jackson en 3.1.0
# tools.jackson.core:jackson-core:jar:3.1.0
# tools.jackson.core:jackson-databind:jar:3.1.0
# tools.jackson.core:jackson-annotations:jar:3.1.0
# tools.jackson.dataformat:jackson-dataformat-yaml:jar:3.1.0
# tools.jackson.datatype:jackson-datatype-jsr310:jar:3.1.0
# tools.jackson.module:jackson-module-parameter-names:jar:3.1.0

# Relancer le scan OWASP pour confirmer la disparition de l'alerte
./mvnw org.owasp:dependency-check-maven:check -DnvdApiKey=YOUR_KEY
```

### Condition de clôture

Retirer les entrées `dependencyManagement` pour Jackson lorsque Spring Boot intègre nativement Jackson >= 3.1.0 dans son BOM (mise à jour de `spring-boot-starter-parent`).

### Timeline

| Date | Action |
| --- | --- |
| 2026-03-14 | Détection par OWASP Dependency-Check dans le pipeline CI |
| 2026-03-14 | Forçage de jackson-core, jackson-databind, jackson-annotations à 3.1.0 via `dependencyManagement` |

---

## CVE-2026-32767 — nginx:1.29.5-alpine

### Détection

- **Date** : 2026-03-19
- **Outil** : Trivy Security Scanner
- **Sévérité** : À préciser (voir NVD)
- **Composant affecté** : `nginx:1.29.5-alpine`

### Description

CVE-2026-32767 affecte nginx en version 1.29.5. La version 1.29.6 contient le correctif.

### Images affectées

| Image | Version vulnérable | Version corrective | Statut |
| --- | --- | --- | --- |
| `nginx` | 1.29.5-alpine | 1.29.6-alpine | ✅ Corrigé |

### Remédiation appliquée

**Action** : Mise à jour vers `nginx:1.29.6-alpine`

**Fichiers modifiés** :

- `Jenkinsfile-CI` (variable `NGINX_IMAGE`)
- `infra/ephemere/docker-compose.yml` (valeur de repli `NGINX_IMAGE`)
- `docs/IMAGE_VERSIONS_MANAGEMENT.md`

**Digest 1.29.6-alpine** : `sha256:08fe94b0d1e72fc687840f5696f6e107a85c327b1bcb8a7acc22f8c100227c67`

**Note** : CVE-2026-22184 (zlib) reste présente dans 1.29.6 (Alpine 3.23.3 — `zlib-1.3.1-r2` non patché). L'exclusion `.trivyignore` correspondante est maintenue.

### Validation

```bash
# Scanner avec Trivy
trivy image --ignorefile rhDemo/.trivyignore --severity CRITICAL,HIGH nginx:1.29.6-alpine
```

### Timeline

| Date | Action |
| --- | --- |
| 2026-03-19 | Détection par Trivy dans le pipeline CI (nginx:1.29.5-alpine) |
| 2026-03-19 | Mise à jour nginx:1.29.5 → 1.29.6 |

### Références

- [NVD — CVE-2026-32767](https://nvd.nist.gov/vuln/detail/CVE-2026-32767)
- [nginx security advisories](https://nginx.org/en/security_advisories.html)

---

## CVE-2026-33186 — NGINX Gateway Fabric

### Détection

- **Date** : 2026-03-19
- **Outil** : Trivy Security Scanner
- **Sévérité** : À préciser (voir NVD)
- **Composant affecté** : `ghcr.io/nginx/nginx-gateway-fabric:2.4.0`

### Description

CVE-2026-33186 affecte NGINX Gateway Fabric en version 2.4.0. La version 2.4.2 contient le correctif.

### Images affectées

| Image | Version vulnérable | Version corrective | Statut |
| --- | --- | --- | --- |
| `ghcr.io/nginx/nginx-gateway-fabric` | 2.4.0 | 2.4.2 | ✅ Corrigé |

### Remédiation appliquée

**Action** : Mise à jour vers `nginx-gateway-fabric:2.4.2`

**Fichiers modifiés** :

- `Jenkinsfile-CI` (variable `NGF_IMAGE`)
- `infra/stagingkub/scripts/init-stagingkub.sh` (variables `NGF_VERSION` et `NGF_IMAGE_DIGEST`)
- `docs/IMAGE_VERSIONS_MANAGEMENT.md`
- `docs/NGINX_GATEWAY_FABRIC_MIGRATION.md`

**Digest 2.4.2** : `sha256:a30677fa38ec7a86ea6cdc40c6e51f6b6867bdab6ba40caeace8e33e5ff63255`

### Validation

```bash
# Vérifier la version après mise à jour du cluster
kubectl get deployment -n nginx-gateway -o jsonpath='{.items[0].spec.template.spec.containers[0].image}'

# Scanner avec Trivy
trivy image ghcr.io/nginx/nginx-gateway-fabric:2.4.2 --severity CRITICAL,HIGH
```

### Timeline

| Date | Action |
| --- | --- |
| 2026-03-19 | Détection par Trivy dans le pipeline CI (NGF 2.4.0) |
| 2026-03-19 | Mise à jour NGF 2.4.0 → 2.4.2 |

### Références

- [NVD — CVE-2026-33186](https://nvd.nist.gov/vuln/detail/CVE-2026-33186)
- [NGINX Gateway Fabric releases](https://github.com/nginx/nginx-gateway-fabric/releases)

---

## Template pour futures vulnérabilités

```markdown
## CVE-XXXX-XXXXX - Titre de la vulnérabilité

### Détection

- **Date** : AAAA-MM-JJ
- **Outil** : Trivy / OWASP / Autre
- **Sévérité** : CRITICAL / HIGH / MEDIUM

### Description

[Description de la vulnérabilité]

### Images affectées

[Liste des images et versions]

### Remédiation

[Action prise pour corriger]

### Validation

[Tests effectués]

### Références

[Liens vers CVE, advisories]
```

---

**Dernière mise à jour** : 2026-03-19 (CVE-2026-32767 nginx, CVE-2026-33186 NGF)
