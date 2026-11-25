---
statut: actif
verifie_le: 2026-11-22
sources:
  - rhDemo/infra/stagingkub/helm/rhdemo/templates/networkpolicy-default-deny.yaml
  - rhDemo/infra/stagingkub/helm/rhdemo/templates/networkpolicy-rhdemo-app.yaml
  - rhDemo/infra/stagingkub/networkpolicies/
  - rhDemo/infra/stagingkub/external-secrets/networkpolicies.yaml
  - rhDemo/infra/stagingkub/helm/rhdemo/values.yaml
---

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
│  │  │  NGF Controller (ngf-nginx-gateway-fabric-*)                                             │   │   │
│  │  │  Label: app.kubernetes.io/name: nginx-gateway-fabric                                     │   │   │
│  │  │  Watch API Server, pousse config via gRPC (:443/:8443)                                   │   │   │
│  │  └──────────────────┬───────────────────────────────────────────────────────────────────────┘   │   │
│  │                     │ gRPC :443/:8443                                                           │   │
│  │                     ▼                                                                           │   │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │  NGF Data Plane (shared-gateway-nginx-*)                                                 │   │   │
│  │  │  Label: app.kubernetes.io/name: shared-gateway-nginx                                     │   │   │
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
│  │  │   Grafana    │◄───│     Loki     │◄───│    Alloy     │                                        │   │
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
| Internet | shared-gateway-nginx (data plane) | 443 | HTTPS | Trafic utilisateur TLS |
| shared-gateway-nginx (data plane) | rhdemo-app | 9000 | HTTP | Application web |
| shared-gateway-nginx (data plane) | keycloak | 8080 | HTTP | Interface admin Keycloak |
| shared-gateway-nginx (data plane) | grafana | 80 | HTTP | Interface Grafana |

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
| Prometheus | kubelet, CoreDNS (kube-system) | 10250, 9153 | HTTPS/HTTP | Scrape métriques nœud et DNS |
| Prometheus | AlertManager | 9093 | HTTP | Envoi des alertes |
| Alloy | Loki | 3100 | HTTP | Push des logs |
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
| Alloy | API Server (host) | 6443 | TCP | Découverte des pods (`discovery.kubernetes`) |
| Prometheus Operator | API Server (host) | 6443 | TCP | Gestion des ServiceMonitors/PrometheusRules |
| Kube State Metrics | API Server (host) | 6443 | TCP | Collecte métriques état du cluster |
| NGF Controller | API Server (host) | 6443 | TCP | Watch des Gateway/HTTPRoute |
| NGF Data Plane → Controller | ngf-nginx-gateway-fabric | 443/8443 | TCP (gRPC) | Réception configuration NGINX |
| ESO (tous les pods) | API Server (host) | 6443 | TCP | Écriture des Secrets à partir des ExternalSecret |
| API Server | Webhook ESO | 10250 | TCP | Validation des ExternalSecret/SecretStore |
| Contrôleur ESO | OpenBao (IP fixe sur le réseau Docker `kind`) | 8200 | HTTPS | Lecture de `kv/stagingkub/*` et `kv/observability/*` ([OPENBAO.md](OPENBAO.md)) |

### 6. Flux Debug (optionnel)

| Source | Destination | Port | Protocole | Description |
|--------|-------------|------|-----------|-------------|
| kubectl exec | Tous les pods | * | TCP | Debug interactif (via API server) |

## Flux bloqués (Egress vers Internet)

Par défaut, tous les flux sortants vers Internet sont **BLOQUÉS** sauf :
- DNS (port 53) vers kube-dns uniquement

La seule sortie du cluster autorisée ne va pas vers Internet : le contrôleur External Secrets Operator joint OpenBao, conteneur de `jenkins-docker` raccordé au réseau Docker `kind`, par un `ipBlock` limité à son IP fixe (`/32`) et au port 8200. Cilium voit ce conteneur comme `world`, d'où l'`ipBlock` plutôt qu'une entité. L'IP est injectée par `install-external-secrets.sh` à l'application des policies.

### Exceptions potentielles (désactivées par défaut)

| Composant | Destination | Port | Justification |
|-----------|-------------|------|---------------|
| Keycloak | SMTP serveur | 25, 587, 465 | Envoi d'emails (vérification, reset password) |
| Keycloak | LDAP/AD | 389, 636 | Fédération d'identités |

Ces flux peuvent être activés via des NetworkPolicies spécifiques si nécessaire.

## Matrice des communications

```text
                     │ rhdemo-app │ keycloak │ pg-rhdemo │ pg-keycloak │ Prometheus │ Grafana │ Loki │ NGF DP │ NGF Ctrl │
─────────────────────┼────────────┼──────────┼───────────┼─────────────┼────────────┼─────────┼──────┼────────┼──────────┤
rhdemo-app           │     -      │    ✓     │     ✓     │      ✗      │     ✗      │    ✗    │  ✗   │   ✗    │    ✗     │
keycloak             │     ✗      │    -     │     ✗     │      ✓      │     ✗      │    ✗    │  ✗   │   ✗    │    ✗     │
postgresql-rhdemo    │     ✗      │    ✗     │     -     │      ✗      │     ✗      │    ✗    │  ✗   │   ✗    │    ✗     │
postgresql-keycloak  │     ✗      │    ✗     │     ✗     │      -      │     ✗      │    ✗    │  ✗   │   ✗    │    ✗     │
Prometheus           │     ✓      │    ✗     │     ✓     │      ✗      │     -      │    ✓    │  ✓   │   ✓    │    ✗     │
Grafana              │     ✗      │    ✗     │     ✗     │      ✗      │     ✓      │    -    │  ✓   │   ✗    │    ✗     │
Loki                 │     ✗      │    ✗     │     ✗     │      ✗      │     ✗      │    ✗    │  -   │   ✗    │    ✗     │
NGF Data Plane       │     ✓      │    ✓     │     ✗     │      ✗      │     ✗      │    ✓    │  ✗   │   -    │    ✓     │
NGF Controller       │     ✗      │    ✗     │     ✗     │      ✗      │     ✗      │    ✗    │  ✗   │   ✗    │    -     │
Alloy                │     ✗      │    ✗     │     ✗     │      ✗      │     ✗      │    ✗    │  ✓   │   ✗    │    ✗     │
Backup CronJobs      │     ✗      │    ✗     │     ✓     │      ✓      │     ✗      │    ✗    │  ✗   │   ✗    │    ✗     │
```

Légende : ✓ = Autorisé, ✗ = Bloqué, - = N/A, NGF DP = Data Plane (shared-gateway-nginx), NGF Ctrl = Controller (nginx-gateway-fabric)

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
| `networkpolicies/monitoring-networkpolicies.yaml` | monitoring | Prometheus, AlertManager, etc. + CiliumNetworkPolicies API Server |
| `networkpolicies/loki-stack-networkpolicies.yaml` | loki-stack | Loki, Alloy, Grafana + CiliumNetworkPolicy API Server |
| `networkpolicies/nginx-gateway-networkpolicies.yaml` | nginx-gateway | NGINX Gateway Fabric + CiliumNetworkPolicy API Server |
| `external-secrets/networkpolicies.yaml` | external-secrets | External Secrets Operator : default-deny, DNS, API Server (CiliumNetworkPolicy), webhook, sortie vers OpenBao. Appliqué par `scripts/components/install-external-secrets.sh` (pas par `apply-networkpolicies.sh`), qui remplace `__OPENBAO_IP__` |

> **Note** : Chaque fichier YAML peut contenir à la fois des `NetworkPolicy` Kubernetes standard
> et des `CiliumNetworkPolicy` spécifiques à Cilium. Les CiliumNetworkPolicies sont nécessaires
> pour autoriser l'accès à l'API Server (voir section [CiliumNetworkPolicy et accès API Server](#ciliumnetworkpolicy-et-accès-api-server)).

### Application et vérification

Commandes d'application (`apply-networkpolicies.sh`), tests de connectivité et de blocage, dépannage : voir le [README des NetworkPolicies](../infra/stagingkub/networkpolicies/README.md), qui porte l'exploitation. Ce document porte la conception (flux, matrice, choix Cilium).

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
- L'accès à l'API Server nécessite des CiliumNetworkPolicies (voir section dédiée ci-dessous)
- Le DNAT Cilium traduit les ports des Services ClusterIP avant l'évaluation des policies : il faut autoriser le port Service **et** le port conteneur (voir section [DNAT Cilium et ports](#dnat-cilium-et-ports-des-services-clusterip))

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
# Ajouter dans la section egress de nginx-gateway-fabric-netpol (data plane, podSelector: shared-gateway-nginx)
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

## CiliumNetworkPolicy et accès API Server

### Problème avec les NetworkPolicies standard et Cilium

Avec Cilium configuré en `kubeProxyReplacement=true` (remplacement complet de kube-proxy par eBPF),
les règles `ipBlock` standard des NetworkPolicies Kubernetes **ne fonctionnent pas** pour autoriser
l'accès à l'API Server Kubernetes. Voici pourquoi :

1. Un pod envoie une requête vers le ClusterIP de l'API Server (`10.96.0.1:443`)
2. Cilium effectue le **DNAT** (traduction d'adresse) **avant** l'évaluation de la NetworkPolicy
3. Le paquet est réécrit vers l'IP du noeud control-plane (`172.21.0.2:6443`)
4. L'API Server est identifié par Cilium comme l'entité réservée `host`, pas comme un CIDR
5. Les règles `ipBlock` ne matchent pas l'identité `host` → le paquet est **droppé**

### Solution : CiliumNetworkPolicy avec `toEntities`

Cilium fournit des entités réservées (`host`, `kube-apiserver`) qui permettent de cibler l'API Server
indépendamment de son adresse IP :

```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: allow-apiserver-<composant>
  namespace: <namespace>
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: <composant>
  egress:
    - toEntities:
        - host
        - kube-apiserver
      toPorts:
        - ports:
            - port: "6443"
              protocol: TCP
```

### CiliumNetworkPolicies déployées

| Namespace | Nom | Pod cible | Raison |
|-----------|-----|-----------|--------|
| loki-stack | `allow-apiserver-alloy` | Alloy | `discovery.kubernetes` (découverte des pods) |
| monitoring | `allow-apiserver-prometheus-operator` | Prometheus Operator | Watch ServiceMonitors/PrometheusRules |
| monitoring | `allow-apiserver-kube-state-metrics` | Kube State Metrics | Collecte métriques état cluster |
| nginx-gateway | `allow-apiserver-access` | NGINX Gateway Fabric | Watch Gateway/HTTPRoute |
| nginx-gateway | `allow-apiserver-cert-generator` | Job hook Helm `cert-generator` (NGF) | Lecture/mise à jour des Secrets `server-tls`/`agent-tls` ; ses pods n'ont pas le label du contrôleur |

### Diagnostic

Pour vérifier si un pod est bloqué par une NetworkPolicy vers l'API Server :

```bash
# Identifier l'endpoint Cilium du pod
kubectl exec -n cilium-system ds/cilium -- cilium-dbg endpoint list | grep <pod-name>

# Monitorer les drops en temps réel (remplacer <ID> par l'endpoint ID)
kubectl exec -n cilium-system ds/cilium -- cilium-dbg monitor --type drop --from <ID>

# Lister les CiliumNetworkPolicies
kubectl get ciliumnetworkpolicies -A
```

Si le monitor affiche `drop (Policy denied) ... identity <N>->host: ... -> 172.21.0.2:6443`,
il manque une CiliumNetworkPolicy `toEntities: [host, kube-apiserver]` pour ce pod.

### DNAT Cilium et ports des Services ClusterIP

Le DNAT Cilium affecte aussi les communications inter-pods via un Service ClusterIP.
Quand un pod contacte un Service sur le port exposé (ex: 443), Cilium traduit l'adresse
**avant** l'évaluation de la NetworkPolicy. Le paquet arrive donc avec le **port conteneur**
(ex: 8443), pas le port du Service.

**Conséquence** : dans les règles NetworkPolicy, il faut autoriser **les deux ports**
(service et conteneur) pour couvrir tous les cas :

```yaml
# Exemple : data plane NGF → controller NGF
# Service expose :443 mais le conteneur écoute sur :8443
ports:
  - protocol: TCP
    port: 443    # port du Service ClusterIP
  - protocol: TCP
    port: 8443   # port conteneur réel (après DNAT Cilium)
```

**Diagnostic** : `cilium-dbg monitor --type drop` montre le port réel après DNAT :

```text
drop (Policy denied) identity 17962->14583: 10.244.0.186:46896 -> 10.244.0.207:8443
#                                                                              ^^^^
#                                                          Port conteneur (pas le port Service 443)
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
