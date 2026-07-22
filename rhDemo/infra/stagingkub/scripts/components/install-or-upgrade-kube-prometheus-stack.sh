#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Installation ou mise à jour en place de kube-prometheus-stack
# (Prometheus + Prometheus Operator + AlertManager + Node Exporter +
# Kube State Metrics)
# ═══════════════════════════════════════════════════════════════
# Idempotent (helm upgrade --install).
#
# Piège Helm spécifique à ce chart : les CRDs (monitoring.coreos.com)
# sont trop volumineuses pour un `kubectl apply` client-side (elles
# dépassent la limite de taille de l'annotation
# kubectl.kubernetes.io/last-applied-configuration) — application
# systématique en --server-side, avant l'upgrade de la release.
#
# Les admission webhooks du Prometheus Operator sont désactivés
# explicitement dans prometheus-values.yaml (prometheusOperator.
# admissionWebhooks.enabled: false) : aucun droit RBAC sur
# admissionregistration.k8s.io n'est donc nécessaire ici.
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_DIR="${SCRIPT_DIR}/../../helm/observability"

# renovate: datasource=helm depName=kube-prometheus-stack registryUrl=https://prometheus-community.github.io/helm-charts
KUBE_PROMETHEUS_STACK_VERSION="81.6.9"  # App: Prometheus Operator v0.88.1

MONITORING_NS="monitoring"

# Mode validation (HELM_DRY_RUN=true) : utilisé par la boucle de validation
# pré-merge de Jenkinsfile-Renovate — aucune mutation du cluster.
HELM_DRY_RUN="${HELM_DRY_RUN:-false}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}▶ Installation/mise à jour de kube-prometheus-stack ${KUBE_PROMETHEUS_STACK_VERSION}...${NC}"

[ -f "${VALUES_DIR}/prometheus-values.yaml" ] || { echo -e "${RED}❌ Fichier prometheus-values.yaml manquant${NC}"; exit 1; }

if [ "$HELM_DRY_RUN" = "true" ]; then
    KUBECTL_APPLY_ARGS="--server-side --dry-run=server --force-conflicts"
    HELM_MODE_ARGS="--dry-run=server"
else
    KUBECTL_APPLY_ARGS="--server-side --force-conflicts"
    HELM_MODE_ARGS="--atomic --wait --timeout 10m"
fi

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update prometheus-community >/dev/null

kubectl create namespace "${MONITORING_NS}" 2>/dev/null || true

echo -e "${YELLOW}  - Application des CRDs (server-side, obligatoire pour ce chart)...${NC}"
helm show crds prometheus-community/kube-prometheus-stack --version "${KUBE_PROMETHEUS_STACK_VERSION}" \
    | kubectl apply ${KUBECTL_APPLY_ARGS} -f -
echo -e "${GREEN}  ✓ CRDs monitoring.coreos.com à jour${NC}"

helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
    --version "${KUBE_PROMETHEUS_STACK_VERSION}" \
    --namespace "${MONITORING_NS}" \
    --values "${VALUES_DIR}/prometheus-values.yaml" \
    ${HELM_MODE_ARGS}

if [ "$HELM_DRY_RUN" = "true" ]; then
    echo -e "${GREEN}✅ Validation dry-run kube-prometheus-stack ${KUBE_PROMETHEUS_STACK_VERSION} OK (aucune mutation du cluster)${NC}"
else
    kubectl rollout status deployment/prometheus-kube-prometheus-operator -n "${MONITORING_NS}" --timeout=300s 2>/dev/null || true
    echo -e "${GREEN}✅ kube-prometheus-stack ${KUBE_PROMETHEUS_STACK_VERSION} opérationnel${NC}"
fi
