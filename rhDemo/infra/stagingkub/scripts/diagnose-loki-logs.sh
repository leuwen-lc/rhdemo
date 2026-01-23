#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Script de diagnostic pour la stack Loki/Promtail/Grafana
# ═══════════════════════════════════════════════════════════════
# Usage: ./diagnose-loki-logs.sh [--verbose]
#
# Ce script diagnostique les problèmes de logs manquants dans Grafana
# en vérifiant chaque composant de la chaîne de collecte.
# ═══════════════════════════════════════════════════════════════

# Note: Ne pas utiliser set -e car des commandes peuvent échouer sans que ce soit critique

# Namespaces
LOKI_NAMESPACE="loki-stack"
APP_NAMESPACE="rhdemo-stagingkub"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Options
VERBOSE=false
[[ "$1" == "--verbose" || "$1" == "-v" ]] && VERBOSE=true

# Compteurs
ERRORS=0
WARNINGS=0

log_section() { echo -e "\n${BOLD}${BLUE}═══════════════════════════════════════════════════════════════${NC}"; echo -e "${BOLD}${BLUE}  $1${NC}"; echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════${NC}"; }
log_check() { echo -e "${CYAN}[CHECK]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; ((WARNINGS++)); }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; ((ERRORS++)); }
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_verbose() { $VERBOSE && echo -e "${CYAN}[DEBUG]${NC} $1"; }

# ═══════════════════════════════════════════════════════════════
# 1. VÉRIFICATION DES PODS
# ═══════════════════════════════════════════════════════════════
check_pods() {
    log_section "1. ÉTAT DES PODS"

    # Pods Loki Stack
    log_check "Pods dans le namespace $LOKI_NAMESPACE..."
    LOKI_PODS=$(kubectl get pods -n "$LOKI_NAMESPACE" -o wide 2>/dev/null || echo "ERROR")
    if [[ "$LOKI_PODS" == "ERROR" ]]; then
        log_error "Impossible de lister les pods dans $LOKI_NAMESPACE"
        return
    fi

    echo "$LOKI_PODS"
    echo ""

    # Vérifier Loki (utilise le label app.kubernetes.io/name=loki du chart Helm)
    LOKI_STATUS=$(kubectl get pods -n "$LOKI_NAMESPACE" -l app.kubernetes.io/name=loki -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "NotFound")
    if [[ "$LOKI_STATUS" == "Running" ]]; then
        log_ok "Loki est Running"
    else
        log_error "Loki n'est pas Running (status: $LOKI_STATUS)"
    fi

    # Vérifier Promtail
    PROMTAIL_PODS=$(kubectl get pods -n "$LOKI_NAMESPACE" -l app.kubernetes.io/name=promtail -o jsonpath='{range .items[*]}{.metadata.name}:{.status.phase}{"\n"}{end}' 2>/dev/null)
    if [[ -n "$PROMTAIL_PODS" ]]; then
        PROMTAIL_NOT_RUNNING=$(echo "$PROMTAIL_PODS" | grep -v ":Running" || true)
        if [[ -z "$PROMTAIL_NOT_RUNNING" ]]; then
            PROMTAIL_COUNT=$(echo "$PROMTAIL_PODS" | wc -l)
            log_ok "Tous les pods Promtail sont Running ($PROMTAIL_COUNT pods)"
        else
            log_error "Certains pods Promtail ne sont pas Running:"
            echo "$PROMTAIL_NOT_RUNNING"
        fi
    else
        log_error "Aucun pod Promtail trouvé"
    fi

    # Vérifier Grafana
    GRAFANA_STATUS=$(kubectl get pods -n "$LOKI_NAMESPACE" -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "NotFound")
    if [[ "$GRAFANA_STATUS" == "Running" ]]; then
        log_ok "Grafana est Running"
    else
        log_error "Grafana n'est pas Running (status: $GRAFANA_STATUS)"
    fi

    # Pods applicatifs
    log_check "Pods dans le namespace $APP_NAMESPACE..."
    APP_PODS=$(kubectl get pods -n "$APP_NAMESPACE" --no-headers 2>/dev/null | awk '{print $1 ": " $3}')
    echo "$APP_PODS"
}

# ═══════════════════════════════════════════════════════════════
# 2. VÉRIFICATION DES LOGS KUBERNETES (SOURCE)
# ═══════════════════════════════════════════════════════════════
check_kubernetes_logs() {
    log_section "2. LOGS KUBERNETES (SOURCE)"

    # Vérifier que les logs existent sur le node
    log_check "Vérification des fichiers de logs sur les nodes..."

    # Liste des pods à vérifier
    declare -A PODS_TO_CHECK=(
        ["rhdemo-app"]="$APP_NAMESPACE"
        ["keycloak"]="$APP_NAMESPACE"
        ["postgresql-rhdemo"]="$APP_NAMESPACE"
    )

    for POD_PREFIX in "${!PODS_TO_CHECK[@]}"; do
        NS="${PODS_TO_CHECK[$POD_PREFIX]}"
        POD_NAME=$(kubectl get pods -n "$NS" -o name 2>/dev/null | grep "$POD_PREFIX" | head -1 | sed 's|pod/||')

        if [[ -n "$POD_NAME" ]]; then
            # Tester si le pod génère des logs
            LOG_COUNT=$(kubectl logs -n "$NS" "$POD_NAME" --tail=10 2>/dev/null | wc -l)
            if [[ $LOG_COUNT -gt 0 ]]; then
                log_ok "$POD_PREFIX: $LOG_COUNT lignes de logs récentes disponibles"
                $VERBOSE && kubectl logs -n "$NS" "$POD_NAME" --tail=3 2>/dev/null | head -3
            else
                log_warn "$POD_PREFIX: Aucun log récent trouvé"
            fi
        else
            log_warn "$POD_PREFIX: Pod non trouvé dans $NS"
        fi
    done

    # Vérifier les CronJobs de backup
    log_check "Vérification des jobs de backup..."
    BACKUP_JOBS=$(kubectl get jobs -n "$APP_NAMESPACE" -l app=postgresql-backup --sort-by=.metadata.creationTimestamp 2>/dev/null | tail -5)
    if [[ -n "$BACKUP_JOBS" ]]; then
        echo "$BACKUP_JOBS"
        # Dernier job
        LAST_JOB=$(kubectl get jobs -n "$APP_NAMESPACE" -l app=postgresql-backup -o jsonpath='{.items[-1].metadata.name}' 2>/dev/null)
        if [[ -n "$LAST_JOB" ]]; then
            JOB_POD=$(kubectl get pods -n "$APP_NAMESPACE" -l job-name="$LAST_JOB" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
            if [[ -n "$JOB_POD" ]]; then
                log_info "Logs du dernier job de backup ($LAST_JOB):"
                kubectl logs -n "$APP_NAMESPACE" "$JOB_POD" --tail=5 2>/dev/null || log_warn "Impossible de récupérer les logs du job"
            fi
        fi
    else
        log_info "Aucun job de backup trouvé (normal si pas encore exécuté)"
    fi
}

# ═══════════════════════════════════════════════════════════════
# 3. VÉRIFICATION PROMTAIL
# ═══════════════════════════════════════════════════════════════
check_promtail() {
    log_section "3. PROMTAIL (COLLECTEUR)"

    # Trouver un pod Promtail
    PROMTAIL_POD=$(kubectl get pods -n "$LOKI_NAMESPACE" -l app.kubernetes.io/name=promtail -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [[ -z "$PROMTAIL_POD" ]]; then
        log_error "Aucun pod Promtail trouvé"
        return
    fi

    log_info "Pod Promtail analysé: $PROMTAIL_POD"

    # Logs Promtail (erreurs récentes)
    log_check "Recherche d'erreurs dans les logs Promtail..."
    PROMTAIL_ERRORS=$(kubectl logs -n "$LOKI_NAMESPACE" "$PROMTAIL_POD" --tail=100 2>/dev/null | grep -iE "error|failed|warning" | tail -10)
    if [[ -n "$PROMTAIL_ERRORS" ]]; then
        log_warn "Erreurs/warnings trouvés dans Promtail:"
        echo "$PROMTAIL_ERRORS"
    else
        log_ok "Pas d'erreurs récentes dans les logs Promtail"
    fi

    # Vérifier les targets Promtail via les logs (plus fiable car pas de curl/wget dans le conteneur)
    log_check "Vérification des targets Promtail via les logs..."

    PROMTAIL_LOGS=$(kubectl logs -n "$LOKI_NAMESPACE" "$PROMTAIL_POD" --tail=200 2>/dev/null)

    # Compter les targets par app via les logs
    for APP in "rhdemo-app" "keycloak" "postgresql-rhdemo" "postgresql-keycloak"; do
        if echo "$PROMTAIL_LOGS" | grep -q "Adding target.*$APP\|tail routine.*$APP"; then
            log_ok "Target pour '$APP' détecté (logs collectés)"
        else
            log_warn "Target pour '$APP' non trouvé dans les logs récents"
        fi
    done

    # Vérifier s'il y a des erreurs de connexion Loki
    log_check "Vérification des erreurs de push vers Loki..."
    PUSH_ERRORS=$(echo "$PROMTAIL_LOGS" | grep -iE "error.*push|failed.*send|connection refused" | tail -3)
    if [[ -n "$PUSH_ERRORS" ]]; then
        log_error "Erreurs de push vers Loki détectées:"
        echo "$PUSH_ERRORS"
    else
        log_ok "Pas d'erreurs de push vers Loki"
    fi

    # Vérifier la config Promtail (peut être dans un Secret plutôt qu'un ConfigMap)
    log_check "Vérification de la configuration Promtail..."
    PROMTAIL_CONFIG=$(kubectl get secret -n "$LOKI_NAMESPACE" promtail -o jsonpath='{.data.promtail\.yaml}' 2>/dev/null | base64 -d 2>/dev/null || echo "")

    if [[ -z "$PROMTAIL_CONFIG" ]]; then
        # Essayer ConfigMap si pas de Secret
        PROMTAIL_CONFIG=$(kubectl get configmap -n "$LOKI_NAMESPACE" -l app.kubernetes.io/name=promtail -o jsonpath='{.items[0].data.promtail\.yaml}' 2>/dev/null || echo "")
    fi

    if [[ -n "$PROMTAIL_CONFIG" ]]; then
        # Vérifier les scrape_configs
        if echo "$PROMTAIL_CONFIG" | grep -q "kubernetes_sd_configs"; then
            log_ok "Configuration kubernetes_sd_configs présente"
        else
            log_error "Configuration kubernetes_sd_configs absente!"
        fi

        # Vérifier le namespace filter
        if echo "$PROMTAIL_CONFIG" | grep -q "$APP_NAMESPACE"; then
            log_ok "Namespace $APP_NAMESPACE configuré dans Promtail"
        else
            log_warn "Namespace $APP_NAMESPACE non explicitement configuré (peut utiliser regex)"
        fi

        $VERBOSE && echo "$PROMTAIL_CONFIG"
    else
        log_warn "Configuration Promtail non trouvée (Secret ou ConfigMap)"
    fi
}

# ═══════════════════════════════════════════════════════════════
# 4. VÉRIFICATION LOKI
# ═══════════════════════════════════════════════════════════════
check_loki() {
    log_section "4. LOKI (STOCKAGE)"

    # Trouver le pod Loki (utilise le label app.kubernetes.io/name=loki du chart Helm)
    LOKI_POD=$(kubectl get pods -n "$LOKI_NAMESPACE" -l app.kubernetes.io/name=loki -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [[ -z "$LOKI_POD" ]]; then
        log_error "Aucun pod Loki trouvé"
        return
    fi

    log_info "Pod Loki analysé: $LOKI_POD"

    # Logs Loki (erreurs récentes)
    log_check "Recherche d'erreurs dans les logs Loki..."
    LOKI_ERRORS=$(kubectl logs -n "$LOKI_NAMESPACE" "$LOKI_POD" --tail=100 2>/dev/null | grep -iE "error|failed|level=error" | tail -10)
    if [[ -n "$LOKI_ERRORS" ]]; then
        log_warn "Erreurs trouvées dans Loki:"
        echo "$LOKI_ERRORS"
    else
        log_ok "Pas d'erreurs récentes dans les logs Loki"
    fi

    # Vérifier les rate limits
    log_check "Vérification des rate limits..."
    RATE_LIMIT_ERRORS=$(kubectl logs -n "$LOKI_NAMESPACE" "$LOKI_POD" --tail=500 2>/dev/null | grep -iE "rate.*limit|too many" | tail -5)
    if [[ -n "$RATE_LIMIT_ERRORS" ]]; then
        log_error "Rate limits atteints! Les logs peuvent être perdus:"
        echo "$RATE_LIMIT_ERRORS"
    else
        log_ok "Pas de rate limiting détecté"
    fi

    # Vérifier l'espace disque du PVC
    log_check "Vérification de l'espace disque Loki..."
    # Exec dans le pod pour vérifier l'espace
    DISK_USAGE=$(kubectl exec -n "$LOKI_NAMESPACE" "$LOKI_POD" -- df -h /data 2>/dev/null | tail -1 || echo "ERROR")
    if [[ "$DISK_USAGE" != "ERROR" ]]; then
        DISK_PERCENT=$(echo "$DISK_USAGE" | awk '{print $5}' | tr -d '%')
        if [[ $DISK_PERCENT -gt 90 ]]; then
            log_error "Disque Loki presque plein: ${DISK_PERCENT}%"
        elif [[ $DISK_PERCENT -gt 80 ]]; then
            log_warn "Disque Loki à ${DISK_PERCENT}%"
        else
            log_ok "Disque Loki OK: ${DISK_PERCENT}% utilisé"
        fi
        echo "  $DISK_USAGE"
    else
        log_warn "Impossible de vérifier l'espace disque Loki"
    fi

    # Test de connectivité Loki API via pod temporaire (plus fiable que port-forward)
    log_check "Test de l'API Loki..."

    # Test ready via loki-gateway (comme Promtail)
    LOKI_READY=$(kubectl run -n "$LOKI_NAMESPACE" test-loki-diag --rm -i --restart=Never --image=curlimages/curl:latest \
        -- curl -s "http://loki-0.loki-headless.$LOKI_NAMESPACE.svc.cluster.local:3100/ready" 2>/dev/null | tail -1)

    if [[ "$LOKI_READY" == "ready" ]]; then
        log_ok "Loki API répond: ready"
    else
        log_warn "Loki API ne répond pas correctement (via test pod)"
    fi

    # Lister les valeurs du label app via loki-gateway
    log_check "Valeurs du label 'app' dans Loki..."
    APP_VALUES=$(kubectl run -n "$LOKI_NAMESPACE" test-loki-apps --rm -i --restart=Never --image=curlimages/curl:latest \
        -- curl -s "http://loki-gateway.$LOKI_NAMESPACE.svc.cluster.local/loki/api/v1/label/app/values" 2>/dev/null | tail -1)

    if [[ "$APP_VALUES" != *"ERROR"* && -n "$APP_VALUES" ]]; then
        log_info "Apps indexées: $APP_VALUES"

        # Vérifier si nos apps sont présentes
        for APP in "rhdemo-app" "keycloak" "postgresql-rhdemo" "postgresql-keycloak"; do
            if echo "$APP_VALUES" | grep -q "$APP"; then
                log_ok "App '$APP' présente dans Loki"
            else
                log_warn "App '$APP' NON présente dans Loki"
            fi
        done
    else
        log_warn "Impossible de récupérer les apps indexées dans Loki"
    fi

    # Lister tous les labels disponibles
    log_check "Labels disponibles dans Loki..."
    LABELS=$(kubectl run -n "$LOKI_NAMESPACE" test-loki-labels --rm -i --restart=Never --image=curlimages/curl:latest \
        -- curl -s "http://loki-gateway.$LOKI_NAMESPACE.svc.cluster.local/loki/api/v1/labels" 2>/dev/null | tail -1)

    if [[ "$LABELS" != *"ERROR"* && -n "$LABELS" ]]; then
        log_info "Labels: $LABELS"
    fi

    # Vérifier la configuration de rétention
    log_check "Configuration de rétention Loki..."
    LOKI_CONFIG=$(kubectl get configmap -n "$LOKI_NAMESPACE" loki -o jsonpath='{.data.loki\.yaml}' 2>/dev/null)
    if [[ -n "$LOKI_CONFIG" ]]; then
        RETENTION=$(echo "$LOKI_CONFIG" | grep -A5 "retention" | head -6)
        if [[ -n "$RETENTION" ]]; then
            log_info "Configuration rétention:"
            echo "$RETENTION"
        else
            log_warn "Pas de configuration de rétention explicite trouvée"
        fi
    fi
}

# ═══════════════════════════════════════════════════════════════
# 5. VÉRIFICATION GRAFANA
# ═══════════════════════════════════════════════════════════════
check_grafana() {
    log_section "5. GRAFANA (VISUALISATION)"

    # Vérifier la datasource Loki
    log_check "Vérification de la datasource Loki dans Grafana..."

    GRAFANA_POD=$(kubectl get pods -n "$LOKI_NAMESPACE" -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [[ -z "$GRAFANA_POD" ]]; then
        log_error "Pod Grafana non trouvé"
        return
    fi

    log_info "Pod Grafana: $GRAFANA_POD"

    # Récupérer le mot de passe admin Grafana
    GRAFANA_PASS=$(kubectl get secret -n "$LOKI_NAMESPACE" loki-grafana -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d)

    if [[ -z "$GRAFANA_PASS" ]]; then
        log_warn "Impossible de récupérer le mot de passe Grafana"
        return
    fi

    # Test health Grafana via kubectl exec (pas besoin de port-forward)
    GRAFANA_HEALTH=$(kubectl exec -n "$LOKI_NAMESPACE" "$GRAFANA_POD" -c grafana -- \
        wget -q -O- "http://admin:${GRAFANA_PASS}@localhost:3000/api/health" 2>/dev/null || echo "ERROR")

    if echo "$GRAFANA_HEALTH" | grep -q "ok"; then
        log_ok "Grafana API répond OK"
    else
        log_warn "Grafana API: $GRAFANA_HEALTH"
    fi

    # Vérifier les datasources
    log_check "Vérification des datasources Grafana..."
    DATASOURCES=$(kubectl exec -n "$LOKI_NAMESPACE" "$GRAFANA_POD" -c grafana -- \
        wget -q -O- "http://admin:${GRAFANA_PASS}@localhost:3000/api/datasources" 2>/dev/null || echo "ERROR")

    if [[ "$DATASOURCES" != "ERROR" && -n "$DATASOURCES" ]]; then
        # Chercher Loki
        if echo "$DATASOURCES" | grep -qi "loki"; then
            log_ok "Datasource Loki configurée dans Grafana"
        else
            log_error "Datasource Loki NON configurée dans Grafana!"
        fi

        # Chercher Prometheus
        if echo "$DATASOURCES" | grep -qi "prometheus"; then
            log_ok "Datasource Prometheus configurée dans Grafana"
        else
            log_warn "Datasource Prometheus non configurée"
        fi

        $VERBOSE && log_info "Datasources: $DATASOURCES"
    else
        log_warn "Impossible de récupérer les datasources Grafana"
    fi
}

# ═══════════════════════════════════════════════════════════════
# 6. VÉRIFICATION RÉSEAU
# ═══════════════════════════════════════════════════════════════
check_network() {
    log_section "6. CONNECTIVITÉ RÉSEAU"

    # Test Promtail -> Loki Gateway
    log_check "Test connectivité Promtail -> Loki Gateway..."
    PROMTAIL_POD=$(kubectl get pods -n "$LOKI_NAMESPACE" -l app.kubernetes.io/name=promtail -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [[ -n "$PROMTAIL_POD" ]]; then
        # Test connectivité vers loki-gateway (utilisé par Promtail pour push)
        HTTP_TEST=$(kubectl run -n "$LOKI_NAMESPACE" test-net-diag --rm -i --restart=Never --image=curlimages/curl:latest \
            -- curl -s -o /dev/null -w "%{http_code}" "http://loki-gateway.$LOKI_NAMESPACE.svc.cluster.local/" 2>/dev/null | tail -1)

        if [[ "$HTTP_TEST" == "200" ]]; then
            log_ok "Connectivité HTTP vers Loki Gateway OK (HTTP $HTTP_TEST)"
        else
            log_warn "Connectivité vers Loki Gateway: HTTP $HTTP_TEST"
        fi

        # Test connectivité vers loki direct
        HTTP_TEST2=$(kubectl run -n "$LOKI_NAMESPACE" test-net-diag2 --rm -i --restart=Never --image=curlimages/curl:latest \
            -- curl -s "http://loki-0.loki-headless.$LOKI_NAMESPACE.svc.cluster.local:3100/ready" 2>/dev/null | tail -1)

        if [[ "$HTTP_TEST2" == "ready" ]]; then
            log_ok "Connectivité HTTP directe vers Loki-0 OK"
        else
            log_warn "Connectivité directe vers Loki-0: $HTTP_TEST2"
        fi
    fi

    # Vérifier les Services
    log_check "Services Loki Stack..."
    kubectl get svc -n "$LOKI_NAMESPACE" --no-headers 2>/dev/null | awk '{print "  " $1 " -> " $5}'
}

# ═══════════════════════════════════════════════════════════════
# 7. VÉRIFICATION DES LABELS PODS
# ═══════════════════════════════════════════════════════════════
check_pod_labels() {
    log_section "7. LABELS DES PODS APPLICATIFS"

    log_check "Labels des pods dans $APP_NAMESPACE..."

    # Pour chaque pod, afficher les labels
    PODS=$(kubectl get pods -n "$APP_NAMESPACE" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels}{"\n"}{end}' 2>/dev/null)

    echo "$PODS" | while read -r line; do
        POD_NAME=$(echo "$line" | cut -f1)
        LABELS=$(echo "$line" | cut -f2)

        echo -e "\n${CYAN}Pod: $POD_NAME${NC}"
        echo "  Labels: $LABELS"

        # Vérifier si le label 'app' est présent
        if echo "$LABELS" | grep -q '"app":'; then
            APP_LABEL=$(echo "$LABELS" | grep -o '"app":"[^"]*"' | cut -d'"' -f4)
            log_ok "Label 'app' présent: $APP_LABEL"
        else
            log_warn "Label 'app' ABSENT - Promtail pourrait ne pas collecter ces logs!"
        fi
    done
}

# ═══════════════════════════════════════════════════════════════
# 8. RÉSUMÉ ET RECOMMANDATIONS
# ═══════════════════════════════════════════════════════════════
show_summary() {
    log_section "8. RÉSUMÉ DU DIAGNOSTIC"

    echo -e "\n${BOLD}Résultats:${NC}"
    echo -e "  - Erreurs:   ${RED}$ERRORS${NC}"
    echo -e "  - Warnings:  ${YELLOW}$WARNINGS${NC}"

    if [[ $ERRORS -gt 0 ]]; then
        echo -e "\n${RED}${BOLD}⚠ Des erreurs ont été détectées!${NC}"
        echo -e "\nActions recommandées:"
        echo "  1. Vérifier les logs des composants en erreur"
        echo "  2. Redémarrer les pods problématiques"
        echo "  3. Vérifier la configuration Promtail/Loki"
    elif [[ $WARNINGS -gt 0 ]]; then
        echo -e "\n${YELLOW}${BOLD}⚡ Des warnings ont été détectés${NC}"
        echo -e "\nActions recommandées:"
        echo "  1. Vérifier si les warnings sont bloquants"
        echo "  2. Consulter les logs détaillés avec --verbose"
    else
        echo -e "\n${GREEN}${BOLD}✓ Tous les composants semblent fonctionnels${NC}"
        echo -e "\nSi les logs sont toujours manquants, vérifiez:"
        echo "  1. La plage de temps dans Grafana"
        echo "  2. Les filtres de la requête LogQL"
        echo "  3. Le délai de propagation (quelques secondes)"
    fi

    echo -e "\n${BOLD}Commandes utiles:${NC}"
    echo "  # Logs Promtail en temps réel"
    echo "  kubectl logs -n $LOKI_NAMESPACE -l app.kubernetes.io/name=promtail -f"
    echo ""
    echo "  # Logs Loki en temps réel"
    echo "  kubectl logs -n $LOKI_NAMESPACE -l app.kubernetes.io/name=loki -f"
    echo ""
    echo "  # Redémarrer Promtail"
    echo "  kubectl rollout restart daemonset -n $LOKI_NAMESPACE -l app.kubernetes.io/name=promtail"
    echo ""
    echo "  # Redémarrer Loki"
    echo "  kubectl rollout restart statefulset -n $LOKI_NAMESPACE loki"
}

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
main() {
    echo -e "${BOLD}${GREEN}"
    echo "═══════════════════════════════════════════════════════════════"
    echo "     DIAGNOSTIC STACK LOKI/PROMTAIL/GRAFANA - rhDemo           "
    echo "═══════════════════════════════════════════════════════════════"
    echo -e "${NC}"
    echo "Date: $(date)"
    echo "Cluster: $(kubectl config current-context 2>/dev/null || echo 'N/A')"
    echo ""

    # Vérifier la connexion au cluster
    if ! kubectl cluster-info &>/dev/null; then
        log_error "Impossible de se connecter au cluster Kubernetes"
        exit 1
    fi

    check_pods
    check_kubernetes_logs
    check_promtail
    check_loki
    check_grafana
    check_network
    check_pod_labels
    show_summary
}

main "$@"
