---
statut: actif
verifie_le: 2026-10-22
sources:
  - rhDemo/infra/stagingkub/helm/rhdemo/templates/postgresql-backup-cronjob.yaml
  - rhDemo/infra/stagingkub/helm/rhdemo/values.yaml
  - rhDemo/infra/stagingkub/kind-config.yaml
---

# Backups PostgreSQL avec CronJobs

## 📋 Vue d'ensemble

Le projet utilise des **CronJobs Kubernetes** pour sauvegarder automatiquement les bases de données PostgreSQL (RHDemo et Keycloak) avec rétention configurable.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Namespace: rhdemo-stagingkub            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐        ┌──────────────────┐         │
│  │ StatefulSet      │        │ StatefulSet      │         │
│  │ postgresql-rhdemo│        │postgresql-keycloak│        │
│  │                  │        │                  │         │
│  │ PVC: 2Gi        │        │ PVC: 2Gi        │         │
│  └────────┬─────────┘        └────────┬─────────┘         │
│           │                           │                    │
│           │ pg_dump                   │ pg_dump            │
│           │                           │                    │
│  ┌────────▼─────────┐        ┌────────▼─────────┐         │
│  │ CronJob          │        │ CronJob          │         │
│  │ postgresql-      │        │ postgresql-      │         │
│  │ rhdemo-backup    │        │ keycloak-backup  │         │
│  │                  │        │                  │         │
│  │ Schedule:        │        │ Schedule:        │         │
│  │ 0 2 * * *        │        │ 0 3 * * *        │         │
│  │ (2h du matin)    │        │ (3h du matin)    │         │
│  └────────┬─────────┘        └────────┬─────────┘         │
│           │                           │                    │
│           ▼                           ▼                    │
│  ┌─────────────────────────────────────────────┐          │
│  │         hostPath (extraMounts KinD)         │          │
│  │ /home/leno-vo/kind-data/rhdemo-stagingkub/ │          │
│  │                                             │          │
│  │  ├── backups/                               │          │
│  │  │   ├── rhdemo/                            │          │
│  │  │   │   ├── rhdemo_20260114_020000.sql.gz │          │
│  │  │   │   ├── rhdemo_20260113_020000.sql.gz │          │
│  │  │   │   └── ...                            │          │
│  │  │   └── keycloak/                          │          │
│  │  │       ├── keycloak_20260114_030000.sql.gz│         │
│  │  │       ├── keycloak_20260113_030000.sql.gz│         │
│  │  │       └── ...                            │          │
│  └─────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Configuration

### Localisation des Templates

**Fichier Helm** : [`infra/stagingkub/helm/rhdemo/templates/postgresql-backup-cronjob.yaml`](../infra/stagingkub/helm/rhdemo/templates/postgresql-backup-cronjob.yaml)

**Configuration** : [`infra/stagingkub/helm/rhdemo/values.yaml`](../infra/stagingkub/helm/rhdemo/values.yaml)

```yaml
postgresqlBackup:
  enabled: true
  retentionDays: 7  # Garder les backups pendant 7 jours

  rhdemo:
    schedule: "0 2 * * *"  # 2h du matin tous les jours

  keycloak:
    schedule: "0 3 * * *"  # 3h du matin tous les jours
```

### Paramètres Configurables

| Paramètre | Description | Valeur par défaut |
|-----------|-------------|-------------------|
| `postgresqlBackup.enabled` | Active/désactive les CronJobs | `true` |
| `postgresqlBackup.retentionDays` | Nombre de jours de rétention | `7` |
| `postgresqlBackup.rhdemo.schedule` | Planning cron RHDemo | `0 2 * * *` |
| `postgresqlBackup.keycloak.schedule` | Planning cron Keycloak | `0 3 * * *` |

---

## 🔄 Fonctionnement des CronJobs

### Étapes d'Exécution

Chaque CronJob exécute les étapes suivantes :

1. **Connexion à PostgreSQL** via variables d'environnement :
   - `PGHOST` : Service Kubernetes (ex: `postgresql-rhdemo`)
   - `PGPORT` : Port PostgreSQL (`5432`)
   - `PGDATABASE` : Nom de la base (ex: `rhdemo`)
   - `PGUSER` / `PGPASSWORD` : Credentials depuis Secrets K8s

2. **Création du backup** :
   ```bash
   pg_dump -Fc -f - | gzip > /backups/rhdemo_YYYYMMDD_HHMMSS.sql.gz
   ```
   - Format custom (`-Fc`) pour compression efficace
   - Compression gzip additionnelle
   - Horodatage dans le nom de fichier

3. **Nettoyage automatique** :
   ```bash
   find /backups -name "rhdemo_*.sql.gz" -type f -mtime +7 -delete
   ```
   - Supprime les backups de plus de 7 jours (configurable)
   - Basé sur `mtime` (modification time)

### Image Utilisée

- **Image** : `postgres:16-alpine`
- **Binaire** : `pg_dump` (inclus dans l'image PostgreSQL)
- **Taille** : ~80MB (Alpine Linux)

---

## 📦 Persistance des Backups

### extraMounts KinD

Les backups sont stockés **hors du conteneur KinD** via `extraMounts` pour survivre aux redémarrages :

**Configuration** : [`infra/stagingkub/kind-config.yaml`](../infra/stagingkub/kind-config.yaml)

```yaml
nodes:
- role: control-plane
  extraMounts:
  # Montage pour les backups PostgreSQL (survit aux redémarrages du cluster)
  - hostPath: /home/leno-vo/kind-data/rhdemo-stagingkub/backups
    containerPath: /mnt/backups
```

**Chemins des backups** :

- **Sur l'hôte** : `/home/leno-vo/kind-data/rhdemo-stagingkub/backups/rhdemo/` et `.../backups/keycloak/`
- **Dans KinD** : `/mnt/backups/rhdemo/` et `/mnt/backups/keycloak/`

**Avantages** :
- ✅ Survie aux redémarrages machine
- ✅ Survie à la recréation du cluster KinD
- ✅ Accès direct depuis l'hôte pour restauration
- ✅ Pas de PersistentVolume Kubernetes requis

> **Note** : Si le cluster KinD a été créé sans l'extraMount `/mnt/backups`, il faudra recréer le cluster avec `./scripts/init-stagingkub.sh` pour que les backups soient accessibles sur l'hôte.

### Persistance des Données PostgreSQL (PV Statiques)

En plus des backups, les **données PostgreSQL** elles-mêmes sont persistées via des **PersistentVolumes statiques** utilisant `hostPath` :

**Fichier Helm** : [`infra/stagingkub/helm/rhdemo/templates/postgresql-persistentvolumes.yaml`](../infra/stagingkub/helm/rhdemo/templates/postgresql-persistentvolumes.yaml)

```yaml
# PV statique pour PostgreSQL RHDemo
apiVersion: v1
kind: PersistentVolume
metadata:
  name: postgresql-rhdemo-pv
spec:
  storageClassName: manual-postgresql
  capacity:
    storage: 2Gi
  hostPath:
    path: /mnt/data/postgresql-rhdemo

# PV statique pour PostgreSQL Keycloak
apiVersion: v1
kind: PersistentVolume
metadata:
  name: postgresql-keycloak-pv
spec:
  storageClassName: manual-postgresql
  capacity:
    storage: 2Gi
  hostPath:
    path: /mnt/data/postgresql-keycloak
```

**Chemins des données** :

- **Sur l'hôte** : `/home/leno-vo/kind-data/rhdemo-stagingkub/postgresql-rhdemo/` et `.../postgresql-keycloak/`
- **Dans KinD** : `/mnt/data/postgresql-rhdemo/` et `/mnt/data/postgresql-keycloak/`

**Avantages des PV statiques** :

- ✅ Données PostgreSQL survivent à la recréation du cluster KinD
- ✅ Realm Keycloak préservé entre les redémarrages
- ✅ Pas de perte de données lors des mises à jour Helm
- ✅ `persistentVolumeReclaimPolicy: Retain` empêche la suppression accidentelle

---

## 🛠️ Commandes Utiles

### Vérifier les CronJobs

```bash
# Lister les CronJobs
kubectl get cronjob -n rhdemo-stagingkub

# Détails d'un CronJob
kubectl describe cronjob postgresql-rhdemo-backup -n rhdemo-stagingkub

# Historique des exécutions
kubectl get jobs -n rhdemo-stagingkub --sort-by=.metadata.creationTimestamp
```

### Vérifier les Backups

```bash
# Lister les backups RHDemo
ls -lh /home/leno-vo/kind-data/rhdemo-stagingkub/backups/rhdemo/

# Lister les backups Keycloak
ls -lh /home/leno-vo/kind-data/rhdemo-stagingkub/backups/keycloak/

# Vérifier la taille totale
du -sh /home/leno-vo/kind-data/rhdemo-stagingkub/backups/
```

### Déclencher un Backup Manuellement

```bash
# Créer un Job à partir du CronJob
kubectl create job --from=cronjob/postgresql-rhdemo-backup manual-backup-$(date +%s) -n rhdemo-stagingkub

# Suivre les logs
kubectl logs -n rhdemo-stagingkub -l job-name=manual-backup-<timestamp> -f
```

### Logs des Backups

```bash
# Dernière exécution RHDemo
kubectl logs -n rhdemo-stagingkub -l app=postgresql-rhdemo-backup --tail=50

# Dernière exécution Keycloak
kubectl logs -n rhdemo-stagingkub -l app=postgresql-keycloak-backup --tail=50
```

---

## 🔧 Restauration d'un Backup

### Méthode 1 : Restauration Directe dans le Pod

```bash
# 1. Copier le backup dans le pod PostgreSQL
BACKUP_FILE="rhdemo_20260114_020000.sql.gz"
kubectl cp /home/leno-vo/kind-data/rhdemo-stagingkub/backups/rhdemo/$BACKUP_FILE \
  rhdemo-stagingkub/postgresql-rhdemo-0:/tmp/$BACKUP_FILE

# 2. Se connecter au pod
kubectl exec -it -n rhdemo-stagingkub postgresql-rhdemo-0 -- bash

# 3. Restaurer la base (dans le pod)
gunzip -c /tmp/$BACKUP_FILE | pg_restore -d rhdemo -U rhdemo --clean --if-exists

# 4. Nettoyer
rm /tmp/$BACKUP_FILE
```

### Méthode 2 : Restauration depuis l'Hôte (Port-Forward)

```bash
# 1. Port-forward vers PostgreSQL
kubectl port-forward -n rhdemo-stagingkub statefulset/postgresql-rhdemo 5432:5432 &
PF_PID=$!

# 2. Restaurer depuis l'hôte
BACKUP_FILE="/home/leno-vo/kind-data/rhdemo-stagingkub/backups/rhdemo/rhdemo_20260114_020000.sql.gz"
gunzip -c $BACKUP_FILE | pg_restore -h localhost -p 5432 -d rhdemo -U rhdemo --clean --if-exists

# 3. Arrêter le port-forward
kill $PF_PID
```

### Restauration Keycloak

```bash
# Même procédure en remplaçant :
# - postgresql-rhdemo-0 → postgresql-keycloak-0
# - rhdemo → keycloak
# - rhdemo-db-secret → keycloak-db-secret
```

**Note** : La restauration nécessite le mot de passe PostgreSQL (disponible dans les Secrets K8s).

---

## 📊 Monitoring

### Vérifier la Santé des Backups

```bash
# Vérifier les CronJobs actifs
kubectl get cronjob -n rhdemo-stagingkub

# Vérifier les Jobs récents (dernières 24h)
kubectl get jobs -n rhdemo-stagingkub --field-selector status.successful=1

# Vérifier les échecs
kubectl get jobs -n rhdemo-stagingkub --field-selector status.failed=1
```

### Alertes Recommandées

**À implémenter avec Prometheus/Grafana** :

1. **Backup manquant** :
   - Alerte si âge du dernier backup > 25h
   - Métrique : `time() - file_mtime`

2. **Échec de Job** :
   - Alerte si `kube_job_status_failed > 0`
   - Métrique : `kube_job_status_failed{namespace="rhdemo-stagingkub"}`

3. **Taille anormale** :
   - Alerte si taille backup < 50% ou > 200% de la moyenne
   - Indicateur de corruption ou problème

---

## 🔐 Sécurité

### Secrets Utilisés

Les CronJobs accèdent aux credentials PostgreSQL via Secrets K8s :

```yaml
env:
- name: PGPASSWORD
  valueFrom:
    secretKeyRef:
      name: rhdemo-db-secret  # ou keycloak-db-secret
      key: password
```

**Création des Secrets** : Voir [`infra/stagingkub/scripts/init-stagingkub.sh`](../infra/stagingkub/scripts/init-stagingkub.sh)

### Permissions Requises

- **ServiceAccount** : `default` (namespace `rhdemo-stagingkub`)
- **RBAC** : Accès réseau aux Services PostgreSQL
- **Filesystem** : Écriture dans `hostPath` monté

---

## 📝 Bonnes Pratiques

### Rétention

- **7 jours** : Valeur par défaut, équilibre entre espace disque et historique
- **Ajustement** : Modifier `postgresqlBackup.retentionDays` dans `values.yaml`
- **Espace requis** : ~50-100MB par backup × 7 jours × 2 bases = **~1Go**

### Horaires

- **2h du matin (RHDemo)** : Faible activité utilisateur
- **3h du matin (Keycloak)** : Décalé de 1h pour éviter surcharge I/O
- **Modification** : Adapter selon timezone et charge applicative

### Vérification

```bash
# Script de vérification quotidien (à automatiser)
#!/bin/bash
BACKUP_DIR="/home/leno-vo/kind-data/rhdemo-stagingkub/backups"

# Vérifier présence backup < 25h
for db in rhdemo keycloak; do
  LATEST=$(find $BACKUP_DIR/$db -name "${db}_*.sql.gz" -mtime -1 | wc -l)
  if [ $LATEST -eq 0 ]; then
    echo "⚠️  Aucun backup récent pour $db!"
  else
    echo "✅ Backup $db OK"
  fi
done
```

---

## 🐛 Dépannage

### Backup Échoue : "Connection refused"

**Symptôme** : `could not connect to server: Connection refused`

**Solutions** :
1. Vérifier que le StatefulSet PostgreSQL est en cours d'exécution :
   ```bash
   kubectl get pods -n rhdemo-stagingkub -l app=postgresql-rhdemo
   ```

2. Vérifier le Service Kubernetes :
   ```bash
   kubectl get svc -n rhdemo-stagingkub postgresql-rhdemo
   ```

3. Tester la connectivité depuis un pod de test :
   ```bash
   kubectl run -it --rm debug --image=postgres:16-alpine --restart=Never -n rhdemo-stagingkub -- \
     psql -h postgresql-rhdemo -U rhdemo -d rhdemo -c "SELECT version();"
   ```

### Backup Échoue : "Authentication failed"

**Symptôme** : `FATAL: password authentication failed`

**Solutions** :
1. Vérifier le Secret Kubernetes :
   ```bash
   kubectl get secret rhdemo-db-secret -n rhdemo-stagingkub -o jsonpath='{.data.password}' | base64 -d
   ```

2. Vérifier que le Secret est monté correctement dans le CronJob :
   ```bash
   kubectl describe cronjob postgresql-rhdemo-backup -n rhdemo-stagingkub
   ```

### Espace Disque Plein

**Symptôme** : `No space left on device`

**Solutions** :
1. Vérifier l'espace utilisé :
   ```bash
   du -sh /home/leno-vo/kind-data/rhdemo-stagingkub/backups/*
   ```

2. Réduire la rétention dans `values.yaml` :
   ```yaml
   postgresqlBackup:
     retentionDays: 3  # Au lieu de 7
   ```

3. Nettoyer manuellement les anciens backups :
   ```bash
   find /home/leno-vo/kind-data/rhdemo-stagingkub/backups -name "*.sql.gz" -mtime +3 -delete
   ```

### CronJob ne S'Exécute Pas

**Symptôme** : Aucun Job créé

**Vérifications** :
1. CronJob suspendu :
   ```bash
   kubectl get cronjob -n rhdemo-stagingkub -o yaml | grep suspend
   ```

2. Vérifier les événements :
   ```bash
   kubectl describe cronjob postgresql-rhdemo-backup -n rhdemo-stagingkub
   ```

3. Forcer l'exécution manuelle pour tester :
   ```bash
   kubectl create job --from=cronjob/postgresql-rhdemo-backup test-backup -n rhdemo-stagingkub
   ```

---

## 📚 Références

### Documentation Kubernetes

- [CronJobs](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)

### PostgreSQL

- [pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)
- [pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html)

### Projet rhDemo

- [kind-config.yaml](../infra/stagingkub/kind-config.yaml) - Configuration extraMounts
- [init-stagingkub.sh](../infra/stagingkub/scripts/init-stagingkub.sh) - Script d'initialisation
- [values.yaml](../infra/stagingkub/helm/rhdemo/values.yaml) - Configuration Helm
