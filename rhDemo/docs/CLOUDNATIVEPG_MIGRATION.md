# Migration vers CloudNativePG

## 📋 Vue d'ensemble

Ce guide décrit la migration des StatefulSets PostgreSQL actuels vers l'opérateur **CloudNativePG** pour bénéficier de :
- ✅ Sauvegardes automatiques avec rétention configurable
- ✅ Point-In-Time Recovery (PITR)
- ✅ Haute disponibilité (replicas automatiques)
- ✅ Pooling de connexions intégré (PgBouncer)
- ✅ Monitoring natif avec métriques Prometheus
- ✅ Gestion automatisée du cycle de vie

## 🎯 Architecture cible

```
┌────────────────────────────────────────────────────────────────┐
│ CloudNativePG Operator                                         │
│  ├─> Cluster postgresql-keycloak                              │
│  │    ├─ Primary Pod (RW)                                     │
│  │    ├─ Replica Pod (RO) [optionnel]                        │
│  │    ├─ PgBouncer (pooling)                                  │
│  │    └─ ScheduledBackup (quotidien)                         │
│  │        └─> PVC backups-keycloak/                          │
│  │                                                             │
│  └─> Cluster postgresql-rhdemo                                │
│       ├─ Primary Pod (RW)                                     │
│       ├─ Replica Pod (RO) [optionnel]                        │
│       ├─ PgBouncer (pooling)                                  │
│       └─ ScheduledBackup (quotidien)                         │
│            └─> PVC backups-rhdemo/                           │
└────────────────────────────────────────────────────────────────┘
```

## 📦 Prérequis

### 1. Persistance des données configurée

Avant de migrer, **assure-toi que les extraMounts KinD sont configurés** :

```bash
# Vérifier que kind-config.yaml contient extraMounts
cat /home/leno-vo/git/repository/rhDemo/infra/stagingkub/kind-config.yaml | grep -A 5 extraMounts

# Si le cluster existe déjà SANS extraMounts, il faut le recréer
kind delete cluster --name rhdemo
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./init-stagingkub.sh
```

### 2. Sauvegarder les données existantes

Avant toute migration, **sauvegarde manuelle obligatoire** :

```bash
# Sauvegarde PostgreSQL Keycloak
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  pg_dump -U keycloak keycloak > /tmp/keycloak-backup-$(date +%Y%m%d-%H%M%S).sql

# Sauvegarde PostgreSQL RHDemo
kubectl exec -n rhdemo-stagingkub postgresql-rhdemo-0 -- \
  pg_dump -U dbrhdemo dbrhdemo > /tmp/rhdemo-backup-$(date +%Y%m%d-%H%M%S).sql
```

## 🚀 Phase 1 : Installation de CloudNativePG Operator

### Étape 1.1 : Installer l'opérateur

```bash
# Ajouter le repository Helm CloudNativePG
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm repo update

# Créer le namespace pour l'opérateur
kubectl create namespace cnpg-system

# Installer l'opérateur CloudNativePG
helm install cnpg \
  --namespace cnpg-system \
  cnpg/cloudnative-pg \
  --set monitoring.enabled=true
```

### Étape 1.2 : Vérifier l'installation

```bash
# Vérifier que l'opérateur est Running
kubectl get pods -n cnpg-system

# Vérifier les CRDs créées
kubectl get crd | grep postgresql.cnpg.io

# Devrait afficher :
# - clusters.postgresql.cnpg.io
# - backups.postgresql.cnpg.io
# - scheduledbackups.postgresql.cnpg.io
# - poolers.postgresql.cnpg.io
```

## 🔄 Phase 2 : Migration PostgreSQL Keycloak

### Étape 2.1 : Créer le Cluster CloudNativePG pour Keycloak

Créer le fichier [infra/stagingkub/helm/rhdemo/templates/cnpg-cluster-keycloak.yaml](../infra/stagingkub/helm/rhdemo/templates/cnpg-cluster-keycloak.yaml) :

```yaml
{{- if .Values.keycloak.cloudnativepg.enabled }}
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgresql-keycloak
  namespace: {{ .Values.global.namespace }}
  labels:
    app: postgresql-keycloak
spec:
  # ⭐ 1 instance = pas de HA (recommandé pour staging)
  # Augmenter à 3 pour activer la haute disponibilité plus tard
  instances: {{ .Values.keycloak.cloudnativepg.instances }}

  imageName: ghcr.io/cloudnative-pg/postgresql:16

  storage:
    size: {{ .Values.keycloak.cloudnativepg.storage.size }}
    storageClass: {{ .Values.keycloak.cloudnativepg.storage.class }}

  bootstrap:
    initdb:
      database: keycloak
      owner: keycloak
      secret:
        name: {{ .Values.keycloak.database.passwordSecret.name }}

  monitoring:
    enablePodMonitor: true

  # Configuration PostgreSQL
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "256MB"
      effective_cache_size: "1GB"
      work_mem: "16MB"

  # Sauvegardes automatiques
  backup:
    barmanObjectStore:
      destinationPath: {{ .Values.keycloak.cloudnativepg.backup.destinationPath }}
      wal:
        compression: gzip
        maxParallel: 2
      data:
        compression: gzip
        immediateCheckpoint: true
    retentionPolicy: "{{ .Values.keycloak.cloudnativepg.backup.retentionPolicy }}"

  # PgBouncer pour pooling de connexions
  pooler:
    enabled: {{ .Values.keycloak.cloudnativepg.pooler.enabled }}
    instances: {{ .Values.keycloak.cloudnativepg.pooler.instances }}
    type: rw
    pgbouncer:
      poolMode: session
      parameters:
        max_client_conn: "1000"
        default_pool_size: "25"
{{- end }}
```

### Étape 2.2 : Créer le ScheduledBackup

Créer [infra/stagingkub/helm/rhdemo/templates/cnpg-scheduled-backup-keycloak.yaml](../infra/stagingkub/helm/rhdemo/templates/cnpg-scheduled-backup-keycloak.yaml) :

```yaml
{{- if .Values.keycloak.cloudnativepg.enabled }}
apiVersion: postgresql.cnpg.io/v1
kind: ScheduledBackup
metadata:
  name: postgresql-keycloak-backup
  namespace: {{ .Values.global.namespace }}
spec:
  schedule: "0 2 * * *"  # Tous les jours à 2h du matin
  backupOwnerReference: self
  cluster:
    name: postgresql-keycloak
  immediate: true  # Première sauvegarde immédiate après création
{{- end }}
```

### Étape 2.3 : Ajouter les valeurs dans values.yaml

Modifier [infra/stagingkub/helm/rhdemo/values.yaml](../infra/stagingkub/helm/rhdemo/values.yaml) :

```yaml
keycloak:
  # Désactiver l'ancien StatefulSet
  enabled: false  # ⚠️ À mettre à false après migration

  # Configuration CloudNativePG
  cloudnativepg:
    enabled: true
    instances: 1  # ⭐ 1 = SANS HA (recommandé staging), 3 = AVEC HA (prod)

    storage:
      size: 2Gi
      class: standard

    backup:
      # PVC local pour les backups
      destinationPath: s3://backups-keycloak
      retentionPolicy: "7d"  # Garder 7 jours de backups

    pooler:
      enabled: true
      instances: 1

  # Adapter le service pour pointer vers CloudNativePG
  database:
    host: postgresql-keycloak-rw  # Service créé par CloudNativePG
    port: 5432
    name: keycloak
    user: keycloak
    passwordSecret:
      name: postgresql-keycloak-secret
      key: password
```

### Étape 2.4 : Migrer les données

```bash
# 1. Scaler down Keycloak (éviter les écritures)
kubectl scale deployment keycloak -n rhdemo-stagingkub --replicas=0

# 2. Faire une dernière sauvegarde complète
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  pg_dump -U keycloak keycloak > /tmp/keycloak-final-backup.sql

# 3. Déployer le nouveau cluster CloudNativePG
helm upgrade rhdemo \
  /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/rhdemo \
  -n rhdemo-stagingkub \
  --set keycloak.enabled=false \
  --set keycloak.cloudnativepg.enabled=true

# 4. Attendre que le cluster soit prêt
kubectl wait --for=condition=ready cluster/postgresql-keycloak -n rhdemo-stagingkub --timeout=5m

# 5. Restaurer les données
kubectl exec -i -n rhdemo-stagingkub postgresql-keycloak-1 -- \
  psql -U keycloak keycloak < /tmp/keycloak-final-backup.sql

# 6. Redémarrer Keycloak avec la nouvelle config
kubectl scale deployment keycloak -n rhdemo-stagingkub --replicas=1

# 7. Vérifier la connexion
kubectl logs -n rhdemo-stagingkub deployment/keycloak --tail=50
```

### Étape 2.5 : Supprimer l'ancien StatefulSet

Une fois que tout fonctionne :

```bash
# Supprimer l'ancien StatefulSet (mais GARDER le PVC pour le moment)
kubectl delete statefulset postgresql-keycloak -n rhdemo-stagingkub

# Vérifier que le nouveau cluster fonctionne bien pendant 1-2 jours

# Ensuite, supprimer l'ancien PVC
kubectl delete pvc postgresql-data-postgresql-keycloak-0 -n rhdemo-stagingkub
```

## 🔄 Phase 3 : Migration PostgreSQL RHDemo

Répéter les mêmes étapes pour PostgreSQL RHDemo :

1. Créer `cnpg-cluster-rhdemo.yaml`
2. Créer `cnpg-scheduled-backup-rhdemo.yaml`
3. Ajouter `rhdemo.cloudnativepg` dans `values.yaml`
4. Scaler down l'application
5. Migrer les données
6. Vérifier et supprimer l'ancien StatefulSet

## 📊 Phase 4 : Configuration des backups

### Vérifier les backups automatiques

```bash
# Lister les backups Keycloak
kubectl get backup -n rhdemo-stagingkub -l cnpg.io/cluster=postgresql-keycloak

# Voir les détails d'un backup
kubectl describe backup <backup-name> -n rhdemo-stagingkub

# Voir le schedule
kubectl get scheduledbackup -n rhdemo-stagingkub
```

### Restauration manuelle d'un backup

```yaml
# restore-keycloak.yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgresql-keycloak-restored
  namespace: rhdemo-stagingkub
spec:
  instances: 1
  storage:
    size: 2Gi

  bootstrap:
    recovery:
      backup:
        name: <backup-name>  # Nom du backup à restaurer

      # Ou Point-In-Time Recovery
      # recoveryTarget:
      #   targetTime: "2026-01-10 14:00:00.000000+00"
```

## 🔍 Monitoring et maintenance

### Dashboards Grafana

CloudNativePG expose des métriques Prometheus qui peuvent être visualisées dans Grafana.

#### Dashboard dédié CloudNativePG

Un dashboard Grafana spécifique a été créé : [grafana-dashboard-cnpg.json](../infra/stagingkub/helm/observability/grafana-dashboard-cnpg.json)

**Panneaux inclus** :
- ✅ Status des clusters (UP/DOWN)
- ✅ Connexions actives par cluster
- ✅ Taille des bases de données
- ✅ Transactions (commits/rollbacks)
- ✅ Âge du dernier backup
- ✅ Fichiers WAL (Write-Ahead Log)
- ✅ Durée des backups

#### Déploiement du dashboard

Le dashboard sera automatiquement chargé par Grafana via ConfigMap :

```bash
# Le dashboard est déjà dans infra/stagingkub/helm/observability/
# Il sera chargé automatiquement au déploiement de la stack Loki

# Accès Grafana
# https://grafana.stagingkub.local (si configuré)
# ou port-forward :
kubectl port-forward -n loki-stack svc/loki-grafana 3000:80
# http://localhost:3000
```

### Métriques Prometheus

CloudNativePG expose automatiquement des métriques :

```bash
# Port-forward vers les métriques
kubectl port-forward -n rhdemo-stagingkub postgresql-keycloak-1 9187:9187

# Accéder aux métriques
curl http://localhost:9187/metrics
```

Métriques clés :
- `cnpg_pg_replication_lag` : Lag de réplication
- `cnpg_pg_database_size_bytes` : Taille de la base
- `cnpg_backends_waiting_total` : Connexions en attente

### Vérifier la santé du cluster

```bash
# Status général
kubectl get cluster -n rhdemo-stagingkub

# Logs du primary
kubectl logs -n rhdemo-stagingkub postgresql-keycloak-1 -f

# Exécuter des requêtes
kubectl exec -it -n rhdemo-stagingkub postgresql-keycloak-1 -- psql -U keycloak
```

## 🚨 Rollback en cas de problème

Si la migration échoue :

```bash
# 1. Supprimer le cluster CloudNativePG
helm upgrade rhdemo \
  /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/rhdemo \
  -n rhdemo-stagingkub \
  --set keycloak.cloudnativepg.enabled=false \
  --set keycloak.enabled=true

# 2. L'ancien StatefulSet sera recréé avec les données intactes (PVC toujours là)

# 3. Restaurer depuis le backup si nécessaire
kubectl exec -i -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  psql -U keycloak keycloak < /tmp/keycloak-final-backup.sql
```

## 📚 Ressources

- [CloudNativePG Documentation](https://cloudnative-pg.io/documentation/)
- [CloudNativePG Helm Chart](https://github.com/cloudnative-pg/charts)
- [PostgreSQL 16 Documentation](https://www.postgresql.org/docs/16/)

## ✅ Checklist de migration

### Pré-migration
- [ ] extraMounts KinD configurés et testés
- [ ] Backups manuels créés et vérifiés
- [ ] Documentation lue et comprise
- [ ] Cluster de test créé (optionnel)

### Migration Keycloak
- [ ] Opérateur CloudNativePG installé
- [ ] Manifests Helm créés
- [ ] Values.yaml configuré
- [ ] Application arrêtée (scaled to 0)
- [ ] Backup final créé
- [ ] Cluster CloudNativePG déployé
- [ ] Données restaurées
- [ ] Application redémarrée
- [ ] Tests fonctionnels OK
- [ ] Backups automatiques vérifiés

### Migration RHDemo
- [ ] Manifests Helm créés
- [ ] Values.yaml configuré
- [ ] Application arrêtée (scaled to 0)
- [ ] Backup final créé
- [ ] Cluster CloudNativePG déployé
- [ ] Données restaurées
- [ ] Application redémarrée
- [ ] Tests fonctionnels OK
- [ ] Backups automatiques vérifiés

### Post-migration
- [ ] Anciens StatefulSets supprimés
- [ ] Anciens PVC supprimés (après période de sécurité)
- [ ] Monitoring configuré (Prometheus/Grafana)
- [ ] Documentation mise à jour
- [ ] CLAUDE.md mis à jour

## 🎯 Bénéfices attendus

Après migration :
- ✅ **Zéro perte de données** même après redémarrage machine (extraMounts)
- ✅ **Backups automatiques** quotidiens avec rétention 7 jours
- ✅ **Point-In-Time Recovery** pour restaurer à n'importe quel moment
- ✅ **Haute disponibilité** (replicas) prêt pour activation (optionnel)
- ✅ **Pooling de connexions** (PgBouncer) pour meilleures performances
- ✅ **Monitoring intégré** avec métriques Prometheus + dashboards Grafana
- ✅ **Gestion simplifiée** : plus besoin de scripts custom

---

## 🔧 Configuration Haute Disponibilité (Optionnel)

### Mode Single Instance (Recommandé pour staging)

Par défaut, la configuration utilise **1 seule instance** :
- ✅ Consommation ressources réduite (~50%)
- ✅ Backups et PITR fonctionnels
- ✅ Monitoring complet
- ❌ Pas de basculement automatique si crash
- ❌ Pas de lecture distribuée

**Configuration** :
```yaml
instances: 1
```

### Mode Haute Disponibilité (Optionnel pour production)

Pour activer la HA, augmenter à **3 instances** :
- ✅ Basculement automatique en cas de crash du primary
- ✅ Lecture distribuée sur replicas
- ✅ Réplication synchrone
- ⚠️ Consommation ressources × 3

**Configuration** :
```yaml
instances: 3  # 1 primary + 2 replicas
```

**Architecture HA** :
```
┌────────────────────────────────────────────┐
│ postgresql-keycloak-1 (Primary - RW)      │
│  ├─> Réplication synchrone                │
│  ↓                                         │
│ postgresql-keycloak-2 (Replica - RO)      │
│                                            │
│ postgresql-keycloak-3 (Replica - RO)      │
└────────────────────────────────────────────┘
```

**Services créés** :
- `postgresql-keycloak-rw` → Primary (lecture/écriture)
- `postgresql-keycloak-ro` → Replicas (lecture seule)
- `postgresql-keycloak-r` → Tous (lecture)

### Activer la HA plus tard (sans migration)

CloudNativePG permet de passer de 1 à 3 instances **sans downtime** :

```bash
# Méthode 1 : Via kubectl patch
kubectl patch cluster postgresql-keycloak -n rhdemo-stagingkub \
  --type merge -p '{"spec":{"instances":3}}'

# Méthode 2 : Via Helm values.yaml
# Éditer values.yaml : instances: 3
helm upgrade rhdemo ./helm/rhdemo -n rhdemo-stagingkub

# CloudNativePG crée automatiquement les replicas
# et synchronise les données depuis le primary
```

**Vérifier la réplication** :
```bash
# Status du cluster
kubectl get cluster postgresql-keycloak -n rhdemo-stagingkub

# Vérifier les instances
kubectl get pods -n rhdemo-stagingkub -l cnpg.io/cluster=postgresql-keycloak

# Lag de réplication
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-1 -- \
  psql -U keycloak -c "SELECT application_name, state, sync_state, replay_lag FROM pg_stat_replication;"
```

### Comparaison modes

| Critère | Single (1 instance) | HA (3 instances) |
|---------|-------------------|------------------|
| **RAM** | ~512 MB | ~1.5 GB |
| **CPU** | 0.5 core | 1.5 cores |
| **Backups** | ✅ Oui | ✅ Oui |
| **PITR** | ✅ Oui | ✅ Oui |
| **Basculement auto** | ❌ Non | ✅ Oui (< 30s) |
| **Lecture distribuée** | ❌ Non | ✅ Oui |
| **Complexité** | Faible | Moyenne |
| **Recommandé pour** | Dev/Staging | Production |
