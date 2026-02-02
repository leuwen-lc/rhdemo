# Étude d'impact : Migration Nginx Ingress Controller → Nginx Gateway Fabric 2.3

**Date** : 2026-02-02
**Statut** : ✅ Migration implémentée
**Environnement cible** : stagingkub (Kubernetes/KinD)
**Version NGF cible** : **2.3.0** (dernière stable, décembre 2024)

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

### 4.1 Ingress actuel → Gateway + HTTPRoute

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

**Après** (Gateway API) - 3 ressources :

```yaml
# 1. GatewayClass (une seule fois dans le cluster)
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: nginx
spec:
  controllerName: gateway.nginx.org/nginx-gateway-controller
---
# 2. Gateway (remplace le Service LoadBalancer/NodePort)
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: rhdemo-gateway
  namespace: rhdemo-stagingkub
spec:
  gatewayClassName: nginx
  listeners:
  - name: https-rhdemo
    hostname: rhdemo-stagingkub.intra.leuwen-lc.fr
    port: 443
    protocol: HTTPS
    tls:
      mode: Terminate
      certificateRefs:
      - name: intra-wildcard-tls
  - name: https-keycloak
    hostname: keycloak-stagingkub.intra.leuwen-lc.fr
    port: 443
    protocol: HTTPS
    tls:
      mode: Terminate
      certificateRefs:
      - name: intra-wildcard-tls
---
# 3. HTTPRoute (remplace les rules Ingress)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: rhdemo-route
  namespace: rhdemo-stagingkub
spec:
  parentRefs:
  - name: rhdemo-gateway
    sectionName: https-rhdemo
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

### Après (simplifié grâce aux headers automatiques)

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
  --set nginxGateway.snippetsFilters.enable=true \
  --set 'nginx.service.nodePorts[0].port=31792' \
  --set 'nginx.service.nodePorts[0].listenerPort=80' \
  --set 'nginx.service.nodePorts[1].port=32616' \
  --set 'nginx.service.nodePorts[1].listenerPort=443'

# 3. Attendre le déploiement (control plane)
echo "Attente du démarrage du control plane..."
kubectl wait --namespace nginx-gateway \
  --for=condition=available deployment/ngf-nginx-gateway-fabric \
  --timeout=120s

# 4. Vérifier que le GatewayClass est créé
kubectl get gatewayclass nginx

echo "✅ NGINX Gateway Fabric 2.3.0 installé"
# Note: Les headers X-Forwarded-* sont configurés automatiquement par NGF
```

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

## 12. Conclusion et recommandation

**Faisabilité** : ✅ Migration réalisable avec les éléments techniques identifiés

### Résumé des découvertes (phase recherche)

| Question initiale | Réponse | Impact |
|-------------------|---------|--------|
| Version à cibler ? | **2.3.0** | Dernière stable, conformité Gateway API |
| Headers X-Forwarded-* ? | **Automatiques** | Simplifie le script d'install (~70 lignes en moins) |
| Proxy buffers ? | **SnippetsFilter** | ProxySettingsPolicy pas encore dispo |
| Syntaxe NodePorts ? | `nodePorts[].port` + `listenerPort` | Format différent de nginx-ingress |

### Points critiques à surveiller

1. ~~Configuration TLS/OAuth2~~ → **Résolu** : Headers X-Forwarded-* automatiques dans NGF
2. **Proxy buffers** : Utiliser SnippetsFilter (section 4.4) - activer via `snippetsFilters.enable=true`
3. **RBAC** : Ajouter permissions `gateway.networking.k8s.io` ET `gateway.nginx.org` (incluant `snippetsfilters`)
4. **Test SnippetsFilter** : Valider la syntaxe NGINX avant déploiement (risque de blocage des updates)

### Avantages de la migration

- Architecture Gateway API standardisée (portable vers d'autres implémentations)
- Séparation claire des responsabilités (GatewayClass/Gateway/Route)
- Control et data planes indépendants (meilleure scalabilité)
- Support actif à long terme par F5/NGINX
- **Headers X-Forwarded-* automatiques** (simplification majeure vs config manuelle actuelle)

### Prêt pour l'implémentation

Tous les éléments techniques sont maintenant documentés pour une migration autonome :
- ✅ Syntaxe Helm exacte pour NodePorts
- ✅ Configuration automatique des headers (plus de ConfigMaps manuels)
- ✅ Solution SnippetsFilter pour les proxy buffers Keycloak
- ✅ RBAC complet incluant les nouvelles ressources
- ✅ Templates Helm proposés dans cette documentation

---

## Annexe : Nouveaux templates Helm proposés

### A. gateway.yaml

```yaml
{{- if .Values.gateway.enabled }}
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: rhdemo-gateway
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "rhdemo.labels" . | nindent 4 }}
spec:
  gatewayClassName: {{ .Values.gateway.className }}
  listeners:
  {{- range .Values.gateway.listeners }}
  - name: {{ .name }}
    hostname: {{ .hostname }}
    port: {{ .port }}
    protocol: {{ .protocol }}
    {{- if .tls }}
    tls:
      mode: {{ .tls.mode }}
      certificateRefs:
      - name: {{ .tls.secretName }}
    {{- end }}
  {{- end }}
{{- end }}
```

### B. httproute.yaml

```yaml
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
  - name: rhdemo-gateway
    sectionName: {{ .listenerName }}
  hostnames:
  - {{ .hostname }}
  rules:
  {{- range .rules }}
  - matches:
    - path:
        type: {{ .pathType }}
        value: {{ .path }}
    backendRefs:
    - name: {{ .serviceName }}
      port: {{ .servicePort }}
  {{- end }}
{{- end }}
```

### C. snippetsfilter-keycloak.yaml (NOUVEAU - critique pour Keycloak)

```yaml
{{- if .Values.gateway.snippetsFilter.enabled }}
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
        # Buffers pour les gros headers Keycloak (cookies de session)
        proxy_buffer_size {{ .Values.gateway.snippetsFilter.proxyBufferSize }};
        proxy_buffers {{ .Values.gateway.snippetsFilter.proxyBuffersNumber }} {{ .Values.gateway.snippetsFilter.proxyBufferSize }};
        proxy_busy_buffers_size {{ .Values.gateway.snippetsFilter.proxyBusyBuffersSize }};
{{- end }}
```

### D. Structure values.yaml proposée (mise à jour)

```yaml
gateway:
  enabled: true
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

  routes:
    - name: rhdemo-route
      listenerName: https-rhdemo
      hostname: rhdemo-stagingkub.intra.leuwen-lc.fr
      snippetsFilter: null  # Pas besoin pour rhdemo-app
      rules:
        - path: /
          pathType: PathPrefix
          serviceName: rhdemo-app
          servicePort: 9000

    - name: keycloak-route
      listenerName: https-keycloak
      hostname: keycloak-stagingkub.intra.leuwen-lc.fr
      snippetsFilter: keycloak-proxy-buffers  # Référence au SnippetsFilter
      rules:
        - path: /
          pathType: PathPrefix
          serviceName: keycloak
          servicePort: 8080

  # ClientSettingsPolicy pour la taille max du body
  clientSettings:
    enabled: true
    maxBodySize: 10m

  # SnippetsFilter pour les proxy buffers (Keycloak)
  # ATTENTION: Nécessite nginxGateway.snippetsFilters.enable=true lors de l'install Helm
  snippetsFilter:
    enabled: true
    proxyBufferSize: "128k"
    proxyBuffersNumber: "4"
    proxyBusyBuffersSize: "256k"

# ═══════════════════════════════════════════════════════════════
# NGINX Gateway Fabric (remplace nginx-ingress)
# ═══════════════════════════════════════════════════════════════
nginx-gateway-fabric:
  enabled: true

  # CRITIQUE: Activer SnippetsFilter pour les proxy buffers
  nginxGateway:
    snippetsFilters:
      enable: true

  nginx:
    service:
      type: NodePort
      externalTrafficPolicy: Local  # Préserve l'IP client source

      # Format NodePorts pour NGF (différent de nginx-ingress!)
      nodePorts:
        - port: 31792        # NodePort exposé sur le cluster
          listenerPort: 80   # Correspond au listener HTTP de la Gateway
        - port: 32616        # NodePort exposé sur le cluster
          listenerPort: 443  # Correspond au listener HTTPS de la Gateway

    container:
      resources:
        requests:
          memory: "128Mi"
          cpu: "100m"
        limits:
          memory: "256Mi"
          cpu: "200m"

  # Control plane resources
  nginxGateway:
    resources:
      requests:
        memory: "64Mi"
        cpu: "50m"
      limits:
        memory: "128Mi"
        cpu: "100m"
```

### E. Résumé des nouveaux fichiers Helm à créer

| Fichier | Remplace | Description |
|---------|----------|-------------|
| `gateway.yaml` | `ingress.yaml` | Définit le Gateway avec listeners TLS |
| `httproute-rhdemo.yaml` | (partie de ingress.yaml) | Route vers rhdemo-app |
| `httproute-keycloak.yaml` | (partie de ingress.yaml) | Route vers Keycloak avec SnippetsFilter |
| `clientsettingspolicy.yaml` | annotation proxy-body-size | Limite taille body 10m |
| `snippetsfilter-keycloak.yaml` | **NOUVEAU** | Proxy buffers pour Keycloak |
