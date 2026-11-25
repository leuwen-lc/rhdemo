# Network Policies - Namespaces externes

Ce dossier contient les Network Policies pour les namespaces qui ne sont pas gérés par le chart Helm `rhdemo`.

## Vue d'ensemble

| Fichier | Namespace | Composants protégés |
|---------|-----------|---------------------|
| `monitoring-networkpolicies.yaml` | monitoring | Prometheus, AlertManager, Prometheus Operator, Node Exporter, Kube State Metrics |
| `loki-stack-networkpolicies.yaml` | loki-stack | Loki, Alloy, Grafana |
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

### Lister toutes les policies

```bash
kubectl get networkpolicies -A
```

### Tester la connectivité autorisée

```bash
# rhdemo-app → postgresql-rhdemo
kubectl exec -n rhdemo-stagingkub deploy/rhdemo-app -- nc -zv postgresql-rhdemo 5432

# rhdemo-app → keycloak
kubectl exec -n rhdemo-stagingkub deploy/rhdemo-app -- nc -zv keycloak 8080

# Grafana → Prometheus
kubectl exec -n loki-stack deploy/grafana -- wget -qO- --timeout=5 http://prometheus-kube-prometheus-prometheus.monitoring:9090/-/ready

# Prometheus → rhdemo-app
kubectl exec -n monitoring deploy/prometheus-kube-prometheus-prometheus -- wget -qO- http://rhdemo-app.rhdemo-stagingkub:9000/actuator/prometheus | head
```

### Tester le blocage

```bash
# rhdemo-app → Internet (doit échouer)
kubectl exec -n rhdemo-stagingkub deploy/rhdemo-app -- wget -qO- --timeout=5 http://example.com || echo "BLOQUÉ (OK)"

# postgresql → Internet (doit échouer)
kubectl exec -n rhdemo-stagingkub sts/postgresql-rhdemo -- wget -qO- --timeout=5 http://example.com || echo "BLOQUÉ (OK)"

# keycloak → postgresql-rhdemo (doit échouer - mauvaise DB)
kubectl exec -n rhdemo-stagingkub deploy/keycloak -- nc -zv postgresql-rhdemo 5432 || echo "BLOQUÉ (OK)"

# nginx-gateway → Internet (doit échouer)
kubectl exec -n nginx-gateway deploy/nginx-gateway-fabric -- wget -qO- --timeout=5 http://example.com || echo "BLOQUÉ (OK)"

# Loki → Internet (doit échouer)
kubectl exec -n loki-stack deploy/loki -- wget -qO- --timeout=5 http://example.com || echo "BLOQUÉ (OK)"
```

### Script de test automatisé

```bash
../scripts/test-network-policies.sh
```

## Flux autorisés

Inventaire des flux par namespace, matrice des communications et justification : [SECURITE_NETWORK_POLICY.md](../../../docs/SECURITE_NETWORK_POLICY.md). Ce README ne porte que l'exploitation.

## Intégration avec le chart Helm rhdemo

Les Network Policies du namespace `rhdemo-stagingkub` sont gérées par le chart Helm dans :
- `helm/rhdemo/templates/networkpolicy-*.yaml`

Ces policies externes complètent la sécurité en isolant également les namespaces d'infrastructure.

## CiliumNetworkPolicies pour l'API Server

Avec Cilium, l'API Server est vu comme l'entité `host`/`kube-apiserver` et non comme un CIDR : les composants qui l'interrogent (NGF et son job `cert-generator`, prometheus-operator, kube-state-metrics, Alloy) ont besoin d'une `CiliumNetworkPolicy` avec `toEntities`. Explication et liste : [SECURITE_NETWORK_POLICY.md](../../../docs/SECURITE_NETWORK_POLICY.md#ciliumnetworkpolicy-et-accès-api-server).

## Dépannage

### Les pods ne peuvent plus communiquer après déploiement des policies

1. Vérifiez que Cilium est bien installé et fonctionnel :
   ```bash
   kubectl get pods -n cilium-system -l k8s-app=cilium
   ```

2. Vérifiez les labels des pods :
   ```bash
   kubectl get pods -n rhdemo-stagingkub --show-labels
   ```

3. Vérifiez les Network Policies actives :
   ```bash
   kubectl describe networkpolicy -n rhdemo-stagingkub
   ```

### Pod en CrashLoopBackOff avec "context deadline exceeded"

C'est probablement un problème d'accès à l'API Server. Vérifiez :

1. Les CiliumNetworkPolicies sont appliquées :

   ```bash
   kubectl get ciliumnetworkpolicies -A
   ```

2. Les drops Cilium :

   ```bash
   kubectl get pods -n cilium-system -l k8s-app=cilium -o name | head -1 | \
       xargs -I {} kubectl -n cilium-system exec {} -- cilium monitor --type drop
   ```

### Prometheus ne scrape plus les métriques

Vérifiez que le namespace monitoring a le bon label :

```bash
kubectl get namespace monitoring --show-labels
# Doit avoir: kubernetes.io/metadata.name=monitoring
```

### Grafana affiche "Data source is not working"

Testez manuellement la connexion depuis le pod Grafana :

```bash
kubectl exec -n loki-stack deploy/grafana -- wget -qO- http://prometheus-kube-prometheus-prometheus.monitoring:9090/-/ready
kubectl exec -n loki-stack deploy/grafana -- wget -qO- http://loki.loki-stack:3100/ready
```

### Routes HTTPS inaccessibles (timeout nginx-gateway)

Si les URLs `https://*.intra.leuwen-lc.fr` répondent par un timeout, vérifiez les points suivants :

**1. Architecture NGF 2.4 : controller et data plane séparés**

Dans NGINX Gateway Fabric 2.4+, le controller et le data plane sont des **pods distincts**
avec des labels différents :

| Composant | Pod | Label |
|-----------|-----|-------|
| Controller | `ngf-nginx-gateway-fabric-*` | `app.kubernetes.io/name: nginx-gateway-fabric` |
| Data Plane | `shared-gateway-nginx-*` | `app.kubernetes.io/name: shared-gateway-nginx` |

Les NetworkPolicies doivent cibler le **bon pod** :
- `nginx-gateway-fabric-netpol` (ingress/egress trafic) → `shared-gateway-nginx` (data plane)
- `nginx-gateway-controller-netpol` (API Server, config) → `nginx-gateway-fabric` (controller)

**2. Communication data plane ↔ controller (gRPC)**

Le data plane se connecte au controller via gRPC pour recevoir sa configuration.
Le Service ClusterIP expose le port 443, mais le conteneur écoute sur 8443.
Avec Cilium DNAT, **les deux ports doivent être autorisés** dans les NetworkPolicies.

```bash
# Vérifier les logs du data plane
kubectl logs -n nginx-gateway -l app.kubernetes.io/name=shared-gateway-nginx --tail=50

# Si vous voyez "dial tcp <IP>:443: i/o timeout", la communication gRPC est bloquée
# Vérifier les drops Cilium
kubectl exec -n cilium-system ds/cilium -- cilium-dbg endpoint list | grep shared-gateway
kubectl exec -n cilium-system ds/cilium -- cilium-dbg monitor --type drop --from <ENDPOINT_ID>
```

**3. Vérifier que les HTTPRoutes sont acceptées**

```bash
kubectl get httproutes -n rhdemo-stagingkub -o wide
kubectl get gateway -n nginx-gateway
```

### Alloy ne collecte aucun log (i/o timeout vers l'API Server)

Si Alloy affiche des erreurs `failed to list *v1.Pod: dial tcp 10.96.0.1:443: i/o timeout`,
c'est que l'accès à l'API Server est bloqué. Avec Cilium, il faut une CiliumNetworkPolicy :

```bash
# Vérifier que la CiliumNetworkPolicy existe
kubectl get ciliumnetworkpolicies -n loki-stack

# Si elle manque, l'appliquer
kubectl apply -f rhDemo/infra/stagingkub/networkpolicies/loki-stack-networkpolicies.yaml

# Redémarrer Alloy
kubectl rollout restart daemonset/alloy -n loki-stack
```

Voir la section [CiliumNetworkPolicy et accès API Server](../../../docs/SECURITE_NETWORK_POLICY.md#ciliumnetworkpolicy-et-accès-api-server) pour plus de détails.
