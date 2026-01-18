# Dashboards Grafana pour rhDemo

## Description

Dashboards Grafana pre-configures pour visualiser les logs et metriques de l'application rhDemo dans l'environnement stagingkub.

- **Logs** : via Loki (collecte Promtail)
- **Metriques** : via Prometheus (kube-prometheus-stack)

---

## Dashboards Disponibles

### 1. rhDemo - Logs Application (Loki)

Dashboard pour visualiser les logs de tous les composants.

#### Panneaux de Logs
- **Logs d'Erreurs** : Affiche uniquement les logs contenant "ERROR" ou "WARN"
- **Logs rhDemo App (Temps Reel)** : Tous les logs de l'application en temps reel
- **Logs Keycloak** : Logs d'authentification
- **Logs PostgreSQL** : Logs des bases de donnees PostgreSQL

#### Metriques Loki
- **Rate d'Erreurs** : Nombre d'erreurs par minute
- **Volume de Logs** : Volume de logs par application (rate sur 5 minutes)
- **Logs WARN** : Compteur des logs de niveau WARNING (derniere heure)
- **Logs ERROR** : Compteur des logs de niveau ERROR (derniere heure)

#### Tableaux
- **Top 10 Pods** : Les 10 pods generant le plus de logs (derniere heure)

---

### 2. rhDemo - Metriques Pods (Prometheus)

Dashboard pour visualiser les metriques de ressources des 4 pods principaux.

#### Vue d'ensemble
- **Statut des Pods** : Nombre de pods en etat Running
- **CPU Total Utilise** : Pourcentage CPU total du namespace
- **Memoire Totale Utilisee** : Memoire totale consommee (en Go)
- **Restarts Totaux** : Nombre de redemarrages sur la derniere heure

#### Graphiques Globaux
- **CPU par Pod** : Evolution CPU de tous les pods avec moyenne/max
- **Memoire par Pod** : Evolution memoire de tous les pods avec moyenne/max

#### Sections par Pod (rhdemo-app, keycloak, postgresql-rhdemo, postgresql-keycloak)

Chaque pod dispose de 3 graphiques :
- **CPU** : Usage reel vs Request vs Limit
- **Memoire** : Usage reel vs Request vs Limit
- **Reseau** : Trafic RX (recu) et TX (emis) en bytes/sec

#### Section Disque / PVC
- **Utilisation Disque par PVC** : Jauge montrant le pourcentage d'utilisation
- **Espace Disque Disponible** : Tableau avec l'espace libre par PVC

---

## Deploiement

### Installation Automatique

Les deux dashboards sont automatiquement deployes lors de l'installation de la stack observabilite :

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./install-observability.sh
```

### Mise a jour Manuelle

Pour mettre a jour les dashboards sans reinstaller la stack complete :

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts

# Deployer tous les dashboards
./deploy-grafana-dashboard.sh

# Deployer uniquement le dashboard des logs
./deploy-grafana-dashboard.sh logs

# Deployer uniquement le dashboard des metriques
./deploy-grafana-dashboard.sh metrics
```

---

## Configuration

### Fichiers

| Fichier | Description |
|---------|-------------|
| `grafana-dashboard-rhdemo-logs.json` | Dashboard Loki (logs) |
| `grafana-dashboard-rhdemo-metrics.json` | Dashboard Prometheus (metriques) |
| `helm/observability/grafana-values.yaml` | Configuration Grafana |

### Datasources

| Datasource | Type | UID | URL |
|------------|------|-----|-----|
| Loki | loki | `loki` | `http://loki-gateway:80` |
| Prometheus | prometheus | `prometheus` | `http://prometheus-kube-prometheus-prometheus.monitoring.svc:9090` |

### Sidecar Dashboard

Le chart Helm Grafana inclut un container sidecar (`grafana-sc-dashboard`) qui :
- Surveille tous les ConfigMaps avec le label `grafana_dashboard=1`
- Ecrit automatiquement les dashboards dans `/tmp/dashboards/`
- Declenche un rechargement automatique dans Grafana
- Permet l'ajout/modification de dashboards sans redemarrage

### Namespace cible

Les dashboards interrogent le namespace : `rhdemo-stagingkub`

---

## Requetes

### Requetes LogQL (Loki)

```logql
# Tous les logs de l'application
{namespace="rhdemo-stagingkub", app="rhdemo-app"}

# Logs d'erreurs uniquement
{namespace="rhdemo-stagingkub", app="rhdemo-app"} |= "ERROR"

# Rate d'erreurs par minute
sum(count_over_time({namespace="rhdemo-stagingkub", app="rhdemo-app"} |= "ERROR" [1m]))

# Volume de logs par application
sum by (app) (rate({namespace="rhdemo-stagingkub"}[5m]))
```

### Requetes PromQL (Prometheus)

```promql
# CPU par pod (pourcentage)
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="rhdemo-stagingkub", container!="", container!="POD"}[5m])) * 100

# Memoire par pod (MB)
sum by (pod) (container_memory_working_set_bytes{namespace="rhdemo-stagingkub", container!="", container!="POD"}) / 1024 / 1024

# Reseau RX (bytes/sec)
sum(rate(container_network_receive_bytes_total{namespace="rhdemo-stagingkub", pod=~"rhdemo-app-.*"}[5m]))

# Utilisation disque PVC (pourcentage)
(kubelet_volume_stats_used_bytes{namespace="rhdemo-stagingkub"}) / (kubelet_volume_stats_capacity_bytes{namespace="rhdemo-stagingkub"}) * 100

# Nombre de restarts
sum(increase(kube_pod_container_status_restarts_total{namespace="rhdemo-stagingkub"}[1h]))

# Resource limits/requests
kube_pod_container_resource_limits{namespace="rhdemo-stagingkub", resource="cpu"}
kube_pod_container_resource_requests{namespace="rhdemo-stagingkub", resource="memory"}
```

---

## Acces

Une fois deployes, les dashboards sont accessibles via :

**URL** : https://grafana.stagingkub.local

**Login** : admin / (voir mot de passe dans `helm/observability/grafana-values.yaml`)

Les dashboards apparaitront automatiquement dans la liste :
- **rhDemo - Logs Application**
- **rhDemo - Metriques Pods**

---

## Troubleshooting

### Le dashboard n'apparait pas

1. Verifier que les ConfigMaps existent :
   ```bash
   kubectl get configmap -n loki-stack | grep grafana-dashboard
   ```

2. Verifier les labels :
   ```bash
   kubectl get configmap grafana-dashboard-rhdemo -n loki-stack -o yaml | grep labels -A 5
   kubectl get configmap grafana-dashboard-rhdemo-metrics -n loki-stack -o yaml | grep labels -A 5
   ```

   Doit contenir : `grafana_dashboard: "1"`

3. Verifier les logs du sidecar Grafana :
   ```bash
   kubectl logs -n loki-stack deployment/grafana -c grafana-sc-dashboard
   ```

### Les graphiques affichent "No Data"

#### Pour les logs (Loki)

1. Verifier que Loki est accessible :
   ```bash
   kubectl get pods -n loki-stack | grep loki
   ```

2. Verifier que des logs sont collectes :
   ```bash
   kubectl logs -n rhdemo-stagingkub deployment/rhdemo-app --tail=10
   ```

#### Pour les metriques (Prometheus)

1. Verifier que Prometheus est accessible :
   ```bash
   kubectl get pods -n monitoring | grep prometheus
   ```

2. Verifier que les metriques sont collectees :
   ```bash
   kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
   # Ouvrir http://localhost:9090/targets
   ```

3. Tester une requete dans Prometheus :
   ```promql
   container_cpu_usage_seconds_total{namespace="rhdemo-stagingkub"}
   ```

### Erreur "datasource not found"

Les dashboards referencent les datasources par leur UID. Verifier :

```bash
# Datasource Loki
kubectl get configmap -n loki-stack -l grafana_datasource=1 -o yaml | grep -A 20 "datasources.yaml"

# Datasource Prometheus
kubectl get configmap grafana-datasource-prometheus -n loki-stack -o yaml
```

Si les UIDs ne correspondent pas, reinstaller la stack :

```bash
./install-observability.sh
```

---

## Personnalisation

Pour modifier un dashboard :

1. Editer le fichier JSON correspondant :
   - `grafana-dashboard-rhdemo-logs.json` pour les logs
   - `grafana-dashboard-rhdemo-metrics.json` pour les metriques

2. Redeployer :
   ```bash
   ./deploy-grafana-dashboard.sh
   ```

Alternativement, depuis l'interface Grafana :
1. Ouvrir le dashboard
2. Faire les modifications
3. Exporter le JSON (Share > Export > Save to file)
4. Remplacer le contenu du fichier JSON
5. Redeployer

**Note** : Les dashboards provisionnes sont en lecture seule dans Grafana. Pour les modifier directement dans l'interface, il faut les dupliquer (Save As).
