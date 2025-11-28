# Scan Sécurité Images Docker avec Trivy

## Vue d'ensemble

Un stage de scan de sécurité Trivy a été ajouté au pipeline Jenkins pour détecter les vulnérabilités dans toutes les images Docker utilisées en staging.

## Images scannées

Le stage scanne automatiquement les 4 images Docker du stack staging :

1. **postgres:16-alpine** - Base de données (rhdemo-db et keycloak-db)
2. **quay.io/keycloak/keycloak:26.4.2** - Serveur d'authentification
3. **nginx:1.27.3-alpine3.21** - Reverse proxy HTTPS (Alpine 3.21 avec correctif libxml2)
4. **rhdemo-api:build-${BUILD_NUMBER}** - Application (image Paketo)

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

### Images tierces (postgres, keycloak, nginx)

Mettre à jour vers des versions patchées dans `infra/staging/docker-compose.yml` :

```yaml
services:
  rhdemo-db:
    image: postgres:16.2-alpine  # Version patchée
  
  keycloak:
    image: quay.io/keycloak/keycloak:26.5.0  # Version patchée
  
  nginx:
    image: nginx:1.27.1-alpine  # Version patchée
```

### Image applicative (rhdemo-api)

Les vulnérabilités dans l'image Paketo proviennent des dépendances Java ou des couches système :

**Dépendances Java** : Mettre à jour dans `pom.xml`
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
    <version>3.5.8</version>  <!-- Version patchée -->
</dependency>
```

**Couches système (buildpacks)** : Rebuilder l'image avec une version récente de Paketo

```bash
pack build rhdemo-api:latest --builder paketobuildpacks/builder-jammy-base:latest
```

## Intégration dans le pipeline

Le stage Trivy s'exécute :

1. **Après** le déploiement et la vérification de santé du stack
2. **Avant** les tests Selenium
3. **Position dans le pipeline** : Ligne 1068 du Jenkinsfile
4. **Condition d'exécution** : `params.DEPLOY_ENV != 'none'`

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

