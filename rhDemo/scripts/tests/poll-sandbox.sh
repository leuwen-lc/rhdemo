#!/usr/bin/env bash
#
# Bac à sable du poller : exécute le VRAI fixcve-auto-poll.sh contre un faux Jenkins et un dépôt
# « origin » local (aucun push vers la forge, aucun credential réel). Réseau requis (OSV, npm,
# Maven Central) : c'est un essai d'intégration, pas un test unitaire.
#
# Usage : poll-sandbox.sh <dossier-jenkins> <commit-de-départ> <build-en-échec> [build-dernier-traité]
#   <dossier-jenkins> : 913-owasp.html, 913-wfapi.json... (rapports réels téléchargés de Jenkins)
#   Le dépôt de départ = <commit-de-départ> + les scripts fixcve de la copie de travail courante.
# Variables : PHASE_B=SUCCESS (défaut) | FAILURE (build de validation rouge, mêmes rapports : rollback
#             attendu) ; OFFLINE=1 (OSV/npm/Maven injoignables via un proxy mort : blocage transitoire).
# Résultat : état, journal et commits du bac à sable affichés ; dossier conservé (chemin affiché).
set -euo pipefail

JENKINS_FILES="$(cd "$1" && pwd)"
BASE_COMMIT="$2"
FAILED_BUILD="$3"
LAST_PROCESSED="${4:-$((FAILED_BUILD - 1))}"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN_REPO="$(cd "${SCRIPTS_DIR}/../.." && pwd)"
BRANCH="$(git -C "${MAIN_REPO}" rev-parse --abbrev-ref HEAD)"
SB="$(mktemp -d -t fixcve-sandbox-XXXX)"
PORT=$((20000 + RANDOM % 10000))

echo "Bac à sable : ${SB}"
git clone -q --bare "${MAIN_REPO}" "${SB}/origin.git"
git clone -q "${SB}/origin.git" "${SB}/seed"
git -C "${SB}/seed" checkout -q -B "${BRANCH}" "${BASE_COMMIT}"
rm -rf "${SB}/seed/rhDemo/scripts"
cp -r "${SCRIPTS_DIR}" "${SB}/seed/rhDemo/scripts"
find "${SB}/seed/rhDemo/scripts" -name __pycache__ -prune -exec rm -rf {} +
cp "${MAIN_REPO}/rhDemo/.gitignore" "${SB}/seed/rhDemo/.gitignore"
git -C "${SB}/seed" add -A
git -C "${SB}/seed" -c user.name=sandbox -c user.email=sandbox@local commit -q -m "test: scripts fixcve courants"
git -C "${SB}/seed" push -q -f origin "${BRANCH}"
git clone -q -b "${BRANCH}" "${SB}/origin.git" "${SB}/clone"
git clone -q -b "${BRANCH}" "${SB}/origin.git" "${SB}/main"
cp -r "${MAIN_REPO}/rhDemo/frontend/node" "${SB}/clone/rhDemo/frontend/node"

mkdir -p "${SB}/state"
# Épinglage de confiance : approbation des scripts du clone (équivalent de fixcve-install.sh --trust).
{ echo "# commit sandbox"; (cd "${SB}/clone" && find rhDemo/scripts -path '*/tests' -prune -o -path '*/__pycache__' -prune -o -type f \
    \( -name 'fixcve-*' -o -path 'rhDemo/scripts/fixcve_lib/*' \) -print | LC_ALL=C sort | xargs sha256sum); } > "${SB}/state/trusted.sha256"
echo '{"jenkins":{"user":"u","token":"t"},"codeberg":{"user":"u","token":"t"}}' > "${SB}/state/creds.json"
touch "${SB}/state/credentials.sops.yaml"
jq -n --argjson n "${LAST_PROCESSED}" \
  '{last_processed_build:$n,status:"idle",pending:null,consecutive_rollbacks:0,consecutive_prepush_failures:0,blocked_confirmed:null,no_action_confirmed:null,consecutive_no_action_pushes:0}' \
  > "${SB}/state/state.json"
cp -r "${JENKINS_FILES}/." "${SB}/jenkins/" 2>/dev/null || { mkdir -p "${SB}/jenkins"; cp -r "${JENKINS_FILES}/." "${SB}/jenkins/"; }
[ -f "${SB}/jenkins/builds.json" ] || jq -n --arg b "${FAILED_BUILD}" \
  '{last: ($b|tonumber), builds: {($b): {result:"FAILURE", wfapi:($b+"-wfapi.json"), owasp:($b+"-owasp.html"), sha:null}}}' \
  > "${SB}/jenkins/builds.json"

python3 -I "${SCRIPTS_DIR}/tests/fake_jenkins.py" "${SB}/jenkins" "${PORT}" &
JENKINS_PID=$!
trap 'kill ${JENKINS_PID} 2>/dev/null || true' EXIT
sleep 1

run_poll() {
  local proxy=()
  [ "${OFFLINE:-0}" == "1" ] && proxy=(https_proxy=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 npm_config_offline=true)
  env "${proxy[@]}" FIXCVE_JENKINS_URL="http://127.0.0.1:${PORT}" FIXCVE_REPO_DIR="${SB}/clone" FIXCVE_REPO_DIR_MAIN="${SB}/main" \
  FIXCVE_STATE_DIR="${SB}/state" FIXCVE_TEST_CREDS_FILE="${SB}/state/creds.json" \
    bash "${SB}/clone/rhDemo/scripts/fixcve-auto-poll.sh" 2>&1 | sed 's/^/  poll | /'
}

echo "=== Cycle 1 (phase A, build #${FAILED_BUILD})"
run_poll
echo "=== État"
jq -c . "${SB}/state/state.json"
echo "=== Commits poussés sur l'origin du bac à sable"
git -C "${SB}/origin.git" log --format='  %h %an : %s' -5 "${BRANCH}"
echo "=== Fichiers du dernier commit"
git -C "${SB}/origin.git" show --stat --format= "${BRANCH}" | sed 's/^/  /'

if [ "$(jq -r .status "${SB}/state/state.json")" == "pending_validation" ]; then
  FIX_SHA="$(jq -r .pending.fix_commit_sha "${SB}/state/state.json")"
  NEXT=$((FAILED_BUILD + 1))
  BUILD_SHA="$(git -C "${SB}/origin.git" rev-parse "${BRANCH}")"
  jq --arg b "${NEXT}" --arg sha "${BUILD_SHA}" --arg r "${PHASE_B:-SUCCESS}" --arg f "${FAILED_BUILD}" \
    '.last = ($b|tonumber) | .builds[$b] = (.builds[$f] + {result:$r, sha:$sha})' \
    "${SB}/jenkins/builds.json" > "${SB}/jenkins/builds.tmp" && mv "${SB}/jenkins/builds.tmp" "${SB}/jenkins/builds.json"
  echo "=== Cycle 2 (phase B, build #${NEXT} ${PHASE_B:-SUCCESS} sur le correctif)"
  run_poll
  jq -c '{status,last_processed_build,pending}' "${SB}/state/state.json"
  git -C "${SB}/origin.git" log --format='  %h %s' -4 "${BRANCH}"
fi
echo "Bac à sable conservé : ${SB}"
