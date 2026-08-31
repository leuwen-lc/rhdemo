#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Vendoring des CRDs Gateway API (channel standard) pour une version
# de NGINX Gateway Fabric donnée.
# ═══════════════════════════════════════════════════════════════
# Remplace la récupération en direct depuis GitHub à chaque exécution
# d'install-or-upgrade-ngf.sh : le manifeste est figé et commité dans
# le dépôt une fois pour toutes à chaque bump de NGF_VERSION.
#
# Usage : ./vendor-gateway-api-crds.sh <NGF_VERSION>
# Exemple : ./vendor-gateway-api-crds.sh 2.6.0
#
# À exécuter et committer dans la même PR que le bump de NGF_VERSION
# dans scripts/components/install-or-upgrade-ngf.sh.
# ═══════════════════════════════════════════════════════════════

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

NGF_VERSION="${1:?Usage: ./vendor-gateway-api-crds.sh <NGF_VERSION> (ex: 2.6.0)}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGINGKUB_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${STAGINGKUB_DIR}/gateway-api-crds/v${NGF_VERSION}"
OUTPUT_FILE="${OUTPUT_DIR}/crds.yaml"

echo -e "${YELLOW}▶ Vendoring des CRDs Gateway API pour NGF v${NGF_VERSION}...${NC}"

mkdir -p "${OUTPUT_DIR}"

kubectl kustomize "https://github.com/nginx/nginx-gateway-fabric/config/crd/gateway-api/standard?ref=v${NGF_VERSION}" > "${OUTPUT_FILE}"

if [ ! -s "${OUTPUT_FILE}" ]; then
    echo -e "${RED}❌ Échec de récupération du manifeste (fichier vide)${NC}"
    rm -f "${OUTPUT_FILE}"
    exit 1
fi

echo -e "${GREEN}✅ Manifeste vendoré : ${OUTPUT_FILE}${NC}"
echo -e "${YELLOW}   N'oubliez pas de committer ce fichier avec le bump de NGF_VERSION.${NC}"
