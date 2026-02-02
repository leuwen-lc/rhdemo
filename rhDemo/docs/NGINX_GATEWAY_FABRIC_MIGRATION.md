# Étude d'impact : Migration Nginx Ingress Controller → Nginx Gateway Fabric 2.3

**Date** : 2026-02-02
**Statut** : ✅ Migration implémentée
**Environnement cible** : stagingkub (Kubernetes/KinD)
**Version NGF cible** : **2.3.0** (dernière stable, décembre 2024)
**Architecture** : **Shared Gateway** (Gateway partagé dans nginx-gateway)

---

## 1. Contexte de la dépréciation

Le projet **Ingress-NGINX** (maintenu par la communauté Kubernetes) atteindra sa fin de vie en **mars 2026**. Après cette date :
- Plus de correctifs de sécurité
- Plus de mises à jour
- Dépôt en mode lecture seule

**Important** : NGINX Gateway Fabric est le successeur recommandé par F5/NGINX et implémente la **Gateway API**, le nouveau standard Kubernetes pour la gestion du trafic.

### Choix de la version 2.3.0

| Version | Date | Recommandation |
|---------|------|----------------|
| 2.2.0 | Octobre 2024 | ❌ Ancienne |
| 2.2.1 | Novembre 2024 | ❌ Correctifs mineurs |
| 2.2.2 | Décembre 2024 | ❌ Correctifs mineurs |
| **2.3.0** | **18 décembre 2024** | ✅ **Recommandée** - Gateway API v1.4.1, conformité complète |

La version 2.3.0 est l'une des 5 seules implémentations Gateway API certifiées conformes.

### Références

- [Migration guide NGINX Ingress → Gateway Fabric](https://docs.nginx.com/nginx-gateway-fabric/install/ingress-to-gateway/)
- [NGINX Gateway Fabric Installation](https://docs.nginx.com/nginx-gateway-fabric/install/)
- [NGINX Gateway Fabric GitHub](https://github.com/nginx/nginx-gateway-fabric)
- [NGINX Gateway Fabric 2.0 Architecture](https://community.f5.com/kb/technicalarticles/announcing-f5-nginx-gateway-fabric-2-0-0-with-a-new-distributed-architecture/341657)
- [Ingress NGINX Deprecation Guide](https://k8s-ops.net/posts/nginx-ingress-deprecation-gateway-api-migration-guide/)
- [SnippetsFilter Documentation](https://docs.nginx.com/nginx-gateway-fabric/traffic-management/snippets/)

---

## 2. Changement d'architecture

| Aspect | Nginx Ingress Controller | NGINX Gateway Fabric 2.x |
|--------|-------------------------|--------------------------|
| **API** | `networking.k8s.io/v1` (Ingress) | `gateway.networking.k8s.io/v1` (Gateway API) |
| **Ressources** | 1 seule (`Ingress`) | 3+ (`GatewayClass`, `Gateway`, `HTTPRoute`) |
| **Architecture** | Control + Data plane combinés | **Distribué** : control et data planes séparés |
| **Configuration** | Annotations propriétaires | Policies standardisées (CRDs) |
| **Namespace** | `ingress-nginx` | `nginx-gateway` |
| **Installation** | Manifest YAML officiel KinD | Helm chart OCI |

### 2.1 Architecture Shared Gateway (implémentée)

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARCHITECTURE SHARED GATEWAY                        │
└─────────────────────────────────────────────────────────────────────────────┘

Internet (HTTPS :443)
         │
         ▼
┌─────────────────────────┐
│   KinD Node            │
│   hostPort: 443        │
│         │              │
│         ▼              │
│   NodePort: 32616      │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  NAMESPACE: nginx-gateway                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  shared-gateway (Gateway)                                               ││
│  │  - Listener: https (*.intra.leuwen-lc.fr:443)                          ││
│  │  - TLS: shared-tls-cert (auto-signé) ou intra-wildcard-tls (Let's Encrypt)
│  │  - allowedRoutes: from: All                                             ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│  ┌───────────────────────┐                                                  │
│  │ ClientSettingsPolicy  │ ← maxBodySize: 50m (pour toutes les apps)        │
│  │ (cible: shared-gateway)│                                                 │
│  └───────────────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          │ parentRefs (cross-namespace)
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  NAMESPACE: rhdemo-stagingkub                                               │
│  ┌───────────────┐     ┌───────────────┐                                    │
│  │ HTTPRoute     │     │ HTTPRoute     │                                    │
│  │ rhdemo-route  │     │ keycloak-route│                                    │
│  │ → rhdemo-app  │     │ → keycloak    │                                    │
│  └───────────────┘     └───────┬───────┘                                    │
│                                │                                            │
│                    ┌───────────┴───────────┐                                │
│                    │ SnippetsFilter        │                                │
│                    │ keycloak-proxy-buffers│                                │
│                    └───────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          │ parentRefs (cross-namespace)
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  NAMESPACE: loki-stack                                                       │
│  ┌───────────────┐                                                          │
│  │ HTTPRoute     │ (créé par grafana-gateway.yaml)                          │
│  │ grafana       │                                                          │
│  │ → grafana     │                                                          │
│  └───────────────┘                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Avantages de l'architecture Shared Gateway** :
- **Certificat unique** : Un seul Secret TLS wildcard `*.intra.leuwen-lc.fr` pour toutes les apps
- **Point d'entrée centralisé** : Gestion simplifiée du NodePort (32616)
- **Cross-namespace** : Les HTTPRoutes de différents namespaces s'attachent au même Gateway
- **Consistance** : Grafana, rhdemo, keycloak utilisent la même configuration TLS

---

## 3. Inventaire des fichiers impactés

### 3.1 Fichiers à réécrire complètement (5 fichiers)

| Fichier | Impact | Effort |
|---------|--------|--------|
| `helm/rhdemo/templates/ingress.yaml` | Remplacer par `gateway.yaml` + `httproute.yaml` | **Élevé** |
| `scripts/init-stagingkub.sh` (lignes 183-286) | Nouvelle procédure d'installation Helm | **Élevé** |
| `helm/rhdemo/values.yaml` (section `ingress:` et `nginx-ingress:`) | Nouvelle structure de configuration | **Moyen** |
| `helm/observability/grafana-values.yaml` | Conversion Ingress Grafana | **Moyen** |
| `scripts/validate-stagingkub.sh` | Nouvelles vérifications Gateway | **Moyen** |

### 3.2 Fichiers à modifier (4 fichiers)

| Fichier | Modification |
|---------|--------------|
| `helm/rhdemo/templates/networkpolicy-rhdemo-app.yaml` | Changer namespace `ingress-nginx` → `nginx-gateway` |
| `helm/rhdemo/templates/networkpolicy-keycloak.yaml` | Changer namespace `ingress-nginx` → `nginx-gateway` |
| `rbac/jenkins-role.yaml` | Ajouter permissions Gateway API CRDs |
| `rbac/setup-jenkins-rbac.sh` | Mettre à jour documentation |

### 3.3 Documentation à mettre à jour (4 fichiers)

- `infra/stagingkub/README.md`
- `helm/rhdemo/README.md`
- `CLAUDE.md` (racine du dépôt)
- `docs/NETWORK_SECURITY_POLICY.md`

---

## 4. Conversion des ressources Kubernetes

### 4.1 Ingress actuel → Shared Gateway + HTTPRoute

**Avant** (Ingress) :

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: rhdemo-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts: [rhdemo-stagingkub.intra.leuwen-lc.fr]
    secretName: intra-wildcard-tls
  rules:
  - host: rhdemo-stagingkub.intra.leuwen-lc.fr
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: rhdemo-app
            port:
              number: 9000
```

**Après** (Gateway API avec Shared Gateway) :

L'architecture implémentée utilise un **Gateway partagé** dans le namespace `nginx-gateway`, auquel s'attachent les HTTPRoutes de différents namespaces.

```yaml
# 1. GatewayClass (créé automatiquement par l'installation Helm de NGF)
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: nginx
spec:
  controllerName: gateway.nginx.org/nginx-gateway-controller
---
# 2. Shared Gateway (créé par init-stagingkub.sh dans nginx-gateway)
# Fichier: infra/stagingkub/shared-gateway.yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: shared-gateway
  namespace: nginx-gateway  # ← Namespace centralisé
spec:
  gatewayClassName: nginx
  listeners:
    - name: https
      hostname: "*.intra.leuwen-lc.fr"  # ← Wildcard pour toutes les apps
      port: 443
      protocol: HTTPS
      tls:
        mode: Terminate
        certificateRefs:
          # Certificat auto-signé (init-stagingkub.sh) ou Let's Encrypt (cert-manager)
          # Let's Encrypt: intra-wildcard-tls
          - name: shared-tls-cert
            kind: Secret
      allowedRoutes:
        namespaces:
          from: All  # ← Permet les HTTPRoutes de tous les namespaces
---
# 3. HTTPRoute (dans le namespace de l'application)
# S'attache au shared-gateway via parentRefs cross-namespace
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: rhdemo-route
  namespace: rhdemo-stagingkub
spec:
  parentRefs:
  - name: shared-gateway
    namespace: nginx-gateway  # ← Référence cross-namespace
    sectionName: https
  hostnames:
  - rhdemo-stagingkub.intra.leuwen-lc.fr
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: rhdemo-app
      port: 9000
```

### 4.1.1 Modes Gateway : Shared vs Dedicated

Le chart Helm supporte deux modes via `values.yaml` :

| Mode                             | Configuration              | Cas d'usage                                |
|----------------------------------|----------------------------|--------------------------------------------|
| **Shared Gateway** (recommandé)  | `useSharedGateway: true`   | Certificat TLS unique, gestion centralisée |
| **Dedicated Gateway**            | `useSharedGateway: false`  | Isolation complète par namespace           |

```yaml
# values.yaml - Mode shared (défaut)
gateway:
  enabled: true
  useSharedGateway: true  # ← Utilise le shared-gateway
  sharedGateway:
    name: shared-gateway
    namespace: nginx-gateway
    sectionName: https
```

### 4.2 Conversion des annotations

| Annotation Ingress actuelle | Équivalent Gateway Fabric |
|----------------------------|---------------------------|
| `nginx.ingress.kubernetes.io/ssl-redirect: "true"` | **Natif** : HTTPS listeners redirigent automatiquement |
| `nginx.ingress.kubernetes.io/force-ssl-redirect: "true"` | **Natif** : même comportement |
| `nginx.ingress.kubernetes.io/proxy-body-size: "10m"` | `ClientSettingsPolicy` CRD avec `body.maxSize: 10m` |
| `nginx.ingress.kubernetes.io/proxy-buffer-size: "128k"` | ⚠️ **SnippetsFilter** (voir section 4.4) |
| `nginx.ingress.kubernetes.io/proxy-buffers-number: "4"` | ⚠️ **SnippetsFilter** (voir section 4.4) |

**Exemple de ClientSettingsPolicy** :

```yaml
apiVersion: gateway.nginx.org/v1alpha1
kind: ClientSettingsPolicy
metadata:
  name: rhdemo-client-settings
  namespace: rhdemo-stagingkub
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: rhdemo-gateway
  body:
    maxSize: 10m
```

### 4.3 Headers X-Forwarded-* (Simplification majeure)

**Bonne nouvelle** : NGF ajoute automatiquement tous les headers X-Forwarded-* par défaut :

```nginx
# Headers ajoutés automatiquement par NGF à chaque location block
proxy_set_header Host "$gw_api_compliant_host";
proxy_set_header X-Forwarded-For "$proxy_add_x_forwarded_for";
proxy_set_header X-Forwarded-Proto "$scheme";
proxy_set_header X-Forwarded-Host "$host";
proxy_set_header X-Forwarded-Port "$server_port";
proxy_set_header X-Real-IP "$remote_addr";
proxy_set_header Upgrade "$http_upgrade";
proxy_set_header Connection "$connection_upgrade";
```

**Impact** : La configuration manuelle actuelle dans `init-stagingkub.sh` (lignes 246-277) qui crée les ConfigMaps `ingress-nginx-controller` et `custom-headers` **n'est plus nécessaire**.

### 4.4 Proxy Buffers pour Keycloak (SnippetsFilter)

⚠️ **Point critique** : Les directives `proxy_buffer_size` et `proxy_buffers` ne sont **PAS encore supportées nativement** dans NGF. Une `ProxySettingsPolicy` est prévue mais pas encore disponible.

**Solution** : Utiliser **SnippetsFilter** pour injecter la configuration NGINX personnalisée.

#### Activation de SnippetsFilter

SnippetsFilter est **désactivé par défaut** pour des raisons de sécurité. Pour l'activer :

```bash
# Via Helm
helm install ngf oci://ghcr.io/nginx/charts/nginx-gateway-fabric \
  --set nginxGateway.snippetsFilters.enable=true \
  # ... autres options
```

#### Configuration SnippetsFilter pour Keycloak

```yaml
apiVersion: gateway.nginx.org/v1alpha1
kind: SnippetsFilter
metadata:
  name: keycloak-proxy-buffers
  namespace: rhdemo-stagingkub
spec:
  snippets:
    - context: http.server.location
      value: |
        proxy_buffer_size 128k;
        proxy_buffers 4 128k;
        proxy_busy_buffers_size 256k;
```

#### Référencement dans HTTPRoute

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: keycloak-route
  namespace: rhdemo-stagingkub
spec:
  parentRefs:
  - name: rhdemo-gateway
    sectionName: https-keycloak
  hostnames:
  - keycloak-stagingkub.intra.leuwen-lc.fr
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    filters:
    - type: ExtensionRef
      extensionRef:
        group: gateway.nginx.org
        kind: SnippetsFilter
        name: keycloak-proxy-buffers
    backendRefs:
    - name: keycloak
      port: 8080
```

#### Risques de SnippetsFilter

| Risque | Mitigation |
|--------|------------|
| Configuration NGINX invalide | Tester en environnement de dev avant prod |
| Bloque les mises à jour de config | Valider la syntaxe NGINX avant apply |
| Accès aux certificats TLS | Restreindre l'accès RBAC aux SnippetsFilter |

---

## 5. Modification du script d'installation

### Avant (init-stagingkub.sh lignes 183-286)

```bash
# Installation via manifest officiel KinD
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Configuration manuelle des NodePorts
kubectl patch svc ingress-nginx-controller -n ingress-nginx -p '{"spec":{"type":"NodePort",...}}'

# Configuration manuelle des headers X-Forwarded-* (70+ lignes)
kubectl patch configmap ingress-nginx-controller ...
cat <<EOF | kubectl apply -f - # ConfigMap custom-headers
...
EOF
```

### Après (simplifié grâce aux headers automatiques + shared-gateway)

```bash
# 1. Installer les CRDs Gateway API
echo "Installation des CRDs Gateway API..."
kubectl kustomize "https://github.com/nginx/nginx-gateway-fabric/config/crd/gateway-api/standard?ref=v2.3.0" | kubectl apply -f -

# 2. Installer NGINX Gateway Fabric via Helm OCI
echo "Installation de NGINX Gateway Fabric 2.3.0..."
helm install ngf oci://ghcr.io/nginx/charts/nginx-gateway-fabric \
  --version 2.3.0 \
  --create-namespace \
  -n nginx-gateway \
  --set nginx.service.type=NodePort \
  --set nginx.service.externalTrafficPolicy=Local \
  --set nginxGateway.snippetsFilters.enable=true

# 3. Attendre le déploiement (control plane)
echo "Attente du démarrage du control plane..."
kubectl wait --namespace nginx-gateway \
  --for=condition=available deployment/ngf-nginx-gateway-fabric \
  --timeout=120s

# 4. Créer le certificat TLS wildcard auto-signé
echo "Création du certificat TLS wildcard..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /tmp/tls.key \
    -out /tmp/tls.crt \
    -subj "/CN=*.intra.leuwen-lc.fr/O=RHDemo"

kubectl create secret tls shared-tls-cert \
    --key=/tmp/tls.key \
    --cert=/tmp/tls.crt \
    -n nginx-gateway

# 5. Créer le shared-gateway
echo "Création du shared-gateway..."
kubectl apply -f infra/stagingkub/shared-gateway.yaml

# 6. IMPORTANT: Patcher le NodePort après création du Gateway
# Le Service est créé dynamiquement par NGF quand le Gateway est créé
echo "Attente du Service shared-gateway-nginx..."
kubectl wait --namespace nginx-gateway \
    --for=jsonpath='{.spec.type}'=NodePort \
    service/shared-gateway-nginx \
    --timeout=60s

# CRITIQUE: Utiliser --type='json' (pas --type='merge') pour les éléments de liste
kubectl patch svc shared-gateway-nginx -n nginx-gateway --type='json' \
    -p='[{"op":"replace","path":"/spec/ports/0/nodePort","value":32616}]'

echo "✅ NGINX Gateway Fabric 2.3.0 + shared-gateway installés"
# Note: Les headers X-Forwarded-* sont configurés automatiquement par NGF
```

### 5.1 Problème NodePort et solution

⚠️ **Point critique découvert lors de l'implémentation** : Les options Helm `nginx.service.nodePorts[].port` ne fonctionnent pas comme attendu. Le NodePort doit être patché **après** la création du Gateway.

**Problème** : Le Service NodePort est créé dynamiquement par NGF quand le Gateway est créé, pas lors de l'installation Helm.

**Erreur courante** avec `--type='merge'` :

```bash
# ❌ NE FONCTIONNE PAS - merge ne modifie pas les éléments de liste
kubectl patch svc shared-gateway-nginx -n nginx-gateway --type='merge' \
    -p '{"spec":{"ports":[{"nodePort":32616}]}}'
```

**Solution** avec `--type='json'` :

```bash
# ✅ FONCTIONNE - json patch pour modifier un élément de liste par index
kubectl patch svc shared-gateway-nginx -n nginx-gateway --type='json' \
    -p='[{"op":"replace","path":"/spec/ports/0/nodePort","value":32616}]'
```

**Explication** :

- `--type='merge'` : Fusionne les objets mais ne peut pas cibler un élément spécifique dans une liste
- `--type='json'` : Permet d'utiliser JSON Patch (RFC 6902) pour modifier un élément par son index (`/spec/ports/0`)

### Syntaxe des NodePorts (format Helm)

La configuration des NodePorts dans NGF utilise un format différent de l'ancien Ingress Controller :

```yaml
# Format Helm values.yaml pour NGF
nginx:
  service:
    type: NodePort
    externalTrafficPolicy: Local  # Préserve l'IP client
    nodePorts:
      - port: 31792        # NodePort exposé
        listenerPort: 80   # Port du listener Gateway (HTTP)
      - port: 32616        # NodePort exposé
        listenerPort: 443  # Port du listener Gateway (HTTPS)
```

**Important** : Les `listenerPort` doivent correspondre aux ports définis dans la ressource Gateway.

---

## 6. Impact sur les Network Policies

Les Network Policies actuelles référencent le namespace `ingress-nginx` :

```yaml
# Dans networkpolicy-rhdemo-app.yaml et networkpolicy-keycloak.yaml
- from:
  - namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: ingress-nginx  # ← À changer
```

**Modification requise** :

```yaml
- from:
  - namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: nginx-gateway  # ← Nouveau namespace
```

---

## 7. Impact sur le RBAC Jenkins

Le fichier `rbac/jenkins-role.yaml` doit être enrichi pour gérer les CRDs Gateway API et SnippetsFilter :

```yaml
# Ajouter ces règles pour Gateway API (standard)
- apiGroups: ["gateway.networking.k8s.io"]
  resources:
    - gateways
    - gateways/status
    - httproutes
    - httproutes/status
    - gatewayclasses
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Ajouter pour les policies et SnippetsFilter NGINX Gateway Fabric
- apiGroups: ["gateway.nginx.org"]
  resources:
    - clientsettingspolicies
    - clientsettingspolicies/status
    - snippetsfilters              # CRITIQUE pour les proxy buffers Keycloak
    - snippetsfilters/status
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

**Note** : Sans les permissions `snippetsfilters`, le déploiement CD échouera car la configuration des proxy buffers pour Keycloak utilise un SnippetsFilter.

---

## 8. Impact sur la configuration KinD

La configuration `kind-config.yaml` a été mise à jour pour utiliser **Cilium 1.18** comme CNI :

```yaml
networking:
  disableDefaultCNI: true   # Désactive kindnet
  kubeProxyMode: none       # Cilium remplace kube-proxy (eBPF)
```

### Avantages de Cilium pour cette migration

| Fonctionnalité | Bénéfice |
|----------------|----------|
| **Network Policies L7** | Filtrage HTTP/gRPC natif (pas besoin de sidecar) |
| **eBPF kube-proxy replacement** | Meilleures performances que iptables |
| **Hubble** | Observabilité réseau intégrée |
| **Compatibilité Gateway API** | Cilium supporte aussi Gateway API (alternative future) |

### Ports mappés

Les ports mappés (31792/32616) restent compatibles avec les NodePorts de Gateway Fabric.

### Script d'installation mis à jour

Le script `init-stagingkub.sh` installe maintenant automatiquement :
1. Cilium 1.18.6 (CNI + kube-proxy replacement)
2. Nginx Ingress Controller (sera remplacé par NGF)

---

## 9. Outil de migration automatique

L'outil **ingress2gateway** peut aider à la conversion initiale :

```bash
# Installation
go install github.com/kubernetes-sigs/ingress2gateway@latest

# Conversion
ingress2gateway print \
  --providers=nginx \
  --input-file=rhDemo/infra/stagingkub/helm/rhdemo/templates/ingress.yaml
```

**Attention** : L'outil génère une base qu'il faut réviser manuellement. Les annotations spécifiques Keycloak (proxy-buffer-size) ne seront pas converties automatiquement.

---

## 10. Matrice des risques (mise à jour après recherche)

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Headers X-Forwarded-* mal configurés | **Faible** ✅ | OAuth2 cassé | NGF les configure automatiquement |
| Proxy buffers insuffisants pour Keycloak | **Élevée** ⚠️ | 502 Bad Gateway | Configurer SnippetsFilter (section 4.4) |
| SnippetsFilter invalide bloque les updates | **Moyenne** | Config gelée | Tester la syntaxe NGINX avant apply |
| Network Policies bloquant le trafic | **Moyenne** | App inaccessible | Valider namespace `nginx-gateway` |
| Jenkins sans permissions Gateway API | **Élevée** | Déploiement CD échoue | Mettre à jour RBAC avant migration |
| Jenkins sans permissions SnippetsFilter | **Élevée** | Déploiement CD échoue | Ajouter `snippetsfilters` au RBAC |
| Rollback difficile | **Faible** | Downtime prolongé | Conserver l'ancien Ingress en parallèle |

### Changements de risque après recherche

| Élément | Avant recherche | Après recherche | Raison |
|---------|-----------------|-----------------|--------|
| Headers X-Forwarded-* | Risque élevé | **Risque faible** | NGF les ajoute automatiquement |
| Proxy buffers | Via Policy | **Via SnippetsFilter** | ProxySettingsPolicy pas encore dispo |
| Activation SnippetsFilter | Non identifié | **Nouveau risque** | Désactivé par défaut, nécessite Helm flag |

---

## 11. Plan de migration suggéré

| Phase | Actions |
|-------|---------|
| **1. Préparation** | Créer branche, mettre à jour RBAC, tester localement |
| **2. Templates Helm** | Créer `gateway.yaml`, `httproute.yaml`, `clientsettingspolicy.yaml` |
| **3. Scripts** | Modifier `init-stagingkub.sh`, `validate-stagingkub.sh` |
| **4. Network Policies** | Changer namespace dans les sélecteurs |
| **5. Tests locaux** | Déployer sur cluster KinD de test |
| **6. Documentation** | Mettre à jour README, CLAUDE.md |
| **7. Déploiement** | Appliquer sur stagingkub avec rollback possible |

---

## 12. Conclusion et statut

**Statut** : ✅ **Migration terminée et fonctionnelle**

### Résumé de l'implémentation

| Élément                  | Décision finale                            | Statut |
|--------------------------|--------------------------------------------|--------|
| Version NGF              | **2.3.0**                                  | ✅     |
| Architecture             | **Shared Gateway** (recommandé)            | ✅     |
| Headers X-Forwarded-*    | **Automatiques** (plus de ConfigMaps)      | ✅     |
| Proxy buffers Keycloak   | **SnippetsFilter**                         | ✅     |
| NodePort patching        | **`--type='json'`** (pas merge)            | ✅     |
| Certificat TLS           | Wildcard auto-signé `*.intra.leuwen-lc.fr` | ✅     |

### Points critiques résolus

1. ✅ **TLS/OAuth2** : Headers X-Forwarded-* automatiques dans NGF
2. ✅ **Proxy buffers** : SnippetsFilter activé via `snippetsFilters.enable=true`
3. ✅ **RBAC Jenkins** : Permissions `gateway.networking.k8s.io` et `gateway.nginx.org` ajoutées
4. ✅ **NodePort** : Patch JSON après création du Gateway (pas via options Helm)
5. ✅ **Certificat** : Domaine `*.intra.leuwen-lc.fr` (pas `*.stagingkub.local`)

### Avantages constatés après migration

- **Simplification** : Plus de ConfigMaps manuels pour les headers X-Forwarded-*
- **Consistance** : Toutes les apps (rhdemo, keycloak, grafana) utilisent le même Gateway
- **Certificat unique** : Un seul Secret TLS wildcard pour tout le domaine
- **Gateway API standard** : Portable vers Cilium Gateway, Envoy, etc.
- **Architecture distribuée** : Control et data planes séparés (meilleure scalabilité)

### Fichiers modifiés/créés

| Fichier                                           | Action   |
|---------------------------------------------------|----------|
| `helm/rhdemo/templates/gateway.yaml`              | Créé     |
| `helm/rhdemo/templates/httproute.yaml`            | Créé     |
| `helm/rhdemo/templates/snippetsfilter.yaml`       | Créé     |
| `helm/rhdemo/templates/clientsettingspolicy.yaml` | Créé     |
| `helm/rhdemo/templates/ingress.yaml`              | Supprimé |
| `helm/rhdemo/values.yaml`                         | Modifié  |
| `scripts/init-stagingkub.sh`                      | Modifié  |
| `scripts/validate-stagingkub.sh`                  | Modifié  |
| `shared-gateway.yaml`                             | Créé     |
| `rbac/jenkins-role.yaml`                          | Modifié  |
| Network Policies                                  | Modifié  |
| `Jenkinsfile-CD`                                  | Modifié  |

### Commandes utiles post-migration

```bash
# Vérifier le Gateway partagé
kubectl get gateway -n nginx-gateway

# Vérifier les HTTPRoutes
kubectl get httproute -n rhdemo-stagingkub
kubectl get httproute -n loki-stack

# Vérifier le NodePort du Service
kubectl get svc shared-gateway-nginx -n nginx-gateway -o jsonpath='{.spec.ports[0].nodePort}'

# Tester la connectivité
curl -k https://rhdemo-stagingkub.intra.leuwen-lc.fr
curl -k https://keycloak-stagingkub.intra.leuwen-lc.fr
curl -k https://grafana-stagingkub.intra.leuwen-lc.fr

# Voir les logs NGF
kubectl logs -n nginx-gateway deployment/ngf-nginx-gateway-fabric
```

---

## Annexe : Templates Helm implémentés

### A. gateway.yaml (mode dedicated uniquement)

Le Gateway dédié n'est créé que si `useSharedGateway: false`. Sinon, les HTTPRoutes s'attachent au shared-gateway.

```yaml
{{- if .Values.gateway.enabled }}
{{- if not .Values.gateway.useSharedGateway }}
# Gateway dédié - créé uniquement si useSharedGateway: false
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: {{ .Values.gateway.dedicatedGateway.name }}
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "rhdemo.labels" . | nindent 4 }}
spec:
  gatewayClassName: {{ .Values.gateway.dedicatedGateway.className }}
  listeners:
  {{- range .Values.gateway.dedicatedGateway.listeners }}
  - name: {{ .name }}
    hostname: {{ .hostname | quote }}
    port: {{ .port }}
    protocol: {{ .protocol }}
    {{- if .tls }}
    tls:
      mode: {{ .tls.mode }}
      certificateRefs:
      - name: {{ .tls.secretName }}
        kind: Secret
    {{- end }}
    allowedRoutes:
      namespaces:
        from: Same
  {{- end }}
{{- end }}
{{- end }}
```

### B. httproute.yaml (supporte shared et dedicated)

```yaml
{{- if .Values.gateway.enabled }}
{{- range .Values.gateway.routes }}
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: {{ .name }}
  namespace: {{ $.Values.global.namespace }}
  labels:
    {{- include "rhdemo.labels" $ | nindent 4 }}
spec:
  parentRefs:
  {{- if $.Values.gateway.useSharedGateway }}
  # Utilise le Gateway partagé (créé par init-stagingkub.sh)
  - name: {{ $.Values.gateway.sharedGateway.name }}
    namespace: {{ $.Values.gateway.sharedGateway.namespace }}
    sectionName: {{ $.Values.gateway.sharedGateway.sectionName }}
  {{- else }}
  # Utilise le Gateway dédié (créé par ce chart)
  - name: {{ $.Values.gateway.dedicatedGateway.name }}
    sectionName: {{ .listenerName }}
  {{- end }}
  hostnames:
  - {{ .hostname | quote }}
  rules:
  {{- range .rules }}
  - matches:
    - path:
        type: {{ .pathType }}
        value: {{ .path }}
    {{- if $.Values.gateway.snippetsFilter.enabled }}
    {{- if eq .serviceName "keycloak" }}
    filters:
    - type: ExtensionRef
      extensionRef:
        group: gateway.nginx.org
        kind: SnippetsFilter
        name: keycloak-proxy-buffers
    {{- end }}
    {{- end }}
    backendRefs:
    - name: {{ .serviceName }}
      port: {{ .servicePort }}
  {{- end }}
{{- end }}
{{- end }}
```

### C. snippetsfilter.yaml (proxy buffers pour Keycloak)

```yaml
{{- if .Values.gateway.enabled }}
{{- if .Values.gateway.snippetsFilter.enabled }}
# SnippetsFilter pour les gros cookies OAuth2 de Keycloak
apiVersion: gateway.nginx.org/v1alpha1
kind: SnippetsFilter
metadata:
  name: keycloak-proxy-buffers
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "rhdemo.labels" . | nindent 4 }}
spec:
  snippets:
    - context: http.server.location
      value: |
        # Buffers pour les gros headers Keycloak (cookies de session OAuth2)
        proxy_buffer_size {{ .Values.gateway.snippetsFilter.proxyBufferSize }};
        proxy_buffers {{ .Values.gateway.snippetsFilter.proxyBuffersNumber }} {{ .Values.gateway.snippetsFilter.proxyBufferSize }};
        proxy_busy_buffers_size {{ .Values.gateway.snippetsFilter.proxyBusyBuffersSize }};
{{- end }}
{{- end }}
```

### D. clientsettingspolicy.yaml (mode dedicated uniquement)

⚠️ **Important** : Cette policy n'est créée que pour le Gateway dédié. Pour le shared-gateway, la ClientSettingsPolicy est créée dans le namespace `nginx-gateway` par `init-stagingkub.sh`.

```yaml
{{- if .Values.gateway.enabled }}
{{- if .Values.gateway.clientSettings.enabled }}
{{- if not .Values.gateway.useSharedGateway }}
# ClientSettingsPolicy - uniquement pour le Gateway dédié
apiVersion: gateway.nginx.org/v1alpha1
kind: ClientSettingsPolicy
metadata:
  name: rhdemo-client-settings
  namespace: {{ .Values.global.namespace }}
spec:
  targetRef:  # ← ATTENTION: targetRef (singulier), pas targetRefs
    group: gateway.networking.k8s.io
    kind: Gateway
    name: {{ .Values.gateway.dedicatedGateway.name }}
  body:
    maxSize: {{ .Values.gateway.clientSettings.maxBodySize | quote }}
{{- end }}
{{- end }}
{{- end }}
```

### E. Structure values.yaml implémentée

```yaml
# ═══════════════════════════════════════════════════════════════
# GATEWAY API (NGINX Gateway Fabric)
# ═══════════════════════════════════════════════════════════════
gateway:
  enabled: true

  # ─────────────────────────────────────────────────────────────
  # MODE SHARED GATEWAY (recommandé)
  # Le Gateway est créé par init-stagingkub.sh dans nginx-gateway
  # Les HTTPRoutes s'y attachent via parentRefs cross-namespace
  # ─────────────────────────────────────────────────────────────
  useSharedGateway: true

  sharedGateway:
    name: shared-gateway
    namespace: nginx-gateway
    sectionName: https  # Nom du listener dans le Gateway

  # ─────────────────────────────────────────────────────────────
  # MODE DEDICATED GATEWAY (alternative)
  # Créé dans le namespace de l'application si useSharedGateway: false
  # ─────────────────────────────────────────────────────────────
  dedicatedGateway:
    name: rhdemo-gateway
    className: nginx
    listeners:
      - name: https-rhdemo
        hostname: rhdemo-stagingkub.intra.leuwen-lc.fr
        port: 443
        protocol: HTTPS
        tls:
          mode: Terminate
          secretName: intra-wildcard-tls
      - name: https-keycloak
        hostname: keycloak-stagingkub.intra.leuwen-lc.fr
        port: 443
        protocol: HTTPS
        tls:
          mode: Terminate
          secretName: intra-wildcard-tls

  # ─────────────────────────────────────────────────────────────
  # ROUTES (communes aux deux modes)
  # ─────────────────────────────────────────────────────────────
  routes:
    - name: rhdemo-route
      listenerName: https-rhdemo  # Utilisé uniquement en mode dedicated
      hostname: rhdemo-stagingkub.intra.leuwen-lc.fr
      rules:
        - path: /
          pathType: PathPrefix
          serviceName: rhdemo-app
          servicePort: 9000

    - name: keycloak-route
      listenerName: https-keycloak  # Utilisé uniquement en mode dedicated
      hostname: keycloak-stagingkub.intra.leuwen-lc.fr
      rules:
        - path: /
          pathType: PathPrefix
          serviceName: keycloak
          servicePort: 8080

  # ClientSettingsPolicy (mode dedicated uniquement)
  clientSettings:
    enabled: true
    maxBodySize: 10m

  # SnippetsFilter pour les proxy buffers Keycloak
  snippetsFilter:
    enabled: true
    proxyBufferSize: "128k"
    proxyBuffersNumber: "4"
    proxyBusyBuffersSize: "256k"
```

### F. shared-gateway.yaml (créé par init-stagingkub.sh)

Ce fichier est appliqué manuellement par le script d'initialisation, pas par Helm :

```yaml
# Fichier: infra/stagingkub/shared-gateway.yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: shared-gateway
  namespace: nginx-gateway
spec:
  gatewayClassName: nginx
  listeners:
    - name: https
      hostname: "*.intra.leuwen-lc.fr"
      port: 443
      protocol: HTTPS
      tls:
        mode: Terminate
        certificateRefs:
          # Certificat auto-signé (init-stagingkub.sh) ou Let's Encrypt (cert-manager)
          # Let's Encrypt: intra-wildcard-tls
          - name: shared-tls-cert
            kind: Secret
      allowedRoutes:
        namespaces:
          from: All  # Permet les HTTPRoutes de tous les namespaces
```

### G. Résumé des fichiers Helm créés

| Fichier                       | Mode      | Description                                    |
|-------------------------------|-----------|------------------------------------------------|
| `gateway.yaml`                | Dedicated | Gateway dédié (si useSharedGateway: false)     |
| `httproute.yaml`              | Les deux  | Routes vers rhdemo-app et keycloak             |
| `snippetsfilter.yaml`         | Les deux  | Proxy buffers pour gros cookies Keycloak       |
| `clientsettingspolicy.yaml`   | Dedicated | Limite taille body (mode dedicated uniquement) |

### H. Fichiers hors Helm (init-stagingkub.sh)

| Fichier                       | Namespace      | Description                              |
|-------------------------------|----------------|------------------------------------------|
| `shared-gateway.yaml`         | nginx-gateway  | Gateway partagé pour toutes les apps     |
| Secret `shared-tls-cert`      | nginx-gateway  | Certificat TLS wildcard auto-signé       |
| ClientSettingsPolicy          | nginx-gateway  | maxBodySize: 50m (pour shared-gateway)   |
