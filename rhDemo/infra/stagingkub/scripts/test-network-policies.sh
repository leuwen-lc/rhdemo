#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Script de test des Network Policies - rhdemo-stagingkub
# ═══════════════════════════════════════════════════════════════════════════════
# Ce script teste que les routes réseau interdites sont bien bloquées par les
# Network Policies. Il utilise des pods existants pour tenter des connexions
# qui devraient échouer (Zero Trust).
#
# Usage: ./test-network-policies.sh [--verbose]
#
# Prérequis:
#   - Cluster KinD rhdemo démarré
#   - Application déployée dans rhdemo-stagingkub
#   - Network Policies activées (networkPolicies.enabled: true)
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="rhdemo-stagingkub"
CONTEXT="kind-rhdemo"
TIMEOUT=3  # Timeout en secondes pour les tests de connexion
VERBOSE=${1:-""}

# Compteurs
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# ═══════════════════════════════════════════════════════════════════════════════
# Fonctions utilitaires
# ═══════════════════════════════════════════════════════════════════════════════

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Fonction pour tester une connexion TCP
# Utilise bash /dev/tcp qui est disponible dans la plupart des conteneurs
# (netcat n'est souvent pas installé dans les images minimales)
# Retourne 0 si la connexion réussit, 1 sinon
test_tcp_connection() {
    local source_pod="$1"
    local target_host="$2"
    local target_port="$3"

    # Utiliser bash /dev/tcp avec timeout
    # Cette méthode fonctionne même sans netcat installé
    kubectl exec -n "$NAMESPACE" "$source_pod" --context "$CONTEXT" -- \
        timeout "$TIMEOUT" bash -c "echo >/dev/tcp/$target_host/$target_port" 2>/dev/null
}

# Fonction pour tester qu'une connexion est BLOQUÉE (attendu: échec)
# Retourne 0 si la connexion est bien bloquée, 1 sinon
test_blocked_connection() {
    local source_pod="$1"
    local target_host="$2"
    local target_port="$3"
    local description="$4"

    TESTS_TOTAL=$((TESTS_TOTAL + 1))

    if [[ "$VERBOSE" == "--verbose" ]]; then
        echo -e "  Testing: $source_pod -> $target_host:$target_port"
    fi

    # On s'attend à ce que la connexion échoue (exit code != 0)
    if test_tcp_connection "$source_pod" "$target_host" "$target_port"; then
        # La connexion a réussi alors qu'elle devrait être bloquée
        log_fail "$description"
        echo -e "       ${RED}Connexion autorisée alors qu'elle devrait être BLOQUÉE${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    else
        # La connexion a échoué comme attendu
        log_success "$description"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    fi
}

# Fonction pour tester qu'une connexion est AUTORISÉE (attendu: succès)
# Retourne 0 si la connexion réussit, 1 sinon
test_allowed_connection() {
    local source_pod="$1"
    local target_host="$2"
    local target_port="$3"
    local description="$4"

    TESTS_TOTAL=$((TESTS_TOTAL + 1))

    if [[ "$VERBOSE" == "--verbose" ]]; then
        echo -e "  Testing: $source_pod -> $target_host:$target_port"
    fi

    if test_tcp_connection "$source_pod" "$target_host" "$target_port"; then
        log_success "$description"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        log_fail "$description"
        echo -e "       ${RED}Connexion bloquée alors qu'elle devrait être AUTORISÉE${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Fonction pour obtenir le nom du pod d'une application
get_pod_name() {
    local app_label="$1"
    kubectl get pods -n "$NAMESPACE" --context "$CONTEXT" \
        -l "app=$app_label" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null
}

# ═══════════════════════════════════════════════════════════════════════════════
# Vérifications préliminaires
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test des Network Policies - rhdemo-stagingkub                    ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo ""

# Vérifier le contexte kubectl
log_info "Vérification du contexte Kubernetes..."
if ! kubectl cluster-info --context "$CONTEXT" &>/dev/null; then
    log_fail "Impossible de se connecter au cluster $CONTEXT"
    exit 1
fi

# Vérifier que les Network Policies sont déployées
log_info "Vérification des Network Policies..."
NP_COUNT=$(kubectl get networkpolicies -n "$NAMESPACE" --context "$CONTEXT" --no-headers 2>/dev/null | wc -l)
if [[ "$NP_COUNT" -eq 0 ]]; then
    log_fail "Aucune Network Policy trouvée dans $NAMESPACE"
    echo -e "       Assurez-vous que networkPolicies.enabled=true dans values.yaml"
    exit 1
fi
log_info "  $NP_COUNT Network Policies trouvées"

# Récupérer les noms des pods
log_info "Récupération des pods..."
RHDEMO_POD=$(get_pod_name "rhdemo-app")
KEYCLOAK_POD=$(get_pod_name "keycloak")
PG_RHDEMO_POD=$(get_pod_name "postgresql-rhdemo")
PG_KEYCLOAK_POD=$(get_pod_name "postgresql-keycloak")

if [[ -z "$RHDEMO_POD" || -z "$KEYCLOAK_POD" || -z "$PG_RHDEMO_POD" || -z "$PG_KEYCLOAK_POD" ]]; then
    log_fail "Impossible de trouver tous les pods nécessaires"
    echo "  rhdemo-app: ${RHDEMO_POD:-NOT FOUND}"
    echo "  keycloak: ${KEYCLOAK_POD:-NOT FOUND}"
    echo "  postgresql-rhdemo: ${PG_RHDEMO_POD:-NOT FOUND}"
    echo "  postgresql-keycloak: ${PG_KEYCLOAK_POD:-NOT FOUND}"
    exit 1
fi

log_info "  rhdemo-app: $RHDEMO_POD"
log_info "  keycloak: $KEYCLOAK_POD"
log_info "  postgresql-rhdemo: $PG_RHDEMO_POD"
log_info "  postgresql-keycloak: $PG_KEYCLOAK_POD"

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  TESTS DES ROUTES INTERDITES (doivent échouer)                    ${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Isolation inter-bases PostgreSQL
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${BLUE}▶ Test 1: Isolation des bases PostgreSQL${NC}"

test_blocked_connection "$PG_RHDEMO_POD" "postgresql-keycloak" "5432" \
    "postgresql-rhdemo → postgresql-keycloak:5432 [INTERDIT]"

test_blocked_connection "$PG_KEYCLOAK_POD" "postgresql-rhdemo" "5432" \
    "postgresql-keycloak → postgresql-rhdemo:5432 [INTERDIT]"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Isolation application ↔ mauvaise base
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${BLUE}▶ Test 2: Applications vers mauvaise base de données${NC}"

test_blocked_connection "$RHDEMO_POD" "postgresql-keycloak" "5432" \
    "rhdemo-app → postgresql-keycloak:5432 [INTERDIT]"

test_blocked_connection "$KEYCLOAK_POD" "postgresql-rhdemo" "5432" \
    "keycloak → postgresql-rhdemo:5432 [INTERDIT]"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Blocage egress Internet
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${BLUE}▶ Test 3: Blocage egress vers Internet${NC}"

# Note: On teste avec une IP publique pour éviter la résolution DNS
# 8.8.8.8 = Google DNS, 1.1.1.1 = Cloudflare DNS
test_blocked_connection "$RHDEMO_POD" "8.8.8.8" "443" \
    "rhdemo-app → Internet (8.8.8.8:443) [INTERDIT]"

test_blocked_connection "$KEYCLOAK_POD" "1.1.1.1" "443" \
    "keycloak → Internet (1.1.1.1:443) [INTERDIT]"

test_blocked_connection "$PG_RHDEMO_POD" "8.8.8.8" "80" \
    "postgresql-rhdemo → Internet (8.8.8.8:80) [INTERDIT]"

test_blocked_connection "$PG_KEYCLOAK_POD" "8.8.8.8" "80" \
    "postgresql-keycloak → Internet (8.8.8.8:80) [INTERDIT]"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4: Blocage egress vers pods non autorisés
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${BLUE}▶ Test 4: Egress vers pods non autorisés${NC}"

# Keycloak n'a pas le droit de contacter rhdemo-app
test_blocked_connection "$KEYCLOAK_POD" "rhdemo-app" "9000" \
    "keycloak → rhdemo-app:9000 [INTERDIT]"

# PostgreSQL n'a pas le droit de contacter les applications
test_blocked_connection "$PG_RHDEMO_POD" "rhdemo-app" "9000" \
    "postgresql-rhdemo → rhdemo-app:9000 [INTERDIT]"

test_blocked_connection "$PG_KEYCLOAK_POD" "keycloak" "8080" \
    "postgresql-keycloak → keycloak:8080 [INTERDIT]"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5: Vérification routes légitimes (contrôle positif)
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  TESTS DES ROUTES AUTORISÉES (contrôle positif)                  ${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}▶ Test 5: Routes légitimes${NC}"

test_allowed_connection "$RHDEMO_POD" "postgresql-rhdemo" "5432" \
    "rhdemo-app → postgresql-rhdemo:5432 [AUTORISÉ]"

test_allowed_connection "$RHDEMO_POD" "keycloak" "8080" \
    "rhdemo-app → keycloak:8080 [AUTORISÉ]"

test_allowed_connection "$KEYCLOAK_POD" "postgresql-keycloak" "5432" \
    "keycloak → postgresql-keycloak:5432 [AUTORISÉ]"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Résumé
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  RÉSUMÉ                                                           ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Tests exécutés: $TESTS_TOTAL"
echo -e "  ${GREEN}Réussis: $TESTS_PASSED${NC}"
echo -e "  ${RED}Échoués: $TESTS_FAILED${NC}"
echo ""

if [[ "$TESTS_FAILED" -eq 0 ]]; then
    echo -e "${GREEN}✅ Toutes les Network Policies sont correctement appliquées !${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Certaines Network Policies ne fonctionnent pas correctement.${NC}"
    echo -e "   Vérifiez que Cilium/le CNI supporte bien les Network Policies."
    echo ""
    exit 1
fi
