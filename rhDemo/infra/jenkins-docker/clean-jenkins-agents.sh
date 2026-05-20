#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# NETTOYAGE DES AGENTS JENKINS ÉPHÉMÈRES ZOMBIES
#
# Usage: ./clean-jenkins-agents.sh [OPTIONS]
#
# Options:
#   --dry-run    Affiche les containers qui seraient supprimés sans les supprimer
#   --help       Affiche cette aide
#
# Ce script supprime les containers basés sur rhdemo-jenkins-agent:latest
# qui sont restés en vie (zombie) après un build annulé ou un timeout.
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

AGENT_IMAGE="rhdemo-jenkins-agent:latest"
DRY_RUN=false

# ───────────────────────────────────────────────────────────────────
# Parsing des arguments
# ───────────────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --help)
      head -16 "$0" | grep -E "^#" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Option inconnue : $arg" >&2
      exit 1
      ;;
  esac
done

# ───────────────────────────────────────────────────────────────────
# Détection des containers zombie
# ───────────────────────────────────────────────────────────────────
echo "🔍 Recherche des agents zombie (image: ${AGENT_IMAGE})..."

ZOMBIE_IDS=$(docker ps -q --filter "ancestor=${AGENT_IMAGE}" 2>/dev/null || true)
ZOMBIE_COUNT=$(echo "${ZOMBIE_IDS}" | grep -c . 2>/dev/null || echo 0)

if [[ -z "${ZOMBIE_IDS}" ]]; then
  echo "✅ Aucun agent zombie trouvé."
  exit 0
fi

echo ""
echo "Agents trouvés :"
docker ps --filter "ancestor=${AGENT_IMAGE}" --format "  • {{.Names}} ({{.ID}})  [depuis {{.RunningFor}}]"
echo ""

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "⚠️  Mode dry-run : aucune suppression effectuée."
  exit 0
fi

# ───────────────────────────────────────────────────────────────────
# Suppression
# ───────────────────────────────────────────────────────────────────
echo "🗑️  Suppression de ${ZOMBIE_COUNT} container(s)..."

while IFS= read -r container_id; do
  [[ -z "${container_id}" ]] && continue
  CONTAINER_NAME=$(docker inspect --format '{{.Name}}' "${container_id}" | sed 's|^/||')
  if docker rm -f "${container_id}" > /dev/null 2>&1; then
    echo "  ✓ Supprimé : ${CONTAINER_NAME} (${container_id})"
  else
    echo "  ✗ Échec suppression : ${CONTAINER_NAME} (${container_id})" >&2
  fi
done <<< "${ZOMBIE_IDS}"

echo ""
echo "✅ Nettoyage terminé."
echo ""
echo "💡 Si un build Jenkins est bloqué ('Waiting for next available executor'),"
echo "   relancez-le depuis l'interface Jenkins."
