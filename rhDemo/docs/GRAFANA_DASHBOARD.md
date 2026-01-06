# Dashboard Grafana pour rhDemo

## Description

Dashboard Grafana pré-configuré pour visualiser les logs de l'application rhDemo dans l'environnement stagingkub via Loki.

## Contenu du Dashboard

Le dashboard "rhDemo - Logs Application" comprend :

### Panneaux de Logs
- 🔴 **Logs d'Erreurs** : Affiche uniquement les logs contenant "ERROR"
- 🔍 **Logs rhDemo App (Temps Réel)** : Tous les logs de l'application en temps réel
- 🔐 **Logs Keycloak** : Logs d'authentification (Login/logout)
- 🗄️ **Logs PostgreSQL** : Logs des bases de données PostgreSQL

### Métriques
- 📊 **Rate d'Erreurs** : Nombre d'erreurs par minute
- 📈 **Volume de Logs** : Volume de logs par application (rate sur 5 minutes)
- ⚠️ **Logs WARN** : Compteur des logs de niveau WARNING (dernière heure)
- 🔴 **Logs ERROR** : Compteur des logs de niveau ERROR (dernière heure)

### Tableaux
- 📊 **Top 10 Pods** : Les 10 pods générant le plus de logs (dernière heure)

## Déploiement

### Installation Automatique

Le dashboard est automatiquement déployé lors de l'installation de la stack Loki :

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./install-loki.sh
```

### Mise à jour Manuelle

Pour mettre à jour uniquement le dashboard sans réinstaller la stack complète :

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./deploy-grafana-dashboard.sh
```

## Configuration

### Fichiers

- **Dashboard JSON** : `grafana-dashboard-rhdemo.json`
  - Contient la définition complète du dashboard au format API Grafana
  - Référence la datasource Loki avec `uid: "loki"`
  - **Note** : Le fichier contient un wrapper `{"dashboard": {...}}` utilisé pour l'import via API
  - Les scripts extraient automatiquement le contenu du dashboard pour le provisioning

- **Configuration Grafana** : `helm/observability/grafana-values.yaml`
  - Définit la datasource Loki avec `uid: loki`
  - Active le sidecar pour le chargement automatique des dashboards depuis ConfigMaps
  - Configure le provisioning des dashboards

### Sidecar Dashboard

Le chart Helm Grafana inclut un container sidecar (`grafana-sc-dashboard`) qui :
- Surveille tous les ConfigMaps avec le label `grafana_dashboard=1`
- Écrit automatiquement les dashboards dans `/tmp/dashboards/`
- Déclenche un rechargement automatique dans Grafana
- Permet l'ajout/modification de dashboards sans redémarrage

### Datasource

Le dashboard utilise la datasource Loki configurée avec :
- **Nom** : Loki
- **Type** : loki
- **UID** : `loki`
- **URL** : `http://loki-gateway:80`

### Namespace

Le dashboard interroge les logs du namespace : `rhdemo-stagingkub`

## Requêtes LogQL

Exemples de requêtes utilisées dans le dashboard :

```logql
# Tous les logs de l'application
{namespace="rhdemo-stagingkub", app="rhdemo-app"}

# Logs d'erreurs uniquement
{namespace="rhdemo-stagingkub", app="rhdemo-app"} |= "ERROR"

# Rate d'erreurs par minute
sum(count_over_time({namespace="rhdemo-stagingkub", app="rhdemo-app"} |= "ERROR" [1m]))

# Volume de logs par application
sum by (app) (rate({namespace="rhdemo-stagingkub"}[5m]))

# Logs Keycloak (authentification)
{namespace="rhdemo-stagingkub", app="keycloak"} |~ "Login|logout|authenticated"
```

## Accès

Une fois déployé, le dashboard est accessible via :

**URL** : https://grafana.stagingkub.local

**Login** : admin / (voir mot de passe dans `helm/observability/grafana-values.yaml`)

Le dashboard apparaîtra automatiquement dans la liste des dashboards Grafana sous le nom :
**"rhDemo - Logs Application"**

## Troubleshooting

### Le dashboard n'apparaît pas

1. Vérifier que le ConfigMap existe :
   ```bash
   kubectl get configmap grafana-dashboard-rhdemo -n loki-stack
   ```

2. Vérifier les labels :
   ```bash
   kubectl get configmap grafana-dashboard-rhdemo -n loki-stack -o yaml | grep labels -A 5
   ```

   Doit contenir : `grafana_dashboard: "1"`

3. Vérifier les logs Grafana :
   ```bash
   kubectl logs -n loki-stack deployment/grafana | grep -i dashboard
   ```

### Les graphiques affichent "No Data"

1. Vérifier que Loki est accessible :
   ```bash
   kubectl get pods -n loki-stack | grep loki
   ```

2. Vérifier la datasource dans Grafana :
   - Aller dans Configuration → Data Sources → Loki
   - Cliquer sur "Test" pour vérifier la connexion
   - Vérifier que l'UID est bien "loki"

3. Vérifier que des logs sont disponibles :
   ```bash
   # Via kubectl
   kubectl logs -n rhdemo-stagingkub deployment/rhdemo-app --tail=10
   ```

### Erreur "datasource not found"

Le dashboard référence la datasource par son UID. Vérifier que la datasource Loki a bien l'UID `loki` :

```bash
kubectl get configmap grafana -n loki-stack -o yaml | grep -A 10 "datasources.yaml"
```

Si ce n'est pas le cas, mettre à jour avec :

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./install-loki.sh
```

## Personnalisation

Pour modifier le dashboard :

1. Éditer le fichier `grafana-dashboard-rhdemo.json`
2. Redéployer avec `./deploy-grafana-dashboard.sh`

Alternativement, depuis l'interface Grafana :
1. Ouvrir le dashboard
2. Faire les modifications
3. Exporter le JSON (Share → Export → Save to file)
4. Remplacer le contenu de `grafana-dashboard-rhdemo.json`
5. Redéployer

**Note** : Les dashboards provisionnés sont en lecture seule dans Grafana. Pour les modifier directement dans l'interface, il faut les dupliquer (Save As).
