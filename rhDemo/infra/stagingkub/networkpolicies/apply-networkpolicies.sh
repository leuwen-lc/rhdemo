#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Script d'application des Network Policies externes
# ═══════════════════════════════════════════════════════════════════════════════
# Ce script applique les Network Policies pour les namespaces qui ne sont pas
# gérés par le chart Helm rhdemo:
#   - monitoring (Prometheus, AlertManager, etc.)
#   - loki-stack (Loki, Promtail, Grafana)
#   - nginx-gateway (NGINX Gateway Fabric)
#
# Usage:
#   ./apply-networkpolicies.sh [--dry-run] [--delete]
#
# Options:
#   --dry-run   Affiche les modifications sans les appliquer
#   --delete    Supprime les Network Policies au lieu de les appliquer
#
# Prérequis:
#   - Cluster KinD rhdemo démarré
#   - kubectl configuré (context: kind-rhdemo)
#   - Namespaces monitoring, loki-stack et nginx-gateway créés
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT="kind-rhdemo"

# Options
DRY_RUN=""
DELETE=false

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run=client"
            shift
            ;;
        --delete)
            DELETE=true
            shift
            ;;
        *)
            error "Option inconnue: $1"
            ;;
    esac
done

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Application des Network Policies (namespaces externes)${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Vérifications préliminaires
log "Vérification du contexte Kubernetes..."
if ! kubectl cluster-info --context "$CONTEXT" &>/dev/null; then
    error "Impossible de se connecter au cluster $CONTEXT"
fi
success "Cluster accessible"

# Vérifier que les namespaces existent
log "Vérification des namespaces..."
for ns in monitoring loki-stack nginx-gateway; do
    if kubectl get namespace "$ns" --context "$CONTEXT" &>/dev/null; then
        success "  Namespace $ns existe"
    else
        warn "  Namespace $ns n'existe pas (sera ignoré)"
    fi
done
echo ""

# Appliquer ou supprimer les Network Policies
if [ "$DELETE" = true ]; then
    log "Suppression des Network Policies..."
    ACTION="delete"
else
    if [ -n "$DRY_RUN" ]; then
        log "Mode dry-run: les modifications ne seront pas appliquées"
    fi
    log "Application des Network Policies..."
    ACTION="apply"
fi

# Fonction pour appliquer/supprimer les policies d'un fichier
apply_policies() {
    local file="$1"
    local ns="$2"

    if ! kubectl get namespace "$ns" --context "$CONTEXT" &>/dev/null; then
        warn "Namespace $ns n'existe pas, ignoré"
        return
    fi

    if [ -f "$file" ]; then
        echo -e "${BLUE}▶ Namespace: $ns${NC}"
        if [ "$DELETE" = true ]; then
            kubectl delete -f "$file" --context "$CONTEXT" --ignore-not-found || true
        else
            kubectl apply -f "$file" --context "$CONTEXT" $DRY_RUN
        fi
        success "  $file traité"
        echo ""
    else
        warn "Fichier $file non trouvé"
    fi
}

# Appliquer les policies pour chaque namespace
apply_policies "$SCRIPT_DIR/monitoring-networkpolicies.yaml" "monitoring"
apply_policies "$SCRIPT_DIR/loki-stack-networkpolicies.yaml" "loki-stack"
apply_policies "$SCRIPT_DIR/nginx-gateway-networkpolicies.yaml" "nginx-gateway"

# Résumé
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Résumé${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

if [ -n "$DRY_RUN" ]; then
    warn "Mode dry-run: aucune modification appliquée"
elif [ "$DELETE" = true ]; then
    success "Network Policies supprimées"
else
    success "Network Policies appliquées"
fi

echo ""
log "Pour vérifier les Network Policies:"
echo "  kubectl get networkpolicies -A | grep -E '(monitoring|loki-stack|nginx-gateway)'"
echo ""
log "Pour tester la connectivité:"
echo "  $SCRIPT_DIR/../scripts/test-network-policies.sh"
echo ""
