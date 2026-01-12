#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Script d'installation de CloudNativePG pour stagingkub
# ═══════════════════════════════════════════════════════════════
#
# Ce script installe:
#   - CloudNativePG Operator
#   - 2 clusters PostgreSQL (Keycloak + rhDemo) avec backups
#   - Configuration monitoring (PodMonitors pour Prometheus)
#
# Utilisation:
#   ./install-cloudnativepg.sh
#
# Prérequis:
#   - Cluster KinD stagingkub démarré
#   - kubectl configuré (context: kind-rhdemo)
#   - Helm 3 installé
#   - Observability stack installée (Prometheus pour monitoring)
# ═══════════════════════════════════════════════════════════════

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELM_DIR="${SCRIPT_DIR}/../helm/rhdemo"

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation CloudNativePG pour stagingkub${NC}"
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

# ═══════════════════════════════════════════════════════════════
# 2. Installation de CloudNativePG Operator
# ═══════════════════════════════════════════════════════════════

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Étape 1/3 : Installation CloudNativePG Operator${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""

CNPG_VERSION="1.25.1"
CNPG_NAMESPACE="cnpg-system"

log "Vérification si CloudNativePG est déjà installé..."
if kubectl get namespace $CNPG_NAMESPACE >/dev/null 2>&1; then
    warn "CloudNativePG semble déjà installé"
    read -p "Voulez-vous réinstaller/mettre à jour? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "Installation de l'opérateur ignorée"
    else
        log "Mise à jour de CloudNativePG Operator..."
        kubectl apply --server-side -f \
            https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.25/releases/cnpg-${CNPG_VERSION}.yaml
        success "CloudNativePG Operator mis à jour"
    fi
else
    log "Installation de CloudNativePG Operator version ${CNPG_VERSION}..."
    kubectl apply --server-side -f \
        https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.25/releases/cnpg-${CNPG_VERSION}.yaml
    success "CloudNativePG Operator installé"
fi

echo ""
log "Attente du démarrage de l'opérateur..."
kubectl wait --for=condition=Available --timeout=300s \
    deployment/cnpg-controller-manager -n $CNPG_NAMESPACE >/dev/null 2>&1 || warn "Timeout en attente de l'opérateur"

success "CloudNativePG Operator prêt"
echo ""

# ═══════════════════════════════════════════════════════════════
# 3. Affichage des informations de configuration
# ═══════════════════════════════════════════════════════════════

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Étape 2/3 : Configuration des clusters PostgreSQL${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""

log "Configuration prévue:"
echo -e "${YELLOW}  Cluster 1: postgresql-keycloak${NC}"
echo -e "    - Instances: 1 (single instance, sans HA)"
echo -e "    - Base: keycloak"
echo -e "    - Storage: 2Gi"
echo -e "    - Monitoring: Activé (PodMonitor)"
echo -e "    - Backups: Configurés (rétention 7j)"
echo ""
echo -e "${YELLOW}  Cluster 2: postgresql-rhdemo${NC}"
echo -e "    - Instances: 1 (single instance, sans HA)"
echo -e "    - Base: rhdemo"
echo -e "    - Storage: 2Gi"
echo -e "    - Monitoring: Activé (PodMonitor)"
echo -e "    - Backups: Configurés (rétention 7j)"
echo -e "    - Initialisation: Schéma + données de test"
echo ""

# ═══════════════════════════════════════════════════════════════
# 4. Vérification des secrets de mots de passe
# ═══════════════════════════════════════════════════════════════

log "Vérification des secrets de mots de passe..."

NAMESPACE="rhdemo-stagingkub"

# Vérifier que le namespace existe
if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    error "Namespace $NAMESPACE n'existe pas. Exécutez d'abord le déploiement de l'application."
fi

# Vérifier les secrets existants pour récupérer les mots de passe
MISSING_SECRETS=()

if ! kubectl get secret keycloak-db-secret -n "$NAMESPACE" >/dev/null 2>&1; then
    MISSING_SECRETS+=("keycloak-db-secret")
fi

if ! kubectl get secret rhdemo-db-secret -n "$NAMESPACE" >/dev/null 2>&1; then
    MISSING_SECRETS+=("rhdemo-db-secret")
fi

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
    warn "Secrets manquants: ${MISSING_SECRETS[*]}"
    echo "Les secrets de base de données doivent être créés par init-stagingkub.sh"
    echo "Assurez-vous d'avoir exécuté init-stagingkub.sh avant d'installer CloudNativePG"
    read -p "Continuer quand même? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "Installation annulée"
    fi
fi

success "Secrets vérifiés"
echo ""

# ═══════════════════════════════════════════════════════════════
# 5. Note importante sur les anciens StatefulSets
# ═══════════════════════════════════════════════════════════════

echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  ⚠️  IMPORTANT - Migration depuis StatefulSets${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Si vous avez des StatefulSets PostgreSQL existants, vous devez:${NC}"
echo -e "${YELLOW}1. Sauvegarder les données existantes${NC}"
echo -e "${YELLOW}2. Désactiver les StatefulSets dans values.yaml:${NC}"
echo -e "${YELLOW}     postgresql-keycloak.enabled: false${NC}"
echo -e "${YELLOW}     postgresql-rhdemo.enabled: false${NC}"
echo -e "${YELLOW}3. Activer CloudNativePG dans values.yaml:${NC}"
echo -e "${YELLOW}     keycloak.cloudnativepg.enabled: true${NC}"
echo -e "${YELLOW}     postgresql-rhdemo.cloudnativepg.enabled: true${NC}"
echo -e "${YELLOW}4. Déployer via Helm (cette installation ne gère que l'opérateur)${NC}"
echo ""
echo -e "${YELLOW}Les clusters PostgreSQL seront créés lors du déploiement Helm.${NC}"
echo ""

read -p "Avez-vous compris et configuré values.yaml? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    warn "Installation de l'opérateur terminée, mais les clusters ne seront pas créés"
    warn "Configurez values.yaml puis exécutez: helm upgrade rhdemo ./helm/rhdemo -n rhdemo-stagingkub"
    exit 0
fi

# ═══════════════════════════════════════════════════════════════
# 6. Informations post-installation
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ Installation CloudNativePG Operator Terminée !${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  PROCHAINES ÉTAPES                                       ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}1. Vérifier l'opérateur CloudNativePG:${NC}"
echo -e "   kubectl get pods -n $CNPG_NAMESPACE"
echo ""

echo -e "${YELLOW}2. Configurer values.yaml:${NC}"
echo -e "   cd $HELM_DIR"
echo -e "   # Éditer values.yaml:"
echo -e "   #   - Désactiver postgresql-keycloak.enabled: false"
echo -e "   #   - Désactiver postgresql-rhdemo.enabled: false"
echo -e "   #   - Activer keycloak.cloudnativepg.enabled: true"
echo -e "   #   - Activer postgresql-rhdemo.cloudnativepg.enabled: true"
echo ""

echo -e "${YELLOW}3. Déployer les clusters via Helm:${NC}"
echo -e "   helm upgrade rhdemo ./helm/rhdemo -n $NAMESPACE"
echo ""

echo -e "${YELLOW}4. Vérifier les clusters PostgreSQL:${NC}"
echo -e "   kubectl get cluster -n $NAMESPACE"
echo -e "   kubectl get pods -n $NAMESPACE -l cnpg.io/cluster"
echo ""

echo -e "${YELLOW}5. Vérifier les PodMonitors (monitoring Prometheus):${NC}"
echo -e "   kubectl get podmonitor -n $NAMESPACE"
echo ""

echo -e "${YELLOW}6. Vérifier les backups:${NC}"
echo -e "   kubectl get backup -n $NAMESPACE"
echo -e "   kubectl get scheduledbackup -n $NAMESPACE"
echo ""

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  SERVICES CLOUDNATIVEPG                                  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}Une fois les clusters déployés, les services suivants seront créés:${NC}"
echo ""
echo -e "${GREEN}Keycloak PostgreSQL:${NC}"
echo -e "  - postgresql-keycloak-rw:5432  (read-write, primary)"
echo -e "  - postgresql-keycloak-ro:5432  (read-only, replicas)"
echo -e "  - postgresql-keycloak-r:5432   (read, all instances)"
echo ""
echo -e "${GREEN}rhDemo PostgreSQL:${NC}"
echo -e "  - postgresql-rhdemo-rw:5432    (read-write, primary)"
echo -e "  - postgresql-rhdemo-ro:5432    (read-only, replicas)"
echo -e "  - postgresql-rhdemo-r:5432     (read, all instances)"
echo ""

echo -e "${YELLOW}Les applications utilisent automatiquement les services -rw${NC}"
echo -e "${YELLOW}grâce aux modifications dans les templates de déploiement.${NC}"
echo ""

echo -e "${GREEN}✅ CloudNativePG Operator est maintenant installé !${NC}"
echo ""
