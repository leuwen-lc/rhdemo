# Loki Stack - Guide de Démarrage Rapide

**⚠️ Sécurité:** Avant de commencer, consultez [SECURITY.md](SECURITY.md) pour les bonnes pratiques de configuration sécurisée.

## 🚀 Installation en 4 étapes

### Étape 1: Démarrer le cluster stagingkub

```bash
cd /home/leno-vo/git/repository/rhDemo
./scripts/init-stagingkub.sh
```

### Étape 2: Configurer le mot de passe Grafana

**⚠️ SÉCURITÉ: Cette étape est obligatoire**

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub

# Générer un mot de passe fort
PASSWORD=$(openssl rand -base64 32)
echo "Mot de passe généré: $PASSWORD"

# Éditer grafana-values.yaml et remplacer adminPassword: "" par le mot de passe généré
# Exemple avec sed:
sed -i "s/adminPassword: \"\"/adminPassword: \"$PASSWORD\"/" grafana-values.yaml

# OU éditer manuellement avec votre éditeur préféré
nano grafana-values.yaml  # ou vim, code, etc.
```

**Important:** Conservez ce mot de passe en lieu sûr (gestionnaire de mots de passe).

### Étape 3: Installer Loki Stack (Charts Modernes)

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./install-loki-modern.sh
```

Le script va automatiquement:
- ✅ Vérifier les prérequis
- ✅ Valider la configuration du mot de passe Grafana
- ✅ Ajouter le repository Helm Grafana
- ✅ Créer le namespace `loki-stack`
- ✅ Générer le certificat TLS pour Grafana
- ✅ Installer Loki (mode SingleBinary)
- ✅ Installer Promtail (collecte logs)
- ✅ Installer Grafana (visualisation)
- ✅ Mettre à jour /etc/hosts

**Durée:** ~2-3 minutes

**Charts utilisés:**
- `grafana/loki` (v6.x)
- `grafana/promtail` (v6.x)
- `grafana/grafana` (v8.x)

### Étape 4: Accéder à Grafana

```bash
# Option 1: Via Ingress (recommandé)
open https://grafana.stagingkub.local

# Option 2: Via Port-Forward (si ingress ne fonctionne pas)
kubectl port-forward -n loki-stack svc/grafana 3000:80
open http://localhost:3000
```

**Credentials:**
- Username: `admin`
- Password: (mot de passe configuré à l'étape 2)

---

## 📊 Première Requête LogQL

1. Dans Grafana, aller sur **Explore** (icône boussole)
2. Sélectionner datasource: **Loki**
3. Dans le query editor, entrer:

```logql
{namespace="rhdemo-stagingkub", app="rhdemo-app"}
```

4. Cliquer sur **Run query**
5. Vous devriez voir les logs de l'application rhDemo!

---

## 🔍 Requêtes Utiles

### Logs par Application

```logql
# rhDemo App
{namespace="rhdemo-stagingkub", app="rhdemo-app"}

# Keycloak
{namespace="rhdemo-stagingkub", app="keycloak"}

# PostgreSQL
{namespace="rhdemo-stagingkub", app=~"postgresql-.*"}
```

### Filtrer par Niveau

```logql
# Erreurs uniquement
{namespace="rhdemo-stagingkub"} |= "ERROR"

# Warnings
{namespace="rhdemo-stagingkub"} |= "WARN"
```

### Recherche de Texte

```logql
# Logs contenant "SQL"
{namespace="rhdemo-stagingkub", app="rhdemo-app"} |= "SQL"

# Logs avec Exception
{namespace="rhdemo-stagingkub"} |~ "Exception|Error"
```

---

## 🛠️ Commandes Utiles

### Vérifier l'Installation

```bash
# Voir tous les pods Loki Stack
kubectl get pods -n loki-stack

# Voir les services
kubectl get svc -n loki-stack

# Voir l'ingress
kubectl get ingress -n loki-stack
```

### Consulter les Logs

```bash
# Logs Loki
kubectl logs -n loki-stack -l app=loki -f

# Logs Promtail
kubectl logs -n loki-stack -l app=promtail -f

# Logs Grafana
kubectl logs -n loki-stack -l app.kubernetes.io/name=grafana -f
```

### Redémarrer un Composant

```bash
# Redémarrer Loki
kubectl rollout restart statefulset -n loki-stack loki

# Redémarrer Promtail
kubectl rollout restart daemonset -n loki-stack loki-stack-promtail

# Redémarrer Grafana
kubectl rollout restart deployment -n loki-stack loki-stack-grafana
```

---

## ⚙️ Configuration

### Modifier la Rétention des Logs

Éditer: `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/loki-modern-values.yaml`

```yaml
loki:
  limits_config:
    retention_period: 336h  # 14 jours (au lieu de 7)
```

Appliquer:
```bash
helm upgrade loki grafana/loki \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/loki-modern-values.yaml
```

### Changer le Password Grafana

**Méthode 1: Avant installation**

Éditer `grafana-values.yaml`:
```yaml
adminPassword: "VotreNouveauMotDePasse"
```

**Méthode 2: Après installation (via Kubernetes Secret)**

```bash
# Générer nouveau mot de passe
NEW_PASSWORD=$(openssl rand -base64 32)

# Mettre à jour le secret
kubectl create secret generic grafana-admin-password \
  --from-literal=admin-password="$NEW_PASSWORD" \
  -n loki-stack --dry-run=client -o yaml | kubectl apply -f -

# Redémarrer Grafana pour prendre en compte
kubectl rollout restart deployment -n loki-stack grafana
```

---

## 🔧 Troubleshooting

### Grafana n'est pas accessible

```bash
# Vérifier les pods
kubectl get pods -n loki-stack

# Si pod en erreur, voir les logs
kubectl logs -n loki-stack -l app.kubernetes.io/name=grafana

# Port-forward temporaire
kubectl port-forward -n loki-stack svc/loki-stack-grafana 3000:80
```

### Aucun log dans Grafana

```bash
# Vérifier que Promtail collecte des logs
kubectl logs -n loki-stack -l app=promtail | grep "discovered"

# Vérifier que Loki reçoit des données
kubectl port-forward -n loki-stack svc/loki 3100:3100
curl "http://localhost:3100/loki/api/v1/label/namespace/values"
# Devrait retourner: ["rhdemo-stagingkub"]
```

### PVC Loki plein

```bash
# Vérifier l'utilisation
kubectl exec -n loki-stack loki-0 -- df -h /loki

# Augmenter la taille (si storage class le supporte)
kubectl patch pvc -n loki-stack loki-data \
  -p '{"spec":{"resources":{"requests":{"storage":"10Gi"}}}}'
```

---

## 📚 Documentation Complète

Pour plus de détails, consulter:

**[/home/leno-vo/git/repository/rhDemo/docs/LOKI_STACK_INTEGRATION.md](../../../docs/LOKI_STACK_INTEGRATION.md)**

Contenu:
- Architecture détaillée
- Configuration avancée
- Queries LogQL complètes
- Dashboards Grafana
- Troubleshooting complet
- Maintenance et backup

---

## 🗑️ Désinstallation

```bash
# Désinstaller Helm release
helm uninstall loki-stack -n loki-stack

# Supprimer PVC (ATTENTION: perte de données)
kubectl delete pvc -n loki-stack loki-data

# Supprimer namespace
kubectl delete namespace loki-stack

# Retirer du DNS
sudo sed -i '/grafana.stagingkub.local/d' /etc/hosts
```

---

**Auteur:** Documentation rhDemo
**Date:** 30 décembre 2025
