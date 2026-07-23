# INTÉGRATION OBSERVABILITY STACK - ENVIRONMENT STAGINGKUB

**Date:** 22 janvier 2026
**Version:** 3.1 (Stack Complète: Prometheus + Loki + Métriques Spring Boot Actuator)
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
7. [Queries LogQL et PromQL](#7-queries-logql-et-promql)
8. [Dashboards Grafana](#8-dashboards-grafana)
9. [Troubleshooting](#9-troubleshooting)
10. [Maintenance](#10-maintenance)

---

## 1. VUE D'ENSEMBLE

### 1.1 Objectif

Déployer une stack d'observabilité complète pour l'environnement stagingkub avec:
- **Prometheus + Operator**: Collecte et stockage des métriques (métriques applicatives, infrastructure, bases de données)
- **Loki**: Système d'agrégation et indexation des logs
- **Alloy**: Agent de collecte des logs (DaemonSet)
- **Grafana**: Interface unifiée de visualisation (métriques + logs)

### 1.2 Stack Complète (Prometheus + Loki + Grafana)

**Architecture de collecte:**
- **Métriques**: Prometheus scrape les endpoints `/metrics` → Stocke dans TSDB → Grafana visualise
- **Logs**: Alloy collecte les logs → Loki les stocke et indexe → Grafana visualise

**Charts utilisés:**
- `prometheus-community/kube-prometheus-stack` (Prometheus + Operator + AlertManager)
- `grafana/loki` v6.x (mode SingleBinary)
- `grafana/alloy` v1.x
- `grafana/grafana` v8.x

### 1.3 Bénéfices

**Métriques (Prometheus):**
✅ Métriques temps réel de tous les composants Kubernetes
✅ Métriques bases de données PostgreSQL
✅ Alerting automatisé via AlertManager
✅ Détection automatique des PodMonitors/ServiceMonitors
✅ Retention 7 jours, storage 10Gi

**Logs (Loki):**
✅ Logs centralisés de tous les composants (rhDemo, Keycloak, PostgreSQL)
✅ Recherche rapide avec LogQL (langage type PromQL)
✅ Rétention configurable des logs
✅ Faible consommation ressources (comparé à ELK stack)
✅ Pas de schéma rigide (indexation par labels uniquement)

**Grafana (Visualisation unifiée):**
✅ Interface unique pour métriques ET logs
✅ Corrélation métriques/logs (même timeline)
✅ Dashboards pré-configurés (rhDemo Logs)
✅ Exploration interactive (Explore)

---

## 2. ARCHITECTURE

### 2.1 Composants Déployés

**Deux namespaces:**
- `monitoring`: Prometheus + Operator + AlertManager
- `loki-stack`: Loki + Alloy + Grafana

```
┌─────────────────────────────────────────────────────────────┐
│  Namespace: monitoring (MÉTRIQUES)                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Prometheus Operator (Deployment)                    │  │
│  │ - Gère automatiquement Prometheus/AlertManager      │  │
│  │ - Surveille les PodMonitors/ServiceMonitors        │  │
│  │ - CPU: 100m / Memory: 128Mi                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Prometheus Server (StatefulSet)                     │  │
│  │ - Service: prometheus-kube-prometheus-prometheus    │  │
│  │ - Port: 9090                                        │  │
│  │ - PVC: 10Gi (rétention 7j, 5GB max)               │  │
│  │ - Scrape interval: 30s                             │  │
│  │ - CPU: 200m / Memory: 512Mi                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ AlertManager (StatefulSet)                          │  │
│  │ - Gestion des alertes Prometheus                   │  │
│  │ - Port: 9093                                        │  │
│  │ - CPU: 50m / Memory: 64Mi                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Node Exporter (DaemonSet)                           │  │
│  │ - Métriques des nodes Kubernetes                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Kube State Metrics (Deployment)                     │  │
│  │ - Métriques des ressources Kubernetes              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Namespace: loki-stack (LOGS + VISUALISATION)               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Alloy (DaemonSet)                                   │  │
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
│  │ - Ingress: grafana-stagingkub.intra.leuwen-lc.fr (HTTPS)       │  │
│  │                                                     │  │
│  │ DataSources configurées:                           │  │
│  │ • Loki: http://loki-gateway:80                    │  │
│  │ • Prometheus: http://prometheus-kube-prometheus-  │  │
│  │               prometheus.monitoring.svc:9090       │  │
│  │                                                     │  │
│  │ - Admin: admin / (voir grafana-values.yaml)       │  │
│  │ - CPU: 250m / Memory: 256Mi                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Labels et Métriques Collectés

**Labels Logs (Loki via Alloy):**

Alloy enrichit automatiquement les logs avec ces labels:

| Label | Exemple | Description |
|-------|---------|-------------|
| `namespace` | `rhdemo-stagingkub` | Namespace Kubernetes |
| `pod` | `rhdemo-app-7d8f9c6b-x5z2k` | Nom du pod |
| `container` | `rhdemo-app` | Nom du container |
| `app` | `rhdemo-app` | Label app |
| `job` | `rhdemo-stagingkub/rhdemo-app` | Namespace/app |
| `stream` | `stdout` ou `stderr` | Stream de sortie |

**Métriques Prometheus:**

Prometheus collecte automatiquement via ServiceMonitors et PodMonitors:

| Source | Métriques Collectées | Configuration |
|--------|---------------------|---------------|
| **Node Exporter** | Métriques nodes (CPU, RAM, disque, réseau) | DaemonSet automatique |
| **Kube State Metrics** | État ressources K8s (pods, deployments, etc.) | Deployment automatique |
| **PostgreSQL** | Métriques PostgreSQL (connexions, requêtes, tables, cache) | Sidecar postgres_exporter avec collecteurs intégrés (`stat_statements`, `long_running_transactions`, `process_idle`) |
| **Application rhDemo** | Métriques Spring Boot Actuator (JVM, HTTP, HikariCP) | ServiceMonitor configuré automatiquement |

### 2.3 Flux de Données

**Flux Logs:**
```
[rhdemo-app Pod] → stdout/stderr → /var/log/pods/rhdemo-stagingkub_rhdemo-app-xxx/
                                                    ↓
                                          [Alloy DaemonSet]
                                                    ↓
                                           Enrichissement labels
                                                    ↓
                                          HTTP POST → [Loki Gateway:80]
                                                    ↓
                                            Indexation + Stockage
                                                    ↓
                                          [Grafana Explore] ← Requête LogQL
```

**Flux Métriques:**
```
[PostgreSQL Pod]      [Nodes]      [Pods K8s]
   :9187/metrics      :9100         kube-state-metrics
         ↓                ↓                ↓
         └────────────────┴────────────────┘
                         ↓
           [Prometheus Server] (scrape toutes les 30s)
                         ↓
              Stockage TSDB (7 jours)
                         ↓
           [Grafana] ← Requêtes PromQL
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

**Ressources totales requises pour Observability Stack complète:**

**Namespace monitoring (Prometheus):**

| Composant | CPU Request | Memory Request | Storage |
|-----------|-------------|----------------|---------|
| Prometheus Operator | 100m | 128Mi | - |
| Prometheus Server | 200m | 512Mi | 10Gi (PVC) |
| AlertManager | 50m | 64Mi | 2Gi (PVC) |
| Node Exporter | ~20m | ~32Mi | - |
| Kube State Metrics | ~10m | ~64Mi | - |
| **Sous-total monitoring** | **~380m** | **~800Mi** | **12Gi** |

**Namespace loki-stack (Logs + Visualisation):**

| Composant | CPU Request | Memory Request | Storage |
|-----------|-------------|----------------|---------|
| Alloy | 100m | 128Mi | - |
| Loki | 250m | 256Mi | 5Gi (PVC) |
| Grafana | 250m | 256Mi | - |
| **Sous-total loki-stack** | **600m** | **640Mi** | **5Gi** |

**TOTAL OBSERVABILITY STACK:**

| Total | CPU Request | Memory Request | Storage |
|-------|-------------|----------------|---------|
| **Somme** | **~980m (~1 CPU)** | **~1.44Gi** | **17Gi** |

**Vérifier ressources disponibles:**

```bash
kubectl top nodes  # Si metrics-server installé
# OU
kubectl describe nodes rhdemo-control-plane | grep -A 5 "Allocated resources"
```

### 3.4 DNS Local

```bash
# Ajouter à /etc/hosts
echo "127.0.0.1 grafana-stagingkub.intra.leuwen-lc.fr" | sudo tee -a /etc/hosts
```

---

## 4. INSTALLATION

### 4.1 Installation Automatique (Recommandée)

**⚠️ PRÉREQUIS SÉCURITÉ: Configurer le mot de passe Grafana**

Avant d'exécuter le script, vous **devez** configurer un mot de passe fort:

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability

# Générer un mot de passe fort
PASSWORD=$(openssl rand -base64 32)
echo "Mot de passe généré: $PASSWORD"

# Éditer grafana-values.yaml et remplacer adminPassword: "" par le mot de passe
sed -i "s/adminPassword: \"\"/adminPassword: \"$PASSWORD\"/" grafana-values.yaml

# IMPORTANT: Sauvegarder ce mot de passe dans un gestionnaire de mots de passe
```

**Script d'installation clé en main (Stack complète):**

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./install-observability.sh
```

**Ce script installe la stack complète (Prometheus + Loki + Grafana):**

**Namespace monitoring:**
- ✅ Prometheus Operator + Prometheus Server
- ✅ AlertManager (alertes)
- ✅ Node Exporter (métriques nodes)
- ✅ Kube State Metrics (métriques K8s)
- ✅ PodMonitor/ServiceMonitor auto-détection

**Namespace loki-stack:**
- ✅ Loki (logs, mode SingleBinary)
- ✅ Alloy (collecte logs DaemonSet)
- ✅ Grafana (visualisation unifiée)
- ✅ Datasource Prometheus auto-configurée
- ✅ Datasource Loki auto-configurée
- ✅ Dashboards pré-chargés (rhDemo Logs)

**Autres actions:**
- ✅ Vérification des prérequis (kubectl, helm, kind-rhdemo)
- ✅ Validation mot de passe Grafana
- ✅ Ajout repositories Helm (prometheus-community + grafana)
- ✅ Création namespaces (monitoring + loki-stack)
- ✅ Génération certificat TLS Grafana
- ✅ Configuration DNS dans `/etc/hosts`

**Durée:** ~5-8 minutes

**Accès après installation:**
- **Grafana**: https://grafana-stagingkub.intra.leuwen-lc.fr (admin / voir grafana-values.yaml)
- **Prometheus**: `kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090`
- **AlertManager**: `kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093`

### 4.2 Installation Manuelle

#### 4.2.1 Ajouter les Repositories Helm

```bash
# Repository Prometheus Community
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

# Repository Grafana
helm repo add grafana https://grafana.github.io/helm-charts

# Mettre à jour
helm repo update

# Vérifier charts disponibles
helm search repo prometheus-community/kube-prometheus-stack
helm search repo grafana/loki
helm search repo grafana/alloy
helm search repo grafana/grafana
```

**Output attendu:**
```
NAME                                            CHART VERSION   APP VERSION     DESCRIPTION
prometheus-community/kube-prometheus-stack      65.x.x          v0.77.x         Prometheus Operator + Prometheus + ...
grafana/loki                                    6.x.x           3.x.x           Loki: like Prometheus, but for logs
grafana/alloy                                   1.x.x           v1.x.x          Grafana Alloy
grafana/grafana                                 8.x.x           11.x.x          The open observability platform
```

#### 4.2.2 Créer les Namespaces

```bash
# Namespace pour Prometheus
kubectl create namespace monitoring

# Namespace pour Loki + Grafana
kubectl create namespace loki-stack

# Vérifier
kubectl get namespaces | grep -E 'monitoring|loki'
```

#### 4.2.3 Créer les Fichiers de Configuration

Les fichiers de configuration sont déjà présents dans le projet:

**Prometheus:** `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/prometheus-values.yaml`

```yaml
# Configuration Prometheus + Operator
# Chart: prometheus-community/kube-prometheus-stack

prometheusOperator:
  enabled: true
  resources:
    requests:
      cpu: 100m
      memory: 128Mi

prometheus:
  enabled: true
  prometheusSpec:
    retention: 7d
    retentionSize: "5GB"
    storageSpec:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 10Gi

    # ⭐ Important pour découverte automatique de tous les PodMonitors
    podMonitorSelectorNilUsesHelmValues: false
    podMonitorSelector: {}  # Scrape TOUS les PodMonitors
    podMonitorNamespaceSelector: {}

    serviceMonitorSelectorNilUsesHelmValues: false
    serviceMonitorSelector: {}  # Scrape TOUS les ServiceMonitors

    scrapeInterval: 30s
    evaluationInterval: 30s

    resources:
      requests:
        cpu: 200m
        memory: 512Mi

# Grafana désactivé (installé séparément dans loki-stack)
grafana:
  enabled: false

alertmanager:
  enabled: true
  alertmanagerSpec:
    storage:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 2Gi

nodeExporter:
  enabled: true

kubeStateMetrics:
  enabled: true

# Désactiver composants non accessibles sur KinD
kubeControllerManager:
  enabled: false
kubeScheduler:
  enabled: false
kubeProxy:
  enabled: false
kubeEtcd:
  enabled: false
```

**Loki:** `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/loki-modern-values.yaml`

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

**Alloy:** `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/alloy-values.yaml`

Remplace Promtail (EOL depuis le 02/03/2026). La config est écrite dans le
langage Alloy (pas du YAML) et reproduit exactement le même comportement que
l'ancienne config Promtail : découverte des pods du namespace
`rhdemo-stagingkub`, mêmes labels (`namespace`/`pod`/`container`/`app`/
`component`/`job`), lecture des logs via hostPath (`/var/log/pods`, pas de
flux réseau vers les pods sources), parsing CRI, push vers Loki. Voir le
fichier source pour le détail complet des blocs `discovery.kubernetes`/
`discovery.relabel`/`loki.source.file`/`loki.process`/`loki.write`.

```yaml
crds:
  create: false   # CRD podlogs non utilisée (config statique ci-dessous)

alloy:
  configMap:
    content: |
      discovery.kubernetes "pods" {
        role = "pod"
        namespaces { names = ["rhdemo-stagingkub"] }
      }
      discovery.relabel "pods" {
        targets = discovery.kubernetes.pods.targets
        # ... règles de relabeling (namespace/pod/container/app/component/job/__path__)
      }
      local.file_match "pods" { path_targets = discovery.relabel.pods.output }
      loki.source.file "pods" {
        targets    = local.file_match.pods.targets
        forward_to = [loki.process.cri.receiver]
      }
      loki.process "cri" {
        stage.cri {}
        forward_to = [loki.write.default.receiver]
      }
      loki.write "default" {
        endpoint {
          url       = "http://loki-gateway.loki-stack.svc.cluster.local/loki/api/v1/push"
          tenant_id = ""
        }
      }
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
```

**Grafana:** `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/grafana-values.yaml`

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
    - grafana-stagingkub.intra.leuwen-lc.fr
  tls:
    - secretName: grafana-tls-cert
      hosts:
        - grafana-stagingkub.intra.leuwen-lc.fr

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
      - name: Prometheus
        type: prometheus
        access: proxy
        url: http://prometheus-kube-prometheus-prometheus.monitoring.svc:9090
        isDefault: false
        editable: true
        jsonData:
          timeInterval: 30s

grafana.ini:
  server:
    domain: grafana-stagingkub.intra.leuwen-lc.fr
    root_url: https://grafana-stagingkub.intra.leuwen-lc.fr
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
  -subj "/CN=grafana-stagingkub.intra.leuwen-lc.fr/O=RHDemo"

# Créer le secret dans Kubernetes
kubectl create secret tls grafana-tls-cert \
  --cert=$TMP/tls.crt \
  --key=$TMP/tls.key \
  -n loki-stack

# Nettoyer
rm -rf $TMP
```

#### 4.2.5 Installer les Charts

**Ordre d'installation: Prometheus → Loki → Alloy → Grafana**

```bash
# 1. Installer Prometheus + Operator (namespace monitoring)
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/prometheus-values.yaml \
  --wait --timeout 10m

# Vérifier installation Prometheus
kubectl get pods -n monitoring
helm list -n monitoring

# 2. Installer Loki (mode SingleBinary)
helm upgrade --install loki grafana/loki \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/loki-modern-values.yaml \
  --wait --timeout 3m

# 3. Installer Alloy
helm upgrade --install alloy grafana/alloy \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/alloy-values.yaml \
  --wait --timeout 2m

# 4. Installer Grafana (avec les 2 datasources)
helm upgrade --install grafana grafana/grafana \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/grafana-values.yaml \
  --wait --timeout 3m

# Vérifier les installations
helm list -n monitoring
helm list -n loki-stack
```

**Output attendu:**

```
# Namespace monitoring
NAME            NAMESPACE       REVISION        STATUS          CHART                              APP VERSION
prometheus      monitoring      1               deployed        kube-prometheus-stack-65.x.x       v0.77.x

# Namespace loki-stack
NAME            NAMESPACE       REVISION        STATUS          CHART                   APP VERSION
loki            loki-stack      1               deployed        loki-6.x.x              3.x.x
alloy           loki-stack      1               deployed        alloy-1.x.x             v1.x.x
grafana         loki-stack      1               deployed        grafana-8.x.x           11.x.x
```

#### 4.2.6 Vérifier le Déploiement

```bash
# Vérifier pods Prometheus (namespace monitoring)
kubectl get pods -n monitoring

# Output attendu:
# NAME                                                   READY   STATUS    RESTARTS   AGE
# prometheus-kube-prometheus-operator-xxx                1/1     Running   0          5m
# prometheus-prometheus-kube-prometheus-prometheus-0     2/2     Running   0          5m
# alertmanager-prometheus-kube-prometheus-alertmanager-0 2/2     Running   0          5m
# prometheus-kube-state-metrics-xxx                      1/1     Running   0          5m
# prometheus-prometheus-node-exporter-xxx                1/1     Running   0          5m

# Vérifier pods Loki Stack
kubectl get pods -n loki-stack

# Output attendu:
# NAME                            READY   STATUS    RESTARTS   AGE
# loki-0                          1/1     Running   0          2m
# alloy-xxxxx                     1/1     Running   0          2m
# grafana-xxxxx                   1/1     Running   0          2m

# Vérifier les services (monitoring)
kubectl get svc -n monitoring

# Vérifier les services (loki-stack)
kubectl get svc -n loki-stack

# Output attendu loki-stack:
# NAME              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
# loki-gateway      ClusterIP   10.96.xxx.xxx    <none>        80/TCP     2m
# grafana           ClusterIP   10.96.xxx.xxx    <none>        80/TCP     2m

# Vérifier l'ingress
kubectl get ingress -n loki-stack

# Vérifier les PVCs (deux namespaces)
kubectl get pvc -n monitoring
kubectl get pvc -n loki-stack

# Vérifier les PodMonitors
kubectl get podmonitor -A

# Vérifier les ServiceMonitors
kubectl get servicemonitor -A
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
grep grafana-stagingkub.intra.leuwen-lc.fr /etc/hosts

# Si absent:
echo "127.0.0.1 grafana-stagingkub.intra.leuwen-lc.fr" | sudo tee -a /etc/hosts
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
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/loki-modern-values.yaml
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

### 5.4 Dashboard rhDemo Pré-configuré (Déploiement Automatique)

**✅ Déploiement automatique lors de l'installation**

Le script `install-loki.sh` déploie automatiquement le dashboard "rhDemo - Logs Application". Aucune action manuelle requise!

**Dashboard inclus:**
- 🔴 **Logs d'Erreurs** : Logs contenant "ERROR"
- 📊 **Rate d'Erreurs** : Nombre d'erreurs par minute
- 📈 **Volume de Logs** : Volume par application
- 🔍 **Logs Temps Réel** : Tous les logs de l'app
- 🔐 **Logs Keycloak** : Authentification
- 🗄️ **Logs PostgreSQL** : Logs des bases de données
- ⚠️ **Compteur WARN** : Logs WARNING dernière heure
- 🔴 **Compteur ERROR** : Logs ERROR dernière heure
- 📊 **Top 10 Pods** : Pods avec le plus de logs

**Fichier source:** `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/grafana-dashboard-rhdemo.json`

**Mise à jour manuelle du dashboard:**

Si vous modifiez le fichier JSON et souhaitez redéployer sans réinstaller toute la stack :

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./deploy-grafana-dashboard.sh
```

**Documentation complète:** Voir [GRAFANA_DASHBOARD.md](../infra/stagingkub/GRAFANA_DASHBOARD.md)

---

## 6. ACCÈS ET UTILISATION

### 6.1 Accéder à Grafana

**URL:** https://grafana-stagingkub.intra.leuwen-lc.fr

**Credentials:**
- Username: `admin`
- Password: (mot de passe configuré dans grafana-values.yaml)

**Navigation:**
1. Menu → Explore
2. Sélectionner datasource: **Loki** (logs) ou **Prometheus** (métriques)
3. Construire requête LogQL ou PromQL

### 6.2 Accéder à Prometheus (optionnel)

```bash
# Port-forward vers Prometheus
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Accéder à http://localhost:9090
```

**URL:** http://localhost:9090

**Features:**
- Status → Targets (vérifier tous les scrapes)
- Status → Service Discovery (vérifier PodMonitors/ServiceMonitors)
- Graph (requêtes PromQL manuelles)

### 6.3 Accéder à AlertManager (optionnel)

```bash
# Port-forward vers AlertManager
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093

# Accéder à http://localhost:9093
```

### 6.4 Interface Grafana Explore

**Éléments clés:**

| Élément | Description |
|---------|-------------|
| **Datasource** | Loki (logs) ou Prometheus (métriques) |
| **Query Editor** | Construire requête LogQL ou PromQL |
| **Log Browser** | (Loki) Labels disponibles (namespace, pod, app, etc.) |
| **Metric Browser** | (Prometheus) Métriques disponibles |
| **Time Range** | Sélecteur période (Last 5m, Last 1h, etc.) |
| **Live** | Tail logs en temps réel (Loki) |
| **Log Details** | Clic sur une ligne → détails + labels |
| **Split View** | Comparer logs et métriques côte à côte |

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

## 7. QUERIES LOGQL ET PROMQL

### 7.1 Queries LogQL (Logs avec Loki)

#### 7.1.1 Logs par Composant

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

#### 7.1.6 Logs en Temps Réel (Live Tail)

**Bouton "Live" dans Grafana Explore** OU:

```bash
# Via CLI (logcli)
logcli query --tail '{namespace="rhdemo-stagingkub", app="rhdemo-app"}'
```

### 7.2 Queries PromQL (Métriques avec Prometheus)

#### 7.2.1 Métriques Kubernetes (Kube State Metrics)

**Pods en cours d'exécution par namespace:**
```promql
kube_pod_status_phase{namespace="rhdemo-stagingkub", phase="Running"}
```

**Pods en erreur:**
```promql
kube_pod_status_phase{namespace="rhdemo-stagingkub", phase=~"Failed|Unknown"}
```

**Nombre de restarts de containers:**
```promql
kube_pod_container_status_restarts_total{namespace="rhdemo-stagingkub"}
```

**Deployments avec replicas disponibles:**
```promql
kube_deployment_status_replicas_available{namespace="rhdemo-stagingkub"}
```

#### 7.2.3 Métriques Nodes (Node Exporter)

**CPU utilisé par node (%):**
```promql
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

**Mémoire utilisée (%):**
```promql
100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))
```

**Espace disque utilisé (%):**
```promql
100 - ((node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100)
```

**Network traffic (bytes/sec):**
```promql
rate(node_network_receive_bytes_total[5m])
rate(node_network_transmit_bytes_total[5m])
```

#### 7.2.4 Métriques Application Spring Boot Actuator

Les métriques Spring Boot Actuator sont collectées automatiquement via le ServiceMonitor `rhdemo-app` déployé dans le namespace `monitoring`.

**Configuration requise:**

- Endpoint `/actuator/prometheus` exposé sans authentification (protégé par NetworkPolicy)
- ServiceMonitor configuré dans le chart Helm `rhdemo`
- Label `environment=stagingkub` ajouté aux métriques

**JVM Heap Memory:**
```promql
sum(jvm_memory_used_bytes{environment="stagingkub", area="heap"}) / 1024 / 1024
```

**JVM Threads actifs:**
```promql
jvm_threads_live_threads{environment="stagingkub"}
```

**Requêtes HTTP par seconde:**
```promql
sum(rate(http_server_requests_seconds_count{environment="stagingkub"}[5m]))
```

**Latence HTTP p50/p95/p99:**
```promql
histogram_quantile(0.95, sum by (le) (rate(http_server_requests_seconds_bucket{environment="stagingkub"}[5m])))
```

**Erreurs HTTP 4xx/5xx:**
```promql
sum(rate(http_server_requests_seconds_count{environment="stagingkub", status=~"4.."}[5m]))
sum(rate(http_server_requests_seconds_count{environment="stagingkub", status=~"5.."}[5m]))
```

**Connexions HikariCP actives:**
```promql
hikaricp_connections_active{environment="stagingkub"}
```

**Pool HikariCP complet:**
```promql
hikaricp_connections{environment="stagingkub"}
hikaricp_connections_idle{environment="stagingkub"}
hikaricp_connections_pending{environment="stagingkub"}
hikaricp_connections_max{environment="stagingkub"}
```

**Garbage Collection:**
```promql
rate(jvm_gc_pause_seconds_sum{environment="stagingkub"}[5m])
```

**Logs par niveau (Logback):**
```promql
rate(logback_events_total{environment="stagingkub", level="error"}[5m])
```

---

## 8. DASHBOARDS GRAFANA

### 8.1 Dashboard rhDemo - Logs d'Application (Pré-configuré)

**✅ Dashboard automatiquement disponible après installation!**

Le dashboard "rhDemo - Logs Application" est déployé automatiquement lors de l'installation de la stack Loki.

**Accès:** Grafana → Dashboards → "rhDemo - Logs Application"

**Contenu du dashboard:**

| Panel | Description | Query |
|-------|-------------|-------|
| 🔴 **Logs d'Erreurs** | Logs contenant ERROR | `{namespace="rhdemo-stagingkub", app="rhdemo-app"} \|= "ERROR"` |
| 📊 **Rate d'Erreurs** | Erreurs par minute | `sum(count_over_time({...} \|= "ERROR" [1m]))` |
| 📈 **Volume de Logs** | Volume par app (rate 5min) | `sum by (app) (rate({namespace="rhdemo-stagingkub"}[5m]))` |
| �� **Logs Temps Réel** | Tous les logs de l'app | `{namespace="rhdemo-stagingkub", app="rhdemo-app"}` |
| 🔐 **Logs Keycloak** | Authentification | `{..., app="keycloak"} \|~ "Login\|logout\|authenticated"` |
| 🗄️ **Logs PostgreSQL** | Logs database | `{..., app=~"postgresql-.*"}` |
| 📊 **Top 10 Pods** | Pods avec le plus de logs | `topk(10, sum by (pod) (count_over_time({...}[1h])))` |
| ⚠️ **Logs WARN** | Compteur WARNING (1h) | `sum(count_over_time({...} \|= "WARN" [1h]))` |
| 🔴 **Logs ERROR** | Compteur ERROR (1h) | `sum(count_over_time({...} \|= "ERROR" [1h]))` |

**Personnalisation:**

Pour modifier le dashboard:
1. Dupliquer le dashboard (Dashboard → Settings → Save As)
2. Modifier la copie selon vos besoins
3. Le dashboard original reste disponible

Pour déployer une nouvelle version du dashboard source:
```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./deploy-grafana-dashboard.sh
```

**Documentation complète:** [GRAFANA_DASHBOARD.md](../infra/stagingkub/GRAFANA_DASHBOARD.md)

### 8.2 Dashboard rhDemo - Métriques Spring Boot Actuator (Pré-configuré)

**Dashboard automatiquement disponible après installation!**

Le dashboard "rhDemo - Metriques Spring Boot Actuator" affiche les métriques JVM, HTTP et HikariCP collectées via `/actuator/prometheus`.

**Accès:** Grafana → Dashboards → "rhDemo - Metriques Spring Boot Actuator"

**Prérequis:**

- ServiceMonitor `rhdemo-app` déployé dans le namespace `monitoring`
- Endpoint `/actuator/prometheus` accessible sans authentification
- NetworkPolicy autorisant le scraping depuis le namespace `monitoring`

**Contenu du dashboard:**

| Section | Panels | Métriques |
|---------|--------|-----------|
| **Vue d'ensemble** | Heap %, Threads, Req/s, DB Active | Stats instantanées |
| **JVM Memory** | Heap Used/Committed/Max, Non-Heap, Par Pool | `jvm_memory_*` |
| **JVM Threads** | Par état, Live/Daemon/Peak | `jvm_threads_*` |
| **Garbage Collection** | Durée GC par action/cause | `jvm_gc_pause_*` |
| **HTTP Requests** | Req/s par status, Latence p50/p95/p99, Par endpoint, Erreurs 4xx/5xx | `http_server_requests_*` |
| **HikariCP** | Active/Idle/Pending/Total/Max, Acquire/Creation Time | `hikaricp_*` |
| **Logback** | Events par niveau (ERROR/WARN/INFO), Uptime | `logback_events_*`, `process_uptime_*` |

**Fichier source:** `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/grafana-dashboard-rhdemo-springboot.json`

**Déploiement:**

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./deploy-grafana-dashboard.sh springboot
# ou pour tous les dashboards:
./deploy-grafana-dashboard.sh all
```

**Configuration ServiceMonitor (Helm):**

Le ServiceMonitor est automatiquement créé lors du déploiement du chart Helm `rhdemo` si `rhdemo.metrics.serviceMonitor.enabled: true` dans `values.yaml`.

```yaml
# values.yaml
rhdemo:
  metrics:
    serviceMonitor:
      enabled: true
      namespace: monitoring
      interval: 30s
      scrapeTimeout: 10s
```

**Fichiers associés:**

- ServiceMonitor: `infra/stagingkub/helm/rhdemo/templates/servicemonitor-rhdemo.yaml`
- NetworkPolicy: `infra/stagingkub/helm/rhdemo/templates/networkpolicy-prometheus.yaml`
- Dashboard: `infra/stagingkub/grafana-dashboard-rhdemo-springboot.json`

### 8.3 Dashboard rhDemo - Métriques PostgreSQL (Pré-configuré)

**Dashboard automatiquement disponible après installation!**

Le dashboard "rhDemo - Métriques PostgreSQL" affiche les métriques de performance de la base de données collectées via les collecteurs intégrés de `postgres_exporter` v0.15.0 (sans requêtes personnalisées dépréciées).

**Accès:** Grafana → Dashboards → "rhDemo - Metriques PostgreSQL"

**Prérequis:**

- Sidecar `postgres_exporter` déployé avec le StatefulSet PostgreSQL
- Extension `pg_stat_statements` activée dans PostgreSQL
- ServiceMonitor `postgresql-rhdemo` déployé dans le namespace `monitoring`

**Contenu du dashboard:**

| Section | Panels | Métriques (collecteurs intégrés) |
|---------|--------|-----------|
| **Vue d'ensemble** | Taille DB, Connexions, Verrous, Dead Tuples, Requêtes Longues | `pg_database_size_bytes`, `pg_stat_activity_count`, `pg_locks_count`, `pg_stat_user_tables_n_dead_tup`, `pg_long_running_transactions` |
| **Top 10 Requêtes Lentes** | Table avec temps total, temps moyen, appels, lignes | `pg_stat_statements_seconds_total`, `pg_stat_statements_calls_total`, `pg_stat_statements_rows_total` |
| **Statistiques Requêtes** | Temps moyen par requête, Appels par requête, Lignes retournées | `pg_stat_statements_seconds_total / pg_stat_statements_calls_total`, `pg_stat_statements_rows_total` |
| **Connexions & Activité** | Par état (active/idle), Verrous par mode | `pg_stat_activity_count{state=...}`, `pg_locks_count{mode=...}` |
| **Statistiques Tables** | Opérations CRUD, Scans seq vs index, Live/Dead tuples | `pg_stat_user_tables_n_tup_ins/upd/del`, `pg_stat_user_tables_seq_scan/idx_scan`, `pg_stat_user_tables_n_live_tup/n_dead_tup` |
| **Cache & I/O** | Cache Hit Ratio, Blocks Hit vs Read | `pg_stat_database_blks_hit`, `pg_stat_database_blks_read` |

**Fichier source:** `/home/leno-vo/git/repository/rhDemo/infra/stagingkub/grafana-dashboard-rhdemo-postgresql.json`

**Déploiement:**

```bash
cd /home/leno-vo/git/repository/rhDemo/infra/stagingkub/scripts
./deploy-grafana-dashboard.sh postgresql
# ou pour tous les dashboards:
./deploy-grafana-dashboard.sh all
```

**Configuration postgres_exporter (Helm):**

Le sidecar postgres_exporter est automatiquement déployé si `postgresql-rhdemo.metrics.enabled: true` dans `values.yaml`.

**Approche:** Utilisation exclusive des collecteurs intégrés de postgres_exporter v0.15.0 (pas de `--extend.query-path` déprécié). Les collecteurs suivants sont activés explicitement (désactivés par défaut) :

- `--collector.stat_statements` : Statistiques des requêtes SQL (temps, appels, lignes)
- `--collector.long_running_transactions` : Détection des transactions longues
- `--collector.process_idle` : Processus PostgreSQL idle

Les collecteurs activés par défaut (`stat_user_tables`, `locks`, `database`, etc.) fournissent les métriques de tables, verrous et taille de base.

```yaml
# values.yaml
postgresql-rhdemo:
  metrics:
    enabled: true
    exporter:
      image:
        repository: quay.io/prometheuscommunity/postgres-exporter
        tag: "v0.15.0"
    serviceMonitor:
      enabled: true
      namespace: monitoring
      interval: 30s
      scrapeTimeout: 10s
```

**Fichiers associés:**

- StatefulSet avec sidecar: `infra/stagingkub/helm/rhdemo/templates/postgresql-rhdemo-statefulset.yaml`
- ServiceMonitor: `infra/stagingkub/helm/rhdemo/templates/servicemonitor-postgresql.yaml`
- Dashboard: `infra/stagingkub/grafana-dashboard-rhdemo-postgresql.json`

**Requêtes PromQL utiles (collecteurs intégrés):**

Top 10 requêtes les plus lentes (temps total):

```promql
topk(10, pg_stat_statements_seconds_total{datname="rhdemo"})
```

Temps moyen par requête:

```promql
pg_stat_statements_seconds_total{datname="rhdemo"} / pg_stat_statements_calls_total{datname="rhdemo"} > 0
```

Connexions par état:

```promql
pg_stat_activity_count{datname="rhdemo"}
```

Cache Hit Ratio:

```promql
sum(pg_stat_database_blks_hit{datname="rhdemo"}) / (sum(pg_stat_database_blks_hit{datname="rhdemo"}) + sum(pg_stat_database_blks_read{datname="rhdemo"}) + 1)
```

Transactions longues en cours:

```promql
pg_long_running_transactions or vector(0)
```

Opérations sur les tables (insertions/mises à jour/suppressions):

```promql
rate(pg_stat_user_tables_n_tup_ins{datname="rhdemo"}[5m])
rate(pg_stat_user_tables_n_tup_upd{datname="rhdemo"}[5m])
rate(pg_stat_user_tables_n_tup_del{datname="rhdemo"}[5m])
```

### 8.4 Dashboard Keycloak - Logs d'Authentification (Custom)

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

### 8.5 Dashboard PostgreSQL - Logs des Bases de Données (Loki)

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

### 9.2 Alloy ne Collecte Pas de Logs

**Symptôme:** Aucun log dans Grafana

**Vérification:**

```bash
# Logs Alloy
kubectl logs -n loki-stack -l app.kubernetes.io/name=alloy

# Vérifier qu'Alloy trouve des pods
kubectl logs -n loki-stack -l app.kubernetes.io/name=alloy | grep "discovered"
```

**Causes fréquentes:**

| Problème | Solution |
|----------|----------|
| Namespace filter trop strict | Vérifier `scrape_configs.relabel_configs` dans values.yaml |
| Alloy ne peut pas lire /var/log/pods | Vérifier mountPath et hostPath dans DaemonSet |
| Logs en JSON non parsés | Ajouter `stage.json` dans le `loki.process` de la config Alloy |

**Vérifier collecte manuelle:**

```bash
# Exec dans Alloy
kubectl exec -n loki-stack -it alloy-xxxxx -- sh

# Lister logs accessibles
ls -la /var/log/pods/rhdemo-stagingkub*/

# Tail un log
tail -f /var/log/pods/rhdemo-stagingkub_rhdemo-app-*/rhdemo-app/*.log
```

### 9.3 Prometheus ne Scrape Pas les Métriques

**Symptôme:** Métriques PostgreSQL ou autres absentes dans Grafana

**Vérification:**

```bash
# Vérifier pods Prometheus
kubectl get pods -n monitoring

# Vérifier les targets Prometheus
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Accéder à http://localhost:9090/targets
# Chercher les targets en état "DOWN"
```

**Vérifier PodMonitors/ServiceMonitors:**

```bash
# Lister tous les PodMonitors
kubectl get podmonitor -A

# Lister tous les ServiceMonitors
kubectl get servicemonitor -A

# Vérifier logs Prometheus Operator
kubectl logs -n monitoring -l app.kubernetes.io/name=prometheus-operator
```

**Causes fréquentes:**

| Problème | Solution |
|----------|----------|
| `podMonitorSelector` trop restrictif | Vérifier `podMonitorSelector: {}` dans prometheus-values.yaml |
| PodMonitor dans mauvais namespace | Vérifier `podMonitorNamespaceSelector: {}` |
| Port métrique incorrect | Vérifier que le pod expose bien le port des métriques |
| Network policy bloque scrape | Vérifier network policies entre namespaces |

**Test manuel scrape:**

```bash
# Port-forward vers un pod avec métriques
kubectl port-forward -n rhdemo-stagingkub <pod-name> <metrics-port>:<metrics-port>

# Vérifier métriques exposées
curl http://localhost:<metrics-port>/metrics
```

### 9.4 Grafana - Datasource Loki ou Prometheus Inaccessible

**Symptôme Loki:** "Data source connected, but no labels received"
**Symptôme Prometheus:** "Data source is working" mais pas de métriques

**Vérification:**

```bash
# Tester connexion depuis pod Grafana
kubectl exec -n loki-stack -it deployment/grafana -- sh

# Curl Loki
wget -O- http://loki-gateway:80/ready

# Tester API labels Loki
wget -O- http://loki-gateway:80/loki/api/v1/labels

# Curl Prometheus
wget -O- http://prometheus-kube-prometheus-prometheus.monitoring.svc:9090/-/healthy

# Tester query Prometheus
wget -O- 'http://prometheus-kube-prometheus-prometheus.monitoring.svc:9090/api/v1/query?query=up'
```

**Solution:**

Vérifier que les services existent:

```bash
# Service Loki
kubectl get svc -n loki-stack loki-gateway

# Service Prometheus
kubectl get svc -n monitoring prometheus-kube-prometheus-prometheus
```

**Reconfigurer datasource Prometheus si nécessaire:**

```bash
# Créer ConfigMap pour datasource Prometheus
cat <<EOF | kubectl apply -n loki-stack -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-datasource-prometheus
  labels:
    grafana_datasource: "1"
data:
  prometheus-datasource.yaml: |
    apiVersion: 1
    datasources:
      - name: Prometheus
        type: prometheus
        access: proxy
        url: http://prometheus-kube-prometheus-prometheus.monitoring.svc:9090
        isDefault: false
        editable: true
EOF

# Redémarrer Grafana
kubectl rollout restart deployment/grafana -n loki-stack
```

### 9.5 Ingress Grafana ne Fonctionne Pas

**Symptôme:** `curl https://grafana-stagingkub.intra.leuwen-lc.fr` timeout

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

### 9.6 Logs Trop Volumineux (PVC Plein)

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

### 9.7 Requêtes LogQL Lentes

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

### 10.2 Backup Métriques Prometheus

**Stratégie:**

Prometheus stocke dans PVC `prometheus-kube-prometheus-prometheus-db`. Pour backup:

```bash
# Snapshot Prometheus (via API)
curl -X POST http://localhost:9090/api/v1/admin/tsdb/snapshot

# Créer backup du PVC
kubectl exec -n monitoring prometheus-prometheus-kube-prometheus-prometheus-0 \
  -- tar czf /tmp/prometheus-backup.tar.gz /prometheus

# Copier localement
kubectl cp monitoring/prometheus-prometheus-kube-prometheus-prometheus-0:/tmp/prometheus-backup.tar.gz \
  ./prometheus-backup-$(date +%Y%m%d).tar.gz
```

**Note:** Pour production, utiliser [Thanos](https://thanos.io/) ou [Cortex](https://cortexmetrics.io/) pour backup long-terme.

### 10.3 Mise à Jour Observability Stack

```bash
# Mettre à jour repos Helm
helm repo update

# Vérifier nouvelles versions
helm search repo prometheus-community/kube-prometheus-stack
helm search repo grafana/loki
helm search repo grafana/alloy
helm search repo grafana/grafana

# Upgrade Prometheus Stack
helm upgrade prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/prometheus-values.yaml

# Upgrade Loki
helm upgrade loki grafana/loki \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/loki-modern-values.yaml

# Upgrade Alloy
helm upgrade alloy grafana/alloy \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/alloy-values.yaml

# Upgrade Grafana
helm upgrade grafana grafana/grafana \
  -n loki-stack \
  -f /home/leno-vo/git/repository/rhDemo/infra/stagingkub/helm/observability/grafana-values.yaml

# Vérifier rollouts
kubectl rollout status statefulset -n monitoring prometheus-prometheus-kube-prometheus-prometheus
kubectl rollout status statefulset -n loki-stack loki
kubectl rollout status daemonset -n loki-stack alloy
kubectl rollout status deployment -n loki-stack grafana
```

### 10.4 Rotation des Logs et Métriques (Automatique)

**Logs (Loki):**
- Rétention: 7 jours (168h défini dans `loki-modern-values.yaml`)
- Suppression automatique via `loki.limits_config.retention_period: 168h`
- Compaction automatique en mode SingleBinary

**Métriques (Prometheus):**
- Rétention: 7 jours (défini dans `prometheus-values.yaml`)
- Taille max: 5GB (retentionSize)
- Suppression automatique par Prometheus TSDB

**Vérifier compaction Loki:**

```bash
# Logs Loki (rechercher compaction)
kubectl logs -n loki-stack loki-0 | grep -i compactor
```

**Vérifier TSDB Prometheus:**

```bash
# Status TSDB
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Accéder à http://localhost:9090/tsdb-status
```

### 10.5 Monitoring de la Stack Observabilité

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

### 10.6 Désinstallation

**Désinstallation complète de la stack Observabilité:**

```bash
# Désinstaller Prometheus Stack
helm uninstall prometheus -n monitoring

# Désinstaller Loki Stack
helm uninstall loki -n loki-stack
helm uninstall alloy -n loki-stack
helm uninstall grafana -n loki-stack

# Supprimer PVCs (ATTENTION: perte de données)
kubectl delete pvc -n monitoring --all
kubectl delete pvc -n loki-stack --all

# Supprimer namespaces
kubectl delete namespace monitoring
kubectl delete namespace loki-stack

# Retirer du DNS
sudo sed -i '/grafana-stagingkub.intra.leuwen-lc.fr/d' /etc/hosts
```

**Désinstallation partielle (garder Loki, supprimer Prometheus):**

```bash
# Désinstaller uniquement Prometheus
helm uninstall prometheus -n monitoring
kubectl delete pvc -n monitoring --all
kubectl delete namespace monitoring

# Loki et Grafana restent fonctionnels (logs uniquement)
```

---

## 11. RESSOURCES UTILES

### Documentation Officielle

**Prometheus:**
- **Prometheus:** https://prometheus.io/docs/introduction/overview/
- **PromQL:** https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Prometheus Operator:** https://prometheus-operator.dev/
- **kube-prometheus-stack:** https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack

**Loki:**
- **Loki:** https://grafana.com/docs/loki/latest/
- **Alloy:** https://grafana.com/docs/alloy/latest/
- **LogQL:** https://grafana.com/docs/loki/latest/query/

**Grafana:**
- **Grafana:** https://grafana.com/docs/grafana/latest/
- **Dashboards:** https://grafana.com/grafana/dashboards/

**Helm Charts:**
- Prometheus Stack: https://github.com/prometheus-community/helm-charts
- Loki: https://github.com/grafana/helm-charts/tree/main/charts/loki
- Alloy: https://github.com/grafana/alloy/tree/main/operations/helm/charts/alloy
- Grafana: https://github.com/grafana/helm-charts/tree/main/charts/grafana

### Tutoriels

**Prometheus:**
- [Getting Started with Prometheus](https://prometheus.io/docs/prometheus/latest/getting_started/)
- [PromQL Cheat Sheet](https://promlabs.com/promql-cheat-sheet/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)

**Loki:**
- [Getting Started with Loki](https://grafana.com/docs/loki/latest/getting-started/)
- [LogQL Cheat Sheet](https://megamorf.gitlab.io/cheat-sheets/loki/)
- [Grafana Loki Workshops](https://github.com/grafana/loki/tree/main/docs/workshops)

### Communauté

- **Prometheus GitHub:** https://github.com/prometheus/prometheus
- **Loki GitHub:** https://github.com/grafana/loki
- **Grafana Slack:** https://slack.grafana.com/
- **Grafana Forum:** https://community.grafana.com/
- **CNCF Slack:** https://slack.cncf.io/

### Documentation Projet rhDemo

- [GRAFANA_DASHBOARD.md](../infra/stagingkub/GRAFANA_DASHBOARD.md) - Documentation dashboard rhDemo Logs
- [POSTGRESQL_BACKUP_CRONJOBS.md](./POSTGRESQL_BACKUP_CRONJOBS.md) - Backups PostgreSQL automatiques


