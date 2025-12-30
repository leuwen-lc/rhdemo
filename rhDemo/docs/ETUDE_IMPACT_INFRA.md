# ÉTUDE D'IMPACT - INFRASTRUCTURE (Nginx, Keycloak, PostgreSQL)

**Date:** 30 décembre 2025
**Version:** 1.0
**Projet concerné:** rhDemo/infra (dev, ephemere, stagingkub)

---

## RÉSUMÉ EXÉCUTIF

Cette étude analyse l'impact des migrations suivantes sur l'infrastructure:

| Composant | Version Actuelle | Version Cible | Risque |
|-----------|------------------|---------------|--------|
| Nginx | 1.29.4-alpine | 1.28.1 | **BLOQUANT** |
| Keycloak | 26.4.2 | 26.4.7 | FAIBLE |
| PostgreSQL | 16-alpine | 18.1 | MOYEN |

**Verdict global:** Migration **PARTIELLEMENT RECOMMANDÉE** avec réserve critique sur Nginx.

### ⚠️ ALERTE CRITIQUE: NGINX 1.28.1

**La version cible Nginx 1.28.1 N'EXISTE PAS** selon la documentation officielle.

**Versions disponibles:**
- Version stable actuelle: **1.28.0** (23 avril 2025)
- Version mainline actuelle: **1.29.4** (version utilisée actuellement)

**RECOMMANDATION:** **NE PAS RÉTROGRADER**
- Rester sur `nginx:1.29.4-alpine` (version actuelle)
- OU migrer vers `nginx:1.28.0-alpine` si version stable requise

---

## 1. NGINX 1.29.4 → 1.28.1 (VERSION INTROUVABLE)

### 1.1 Problème Identifié

**Version demandée:** 1.28.1
**Statut:** ❌ **INTROUVABLE** dans les releases officielles Nginx

**Sources vérifiées:**
- https://nginx.org/en/CHANGES
- https://github.com/nginx/nginx/releases
- Docker Hub: nginx official images

### 1.2 Options Disponibles

#### Option A: Rester sur 1.29.4 (RECOMMANDÉ)
**Avantages:**
- Version actuelle stable et testée
- Aucune migration nécessaire
- Pas de risque de régression

**Inconvénients:**
- Version mainline (non LTS)

#### Option B: Migrer vers 1.28.0 (stable)
**Avantages:**
- Version stable LTS
- Support long terme

**Inconvénients:**
- Régression fonctionnelle possible
- Tests complets requis

### 1.3 Breaking Changes Nginx 1.28.0 (si migration)

**Aucun breaking change** entre 1.26 et 1.28 selon les release notes officielles.

### 1.4 Nouvelles Directives Nginx 1.28.0

Compatibles avec configuration existante:
- `ssl_object_cache_inheritable` (optimisation cache SSL)
- `ssl_certificate_cache` (cache certificats)
- `proxy_ssl_certificate_cache`, `grpc_ssl_certificate_cache`
- `keepalive_min_timeout`

### 1.5 Changements de Sécurité

- **TLSv1 et TLSv1.1:** Désactivés par défaut (déjà désactivés dans config actuelle)
- **Taille sessions SSL:** Augmentée à 8192

### 1.6 Configuration Actuelle

**Fichiers analysés:**

1. `/home/leno-vo/git/repository/rhDemo/infra/ephemere/nginx/nginx.conf`
2. `/home/leno-vo/git/repository/rhDemo/infra/ephemere/nginx/conf.d/rhdemo.conf`
3. `/home/leno-vo/git/repository/rhDemo/infra/ephemere/nginx/conf.d/keycloak.conf`

**Compatibilité:**

| Directive Actuelle | Nginx 1.28.0 | Nginx 1.29.4 | Commentaire |
|-------------------|--------------|--------------|-------------|
| `ssl_protocols TLSv1.2 TLSv1.3` | ✅ Compatible | ✅ Compatible | Pas de changement |
| `http2 on` | ✅ Compatible | ✅ Compatible | Syntaxe valide |
| `proxy_pass`, `upstream` | ✅ Compatible | ✅ Compatible | Pas de breaking change |
| Headers `add_header` | ✅ Compatible | ✅ Compatible | CSP stricte maintenue |

### 1.7 Content-Security-Policy

**RHDemo:** CSP stricte sans `unsafe-inline` (gérée par Spring Security)
**Keycloak:** CSP complétée dans `/nginx/conf.d/keycloak.conf`

**Compatibilité:** ✅ Aucun changement requis.

### 1.8 Fichiers à Modifier (si migration vers 1.28.0)

**Environnement EPHEMERE:**

`/home/leno-vo/git/repository/rhDemo/infra/ephemere/docker-compose.yml`

```yaml
# AVANT (ligne 147)
nginx:
  image: ${NGINX_IMAGE:-nginx:1.29.4-alpine}

# APRÈS (si migration vers 1.28.0)
nginx:
  image: ${NGINX_IMAGE:-nginx:1.28.0-alpine}
```

**Jenkinsfile-CI:**

`/home/leno-vo/git/repository/rhDemo/Jenkinsfile-CI`

```groovy
# AVANT (ligne 48)
NGINX_IMAGE = "nginx:1.29.4-alpine"

# APRÈS (si migration vers 1.28.0)
NGINX_IMAGE = "nginx:1.28.0-alpine"
```

**Environnement STAGINGKUB:**

Pas d'image Nginx custom - utilise Nginx Ingress Controller Kubernetes (version gérée par chart Helm).

### 1.9 Tests Requis (si migration)

- [ ] Configuration Nginx valide: `nginx -t`
- [ ] Redémarrage sans erreur: `docker logs -f rhdemo-ephemere-nginx`
- [ ] Accès HTTPS: `https://rhdemo.ephemere.local/`
- [ ] Reverse proxy Spring Boot: `/api/employes`
- [ ] Reverse proxy Keycloak: `https://keycloak.ephemere.local:58443/`
- [ ] Headers CSP présents: `curl -I https://rhdemo.ephemere.local/`
- [ ] Tests Selenium complets

### 1.10 RECOMMANDATION NGINX

**❌ NE PAS MIGRER vers 1.28.1** (version introuvable)

**✅ RESTER sur 1.29.4-alpine** (version actuelle stable)

**OU**

**✅ MIGRER vers 1.28.0-alpine** (si version stable LTS requise)

---

## 2. KEYCLOAK 26.4.2 → 26.4.7

### 2.1 Nature de la Mise à Jour

**Type:** Patch de sécurité (release mineure)
**Date de sortie:** 10 décembre 2025
**CVE corrigée:** [CVE-2025-13467](https://www.keycloak.org/2025/12/keycloak-2647-released)

### 2.2 Versions Actuelles

**Environnement DEV:**
`/home/leno-vo/git/repository/rhDemo/infra/dev/docker-compose.yml` (ligne 29)

**Environnement EPHEMERE:**
`/home/leno-vo/git/repository/rhDemo/infra/ephemere/docker-compose.yml` (ligne 50)

**Environnement STAGINGKUB:**
`/home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/rhdemo/values.yaml` (lignes 86-87)

```yaml
keycloak:
  image: quay.io/keycloak/keycloak:26.4.2
```

### 2.3 Breaking Changes

**Aucun breaking change critique** selon documentation officielle.

### 2.4 Changements Mineurs

#### Realm Representation
**Impact:** Liste des identity providers retirée de l'export.

**Action:** Tester l'export/import de realm après migration.

#### Admin Client Role
**Impact:** Rôle "admin" requiert désormais un utilisateur server admin.

**Action:** Vérifier permissions utilisateur admin Keycloak.

#### Cache Key Changes
**Impact:** Clé de cache des sessions modifiée.

**Action:** Ne pas déployer 26.4.x avec versions précédentes en cluster (pas applicable - déploiement mono-instance).

### 2.5 Impact sur rhDemoInitKeycloak

**Fichier:** `/home/leno-vo/git/repository/rhDemoInitKeycloak/pom.xml` (ligne 25)

```xml
<!-- AVANT -->
<keycloak.version>26.0.7</keycloak.version>

<!-- APRÈS -->
<keycloak.version>26.4.7</keycloak.version>
```

**Action requise:** Recompilation + tests.

```bash
cd /home/leno-vo/git/repository/rhDemoInitKeycloak
./mvnw clean package
```

**Tests requis:**
- [ ] Création realm RHDemo OK
- [ ] Création client OAuth2 "RHDemo" OK
- [ ] Création utilisateurs de test OK (admil, consuela, madjid)

### 2.6 Impact sur OAuth2/OIDC (Spring Security)

**Configuration OAuth2 actuelle:**

`/home/leno-vo/git/repository/rhDemo/src/main/resources/application-ephemere.yml`

```yaml
spring:
  security:
    oauth2:
      client:
        registration:
          keycloak:
            client-id: RHDemo
            client-secret: ${rhdemo.client.registration.keycloak.client.secret}
            authorization-grant-type: authorization_code
            scope: openid
        provider:
          keycloak:
            authorization-uri: https://keycloak.ephemere.local:58443/realms/RHDemo/...
            token-uri: http://keycloak-ephemere:8080/realms/RHDemo/...
            jwk-set-uri: http://keycloak-ephemere:8080/realms/RHDemo/.../certs
```

**Compatibilité:** ✅ **Configuration actuelle COMPATIBLE** avec Keycloak 26.4.7.

### 2.7 Migration Base de Données Keycloak

**Impact:** Keycloak 26.4.7 peut inclure changements schéma PostgreSQL.

**Procédure:**

1. **Sauvegarde obligatoire:**
```bash
# Environnement EPHEMERE
docker exec keycloak-ephemere-db pg_dump -U keycloak keycloak > keycloak_backup_$(date +%Y%m%d).sql

# Environnement STAGINGKUB
kubectl exec postgresql-keycloak-0 -n rhdemo-stagingkub -- \
  pg_dumpall -U keycloak > keycloak_stagingkub_backup_$(date +%Y%m%d).sql
```

2. **Migration automatique:** Keycloak applique migrations au démarrage (Liquibase intégré).

3. **Rollback:** Restaurer dump SQL en cas d'échec.

### 2.8 Fichiers à Modifier

**Environnement DEV:**

`/home/leno-vo/git/repository/rhDemo/infra/dev/docker-compose.yml`

```yaml
# AVANT (ligne 29)
keycloak-dev:
  image: quay.io/keycloak/keycloak:26.4.2

# APRÈS
keycloak-dev:
  image: quay.io/keycloak/keycloak:26.4.7
```

**Environnement EPHEMERE:**

`/home/leno-vo/git/repository/rhDemo/infra/ephemere/docker-compose.yml`

```yaml
# AVANT (ligne 50)
keycloak:
  image: ${KEYCLOAK_IMAGE:-quay.io/keycloak/keycloak:26.4.2}

# APRÈS
keycloak:
  image: ${KEYCLOAK_IMAGE:-quay.io/keycloak/keycloak:26.4.7}
```

**Jenkinsfile-CI:**

`/home/leno-vo/git/repository/rhDemo/Jenkinsfile-CI`

```groovy
# AVANT (ligne 50)
KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.4.2"

# APRÈS
KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.4.7"
```

**Environnement STAGINGKUB:**

`/home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/rhdemo/values.yaml`

```yaml
# AVANT (lignes 86-87)
keycloak:
  image:
    tag: "26.4.2"

# APRÈS
keycloak:
  image:
    tag: "26.4.7"
```

**rhDemoInitKeycloak:**

`/home/leno-vo/git/repository/rhDemoInitKeycloak/pom.xml`

```xml
<!-- AVANT (ligne 25) -->
<keycloak.version>26.0.7</keycloak.version>

<!-- APRÈS -->
<keycloak.version>26.4.7</keycloak.version>
```

### 2.9 Tests Requis

- [ ] Keycloak 26.4.7 démarre sans erreur
- [ ] Migration DB réussie (logs Liquibase)
- [ ] rhDemoInitKeycloak exécute sans erreur Admin API
- [ ] Login OAuth2 fonctionne (Spring Security)
- [ ] Logout OIDC complet
- [ ] Roles admin/consult/MAJ appliqués correctement
- [ ] Tests Selenium IHM complets

### 2.10 Procédure de Migration

#### Environnement EPHEMERE (Docker Compose)

```bash
# 1. Sauvegarde DB Keycloak
docker exec keycloak-ephemere-db pg_dump -U keycloak keycloak > keycloak_backup_$(date +%Y%m%d).sql

# 2. Mettre à jour docker-compose.yml et Jenkinsfile-CI

# 3. Redémarrer Keycloak
cd /home/leno-vo/git/repository/rhDemo/infra/ephemere
docker-compose up -d keycloak

# 4. Surveiller logs migration DB
docker logs -f keycloak-ephemere

# 5. Vérifier accès UI
# https://keycloak.ephemere.local:58443/

# 6. Tester rhDemoInitKeycloak
cd /home/leno-vo/git/repository/rhDemoInitKeycloak
./mvnw clean package
java -jar target/rhDemoInitKeycloak-1.0.0.jar
```

#### Environnement STAGINGKUB (Kubernetes)

```bash
# 1. Sauvegarde DB
kubectl exec postgresql-keycloak-0 -n rhdemo-stagingkub -- \
  pg_dumpall -U keycloak > keycloak_stagingkub_backup_$(date +%Y%m%d).sql

# 2. Mettre à jour values.yaml

# 3. Déployer Helm
helm upgrade rhdemo ./infra/stagingkub/helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --install

# 4. Surveiller rollout
kubectl rollout status deployment/keycloak -n rhdemo-stagingkub

# 5. Vérifier logs
kubectl logs -f deployment/keycloak -n rhdemo-stagingkub

# 6. Tester accès
# https://keycloak.stagingkub.local/
```

### 2.11 Rollback

```bash
# Environnement EPHEMERE
docker-compose stop keycloak keycloak-db
docker exec -i keycloak-ephemere-db psql -U keycloak -d keycloak < keycloak_backup_YYYYMMDD.sql
# Éditer docker-compose.yml → version 26.4.2
docker-compose up -d keycloak

# Environnement STAGINGKUB
kubectl exec -i postgresql-keycloak-0 -n rhdemo-stagingkub -- \
  psql -U keycloak < keycloak_stagingkub_backup_YYYYMMDD.sql
# Restaurer values.yaml → version 26.4.2
helm upgrade rhdemo ./infra/stagingkub/helm/rhdemo --namespace rhdemo-stagingkub
```

---

## 3. POSTGRESQL 16 → 18.1

### 3.1 Nature de la Mise à Jour

**Type:** Mise à jour majeure (2 versions majeures)
**Date de sortie PostgreSQL 18:** 25 septembre 2025
**Date de sortie PostgreSQL 18.1:** 13 novembre 2025

### 3.2 Versions Actuelles

**Environnement DEV:**
`/home/leno-vo/git/repository/rhDemo/infra/dev/docker-compose.yml` (ligne 6)

**Environnement EPHEMERE:**
`/home/leno-vo/git/repository/rhDemo/infra/ephemere/docker-compose.yml` (lignes 6 et 29)

**Environnement STAGINGKUB:**
`/home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/rhdemo/values.yaml` (lignes 15-16 et 50-52)

```yaml
image: postgres:16-alpine
```

### 3.3 Breaking Changes Critiques

#### Data Checksums par défaut

**Impact:** `initdb` active les checksums par défaut sur PostgreSQL 18.

**Problème:** Migration depuis PostgreSQL 16 sans checksums nécessite:
- Option `--no-data-checksums` OU
- Dump/restore (RECOMMANDÉ)

**Vérification checksums PostgreSQL 16:**

```bash
# Environnement EPHEMERE
docker exec rhdemo-ephemere-db pg_controldata | grep checksum
docker exec keycloak-ephemere-db pg_controldata | grep checksum

# Si "Data page checksum version: 0" → checksums désactivés
# → PostgreSQL 18 nécessite dump/restore
```

#### Time Zone Abbreviations

**Impact:** Priorité session > `timezone_abbreviations`.

**Risque:** FAIBLE (pas de TZ abbreviations custom détectées).

#### Generated Columns

**Impact:** Virtual generated columns par défaut.

**Risque:** FAIBLE (pas de colonnes générées dans schéma).

### 3.4 Compatibilité SQL

**Schéma rhDemo:** `pgschema.sql` (1 table `employes`, 5 index)

| Instruction | PostgreSQL 16 | PostgreSQL 18 | Statut |
|-------------|---------------|---------------|--------|
| `BIGSERIAL` | ✅ | ✅ | Compatible |
| `VARCHAR(n)` | ✅ | ✅ | Compatible |
| `CREATE INDEX` | ✅ | ✅ | Compatible |
| `CREATE UNIQUE INDEX` | ✅ | ✅ | Compatible |
| `INSERT INTO` | ✅ | ✅ | Compatible |

**Verdict:** Schéma et données **100% compatibles** sans modification.

### 3.5 Nouvelles Fonctionnalités

| Feature | Bénéfice |
|---------|----------|
| **Asynchronous I/O (AIO)** | Amélioration jusqu'à 3x pour scans séquentiels, VACUUM |
| **Skip Scan** | Optimisation index B-tree multi-colonnes |
| **Data Checksums** | Détection corruption données |
| **uuidv7()** | UUIDs ordonnés par timestamp |
| **OAuth Authentication** | Authentification PostgreSQL via OAuth (non nécessaire) |
| **Temporal Constraints** | Contraintes PK/FK/UNIQUE temporelles (non utilisé) |

### 3.6 Driver JDBC PostgreSQL

**Version actuelle:** Gérée par Spring Boot 3.5.8 (~42.7.x)

**Compatibilité:** PostgreSQL 8.4 → PostgreSQL 18+ ✅

**Action:** Aucune mise à jour driver nécessaire.

### 3.7 Procédure de Migration (Dump/Restore)

**Option recommandée:** Dump/Restore (compatible Docker Compose et Kubernetes).

#### Environnement EPHEMERE

```bash
# 1. Sauvegarde PostgreSQL 16
docker exec rhdemo-ephemere-db pg_dumpall -U rhdemo > rhdemo_pg16_backup_$(date +%Y%m%d).sql
docker exec keycloak-ephemere-db pg_dumpall -U keycloak > keycloak_pg16_backup_$(date +%Y%m%d).sql

# 2. Arrêter et supprimer volumes
cd /home/leno-vo/git/repository/rhDemo/infra/ephemere
docker-compose down -v

# 3. Mettre à jour docker-compose.yml
# Remplacer postgres:16-alpine par postgres:18.1-alpine

# 4. Démarrer PostgreSQL 18.1
docker-compose up -d rhdemo-db keycloak-db

# 5. Restaurer données
docker exec -i rhdemo-ephemere-db psql -U rhdemo < rhdemo_pg16_backup_$(date +%Y%m%d).sql
docker exec -i keycloak-ephemere-db psql -U keycloak < keycloak_pg16_backup_$(date +%Y%m%d).sql

# 6. Vérifier checksums
docker exec rhdemo-ephemere-db pg_controldata | grep checksum
# Attendu: "Data page checksum version: 1" (checksums activés)

# 7. Vérifier données
docker exec rhdemo-ephemere-db psql -U rhdemo -d rhdemo -c "SELECT COUNT(*) FROM employes;"
# Attendu: 304
```

#### Environnement STAGINGKUB

```bash
# 1. Sauvegarde PostgreSQL 16
kubectl exec postgresql-rhdemo-0 -n rhdemo-stagingkub -- \
  pg_dumpall -U rhdemo > rhdemo_stagingkub_pg16_backup_$(date +%Y%m%d).sql

kubectl exec postgresql-keycloak-0 -n rhdemo-stagingkub -- \
  pg_dumpall -U keycloak > keycloak_stagingkub_pg16_backup_$(date +%Y%m%d).sql

# 2. Supprimer StatefulSets et PVC PostgreSQL
kubectl delete statefulset postgresql-rhdemo postgresql-keycloak -n rhdemo-stagingkub
kubectl delete pvc data-postgresql-rhdemo-0 data-postgresql-keycloak-0 -n rhdemo-stagingkub

# 3. Mettre à jour values.yaml
# postgresql-rhdemo.image.tag: "18.1-alpine"
# postgresql-keycloak.image.tag: "18.1-alpine"

# 4. Déployer PostgreSQL 18.1
helm upgrade rhdemo ./infra/stagingkub/helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --install

# 5. Restaurer données
kubectl exec -i postgresql-rhdemo-0 -n rhdemo-stagingkub -- \
  psql -U rhdemo < rhdemo_stagingkub_pg16_backup_$(date +%Y%m%d).sql

kubectl exec -i postgresql-keycloak-0 -n rhdemo-stagingkub -- \
  psql -U keycloak < keycloak_stagingkub_pg16_backup_$(date +%Y%m%d).sql

# 6. Redémarrer applications
kubectl rollout restart deployment/keycloak -n rhdemo-stagingkub
kubectl rollout restart deployment/rhdemo-app -n rhdemo-stagingkub

# 7. Vérifier données
kubectl exec postgresql-rhdemo-0 -n rhdemo-stagingkub -- \
  psql -U rhdemo -d rhdemo -c "SELECT COUNT(*) FROM employes;"
# Attendu: 304
```

### 3.8 Fichiers à Modifier

**Environnement DEV:**

`/home/leno-vo/git/repository/rhDemo/infra/dev/docker-compose.yml`

```yaml
# AVANT (ligne 6)
rhdemo-db-dev:
  image: postgres:16-alpine

# APRÈS
rhdemo-db-dev:
  image: postgres:18.1-alpine
```

**Environnement EPHEMERE:**

`/home/leno-vo/git/repository/rhDemo/infra/ephemere/docker-compose.yml`

```yaml
# AVANT (lignes 6 et 29)
rhdemo-db:
  image: ${POSTGRES_IMAGE:-postgres:16-alpine}

keycloak-db:
  image: ${POSTGRES_IMAGE:-postgres:16-alpine}

# APRÈS
rhdemo-db:
  image: ${POSTGRES_IMAGE:-postgres:18.1-alpine}

keycloak-db:
  image: ${POSTGRES_IMAGE:-postgres:18.1-alpine}
```

**Jenkinsfile-CI:**

`/home/leno-vo/git/repository/rhDemo/Jenkinsfile-CI`

```groovy
# AVANT (ligne 49)
POSTGRES_IMAGE = "postgres:16-alpine"

# APRÈS
POSTGRES_IMAGE = "postgres:18.1-alpine"
```

**Environnement STAGINGKUB:**

`/home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/rhdemo/values.yaml`

```yaml
# AVANT (lignes 15-16)
postgresql-rhdemo:
  image:
    tag: "16-alpine"

# AVANT (lignes 50-52)
postgresql-keycloak:
  image:
    tag: "16-alpine"

# APRÈS
postgresql-rhdemo:
  image:
    tag: "18.1-alpine"

postgresql-keycloak:
  image:
    tag: "18.1-alpine"
```

### 3.9 Tests Requis

- [ ] Vérifier version: `SELECT version();`
- [ ] Vérifier checksums: `pg_controldata | grep checksum`
- [ ] Vérifier tables: `\dt`
- [ ] Compter employés: `SELECT COUNT(*) FROM employes;` (doit retourner 304)
- [ ] Tests d'intégration API complets
- [ ] Tests Selenium IHM complets
- [ ] Mesures performance I/O (avant/après)

### 3.10 Rollback

**ATTENTION:** Migration PostgreSQL 16 → 18 est **IRRÉVERSIBLE** (PostgreSQL 16 ne peut pas lire dumps PG 18).

**Stratégie:** Conserver dumps PostgreSQL 16 avant migration. En cas d'échec:

```bash
# Environnement EPHEMERE
docker-compose down -v
# Restaurer docker-compose.yml → postgres:16-alpine
docker-compose up -d rhdemo-db keycloak-db
docker exec -i rhdemo-ephemere-db psql -U rhdemo < rhdemo_pg16_backup_YYYYMMDD.sql
docker exec -i keycloak-ephemere-db psql -U keycloak < keycloak_pg16_backup_YYYYMMDD.sql

# Environnement STAGINGKUB
kubectl delete statefulset postgresql-rhdemo postgresql-keycloak -n rhdemo-stagingkub
# Restaurer values.yaml → tag: "16-alpine"
helm upgrade rhdemo ./infra/stagingkub/helm/rhdemo --namespace rhdemo-stagingkub
kubectl exec -i postgresql-rhdemo-0 -n rhdemo-stagingkub -- \
  psql -U rhdemo < rhdemo_stagingkub_pg16_backup_YYYYMMDD.sql
kubectl exec -i postgresql-keycloak-0 -n rhdemo-stagingkub -- \
  psql -U keycloak < keycloak_stagingkub_pg16_backup_YYYYMMDD.sql
```

---

## 4. ORDRE DE MIGRATION RECOMMANDÉ

### Phase 1: Préparation (30 minutes)

**Sauvegardes complètes:**

```bash
# Environnement EPHEMERE
docker exec rhdemo-ephemere-db pg_dumpall -U rhdemo > backup_rhdemo_pg16_$(date +%Y%m%d).sql
docker exec keycloak-ephemere-db pg_dumpall -U keycloak > backup_keycloak_pg16_$(date +%Y%m%d).sql

# Environnement STAGINGKUB
kubectl exec postgresql-rhdemo-0 -n rhdemo-stagingkub -- \
  pg_dumpall -U rhdemo > backup_rhdemo_stagingkub_pg16_$(date +%Y%m%d).sql
kubectl exec postgresql-keycloak-0 -n rhdemo-stagingkub -- \
  pg_dumpall -U keycloak > backup_keycloak_stagingkub_pg16_$(date +%Y%m%d).sql
```

**Test de restauration:**

```bash
docker run --rm -e POSTGRES_PASSWORD=test postgres:18.1-alpine
docker exec -i <container_id> psql -U postgres < backup_rhdemo_pg16_*.sql
# Vérifier: pas d'erreurs
```

**Vérifier checksums PostgreSQL 16:**

```bash
docker exec rhdemo-ephemere-db pg_controldata | grep checksum
# Si "Data page checksum version: 0" → checksums désactivés
# → PostgreSQL 18 nécessite dump/restore (PAS pg_upgrade)
```

### Phase 2: Migration Environnement DEV (15 minutes)

**Risque:** FAIBLE (environnement non critique)

1. Mettre à jour `/infra/dev/docker-compose.yml`
2. Recréer: `docker-compose down -v && docker-compose up -d`
3. Tests:
   - Démarrage PostgreSQL 18.1 OK
   - Démarrage Keycloak 26.4.7 OK
   - Connexion JDBC Spring Boot OK

4. Rollback si échec:
   - Restaurer versions précédentes dans docker-compose.yml
   - Recréer: `docker-compose down -v && docker-compose up -d`

### Phase 3: Migration rhDemoInitKeycloak (10 minutes)

1. Mettre à jour `/rhDemoInitKeycloak/pom.xml` (ligne 25)
2. Recompiler: `./mvnw clean package`
3. Tester en environnement DEV:
   ```bash
   java -jar target/rhDemoInitKeycloak-1.0.0.jar
   ```
4. Vérifier:
   - Création realm RHDemo OK
   - Création client OAuth2 "RHDemo" OK
   - Création utilisateurs OK

### Phase 4: Migration Environnement EPHEMERE (1 heure)

**Risque:** MOYEN (impact CI/CD)

**Composants à migrer:**
- ❌ Nginx: RESTER sur 1.29.4-alpine (1.28.1 introuvable)
- ✅ Keycloak: 26.4.2 → 26.4.7
- ✅ PostgreSQL: 16 → 18.1

1. Mettre à jour fichiers:
   - `infra/ephemere/docker-compose.yml`
   - `Jenkinsfile-CI` (lignes 48-50)

2. Commit et Push:
   ```bash
   git add infra/ephemere/docker-compose.yml Jenkinsfile-CI
   git commit -m "chore: upgrade PostgreSQL 16→18.1, Keycloak 26.4.2→26.4.7"
   git push
   ```

3. Exécuter pipeline Jenkins CI (build manuel de test)

4. Vérifier stages critiques:
   - Stage "Démarrage Environnement Ephemere" OK
   - Stage "Initialisation Keycloak" OK
   - Stage "Tests Selenium" OK
   - Stage "Scan Trivy" pas de CVE critiques

5. Rollback si échec:
   ```bash
   git revert <commit_hash>
   git push
   # Relancer pipeline
   ```

### Phase 5: Migration Environnement STAGINGKUB (1 heure)

**Risque:** MOYEN (environnement production-like)

**Fenêtre de maintenance requise.**

1. Mettre à jour `infra/stagingkub/helm/rhdemo/values.yaml`

2. Sauvegarde finale (déjà faite en Phase 1, vérifier fraîcheur)

3. Déploiement Helm avec destruction volumes PostgreSQL:
   ```bash
   kubectl delete statefulset postgresql-rhdemo postgresql-keycloak -n rhdemo-stagingkub
   kubectl delete pvc data-postgresql-rhdemo-0 data-postgresql-keycloak-0 -n rhdemo-stagingkub

   helm upgrade rhdemo ./infra/stagingkub/helm/rhdemo \
     --namespace rhdemo-stagingkub \
     --install
   ```

4. Restaurer données:
   ```bash
   kubectl exec -i postgresql-rhdemo-0 -n rhdemo-stagingkub -- \
     psql -U rhdemo < backup_rhdemo_stagingkub_pg16_*.sql
   kubectl exec -i postgresql-keycloak-0 -n rhdemo-stagingkub -- \
     psql -U keycloak < backup_keycloak_stagingkub_pg16_*.sql
   ```

5. Redémarrer pods:
   ```bash
   kubectl rollout restart deployment/keycloak -n rhdemo-stagingkub
   kubectl rollout restart deployment/rhdemo-app -n rhdemo-stagingkub
   ```

6. Tests de validation:
   - Connexion HTTPS: `https://rhdemo.stagingkub.local/`
   - Login Keycloak OK
   - API rhDemo: `/api/employes` retourne données
   - Actuator: `/actuator/health` → UP

---

## 5. MATRICE DE RISQUES

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **Nginx 1.28.1 introuvable** | **ÉLEVÉ** | **BLOQUANT** | **Rester sur 1.29.4 ou utiliser 1.28.0** |
| Keycloak Admin API incompatibilité | MOYEN | MOYEN | Tests rhDemoInitKeycloak obligatoires |
| PostgreSQL migration checksums échec | MOYEN | ÉLEVÉ | Dump/restore au lieu de pg_upgrade |
| PostgreSQL corruption données | FAIBLE | CRITIQUE | Sauvegardes + validation restauration |
| JDBC Driver incompatibilité | FAIBLE | MOYEN | Driver 42.7.8+ compatible PG 18 |
| OAuth2 Keycloak régression | FAIBLE | ÉLEVÉ | Tests Selenium IHM complets |

---

## 6. RECOMMANDATIONS FINALES

### 6.1 Verdict par Composant

| Composant | Action Recommandée | Priorité |
|-----------|-------------------|----------|
| **Nginx** | ❌ **NE PAS MIGRER vers 1.28.1** (introuvable) <br> ✅ **RESTER sur 1.29.4-alpine** | BLOQUANT |
| **Keycloak** | ✅ **MIGRER vers 26.4.7** (patch CVE-2025-13467) | HAUTE |
| **PostgreSQL** | ⚠️ **MIGRER vers 18.1 avec PRÉCAUTIONS** (dump/restore obligatoire) | MOYENNE |

### 6.2 Plan de Migration Recommandé

**Scénario Recommandé:**

```
Nginx: INCHANGÉ (rester sur 1.29.4)
Keycloak: 26.4.2 → 26.4.7
PostgreSQL: 16 → 18.1 (dump/restore)
```

**Avantages:**
- Corrige CVE-2025-13467 (Keycloak)
- Bénéficie de PostgreSQL 18 AIO (performance)
- Minimise risques (pas de changement Nginx)

**Inconvénient:**
- Migration PostgreSQL 16→18 irréversible

### 6.3 Actions Critiques Avant Migration

**Obligatoires:**

1. ✅ Sauvegardes complètes de toutes les bases PostgreSQL
2. ✅ Test de restauration des sauvegardes sur PostgreSQL 18.1
3. ✅ Vérifier checksums PostgreSQL 16 (`pg_controldata`)
4. ✅ Tester rhDemoInitKeycloak avec Keycloak 26.4.7 en environnement DEV
5. ✅ Exécuter pipeline Jenkins CI complet après modification Jenkinsfile-CI

**Recommandées:**

6. 🔹 Créer branche Git `feature/upgrade-postgres18-keycloak26.4.7`
7. 🔹 Tester en environnement DEV pendant 48h avant migration stagingkub
8. 🔹 Planifier fenêtre de maintenance stagingkub (1h, hors heures ouvrées)
9. 🔹 Documenter procédure de rollback dans runbook
10. 🔹 Surveiller logs PostgreSQL 18 post-migration

### 6.4 Calendrier Suggéré

**Semaine 1:**
- Jour 1: Sauvegardes + Tests restauration
- Jour 2-3: Migration environnement DEV + tests rhDemoInitKeycloak
- Jour 4-5: Validation 48h environnement DEV

**Semaine 2:**
- Jour 1: Migration environnement EPHEMERE (CI/CD)
- Jour 2-3: Exécution pipeline Jenkins + validation tests Selenium
- Jour 4-5: Monitoring stabilité

**Semaine 3:**
- Jour 1: **FENÊTRE MAINTENANCE**: Migration stagingkub (soirée/weekend)
- Jour 2-5: Monitoring production-like + rollback si nécessaire

---

## 7. CHECKLIST DE DÉPLOIEMENT

### Avant Migration

- [ ] Backups PostgreSQL complets (ephemere + stagingkub)
- [ ] Test restauration sauvegardes sur PG 18.1
- [ ] Vérification checksums PostgreSQL 16
- [ ] Branche Git créée (`feature/upgrade-postgres18-keycloak26.4.7`)
- [ ] Fenêtre maintenance planifiée (stagingkub)

### Pendant Migration

- [ ] Mise à jour environnement DEV OK
- [ ] Tests rhDemoInitKeycloak + Keycloak 26.4.7 OK
- [ ] Mise à jour Jenkinsfile-CI + ephemere docker-compose.yml
- [ ] Pipeline Jenkins CI exécuté avec succès
- [ ] Tests Selenium passent
- [ ] Mise à jour values.yaml stagingkub
- [ ] Déploiement Helm stagingkub OK
- [ ] Restauration données PostgreSQL OK

### Après Migration

- [ ] Validation PostgreSQL 18.1 (version, checksums, données)
- [ ] Validation Keycloak 26.4.7 (version, login OAuth2)
- [ ] Validation rhDemo (API, actuator/health)
- [ ] Monitoring 48h sans erreurs
- [ ] Documentation mise à jour
- [ ] Sauvegardes post-migration créées

### Si Échec

- [ ] Rollback environnement impacté
- [ ] Restauration depuis sauvegardes PostgreSQL 16
- [ ] Validation rollback (tests smoke)
- [ ] Investigation logs d'erreurs
- [ ] Documentation incident

---

## 8. SOURCES

### Nginx
- [Nginx 1.28.0 Changelog](https://nginx.org/en/CHANGES-1.28)
- [Nginx Official Releases](https://github.com/nginx/nginx/releases)
- [Nginx Ingress Controller Releases](https://docs.nginx.com/nginx-ingress-controller/releases/)

### Keycloak
- [Keycloak 26.4.7 Release](https://www.keycloak.org/2025/12/keycloak-2647-released)
- [Keycloak Upgrading Guide](https://www.keycloak.org/docs/latest/upgrading/index.html)
- [Red Hat Keycloak 26.4 Migration Guide](https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.4/pdf/migration_guide/Red_Hat_build_of_Keycloak-26.4-MIGRATION_GUIDE-en-US.pdf)

### PostgreSQL
- [PostgreSQL 18 Release Notes](https://www.postgresql.org/docs/current/release-18.html)
- [PostgreSQL 18.1 Release](https://www.postgresql.org/docs/current/release-18-1.html)
- [PostgreSQL Upgrading Guide](https://www.postgresql.org/docs/current/upgrading.html)
- [PostgreSQL JDBC Driver](https://jdbc.postgresql.org/)

---

**Fin du document**
