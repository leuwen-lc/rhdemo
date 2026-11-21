#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# Installation ou mise à jour d'External Secrets Operator (ESO) et de son
# raccordement à OpenBao (docs/OPENBAO.md, ETUDE_OPENBAO.md étape 3)
# ═══════════════════════════════════════════════════════════════
# Idempotent. Lancé par init-stagingkub.sh, ou à la main avec le kubeconfig
# administrateur du cluster. Volontairement hors du motif install-or-upgrade-*.sh :
# la mise à jour en place automatique (Jenkinsfile-Stagingkub-Upgrade-Deploy) n'a
# pas les droits RBAC nécessaires (CRDs, ClusterRoleBinding auth-delegator) ; une
# montée de version proposée par Renovate s'applique en relançant ce script.
#
# Prérequis : OpenBao démarré, déverrouillé, configuré (configure-openbao.sh base
# puis kubernetes) et alimenté (openbao-setup.py stagingkub, et observability pour
# l'admin de Grafana dans loki-stack).
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGINGKUB_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
JENKINS_DOCKER_DIR="$(cd "${STAGINGKUB_DIR}/../jenkins-docker" && pwd)"
ESO_DIR="${STAGINGKUB_DIR}/external-secrets"
# shellcheck source=../../../jenkins-docker/openbao/lib.sh
source "${JENKINS_DOCKER_DIR}/openbao/lib.sh"

# renovate: datasource=helm depName=external-secrets registryUrl=https://charts.external-secrets.io
ESO_VERSION="2.15.0"
ESO_NAMESPACE="external-secrets"
APP_NAMESPACE="rhdemo-stagingkub"
OBS_NAMESPACE="loki-stack"
CA_FILE="${JENKINS_DOCKER_DIR}/certs/ca/root-ca.crt"
TARGET_SECRETS="rhdemo-db-secret keycloak-db-secret keycloak-admin-secret rhdemo-app-secrets"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

[ -f "${CA_FILE}" ] || { echo -e "${RED}❌ Autorité locale absente (${CA_FILE}) : infra/jenkins-docker/openbao/init-local-ca.sh ca${NC}"; exit 1; }

# ─── 1. OpenBao joignable depuis le cluster ───
echo -e "${YELLOW}▶ Raccordement d'OpenBao au réseau kind...${NC}"
openbao_connect_kind
OPENBAO_IP="$(openbao_kind_ip)"
echo -e "${GREEN}  ✓ OpenBao sur le réseau kind : ${OPENBAO_IP}${NC}"
state="$(openbao_seal_state)"
if [ "${state}" != "unsealed" ]; then
    echo -e "${YELLOW}  ⚠ OpenBao est « ${state} » : les ExternalSecret resteront en erreur jusqu'au déverrouillage (openbao/unseal.sh)${NC}"
fi
if ! openssl x509 -in "${JENKINS_DOCKER_DIR}/certs/openbao/openbao.crt" -noout -ext subjectAltName 2>/dev/null | grep -q "IP Address:${OPENBAO_IP}"; then
    echo -e "${RED}❌ Le certificat d'OpenBao ne contient pas ${OPENBAO_IP} : init-local-ca.sh openbao, puis redémarrer OpenBao${NC}"
    exit 1
fi

# ─── 2. Chart ESO ───
echo -e "${YELLOW}▶ External Secrets Operator ${ESO_VERSION}...${NC}"
helm repo add external-secrets https://charts.external-secrets.io --force-update >/dev/null 2>&1 || true
kubectl create namespace "${ESO_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
# Network Policies AVANT les pods : Default Deny dès le démarrage
sed "s/__OPENBAO_IP__/${OPENBAO_IP}/g" "${ESO_DIR}/networkpolicies.yaml" | kubectl apply -f -
helm upgrade --install external-secrets external-secrets/external-secrets \
    --version "${ESO_VERSION}" \
    --namespace "${ESO_NAMESPACE}" \
    --set installCRDs=true \
    --rollback-on-failure --wait --timeout 5m
echo -e "${GREEN}  ✓ ESO opérationnel${NC}"

# ─── 3. SecretStore et autorité locale ───
echo -e "${YELLOW}▶ SecretStore openbao (${APP_NAMESPACE})...${NC}"
kubectl create configmap openbao-ca -n "${APP_NAMESPACE}" --from-file=ca.crt="${CA_FILE}" \
    --dry-run=client -o yaml | kubectl apply -f -
sed "s/__OPENBAO_IP__/${OPENBAO_IP}/g" "${ESO_DIR}/secretstore.yaml" | kubectl apply -f -

# ─── 4. ExternalSecrets ───
# Les Secrets créés avant ESO (kubectl create secret) sont supprimés pour qu'ESO les
# recrée avec son ownerReference ; les pods en cours gardent leurs valeurs.
for s in ${TARGET_SECRETS}; do
    owner="$(kubectl get secret "${s}" -n "${APP_NAMESPACE}" -o jsonpath='{.metadata.ownerReferences[0].kind}' 2>/dev/null || true)"
    if kubectl get secret "${s}" -n "${APP_NAMESPACE}" >/dev/null 2>&1 && [ "${owner}" != "ExternalSecret" ]; then
        kubectl delete secret "${s}" -n "${APP_NAMESPACE}"
    fi
done
kubectl apply -f "${ESO_DIR}/externalsecrets.yaml"

echo -e "${YELLOW}▶ Attente de la synchronisation...${NC}"
failed=""
for s in ${TARGET_SECRETS}; do
    if kubectl wait externalsecret "${s}" -n "${APP_NAMESPACE}" --for=condition=Ready --timeout=90s >/dev/null 2>&1; then
        echo -e "${GREEN}  ✓ ${s}${NC}"
    else
        failed="${failed} ${s}"
        echo -e "${RED}  ✗ ${s} : kubectl describe externalsecret ${s} -n ${APP_NAMESPACE}${NC}"
    fi
done
if [ -n "${failed}" ]; then
    echo -e "${RED}❌ ExternalSecret non synchronisé(s) :${failed}${NC}"
    echo -e "${YELLOW}   OpenBao déverrouillé ? configure-openbao.sh kubernetes fait ? openbao-setup.py stagingkub fait ?${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Secrets applicatifs synchronisés depuis OpenBao${NC}"

# ─── 5. Observabilité : admin de Grafana (loki-stack) ───
# Namespace créé ici s'il manque (install-observability.sh vient après) ; même création
# simple que install-or-upgrade-grafana.sh. Un échec n'arrête pas l'installation :
# seul Grafana en dépend, et son script vérifie la présence du Secret.
echo -e "${YELLOW}▶ SecretStore openbao (${OBS_NAMESPACE}, admin de Grafana)...${NC}"
kubectl create namespace "${OBS_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl create configmap openbao-ca -n "${OBS_NAMESPACE}" --from-file=ca.crt="${CA_FILE}" \
    --dry-run=client -o yaml | kubectl apply -f -
sed "s/__OPENBAO_IP__/${OPENBAO_IP}/g" "${ESO_DIR}/observability.yaml" | kubectl apply -f -
if kubectl wait externalsecret grafana-admin -n "${OBS_NAMESPACE}" --for=condition=Ready --timeout=60s >/dev/null 2>&1; then
    echo -e "${GREEN}  ✓ grafana-admin${NC}"
else
    echo -e "${YELLOW}  ⚠ grafana-admin non synchronisé : kv/observability/grafana absent ? (rhDemo/scripts/openbao-setup.py observability)${NC}"
fi
