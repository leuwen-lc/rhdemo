# CloudNativePG - FAQ

## Questions fréquentes sur CloudNativePG pour rhDemo

---

## 🔧 Configuration et Architecture

### Q1 : Peut-on utiliser CloudNativePG SANS haute disponibilité ?

**Réponse : OUI, c'est même recommandé pour staging !**

CloudNativePG supporte très bien le mode **single instance** (1 seule base) :

```yaml
spec:
  instances: 1  # Pas de réplication = pas de HA
```

**Ce que tu gardes avec 1 instance** :
- ✅ Backups automatiques quotidiens
- ✅ Point-In-Time Recovery (PITR)
- ✅ PgBouncer (pooling de connexions)
- ✅ Monitoring Prometheus complet
- ✅ Gestion automatisée du cycle de vie
- ✅ Restauration depuis backup

**Ce que tu n'as pas avec 1 instance** :
- ❌ Basculement automatique si le pod crash
- ❌ Lecture distribuée sur plusieurs replicas

**Consommation ressources** :
- Single instance : ~512 MB RAM, 0.5 CPU
- HA (3 instances) : ~1.5 GB RAM, 1.5 CPU

**Configuration recommandée pour stagingkub** :
- **Keycloak** : 1 instance (les realms changent rarement)
- **RHDemo** : 1 instance (environnement de test)

### Q2 : Peut-on activer la HA plus tard ?

**Réponse : OUI, sans migration !**

Tu peux passer de 1 à 3 instances à tout moment :

```bash
# Éditer le Cluster
kubectl patch cluster postgresql-keycloak -n rhdemo-stagingkub \
  --type merge -p '{"spec":{"instances":3}}'

# CloudNativePG crée automatiquement 2 replicas
# et les synchronise avec le primary (sans downtime)
```

---

## 📊 Monitoring et Grafana

### Q3 : Peut-on intégrer CloudNativePG dans Grafana ?

**Réponse : OUI, complètement !**

CloudNativePG expose **plus de 50 métriques Prometheus** natives.

**Dashboard créé** : [grafana-dashboard-cnpg.json](../infra/stagingkub/helm/observability/grafana-dashboard-cnpg.json)

**Métriques disponibles** :
- `cnpg_pg_up` - Status du cluster (UP/DOWN)
- `cnpg_backends_total` - Connexions actives
- `cnpg_pg_database_size_bytes` - Taille des bases
- `cnpg_pg_stat_database_xact_commit` - Transactions committées
- `cnpg_pg_backup_last_available_timestamp` - Âge dernier backup
- `cnpg_pg_backup_duration_seconds` - Durée des backups
- `cnpg_pg_wal_files` - Fichiers WAL
- `cnpg_pg_replication_lag` - Lag réplication (si HA)

**Panneaux du dashboard** :
1. Status des clusters (gauges UP/DOWN)
2. Connexions actives par cluster
3. Taille des bases de données
4. Transactions (commits/rollbacks)
5. Âge du dernier backup (alertes si > 24h)
6. Fichiers WAL (Write-Ahead Log)
7. Durée des backups

**Intégration automatique** :
```yaml
# CloudNativePG crée automatiquement un PodMonitor
# Si Prometheus Operator est installé, les métriques
# sont scrapées automatiquement

apiVersion: postgresql.cnpg.io/v1
kind: Cluster
spec:
  monitoring:
    enablePodMonitor: true  # ⭐ Active le scraping auto
```

**Accès aux métriques** :
```bash
# Port-forward vers les métriques
kubectl port-forward -n rhdemo-stagingkub postgresql-keycloak-1 9187:9187

# Consulter les métriques
curl http://localhost:9187/metrics
```

### Q4 : Le dashboard sera-t-il chargé automatiquement dans Grafana ?

**Réponse : Oui, via ConfigMap !**

Le dashboard `grafana-dashboard-cnpg.json` peut être chargé automatiquement :

**Méthode 1 : Via sidecar (recommandé)** :
```yaml
# Dans le Helm chart Grafana (loki-stack)
grafana:
  sidecar:
    dashboards:
      enabled: true
      label: grafana_dashboard
      folder: /tmp/dashboards
      provider:
        folder: CloudNativePG
```

Créer une ConfigMap avec le dashboard :
```bash
kubectl create configmap grafana-dashboard-cnpg \
  --from-file=grafana-dashboard-cnpg.json \
  -n loki-stack \
  --dry-run=client -o yaml | kubectl label -f - grafana_dashboard=1 --local -o yaml | kubectl apply -f -
```

**Méthode 2 : Import manuel** :
1. Accéder à Grafana : http://localhost:3000
2. Menu : Dashboards → Import
3. Uploader `grafana-dashboard-cnpg.json`

---

## 💾 Backups et Restauration

### Q5 : Les backups fonctionnent-ils sans HA ?

**Réponse : OUI, totalement indépendant !**

Les backups automatiques **ne nécessitent pas la HA** :

```yaml
spec:
  instances: 1  # Single instance

  backup:
    barmanObjectStore:
      destinationPath: /backups/keycloak
      wal:
        compression: gzip
    retentionPolicy: "7d"
```

**Schedule automatique** :
```yaml
apiVersion: postgresql.cnpg.io/v1
kind: ScheduledBackup
metadata:
  name: postgresql-keycloak-backup
spec:
  schedule: "0 2 * * *"  # Tous les jours à 2h
  cluster:
    name: postgresql-keycloak
```

**Backups créés** :
- Base backup complet (quotidien)
- WAL archivés en continu (permet PITR)
- Compression gzip automatique
- Rétention 7 jours (configurable)

### Q6 : Comment restaurer depuis un backup ?

**Réponse : Via un nouveau Cluster** :

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgresql-keycloak-restored
spec:
  instances: 1

  bootstrap:
    recovery:
      backup:
        name: <backup-name>  # Nom du backup

      # Ou Point-In-Time Recovery
      recoveryTarget:
        targetTime: "2026-01-10 14:00:00+00"
```

---

## 🔄 Migration et Cohabitation

### Q7 : Peut-on garder les StatefulSets actuels pendant la migration ?

**Réponse : OUI, c'est la stratégie recommandée !**

**Migration progressive** :
1. Installer l'opérateur CloudNativePG (pas d'impact sur StatefulSets)
2. Créer le Cluster CloudNativePG Keycloak (coexiste)
3. Migrer les données de StatefulSet → CloudNativePG
4. Tester pendant 2-3 jours
5. Si OK : supprimer l'ancien StatefulSet
6. Répéter pour PostgreSQL RHDemo

**Rollback facile** :
```bash
# Supprimer le Cluster CloudNativePG
kubectl delete cluster postgresql-keycloak -n rhdemo-stagingkub

# L'ancien StatefulSet peut être recréé via Helm
helm upgrade rhdemo ./helm/rhdemo \
  --set keycloak.cloudnativepg.enabled=false \
  --set keycloak.enabled=true
```

---

## 🎯 Comparaisons

### Q8 : Quelle est la différence entre StatefulSet et CloudNativePG ?

| Critère | StatefulSet actuel | CloudNativePG |
|---------|-------------------|---------------|
| **Backups** | ❌ Manuels | ✅ Automatiques quotidiens |
| **PITR** | ❌ Non | ✅ Oui (restaurer à n'importe quel moment) |
| **HA** | ❌ Non | ⚠️ Optionnel (instances: 3) |
| **Pooling** | ❌ Non | ✅ PgBouncer intégré |
| **Monitoring** | ⚠️ Basique | ✅ 50+ métriques Prometheus |
| **Gestion** | 🔧 Scripts custom | ✅ Opérateur automatisé |
| **Complexité** | Faible | Moyenne |
| **Ressources (1 instance)** | ~400 MB | ~512 MB |

### Q9 : CloudNativePG vs Zalando Postgres Operator ?

| Critère | CloudNativePG | Zalando PG Operator |
|---------|--------------|---------------------|
| **Projet** | CNCF Sandbox | Zalando |
| **Maturité** | Récent (2021), très actif | Ancien (2016), mature |
| **Backups** | Barman intégré | pgBackRest ou WAL-G |
| **PITR** | ✅ Oui | ✅ Oui |
| **Pooling** | PgBouncer natif | Pooler séparé |
| **Configuration** | Plus simple | Plus verbeux |
| **Community** | Croissante | Établie |
| **Recommandé pour** | Nouveau projet | Migration existant |

**Pourquoi CloudNativePG pour rhDemo ?**
- ✅ Plus simple à configurer
- ✅ PgBouncer intégré
- ✅ Backups Barman natifs
- ✅ Projet CNCF (neutralité)
- ✅ Documentation excellente

---

## 🚀 Mise en production

### Q10 : CloudNativePG est-il prêt pour la production ?

**Réponse : OUI, utilisé en production par de grandes entreprises !**

**Adopteurs connus** :
- EDB (EnterpriseDB) - sponsor principal
- CNCF (projet Sandbox officiel)
- Nombreuses entreprises européennes

**Garanties** :
- ✅ Tests automatisés complets
- ✅ Releases régulières (tous les 3 mois)
- ✅ Support communautaire actif
- ✅ Documentation complète

**Version recommandée** :
- Utiliser la dernière version stable (actuellement 1.23+)
- Compatible PostgreSQL 12 → 16

**Configuration production type** :
```yaml
instances: 3  # HA activée
storage:
  size: 20Gi
  storageClass: fast-ssd  # SSD pour perfs
resources:
  requests:
    memory: 1Gi
    cpu: 500m
  limits:
    memory: 2Gi
    cpu: 2000m
backup:
  retentionPolicy: "30d"  # 30 jours en prod
pooler:
  instances: 3  # PgBouncer HA aussi
```

---

## 📚 Ressources

- [CloudNativePG Documentation](https://cloudnative-pg.io/documentation/)
- [CloudNativePG GitHub](https://github.com/cloudnative-pg/cloudnative-pg)
- [Helm Charts](https://github.com/cloudnative-pg/charts)
- [Guide Migration rhDemo](./CLOUDNATIVEPG_MIGRATION.md)
- [Dashboard Grafana](../infra/stagingkub/helm/observability/grafana-dashboard-cnpg.json)

---

## 🎯 Résumé pour rhDemo stagingkub

**Configuration recommandée** :
```yaml
keycloak:
  cloudnativepg:
    enabled: true
    instances: 1  # ⭐ SANS HA pour staging
    backup:
      retentionPolicy: "7d"
    pooler:
      enabled: true
      instances: 1

rhdemo:
  cloudnativepg:
    enabled: true
    instances: 1  # ⭐ SANS HA pour staging
    backup:
      retentionPolicy: "7d"
    pooler:
      enabled: true
      instances: 1
```

**Bénéfices pour stagingkub** :
- ✅ Persistance garantie (extraMounts + backups auto)
- ✅ Recovery rapide (PITR)
- ✅ Monitoring complet (Grafana)
- ✅ Gestion simplifiée (opérateur)
- ✅ Consommation raisonnable (~1 GB RAM total)
- ✅ HA activable plus tard si besoin

---

**Dernière mise à jour** : 2026-01-10
