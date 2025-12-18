# 🔓 Scripts de déblocage Helm

Ces scripts permettent de résoudre l'erreur courante :
```
Error: UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress
```

## 📋 Scripts disponibles

### 1. `helm-unlock.sh` - Version complète avec confirmation

Script interactif qui affiche l'état de tous les secrets Helm et demande confirmation avant suppression.

**Usage :**
```bash
# Avec valeurs par défaut (rhdemo-stagingkub / rhdemo)
./helm-unlock.sh

# Avec paramètres personnalisés
./helm-unlock.sh <NAMESPACE> <RELEASE_NAME>

# Exemple
./helm-unlock.sh rhdemo-stagingkub rhdemo
```

**Fonctionnalités :**
- ✅ Affiche tous les secrets Helm et leur état
- ✅ Détecte automatiquement les états bloquants (pending-*)
- ✅ Demande confirmation avant suppression (mode interactif)
- ✅ Suppression automatique en mode non-interactif
- ✅ Affiche des statistiques détaillées

### 2. `helm-unlock-quick.sh` - Version rapide sans confirmation

Script one-liner qui supprime immédiatement tous les verrous pending sans demander confirmation.

**Usage :**
```bash
# Avec valeurs par défaut
./helm-unlock-quick.sh

# Avec paramètres personnalisés
./helm-unlock-quick.sh <NAMESPACE> <RELEASE_NAME>
```

**⚠️ Attention :** Ce script supprime les verrous sans confirmation. À utiliser uniquement si vous êtes sûr.

## 🔍 États Helm bloquants

Les états suivants empêchent les déploiements Helm :

| État | Description | Cause |
|------|-------------|-------|
| `pending-install` | Installation en cours | Installation interrompue |
| `pending-upgrade` | Mise à jour en cours | Upgrade interrompu |
| `pending-rollback` | Rollback en cours | Rollback interrompu |

## 🎯 Quand utiliser ces scripts ?

### Cas d'usage typiques :

1. **Pipeline CD/CI interrompu** : Vous avez arrêté un build Jenkins pendant le déploiement Helm
2. **Timeout réseau** : La connexion kubectl a été perdue pendant un déploiement
3. **Processus tué** : Vous avez tué (`Ctrl+C` ou `kill`) un processus helm en cours
4. **Déploiement bloqué** : Helm attend indéfiniment un rollback

### Symptômes :

```bash
$ helm upgrade --install myapp ./chart
Error: UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress
```

## 🛠️ Utilisation manuelle (sans script)

Si vous préférez débloquer manuellement :

```bash
# 1. Lister les secrets Helm
kubectl get secrets -n rhdemo-stagingkub -l owner=helm,name=rhdemo

# 2. Identifier le dernier secret (numéro le plus élevé)
kubectl get secrets -n rhdemo-stagingkub -l owner=helm,name=rhdemo --sort-by=.metadata.creationTimestamp

# 3. Vérifier l'état d'un secret spécifique
kubectl get secret sh.helm.release.v1.rhdemo.v20 -n rhdemo-stagingkub \
  -o jsonpath='{.data.release}' | base64 -d | base64 -d | gzip -d | jq -r '.info.status'

# 4. Supprimer le secret bloqué
kubectl delete secret sh.helm.release.v1.rhdemo.v20 -n rhdemo-stagingkub
```

## 🔄 Workflow complet de déblocage

```bash
# 1. Débloquer avec le script
./helm-unlock.sh

# 2. Vérifier l'état du release
helm status rhdemo -n rhdemo-stagingkub

# 3. Relancer le déploiement
helm upgrade --install rhdemo ./chart \
  --namespace rhdemo-stagingkub \
  --wait --timeout 10m
```

## 🚨 Prévention

Pour éviter les verrous Helm :

### ✅ Bonnes pratiques :

1. **Toujours utiliser `--atomic`** : Rollback automatique en cas d'échec
   ```bash
   helm upgrade --install myapp ./chart --atomic
   ```

2. **Définir un timeout raisonnable** : Évite les attentes infinies
   ```bash
   helm upgrade --install myapp ./chart --timeout 10m
   ```

3. **Ne jamais interrompre brutalement** : Utilisez `Ctrl+C` une seule fois et laissez Helm se terminer proprement

4. **Monitorer les pods avant déploiement** : Vérifiez que tout est OK (secrets, images, ressources)

### ❌ À éviter :

- ❌ Tuer le processus Helm avec `kill -9`
- ❌ Interrompre plusieurs fois avec `Ctrl+C`
- ❌ Déployer sans vérifier les prérequis (secrets, images)

## 📚 Ressources

- [Documentation Helm](https://helm.sh/docs/)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Debugging Helm](https://helm.sh/docs/howto/charts_tips_and_tricks/)

## 🐛 Dépannage

### Le script ne trouve pas de verrous mais l'erreur persiste

```bash
# Vérifier manuellement tous les états
for secret in $(kubectl get secrets -n rhdemo-stagingkub -l owner=helm,name=rhdemo -o name); do
    echo "=== $secret ==="
    kubectl get $secret -n rhdemo-stagingkub -o jsonpath='{.data.release}' \
        | base64 -d | base64 -d | gzip -d | jq -r '.info.status'
done
```

### Solution radicale : Réinstallation complète

Si rien ne fonctionne :

```bash
# ⚠️ ATTENTION : Cela supprime tout le déploiement
helm uninstall rhdemo -n rhdemo-stagingkub
kubectl delete secrets -n rhdemo-stagingkub -l owner=helm,name=rhdemo
helm install rhdemo ./chart -n rhdemo-stagingkub
```

---

**Dernière mise à jour** : 2025-12-18
