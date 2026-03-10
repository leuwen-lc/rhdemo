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
|-------|-------------------|--------|
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
|------|--------|
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



## 2025-11-28 : Nouvelles CVE CRITICAL détectées dans nginx:1.27.3-alpine3.21

### Détection supplémentaire
- **Date** : 2025-11-28
- **Contexte** : Après migration vers nginx:1.27.3-alpine3.21, Trivy détecte encore 2 CVE CRITICAL

**Résultats du scan** :
```
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
|------|--------|
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

**Risque réel : NUL (faux positif fonctionnel)**

`gosu` est un utilitaire de type `setuid+setgid+exec` dont le rôle unique est de changer d'utilisateur Unix puis d'exécuter une commande. Il **n'effectue aucune connexion réseau** et **n'utilise jamais** le package `crypto/tls` à l'exécution. Le code vulnérable est inclus dans le binaire Go par le compilateur mais n'est jamais appelé.

Cette position est confirmée par :
- Le mainteneur de gosu via [`govulncheck`](https://github.com/tianon/gosu/issues/144) qui vérifie que les chemins de code vulnérables ne sont pas atteignables
- La discussion upstream [docker-library/postgres#1324](https://github.com/docker-library/postgres/issues/1324)

### Images affectées

| Image | Composant | Status |
|-------|-----------|--------|
| postgres:18-alpine | gosu 1.19 (Go 1.24.6) | ⚠️ CVE présente mais non exploitable |
| rhdemo-api | N/A | ✅ Non affecté |
| nginx | N/A | ✅ Non affecté |
| keycloak | N/A | ✅ Non affecté |

### Remédiation appliquée

**Action** : Exclusion de la CVE dans Trivy via `.trivyignore` (risque accepté - faux positif fonctionnel)

**Fichier créé** : `rhDemo/.trivyignore`
```
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


## CVE-2026-24400

### Détection
- **Date** : 2026-03-10
- **Outil** : OWASP
- **Sévérité** : HIGH 

### Description : Starting in version 1.4.0 and prior to version 3.27.7, an XML External Entity (XXE) vulnerability exists in `org.assertj.core.util.xml.XmlStringPrettyFormatter`: the `toXmlDocument(String)` method initializes `DocumentBuilderFactory` with default settings, without disabling DTDs or external entities. 

### Images affectées
POM uniquement

### Remédiation
Passage à la version Spring Boot 4.03


## CVE-2026-0540

### Détection
- **Date** : 2026-03-10
- **Outil** : OWASP
- **Sévérité** : MEDIUM (faux positif) ?

### Description : DOMPurify 3.1.3 through 3.3.1 and 2.5.3 through 2.5.8, fixed in commit 729097f, contain a cross-site scripting vulnerability that allows attackers to bypass attribute sanitization by exploiting five missing rawtext elements (noscript, xmp, noembed, noframes, iframe) in the SAFE_FOR_XML regex.

### Images affectées
POM uniquement

### Remédiation
Passage à la version srpingdoc-openapi 3.0.1

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

**Dernière mise à jour** : 2026-03-10

---
