# Gestion des Versions d'Images Docker

## Principe

Les versions des images Docker sont **définies une seule fois** dans `infra/staging/docker-compose.yml` et **lues automatiquement** par le Jenkinsfile pour le scan Trivy.

## Source de vérité unique

**Fichier de référence** : `infra/staging/docker-compose.yml`

```yaml
services:
  rhdemo-db:
    image: ${POSTGRES_IMAGE:-postgres:16-alpine}
  
  keycloak:
    image: ${KEYCLOAK_IMAGE:-quay.io/keycloak/keycloak:26.4.2}
  
  nginx:
    image: ${NGINX_IMAGE:-nginx:1.29.3-alpine}
  
  rhdemo-app:
    image: rhdemo-api:${APP_VERSION:-0.0.1-SNAPSHOT}
```

## Lecture automatique dans le Jenkinsfile

Le stage Trivy extrait automatiquement les versions avec `yq` :

```groovy
stage('🔍 Scan Sécurité Images Docker (Trivy)') {
    steps {
        sh '''
            # Aller dans le répertoire staging
            cd ${STAGING_INFRA_PATH}

            # Extraire les versions depuis docker-compose.yml
            POSTGRES_IMAGE=$(yq eval '.services.rhdemo-db.image' docker-compose.yml | sed 's/\${POSTGRES_IMAGE:-//' | sed 's/}//')
            KEYCLOAK_IMAGE=$(yq eval '.services.keycloak.image' docker-compose.yml | sed 's/\${KEYCLOAK_IMAGE:-//' | sed 's/}//')
            NGINX_IMAGE=$(yq eval '.services.nginx.image' docker-compose.yml | sed 's/\${NGINX_IMAGE:-//' | sed 's/}//')

            # Scanner les images
            scan_image "$POSTGRES_IMAGE" "postgres"
            scan_image "$KEYCLOAK_IMAGE" "keycloak"
            scan_image "$NGINX_IMAGE" "nginx"
        '''
    }
}
```

## Avantages

✅ **Source unique de vérité** : Les versions ne sont définies qu'une seule fois  
✅ **Maintenance facilitée** : Mise à jour dans un seul fichier (docker-compose.yml)  
✅ **Cohérence garantie** : Trivy scanne exactement les mêmes versions que celles déployées  
✅ **Pas de duplication** : Évite les erreurs de synchronisation entre fichiers  

## Comment mettre à jour une image

### 1. Modifier docker-compose.yml

```yaml
# Exemple : Mise à jour de Nginx
nginx:
  image: ${NGINX_IMAGE:-nginx:1.29.3-alpine}  # ← Modifier ici uniquement
```

### 2. Le Jenkinsfile s'adapte automatiquement

Le scan Trivy utilisera automatiquement la nouvelle version sans modification du Jenkinsfile.

### 3. Vérifier le scan

Dans les logs Jenkins, vous verrez :

```
📋 Lecture des versions depuis docker-compose.yml...
   PostgreSQL : postgres:16-alpine
   Keycloak   : quay.io/keycloak/keycloak:26.4.2
   Nginx      : nginx:1.29.3-alpine
   RHDemo App : rhdemo-api:build-196
```

## Format des images dans docker-compose.yml

### Avec variable d'environnement (recommandé)

Permet de surcharger via `.env` ou variables Jenkins :

```yaml
services:
  nginx:
    image: ${NGINX_IMAGE:-nginx:1.29.3-alpine}
    #      ^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^^^
    #      Variable env    Valeur par défaut
```

### Sans variable (direct)

```yaml
services:
  nginx:
    image: nginx:1.29.3-alpine
```

Le Jenkinsfile gère les deux formats grâce à `sed` qui nettoie les variables.

## Outils utilisés

- **`yq`** : Parser YAML pour extraire les valeurs
- **`sed`** : Nettoyer les variables `${VAR:-default}` pour obtenir la valeur par défaut
- **`bash`** : Orchestrer l'extraction et le scan

## Exemple complet de mise à jour

### Scénario : Corriger une CVE dans Nginx

1. **Identifier la version corrigée**
   ```bash
   # Via Trivy ou recherche CVE
   # Nginx 1.29.3-alpine corrige CVE-2025-XXXXX
   ```

2. **Modifier docker-compose.yml**
   ```yaml
   nginx:
     image: ${NGINX_IMAGE:-nginx:1.29.3-alpine}  # 1.27.3 → 1.29.3
   ```

3. **Commit et push**
   ```bash
   git add infra/staging/docker-compose.yml
   git commit -m "fix: upgrade nginx to 1.29.3-alpine (CVE-2025-XXXXX)"
   git push
   ```

4. **Lancer le build Jenkins**
   - Le stage Trivy lira automatiquement `nginx:1.29.3-alpine`
   - Vérifiera qu'il n'y a plus de CVE CRITICAL

5. **Vérifier les logs**
   ```
   📋 Lecture des versions depuis docker-compose.yml...
      Nginx      : nginx:1.29.3-alpine

   🔍 Scan: nginx:1.29.3-alpine
      ├─ CRITICAL:   0
      ├─ HIGH:       2
      └─ MEDIUM:     7
   
   ✅ SUCCÈS: Aucune vulnérabilité CRITICAL détectée
   ```

## Troubleshooting

### Problème : yq retourne une valeur vide

**Cause** : Le chemin YAML est incorrect

**Solution** : Vérifier le nom du service dans docker-compose.yml
```bash
yq eval '.services | keys' docker-compose.yml  # Liste tous les services
```

### Problème : Variable non substituée (`${VAR:-default}` apparaît tel quel)

**Cause** : Le `sed` ne nettoie pas correctement

**Solution** : Vérifier l'expression sed
```bash
echo '${NGINX_IMAGE:-nginx:1.29.3-alpine}' | sed 's/\${[^:]*:-//' | sed 's/}//'
# Résultat attendu : nginx:1.29.3-alpine
```

### Problème : Image scannée différente de celle déployée

**Cause** : Variables d'environnement surchargées ailleurs

**Solution** : Vérifier les exports dans le Jenkinsfile avant docker-compose up
```bash
export NGINX_IMAGE="nginx:custom-version"  # ← Peut écraser la valeur par défaut
```

## Références

- [yq documentation](https://mikefarah.gitbook.io/yq/)
- [Docker Compose variable substitution](https://docs.docker.com/compose/environment-variables/set-environment-variables/)
- [Trivy image scanning](https://aquasecurity.github.io/trivy/)

---

**Dernière mise à jour** : 2025-11-28
