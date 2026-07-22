#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Installation ou mise à jour en place de Promtail
# ═══════════════════════════════════════════════════════════════
# Idempotent (helm upgrade --install). Composant le plus sûr du lot :
# ClusterRole strictement en lecture (get/list/watch pods/nodes/
# namespaces pour la découverte de service), aucune CRD, aucun
# webhook d'admission. Simple `helm upgrade --atomic --wait` suffit,
# sans préflight ni contrainte de saut de version.
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_DIR="${SCRIPT_DIR}/../../helm/observability"

# renovate: datasource=helm depName=promtail registryUrl=https://grafana.github.io/helm-charts
PROMTAIL_VERSION="6.17.1"  # App: Promtail 3.5.1

LOKI_NS="loki-stack"

# Mode validation (HELM_DRY_RUN=true) : utilisé par la boucle de validation
# pré-merge de Jenkinsfile-Renovate — aucune mutation du cluster.
HELM_DRY_RUN="${HELM_DRY_RUN:-false}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}▶ Installation/mise à jour de Promtail ${PROMTAIL_VERSION}...${NC}"

[ -f "${VALUES_DIR}/promtail-values.yaml" ] || { echo -e "${RED}❌ Fichier promtail-values.yaml manquant${NC}"; exit 1; }

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

helm upgrade --install promtail grafana/promtail \
    --version "${PROMTAIL_VERSION}" \
    --namespace "${LOKI_NS}" \
    -f "${VALUES_DIR}/promtail-values.yaml" \
    ${HELM_MODE_ARGS}

if [ "$HELM_DRY_RUN" = "true" ]; then
    echo -e "${GREEN}✅ Validation dry-run Promtail ${PROMTAIL_VERSION} OK (aucune mutation du cluster)${NC}"
else
    echo -e "${GREEN}✅ Promtail ${PROMTAIL_VERSION} opérationnel${NC}"
fi
