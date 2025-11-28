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
- `infra/staging/docker-compose.yml` (ligne 148)
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

**Dernière mise à jour** : 2025-11-27
