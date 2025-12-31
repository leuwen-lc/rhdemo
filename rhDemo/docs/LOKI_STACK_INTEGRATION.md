# INTÉGRATION LOKI STACK - ENVIRONMENT STAGINGKUB

**Date:** 31 décembre 2025
**Version:** 2.0 (Charts Modernes)
**Environnement:** stagingkub (Kubernetes KinD)

**⚠️ Sécurité:** Consultez [/infra/stagingkub/SECURITY.md](../infra/stagingkub/SECURITY.md) pour les bonnes pratiques de configuration sécurisée.

---

## TABLE DES MATIÈRES

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture](#2-architecture)
3. [Prérequis](#3-prérequis)
4. [Installation](#4-installation)
5. [Configuration](#5-configuration)
6. [Accès et Utilisation](#6-accès-et-utilisation)
7. [Queries LogQL Utiles](#7-queries-logql-utiles)
8. [Dashboards Grafana](#8-dashboards-grafana)
9. [Troubleshooting](#9-troubleshooting)
10. [Maintenance](#10-maintenance)

---

## 1. VUE D'ENSEMBLE

### 1.1 Objectif

Déployer une stack de collecte de logs centralisée pour l'environnement stagingkub avec:
- **Promtail**: Agent de collecte des logs (DaemonSet)
- **Loki**: Système d'agrégation et indexation (StatefulSet)
- **Grafana**: Interface de visualisation et recherche

### 1.2 Stack PLG (Promtail + Loki + Grafana)

**Promtail** collecte les logs de tous les pods → **Loki** les stocke et indexe → **Grafana** permet la recherche et visualisation.

**Charts utilisés (modernes):**
- `grafana/loki` v6.x (mode SingleBinary)
- `grafana/promtail` v6.x
- `grafana/grafana` v8.x

### 1.3 Bénéfices

✅ Logs centralisés de tous les composants (rhDemo, Keycloak, PostgreSQL)
✅ Recherche rapide avec LogQL (langage type PromQL)
✅ Rétention configurable des logs
✅ Faible consommation ressources (comparé à ELK stack)
✅ Interface Grafana familière
✅ Pas de schéma rigide (indexation par labels uniquement)

---

## 2. ARCHITECTURE

### 2.1 Composants Déployés

```
┌─────────────────────────────────────────────────────────────┐
│  Namespace: loki-stack                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Promtail (DaemonSet)                                │  │
│  │ - 1 pod par node (KinD: 1 node control-plane)      │  │
│  │ - Lit /var/log/pods/**/*.log                       │  │
│  │ - Envoie à Loki via HTTP (port 3100)              │  │
│  │ - CPU: 100m / Memory: 128Mi                        │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       ↓                                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Loki (StatefulSet, replicas: 1)                    │  │
│  │ - Mode: SingleBinary                               │  │
│  │ - Service: loki-gateway:80 (ClusterIP)            │  │
│  │ - PVC: loki-data (5Gi, ReadWriteOnce)             │  │
│  │ - Stockage: filesystem (tsdb, schema v13)         │  │
│  │ - Rétention: 168h (7 jours par défaut)            │  │
│  │ - CPU: 250m / Memory: 256Mi                        │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       ↓                                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Grafana (Deployment, replicas: 1)                  │  │
│  │ - Service: grafana:80 (ClusterIP)                  │  │
│  │ - Ingress: grafana.stagingkub.local                │  │
│  │ - DataSource: Loki (http://loki-gateway:80)       │  │
│  │ - Admin: admin / rhDemoAdmin2025                   │  │
│  │ - CPU: 250m / Memory: 256Mi                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Labels Collectés

Promtail enrichit automatiquement les logs avec ces labels:

| Label | Exemple | Description |
|-------|---------|-------------|
| `namespace` | `rhdemo-stagingkub` | Namespace Kubernetes |
| `pod` | `rhdemo-app-7d8f9c6b-x5z2k` | Nom du pod |
| `container` | `rhdemo-app` | Nom du container |
| `app` | `rhdemo-app` | Label app |
| `job` | `rhdemo-stagingkub/rhdemo-app` | Namespace/app |
| `stream` | `stdout` ou `stderr` | Stream de sortie |

### 2.3 Flux de Données

```
[rhdemo-app Pod] → stdout/stderr → /var/log/pods/rhdemo-stagingkub_rhdemo-app-xxx/
                                                    ↓
                                          [Promtail DaemonSet]
                                                    ↓
                                           Enrichissement labels
                                                    ↓
                                          HTTP POST → [Loki Gateway:80]
                                                    ↓
                                            Indexation + Stockage
                                                    ↓
                                          [Grafana Explore] ← Requête LogQL
```

---

## 3. PRÉREQUIS

### 3.1 Cluster Kubernetes

- ✅ Cluster KinD `rhdemo` démarré
- ✅ Namespace `rhdemo-stagingkub` existant
- ✅ Ingress Nginx Controller installé

### 3.2 Outils Locaux

```bash
# Vérifier installations
helm version  # v3.x requis
kubectl version --client  # v1.25+ recommandé
kind version  # v0.20+
```

### 3.3 Ressources Disponibles

**Ressources totales requises pour Loki Stack:**

| Composant | CPU Request | Memory Request | Storage |
|-----------|-------------|----------------|---------|
| Promtail | 100m | 128Mi | - |
| Loki | 250m | 256Mi | 5Gi (PVC) |
| Grafana | 250m | 256Mi | - |
| **TOTAL** | **600m** | **640Mi** | **5Gi** |

**Vérifier ressources disponibles:**

```bash
kubectl top nodes  # Si metrics-server installé
# OU
kubectl describe nodes rhdemo-control-plane | grep -A 5 "Allocated resources"
```

### 3.4 DNS Local

```bash
# Ajouter à /etc/hosts
echo "127.0.0.1 grafana.stagingkub.local" | sudo tee -a /etc/hosts
```

---

## 4. INSTALLATION

### 4.1 Installation Automatique (Recommandée)

**⚠️ PRÉREQUIS SÉCURITÉ: Configurer le mot de passe Grafana**

Avant d'exécuter le script, vous **devez** configurer un mot de passe fort:

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub

# Générer un mot de passe fort
PASSWORD=$(openssl rand -base64 32)
echo "Mot de passe généré: $PASSWORD"

# Éditer grafana-values.yaml et remplacer adminPassword: "" par le mot de passe
sed -i "s/adminPassword: \"\"/adminPassword: \"$PASSWORD\"/" grafana-values.yaml

# IMPORTANT: Sauvegarder ce mot de passe dans un gestionnaire de mots de passe
```

**Script d'installation clé en main:**

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./install-loki-modern.sh
```

Ce script effectue automatiquement:
- ✅ Vérification des prérequis
- ✅ Validation de la configuration du mot de passe
- ✅ Ajout du repository Helm Grafana
- ✅ Création du namespace `loki-stack`
- ✅ Génération du certificat TLS
- ✅ Installation de Loki (mode SingleBinary)
- ✅ Installation de Promtail
- ✅ Installation de Grafana
- ✅ Configuration DNS dans `/etc/hosts`

**Durée:** ~2-3 minutes

Pour un guide rapide, voir: [LOKI_QUICKSTART.md](../infra/stagingkub/LOKI_QUICKSTART.md)

### 4.2 Installation Manuelle

#### 4.2.1 Ajouter le Repository Helm Grafana

```bash
# Ajouter le repo officiel Grafana
helm repo add grafana https://grafana.github.io/helm-charts

# Mettre à jour
helm repo update

# Vérifier charts disponibles
helm search repo grafana/loki
helm search repo grafana/promtail
helm search repo grafana/grafana
```

**Output attendu:**
```
NAME                    CHART VERSION   APP VERSION     DESCRIPTION
grafana/loki            6.x.x           3.x.x           Loki: like Prometheus, but for logs
grafana/promtail        6.x.x           3.x.x           Promtail log collector
grafana/grafana         8.x.x           11.x.x          The open observability platform
```

#### 4.2.2 Créer le Namespace

```bash
# Créer namespace dédié pour Loki Stack
kubectl create namespace loki-stack

# Vérifier
kubectl get namespaces | grep loki
```

#### 4.2.3 Créer les Fichiers de Configuration

Les fichiers de configuration sont déjà présents dans le projet:

**Loki:** `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/loki-modern-values.yaml`

```yaml
# Configuration Loki moderne (chart grafana/loki)
# Chart: grafana/loki v6.x
deploymentMode: SingleBinary

loki:
  auth_enabled: false
  commonConfig:
    replication_factor: 1
  storage:
    type: 'filesystem'
  schemaConfig:
    configs:
      - from: "2024-01-01"
        store: tsdb
        object_store: filesystem
        schema: v13
        index:
          prefix: loki_index_
          period: 24h
  limits_config:
    retention_period: 168h  # 7 jours
    ingestion_rate_mb: 10
    ingestion_burst_size_mb: 20

singleBinary:
  replicas: 1
  resources:
    requests:
      cpu: 250m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi
  persistence:
    enabled: true
    size: 5Gi

# Services désactivés (mode SingleBinary)
read:
  replicas: 0
write:
  replicas: 0
backend:
  replicas: 0
```

**Promtail:** `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/promtail-values.yaml`

```yaml
# Configuration Promtail
# Chart: grafana/promtail v6.x
config:
  clients:
    - url: http://loki-gateway/loki/api/v1/push
      tenant_id: ""
  positions:
    filename: /tmp/positions.yaml
  snippets:
    scrapeConfigs: |
      - job_name: kubernetes-pods
        kubernetes_sd_configs:
          - role: pod
            namespaces:
              names:
                - rhdemo-stagingkub
        pipeline_stages:
          - cri: {}
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_label_app]
            action: keep
            regex: .+
          - source_labels: [__meta_kubernetes_namespace]
            target_label: namespace
          - source_labels: [__meta_kubernetes_pod_name]
            target_label: pod
          - source_labels: [__meta_kubernetes_pod_container_name]
            target_label: container
          - source_labels: [__meta_kubernetes_pod_label_app]
            target_label: app

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 200m
    memory: 256Mi
```

**Grafana:** `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/grafana-values.yaml`

```yaml
# Configuration Grafana
# Chart: grafana/grafana v8.x

adminUser: admin
# ⚠️ SÉCURITÉ: Définir un mot de passe fort avant installation
adminPassword: ""  # TODO: Renseigner un mot de passe fort (openssl rand -base64 32)

resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi

ingress:
  enabled: true
  ingressClassName: nginx
  hosts:
    - grafana.stagingkub.local
  tls:
    - secretName: grafana-tls-cert
      hosts:
        - grafana.stagingkub.local

datasources:
  datasources.yaml:
    apiVersion: 1
    datasources:
      - name: Loki
        type: loki
        access: proxy
        url: http://loki-gateway:80
        isDefault: true
        jsonData:
          maxLines: 1000

grafana.ini:
  server:
    domain: grafana.stagingkub.local
    root_url: https://grafana.stagingkub.local
  analytics:
    reporting_enabled: false
    check_for_updates: false
  users:
    allow_sign_up: false
```

**⚠️ Avant de continuer:** Vous devez configurer le mot de passe Grafana:

```bash
# Générer un mot de passe fort
PASSWORD=$(openssl rand -base64 32)

# Éditer grafana-values.yaml et remplacer adminPassword: ""
sed -i "s/adminPassword: \"\"/adminPassword: \"$PASSWORD\"/" grafana-values.yaml

# Sauvegarder le mot de passe dans un gestionnaire de mots de passe
echo "Mot de passe Grafana: $PASSWORD"
```

#### 4.2.4 Générer le Certificat TLS pour Grafana

```bash
# Créer répertoire temporaire
TMP=$(mktemp -d)

# Générer certificat self-signed
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout $TMP/tls.key \
  -out $TMP/tls.crt \
  -subj "/CN=grafana.stagingkub.local/O=RHDemo"

# Créer le secret dans Kubernetes
kubectl create secret tls grafana-tls-cert \
  --cert=$TMP/tls.crt \
  --key=$TMP/tls.key \
  -n loki-stack

# Nettoyer
rm -rf $TMP
```

#### 4.2.5 Installer les Charts

```bash
# Installer Loki (mode SingleBinary)
helm upgrade --install loki grafana/loki \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/loki-modern-values.yaml \
  --wait --timeout 3m

# Installer Promtail
helm upgrade --install promtail grafana/promtail \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/promtail-values.yaml \
  --wait --timeout 2m

# Installer Grafana
helm upgrade --install grafana grafana/grafana \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/grafana-values.yaml \
  --wait --timeout 3m

# Vérifier l'installation
helm list -n loki-stack
```

**Output attendu:**
```
NAME            NAMESPACE       REVISION        STATUS          CHART                   APP VERSION
loki            loki-stack      1               deployed        loki-6.x.x              3.x.x
promtail        loki-stack      1               deployed        promtail-6.x.x          3.x.x
grafana         loki-stack      1               deployed        grafana-8.x.x           11.x.x
```

#### 4.2.6 Vérifier le Déploiement

```bash
# Vérifier tous les pods
kubectl get pods -n loki-stack

# Output attendu:
# NAME                            READY   STATUS    RESTARTS   AGE
# loki-0                          1/1     Running   0          2m
# promtail-xxxxx                  1/1     Running   0          2m
# grafana-xxxxx                   1/1     Running   0          2m

# Vérifier les services
kubectl get svc -n loki-stack

# Output attendu:
# NAME              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
# loki-gateway      ClusterIP   10.96.xxx.xxx    <none>        80/TCP     2m
# grafana           ClusterIP   10.96.xxx.xxx    <none>        80/TCP     2m

# Vérifier l'ingress
kubectl get ingress -n loki-stack

# Vérifier le PVC
kubectl get pvc -n loki-stack
```

#### 4.2.7 Vérifier la Collecte des Logs

```bash
# Port-forward Loki Gateway pour tester
kubectl port-forward -n loki-stack svc/loki-gateway 3100:80 &

# Interroger Loki directement (via API)
curl -G -s "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query={namespace="rhdemo-stagingkub"}' \
  | jq '.data.result'

# Si des logs sont présents, vous verrez un JSON avec les streams

# Vérifier les labels disponibles
curl -s "http://localhost:3100/loki/api/v1/labels" | jq

# Arrêter le port-forward
kill %1
```

---

## 5. CONFIGURATION

### 5.1 Ajouter Grafana au DNS Local

```bash
# Déjà ajouté en prérequis, vérifier
grep grafana.stagingkub.local /etc/hosts

# Si absent:
echo "127.0.0.1 grafana.stagingkub.local" | sudo tee -a /etc/hosts
```

### 5.2 Ajuster la Rétention des Logs

Par défaut: **7 jours** (168h).

**Pour modifier:**

Éditer `loki-modern-values.yaml`:

```yaml
loki:
  limits_config:
    retention_period: 336h  # 14 jours au lieu de 7
```

**Appliquer:**

```bash
helm upgrade loki grafana/loki \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/loki-modern-values.yaml
```

### 5.3 Augmenter les Ressources (si nécessaire)

Si vous avez beaucoup de logs (>100MB/jour):

```yaml
# loki-modern-values.yaml
singleBinary:
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 1Gi
  persistence:
    size: 10Gi  # Augmenter stockage

loki:
  limits_config:
    ingestion_rate_mb: 20
    ingestion_burst_size_mb: 40
```

### 5.4 Ajouter des Dashboards Pré-configurés

**Via Grafana UI** (après installation):

1. Aller sur https://grafana.stagingkub.local
2. Login: `admin` / (votre mot de passe configuré)
3. Dashboards → Import
4. Utiliser ID: `13639` (Logs / App Dashboard)
5. Sélectionner datasource: Loki

**Via ConfigMap** (automatique):

Un dashboard pré-configuré est disponible dans le projet:
- `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/grafana-dashboard-rhdemo.json`

Pour l'importer:
1. Grafana → Dashboards → Import
2. Upload le fichier JSON
3. Sélectionner datasource: Loki
4. Save

Le dashboard inclut:
- Logs en temps réel des différents composants
- Graphiques d'erreurs par minute
- Top 10 des erreurs les plus fréquentes
- Volume de logs par application

---

## 6. ACCÈS ET UTILISATION

### 6.1 Accéder à Grafana

**URL:** https://grafana.stagingkub.local

**Credentials:**
- Username: `admin`
- Password: (mot de passe configuré dans grafana-values.yaml)

**Navigation:**
1. Menu → Explore
2. Sélectionner datasource: **Loki**
3. Construire requête LogQL

### 6.2 Interface Grafana Explore

**Éléments clés:**

| Élément | Description |
|---------|-------------|
| **Datasource** | Loki (par défaut) |
| **Query Editor** | Construire requête LogQL |
| **Log Browser** | Labels disponibles (namespace, pod, app, etc.) |
| **Time Range** | Sélecteur période (Last 5m, Last 1h, etc.) |
| **Live** | Tail logs en temps réel |
| **Log Details** | Clic sur une ligne → détails + labels |

### 6.3 Modes de Recherche

#### Mode Builder (Recommandé pour débuter)

1. Cliquer sur "Log browser"
2. Sélectionner labels:
   - `namespace` = `rhdemo-stagingkub`
   - `app` = `rhdemo-app`
3. Cliquer "Show logs"

#### Mode Code (LogQL avancé)

Écrire directement la requête LogQL:

```logql
{namespace="rhdemo-stagingkub", app="rhdemo-app"}
```

---

## 7. QUERIES LOGQL UTILES

### 7.1 Logs par Composant

**Tous les logs rhDemo app:**
```logql
{namespace="rhdemo-stagingkub", app="rhdemo-app"}
```

**Logs Keycloak uniquement:**
```logql
{namespace="rhdemo-stagingkub", app="keycloak"}
```

**Logs PostgreSQL rhDemo:**
```logql
{namespace="rhdemo-stagingkub", app="postgresql-rhdemo"}
```

**Logs PostgreSQL Keycloak:**
```logql
{namespace="rhdemo-stagingkub", app="postgresql-keycloak"}
```

### 7.2 Filtres par Mot-clé

**Rechercher "ERROR":**
```logql
{namespace="rhdemo-stagingkub"} |= "ERROR"
```

**Rechercher "Exception" (case-insensitive):**
```logql
{namespace="rhdemo-stagingkub"} |~ "(?i)exception"
```

**Exclure logs contenant "health":**
```logql
{namespace="rhdemo-stagingkub"} != "health"
```

**Logs contenant "SQL" MAIS PAS "SELECT":**
```logql
{namespace="rhdemo-stagingkub"} |= "SQL" != "SELECT"
```

### 7.3 Logs d'Erreurs Spring Boot

**Stack traces Java:**
```logql
{namespace="rhdemo-stagingkub", app="rhdemo-app"} |~ "Exception|Error"
```

**Logs niveau ERROR:**
```logql
{namespace="rhdemo-stagingkub", app="rhdemo-app"} |= "ERROR"
```

**Logs d'une classe spécifique:**
```logql
{namespace="rhdemo-stagingkub", app="rhdemo-app"} |~ "EmployeService"
```

### 7.4 Logs d'Authentification Keycloak

**Logins réussis:**
```logql
{namespace="rhdemo-stagingkub", app="keycloak"} |~ "Login|authenticated"
```

**Échecs d'authentification:**
```logql
{namespace="rhdemo-stagingkub", app="keycloak"} |~ "Invalid|failed.*login"
```

**Activité utilisateur "admil":**
```logql
{namespace="rhdemo-stagingkub", app="keycloak"} |~ "admil"
```

### 7.5 Logs PostgreSQL

**Requêtes lentes (>1s):**
```logql
{namespace="rhdemo-stagingkub", app=~"postgresql-.*"} |~ "duration.*[1-9][0-9]{3,} ms"
```

**Erreurs SQL:**
```logql
{namespace="rhdemo-stagingkub", app=~"postgresql-.*"} |~ "ERROR"
```

**Connexions/déconnexions:**
```logql
{namespace="rhdemo-stagingkub", app=~"postgresql-.*"} |~ "connection.*authorized|disconnection"
```

### 7.6 Agrégations et Métriques

**Compter les logs ERROR par minute:**
```logql
sum(count_over_time({namespace="rhdemo-stagingkub"} |= "ERROR" [1m]))
```

**Rate de logs par app:**
```logql
sum by (app) (rate({namespace="rhdemo-stagingkub"}[5m]))
```

**Top 10 pods par volume de logs:**
```logql
topk(10, sum by (pod) (count_over_time({namespace="rhdemo-stagingkub"}[1h])))
```

### 7.7 Logs en Temps Réel (Live Tail)

**Bouton "Live" dans Grafana Explore** OU:

```bash
# Via CLI (logcli)
logcli query --tail '{namespace="rhdemo-stagingkub", app="rhdemo-app"}'
```

---

## 8. DASHBOARDS GRAFANA

### 8.1 Dashboard rhDemo - Logs d'Application

**Créer manuellement:**

1. Grafana → Dashboards → New Dashboard
2. Add Panel → Logs
3. Query: `{namespace="rhdemo-stagingkub", app="rhdemo-app"}`
4. Options:
   - Visualization: Logs
   - Time range: Last 6 hours
   - Show labels: app, pod, container
   - Dedupe: exact
5. Save Dashboard: "rhDemo Application Logs"

**Panels recommandés:**

| Panel | Query | Type |
|-------|-------|------|
| **Logs Stream** | `{namespace="rhdemo-stagingkub", app="rhdemo-app"}` | Logs |
| **Error Rate** | `sum(rate({namespace="rhdemo-stagingkub", app="rhdemo-app"} \|= "ERROR" [5m]))` | Graph |
| **Top Errors** | `topk(10, count_over_time({namespace="rhdemo-stagingkub", app="rhdemo-app"} \|= "ERROR" [1h]))` | Table |
| **Logs by Level** | `sum by (level) (count_over_time({namespace="rhdemo-stagingkub", app="rhdemo-app"} \| json [5m]))` | Pie Chart |

### 8.2 Dashboard Keycloak - Logs d'Authentification

**Query principale:**
```logql
{namespace="rhdemo-stagingkub", app="keycloak"}
```

**Panels:**

| Panel | Query | Métrique |
|-------|-------|----------|
| **Login Rate** | `sum(rate({app="keycloak"} \|~ "Login" [5m]))` | Logins/sec |
| **Failed Logins** | `sum(count_over_time({app="keycloak"} \|~ "failed.*login" [1h]))` | Total failures |
| **Active Users** | Extraction custom via `\| regexp "user=(?P<user>\\w+)"` | Unique users |

### 8.3 Dashboard PostgreSQL - Logs Database

**Query principale:**
```logql
{namespace="rhdemo-stagingkub", app=~"postgresql-.*"}
```

**Panels:**

| Panel | Query | Métrique |
|-------|-------|----------|
| **Slow Queries** | `{app=~"postgresql-.*"} \|~ "duration.*[1-9][0-9]{3,} ms"` | Requêtes >1s |
| **Connection Pool** | Extraction connections actives | Connections |
| **Error Log** | `{app=~"postgresql-.*"} \|= "ERROR"` | Erreurs SQL |

### 8.4 Dashboard Consolidé - Vue d'Ensemble

**Variables:**

Créer variables pour filtrer dynamiquement:

| Variable | Query | Type |
|----------|-------|------|
| `$app` | `label_values(app)` | Multi-select |
| `$pod` | `label_values({namespace="rhdemo-stagingkub"}, pod)` | Multi-select |

**Query utilisant variables:**
```logql
{namespace="rhdemo-stagingkub", app=~"$app", pod=~"$pod"}
```

### 8.5 Exporter/Importer Dashboard

**Exporter:**

1. Dashboard → Settings → JSON Model
2. Copier JSON
3. Sauvegarder dans `/infra/stagingkub/grafana-dashboards/rhdemo-logs.json`

**Importer:**

1. Dashboards → Import
2. Upload JSON file
3. Sélectionner datasource: Loki

---

## 9. TROUBLESHOOTING

### 9.1 Loki ne Démarre Pas

**Symptôme:** Pod `loki-0` en CrashLoopBackOff

**Vérification:**

```bash
kubectl logs -n loki-stack loki-0
kubectl describe pod -n loki-stack loki-0
```

**Causes fréquentes:**

| Erreur | Solution |
|--------|----------|
| "permission denied /loki/chunks" | Vérifier PVC permissions: `securityContext.fsGroup: 10001` |
| "out of memory" | Augmenter memory limits dans values.yaml |
| "cannot bind :3100" | Port déjà utilisé (vérifier autre Loki) |

**Fix permissions PVC:**

```bash
# Ajouter à loki-stack-values.yaml
loki:
  podSecurityContext:
    fsGroup: 10001
  containerSecurityContext:
    runAsUser: 10001
    runAsNonRoot: true
```

### 9.2 Promtail ne Collecte Pas de Logs

**Symptôme:** Aucun log dans Grafana

**Vérification:**

```bash
# Logs Promtail
kubectl logs -n loki-stack -l app=promtail

# Vérifier que Promtail trouve des pods
kubectl logs -n loki-stack -l app=promtail | grep "discovered"
```

**Causes fréquentes:**

| Problème | Solution |
|----------|----------|
| Namespace filter trop strict | Vérifier `scrape_configs.relabel_configs` dans values.yaml |
| Promtail ne peut pas lire /var/log/pods | Vérifier mountPath et hostPath dans DaemonSet |
| Logs en JSON non parsés | Ajouter pipeline stage `json` dans Promtail config |

**Vérifier collecte manuelle:**

```bash
# Exec dans Promtail
kubectl exec -n loki-stack -it loki-stack-promtail-xxxxx -- sh

# Lister logs accessibles
ls -la /var/log/pods/rhdemo-stagingkub*/

# Tail un log
tail -f /var/log/pods/rhdemo-stagingkub_rhdemo-app-*/rhdemo-app/*.log
```

### 9.3 Grafana - Datasource Loki Inaccessible

**Symptôme:** "Data source connected, but no labels received"

**Vérification:**

```bash
# Tester connexion depuis pod Grafana
kubectl exec -n loki-stack -it loki-stack-grafana-xxxxx -- sh

# Curl Loki
wget -O- http://loki:3100/ready

# Tester API labels
wget -O- http://loki:3100/loki/api/v1/labels
```

**Solution:**

Vérifier que le service `loki` existe:

```bash
kubectl get svc -n loki-stack loki

# Output attendu:
# NAME   TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
# loki   ClusterIP   10.96.xxx.xxx   <none>        3100/TCP   5m
```

### 9.4 Ingress Grafana ne Fonctionne Pas

**Symptôme:** `curl https://grafana.stagingkub.local` timeout

**Vérification:**

```bash
# Vérifier Ingress
kubectl get ingress -n loki-stack

# Vérifier annotations
kubectl describe ingress -n loki-stack loki-stack-grafana

# Vérifier service Grafana
kubectl get svc -n loki-stack loki-stack-grafana
```

**Solutions:**

1. **Vérifier Nginx Ingress Controller:**
   ```bash
   kubectl get pods -n ingress-nginx
   ```

2. **Vérifier TLS secret:**
   ```bash
   kubectl get secret -n loki-stack grafana-tls-cert
   ```

3. **Port-forward temporaire:**
   ```bash
   kubectl port-forward -n loki-stack svc/loki-stack-grafana 3000:80
   # Accéder: http://localhost:3000
   ```

### 9.5 Logs Trop Volumineux (PVC Plein)

**Symptôme:** Loki ne peut plus écrire

**Vérification:**

```bash
# Vérifier utilisation PVC
kubectl exec -n loki-stack loki-0 -- df -h /loki

# Output:
# Filesystem      Size  Used Avail Use% Mounted on
# /dev/xxx        5.0G  4.9G  100M  98% /loki
```

**Solutions:**

1. **Augmenter PVC (si storage class supporte):**
   ```bash
   kubectl patch pvc -n loki-stack loki-data \
     -p '{"spec":{"resources":{"requests":{"storage":"10Gi"}}}}'
   ```

2. **Réduire rétention:**
   ```yaml
   # loki-modern-values.yaml
   loki:
     limits_config:
       retention_period: 72h  # 3 jours au lieu de 7
   ```

3. **Forcer compaction:**
   ```bash
   # Redémarrer Loki (force compaction)
   kubectl rollout restart statefulset -n loki-stack loki
   ```

### 9.6 Requêtes LogQL Lentes

**Symptôme:** Timeout ou >10s pour afficher logs

**Optimisations:**

1. **Limiter time range:**
   - Utiliser "Last 1h" au lieu de "Last 24h"

2. **Ajouter plus de labels:**
   ```logql
   # LENT (scan tous namespaces)
   {app="rhdemo-app"}

   # RAPIDE (scan 1 namespace)
   {namespace="rhdemo-stagingkub", app="rhdemo-app"}
   ```

3. **Augmenter ressources Loki:**
   ```yaml
   # loki-modern-values.yaml
   singleBinary:
     resources:
       limits:
         cpu: 1000m
         memory: 1Gi
   ```

---

## 10. MAINTENANCE

### 10.1 Backup des Logs

**Stratégie:**

Loki stocke dans PVC `loki-data`. Pour backup:

```bash
# Créer backup du PVC
kubectl exec -n loki-stack loki-0 -- tar czf /tmp/loki-backup.tar.gz /loki/chunks /loki/boltdb-shipper-active

# Copier localement
kubectl cp loki-stack/loki-0:/tmp/loki-backup.tar.gz ./loki-backup-$(date +%Y%m%d).tar.gz

# Nettoyer
kubectl exec -n loki-stack loki-0 -- rm /tmp/loki-backup.tar.gz
```

**Restauration:**

```bash
# Copier backup dans pod
kubectl cp ./loki-backup-20251230.tar.gz loki-stack/loki-0:/tmp/

# Arrêter Loki
kubectl scale statefulset -n loki-stack loki --replicas=0

# Restaurer
kubectl exec -n loki-stack loki-0 -- tar xzf /tmp/loki-backup-20251230.tar.gz -C /

# Redémarrer Loki
kubectl scale statefulset -n loki-stack loki --replicas=1
```

### 10.2 Mise à Jour Loki Stack

```bash
# Mettre à jour repo Helm
helm repo update

# Vérifier nouvelle version
helm search repo grafana/loki
helm search repo grafana/promtail
helm search repo grafana/grafana

# Upgrade Loki
helm upgrade loki grafana/loki \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/loki-modern-values.yaml

# Upgrade Promtail
helm upgrade promtail grafana/promtail \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/promtail-values.yaml

# Upgrade Grafana
helm upgrade grafana grafana/grafana \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/grafana-values.yaml

# Vérifier rollout
kubectl rollout status statefulset -n loki-stack loki
kubectl rollout status daemonset -n loki-stack promtail
kubectl rollout status deployment -n loki-stack grafana
```

### 10.3 Rotation des Logs (Automatique)

**Configuration actuelle:** 7 jours (défini dans loki-modern-values.yaml)

Loki supprime automatiquement les logs >7 jours via:
- `loki.limits_config.retention_period: 168h`

En mode SingleBinary, la compaction est gérée automatiquement par le composant unique.

**Vérifier compaction:**

```bash
# Logs Loki (rechercher compaction)
kubectl logs -n loki-stack loki-0 | grep -i compactor
```

### 10.4 Monitoring de Loki (avec Prometheus)

**Si Prometheus déployé:**

Loki expose métriques sur `/metrics`:

```yaml
# ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: loki
  namespace: loki-stack
spec:
  selector:
    matchLabels:
      app: loki
  endpoints:
    - port: http-metrics
      interval: 30s
```

**Métriques clés:**

| Métrique | Description |
|----------|-------------|
| `loki_ingester_memory_chunks` | Chunks en mémoire |
| `loki_ingester_received_bytes_total` | Bytes reçus total |
| `loki_request_duration_seconds` | Latence requêtes |
| `loki_distributor_lines_received_total` | Lignes de logs reçues |

### 10.5 Désinstallation

```bash
# Désinstaller les Helm releases
helm uninstall loki -n loki-stack
helm uninstall promtail -n loki-stack
helm uninstall grafana -n loki-stack

# Supprimer PVC (ATTENTION: perte de données)
kubectl delete pvc -n loki-stack --all

# Supprimer namespace
kubectl delete namespace loki-stack

# Retirer du DNS
sudo sed -i '/grafana.stagingkub.local/d' /etc/hosts
```

---

## 11. RESSOURCES UTILES

### Documentation Officielle

- **Loki:** https://grafana.com/docs/loki/latest/
- **Promtail:** https://grafana.com/docs/loki/latest/send-data/promtail/
- **LogQL:** https://grafana.com/docs/loki/latest/query/
- **Helm Charts:**
  - Loki: https://github.com/grafana/helm-charts/tree/main/charts/loki
  - Promtail: https://github.com/grafana/helm-charts/tree/main/charts/promtail
  - Grafana: https://github.com/grafana/helm-charts/tree/main/charts/grafana

### Tutoriels

- [Getting Started with Loki](https://grafana.com/docs/loki/latest/getting-started/)
- [LogQL Cheat Sheet](https://megamorf.gitlab.io/cheat-sheets/loki/)
- [Grafana Loki Workshops](https://github.com/grafana/loki/tree/main/docs/workshops)

### Communauté

- GitHub: https://github.com/grafana/loki
- Slack: https://slack.grafana.com/
- Forum: https://community.grafana.com/

---

**Fin du document**

**Auteur:** Claude Code
**Version:** 2.0 (Charts Modernes)
**Date:** 31 décembre 2025

---

## NOTES DE MIGRATION

### Version 2.0 - Migration vers Charts Modernes

Cette version utilise les charts Helm modernes séparés au lieu du chart monolithique `loki-stack` (deprecated):

**Changements principaux:**
- ✅ Chart `grafana/loki-stack` → `grafana/loki` v6.x + `grafana/promtail` v6.x + `grafana/grafana` v8.x
- ✅ Architecture: SingleBinary mode pour Loki (au lieu de composants séparés)
- ✅ Schéma de stockage: tsdb + schema v13 (au lieu de boltdb-shipper + v11)
- ✅ Service Loki: `loki-gateway:80` (au lieu de `loki:3100`)
- ✅ Installation via script automatique: `install-loki-modern.sh`

**Fichiers de configuration:**
- `loki-modern-values.yaml` - Configuration Loki
- `promtail-values.yaml` - Configuration Promtail
- `grafana-values.yaml` - Configuration Grafana

**Guide rapide:** [LOKI_QUICKSTART.md](../infra/stagingkub/LOKI_QUICKSTART.md)
