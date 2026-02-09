# Network Policies - Namespaces externes

Ce dossier contient les Network Policies pour les namespaces qui ne sont pas gérés par le chart Helm `rhdemo`.

## Vue d'ensemble

| Fichier | Namespace | Composants protégés |
|---------|-----------|---------------------|
| `monitoring-networkpolicies.yaml` | monitoring | Prometheus, AlertManager, Prometheus Operator, Node Exporter, Kube State Metrics |
| `loki-stack-networkpolicies.yaml` | loki-stack | Loki, Promtail, Grafana |
| `nginx-gateway-networkpolicies.yaml` | nginx-gateway | NGINX Gateway Fabric |

## Stratégie

Toutes les policies suivent la même stratégie **Zero Trust / Default Deny** :

1. **Default Deny** : Tout trafic (ingress + egress) est bloqué par défaut
2. **Whitelist** : Seuls les flux explicitement autorisés sont permis
3. **Least Privilege** : Chaque pod n'a accès qu'aux ressources strictement nécessaires

## Application

### Appliquer les policies

```bash
./apply-networkpolicies.sh
```

### Mode dry-run (prévisualisation)

```bash
./apply-networkpolicies.sh --dry-run
```

### Supprimer les policies

```bash
./apply-networkpolicies.sh --delete
```

## Vérification

### Lister les Network Policies

```bash
kubectl get networkpolicies -A | grep -E '(monitoring|loki-stack|nginx-gateway)'
```

### Tester la connectivité

```bash
../scripts/test-network-policies.sh
```

## Architecture des flux

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLUSTER KUBERNETES                              │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        nginx-gateway                                    │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │  nginx-gateway-fabric                                           │   │ │
│  │  │  INGRESS: Internet (80, 443), Prometheus (9113)                 │   │ │
│  │  │  EGRESS: rhdemo-app (9000), keycloak (8080), grafana (80)      │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                    ┌───────────────┼───────────────┐                        │
│                    ▼               ▼               ▼                        │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │  rhdemo-stagingkub  │  │    loki-stack   │  │       monitoring        │ │
│  │  (Helm chart)       │  │                 │  │                         │ │
│  │  - rhdemo-app       │  │  - Grafana ◄────┼──┼─ Prometheus             │ │
│  │  - keycloak         │  │  - Loki ◄───────┼──┤                         │ │
│  │  - postgresql x2    │  │  - Promtail     │  │  - AlertManager         │ │
│  └─────────────────────┘  └─────────────────┘  │  - Node Exporter        │ │
│                                                 │  - Kube State Metrics   │ │
│                                                 └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Flux autorisés par namespace

### monitoring

| Source | Destination | Port | Description |
|--------|-------------|------|-------------|
| Prometheus | rhdemo-stagingkub/* | 9000, 9187 | Scrape métriques |
| Prometheus | loki-stack/* | 3100, 80 | Scrape Loki, Grafana |
| Prometheus | nginx-gateway/* | 9113 | Scrape NGF |
| Prometheus | kube-system/* | 10250, 9153 | Scrape kubelet, CoreDNS |
| loki-stack/Grafana | Prometheus | 9090 | Requêtes PromQL |
| Prometheus | AlertManager | 9093 | Push alertes |

### loki-stack

| Source | Destination | Port | Description |
|--------|-------------|------|-------------|
| Promtail | Loki | 3100 | Push logs |
| Grafana | Loki | 3100 | Requêtes LogQL |
| Grafana | monitoring/Prometheus | 9090 | Requêtes PromQL |
| nginx-gateway | Grafana | 80 | Trafic utilisateur |
| monitoring/Prometheus | Loki, Grafana | 3100, 80 | Scrape métriques |

### nginx-gateway

| Source | Destination | Port | Description |
|--------|-------------|------|-------------|
| Internet | nginx-gateway-fabric | 80, 443 | Trafic utilisateur |
| nginx-gateway-fabric | rhdemo-stagingkub/rhdemo-app | 9000 | Backend app |
| nginx-gateway-fabric | rhdemo-stagingkub/keycloak | 8080 | Backend auth |
| nginx-gateway-fabric | loki-stack/grafana | 80 | Backend monitoring |
| monitoring/Prometheus | nginx-gateway-fabric | 9113 | Scrape métriques |

## Intégration avec le chart Helm rhdemo

Les Network Policies du namespace `rhdemo-stagingkub` sont gérées par le chart Helm dans :
- `helm/rhdemo/templates/networkpolicy-*.yaml`

Ces policies externes complètent la sécurité en isolant également les namespaces d'infrastructure.

## CiliumNetworkPolicies pour l'API Server

### Pourquoi des CiliumNetworkPolicies ?

Avec Cilium comme CNI, l'API Server Kubernetes (qui tourne sur le node host) est vu comme l'entité spéciale "host" et non comme un CIDR externe. Les règles `ipBlock` standard des NetworkPolicies ne fonctionnent **pas** pour atteindre le node host.

**Symptôme** : Les pods qui ont besoin d'accéder à l'API Server (prometheus-operator, kube-state-metrics, nginx-gateway-fabric) restent en `CrashLoopBackOff` avec l'erreur :

```text
failed to get server groups: Get "https://10.96.0.1:443/api?timeout=10s": context deadline exceeded
```

**Solution** : Utiliser des `CiliumNetworkPolicy` avec `toEntities: [host, kube-apiserver]` pour autoriser l'egress vers l'API Server.

### Composants nécessitant l'accès API Server

| Namespace | Composant | Raison |
|-----------|-----------|--------|
| nginx-gateway | nginx-gateway-fabric | Lecture Gateway/HTTPRoute CRDs |
| monitoring | prometheus-operator | Gestion CRDs ServiceMonitor, etc. |
| monitoring | kube-state-metrics | Lecture état cluster |

### Vérifier les drops Cilium

Pour diagnostiquer les problèmes de Network Policy avec Cilium :

```bash
# Voir les paquets bloqués par Cilium
kubectl get pods -n kube-system -l k8s-app=cilium -o name | head -1 | \
    xargs -I {} kubectl -n kube-system exec {} -- cilium monitor --type drop
```

## Dépannage

### Les pods ne démarrent pas

Vérifiez que le CNI (Cilium) supporte les Network Policies :

```bash
kubectl get pods -n kube-system -l k8s-app=cilium
```

### Pod en CrashLoopBackOff avec "context deadline exceeded"

C'est probablement un problème d'accès à l'API Server. Vérifiez :

1. Les CiliumNetworkPolicies sont appliquées :

   ```bash
   kubectl get ciliumnetworkpolicies -A
   ```

2. Les drops Cilium :

   ```bash
   kubectl get pods -n kube-system -l k8s-app=cilium -o name | head -1 | \
       xargs -I {} kubectl -n kube-system exec {} -- cilium monitor --type drop
   ```

### Grafana ne peut pas accéder à Prometheus

Vérifiez les labels des pods :

```bash
kubectl get pods -n monitoring -l app.kubernetes.io/name=prometheus --show-labels
kubectl get pods -n loki-stack -l app.kubernetes.io/name=grafana --show-labels
```

### Grafana crash à cause du téléchargement de plugins

En mode Zero Trust, l'accès à Internet (grafana.com) est bloqué. Options :

1. Pré-installer les plugins dans l'image Docker
2. Désactiver l'installation automatique dans la configuration Helm
3. (Non recommandé) Autoriser l'egress vers grafana.com

### Prometheus ne scrape pas les métriques

Vérifiez les Network Policies actives :

```bash
kubectl describe networkpolicy prometheus-netpol -n monitoring
```

Testez la connectivité manuellement :

```bash
kubectl exec -n monitoring deploy/prometheus-kube-prometheus-prometheus -- \
    wget -qO- --timeout=5 http://rhdemo-app.rhdemo-stagingkub:9000/actuator/prometheus | head
```
