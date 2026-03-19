# NGINX Gateway Fabric — Configuration stagingkub

**Statut** : ✅ Migration implémentée
**Environnement** : stagingkub (Kubernetes/KinD)
**Version** : **2.4.2** (correctif CVE-2026-33186)
**Architecture** : **Shared Gateway** (namespace `nginx-gateway`)

---

## 1. Architecture

```text
Internet (HTTPS :443)
         │
         ▼
┌─────────────────────────┐
│   KinD Node             │
│   hostPort: 443         │
│         │               │
│         ▼               │
│   NodePort: 32616       │
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
│                    │ ProxySettingsPolicy   │                                │
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

**Avantages du Shared Gateway** :
- **Certificat unique** : Un seul Secret TLS wildcard `*.intra.leuwen-lc.fr` pour toutes les apps
- **Point d'entrée centralisé** : Gestion simplifiée du NodePort (32616)
- **Cross-namespace** : HTTPRoutes de différents namespaces sur le même Gateway
- **Headers X-Forwarded-*** : Configurés automatiquement par NGF, aucun ConfigMap manuel

---

## 2. Shared Gateway (init-stagingkub.sh)

```yaml
# infra/stagingkub/shared-gateway.yaml
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
          from: All
```

---

## 3. Configuration Helm (values.yaml)

```yaml
# ═══════════════════════════════════════════════════════════════
# GATEWAY API (NGINX Gateway Fabric 2.4.2)
# ═══════════════════════════════════════════════════════════════
gateway:
  enabled: true

  sharedGateway:
    name: shared-gateway
    namespace: nginx-gateway
    sectionName: https

  routes:
    - name: rhdemo-route
      hostname: rhdemo-stagingkub.intra.leuwen-lc.fr
      rules:
        - path: /
          pathType: PathPrefix
          serviceName: rhdemo-app
          servicePort: 9000

    - name: keycloak-route
      hostname: keycloak-stagingkub.intra.leuwen-lc.fr
      rules:
        - path: /
          pathType: PathPrefix
          serviceName: keycloak
          servicePort: 8080

  # ProxySettingsPolicy pour les proxy buffers Keycloak (NGF 2.4+)
  proxySettings:
    enabled: true
    bufferSize: "128k"
    buffersNumber: 4
    busyBuffersSize: "256k"
```

---

## 4. Templates Helm

### httproute.yaml

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
  - name: {{ $.Values.gateway.sharedGateway.name }}
    namespace: {{ $.Values.gateway.sharedGateway.namespace }}
    sectionName: {{ $.Values.gateway.sharedGateway.sectionName }}
  hostnames:
  - {{ .hostname | quote }}
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
{{- end }}
```

### proxysettingspolicy.yaml (proxy buffers Keycloak)

La **ProxySettingsPolicy** est native NGF 2.4+ et remplace SnippetsFilter.
Elle cible directement l'HTTPRoute, sans flag Helm supplémentaire.

```yaml
{{- if .Values.gateway.enabled }}
{{- if .Values.gateway.proxySettings.enabled }}
apiVersion: gateway.nginx.org/v1alpha1
kind: ProxySettingsPolicy
metadata:
  name: keycloak-proxy-buffers
  namespace: {{ .Values.global.namespace }}
  labels:
    {{- include "rhdemo.labels" . | nindent 4 }}
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: keycloak-route
  buffering:
    bufferSize: {{ .Values.gateway.proxySettings.bufferSize | quote }}
    buffers:
      number: {{ .Values.gateway.proxySettings.buffersNumber }}
      size: {{ .Values.gateway.proxySettings.bufferSize | quote }}
    busyBuffersSize: {{ .Values.gateway.proxySettings.busyBuffersSize | quote }}
{{- end }}
{{- end }}
```

---

## 5. Network Policies

Les Network Policies utilisent le namespace `nginx-gateway` (pas `ingress-nginx`) :

```yaml
# networkpolicy-rhdemo-app.yaml et networkpolicy-keycloak.yaml
- from:
  - namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: nginx-gateway
```

---

## 6. RBAC Jenkins

Le fichier `rbac/jenkins-role.yaml` inclut les permissions Gateway API et policies NGF :

```yaml
# Gateway API standard
- apiGroups: ["gateway.networking.k8s.io"]
  resources:
    - gateways
    - gateways/status
    - httproutes
    - httproutes/status
    - gatewayclasses
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Policies NGINX Gateway Fabric
- apiGroups: ["gateway.nginx.org"]
  resources:
    - clientsettingspolicies
    - clientsettingspolicies/status
    - proxysettingspolicies        # Requis pour les proxy buffers Keycloak
    - proxysettingspolicies/status
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

---

## 7. NodePort — point critique

Le Service NodePort est créé dynamiquement par NGF lors de la création du Gateway, pas lors de l'installation Helm. Le patch doit utiliser `--type='json'` :

```bash
# ✅ FONCTIONNE — json patch pour cibler un élément de liste par index
kubectl patch svc shared-gateway-nginx -n nginx-gateway --type='json' \
    -p='[{"op":"replace","path":"/spec/ports/0/nodePort","value":32616}]'

# ❌ NE FONCTIONNE PAS — merge ne peut pas modifier un élément de liste
kubectl patch svc shared-gateway-nginx -n nginx-gateway --type='merge' \
    -p '{"spec":{"ports":[{"nodePort":32616}]}}'
```

---

## 8. Matrice des risques

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Headers X-Forwarded-* mal configurés | **Faible** ✅ | OAuth2 cassé | NGF les configure automatiquement |
| Proxy buffers insuffisants pour Keycloak | **Faible** ✅ | 502 Bad Gateway | ProxySettingsPolicy (section 4) |
| Network Policies bloquant le trafic | **Moyenne** | App inaccessible | Valider namespace `nginx-gateway` |
| Jenkins sans permissions Gateway API | **Élevée** | Déploiement échoue | RBAC à jour (section 6) |
| Jenkins sans permissions ProxySettings | **Élevée** | Déploiement échoue | `proxysettingspolicies` dans RBAC |
| Rollback difficile | **Faible** | Downtime prolongé | Conserver l'ancien Ingress en parallèle |

---

## 9. Commandes utiles

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

# Logs NGF
kubectl logs -n nginx-gateway deployment/ngf-nginx-gateway-fabric

# Mise à jour de version
helm upgrade ngf oci://ghcr.io/nginx/charts/nginx-gateway-fabric \
  --version <nouvelle-version> \
  -n nginx-gateway
```

---

## 10. Fichiers de l'implémentation

| Fichier | Description |
|---------|-------------|
| `helm/rhdemo/templates/httproute.yaml` | Routes rhdemo-app et keycloak |
| `helm/rhdemo/templates/proxysettingspolicy.yaml` | Proxy buffers Keycloak |
| `helm/rhdemo/values.yaml` | Configuration gateway/routes/proxySettings |
| `scripts/init-stagingkub.sh` | Installation NGF + shared-gateway + NodePort |
| `shared-gateway.yaml` | Gateway partagé (namespace nginx-gateway) |
| `rbac/jenkins-role.yaml` | Permissions Gateway API et gateway.nginx.org |
| Network Policies | Sélecteur namespace `nginx-gateway` |
