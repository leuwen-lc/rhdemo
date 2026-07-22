#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Script d'installation de la stack Observabilité complète
# ═══════════════════════════════════════════════════════════════
#
# Ce script installe:
#   - Prometheus (métriques) + Prometheus Operator + AlertManager
#   - Loki (logs) + Promtail + Grafana
#   - Configuration Grafana avec les deux datasources
#   - Dashboards: Logs, Métriques Pods, Spring Boot Actuator, PostgreSQL
#
# Les commandes Helm par composant sont factorisées dans
# scripts/components/install-or-upgrade-*.sh — ce script (chemin
# "reconstruction complète") et le pipeline Jenkins de mise à jour en
# place (RHDemo-Stagingkub-Upgrade-Deploy) appellent les mêmes scripts,
# pour ne jamais diverger.
#
# Utilisation:
#   ./install-observability.sh
#
# Prérequis:
#   - Cluster KinD stagingkub démarré
#   - kubectl configuré (context: kind-rhdemo)
#   - Helm 3 installé
# ═══════════════════════════════════════════════════════════════

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_DIR="${SCRIPT_DIR}/../helm/observability"
COMPONENTS_DIR="${SCRIPT_DIR}/components"

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation de la Stack Observabilité Complète${NC}"
echo -e "${GREEN}  Prometheus (métriques) + Loki (logs) + Grafana${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════
# 1. Vérifications préalables
# ═══════════════════════════════════════════════════════════════

log "Vérification des prérequis..."
command -v kubectl >/dev/null 2>&1 || error "kubectl non installé"
command -v helm >/dev/null 2>&1 || error "helm non installé"
kubectl cluster-info >/dev/null 2>&1 || error "Cluster Kubernetes inaccessible"

# Vérifier le contexte
CURRENT_CONTEXT=$(kubectl config current-context 2>/dev/null || echo "")
if [ "$CURRENT_CONTEXT" != "kind-rhdemo" ]; then
    warn "Contexte actuel : $CURRENT_CONTEXT"
    log "Basculement vers kind-rhdemo..."
    kubectl config use-context kind-rhdemo
fi

success "Prérequis OK"
echo ""

# Vérifier les fichiers de configuration
log "Vérification des fichiers de configuration..."
[ -f "$VALUES_DIR/prometheus-values.yaml" ] || error "Fichier prometheus-values.yaml manquant"
[ -f "$VALUES_DIR/loki-modern-values.yaml" ] || error "Fichier loki-modern-values.yaml manquant"
[ -f "$VALUES_DIR/promtail-values.yaml" ] || error "Fichier promtail-values.yaml manquant"
[ -f "$VALUES_DIR/grafana-values.yaml" ] || error "Fichier grafana-values.yaml manquant"
success "Fichiers de configuration OK"
echo ""

# ═══════════════════════════════════════════════════════════════
# 2. Installation/mise à jour des composants (scripts factorisés)
# ═══════════════════════════════════════════════════════════════

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Étape 1/4 : Prometheus + Operator${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""
"${COMPONENTS_DIR}/install-or-upgrade-kube-prometheus-stack.sh"
echo ""

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Étape 2/4 : Loki${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""
"${COMPONENTS_DIR}/install-or-upgrade-loki.sh"
echo ""

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Étape 3/4 : Promtail${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""
"${COMPONENTS_DIR}/install-or-upgrade-promtail.sh"
echo ""

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Étape 4/4 : Grafana (release + HTTPRoute + datasource + dashboards)${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""
"${COMPONENTS_DIR}/install-or-upgrade-grafana.sh"
echo ""

# ═══════════════════════════════════════════════════════════════
# 3. Configuration DNS
# ═══════════════════════════════════════════════════════════════

DOMAIN="grafana-stagingkub.intra.leuwen-lc.fr"
MONITORING_NS="monitoring"
LOKI_NS="loki-stack"

log "Configuration DNS..."
if ! grep -q "$DOMAIN" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 $DOMAIN" | sudo tee -a /etc/hosts >/dev/null
    success "DNS configuré"
else
    warn "DNS déjà configuré"
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# 4. Affichage final
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ Installation de la Stack Observabilité Terminée !${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  INTERFACES DISPONIBLES                                  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}📊 Grafana (Logs + Métriques):${NC}"
echo -e "  URL: ${GREEN}https://$DOMAIN${NC}"
echo -e "  Login: ${GREEN}admin${NC}"
echo -e "  Password: ${GREEN}(voir $VALUES_DIR/grafana-values.yaml)${NC}"
echo ""
echo -e "  Datasources:"
echo -e "    - ${GREEN}✓${NC} Loki (logs)"
echo -e "    - ${GREEN}✓${NC} Prometheus (métriques)"
echo ""
echo -e "  Dashboards:"
echo -e "    - ${GREEN}✓${NC} rhDemo - Logs Application (Loki)"
echo -e "    - ${GREEN}✓${NC} rhDemo - Metriques Pods (Prometheus)"
echo -e "    - ${GREEN}✓${NC} rhDemo - Metriques Spring Boot Actuator (Prometheus)"
echo -e "    - ${GREEN}✓${NC} rhDemo - Metriques PostgreSQL (Prometheus)"
echo ""

echo -e "${YELLOW}📈 Prometheus (Métriques):${NC}"
echo -e "  kubectl port-forward -n $MONITORING_NS svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo -e "  URL: ${GREEN}http://localhost:9090${NC}"
echo ""

echo -e "${YELLOW}🔔 AlertManager (Alertes):${NC}"
echo -e "  kubectl port-forward -n $MONITORING_NS svc/prometheus-kube-prometheus-alertmanager 9093:9093"
echo -e "  URL: ${GREEN}http://localhost:9093${NC}"
echo ""

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  STATUS DES PODS                                         ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}Namespace monitoring (Prometheus):${NC}"
kubectl get pods -n $MONITORING_NS | head -10
echo ""

echo -e "${YELLOW}Namespace loki-stack (Loki + Grafana):${NC}"
kubectl get pods -n $LOKI_NS
echo ""

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  COMMANDES UTILES                                        ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "  ${YELLOW}# Voir les ServiceMonitors (métriques scrappées)${NC}"
echo -e "  kubectl get servicemonitor -A"
echo ""

echo -e "  ${YELLOW}# Voir les PodMonitors${NC}"
echo -e "  kubectl get podmonitor -A"
echo ""

echo -e "  ${YELLOW}# Voir les targets Prometheus${NC}"
echo -e "  # → Ouvrir http://localhost:9090/targets après port-forward"
echo ""

echo -e "  ${YELLOW}# Port-forward Grafana (si Ingress ne fonctionne pas)${NC}"
echo -e "  kubectl port-forward -n $LOKI_NS svc/grafana 3000:80"
echo -e "  # → http://localhost:3000"
echo ""

echo -e "  ${YELLOW}# Logs Prometheus Operator${NC}"
echo -e "  kubectl logs -n $MONITORING_NS -l app.kubernetes.io/name=prometheus-operator -f"
echo ""

echo -e "${GREEN}✅ La stack Observabilité est maintenant prête !${NC}"
echo -e "${GREEN}✅ Prometheus collecte automatiquement les métriques des composants${NC}"
echo -e "${GREEN}✅ Loki collecte déjà les logs de tous les pods${NC}"
echo ""
