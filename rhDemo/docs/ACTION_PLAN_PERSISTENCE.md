# Plan d'action : Sécurisation de la persistance des données

## 🎯 Objectif

Éviter la perte de données après un redémarrage de machine et mettre en place des backups automatiques via CloudNativePG.

---

## ⚡ Actions immédiates (AUJOURD'HUI)

### 1️⃣ Restaurer Keycloak (10 minutes)

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./init-keycloak-stagingkub.sh
```

**Résultat attendu** :
- ✅ Realm `RHDemo` recréé
- ✅ Client OAuth2 configuré
- ✅ 3 utilisateurs de test créés

---

## 🛡️ Phase 1 : Configurer la persistance (1-2 heures)

### Étape 1 : Sauvegarder les données actuelles

```bash
# Créer le répertoire de backups
mkdir -p /home/leno-vo/backups/stagingkub

# Backup Keycloak
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  pg_dump -U keycloak keycloak > /home/leno-vo/backups/stagingkub/keycloak-$(date +%Y%m%d).sql

# Backup RHDemo
kubectl exec -n rhdemo-stagingkub postgresql-rhdemo-0 -- \
  pg_dump -U dbrhdemo dbrhdemo > /home/leno-vo/backups/stagingkub/rhdemo-$(date +%Y%m%d).sql

# Vérifier les backups
ls -lh /home/leno-vo/backups/stagingkub/
```

### Étape 2 : Recréer le cluster avec extraMounts

```bash
# Supprimer le cluster actuel
kind delete cluster --name rhdemo

# Recréer avec la configuration persistante (utilise kind-config.yaml)
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./init-stagingkub.sh
```

**Ce que fait le script** :
- ✅ Crée `/home/leno-vo/kind-data/rhdemo-stagingkub` sur l'hôte
- ✅ Monte ce répertoire dans le node KinD
- ✅ Configure le cluster avec la nouvelle persistance

### Étape 3 : Redéployer l'application

```bash
# Déployer l'application (ajuster la version si besoin)
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./deploy.sh 1.1.2-RELEASE
```

### Étape 4 : Restaurer Keycloak

```bash
# Réinitialiser Keycloak avec le script
./init-keycloak-stagingkub.sh
```

### Étape 5 : Restaurer les données métier (si nécessaire)

```bash
# Restaurer la base RHDemo depuis le backup
kubectl exec -i -n rhdemo-stagingkub postgresql-rhdemo-0 -- \
  psql -U dbrhdemo dbrhdemo < /home/leno-vo/backups/stagingkub/rhdemo-20260110.sql
```

### Étape 6 : Tester la persistance

```bash
# 1. Vérifier que tout fonctionne
curl -k https://rhdemo.stagingkub.local

# 2. Redémarrer la machine
sudo reboot

# 3. Après redémarrage, vérifier que les données sont toujours là
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  psql -U keycloak -d keycloak -c "SELECT id, name FROM realm;"

# Devrait montrer le realm RHDemo ✅
```

---

## 🚀 Phase 2 : Migration vers CloudNativePG (1 journée)

**Quand** : Après avoir validé que extraMounts fonctionne (attendre 2-3 jours)

### Documentation complète

Suivre le guide [CLOUDNATIVEPG_MIGRATION.md](./CLOUDNATIVEPG_MIGRATION.md)

### Résumé des étapes

1. **Installer l'opérateur CloudNativePG**
   ```bash
   helm repo add cnpg https://cloudnative-pg.github.io/charts
   helm install cnpg --namespace cnpg-system --create-namespace cnpg/cloudnative-pg
   ```

2. **Créer les manifests Helm**
   - `cnpg-cluster-keycloak.yaml`
   - `cnpg-scheduled-backup-keycloak.yaml`
   - Configurer `values.yaml`

3. **Migrer PostgreSQL Keycloak**
   - Scaler down Keycloak
   - Backup final
   - Déployer cluster CloudNativePG
   - Restaurer données
   - Tester

4. **Migrer PostgreSQL RHDemo**
   - Répéter le processus

5. **Configurer les backups automatiques**
   - Vérifier ScheduledBackup
   - Tester restauration

### Bénéfices après migration

- ✅ **Backups automatiques** quotidiens (2h du matin)
- ✅ **Rétention 7 jours** (configurable)
- ✅ **Point-In-Time Recovery** (restaurer à n'importe quel moment)
- ✅ **Haute disponibilité** (replicas PostgreSQL)
- ✅ **PgBouncer** intégré (pooling de connexions)
- ✅ **Monitoring Prometheus** natif

---

## 📊 État d'avancement

### ✅ Fait
- [x] Diagnostic du problème (perte données Keycloak)
- [x] Création fichier `kind-config.yaml` avec extraMounts
- [x] Modification script `init-stagingkub.sh`
- [x] Documentation migration CloudNativePG
- [x] Mise à jour CLAUDE.md

### 🔄 En cours
- [ ] Restauration Keycloak (action immédiate)
- [ ] Recréation cluster avec extraMounts

### 📅 À planifier
- [ ] Migration vers CloudNativePG (après validation extraMounts)

---

## 🧪 Tests de validation

### Test 1 : Persistance après redémarrage machine

```bash
# 1. Créer des données de test
kubectl exec -it -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  psql -U keycloak -d keycloak -c \
  "CREATE TABLE IF NOT EXISTS test_persistence (id SERIAL, data TEXT); \
   INSERT INTO test_persistence (data) VALUES ('test-$(date +%s)');"

# 2. Redémarrer la machine
sudo reboot

# 3. Après redémarrage, vérifier
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  psql -U keycloak -d keycloak -c "SELECT * FROM test_persistence;"

# Devrait montrer les données créées ✅
```

### Test 2 : Vérifier le montage extraMounts

```bash
# 1. Créer un fichier dans le node KinD
docker exec rhdemo-control-plane sh -c \
  "echo 'test-persistence' > /var/local-path-provisioner/TEST-FILE"

# 2. Vérifier sur l'hôte
cat /home/leno-vo/kind-data/rhdemo-stagingkub/TEST-FILE

# Devrait afficher "test-persistence" ✅
```

### Test 3 : Backup et restore manuel

```bash
# 1. Faire un backup
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  pg_dump -U keycloak keycloak > /tmp/test-backup.sql

# 2. Insérer des données de test
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  psql -U keycloak -d keycloak -c \
  "INSERT INTO test_persistence (data) VALUES ('should-be-removed');"

# 3. Restaurer depuis le backup
kubectl exec -i -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  psql -U keycloak keycloak < /tmp/test-backup.sql

# 4. Vérifier que les nouvelles données ont disparu
kubectl exec -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  psql -U keycloak -d keycloak -c "SELECT * FROM test_persistence;"

# Ne devrait PAS contenir "should-be-removed" ✅
```

---

## 🚨 Rollback

Si quelque chose se passe mal pendant la migration :

### Rollback Phase 1 (extraMounts)

```bash
# Supprimer le nouveau cluster
kind delete cluster --name rhdemo

# Recréer sans extraMounts (ancienne méthode)
# Éditer temporairement init-stagingkub.sh pour retirer extraMounts
# Puis :
./init-stagingkub.sh

# Restaurer depuis backup
kubectl exec -i -n rhdemo-stagingkub postgresql-keycloak-0 -- \
  psql -U keycloak keycloak < /home/leno-vo/backups/stagingkub/keycloak-20260110.sql
```

### Rollback Phase 2 (CloudNativePG)

Voir section "Rollback" dans [CLOUDNATIVEPG_MIGRATION.md](./CLOUDNATIVEPG_MIGRATION.md)

---

## 📞 Support

### Problèmes courants

**Problème** : Le cluster ne démarre pas après recréation
```bash
# Vérifier les logs
docker logs rhdemo-control-plane

# Vérifier le montage
docker inspect rhdemo-control-plane | grep -A 10 Mounts
```

**Problème** : Permissions refusées sur `/home/leno-vo/kind-data/`
```bash
# Corriger les permissions
sudo chown -R $USER:$USER /home/leno-vo/kind-data/
chmod -R 755 /home/leno-vo/kind-data/
```

**Problème** : Le script init-keycloak-stagingkub.sh échoue
```bash
# Vérifier que Keycloak est ready
kubectl wait --for=condition=ready pod -l app=keycloak -n rhdemo-stagingkub --timeout=5m

# Vérifier les logs Keycloak
kubectl logs -n rhdemo-stagingkub -l app=keycloak --tail=100
```

---

## 📚 Documentation créée

1. [kind-config.yaml](../infra/stagingkub/kind-config.yaml) - Configuration KinD avec extraMounts
2. [CLOUDNATIVEPG_MIGRATION.md](./CLOUDNATIVEPG_MIGRATION.md) - Guide complet migration CloudNativePG
3. [PERSISTENCE_DATA_RECOVERY.md](./PERSISTENCE_DATA_RECOVERY.md) - Diagnostic et solutions
4. **Ce fichier** - Plan d'action étape par étape

---

## ✅ Checklist finale

### Actions immédiates
- [ ] Restaurer Keycloak avec `init-keycloak-stagingkub.sh`
- [ ] Tester la connexion à l'application

### Phase 1 (à faire dans les prochains jours)
- [ ] Sauvegarder les données actuelles
- [ ] Recréer le cluster avec extraMounts
- [ ] Redéployer l'application
- [ ] Restaurer les données
- [ ] Tester la persistance (redémarrage machine)

### Phase 2 (après validation Phase 1)
- [ ] Installer opérateur CloudNativePG
- [ ] Créer manifests Helm
- [ ] Migrer PostgreSQL Keycloak
- [ ] Migrer PostgreSQL RHDemo
- [ ] Configurer backups automatiques
- [ ] Tester Point-In-Time Recovery

---

**Document créé le** : 2026-01-10
**Auteur** : Claude Code (avec leno-vo)
**Statut** : En cours d'implémentation
