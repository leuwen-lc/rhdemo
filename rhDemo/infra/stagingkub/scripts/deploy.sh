#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Script de déploiement de RHDemo sur stagingkub (KinD)
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGINGKUB_DIR="$(dirname "$SCRIPT_DIR")"
HELM_CHART_DIR="$STAGINGKUB_DIR/helm/rhdemo"

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Paramètres
APP_VERSION="${1:-1.1.0-SNAPSHOT}"
RELEASE_NAME="${2:-rhdemo}"
NAMESPACE="${3:-rhdemo-staging}"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Déploiement de RHDemo sur stagingkub${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Version de l'application : ${APP_VERSION}${NC}"
echo -e "${YELLOW}Release name : ${RELEASE_NAME}${NC}"
echo -e "${YELLOW}Namespace : ${NAMESPACE}${NC}"
echo ""

# Vérifier que le cluster est accessible
echo -e "${YELLOW}▶ Vérification du cluster Kubernetes...${NC}"
if ! kubectl cluster-info --context kind-rhdemo &> /dev/null; then
    echo -e "${RED}❌ Cluster KinD 'rhdemo' non accessible${NC}"
    echo -e "${YELLOW}Veuillez exécuter : ./init-stagingkub.sh${NC}"
    exit 1
fi
kubectl config use-context kind-rhdemo
echo -e "${GREEN}✅ Cluster accessible${NC}"

# Vérifier que l'image Docker existe localement
echo -e "${YELLOW}▶ Vérification de l'image Docker rhdemo-api:${APP_VERSION}...${NC}"
if ! docker image inspect rhdemo-api:${APP_VERSION} &> /dev/null; then
    echo -e "${RED}❌ Image Docker rhdemo-api:${APP_VERSION} non trouvée${NC}"
    echo -e "${YELLOW}Veuillez construire l'image d'abord${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Image Docker trouvée${NC}"

# Charger l'image dans KinD
echo -e "${YELLOW}▶ Chargement de l'image dans KinD...${NC}"
kind load docker-image rhdemo-api:${APP_VERSION} --name rhdemo
echo -e "${GREEN}✅ Image chargée dans KinD${NC}"

# Déployer ou mettre à jour avec Helm
echo -e "${YELLOW}▶ Déploiement avec Helm...${NC}"
helm upgrade --install ${RELEASE_NAME} ${HELM_CHART_DIR} \
  --namespace ${NAMESPACE} \
  --create-namespace \
  --set rhdemo.image.tag=${APP_VERSION} \
  --wait \
  --timeout 10m

echo -e "${GREEN}✅ Déploiement réussi${NC}"

# Afficher le statut
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ RHDemo déployé avec succès sur stagingkub${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Statut des pods :${NC}"
kubectl get pods -n ${NAMESPACE}
echo ""
echo -e "${YELLOW}Statut des services :${NC}"
kubectl get svc -n ${NAMESPACE}
echo ""
echo -e "${YELLOW}Statut de l'ingress :${NC}"
kubectl get ingress -n ${NAMESPACE}
echo ""
echo -e "${YELLOW}URLs d'accès :${NC}"
echo -e "  Application : ${BLUE}https://rhdemo.staging.local${NC}"
echo -e "  Keycloak : ${BLUE}https://keycloak.staging.local${NC}"
echo ""
echo -e "${YELLOW}Pour voir les logs de l'application :${NC}"
echo -e "  ${BLUE}kubectl logs -f -n ${NAMESPACE} -l app=rhdemo-app${NC}"
echo ""
