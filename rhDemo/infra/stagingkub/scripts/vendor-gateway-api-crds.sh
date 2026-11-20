#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# Vendoring des CRDs Gateway API (channel standard) pour une version
# de NGINX Gateway Fabric donnée.
# ═══════════════════════════════════════════════════════════════
# Le manifeste est figé et commité dans le dépôt à chaque montée de
# NGF_VERSION, plutôt que récupéré en direct depuis GitHub à chaque
# exécution d'install-or-upgrade-ngf.sh.
#
# Usage : ./vendor-gateway-api-crds.sh <NGF_VERSION>
# Exemple : ./vendor-gateway-api-crds.sh 2.8.0
#
# Exécuté automatiquement par Renovate (postUpgradeTasks de renovate.json,
# commande autorisée par RENOVATE_ALLOWED_COMMANDS dans Jenkinsfile-Renovate)
# dans la PR qui monte NGF_VERSION. Lancement manuel possible, depuis
# n'importe quel répertoire.
#
# Méthode : NGF épingle la version de Gateway API dans
# config/crd/gateway-api/standard/kustomization.yaml (référence au dépôt
# kubernetes-sigs/gateway-api). On lit cette version, puis on télécharge
# l'asset standard-install.yaml de la release Gateway API correspondante :
# mêmes objets que le `kubectl kustomize` de ce fichier (vérifié le
# 2026-11-06 pour NGF 2.6.0 et 2.8.0, Gateway API v1.5.1 et v1.6.3), sans
# dépendre de kubectl, absent de l'image Renovate. Téléchargement par curl,
# ou par node s'il manque. Les manifestes des autres versions de NGF sont
# supprimés.
# ═══════════════════════════════════════════════════════════════

NGF_VERSION="${1:?Usage: ./vendor-gateway-api-crds.sh <NGF_VERSION> (ex: 2.8.0)}"
[[ "$NGF_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "❌ Version NGF invalide : ${NGF_VERSION}" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRDS_ROOT="$(dirname "$SCRIPT_DIR")/gateway-api-crds"
OUTPUT_DIR="${CRDS_ROOT}/v${NGF_VERSION}"
OUTPUT_FILE="${OUTPUT_DIR}/crds.yaml"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Téléchargement HTTPS avec échec sur code HTTP d'erreur ; redirections suivies
# (les assets de release GitHub redirigent vers un CDN).
fetch() {
    local url="$1" dest="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --max-time 120 -o "$dest" "$url"
    else
        node -e '
            const [url, dest] = process.argv.slice(1);
            fetch(url, { signal: AbortSignal.timeout(120000) })
              .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status} sur ${url}`); return r.text(); })
              .then(t => require("fs").writeFileSync(dest, t))
              .catch(e => { console.error(e.message); process.exit(1); });
        ' "$url" "$dest"
    fi
}

echo "▶ Vendoring des CRDs Gateway API pour NGF v${NGF_VERSION}..."

fetch "https://raw.githubusercontent.com/nginx/nginx-gateway-fabric/v${NGF_VERSION}/config/crd/gateway-api/standard/kustomization.yaml" \
      "${TMP_DIR}/kustomization.yaml"

# Une seule ressource attendue, au format connu : sinon NGF a changé sa façon
# d'embarquer Gateway API et la méthode doit être revue, pas devinée.
mapfile -t RESOURCES < <(grep -E '^[[:space:]]*-[[:space:]]' "${TMP_DIR}/kustomization.yaml")
GW_REGEX='^[[:space:]]*-[[:space:]]+https://github\.com/kubernetes-sigs/gateway-api/config/crd\?(timeout=[0-9]+&)?ref=(v[0-9]+\.[0-9]+\.[0-9]+)[[:space:]]*$'
if [ "${#RESOURCES[@]}" -ne 1 ] || ! [[ "${RESOURCES[0]}" =~ $GW_REGEX ]]; then
    echo "❌ kustomization.yaml de NGF v${NGF_VERSION} au format inattendu :" >&2
    cat "${TMP_DIR}/kustomization.yaml" >&2
    exit 1
fi
GW_VERSION="${BASH_REMATCH[2]}"
echo "  Gateway API épinglée par NGF : ${GW_VERSION}"

fetch "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GW_VERSION}/standard-install.yaml" \
      "${TMP_DIR}/crds.yaml"

# Contrôles de cohérence : des CRDs, chacune annotée de la version attendue.
# (Les ValidatingAdmissionPolicy du même fichier portent en amont une version
# "-dev" selon les versions : on exige au moins une annotation exacte par CRD.)
CRD_COUNT=$(grep -c '^kind: CustomResourceDefinition$' "${TMP_DIR}/crds.yaml" || true)
OK_BUNDLE=$(grep -c "gateway.networking.k8s.io/bundle-version: ${GW_VERSION}$" "${TMP_DIR}/crds.yaml" || true)
if [ "${CRD_COUNT}" -eq 0 ] || [ "${OK_BUNDLE}" -lt "${CRD_COUNT}" ]; then
    echo "❌ Manifeste inattendu : ${CRD_COUNT} CRD, ${OK_BUNDLE} annotée(s) bundle-version ${GW_VERSION}" >&2
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"
mv "${TMP_DIR}/crds.yaml" "${OUTPUT_FILE}"

# Seul le manifeste de la version courante sert (install-or-upgrade-ngf.sh).
find "${CRDS_ROOT}" -mindepth 1 -maxdepth 1 -type d -name 'v*' ! -name "v${NGF_VERSION}" -exec rm -rf {} +

echo "✅ Manifeste vendoré : ${OUTPUT_FILE} (${CRD_COUNT} CRD, Gateway API ${GW_VERSION})"
