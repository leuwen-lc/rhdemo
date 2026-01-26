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
│  │                              Namespace: ingress-nginx                                            │   │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │  nginx-ingress-controller                                                                │   │   │
│  │  │  Ports: 80 (HTTP), 443 (HTTPS)                                                          │   │   │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                    │                                         │
│                                          │ :9000              │ :8080                                   │
│                                          ▼                    ▼                                         │
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
│  │  │  postgresql-rhdemo     │         │  postgresql-keycloak   │                                  │   │
│  │  │  Port: 5432 (PG)       │         │  Port: 5432 (PG)       │                                  │   │
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
│  │  │  Prometheus  │───►│   Grafana    │◄───│     Loki     │◄───│   Promtail   │                   │   │
│  │  │  :9090       │    │   :3000      │    │   :3100      │    │  (DaemonSet) │                   │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘                   │   │
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

### 1. Flux d'entrée utilisateur (via Ingress)

| Source | Destination | Port | Protocole | Description |
|--------|-------------|------|-----------|-------------|
| Internet | nginx-ingress | 443 | HTTPS | Trafic utilisateur TLS |
| nginx-ingress | rhdemo-app | 9000 | HTTP | Application web |
| nginx-ingress | keycloak | 8080 | HTTP | Interface admin Keycloak |

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
| Promtail | Loki | 3100 | HTTP | Push des logs |
| Grafana | Prometheus | 9090 | HTTP | Requêtes métriques |
| Grafana | Loki | 3100 | HTTP | Requêtes logs |

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
                    │ rhdemo-app │ keycloak │ pg-rhdemo │ pg-keycloak │ Prometheus │ Grafana │ Ingress │
────────────────────┼────────────┼──────────┼───────────┼─────────────┼────────────┼─────────┼─────────┤
rhdemo-app          │     -      │    ✓     │     ✓     │      ✗      │     ✗      │    ✗    │    ✗    │
keycloak            │     ✗      │    -     │     ✗     │      ✓      │     ✗      │    ✗    │    ✗    │
postgresql-rhdemo   │     ✗      │    ✗     │     -     │      ✗      │     ✗      │    ✗    │    ✗    │
postgresql-keycloak │     ✗      │    ✗     │     ✗     │      -      │     ✗      │    ✗    │    ✗    │
Prometheus          │     ✓      │    ✗     │     ✓     │      ✗      │     -      │    ✗    │    ✗    │
Grafana             │     ✗      │    ✗     │     ✗     │      ✗      │     ✓      │    -    │    ✗    │
Ingress             │     ✓      │    ✓     │     ✗     │      ✗      │     ✗      │    ✗    │    -    │
Backup CronJobs     │     ✗      │    ✗     │     ✓     │      ✓      │     ✗      │    ✗    │    ✗    │
```

Légende : ✓ = Autorisé, ✗ = Bloqué, - = N/A

## Implémentation des NetworkPolicies

### Stratégie

1. **Default Deny** : Bloquer tout le trafic par défaut (ingress + egress)
2. **Whitelist** : Autoriser explicitement chaque flux légitime
3. **Least Privilege** : Limiter aux ports et protocoles strictement nécessaires

### Fichiers NetworkPolicy

| Fichier | Description |
|---------|-------------|
| `default-deny-all.yaml` | Politique par défaut bloquant tout |
| `allow-dns.yaml` | Autoriser DNS pour tous les pods |
| `rhdemo-app-netpol.yaml` | Règles pour rhdemo-app |
| `keycloak-netpol.yaml` | Règles pour keycloak |
| `postgresql-rhdemo-netpol.yaml` | Règles pour postgresql-rhdemo |
| `postgresql-keycloak-netpol.yaml` | Règles pour postgresql-keycloak |
| `backup-cronjobs-netpol.yaml` | Règles pour les CronJobs de backup |

## Vérification des NetworkPolicies

### Tester la connectivité autorisée

```bash
# rhdemo-app → postgresql-rhdemo
kubectl exec -n rhdemo-stagingkub deploy/rhdemo-app -- nc -zv postgresql-rhdemo 5432

# rhdemo-app → keycloak
kubectl exec -n rhdemo-stagingkub deploy/rhdemo-app -- nc -zv keycloak 8080

# Prometheus → rhdemo-app
kubectl exec -n monitoring deploy/prometheus-server -- wget -qO- http://rhdemo-app.rhdemo-stagingkub:9000/actuator/prometheus | head
```

### Tester le blocage

```bash
# rhdemo-app → Internet (doit échouer)
kubectl exec -n rhdemo-stagingkub deploy/rhdemo-app -- wget -qO- --timeout=5 http://example.com || echo "BLOQUÉ (OK)"

# postgresql → Internet (doit échouer)
kubectl exec -n rhdemo-stagingkub sts/postgresql-rhdemo -- wget -qO- --timeout=5 http://example.com || echo "BLOQUÉ (OK)"

# keycloak → postgresql-rhdemo (doit échouer - mauvaise DB)
kubectl exec -n rhdemo-stagingkub deploy/keycloak -- nc -zv postgresql-rhdemo 5432 || echo "BLOQUÉ (OK)"
```

## Considérations de sécurité

### Points forts
- Isolation complète entre les bases de données
- Pas d'accès Internet direct depuis les pods applicatifs
- Scraping Prometheus limité aux endpoints autorisés
- Trafic utilisateur filtré via Ingress uniquement

### Limitations
- Les health checks kubelet nécessitent une règle permissive (pas de sélection par namespace)
- Le DNS est autorisé vers kube-dns uniquement (pas de DNS externe)
- Les CronJobs de backup ont accès aux deux PostgreSQL (nécessaire pour leur fonction)

### Améliorations futures
- Ajouter des NetworkPolicies dans le namespace `monitoring`
- Implémenter mTLS entre les services (via Istio/Linkerd)
- Ajouter des règles egress plus strictes par CIDR pour bloquer les IPs internes

## Activation des flux externes (optionnel)

### Activer SMTP pour Keycloak

Si Keycloak doit envoyer des emails :

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
# keycloak-allow-ldap.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: keycloak-allow-ldap
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
            cidr: <LDAP_SERVER_IP>/32
      ports:
        - protocol: TCP
          port: 636  # LDAPS
```
