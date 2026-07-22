#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Installation ou mise à jour en place de NGINX Gateway Fabric (NGF)
# ═══════════════════════════════════════════════════════════════
# Idempotent (helm upgrade --install). Les CRDs Gateway API sont
# vendorées dans le dépôt (cf. vendor-gateway-api-crds.sh) plutôt que
# récupérées en direct depuis GitHub à chaque exécution.
#
# Piège Helm couvert explicitement : le contenu du dossier crds/ d'un
# chart n'est jamais mis à jour par `helm upgrade` (limitation connue
# de Helm) — les CRDs propres à NGF (gateway.nginx.org) sont donc
# extraites du chart et appliquées explicitement, avant la release.
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGINGKUB_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# renovate: datasource=helm depName=nginx-gateway-fabric registryUrl=oci://ghcr.io/nginx/charts
NGF_VERSION="2.6.0"

NGF_NAMESPACE="nginx-gateway"

# Mode validation (HELM_DRY_RUN=true) : utilisé par la boucle de validation
# pré-merge de Jenkinsfile-Renovate — aucune mutation du cluster, y compris
# pour les CRDs (kubectl --dry-run=server) et le patch de NodePort.
HELM_DRY_RUN="${HELM_DRY_RUN:-false}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}▶ Installation/mise à jour de NGINX Gateway Fabric ${NGF_VERSION}...${NC}"

if [ "$HELM_DRY_RUN" = "true" ]; then
    KUBECTL_APPLY_ARGS="--server-side --dry-run=server --force-conflicts"
    HELM_MODE_ARGS="--dry-run=server"
else
    KUBECTL_APPLY_ARGS="--server-side --force-conflicts"
    HELM_MODE_ARGS="--atomic --wait --timeout 5m"
fi

# ─── 1. CRDs Gateway API (vendorées) ───
CRD_MANIFEST="${STAGINGKUB_DIR}/gateway-api-crds/v${NGF_VERSION}/crds.yaml"
if [ ! -f "${CRD_MANIFEST}" ]; then
    echo -e "${RED}❌ Manifeste de CRDs vendoré introuvable : ${CRD_MANIFEST}${NC}"
    echo -e "${YELLOW}   Exécutez d'abord : ./vendor-gateway-api-crds.sh ${NGF_VERSION}${NC}"
    exit 1
fi
kubectl apply ${KUBECTL_APPLY_ARGS} -f "${CRD_MANIFEST}"
echo -e "${GREEN}  ✓ CRDs Gateway API à jour (manifeste vendoré ${CRD_MANIFEST})${NC}"

# ─── 2. CRDs propres à NGF (gateway.nginx.org), extraites du chart ───
NGF_CRDS_TMP="$(mktemp)"
if helm show crds oci://ghcr.io/nginx/charts/nginx-gateway-fabric --version "${NGF_VERSION}" > "${NGF_CRDS_TMP}" 2>/dev/null && [ -s "${NGF_CRDS_TMP}" ]; then
    kubectl apply ${KUBECTL_APPLY_ARGS} -f "${NGF_CRDS_TMP}"
    echo -e "${GREEN}  ✓ CRDs NGF (gateway.nginx.org) à jour${NC}"
else
    echo -e "${YELLOW}  ⚠ Aucune CRD embarquée trouvée dans le chart NGF (à vérifier si inattendu)${NC}"
fi
rm -f "${NGF_CRDS_TMP}"

# ─── 3. Release Helm NGF (ou validation dry-run=server) ───
helm upgrade --install ngf oci://ghcr.io/nginx/charts/nginx-gateway-fabric \
    --version "${NGF_VERSION}" \
    --create-namespace \
    --namespace "${NGF_NAMESPACE}" \
    --set nginx.service.type=NodePort \
    --set nginx.service.externalTrafficPolicy=Local \
    --set 'nginx.service.ports[0].port=80' \
    --set 'nginx.service.ports[0].nodePort=31792' \
    --set 'nginx.service.ports[1].port=443' \
    --set 'nginx.service.ports[1].nodePort=32616' \
    ${HELM_MODE_ARGS}

if [ "$HELM_DRY_RUN" = "true" ]; then
    echo -e "${GREEN}✅ Validation dry-run NGINX Gateway Fabric ${NGF_VERSION} OK (aucune mutation du cluster)${NC}"
    exit 0
fi

kubectl rollout status deployment -n "${NGF_NAMESPACE}" -l app.kubernetes.io/name=nginx-gateway-fabric --timeout=180s 2>/dev/null || true

# ─── 4. Re-patch du NodePort HTTPS si le Gateway partagé existe déjà ───
# (no-op au tout premier install, avant la création du Gateway partagé
# par init-stagingkub.sh — le patch est refait à cette étape-là aussi)
CURRENT_NODEPORT=$(kubectl get svc shared-gateway-nginx -n "${NGF_NAMESPACE}" -o jsonpath='{.spec.ports[?(@.port==443)].nodePort}' 2>/dev/null || true)
if [ -n "${CURRENT_NODEPORT}" ] && [ "${CURRENT_NODEPORT}" != "32616" ]; then
    kubectl patch svc shared-gateway-nginx -n "${NGF_NAMESPACE}" --type='json' \
        -p='[{"op":"replace","path":"/spec/ports/0/nodePort","value":32616}]'
    echo -e "${GREEN}  ✓ NodePort HTTPS re-patché (${CURRENT_NODEPORT} → 32616)${NC}"
fi

echo -e "${GREEN}✅ NGINX Gateway Fabric ${NGF_VERSION} opérationnel${NC}"
