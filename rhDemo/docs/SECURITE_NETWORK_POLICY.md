# Étude des flux réseau et Network Policies - Stagingkub

Ce document décrit tous les flux réseau légitimes dans l'environnement stagingkub et les NetworkPolicies implémentées pour les sécuriser.

## Architecture réseau

```text
                                    ┌─────────────────────────────────────────────────────────────┐
                                    │                        INTERNET                              │
                                    └─────────────────────────────────────────────────────────────┘
                                                             │
                                                             │ ❌ BLOQUÉ (sauf DNS)
                                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         CLUSTER KUBERNETES                                              │
│                                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              Namespace: nginx-gateway                                            │   │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │  nginx-gateway-fabric (NGINX Gateway Fabric 2.4+)                                        │   │   │
│  │  │  Ports: 80 (HTTP), 443 (HTTPS), 9113 (metrics)                                          │   │   │
│  │  │  Backends autorisés: rhdemo-app:9000, keycloak:8080, grafana:80                         │   │   │
│  │  │  ❌ Pas d'accès Internet (egress bloqué)                                                 │   │   │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                    │                    │                    │
│                                          │ :9000              │ :8080              │ :80                │
│                                          ▼                    ▼                    ▼                    │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              Namespace: rhdemo-stagingkub                                        │   │
│  │                                                                                                  │   │
│  │  ┌────────────────────────┐         ┌────────────────────────┐                                  │   │
│  │  │      rhdemo-app        │◄───────►│       keycloak         │                                  │   │
│  │  │  Port: 9000 (HTTP)     │  OAuth2 │  Port: 8080 (HTTP)     │                                  │   │
│  │  │  /actuator/prometheus  │         │  Port: 9000 (health)   │                                  │   │
│  │  └───────────┬────────────┘         └───────────┬────────────┘                                  │   │
│  │              │                                  │                                               │   │
│  │              │ :5432                            │ :5432                                         │   │
│  │              ▼                                  ▼                                               │   │
│  │  ┌────────────────────────┐         ┌────────────────────────┐                                  │   │
│  │  │  postgresql-rhdemo     │    ❌    │  postgresql-keycloak   │                                  │   │
│  │  │  Port: 5432 (PG)       │◄───────►│  Port: 5432 (PG)       │  ← Isolation inter-DB            │   │
│  │  │  Port: 9187 (metrics)  │         │                        │                                  │   │
│  │  └────────────────────────┘         └────────────────────────┘                                  │   │
│  │                                                                                                  │   │
│  │  ┌────────────────────────┐         ┌────────────────────────┐                                  │   │
│  │  │  backup-rhdemo         │         │  backup-keycloak       │                                  │   │
│  │  │  (CronJob)             │         │  (CronJob)             │                                  │   │
│  │  └────────────────────────┘         └────────────────────────┘                                  │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                          ▲                                                              │
│                                          │ Scrape :9000, :9187                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              Namespace: monitoring                                               │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │   │
│  │  │  Prometheus  │───►│ AlertManager │    │ Node Exporter│    │ Kube State   │                   │   │
│  │  │  :9090       │    │   :9093      │    │   :9100      │    │ Metrics:8080 │                   │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘                   │   │
│  │         │                                                                                        │   │
│  │         │ PromQL                                                                                 │   │
│  │         ▼                                                                                        │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                                              │
│                                          ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              Namespace: loki-stack                                               │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                                        │   │
│  │  │   Grafana    │◄───│     Loki     │◄───│   Promtail   │                                        │   │
│  │  │   :80/:3000  │    │   :3100      │    │  (DaemonSet) │                                        │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘                                        │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              Namespace: kube-system                                              │   │
│  │  ┌──────────────┐                                                                               │   │
│  │  │  kube-dns    │◄─────── Tous les pods (résolution DNS)                                        │   │
│  │  │  :53 UDP/TCP │                                                                               │   │
│  │  └──────────────┘                                                                               │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Inventaire des flux légitimes

### 1. Flux d'entrée utilisateur (via Gateway)

| Source | Destination | Port | Protocole | Description |
|--------|-------------|------|-----------|-------------|
| Internet | nginx-gateway-fabric | 443 | HTTPS | Trafic utilisateur TLS |
| nginx-gateway-fabric | rhdemo-app | 9000 | HTTP | Application web |
| nginx-gateway-fabric | keycloak | 8080 | HTTP | Interface admin Keycloak |
| nginx-gateway-fabric | grafana | 80 | HTTP | Interface Grafana |

### 2. Flux applicatifs internes

| Source | Destination | Port | Protocole | Description |
|--------|-------------|------|-----------|-------------|
| rhdemo-app | keycloak | 8080 | HTTP | OAuth2/OIDC (login, token validation) |
| rhdemo-app | postgresql-rhdemo | 5432 | TCP | Accès base de données |
| keycloak | postgresql-keycloak | 5432 | TCP | Accès base de données Keycloak |

### 3. Flux d'observabilité

| Source | Destination | Port | Protocole | Description |
|--------|-------------|------|-----------|-------------|
| Prometheus | rhdemo-app | 9000 | HTTP | Scrape /actuator/prometheus |
| Prometheus | postgresql-rhdemo | 9187 | HTTP | Scrape postgres_exporter /metrics |
| Prometheus | nginx-gateway-fabric | 9113 | HTTP | Scrape métriques NGINX |
| Prometheus | Loki | 3100 | HTTP | Scrape métriques Loki |
| Prometheus | Grafana | 80 | HTTP | Scrape métriques Grafana |
| Promtail | Loki | 3100 | HTTP | Push des logs |
| Grafana | Prometheus | 9090 | HTTP | Requêtes métriques (PromQL) |
| Grafana | Loki | 3100 | HTTP | Requêtes logs (LogQL) |

### 4. Flux de backup

| Source | Destination | Port | Protocole | Description |
|--------|-------------|------|-----------|-------------|
| backup-rhdemo (CronJob) | postgresql-rhdemo | 5432 | TCP | pg_dump quotidien |
| backup-keycloak (CronJob) | postgresql-keycloak | 5432 | TCP | pg_dump quotidien |

### 5. Flux système Kubernetes

| Source | Destination | Port | Protocole | Description |
|--------|-------------|------|-----------|-------------|
| Tous les pods | kube-dns | 53 | UDP/TCP | Résolution DNS |
| kubelet | Tous les pods | * | TCP | Health checks (liveness/readiness) |

### 6. Flux Debug (optionnel)

| Source | Destination | Port | Protocole | Description |
|--------|-------------|------|-----------|-------------|
| kubectl exec | Tous les pods | * | TCP | Debug interactif (via API server) |

## Flux bloqués (Egress vers Internet)

Par défaut, tous les flux sortants vers Internet sont **BLOQUÉS** sauf :
- DNS (port 53) vers kube-dns uniquement

### Exceptions potentielles (désactivées par défaut)

| Composant | Destination | Port | Justification |
|-----------|-------------|------|---------------|
| Keycloak | SMTP serveur | 25, 587, 465 | Envoi d'emails (vérification, reset password) |
| Keycloak | LDAP/AD | 389, 636 | Fédération d'identités |

Ces flux peuvent être activés via des NetworkPolicies spécifiques si nécessaire.

## Matrice des communications

```text
                    │ rhdemo-app │ keycloak │ pg-rhdemo │ pg-keycloak │ Prometheus │ Grafana │ Loki │ NGF │
────────────────────┼────────────┼──────────┼───────────┼─────────────┼────────────┼─────────┼──────┼─────┤
rhdemo-app          │     -      │    ✓     │     ✓     │      ✗      │     ✗      │    ✗    │  ✗   │  ✗  │
keycloak            │     ✗      │    -     │     ✗     │      ✓      │     ✗      │    ✗    │  ✗   │  ✗  │
postgresql-rhdemo   │     ✗      │    ✗     │     -     │      ✗      │     ✗      │    ✗    │  ✗   │  ✗  │
postgresql-keycloak │     ✗      │    ✗     │     ✗     │      -      │     ✗      │    ✗    │  ✗   │  ✗  │
Prometheus          │     ✓      │    ✗     │     ✓     │      ✗      │     -      │    ✓    │  ✓   │  ✓  │
Grafana             │     ✗      │    ✗     │     ✗     │      ✗      │     ✓      │    -    │  ✓   │  ✗  │
Loki                │     ✗      │    ✗     │     ✗     │      ✗      │     ✗      │    ✗    │  -   │  ✗  │
nginx-gateway       │     ✓      │    ✓     │     ✗     │      ✗      │     ✗      │    ✓    │  ✗   │  -  │
Promtail            │     ✗      │    ✗     │     ✗     │      ✗      │     ✗      │    ✗    │  ✓   │  ✗  │
Backup CronJobs     │     ✗      │    ✗     │     ✓     │      ✓      │     ✗      │    ✗    │  ✗   │  ✗  │
```

Légende : ✓ = Autorisé, ✗ = Bloqué, - = N/A

## Implémentation des NetworkPolicies

### Stratégie

1. **Default Deny** : Bloquer tout le trafic par défaut (ingress + egress)
2. **Whitelist** : Autoriser explicitement chaque flux légitime
3. **Least Privilege** : Limiter aux ports et protocoles strictement nécessaires

### Organisation des fichiers

Les Network Policies sont réparties en deux emplacements :

#### Namespace rhdemo-stagingkub (Helm chart)

| Fichier | Description |
|---------|-------------|
| `helm/rhdemo/templates/networkpolicy-default-deny.yaml` | Default deny + DNS |
| `helm/rhdemo/templates/networkpolicy-rhdemo-app.yaml` | Règles pour rhdemo-app |
| `helm/rhdemo/templates/networkpolicy-keycloak.yaml` | Règles pour keycloak |
| `helm/rhdemo/templates/networkpolicy-postgresql.yaml` | Règles pour les deux PostgreSQL |
| `helm/rhdemo/templates/networkpolicy-backup.yaml` | Règles pour les CronJobs de backup |

#### Namespaces externes (fichiers YAML statiques)

| Fichier | Namespace | Description |
|---------|-----------|-------------|
| `networkpolicies/monitoring-networkpolicies.yaml` | monitoring | Prometheus, AlertManager, etc. |
| `networkpolicies/loki-stack-networkpolicies.yaml` | loki-stack | Loki, Promtail, Grafana |
| `networkpolicies/nginx-gateway-networkpolicies.yaml` | nginx-gateway | NGINX Gateway Fabric |

### Application des policies externes

```bash
# Appliquer toutes les policies
cd rhDemo/infra/stagingkub/networkpolicies
./apply-networkpolicies.sh

# Mode dry-run (prévisualisation)
./apply-networkpolicies.sh --dry-run

# Supprimer les policies
./apply-networkpolicies.sh --delete
```

## Vérification des NetworkPolicies

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
./scripts/test-network-policies.sh
```

## Considérations de sécurité

### Points forts
- Isolation complète entre les bases de données (postgresql-rhdemo ↔ postgresql-keycloak)
- Pas d'accès Internet direct depuis les pods applicatifs
- Scraping Prometheus limité aux endpoints autorisés
- Trafic utilisateur filtré via Gateway uniquement
- **nginx-gateway ne peut contacter que les backends autorisés** (pas d'accès Internet)
- **Stack observabilité isolée** (monitoring, loki-stack)
- Egress strictement contrôlé pour chaque composant

### Limitations connues
- Les health checks kubelet nécessitent une règle permissive (pas de sélection par namespace)
- Le DNS est autorisé vers kube-dns uniquement (pas de DNS externe)
- Prometheus Operator nécessite un accès à l'API Server (règle plus large)

### Comparaison avec/sans Network Policies

| Scénario | Sans policies | Avec policies |
|----------|---------------|---------------|
| Pod compromis → exfiltration Internet | ✓ Possible | ✗ Bloqué |
| Pod compromis → scan réseau interne | ✓ Possible | ✗ Bloqué |
| postgresql-rhdemo → postgresql-keycloak | ✓ Possible | ✗ Bloqué |
| nginx-gateway → service non autorisé | ✓ Possible | ✗ Bloqué |
| Grafana → service non autorisé | ✓ Possible | ✗ Bloqué |

## Activation des flux externes (optionnel)

### Activer SMTP pour Keycloak

Si Keycloak doit envoyer des emails, modifier `values.yaml` :

```yaml
networkPolicies:
  keycloak:
    allowSmtp: true
    smtpCidr: "10.0.0.50/32"  # IP du serveur SMTP
```

Ou appliquer manuellement :

```yaml
# keycloak-allow-smtp.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: keycloak-allow-smtp
  namespace: rhdemo-stagingkub
spec:
  podSelector:
    matchLabels:
      app: keycloak
  policyTypes:
    - Egress
  egress:
    - to:
        - ipBlock:
            cidr: <SMTP_SERVER_IP>/32
      ports:
        - protocol: TCP
          port: 587
```

### Activer LDAP pour Keycloak

```yaml
networkPolicies:
  keycloak:
    allowLdap: true
    ldapCidr: "10.0.0.60/32"  # IP du serveur LDAP
```

### Ajouter un nouveau backend à nginx-gateway

Si vous ajoutez un nouveau service exposé via la Gateway, modifiez `nginx-gateway-networkpolicies.yaml` :

```yaml
# Ajouter dans la section egress de nginx-gateway-fabric-netpol
- to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: <NAMESPACE>
      podSelector:
        matchLabels:
          app: <SERVICE_LABEL>
  ports:
    - protocol: TCP
      port: <PORT>
```

## Dépannage

### Les pods ne peuvent plus communiquer après déploiement des policies

1. Vérifiez que Cilium est bien installé et fonctionnel :
   ```bash
   kubectl get pods -n kube-system -l k8s-app=cilium
   ```

2. Vérifiez les labels des pods :
   ```bash
   kubectl get pods -n rhdemo-stagingkub --show-labels
   ```

3. Vérifiez les Network Policies actives :
   ```bash
   kubectl describe networkpolicy -n rhdemo-stagingkub
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

## Évolutions futures

### CiliumNetworkPolicy L7 (optionnel)

Avec Cilium comme CNI, vous pouvez ajouter du filtrage HTTP :

```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: rhdemo-app-l7
  namespace: rhdemo-stagingkub
spec:
  endpointSelector:
    matchLabels:
      app: rhdemo-app
  ingress:
    - fromEndpoints:
        - matchLabels:
            io.kubernetes.pod.namespace: nginx-gateway
      toPorts:
        - ports:
            - port: "9000"
              protocol: TCP
          rules:
            http:
              - method: "GET"
              - method: "POST"
              - method: "PUT"
              - method: "DELETE"
```

### mTLS avec service mesh

Pour ajouter le chiffrement inter-services :
- Istio ou Linkerd peuvent être intégrés
- Nécessite des ajustements des Network Policies pour autoriser les sidecars
