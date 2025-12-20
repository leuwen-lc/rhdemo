#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Script de nettoyage complet du cluster KinD stagingkub
# Supprime le cluster et toutes les données pour repartir sur du propre
# ═══════════════════════════════════════════════════════════════

# Couleurs pour les logs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Nettoyage complet du cluster KinD stagingkub${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Vérifier que KinD est installé
if ! command -v kind &> /dev/null; then
    echo -e "${RED}❌ KinD n'est pas installé.${NC}"
    exit 1
fi

# Supprimer le cluster KinD s'il existe
echo -e "${YELLOW}▶ Suppression du cluster KinD 'rhdemo'...${NC}"
if kind get clusters | grep -q "^rhdemo$"; then
    # Avant de supprimer le cluster, nettoyer les données persistantes dans le conteneur
    echo -e "${YELLOW}  - Nettoyage des données persistantes dans le nœud KinD...${NC}"
    docker exec rhdemo-control-plane sh -c "rm -rf /var/local-path-provisioner/*" 2>/dev/null || true

    kind delete cluster --name rhdemo
    echo -e "${GREEN}✅ Cluster KinD 'rhdemo' supprimé${NC}"
else
    echo -e "${YELLOW}ℹ️  Cluster KinD 'rhdemo' n'existe pas${NC}"
fi

# Supprimer les volumes Docker orphelins créés par KinD
echo -e "${YELLOW}▶ Nettoyage des volumes Docker orphelins...${NC}"
docker volume prune -f > /dev/null 2>&1
echo -e "${GREEN}✅ Volumes Docker nettoyés${NC}"

# Optionnel : Nettoyer les images non utilisées
read -p "Voulez-vous nettoyer les images Docker non utilisées ? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}▶ Nettoyage des images Docker non utilisées...${NC}"
    docker image prune -a -f
    echo -e "${GREEN}✅ Images Docker nettoyées${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Nettoyage complet terminé${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Prochaines étapes :${NC}"
echo -e "  1. Relancer ${BLUE}./init-stagingkub.sh${NC} pour recréer le cluster"
echo -e "  2. Déployer l'application via le pipeline Jenkins"
echo ""
