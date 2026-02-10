#!/bin/bash
#
# Migration PostgreSQL 16 → 18 pour la base rhdemo
# Stratégie : Dump/Restore (adaptée à l'environnement KinD stagingkub)
#
# Prérequis :
#   - kubectl configuré pour le cluster kind-rhdemo
#   - Namespace rhdemo-stagingkub existant avec PostgreSQL 16 déployé
#   - Helm chart déjà mis à jour pour PG 18 (mountPath, pas de PGDATA)
#
# Usage : ./migrate-postgresql-rhdemo.sh [phase]
#   Phases disponibles :
#     backup   - Sauvegarde la base rhdemo (pg_dump)
#     prepare  - Supprime StatefulSet, PVC, PV et nettoie le répertoire host
#     deploy   - Redéploie via Helm (crée PG 18 vide)
#     restore  - Restaure le dump dans PostgreSQL 18
#     status   - Affiche l'état actuel (version PG, données)
#     full     - Exécute toutes les phases dans l'ordre
#
# IMPORTANT : Le chart Helm gère les deux bases (rhdemo + keycloak).
#   helm upgrade redéploie les deux StatefulSets.
#   Si les deux bases doivent migrer, préparer les deux AVANT le deploy.
#   Ordre recommandé :
#     1. ./migrate-postgresql-rhdemo.sh backup
#     2. ./migrate-postgresql-keycloak.sh backup
#     3. ./migrate-postgresql-rhdemo.sh prepare
#     4. ./migrate-postgresql-keycloak.sh prepare
#     5. ./migrate-postgresql-rhdemo.sh deploy   (redéploie les deux)
#     6. ./migrate-postgresql-rhdemo.sh restore
#     7. ./migrate-postgresql-keycloak.sh restore

set -euo pipefail

# Configuration
NAMESPACE="rhdemo-stagingkub"
DB_NAME="rhdemo"
DB_USER="rhdemo"
STS_NAME="postgresql-rhdemo"
PVC_NAME="postgresql-data-postgresql-rhdemo-0"
PV_NAME="postgresql-rhdemo-pv"
HOST_DATA_DIR="/home/leno-vo/kind-data/rhdemo-stagingkub/postgresql-rhdemo"
BACKUP_DIR="/tmp"
BACKUP_FILE="${BACKUP_DIR}/rhdemo-pg16-backup.sql"
HELM_DIR="$(cd "$(dirname "$0")/../helm/rhdemo" && pwd)"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_prerequisites() {
    log_info "Vérification des prérequis..."

    if ! command -v kubectl &>/dev/null; then
        log_error "kubectl non trouvé"
        exit 1
    fi

    if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
        log_error "Namespace $NAMESPACE introuvable"
        exit 1
    fi

    log_info "Prérequis OK"
}

phase_backup() {
    log_info "=== PHASE : BACKUP de la base $DB_NAME ==="

    # Vérifier que le pod existe
    if ! kubectl get statefulset -n "$NAMESPACE" "$STS_NAME" &>/dev/null; then
        log_error "StatefulSet $STS_NAME introuvable. Rien à sauvegarder."
        exit 1
    fi

    # Vérifier que le pod est ready
    if ! kubectl wait --for=condition=ready pod "${STS_NAME}-0" -n "$NAMESPACE" --timeout=30s &>/dev/null; then
        log_error "Pod ${STS_NAME}-0 non prêt"
        exit 1
    fi

    # Afficher la version PostgreSQL actuelle
    local pg_version
    pg_version=$(kubectl exec -n "$NAMESPACE" "${STS_NAME}-0" -- psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT version();" 2>/dev/null | head -1 | xargs)
    log_info "Version PostgreSQL : $pg_version"

    # Compter les enregistrements
    log_info "Nombre d'enregistrements avant backup :"
    kubectl exec -n "$NAMESPACE" "${STS_NAME}-0" -- \
        psql -U "$DB_USER" -d "$DB_NAME" -c \
        "SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname;" 2>/dev/null || true

    # Dump
    log_info "Création du dump dans ${BACKUP_FILE}..."
    kubectl exec -n "$NAMESPACE" "${STS_NAME}-0" -- \
        pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists > "$BACKUP_FILE"

    local size
    size=$(du -h "$BACKUP_FILE" | cut -f1)
    log_info "Dump créé : ${BACKUP_FILE} (${size})"

    log_info "=== BACKUP TERMINÉ ==="
}

phase_prepare() {
    log_info "=== PHASE : PREPARE (nettoyage pour PG 18) ==="

    # Vérifier que le backup existe
    if [[ ! -f "$BACKUP_FILE" ]]; then
        log_error "Backup introuvable : ${BACKUP_FILE}"
        log_error "Exécutez d'abord : $0 backup"
        exit 1
    fi

    log_warn "Cette phase va supprimer le StatefulSet, PVC, PV et les données PG 16."
    log_warn "Les données sont sauvegardées dans : ${BACKUP_FILE}"
    read -p "Continuer ? (oui/non) " -r
    if [[ ! $REPLY == "oui" ]]; then
        log_info "Annulé"
        exit 0
    fi

    # 1. Supprimer le StatefulSet (arrête le pod)
    log_info "Suppression du StatefulSet ${STS_NAME}..."
    kubectl delete statefulset -n "$NAMESPACE" "$STS_NAME" --ignore-not-found=true
    sleep 3

    # 2. Supprimer le PVC
    log_info "Suppression du PVC ${PVC_NAME}..."
    kubectl delete pvc -n "$NAMESPACE" "$PVC_NAME" --ignore-not-found=true

    # 3. Supprimer le PV (en statut Released après suppression du PVC)
    log_info "Suppression du PV ${PV_NAME}..."
    kubectl delete pv "$PV_NAME" --ignore-not-found=true

    # 4. Nettoyer le répertoire host (données PG 16 incompatibles PG 18)
    log_info "Nettoyage du répertoire host ${HOST_DATA_DIR}..."
    if [[ -d "$HOST_DATA_DIR" ]]; then
        rm -rf "${HOST_DATA_DIR:?}"/*
        log_info "Répertoire nettoyé"
    else
        log_info "Répertoire inexistant (OK)"
    fi

    log_info "=== PREPARE TERMINÉ ==="
    log_info "Prochaine étape : $0 deploy (ou migrate-postgresql-keycloak.sh prepare si les deux migrent)"
}

phase_deploy() {
    log_info "=== PHASE : DEPLOY (Helm upgrade → PG 18) ==="

    if ! command -v helm &>/dev/null; then
        log_error "helm non trouvé"
        exit 1
    fi

    log_warn "helm upgrade va redéployer TOUS les composants du chart (rhdemo + keycloak)."
    log_warn "Si la base keycloak doit aussi migrer, exécutez d'abord :"
    log_warn "  ./migrate-postgresql-keycloak.sh backup && ./migrate-postgresql-keycloak.sh prepare"
    read -p "Lancer helm upgrade ? (oui/non) " -r
    if [[ ! $REPLY == "oui" ]]; then
        log_info "Annulé"
        exit 0
    fi

    log_info "Déploiement Helm..."
    helm upgrade --install rhdemo "$HELM_DIR" \
        --namespace "$NAMESPACE" \
        --wait \
        --timeout 5m

    log_info "Attente du pod ${STS_NAME}-0..."
    kubectl wait --for=condition=ready pod "${STS_NAME}-0" -n "$NAMESPACE" --timeout=120s

    # Vérifier la version PG
    local pg_version
    pg_version=$(kubectl exec -n "$NAMESPACE" "${STS_NAME}-0" -- psql -U "$DB_USER" -d "$DB_NAME" -t -c "SHOW server_version;" 2>/dev/null | xargs)
    log_info "PostgreSQL déployé en version : ${pg_version}"

    log_info "=== DEPLOY TERMINÉ ==="
    log_info "Prochaine étape : $0 restore"
}

phase_restore() {
    log_info "=== PHASE : RESTORE du dump dans PG 18 ==="

    # Vérifier que le backup existe
    if [[ ! -f "$BACKUP_FILE" ]]; then
        log_error "Backup introuvable : ${BACKUP_FILE}"
        exit 1
    fi

    # Vérifier que le pod est ready
    if ! kubectl wait --for=condition=ready pod "${STS_NAME}-0" -n "$NAMESPACE" --timeout=30s &>/dev/null; then
        log_error "Pod ${STS_NAME}-0 non prêt. Exécutez d'abord : $0 deploy"
        exit 1
    fi

    # Copier le dump dans le pod
    log_info "Copie du dump vers le pod..."
    kubectl cp "$BACKUP_FILE" "$NAMESPACE/${STS_NAME}-0:/tmp/restore.sql"

    # Restaurer
    log_info "Restauration de la base ${DB_NAME}..."
    kubectl exec -n "$NAMESPACE" "${STS_NAME}-0" -- \
        psql -U "$DB_USER" -d "$DB_NAME" -f /tmp/restore.sql 2>&1 | tail -5

    # Nettoyage du fichier temporaire dans le pod
    kubectl exec -n "$NAMESPACE" "${STS_NAME}-0" -- rm -f /tmp/restore.sql

    # Vérification
    log_info "Vérification des données restaurées :"
    kubectl exec -n "$NAMESPACE" "${STS_NAME}-0" -- \
        psql -U "$DB_USER" -d "$DB_NAME" -c \
        "SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname;" 2>/dev/null || true

    log_info "=== RESTORE TERMINÉ ==="
    log_info "Le fichier de backup ${BACKUP_FILE} peut être supprimé manuellement."
}

phase_status() {
    log_info "=== STATUT PostgreSQL ${DB_NAME} ==="

    # Vérifier le StatefulSet
    if ! kubectl get statefulset -n "$NAMESPACE" "$STS_NAME" &>/dev/null; then
        log_warn "StatefulSet $STS_NAME introuvable"
        return
    fi

    # Vérifier que le pod est ready
    if ! kubectl wait --for=condition=ready pod "${STS_NAME}-0" -n "$NAMESPACE" --timeout=10s &>/dev/null; then
        log_warn "Pod ${STS_NAME}-0 non prêt"
        return
    fi

    # Version
    local pg_version
    pg_version=$(kubectl exec -n "$NAMESPACE" "${STS_NAME}-0" -- psql -U "$DB_USER" -d "$DB_NAME" -t -c "SHOW server_version;" 2>/dev/null | xargs)
    log_info "Version PostgreSQL : ${pg_version}"

    # PGDATA
    local pgdata
    pgdata=$(kubectl exec -n "$NAMESPACE" "${STS_NAME}-0" -- psql -U "$DB_USER" -d "$DB_NAME" -t -c "SHOW data_directory;" 2>/dev/null | xargs)
    log_info "Data directory : ${pgdata}"

    # Données
    log_info "Tables et enregistrements :"
    kubectl exec -n "$NAMESPACE" "${STS_NAME}-0" -- \
        psql -U "$DB_USER" -d "$DB_NAME" -c \
        "SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname;" 2>/dev/null || true

    # PV/PVC
    log_info "PVC :"
    kubectl get pvc -n "$NAMESPACE" "$PVC_NAME" 2>/dev/null || echo "  (introuvable)"
    log_info "PV :"
    kubectl get pv "$PV_NAME" 2>/dev/null || echo "  (introuvable)"

    # Backup local
    if [[ -f "$BACKUP_FILE" ]]; then
        local size
        size=$(du -h "$BACKUP_FILE" | cut -f1)
        log_info "Backup local : ${BACKUP_FILE} (${size})"
    else
        log_info "Backup local : aucun"
    fi
}

phase_full() {
    log_info "=== MIGRATION COMPLÈTE : ${DB_NAME} (PG 16 → PG 18) ==="
    log_warn "Cette procédure va :"
    log_warn "  1. Sauvegarder la base (pg_dump)"
    log_warn "  2. Supprimer le StatefulSet, PVC, PV et nettoyer les données"
    log_warn "  3. Redéployer via Helm (PG 18)"
    log_warn "  4. Restaurer le dump"
    echo ""
    read -p "Lancer la migration complète ? (oui/non) " -r
    if [[ ! $REPLY == "oui" ]]; then
        log_info "Annulé"
        exit 0
    fi

    phase_backup
    echo ""

    # Skip interactive prompt in full mode
    log_info "Suppression des ressources Kubernetes..."
    kubectl delete statefulset -n "$NAMESPACE" "$STS_NAME" --ignore-not-found=true
    sleep 3
    kubectl delete pvc -n "$NAMESPACE" "$PVC_NAME" --ignore-not-found=true
    kubectl delete pv "$PV_NAME" --ignore-not-found=true
    if [[ -d "$HOST_DATA_DIR" ]]; then
        rm -rf "${HOST_DATA_DIR:?}"/*
    fi
    log_info "Nettoyage terminé"
    echo ""

    phase_deploy
    echo ""

    phase_restore
    echo ""

    phase_status
    log_info "=== MIGRATION COMPLÈTE TERMINÉE ==="
}

show_usage() {
    echo "Usage: $0 [phase]"
    echo ""
    echo "Migration PostgreSQL 16 → 18 pour la base rhdemo (dump/restore)"
    echo ""
    echo "Phases disponibles :"
    echo "  backup   - Sauvegarde la base rhdemo (pg_dump)"
    echo "  prepare  - Supprime StatefulSet, PVC, PV et nettoie le host"
    echo "  deploy   - Redéploie via Helm (PG 18 vide)"
    echo "  restore  - Restaure le dump dans PostgreSQL 18"
    echo "  status   - Affiche l'état actuel"
    echo "  full     - Exécute toutes les phases"
    echo ""
    echo "Migration d'une seule base :"
    echo "  $0 full"
    echo ""
    echo "Migration des deux bases (rhdemo + keycloak) :"
    echo "  1. $0 backup"
    echo "  2. ./migrate-postgresql-keycloak.sh backup"
    echo "  3. $0 prepare"
    echo "  4. ./migrate-postgresql-keycloak.sh prepare"
    echo "  5. $0 deploy"
    echo "  6. $0 restore"
    echo "  7. ./migrate-postgresql-keycloak.sh restore"
}

# Main
case "${1:-help}" in
    backup)
        check_prerequisites
        phase_backup
        ;;
    prepare)
        check_prerequisites
        phase_prepare
        ;;
    deploy)
        check_prerequisites
        phase_deploy
        ;;
    restore)
        check_prerequisites
        phase_restore
        ;;
    status)
        check_prerequisites
        phase_status
        ;;
    full)
        check_prerequisites
        phase_full
        ;;
    *)
        show_usage
        ;;
esac
