# Changelog - Configuration OWASP Dependency-Check

## Date : 26 novembre 2025

### Contexte

Migration de l'analyse OWASP Dependency-Check du **plugin Maven** vers le **plugin Jenkins** pour résoudre l'incompatibilité CVSS v4.0.

**Problème résolu** : `IllegalArgumentException: SAFETY` - Le plugin Maven ne pouvait pas parser les nouvelles énumérations CVSS v4.0 du NVD.

---

## Modifications apportées

### 1. Plugin déjà installé

✅ Le plugin `dependency-check-jenkins-plugin` était déjà présent dans [plugins.txt](plugins.txt#L50).

**Aucune modification requise dans plugins.txt.**

---

### 2. Configuration JCasC mise à jour

**Fichier** : [jenkins-casc.yaml](jenkins-casc.yaml)

**Ajout de l'outil OWASP Dependency-Check** (lignes 73-81) :

```yaml
# OWASP Dependency-Check
dependencyCheck:
  installations:
    - name: "dependency-check-9.2.0"
      properties:
        - installSource:
            installers:
              - dependencyCheckInstaller:
                  id: "9.2.0"
```

**Ajout documentation credential NVD API** (lignes 121-126) :

```yaml
# 7. nvd-api-key (Secret text - recommandé pour OWASP Dependency-Check)
#    - Type: Secret text
#    - ID: nvd-api-key
#    - Secret: ${NVD_API_KEY}
#    - Description: NVD API Key for OWASP Dependency-Check
#    - Obtenir une clé sur: https://nvd.nist.gov/developers/request-an-api-key
```

---

### 3. Variables d'environnement

**Fichier** : [.env.example](.env.example)

**Ajout** (lignes 40-46) :

```env
# ────────────────────────────────────────────────────────────────
# OWASP DEPENDENCY-CHECK
# ────────────────────────────────────────────────────────────────
# NVD API Key pour éviter les limitations de taux
# Obtenir une clé sur: https://nvd.nist.gov/developers/request-an-api-key
# Format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NVD_API_KEY=your-nvd-api-key
```

---

### 4. Documentation mise à jour

**Fichier** : [README.md](README.md)

#### Modifications :

1. **Architecture diagram** (ligne 51) :
   - Ajout : `• OWASP Dep-Check` dans la liste des plugins

2. **Table des volumes** (ligne 86) :
   - Ajout : `rhdemo-jenkins-home/dependency-check-data` | Cache NVD OWASP | ~2-3 GB

3. **Section "Variables importantes"** (lignes 170-173) :
   ```env
   # OWASP Dependency-Check (recommandé)
   NVD_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   # Obtenir sur: https://nvd.nist.gov/developers/request-an-api-key
   ```

4. **JCasC description** (ligne 179) :
   - Mise à jour : `Outils (JDK21, Maven3, Git, OWASP Dependency-Check)`

5. **Section Plugins / Sécurité** (lignes 263-266) :
   ```markdown
   ### Sécurité
   - OWASP Dependency-Check Jenkins Plugin
     - Outil configuré : dependency-check-9.2.0
     - Support CVSS v4.0
     - Cache NVD partagé entre builds
   ```

6. **Nouvelle section "OWASP Dependency-Check"** (lignes 388-438) :
   - Configuration automatique
   - Procédure d'obtention clé API NVD
   - Instructions pour créer le credential Jenkins
   - Comparaison avec/sans clé API
   - Lien vers documentation complète

---

### 5. Script de configuration créé

**Fichier** : [configure-nvd-key.sh](configure-nvd-key.sh) (nouveau)

**Description** : Script interactif pour configurer la clé API NVD dans `.env`.

**Usage** :
```bash
./configure-nvd-key.sh
```

**Fonctionnalités** :
- ✅ Détection automatique du fichier `.env`
- ✅ Validation basique du format de clé
- ✅ Mise à jour ou ajout de `NVD_API_KEY`
- ✅ Instructions pour obtenir une clé
- ✅ Option d'ouverture automatique du formulaire NVD

---

### 6. Guide de démarrage rapide mis à jour

**Fichier** : [QUICKSTART.md](QUICKSTART.md)

**Ajout** (lignes 45-50) :

```env
# Recommandé (pour OWASP Dependency-Check)
NVD_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# Obtenir sur: https://nvd.nist.gov/developers/request-an-api-key
```

**💡 Astuce** : Utilisez `./configure-nvd-key.sh` pour configurer facilement la clé API NVD.

---

## Résumé des fichiers modifiés

| Fichier | Type de modification | Lignes modifiées |
|---------|---------------------|------------------|
| `plugins.txt` | ✅ Aucune (déjà présent) | - |
| `jenkins-casc.yaml` | ✏️ Modification | 73-81, 121-126 |
| `.env.example` | ✏️ Modification | 40-46 |
| `README.md` | ✏️ Modification | 51, 86, 170-173, 179, 263-266, 388-438 |
| `QUICKSTART.md` | ✏️ Modification | 45-50 |
| `configure-nvd-key.sh` | ➕ Nouveau fichier | - |
| `CHANGELOG_OWASP.md` | ➕ Nouveau fichier | - |

---

## Actions requises après déploiement

### Pour l'administrateur Jenkins

1. **Obtenir une clé API NVD** (recommandé) :
   - Aller sur https://nvd.nist.gov/developers/request-an-api-key
   - Remplir le formulaire avec email professionnel
   - Confirmer par email
   - Recevoir la clé API

2. **Configurer la clé dans `.env`** :
   ```bash
   # Option 1 : Script interactif
   ./configure-nvd-key.sh

   # Option 2 : Manuellement
   nano .env
   # Ajouter : NVD_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```

3. **Créer le credential dans Jenkins** :
   - **Manage Jenkins** → **Manage Credentials**
   - **Add Credentials** → **Secret text**
   - **ID** : `nvd-api-key`
   - **Secret** : Coller la clé API NVD
   - **Description** : `NVD API Key for OWASP Dependency-Check`

4. **Redémarrer Jenkins** :
   ```bash
   docker-compose restart jenkins
   ```

5. **Vérifier la configuration** :
   - **Manage Jenkins** → **Global Tool Configuration**
   - Section **Dependency-Check**
   - Vérifier que `dependency-check-9.2.0` est présent

### Pour les développeurs

✅ Aucune action requise - la configuration est transparente.

Le Jenkinsfile a été mis à jour pour utiliser automatiquement le plugin Jenkins au lieu du plugin Maven.

---

## Avantages de cette migration

| Aspect | Plugin Maven | Plugin Jenkins |
|--------|--------------|----------------|
| **Compatibilité CVSS v4.0** | ❌ Erreurs | ✅ Compatible |
| **Cache NVD** | Par build (~2-3 GB à chaque fois) | Partagé (téléchargement unique) |
| **Rapports** | HTML statique | UI Jenkins + graphiques |
| **Seuils** | `failBuildOnCVSS` uniquement | Granulaires (Critical/High/Medium/Low) |
| **Performance** | Téléchargement NVD répétitif | Mise à jour contrôlée (24h) |

---

## Documentation de référence

- **Guide complet plugin Jenkins** : [../../docs/OWASP_JENKINS_PLUGIN.md](../../docs/OWASP_JENKINS_PLUGIN.md)
- **Guide installation admin** : [../../docs/JENKINS_OWASP_SETUP.md](../../docs/JENKINS_OWASP_SETUP.md)
- **Guide migration** : [../../docs/OWASP_MIGRATION_JENKINS_PLUGIN.md](../../docs/OWASP_MIGRATION_JENKINS_PLUGIN.md)
- **Jenkinsfile modifié** : [../../Jenkinsfile](../../Jenkinsfile) (stage ligne 422-460)

---

## Notes de version

**Version Jenkins requise** : 2.361.4+
**Version plugin** : `dependency-check-jenkins-plugin:latest`
**Version outil** : `dependency-check-9.2.0`
**Compatibilité** : CVSS v4.0 ✅

---

**Date de mise en production** : 26 novembre 2025
**Auteur** : Migration automatisée vers plugin Jenkins
**Impact** : Transparent pour les développeurs, configuration requise pour admin Jenkins
