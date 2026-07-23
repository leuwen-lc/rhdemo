#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Installation ou mise à jour en place de Loki
# ═══════════════════════════════════════════════════════════════
# Idempotent (helm upgrade --install). Aucune CRD, mais un ClusterRole
# en LECTURE SEULE propre (loki-clusterrole : get/watch/list sur
# configmaps/secrets, vérifié via `helm template` sur le chart réel).
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_DIR="${SCRIPT_DIR}/../../helm/observability"

# Depuis la chart 7.0.0, le dépôt https://grafana.github.io/helm-charts ne
# publie plus que la variante Grafana Enterprise Logs (GEL) — le chart OSS a
# été forké vers grafana-community/helm-charts (annoncé dans le CHANGELOG.md
# amont, effectif au 16/03/2026). enterprise.enabled est à false par défaut
# dans le chart GEL, donc rester sur l'ancien dépôt ne casserait pas le
# déploiement actuel, mais figerait les correctifs/évolutions OSS futurs sur
# une branche de maintenance dédiée à GEL. Bascule vers le fork communautaire,
# seule continuation réelle du chart OSS.
# renovate: datasource=helm depName=loki registryUrl=https://grafana-community.github.io/helm-charts
LOKI_VERSION="18.5.0"  # App: Loki 3.6.7

LOKI_NS="loki-stack"

# Mode validation (HELM_DRY_RUN=true) : utilisé par la boucle de validation
# pré-merge de Jenkinsfile-Renovate — aucune mutation du cluster.
HELM_DRY_RUN="${HELM_DRY_RUN:-false}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}▶ Installation/mise à jour de Loki ${LOKI_VERSION}...${NC}"

[ -f "${VALUES_DIR}/loki-modern-values.yaml" ] || { echo -e "${RED}❌ Fichier loki-modern-values.yaml manquant${NC}"; exit 1; }

if [ "$HELM_DRY_RUN" = "true" ]; then
    HELM_MODE_ARGS="--dry-run=server"
else
    HELM_MODE_ARGS="--atomic --wait --timeout 5m"
fi

helm repo add grafana https://grafana-community.github.io/helm-charts --force-update >/dev/null 2>&1 || true
helm repo update grafana >/dev/null

kubectl create namespace "${LOKI_NS}" 2>/dev/null || true

helm upgrade --install loki grafana/loki \
    --version "${LOKI_VERSION}" \
    --namespace "${LOKI_NS}" \
    -f "${VALUES_DIR}/loki-modern-values.yaml" \
    ${HELM_MODE_ARGS}

if [ "$HELM_DRY_RUN" = "true" ]; then
    echo -e "${GREEN}✅ Validation dry-run Loki ${LOKI_VERSION} OK (aucune mutation du cluster)${NC}"
else
    echo -e "${GREEN}✅ Loki ${LOKI_VERSION} opérationnel${NC}"
fi
