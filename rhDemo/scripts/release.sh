#!/bin/bash
# Script: release.sh
# Description: Automatise les étapes de release RHDemo (bump version, tag, retour SNAPSHOT)
# Usage:
#   ./release.sh pre-merge  <VERSION_RELEASE> <BRANCHE>
#   ./release.sh post-merge <VERSION_RELEASE> <VERSION_SNAPSHOT_SUIVANTE>
#
# Exemples:
#   ./release.sh pre-merge  1.1.9-RELEASE evolutions-post-1.1.8
#   ./release.sh post-merge 1.1.9-RELEASE 1.2.0-SNAPSHOT
#
# Workflow complet:
#   1. Sur la branche d'évolution :
#        ./release.sh pre-merge 1.1.9-RELEASE evolutions-post-1.1.8
#   2. Vérifier CI verte sur Codeberg, créer la PR, faire relire
#   3. Merger en squash signé en local (manuel — nécessite clé GPG/SSH locale) :
#        git fetch origin && git checkout master
#        git merge --squash origin/evolutions-post-1.1.8
#        git commit -S -m "release: merge evolutions-post-1.1.8"
#        git push origin master
#   4. Sur master après le merge :
#        ./release.sh post-merge 1.1.9-RELEASE 1.2.0-SNAPSHOT

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Couleurs
# ─────────────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

log()     { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERREUR]${NC} $1" >&2; exit 1; }
step()    { echo -e "\n${BOLD}══════════════════════════════════════════════${NC}"; \
            echo -e "${BOLD}  $1${NC}"; \
            echo -e "${BOLD}══════════════════════════════════════════════${NC}"; }

# ─────────────────────────────────────────────────────────────────────────────
# Chemins
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel)"
RHDEMO_DIR="${REPO_ROOT}/rhDemo"
MVNW="${RHDEMO_DIR}/mvnw"

POM_FILES=(
    "${REPO_ROOT}/rhDemo/pom.xml"
    "${REPO_ROOT}/rhDemoAPITestIHM/pom.xml"
    "${REPO_ROOT}/rhDemoInitKeycloak/pom.xml"
)

# ─────────────────────────────────────────────────────────────────────────────
# Fonctions utilitaires
# ─────────────────────────────────────────────────────────────────────────────

current_version() {
    # Utilise mvnw pour lire la version projet (fiable, ignore les versions des dépendances)
    "${MVNW}" -f "${RHDEMO_DIR}/pom.xml" help:evaluate \
        -Dexpression=project.version -q -DforceStdout 2>/dev/null
}

current_branch() {
    git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD
}

check_clean_tree() {
    if ! git -C "${REPO_ROOT}" diff --quiet || \
       ! git -C "${REPO_ROOT}" diff --cached --quiet; then
        error "Le répertoire de travail contient des modifications non commitées.\nCommitez ou stashez avant de continuer."
    fi
    success "Répertoire de travail propre"
}

bump_version() {
    local from="$1"
    local to="$2"
    log "Remplacement de la version : ${from} → ${to}"
    for pom in "${POM_FILES[@]}"; do
        [ -f "${pom}" ] || error "pom.xml introuvable : ${pom}"
        if grep -q "<version>${from}</version>" "${pom}"; then
            sed -i "s|<version>${from}</version>|<version>${to}</version>|" "${pom}"
            success "$(basename "$(dirname "${pom}")")/pom.xml → ${to}"
        else
            warn "Version '${from}' non trouvée dans $(basename "$(dirname "${pom}")")/pom.xml"
        fi
    done
}

commit_poms_and_push() {
    local message="$1"
    local branch="$2"
    log "Commit : \"${message}\""
    git -C "${REPO_ROOT}" add \
        rhDemo/pom.xml \
        rhDemoAPITestIHM/pom.xml \
        rhDemoInitKeycloak/pom.xml
    git -C "${REPO_ROOT}" commit -m "${message}"
    log "Push vers origin/${branch}..."
    git -C "${REPO_ROOT}" push origin "${branch}"
    success "Push terminé"
}

confirm_or_abort() {
    local message="$1"
    warn "${message}"
    read -r -p "   Continuer quand même ? [o/N] " reply
    [[ "${reply}" =~ ^[Oo]$ ]] || error "Annulé par l'utilisateur."
}

usage() {
    echo ""
    echo -e "${BOLD}Usage :${NC}"
    echo "  $0 pre-merge  <VERSION_RELEASE> <BRANCHE>"
    echo "  $0 post-merge <VERSION_RELEASE> <VERSION_SNAPSHOT_SUIVANTE>"
    echo ""
    echo -e "${BOLD}Exemples :${NC}"
    echo "  $0 pre-merge  1.1.9-RELEASE evolutions-post-1.1.8"
    echo "  $0 post-merge 1.1.9-RELEASE 1.2.0-SNAPSHOT"
    echo ""
    echo -e "${BOLD}Description :${NC}"
    echo "  pre-merge   Aligne la branche avec master, bumpe les pom en RELEASE, commit, push."
    echo "              À lancer avant de créer la PR sur Codeberg."
    echo ""
    echo "  post-merge  À lancer sur master après le squash merge signé."
    echo "              Crée le tag annoté, le pousse, bumpe les pom en SNAPSHOT, commit, push."
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# COMMANDE : pre-merge
# ─────────────────────────────────────────────────────────────────────────────
cmd_pre_merge() {
    local release_version="${1:-}"
    local branch="${2:-}"

    if [ -z "${release_version}" ] || [ -z "${branch}" ]; then
        echo -e "${RED}[ERREUR]${NC} Arguments manquants." >&2
        usage; exit 1
    fi
    [[ "${release_version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+-RELEASE$ ]] || \
        error "La version release doit être au format X.Y.Z-RELEASE (ex: 1.1.9-RELEASE)"

    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   PRÉ-MERGE : préparation de la PR release   ${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    log "Version release : ${BOLD}${release_version}${NC}"
    log "Branche         : ${BOLD}${branch}${NC}"

    step "1/5 — Vérifications préalables"
    check_clean_tree

    local current_branch_name
    current_branch_name="$(current_branch)"
    if [ "${current_branch_name}" != "${branch}" ]; then
        warn "Branche courante : '${current_branch_name}' (attendue : '${branch}')"
        read -r -p "   Basculer sur '${branch}' ? [o/N] " reply
        [[ "${reply}" =~ ^[Oo]$ ]] || error "Annulé."
        git -C "${REPO_ROOT}" checkout "${branch}"
        success "Basculé sur '${branch}'"
    else
        success "Branche courante : ${branch}"
    fi

    local snapshot_version
    snapshot_version="$(current_version)"
    [[ "${snapshot_version}" =~ -SNAPSHOT$ ]] || \
        error "La version courante '${snapshot_version}' n'est pas une SNAPSHOT. Vérifiez les pom.xml."

    # Vérifier la cohérence : 1.1.9-SNAPSHOT → 1.1.9-RELEASE
    local expected_snapshot="${release_version/-RELEASE/-SNAPSHOT}"
    if [ "${snapshot_version}" != "${expected_snapshot}" ]; then
        confirm_or_abort "Version pom.xml '${snapshot_version}' ≠ attendue '${expected_snapshot}'. La numérotation est-elle correcte ?"
    else
        success "Version pom.xml : ${snapshot_version}"
    fi

    step "2/5 — Mise à jour de la branche"
    log "Pull --rebase de origin/${branch}..."
    git -C "${REPO_ROOT}" pull --rebase origin "${branch}"
    success "Branche à jour avec origin/${branch}"

    step "3/5 — Alignement avec master"
    log "Fetch origin..."
    git -C "${REPO_ROOT}" fetch origin
    log "Merge de origin/master dans ${branch}..."
    if ! git -C "${REPO_ROOT}" merge origin/master --no-edit; then
        echo ""
        warn "Des conflits sont présents. Résolvez-les puis relancez cette étape manuellement :"
        echo "   git add <fichiers_résolus>"
        echo "   git merge --continue"
        exit 1
    fi
    success "Aligné avec origin/master"

    step "4/5 — Bump de version : ${snapshot_version} → ${release_version}"
    bump_version "${snapshot_version}" "${release_version}"

    step "5/5 — Commit et push"
    commit_poms_and_push "chore(release): passage à la version ${release_version}" "${branch}"

    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   PRÉ-MERGE TERMINÉ ✅                       ${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BOLD}Étapes suivantes (manuelles) :${NC}"
    echo "  1. Attendre que la CI Jenkins soit verte sur Codeberg"
    echo "  2. Ouvrir la PR : ${branch} → master (si pas déjà fait)"
    echo "  3. Faire relire la PR, obtenir l'approbation"
    echo "  4. Merger en squash signé en local :"
    echo ""
    echo -e "     ${BLUE}git fetch origin${NC}"
    echo -e "     ${BLUE}git checkout master${NC}"
    echo -e "     ${BLUE}git merge --squash origin/${branch}${NC}"
    echo -e "     ${BLUE}git commit -S -m \"release: merge ${branch}\"${NC}"
    echo -e "     ${BLUE}git push origin master${NC}"
    echo ""
    echo "  5. Lancer la phase post-merge :"
    echo -e "     ${BLUE}$0 post-merge ${release_version} <PROCHAINE_VERSION_SNAPSHOT>${NC}"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# COMMANDE : post-merge
# ─────────────────────────────────────────────────────────────────────────────
cmd_post_merge() {
    local release_version="${1:-}"
    local next_snapshot="${2:-}"

    if [ -z "${release_version}" ] || [ -z "${next_snapshot}" ]; then
        echo -e "${RED}[ERREUR]${NC} Arguments manquants." >&2
        usage; exit 1
    fi
    [[ "${release_version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+-RELEASE$ ]] || \
        error "La version release doit être au format X.Y.Z-RELEASE (ex: 1.1.9-RELEASE)"
    [[ "${next_snapshot}" =~ ^[0-9]+\.[0-9]+\.[0-9]+-SNAPSHOT$ ]] || \
        error "La version SNAPSHOT doit être au format X.Y.Z-SNAPSHOT (ex: 1.2.0-SNAPSHOT)"

    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   POST-MERGE : tag release + retour SNAPSHOT ${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    log "Version release   : ${BOLD}${release_version}${NC}"
    log "Prochain SNAPSHOT : ${BOLD}${next_snapshot}${NC}"

    step "1/5 — Vérifications préalables"
    check_clean_tree

    local current_branch_name
    current_branch_name="$(current_branch)"
    if [ "${current_branch_name}" != "master" ]; then
        warn "Branche courante : '${current_branch_name}' (attendue : 'master')"
        read -r -p "   Basculer sur 'master' ? [o/N] " reply
        [[ "${reply}" =~ ^[Oo]$ ]] || error "Annulé."
        git -C "${REPO_ROOT}" checkout master
        success "Basculé sur master"
    else
        success "Branche courante : master"
    fi

    step "2/5 — Mise à jour de master"
    log "Pull de origin/master..."
    git -C "${REPO_ROOT}" pull origin master
    success "master local à jour"

    local pom_version
    pom_version="$(current_version)"
    if [ "${pom_version}" != "${release_version}" ]; then
        error "Version dans pom.xml : '${pom_version}', attendue : '${release_version}'.\nLe squash merge a-t-il bien été pushé sur origin/master ?"
    fi
    success "Version pom.xml confirmée : ${pom_version}"

    step "3/5 — Création du tag ${release_version}"
    if git -C "${REPO_ROOT}" tag -l "${release_version}" | grep -q "${release_version}"; then
        confirm_or_abort "Le tag '${release_version}' existe déjà localement."
    fi
    git -C "${REPO_ROOT}" tag -a "${release_version}" -m "Release ${release_version}"
    success "Tag annoté créé : ${release_version}"

    log "Push du tag vers origin..."
    git -C "${REPO_ROOT}" push origin "${release_version}"
    success "Tag '${release_version}' publié sur Codeberg"

    step "4/5 — Retour en SNAPSHOT : ${release_version} → ${next_snapshot}"
    bump_version "${release_version}" "${next_snapshot}"

    step "5/5 — Commit et push"
    commit_poms_and_push "chore: retour à ${next_snapshot} après ${release_version}" "master"

    local evolution_branch="evolutions-post-${release_version/-RELEASE/}"

    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   POST-MERGE TERMINÉ ✅                      ${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BOLD}Récapitulatif :${NC}"
    echo "  ✅ Tag ${release_version} créé et publié sur Codeberg"
    echo "  ✅ master repassé en ${next_snapshot}"
    echo ""
    echo -e "${BOLD}Prochaine étape — créer la branche d'évolution suivante :${NC}"
    echo ""
    echo -e "     ${BLUE}git checkout -b ${evolution_branch}${NC}"
    echo -e "     ${BLUE}git push origin ${evolution_branch}${NC}"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────
COMMAND="${1:-}"
shift || true

case "${COMMAND}" in
    pre-merge)  cmd_pre_merge  "$@" ;;
    post-merge) cmd_post_merge "$@" ;;
    help|--help|-h|"") usage ;;
    *) error "Commande inconnue : '${COMMAND}'. Utilisez 'pre-merge', 'post-merge' ou 'help'." ;;
esac
