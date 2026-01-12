# Récupération après perte de données Keycloak

## 🚨 Problème rencontré

Après un redémarrage de machine, les données du realm `RHDemo` dans Keycloak ont été perdues.

### Cause racine

Le cluster KinD utilisait des volumes `hostPath` **à l'intérieur du conteneur Docker** du node KinD :
- Volume : `/var/local-path-provisioner/pvc-xxx` (dans le conteneur rhdemo-control-plane)
- **Problème** : Lors du redémarrage machine, le node Docker est recréé avec un nouveau filesystem
- Les PersistentVolumes ont une politique `RECLAIM POLICY: Delete`
- Résultat : Toutes les données sont perdues (base Keycloak réinitialisée avec uniquement le realm `master`)

### Événement Kubernetes observé

```
39m  Normal  SandboxChanged  pod/postgresql-keycloak-0  Pod sandbox changed, it will be killed and re-created.
```

---

## ✅ Solution immédiate : Réinitialiser Keycloak

### Étape 1 : Restaurer la configuration Keycloak

Utiliser le script d'initialisation automatique :

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./init-keycloak-stagingkub.sh
```

Ce script va :
1. ✅ Déchiffrer automatiquement les secrets de stagingkub avec SOPS
2. ✅ Créer un port-forward vers Keycloak
3. ✅ Recréer le realm `RHDemo`
4. ✅ Recréer le client OAuth2 avec le bon secret
5. ✅ Recréer les 3 utilisateurs de test avec leurs rôles

### Étape 2 : Vérifier la restauration

```bash
# Vérifier les realms dans la base
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  psql -U keycloak -d keycloak -c "SELECT id, name FROM realm;"

# Devrait afficher :
#                  id                  |  name
# --------------------------------------+--------
#  e4118a92-248b-4d3d-8859-251489aaa225 | master
#  <nouveau-id>                         | RHDemo

# Tester la connexion à l'application
# https://rhdemo.stagingkub.local
```

---

## 🛡️ Solution permanente : Persistance des données

Pour éviter que cela se reproduise, nous avons mis en place **extraMounts KinD**.

### Architecture de persistance

**Avant (données perdues au redémarrage)** :
```
Host Machine
  └─> Docker Container (rhdemo-control-plane)
       └─> /var/local-path-provisioner/pvc-xxx  ❌ PERDU au restart
```

**Après (données persistantes)** :
```
Host Machine (/home/leno-vo/kind-data/rhdemo-stagingkub)  ✅ PERSISTE
  └─> extraMount ↓
       Docker Container (rhdemo-control-plane)
         └─> /var/local-path-provisioner  (lié au host)
              └─> pvc-xxx/  ✅ PERSISTE
```

### Fichiers créés/modifiés

1. **[kind-config.yaml](../infra/stagingkub/kind-config.yaml)** (nouveau)
   - Configuration KinD avec extraMounts
   - Monte `/home/leno-vo/kind-data/rhdemo-stagingkub` dans le node

2. **[init-stagingkub.sh](../infra/stagingkub/scripts/init-stagingkub.sh)** (modifié)
   - Utilise maintenant le fichier `kind-config.yaml` persistant
   - Crée automatiquement le répertoire de persistance sur l'hôte

### Recréer le cluster avec persistance

⚠️ **Attention** : Cela va détruire le cluster actuel et toutes ses données.

```bash
# 1. Sauvegarder les données actuelles
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  pg_dump -U keycloak keycloak > /tmp/keycloak-backup.sql

kubectl exec -n rhdemo-stagingkub postgresql-rhdemo-0 -- \
  pg_dump -U dbrhdemo dbrhdemo > /tmp/rhdemo-backup.sql

# 2. Supprimer le cluster actuel
kind delete cluster --name rhdemo

# 3. Recréer avec la nouvelle configuration persistante
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./init-stagingkub.sh

# 4. Redéployer l'application
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./deploy.sh 1.1.2-RELEASE  # (ou votre version)

# 5. Restaurer Keycloak
./init-keycloak-stagingkub.sh

# 6. Restaurer les données métier
kubectl exec -i -n rhdemo-stagingkub postgresql-rhdemo-0 -- \
  psql -U dbrhdemo dbrhdemo < /tmp/rhdemo-backup.sql
```

### Vérifier la persistance

```bash
# Vérifier que le répertoire de persistance existe sur l'hôte
ls -la /home/leno-vo/kind-data/rhdemo-stagingkub/

# Vérifier le montage dans le node KinD
docker exec rhdemo-control-plane ls -la /var/local-path-provisioner/

# Devrait montrer les mêmes fichiers (c'est le même répertoire)
```

---

## 🚀 Prochaine étape : CloudNativePG

Pour une gestion encore plus robuste des backups, voir [CLOUDNATIVEPG_MIGRATION.md](./CLOUDNATIVEPG_MIGRATION.md).

CloudNativePG apportera :
- ✅ Backups automatiques quotidiens avec rétention
- ✅ Point-In-Time Recovery (restaurer à n'importe quel moment)
- ✅ Haute disponibilité (replicas)
- ✅ Pooling de connexions (PgBouncer)
- ✅ Monitoring Prometheus intégré

---

## 📊 Comparaison des solutions

| Solution | Survit au redémarrage machine | Backups automatiques | PITR | HA | Complexité |
|----------|------------------------------|----------------------|------|-------|-----------|
| **StatefulSet actuel (sans extraMounts)** | ❌ NON | ❌ Non | ❌ Non | ❌ Non | Faible |
| **StatefulSet + extraMounts** | ✅ OUI | ❌ Non (manuel) | ❌ Non | ❌ Non | Faible |
| **CloudNativePG + extraMounts** | ✅ OUI | ✅ Oui (quotidien) | ✅ Oui | ✅ Oui | Moyenne |

---

## 🔧 Commandes de diagnostic

### Vérifier l'état des PV/PVC

```bash
# Lister les PVC
kubectl get pvc -n rhdemo-stagingkub

# Voir les détails d'un PVC
kubectl describe pvc postgresql-data-postgresql-keycloak-0 -n rhdemo-stagingkub

# Lister les PV avec leur politique de rétention
kubectl get pv -o custom-columns=NAME:.metadata.name,RECLAIM:.spec.persistentVolumeReclaimPolicy,STATUS:.status.phase
```

### Vérifier les données dans PostgreSQL

```bash
# Connexion à PostgreSQL Keycloak
kubectl exec -it -n rhdemo-stagingkub postgresql-keycloak-0 -- psql -U keycloak

# Lister les realms
SELECT id, name FROM realm;

# Lister les clients d'un realm
SELECT id, client_id FROM client WHERE realm_id = '<realm-id>';

# Lister les utilisateurs
SELECT id, username, email FROM user_entity WHERE realm_id = '<realm-id>';
```

### Vérifier les événements récents

```bash
# Événements du namespace
kubectl get events -n rhdemo-stagingkub --sort-by='.lastTimestamp' | tail -20

# Événements d'un pod spécifique
kubectl describe pod postgresql-keycloak-0 -n rhdemo-stagingkub | grep -A 10 Events
```

---

## 📝 Checklist de recovery

### Après un redémarrage machine (avec extraMounts)
- [ ] Vérifier que le cluster KinD est démarré : `kind get clusters`
- [ ] Vérifier que les pods sont Running : `kubectl get pods -n rhdemo-stagingkub`
- [ ] Tester l'accès à l'application : https://rhdemo.stagingkub.local
- [ ] Vérifier la connexion avec un utilisateur de test

### Après un redémarrage machine (SANS extraMounts)
- [ ] Réinitialiser Keycloak : `./init-keycloak-stagingkub.sh`
- [ ] Restaurer les données métier si nécessaire (depuis backup manuel)
- [ ] **Action recommandée** : Recréer le cluster avec extraMounts (voir section ci-dessus)

---

## 💡 Bonnes pratiques

### Backups manuels réguliers

En attendant CloudNativePG, faire des backups manuels réguliers :

```bash
# Script de backup à exécuter régulièrement
#!/bin/bash
BACKUP_DIR="/home/leno-vo/backups/stagingkub"
mkdir -p "$BACKUP_DIR"

DATE=$(date +%Y%m%d-%H%M%S)

# Backup Keycloak
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  pg_dump -U keycloak keycloak > "$BACKUP_DIR/keycloak-$DATE.sql"

# Backup RHDemo
kubectl exec -n rhdemo-stagingkub postgresql-rhdemo-0 -- \
  pg_dump -U dbrhdemo dbrhdemo > "$BACKUP_DIR/rhdemo-$DATE.sql"

# Compression
gzip "$BACKUP_DIR"/*.sql

# Rotation : garder 30 jours
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

echo "Backups créés dans $BACKUP_DIR"
```

### Sauvegarde du répertoire de persistance

Le répertoire extraMounts peut être sauvegardé directement :

```bash
# Backup complet du répertoire de persistance
tar -czf ~/backups/stagingkub-persistence-$(date +%Y%m%d).tar.gz \
  /home/leno-vo/kind-data/rhdemo-stagingkub

# Restauration
tar -xzf ~/backups/stagingkub-persistence-20260110.tar.gz -C /
```

---

## 📚 Ressources

- [Configuration KinD](../infra/stagingkub/kind-config.yaml)
- [Script d'initialisation Keycloak](../infra/stagingkub/scripts/init-keycloak-stagingkub.sh)
- [Guide migration CloudNativePG](./CLOUDNATIVEPG_MIGRATION.md)
- [Documentation KinD extraMounts](https://kind.sigs.k8s.io/docs/user/configuration/#extra-mounts)

---

**Dernière mise à jour** : 2026-01-10
