#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Script temporaire de test déploiement Helm (debug)
# ═══════════════════════════════════════════════════════════════

set -e

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
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Test déploiement Helm${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELM_DIR="${SCRIPT_DIR}/helm/rhdemo"
NAMESPACE="rhdemo-stagingkub"
K8S_CONTEXT="kind-rhdemo"

# Vérifier le contexte Kubernetes
CURRENT_CONTEXT=$(kubectl config current-context 2>/dev/null || echo "")
if [ "$CURRENT_CONTEXT" != "$K8S_CONTEXT" ]; then
    warn "Contexte actuel : $CURRENT_CONTEXT"
    log "Basculement vers $K8S_CONTEXT..."
    kubectl config use-context $K8S_CONTEXT
fi

# Vérifier que les secrets existent
log "Vérification des secrets..."
if ! kubectl get secret rhdemo-db-secret -n $NAMESPACE >/dev/null 2>&1; then
    error "Secret rhdemo-db-secret manquant. Exécutez init-stagingkub.sh d'abord."
fi
if ! kubectl get secret keycloak-db-secret -n $NAMESPACE >/dev/null 2>&1; then
    error "Secret keycloak-db-secret manquant. Exécutez init-stagingkub.sh d'abord."
fi
success "Secrets présents"

# Vérifier la syntaxe du chart Helm
log "Vérification syntaxe Helm (dry-run)..."
helm upgrade --install rhdemo $HELM_DIR \
  --namespace $NAMESPACE \
  --create-namespace \
  --set rhdemo.image.repository=localhost:5000/rhdemo-api \
  --set rhdemo.image.tag=latest \
  --set rhdemo.image.pullPolicy=Always \
  --dry-run \
  --debug > /tmp/helm-dry-run.yaml 2>&1 || {
    error "Erreur de syntaxe Helm. Voir /tmp/helm-dry-run.yaml"
}

success "Syntaxe Helm OK"
log "Manifests générés dans /tmp/helm-dry-run.yaml"

# Demander confirmation
echo ""
read -p "Lancer le déploiement réel ? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log "Déploiement annulé"
    exit 0
fi

# Déploiement réel
echo ""
log "Lancement du déploiement Helm..."
helm upgrade --install rhdemo $HELM_DIR \
  --namespace $NAMESPACE \
  --create-namespace \
  --set rhdemo.image.repository=localhost:5000/rhdemo-api \
  --set rhdemo.image.tag=latest \
  --set rhdemo.image.pullPolicy=Always \
  --wait \
  --timeout 15m \
  --debug

success "Déploiement Helm terminé !"

# Vérifier l'état
echo ""
log "État des pods:"
kubectl get pods -n $NAMESPACE

echo ""
log "État des StatefulSets PostgreSQL:"
kubectl get statefulset -n $NAMESPACE

echo ""
success "Script terminé avec succès !"
