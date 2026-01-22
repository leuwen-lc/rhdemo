#!/bin/bash

# Script pour deployer ou mettre a jour les dashboards Grafana rhDemo
# Usage: ./deploy-grafana-dashboard.sh [logs|metrics|springboot|all]
#
# Ce script peut etre execute independamment pour mettre a jour les dashboards
# sans reinstaller toute la stack Loki/Prometheus
#
# Arguments:
#   logs       - Deploie uniquement le dashboard des logs (Loki)
#   metrics    - Deploie uniquement le dashboard des metriques Kubernetes (Prometheus)
#   springboot - Deploie uniquement le dashboard Spring Boot Actuator (Prometheus)
#   all        - Deploie tous les dashboards (defaut)

set -e

NAMESPACE="loki-stack"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Fichiers des dashboards (relatifs au dossier parent du script)
DASHBOARD_LOGS="../grafana-dashboard-rhdemo-logs.json"
DASHBOARD_METRICS="../grafana-dashboard-rhdemo-metrics.json"
DASHBOARD_SPRINGBOOT="../grafana-dashboard-rhdemo-springboot.json"

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Fonction pour deployer un dashboard
deploy_dashboard() {
    local dashboard_file="$1"
    local configmap_name="$2"
    local json_filename="$3"
    local dashboard_title="$4"

    if [ ! -f "${SCRIPT_DIR}/${dashboard_file}" ]; then
        warn "Fichier dashboard non trouve: ${SCRIPT_DIR}/${dashboard_file}"
        return 1
    fi

    log "Deploiement du dashboard: ${dashboard_title}"

    # Extraire le contenu du dashboard (sans le wrapper API)
    if command -v jq >/dev/null 2>&1; then
        cat "${SCRIPT_DIR}/${dashboard_file}" | jq '.dashboard' > "/tmp/${json_filename}" 2>/dev/null
    else
        warn "jq non disponible, utilisation du fichier tel quel"
        cp "${SCRIPT_DIR}/${dashboard_file}" "/tmp/${json_filename}"
    fi

    # Creer ou mettre a jour le ConfigMap
    kubectl create configmap "${configmap_name}" \
      --from-file="${json_filename}=/tmp/${json_filename}" \
      --namespace="${NAMESPACE}" \
      --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1

    # Ajouter les labels pour que Grafana le detecte
    kubectl patch configmap "${configmap_name}" -n "${NAMESPACE}" \
      -p '{"metadata":{"labels":{"grafana_dashboard":"1"}}}' >/dev/null 2>&1

    rm -f "/tmp/${json_filename}"
    success "Dashboard deploye: ${dashboard_title}"
}

# Argument par defaut
ACTION="${1:-all}"

echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}    Deploiement Dashboards Grafana rhDemo        ${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""

# Verifier la connexion au cluster
kubectl cluster-info >/dev/null 2>&1 || error "Cluster Kubernetes inaccessible"

# Verifier que le namespace existe
if ! kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; then
    error "Namespace ${NAMESPACE} non trouve. Installer d'abord la stack observabilite."
fi

DEPLOYED_COUNT=0

case "${ACTION}" in
    logs)
        log "Mode: Deploiement du dashboard Logs uniquement"
        echo ""
        deploy_dashboard "${DASHBOARD_LOGS}" "grafana-dashboard-rhdemo" "rhdemo-logs.json" "rhDemo - Logs Application" && ((DEPLOYED_COUNT++)) || true
        ;;
    metrics)
        log "Mode: Deploiement du dashboard Metriques Kubernetes uniquement"
        echo ""
        deploy_dashboard "${DASHBOARD_METRICS}" "grafana-dashboard-rhdemo-metrics" "rhdemo-metrics.json" "rhDemo - Metriques Pods" && ((DEPLOYED_COUNT++)) || true
        ;;
    springboot)
        log "Mode: Deploiement du dashboard Spring Boot Actuator uniquement"
        echo ""
        deploy_dashboard "${DASHBOARD_SPRINGBOOT}" "grafana-dashboard-rhdemo-springboot" "rhdemo-springboot.json" "rhDemo - Metriques Spring Boot Actuator" && ((DEPLOYED_COUNT++)) || true
        ;;
    all)
        log "Mode: Deploiement de tous les dashboards"
        echo ""
        deploy_dashboard "${DASHBOARD_LOGS}" "grafana-dashboard-rhdemo" "rhdemo-logs.json" "rhDemo - Logs Application" && ((DEPLOYED_COUNT++)) || true
        deploy_dashboard "${DASHBOARD_METRICS}" "grafana-dashboard-rhdemo-metrics" "rhdemo-metrics.json" "rhDemo - Metriques Pods" && ((DEPLOYED_COUNT++)) || true
        deploy_dashboard "${DASHBOARD_SPRINGBOOT}" "grafana-dashboard-rhdemo-springboot" "rhdemo-springboot.json" "rhDemo - Metriques Spring Boot Actuator" && ((DEPLOYED_COUNT++)) || true
        ;;
    *)
        error "Action inconnue: ${ACTION}. Utiliser: logs, metrics, springboot ou all"
        ;;
esac

# Attendre que le sidecar detecte les changements
if [ ${DEPLOYED_COUNT} -gt 0 ]; then
    echo ""
    log "Attente de la detection par le sidecar Grafana..."
    sleep 3
    success "Dashboards recharges automatiquement"
fi

echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}   ${DEPLOYED_COUNT} Dashboard(s) Deploye(s) avec Succes!      ${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo -e "${BLUE}Dashboards disponibles:${NC}"
if [ "${ACTION}" = "logs" ] || [ "${ACTION}" = "all" ]; then
    echo -e "  - rhDemo - Logs Application (Loki)"
fi
if [ "${ACTION}" = "metrics" ] || [ "${ACTION}" = "all" ]; then
    echo -e "  - rhDemo - Metriques Pods (Prometheus - Kubernetes)"
fi
if [ "${ACTION}" = "springboot" ] || [ "${ACTION}" = "all" ]; then
    echo -e "  - rhDemo - Metriques Spring Boot Actuator (Prometheus - JVM/HTTP/HikariCP)"
fi
echo ""
echo -e "${BLUE}URL Grafana:${NC} https://grafana.stagingkub.local"
echo ""
echo -e "${YELLOW}Note:${NC} Les dashboards sont automatiquement charges dans Grafana"
echo -e "${YELLOW}Usage:${NC} $0 [logs|metrics|springboot|all]"
echo ""
