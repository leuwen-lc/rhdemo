#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Installation ou mise à jour en place de Grafana Alloy
# ═══════════════════════════════════════════════════════════════
# Remplace Promtail (EOL depuis le 02/03/2026, cf. docs/STAGINGKUB_REBUILD_PIPELINE.md).
# Idempotent (helm upgrade --install). Composant le plus sûr du lot :
# ClusterRole strictement en lecture (get/list/watch pods/pods-log/
# namespaces/endpoints/endpointslices/ingresses/services pour la découverte
# de service), CRD podlogs.monitoring.grafana.com désactivée (crds.create:
# false dans alloy-values.yaml, non utilisée par la config statique
# ci-dessous), aucun webhook d'admission. Simple `helm upgrade --atomic
# --wait` suffit, sans préflight ni contrainte de saut de version.
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_DIR="${SCRIPT_DIR}/../../helm/observability"

# renovate: datasource=helm depName=alloy registryUrl=https://grafana.github.io/helm-charts
ALLOY_VERSION="1.11.0"  # App: Alloy v1.18.0

LOKI_NS="loki-stack"

# Mode validation (HELM_DRY_RUN=true) : utilisé par la boucle de validation
# pré-merge de Jenkinsfile-Renovate — aucune mutation du cluster.
HELM_DRY_RUN="${HELM_DRY_RUN:-false}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}▶ Installation/mise à jour d'Alloy ${ALLOY_VERSION}...${NC}"

[ -f "${VALUES_DIR}/alloy-values.yaml" ] || { echo -e "${RED}❌ Fichier alloy-values.yaml manquant${NC}"; exit 1; }

if [ "$HELM_DRY_RUN" = "true" ]; then
    HELM_MODE_ARGS="--dry-run=server"
else
    HELM_MODE_ARGS="--atomic --wait --timeout 2m"
fi

# --force-update : l'alias "grafana" est aussi utilisé par install-or-upgrade-loki.sh
# qui pointe désormais vers un dépôt différent (fork communautaire) — sans ce
# flag, un "helm repo add" avec une URL différente de l'alias existant échoue
# silencieusement (repris par le "|| true"), laissant l'alias sur la mauvaise URL
# si les scripts s'enchaînent sur le même agent.
helm repo add grafana https://grafana.github.io/helm-charts --force-update >/dev/null 2>&1 || true
helm repo update grafana >/dev/null

kubectl create namespace "${LOKI_NS}" 2>/dev/null || true

helm upgrade --install alloy grafana/alloy \
    --version "${ALLOY_VERSION}" \
    --namespace "${LOKI_NS}" \
    -f "${VALUES_DIR}/alloy-values.yaml" \
    ${HELM_MODE_ARGS}

if [ "$HELM_DRY_RUN" = "true" ]; then
    echo -e "${GREEN}✅ Validation dry-run Alloy ${ALLOY_VERSION} OK (aucune mutation du cluster)${NC}"
else
    echo -e "${GREEN}✅ Alloy ${ALLOY_VERSION} opérationnel${NC}"
fi
