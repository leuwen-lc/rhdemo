#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Script d'installation de la stack Observabilité complète
# ═══════════════════════════════════════════════════════════════
#
# Ce script installe:
#   - Prometheus (métriques) + Prometheus Operator + AlertManager
#   - Loki (logs) + Promtail + Grafana
#   - Configuration Grafana avec les deux datasources
#   - Dashboards: rhDemo Logs
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

# Vérifier le mot de passe Grafana
log "Vérification de la configuration Grafana..."
GRAFANA_PASSWORD=$(grep "^adminPassword:" $VALUES_DIR/grafana-values.yaml | awk '{print $2}' | tr -d '"')
if [ -z "$GRAFANA_PASSWORD" ] || [ "$GRAFANA_PASSWORD" = '""' ]; then
    error "Le mot de passe Grafana n'est pas configuré dans $VALUES_DIR/grafana-values.yaml"
fi
success "Configuration Grafana validée"
echo ""

# ═══════════════════════════════════════════════════════════════
# 2. Ajout des repositories Helm
# ═══════════════════════════════════════════════════════════════

log "Ajout des repositories Helm..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo add grafana https://grafana.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update >/dev/null 2>&1
success "Repositories Helm ajoutés"
echo ""

# ═══════════════════════════════════════════════════════════════
# 3. Installation de Prometheus (namespace: monitoring)
# ═══════════════════════════════════════════════════════════════

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Étape 1/2 : Installation de Prometheus + Operator${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""

MONITORING_NS="monitoring"

log "Création du namespace $MONITORING_NS..."
kubectl create namespace $MONITORING_NS 2>/dev/null || warn "Namespace existe déjà"
success "Namespace $MONITORING_NS prêt"
echo ""

log "Installation de kube-prometheus-stack..."
echo -e "${BLUE}  - Prometheus (métriques)${NC}"
echo -e "${BLUE}  - Prometheus Operator (gestion automatique)${NC}"
echo -e "${BLUE}  - AlertManager (alertes)${NC}"
echo -e "${BLUE}  - Node Exporter (métriques nodes)${NC}"
echo -e "${BLUE}  - Kube State Metrics (métriques Kubernetes)${NC}"
echo -e "${BLUE}  - Rétention: 7 jours, Storage: 10Gi${NC}"
echo ""

helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
    --namespace $MONITORING_NS \
    --values "$VALUES_DIR/prometheus-values.yaml" \
    --wait \
    --timeout 10m >/dev/null 2>&1

success "Prometheus installé"
echo ""

# Vérifier les pods Prometheus
log "Vérification des pods Prometheus..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus -n $MONITORING_NS --timeout=5m 2>/dev/null || warn "Timeout en attente des pods"
success "Pods Prometheus prêts"
echo ""

# ═══════════════════════════════════════════════════════════════
# 4. Installation de Loki + Grafana (namespace: loki-stack)
# ═══════════════════════════════════════════════════════════════

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Étape 2/2 : Installation de Loki + Grafana${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""

LOKI_NS="loki-stack"
DOMAIN="grafana.stagingkub.local"

log "Création du namespace $LOKI_NS..."
kubectl create namespace $LOKI_NS 2>/dev/null || warn "Namespace existe déjà"
success "Namespace $LOKI_NS prêt"
echo ""

# Certificat TLS pour Grafana
log "Génération du certificat TLS pour Grafana..."
if ! kubectl get secret -n $LOKI_NS grafana-tls-cert >/dev/null 2>&1; then
    TMP=$(mktemp -d)
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout $TMP/tls.key -out $TMP/tls.crt \
        -subj "/CN=$DOMAIN/O=RHDemo" 2>/dev/null
    kubectl create secret tls grafana-tls-cert \
        --cert=$TMP/tls.crt --key=$TMP/tls.key -n $LOKI_NS
    rm -rf $TMP
    success "Certificat TLS créé"
else
    warn "Certificat TLS existe déjà"
fi
echo ""

# Installation Loki
log "Installation de Loki..."
helm upgrade --install loki grafana/loki \
    -n $LOKI_NS \
    -f $VALUES_DIR/loki-modern-values.yaml \
    --wait --timeout 3m >/dev/null 2>&1
success "Loki installé"
echo ""

# Installation Promtail
log "Installation de Promtail..."
helm upgrade --install promtail grafana/promtail \
    -n $LOKI_NS \
    -f $VALUES_DIR/promtail-values.yaml \
    --wait --timeout 2m >/dev/null 2>&1
success "Promtail installé"
echo ""

# Installation Grafana
log "Installation de Grafana..."
helm upgrade --install grafana grafana/grafana \
    -n $LOKI_NS \
    -f $VALUES_DIR/grafana-values.yaml \
    --wait --timeout 3m >/dev/null 2>&1
success "Grafana installé"
echo ""

# ═══════════════════════════════════════════════════════════════
# 5. Configuration de la datasource Prometheus dans Grafana
# ═══════════════════════════════════════════════════════════════

log "Configuration de la datasource Prometheus dans Grafana..."

# Créer une ConfigMap pour la datasource Prometheus
cat <<EOF | kubectl apply -n $LOKI_NS -f - >/dev/null 2>&1
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-datasource-prometheus
  namespace: $LOKI_NS
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

success "Datasource Prometheus configurée"
echo ""

# Redémarrer Grafana pour charger la datasource
log "Redémarrage de Grafana pour charger la configuration..."
kubectl rollout restart deployment/grafana -n $LOKI_NS >/dev/null 2>&1
kubectl rollout status deployment/grafana -n $LOKI_NS --timeout=2m >/dev/null 2>&1 || warn "Timeout redémarrage Grafana"
success "Grafana redémarré"
echo ""

# ═══════════════════════════════════════════════════════════════
# 6. Déploiement des dashboards Grafana
# ═══════════════════════════════════════════════════════════════

log "Deploiement des dashboards Grafana..."

# Dashboard rhDemo Logs (Loki)
DASHBOARD_LOGS="../grafana-dashboard-rhdemo-logs.json"
if [ -f "$DASHBOARD_LOGS" ]; then
    cat "$DASHBOARD_LOGS" | jq '.dashboard' > /tmp/rhdemo-logs.json 2>/dev/null || cp "$DASHBOARD_LOGS" /tmp/rhdemo-logs.json

    kubectl create configmap grafana-dashboard-rhdemo \
        --from-file="rhdemo-logs.json=/tmp/rhdemo-logs.json" \
        --namespace="$LOKI_NS" \
        --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1

    kubectl patch configmap grafana-dashboard-rhdemo -n $LOKI_NS \
        -p '{"metadata":{"labels":{"grafana_dashboard":"1"}}}' >/dev/null 2>&1

    rm -f /tmp/rhdemo-logs.json
    success "Dashboard rhDemo Logs deploye"
else
    warn "Dashboard $DASHBOARD_LOGS introuvable"
fi

# Dashboard rhDemo Metriques (Prometheus)
DASHBOARD_METRICS="../grafana-dashboard-rhdemo-metrics.json"
if [ -f "$DASHBOARD_METRICS" ]; then
    cat "$DASHBOARD_METRICS" | jq '.dashboard' > /tmp/rhdemo-metrics.json 2>/dev/null || cp "$DASHBOARD_METRICS" /tmp/rhdemo-metrics.json

    kubectl create configmap grafana-dashboard-rhdemo-metrics \
        --from-file="rhdemo-metrics.json=/tmp/rhdemo-metrics.json" \
        --namespace="$LOKI_NS" \
        --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1

    kubectl patch configmap grafana-dashboard-rhdemo-metrics -n $LOKI_NS \
        -p '{"metadata":{"labels":{"grafana_dashboard":"1"}}}' >/dev/null 2>&1

    rm -f /tmp/rhdemo-metrics.json
    success "Dashboard rhDemo Metriques deploye"
else
    warn "Dashboard $DASHBOARD_METRICS introuvable"
fi

echo ""

# ═══════════════════════════════════════════════════════════════
# 7. Configuration DNS
# ═══════════════════════════════════════════════════════════════

log "Configuration DNS..."
if ! grep -q "$DOMAIN" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 $DOMAIN" | sudo tee -a /etc/hosts >/dev/null
    success "DNS configuré"
else
    warn "DNS déjà configuré"
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# 8. Affichage final
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
