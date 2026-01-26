#!/bin/bash
#
# Script d'installation RBAC pour Jenkins sur le cluster stagingkub
#
# Ce script :
# 1. Crée le namespace rhdemo-stagingkub si nécessaire
# 2. Crée le namespace monitoring si nécessaire (pour ServiceMonitors)
# 3. Applique les ressources RBAC (ServiceAccount, Role, RoleBinding, etc.)
# 4. Génère un fichier kubeconfig dédié pour Jenkins
#
# Usage : ./setup-jenkins-rbac.sh [--generate-kubeconfig]
#
# Options:
#   --generate-kubeconfig  Génère le fichier kubeconfig après création des ressources
#

set -euo pipefail

# === Configuration ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="rhdemo-stagingkub"
MONITORING_NAMESPACE="monitoring"
SERVICE_ACCOUNT="jenkins-deployer"
SECRET_NAME="jenkins-deployer-token"
KUBECONFIG_OUTPUT="${SCRIPT_DIR}/jenkins-kubeconfig.yaml"
CLUSTER_NAME="kind-rhdemo"
CONTEXT_NAME="jenkins-rhdemo-stagingkub"

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# === Vérification des prérequis ===
check_prerequisites() {
    log_info "Vérification des prérequis..."

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl n'est pas installé"
        exit 1
    fi

    if ! kubectl cluster-info &> /dev/null; then
        log_error "Impossible de se connecter au cluster Kubernetes"
        log_error "Vérifiez que le cluster KinD 'rhdemo' est démarré"
        exit 1
    fi

    # Vérification du contexte
    CURRENT_CONTEXT=$(kubectl config current-context)
    if [[ "$CURRENT_CONTEXT" != "kind-rhdemo" ]]; then
        log_warn "Le contexte actuel est '$CURRENT_CONTEXT', pas 'kind-rhdemo'"
        read -p "Voulez-vous continuer ? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    log_info "Prérequis validés"
}

# === Création des namespaces ===
create_namespaces() {
    log_info "Création des namespaces si nécessaires..."

    # Namespace principal
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Namespace '$NAMESPACE' existe déjà"
    else
        kubectl create namespace "$NAMESPACE"
        log_info "Namespace '$NAMESPACE' créé"
    fi

    # Namespace monitoring (pour ServiceMonitors)
    if kubectl get namespace "$MONITORING_NAMESPACE" &> /dev/null; then
        log_info "Namespace '$MONITORING_NAMESPACE' existe déjà"
    else
        kubectl create namespace "$MONITORING_NAMESPACE"
        log_info "Namespace '$MONITORING_NAMESPACE' créé"
    fi
}

# === Application des ressources RBAC ===
apply_rbac() {
    log_info "Application des ressources RBAC..."

    # ServiceAccount et Secret
    log_info "  -> ServiceAccount et Secret..."
    kubectl apply -f "${SCRIPT_DIR}/jenkins-serviceaccount.yaml"

    # Role dans rhdemo-stagingkub
    log_info "  -> Role (namespace: $NAMESPACE)..."
    kubectl apply -f "${SCRIPT_DIR}/jenkins-role.yaml"

    # RoleBinding dans rhdemo-stagingkub
    log_info "  -> RoleBinding (namespace: $NAMESPACE)..."
    kubectl apply -f "${SCRIPT_DIR}/jenkins-rolebinding.yaml"

    # ClusterRole (ressources cluster-wide)
    log_info "  -> ClusterRole..."
    kubectl apply -f "${SCRIPT_DIR}/jenkins-clusterrole.yaml"

    # ClusterRoleBinding
    log_info "  -> ClusterRoleBinding..."
    kubectl apply -f "${SCRIPT_DIR}/jenkins-clusterrolebinding.yaml"

    # Role et RoleBinding dans monitoring
    log_info "  -> Role et RoleBinding (namespace: $MONITORING_NAMESPACE)..."
    kubectl apply -f "${SCRIPT_DIR}/jenkins-monitoring-role.yaml"

    log_info "Ressources RBAC appliquées avec succès"
}

# === Génération du kubeconfig ===
generate_kubeconfig() {
    log_info "Génération du kubeconfig pour Jenkins..."

    # Attendre que le secret soit créé avec le token
    log_info "  -> Attente du token du ServiceAccount..."
    for i in {1..30}; do
        TOKEN=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.token}' 2>/dev/null | base64 -d || true)
        if [[ -n "$TOKEN" ]]; then
            break
        fi
        sleep 1
    done

    if [[ -z "$TOKEN" ]]; then
        log_error "Impossible de récupérer le token du ServiceAccount après 30 secondes"
        exit 1
    fi

    # Récupérer le certificat CA
    CA_CERT=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.ca\.crt}')

    # Récupérer l'URL du serveur API
    # Pour KinD, on utilise l'adresse interne du control-plane
    API_SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')

    # Générer le kubeconfig
    cat > "$KUBECONFIG_OUTPUT" <<EOF
apiVersion: v1
kind: Config
preferences: {}

clusters:
  - name: ${CLUSTER_NAME}
    cluster:
      certificate-authority-data: ${CA_CERT}
      server: ${API_SERVER}

contexts:
  - name: ${CONTEXT_NAME}
    context:
      cluster: ${CLUSTER_NAME}
      namespace: ${NAMESPACE}
      user: ${SERVICE_ACCOUNT}

current-context: ${CONTEXT_NAME}

users:
  - name: ${SERVICE_ACCOUNT}
    user:
      token: ${TOKEN}
EOF

    chmod 600 "$KUBECONFIG_OUTPUT"

    log_info "Kubeconfig généré : $KUBECONFIG_OUTPUT"
    log_info ""
    log_info "Pour utiliser ce kubeconfig dans Jenkins :"
    log_info "  1. Copiez le fichier dans le conteneur Jenkins"
    log_info "  2. Définissez KUBECONFIG=/chemin/vers/jenkins-kubeconfig.yaml"
    log_info ""
    log_info "Ou installez-le comme credential Jenkins (type 'Secret file')"
}

# === Vérification des permissions ===
verify_permissions() {
    log_info "Vérification des permissions du ServiceAccount..."

    # Test de lecture des pods
    if kubectl auth can-i get pods -n "$NAMESPACE" --as="system:serviceaccount:${NAMESPACE}:${SERVICE_ACCOUNT}" &> /dev/null; then
        log_info "  ✓ Lecture des pods"
    else
        log_error "  ✗ Lecture des pods"
    fi

    # Test de création des secrets
    if kubectl auth can-i create secrets -n "$NAMESPACE" --as="system:serviceaccount:${NAMESPACE}:${SERVICE_ACCOUNT}" &> /dev/null; then
        log_info "  ✓ Création des secrets"
    else
        log_error "  ✗ Création des secrets"
    fi

    # Test de création des deployments
    if kubectl auth can-i create deployments -n "$NAMESPACE" --as="system:serviceaccount:${NAMESPACE}:${SERVICE_ACCOUNT}" &> /dev/null; then
        log_info "  ✓ Création des deployments"
    else
        log_error "  ✗ Création des deployments"
    fi

    # Test d'exec dans les pods
    if kubectl auth can-i create pods/exec -n "$NAMESPACE" --as="system:serviceaccount:${NAMESPACE}:${SERVICE_ACCOUNT}" &> /dev/null; then
        log_info "  ✓ Exec dans les pods"
    else
        log_error "  ✗ Exec dans les pods"
    fi

    # Test de création des PersistentVolumes (cluster-wide)
    if kubectl auth can-i create persistentvolumes --as="system:serviceaccount:${NAMESPACE}:${SERVICE_ACCOUNT}" &> /dev/null; then
        log_info "  ✓ Création des PersistentVolumes"
    else
        log_error "  ✗ Création des PersistentVolumes"
    fi

    # Test de création des ServiceMonitors dans monitoring
    if kubectl auth can-i create servicemonitors.monitoring.coreos.com -n "$MONITORING_NAMESPACE" --as="system:serviceaccount:${NAMESPACE}:${SERVICE_ACCOUNT}" &> /dev/null; then
        log_info "  ✓ Création des ServiceMonitors (namespace: monitoring)"
    else
        log_warn "  ✗ Création des ServiceMonitors (CRD peut ne pas être installé)"
    fi

    # Test de NON-accès à d'autres namespaces
    if ! kubectl auth can-i get pods -n "kube-system" --as="system:serviceaccount:${NAMESPACE}:${SERVICE_ACCOUNT}" &> /dev/null; then
        log_info "  ✓ Pas d'accès au namespace kube-system (sécurité OK)"
    else
        log_warn "  ⚠ Accès au namespace kube-system détecté"
    fi
}

# === Affichage du résumé ===
print_summary() {
    echo ""
    echo "=============================================="
    echo "        RBAC Jenkins - Configuration          "
    echo "=============================================="
    echo ""
    echo "ServiceAccount : ${SERVICE_ACCOUNT}"
    echo "Namespace      : ${NAMESPACE}"
    echo ""
    echo "Ressources créées :"
    echo "  - ServiceAccount/${SERVICE_ACCOUNT}"
    echo "  - Secret/${SECRET_NAME}"
    echo "  - Role/jenkins-deployer-role"
    echo "  - RoleBinding/jenkins-deployer-rolebinding"
    echo "  - ClusterRole/jenkins-deployer-cluster-role"
    echo "  - ClusterRoleBinding/jenkins-deployer-cluster-rolebinding"
    echo "  - Role/jenkins-deployer-monitoring-role (namespace: monitoring)"
    echo "  - RoleBinding/jenkins-deployer-monitoring-rolebinding (namespace: monitoring)"
    echo ""
    echo "Permissions accordées :"
    echo "  Namespace ${NAMESPACE} :"
    echo "    - pods (get, list, watch, delete)"
    echo "    - pods/exec (create)"
    echo "    - pods/log (get, list)"
    echo "    - services, configmaps, secrets (CRUD)"
    echo "    - deployments, statefulsets (CRUD)"
    echo "    - replicasets (get, list, watch)"
    echo "    - cronjobs, jobs (CRUD/read)"
    echo "    - ingresses, networkpolicies (CRUD)"
    echo "    - persistentvolumeclaims (CRUD)"
    echo ""
    echo "  Namespace ${MONITORING_NAMESPACE} :"
    echo "    - servicemonitors, podmonitors (CRUD)"
    echo ""
    echo "  Cluster-wide :"
    echo "    - persistentvolumes (CRUD)"
    echo "    - storageclasses (get, list, watch)"
    echo "    - namespaces (get, list, watch, create)"
    echo "    - nodes (get, list)"
    echo ""
    echo "=============================================="
}

# === Main ===
main() {
    local generate_kubeconfig_flag=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --generate-kubeconfig)
                generate_kubeconfig_flag=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [--generate-kubeconfig]"
                echo ""
                echo "Options:"
                echo "  --generate-kubeconfig  Génère le fichier kubeconfig après création"
                exit 0
                ;;
            *)
                log_error "Option inconnue: $1"
                exit 1
                ;;
        esac
    done

    check_prerequisites
    create_namespaces
    apply_rbac
    verify_permissions

    if [[ "$generate_kubeconfig_flag" == true ]]; then
        generate_kubeconfig
    fi

    print_summary
}

main "$@"
