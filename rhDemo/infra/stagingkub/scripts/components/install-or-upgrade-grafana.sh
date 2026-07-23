#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Installation ou mise à jour en place de Grafana
# ═══════════════════════════════════════════════════════════════
# Idempotent (helm upgrade --install) : release Helm + HTTPRoute +
# datasource Prometheus + redémarrage + dashboards.
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_DIR="${SCRIPT_DIR}/../../helm/observability"

# renovate: datasource=helm depName=grafana registryUrl=https://grafana.github.io/helm-charts
GRAFANA_VERSION="10.5.15"  # App: Grafana 12.3.1

LOKI_NS="loki-stack"
DOMAIN="grafana-stagingkub.intra.leuwen-lc.fr"

# Mode validation (HELM_DRY_RUN=true) : utilisé par la boucle de validation
# pré-merge de Jenkinsfile-Renovate — seule la release Helm est validée
# (--dry-run=server) ; HTTPRoute/datasource/restart/dashboards ne sont pas
# des mutations liées à la version du chart et sont sautées entièrement.
HELM_DRY_RUN="${HELM_DRY_RUN:-false}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}▶ Installation/mise à jour de Grafana ${GRAFANA_VERSION}...${NC}"

[ -f "${VALUES_DIR}/grafana-values.yaml" ] || { echo -e "${RED}❌ Fichier grafana-values.yaml manquant${NC}"; exit 1; }

GRAFANA_PASSWORD=$(grep "^adminPassword:" "${VALUES_DIR}/grafana-values.yaml" | awk '{print $2}' | tr -d '"')
if [ -z "$GRAFANA_PASSWORD" ] || [ "$GRAFANA_PASSWORD" = '""' ]; then
    echo -e "${RED}❌ Le mot de passe Grafana n'est pas configuré dans ${VALUES_DIR}/grafana-values.yaml${NC}"
    exit 1
fi

if [ "$HELM_DRY_RUN" = "true" ]; then
    HELM_MODE_ARGS="--dry-run=server"
else
    HELM_MODE_ARGS="--atomic --wait --timeout 3m"
fi

# --force-update : voir install-or-upgrade-alloy.sh (alias "grafana" partagé
# avec install-or-upgrade-loki.sh, qui pointe désormais vers un dépôt différent).
helm repo add grafana https://grafana.github.io/helm-charts --force-update >/dev/null 2>&1 || true
helm repo update grafana >/dev/null

kubectl create namespace "${LOKI_NS}" 2>/dev/null || true

helm upgrade --install grafana grafana/grafana \
    --version "${GRAFANA_VERSION}" \
    --namespace "${LOKI_NS}" \
    -f "${VALUES_DIR}/grafana-values.yaml" \
    ${HELM_MODE_ARGS}

if [ "$HELM_DRY_RUN" = "true" ]; then
    echo -e "${GREEN}✅ Validation dry-run Grafana ${GRAFANA_VERSION} OK (aucune mutation du cluster)${NC}"
    exit 0
fi

# HTTPRoute (attachée au Gateway partagé) — idempotente
cat <<EOF | kubectl apply -f -
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: grafana-route
  namespace: ${LOKI_NS}
spec:
  parentRefs:
  - name: shared-gateway
    namespace: nginx-gateway
    sectionName: https
  hostnames:
  - "${DOMAIN}"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: grafana
      port: 80
EOF

# Datasource Prometheus — idempotente
cat <<EOF | kubectl apply -n "${LOKI_NS}" -f - >/dev/null 2>&1
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-datasource-prometheus
  namespace: ${LOKI_NS}
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
        jsonData:
          timeInterval: 30s
EOF

kubectl rollout restart deployment/grafana -n "${LOKI_NS}" >/dev/null 2>&1
kubectl rollout status deployment/grafana -n "${LOKI_NS}" --timeout=2m

"${SCRIPT_DIR}/../deploy-grafana-dashboard.sh" all

echo -e "${GREEN}✅ Grafana ${GRAFANA_VERSION} opérationnel${NC}"
