#!/bin/bash

# Script pour déployer ou mettre à jour le dashboard Grafana rhDemo
# Usage: ./deploy-grafana-dashboard.sh
#
# Ce script peut être exécuté indépendamment pour mettre à jour le dashboard
# sans réinstaller toute la stack Loki

set -e

NAMESPACE="loki-stack"
DASHBOARD_FILE="../grafana-dashboard-rhdemo.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

echo ""
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo -e "${GREEN}  Déploiement Dashboard Grafana    ${NC}"
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo ""

# Vérifier que le fichier JSON existe
if [ ! -f "${SCRIPT_DIR}/${DASHBOARD_FILE}" ]; then
    error "Fichier dashboard non trouvé: ${SCRIPT_DIR}/${DASHBOARD_FILE}"
fi

# 1. Créer ou mettre à jour le ConfigMap avec le dashboard
log "Création du ConfigMap pour le dashboard..."

# Extraire le contenu du dashboard (sans le wrapper API)
cat "${SCRIPT_DIR}/${DASHBOARD_FILE}" | jq '.dashboard' > /tmp/rhdemo-logs.json 2>/dev/null || {
    warn "jq non disponible, utilisation du fichier tel quel"
    cp "${SCRIPT_DIR}/${DASHBOARD_FILE}" /tmp/rhdemo-logs.json
}

kubectl create configmap grafana-dashboard-rhdemo \
  --from-file="rhdemo-logs.json=/tmp/rhdemo-logs.json" \
  --namespace="${NAMESPACE}" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1
success "ConfigMap créé/mis à jour"

# 2. Ajouter les labels nécessaires pour que Grafana le détecte
log "Ajout des labels au ConfigMap..."
kubectl patch configmap grafana-dashboard-rhdemo -n ${NAMESPACE} \
  -p '{"metadata":{"labels":{"grafana_dashboard":"1"}}}' >/dev/null 2>&1

rm -f /tmp/rhdemo-logs.json
success "Labels ajoutés"

# 3. Attendre que le sidecar détecte le changement
log "Attente de la détection par le sidecar..."
sleep 3
success "Dashboard rechargé automatiquement"

echo ""
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo -e "${GREEN}   Dashboard Déployé avec Succès!  ${NC}"
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Dashboard:${NC} rhDemo - Logs Application"
echo -e "${BLUE}URL:${NC} https://grafana.stagingkub.local"
echo ""
echo -e "${YELLOW}Note:${NC} Le dashboard sera automatiquement chargé dans Grafana"
echo ""
