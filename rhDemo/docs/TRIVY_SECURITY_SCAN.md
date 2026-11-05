---
statut: actif
verifie_le: 2026-10-23
sources:
  - rhDemo/Jenkinsfile-CI
  - rhDemo/.trivyignore.yaml
  - rhDemo/vars/rhDemoLib.groovy
---

# Scan Sécurité Images Docker avec Trivy

## Vue d'ensemble

Un stage de scan de sécurité Trivy (`Jenkinsfile-CI`) détecte les vulnérabilités
dans les images Docker du stack. Les scans tournent **en parallèle**, avec un
cache Trivy partagé (bases `vuln` + `java`) pré-alimenté en début de stage.

## Périmètre du scan

`Jenkinsfile-CI` ne scanne que **l'application et ce qui est livré avec elle** : les images de
l'environnement ephemere et celles du chart Helm `rhdemo`. Les composants système de stagingkub
(Cilium, NGINX Gateway Fabric, kube-prometheus-stack, Loki, Alloy, Grafana) n'y figurent pas : ils
ne sont pas livrés par ce pipeline, et un CVE dans l'un d'eux ne doit pas bloquer un commit
applicatif. Leurs images sont scannées par `Jenkinsfile-Renovate` avant le merge de chaque montée
de version, à partir du rendu de leur chart (cf.
[RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md), aiguillage, chemin 1). Raisons du choix :
[DECISIONS.md](DECISIONS.md).

## Images scannées

1. **postgres**, **keycloak**, **nginx** — variables `*_IMAGE` de `Jenkinsfile-CI`, exportées vers
   le Docker Compose d'ephemere
2. **rhdemo-app** — `RHDEMO_IMAGE` (application, construite par `docker build` sur `rhDemo/Dockerfile`, base Eclipse Temurin 25)
3. **images tierces du chart `rhdemo`** — lues dans `global.images` de
   `infra/stagingkub/helm/rhdemo/values.yaml` au moment du scan (aujourd'hui `busybox` et
   `postgres-exporter` en plus de postgres et keycloak). Une image identique à celle d'ephemere
   n'est pas scannée deux fois ; une référence divergente a son propre rapport suffixé `-stagingkub`.

Les noms de rapport doivent rester alignés sur `TRIVY_IMAGES` de `scripts/fixcve-detect.py`.

> Les valeurs exactes (versions + digests) vivent dans `Jenkinsfile-CI` et `values.yaml` ; ne pas
> les recopier ici, elles bougent à chaque PR Renovate.

## Critères de succès/échec

- ✅ **SUCCÈS** : Aucune vulnérabilité CRITICAL détectée
- ⚠️ **AVERTISSEMENT** : Vulnérabilités HIGH/MEDIUM détectées (non bloquantes)
- ❌ **ÉCHEC** : Une ou plusieurs vulnérabilités CRITICAL détectées

Le build Jenkins échouera si des vulnérabilités CRITICAL sont trouvées.

## Installation de Trivy

Trivy est pré-installé dans l'image Jenkins personnalisée via le Dockerfile :

```dockerfile
# INSTALLATION TRIVY (scanner de vulnérabilités pour images Docker)
RUN wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor -o /usr/share/keyrings/trivy.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb generic main" > /etc/apt/sources.list.d/trivy.list && \
    apt-get update && \
    apt-get install -y trivy && \
    rm -rf /var/lib/apt/lists/* && \
    trivy --version
```

**Fichier modifié** : `infra/jenkins-docker/Dockerfile.jenkins` (lignes 74-83)

## Rapports générés

Les rapports Trivy sont archivés à chaque build :

- **Format** : JSON
- **Emplacement** : `trivy-reports/*.json`
- **Archivés dans Jenkins** : Téléchargeables depuis la page du build

### Structure d'un rapport

```json
{
  "Results": [
    {
      "Target": "image_name",
      "Vulnerabilities": [
        {
          "VulnerabilityID": "CVE-2024-XXXXX",
          "PkgName": "package-name",
          "InstalledVersion": "1.0.0",
          "FixedVersion": "1.0.1",
          "Severity": "CRITICAL",
          "Description": "...",
          "References": ["https://..."]
        }
      ]
    }
  ]
}
```

## Analyser les rapports

### Compter les vulnérabilités par sévérité

```bash
# CRITICAL
jq '[.Results[]?.Vulnerabilities[]? | select(.Severity=="CRITICAL")] | length' trivy-reports/postgres.json

# HIGH
jq '[.Results[]?.Vulnerabilities[]? | select(.Severity=="HIGH")] | length' trivy-reports/keycloak.json

# Liste des CVE CRITICAL avec packages affectés
jq '.Results[]?.Vulnerabilities[]? | select(.Severity=="CRITICAL") | {CVE: .VulnerabilityID, Package: .PkgName, Installed: .InstalledVersion, Fixed: .FixedVersion}' trivy-reports/rhdemo-app.json
```

### Rapport consolidé

Le stage affiche automatiquement un rapport consolidé :

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 RAPPORT CONSOLIDÉ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
postgres             : CRITICAL=  0, HIGH=  5, MEDIUM= 12
keycloak             : CRITICAL=  0, HIGH=  8, MEDIUM= 23
nginx                : CRITICAL=  0, HIGH=  2, MEDIUM=  7
rhdemo-app           : CRITICAL=  0, HIGH=  3, MEDIUM= 15
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL                : CRITICAL=  0, HIGH= 18, MEDIUM= 57
```

## Corriger les vulnérabilités

### Images tierces (postgres, keycloak, nginx, busybox, postgres-exporter)

Elles sont pré-épinglées `tag@sha256:digest` dans les variables `*_IMAGE` de
`Jenkinsfile-CI` (et dans `global.images.*` des values Helm de stagingkub).
Renovate ouvre les PR de montée ; en remédiation manuelle, voir la skill
`/fixcve` (busybox et postgres-exporter sont détectés mais jamais remédiés automatiquement :
ils ne figurent pas dans `IMAGES` de `scripts/fixcve_lib/registry.py`). Le même tag+digest est réutilisé par `infra/ephemere/docker-compose.yml`
via ces variables d'environnement.

### Image applicative (rhdemo-app)

L'image est construite par `docker build` sur `rhDemo/Dockerfile` (base Eclipse
Temurin 25). Les vulnérabilités proviennent des dépendances Java ou de la couche
de base :

- **Dépendances Java** : montée de version dans `pom.xml` (souvent via une PR
  Renovate ou `/fixcve`) — cf. [OWASP_DEPENDENCY_CHECK.md](OWASP_DEPENDENCY_CHECK.md).
- **Couche de base** : bump de l'étiquette `eclipse-temurin` dans `rhDemo/Dockerfile`.

### CVE acceptées temporairement (`.trivyignore.yaml`)

Quand aucun correctif n'est publié en amont, une vulnérabilité peut être exclue du scan par une entrée de `rhDemo/.trivyignore.yaml` (champs `id`, `pkg-name`, `statement`). Le fichier est passé à Trivy par `--ignorefile` dans `vars/rhDemoLib.groovy`.

- Chaque entrée est justifiée dans [SECURITY_ADVISORIES.md](SECURITY_ADVISORIES.md) ; les acceptations sans correctif amont portent la mention `[PENDING_UPSTREAM_FIX]` et sont revérifiées à chaque cycle de `fixcve-auto` ([FIXCVE_AUTO.md](FIXCVE_AUTO.md)).
- Une acceptation n'est pas une correction : elle doit être retirée dès que le paquet corrigé est publié. Exemple en cours : CVE-2026-91403 sur l'image Keycloak (CVE-2026-114406, retirée le 2026-11-05 avec Keycloak 26.8.1), voir [SECURITE_CA_EMUDHRA_PLAN.md](SECURITE_CA_EMUDHRA_PLAN.md).

## Intégration dans le pipeline

Le stage Trivy (`Jenkinsfile-CI`) :

1. s'exécute **après** le build de l'image applicative et le déploiement du stack ephemere, **avant** les tests Selenium ;
2. pré-alimente le cache Trivy (`vuln` + `java`, volume `rhdemo-trivy-cache` de l'agent), contrôle sa fraîcheur (échec si la base `vuln` a plus de 72 h ou si la date `NextUpdate` de la Java DB est dépassée : un téléchargement en échec n'est sinon pas visible, les scans tournant en `--skip-db-update`), puis lance les 5 scans en `parallel` (`failFast: false`) ;
3. agrège les résultats (`aggregateTrivyResults`) et **échoue le build** dès une vulnérabilité `CRITICAL` ;
4. archive `trivy-reports/**` et publie un rapport HTML agrégé ;
5. est suivi d'un stage **SBOM CycloneDX** sur l'image applicative.

## Désactiver temporairement le scan

Si nécessaire pour débloquer un déploiement urgent :

**Option 1** : Commenter le stage dans le Jenkinsfile

```groovy
// stage('🔍 Scan Sécurité Images Docker (Trivy)') {
//     ...
// }
```

**Option 2** : Modifier le seuil d'échec (déconseillé)

```bash
if [ "$CRITICAL" -gt 10 ]; then  # Au lieu de -gt 0
    FAILED=true
fi
```

## Références

- [Documentation Trivy](https://aquasecurity.github.io/trivy/)
- [Base de données NVD (CVE)](https://nvd.nist.gov/)
- [CVSS Scoring](https://www.first.org/cvss/)

## Changelog

- **2025-11-27** : Ajout initial du stage Trivy au pipeline Jenkins
- **2026-08** : 5e image scannée (nginx-gateway-fabric) ; images tierces pré-épinglées `tag@sha256:digest` et suivies par Renovate ; image applicative construite via `docker build` (Dockerfile Temurin 25) et non plus Paketo ; ajout du cache Trivy partagé et du stage SBOM CycloneDX
- **2026-11** : périmètre recentré sur l'applicatif : nginx-gateway-fabric retiré (l'image scannée n'était pas celle déployée par le chart), busybox et postgres-exporter ajoutés depuis `values.yaml` ; composants système scannés par `Jenkinsfile-Renovate` à chaque montée de chart

## Historique des vulnérabilités détectées

### 2025-11-27 : CVE-2025-49794 & CVE-2025-49796 (libxml2)

**Première détection par Trivy** : Le stage a immédiatement détecté 2 vulnérabilités CRITICAL dans l'image Nginx.

**Diagnostic** :
- Image affectée : `nginx:1.27-alpine` (basée sur Alpine 3.20)
- Package vulnérable : `libxml2` (version < 2.13.6)
- CVE détectées : CVE-2025-49794 (use-after-free), CVE-2025-49796 (type confusion)
- Sévérité : CRITICAL (CVSS 9.1)

**Remédiation** :
- Action : Mise à jour vers `nginx:1.27.3-alpine3.21`
- Alpine 3.21 inclut libxml2 2.13.6 avec les correctifs
- Temps de remédiation : < 1 heure après détection

**Résultat** : ✅ 0 vulnérabilités CRITICAL après mise à jour

**Documentation détaillée** : Voir [SECURITY_ADVISORIES.md](SECURITY_ADVISORIES.md)

