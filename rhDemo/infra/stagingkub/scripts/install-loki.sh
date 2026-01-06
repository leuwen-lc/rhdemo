#!/bin/bash

###########################################
# Script d'installation Loki Stack
# Charts: grafana/loki, grafana/promtail, grafana/grafana
# Date: 2026-01-05
###########################################

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

NAMESPACE="loki-stack"
DOMAIN="grafana.stagingkub.local"
VALUES_DIR="../helm/observability"

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo -e "${GREEN}═══════════════════════════════════${NC}"
echo -e "${GREEN}  Installation Loki Stack  ${NC}"
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo ""

# 1. Vérifications
log "Vérification des prérequis..."
command -v kubectl >/dev/null 2>&1 || error "kubectl non installé"
command -v helm >/dev/null 2>&1 || error "helm non installé"
kubectl cluster-info >/dev/null 2>&1 || error "Cluster Kubernetes inaccessible"
success "Prérequis OK"

# 2. Vérification mot de passe Grafana
log "Vérification de la configuration Grafana..."
GRAFANA_PASSWORD=$(grep "^adminPassword:" $VALUES_DIR/grafana-values.yaml | awk '{print $2}' | tr -d '"')
if [ -z "$GRAFANA_PASSWORD" ] || [ "$GRAFANA_PASSWORD" = '""' ]; then
    error "Le mot de passe Grafana n'est pas configuré dans $VALUES_DIR/grafana-values.yaml. Veuillez définir adminPassword avec un mot de passe fort."
fi
success "Configuration Grafana validée"

# 3. Repository Helm
log "Ajout du repository Grafana..."
helm repo add grafana https://grafana.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update >/dev/null 2>&1
success "Repository ajouté"

# 4. Namespace
log "Création du namespace $NAMESPACE..."
kubectl create namespace $NAMESPACE 2>/dev/null || warn "Namespace existe déjà"
success "Namespace prêt"

# 5. Certificat TLS
log "Génération du certificat TLS..."
if ! kubectl get secret -n $NAMESPACE grafana-tls-cert >/dev/null 2>&1; then
    TMP=$(mktemp -d)
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout $TMP/tls.key -out $TMP/tls.crt \
        -subj "/CN=$DOMAIN/O=RHDemo" 2>/dev/null
    kubectl create secret tls grafana-tls-cert \
        --cert=$TMP/tls.crt --key=$TMP/tls.key -n $NAMESPACE
    rm -rf $TMP
    success "Certificat créé"
else
    warn "Certificat existe déjà"
fi

# 6. Installation Loki
log "Installation de Loki..."
helm upgrade --install loki grafana/loki \
    -n $NAMESPACE \
    -f $VALUES_DIR/loki-modern-values.yaml \
    --wait --timeout 3m >/dev/null 2>&1
success "Loki installé"

# 7. Installation Promtail
log "Installation de Promtail..."
helm upgrade --install promtail grafana/promtail \
    -n $NAMESPACE \
    -f $VALUES_DIR/promtail-values.yaml \
    --wait --timeout 2m >/dev/null 2>&1
success "Promtail installé"

# 8. Installation Grafana
log "Installation de Grafana..."
helm upgrade --install grafana grafana/grafana \
    -n $NAMESPACE \
    -f $VALUES_DIR/grafana-values.yaml \
    --wait --timeout 3m >/dev/null 2>&1
success "Grafana installé"

# 9. Déploiement du dashboard rhDemo
log "Déploiement du dashboard rhDemo..."
DASHBOARD_FILE="../grafana-dashboard-rhdemo.json"
if [ -f "$DASHBOARD_FILE" ]; then
    # Extraire le contenu du dashboard (sans le wrapper API)
    cat "$DASHBOARD_FILE" | jq '.dashboard' > /tmp/rhdemo-logs.json 2>/dev/null || {
        warn "jq non disponible, utilisation du fichier tel quel"
        cp "$DASHBOARD_FILE" /tmp/rhdemo-logs.json
    }

    kubectl create configmap grafana-dashboard-rhdemo \
        --from-file="rhdemo-logs.json=/tmp/rhdemo-logs.json" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1

    kubectl patch configmap grafana-dashboard-rhdemo -n $NAMESPACE \
        -p '{"metadata":{"labels":{"grafana_dashboard":"1"}}}' >/dev/null 2>&1

    rm -f /tmp/rhdemo-logs.json

    success "Dashboard rhDemo déployé"
else
    warn "Dashboard $DASHBOARD_FILE introuvable, ignoré"
fi

# 10. DNS
log "Configuration DNS..."
if ! grep -q "$DOMAIN" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 $DOMAIN" | sudo tee -a /etc/hosts >/dev/null
    success "DNS configuré"
else
    warn "DNS déjà configuré"
fi

# 11. Affichage final
echo ""
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo -e "${GREEN}    Installation Terminée ! ✓      ${NC}"
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Grafana:${NC} https://$DOMAIN"
echo -e "${BLUE}Login:${NC} admin / (mot de passe configuré dans helm/observability/grafana-values.yaml)"
echo -e "${BLUE}Dashboard:${NC} rhDemo - Logs Application (automatiquement disponible)"
echo ""
echo -e "${BLUE}Pods:${NC}"
kubectl get pods -n $NAMESPACE
echo ""
echo -e "${BLUE}Première requête LogQL:${NC}"
echo -e "  {namespace=\"rhdemo-stagingkub\", app=\"rhdemo-app\"}"
echo ""
echo -e "${YELLOW}Si Grafana n'est pas accessible via Ingress:${NC}"
echo -e "  kubectl port-forward -n $NAMESPACE svc/grafana 3000:80"
echo -e "  Puis: http://localhost:3000"
echo ""
