#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# SCRIPT DE TEST : Accès Jenkins → stagingkub
#
# Teste que Jenkins peut accéder :
# - Au registry Docker
# - Au cluster Kubernetes KinD
# - Aux commandes kubectl et helm
# ═══════════════════════════════════════════════════════════════════

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ERRORS=0

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test d'accès Jenkins → stagingkub${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# ────────────────────────────────────────────────────────────────
# 1. Vérifier que Jenkins tourne
# ────────────────────────────────────────────────────────────────

echo -e "${YELLOW}▶ Vérification de Jenkins${NC}"

echo -n "Container Jenkins en cours d'exécution... "
if docker ps --format '{{.Names}}' | grep -q "^rhdemo-jenkins$"; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ Jenkins ne tourne pas${NC}"
    echo -e "${YELLOW}Démarrez Jenkins avec: cd rhDemo/infra/jenkins-docker && ./start-jenkins.sh${NC}"
    exit 1
fi
echo ""

# ────────────────────────────────────────────────────────────────
# 2. Vérifier la connectivité réseau
# ────────────────────────────────────────────────────────────────

echo -e "${YELLOW}▶ Vérification de la connectivité réseau${NC}"

echo -n "Jenkins connecté au réseau 'kind'... "
if docker network inspect kind 2>/dev/null | grep -q "rhdemo-jenkins"; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ NON CONNECTÉ${NC}"
    echo -e "${YELLOW}Connexion automatique...${NC}"
    docker network connect kind rhdemo-jenkins && echo -e "${GREEN}✅ Connecté${NC}" || echo -e "${RED}❌ Échec${NC}"
    ((ERRORS++))
fi

echo -n "Registry accessible depuis Jenkins... "
REGISTRY_NAME=$(docker ps --filter "publish=5000" --format '{{.Names}}' | head -n 1)
if [ -n "$REGISTRY_NAME" ]; then
    if docker exec rhdemo-jenkins curl -sf http://$REGISTRY_NAME:5000/v2/ > /dev/null; then
        echo -e "${GREEN}✅ OK ($REGISTRY_NAME)${NC}"
    else
        echo -e "${RED}❌ Registry détecté mais non accessible${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${RED}❌ Aucun registry sur le port 5000${NC}"
    ((ERRORS++))
fi

echo -n "Cluster KinD accessible depuis Jenkins... "
if docker exec rhdemo-jenkins kubectl cluster-info 2>&1 | grep -q "is running"; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ Cluster non accessible${NC}"
    echo -e "${YELLOW}Configuration de kubectl...${NC}"

    # Créer le répertoire .kube s'il n'existe pas
    docker exec rhdemo-jenkins mkdir -p /var/jenkins_home/.kube

    # Générer et installer la kubeconfig
    kind get kubeconfig --name rhdemo | sed 's|https://127.0.0.1:[0-9]*|https://rhdemo-control-plane:6443|g' | \
        docker exec -i rhdemo-jenkins tee /var/jenkins_home/.kube/config > /dev/null

    docker exec rhdemo-jenkins chmod 600 /var/jenkins_home/.kube/config
    docker exec rhdemo-jenkins chown 1000:1000 /var/jenkins_home/.kube/config

    # Re-tester
    if docker exec rhdemo-jenkins kubectl cluster-info 2>&1 | grep -q "is running"; then
        echo -e "${GREEN}✅ Configuration réussie${NC}"
    else
        echo -e "${RED}❌ Échec de configuration${NC}"
        ((ERRORS++))
    fi
fi
echo ""

# ────────────────────────────────────────────────────────────────
# 3. Vérifier les commandes
# ────────────────────────────────────────────────────────────────

echo -e "${YELLOW}▶ Vérification des commandes disponibles${NC}"

echo -n "kubectl disponible... "
if docker exec rhdemo-jenkins which kubectl > /dev/null 2>&1; then
    KUBECTL_VERSION=$(docker exec rhdemo-jenkins kubectl version --client --short 2>/dev/null | grep Client || echo "unknown")
    echo -e "${GREEN}✅ OK ($KUBECTL_VERSION)${NC}"
else
    echo -e "${RED}❌ NON DISPONIBLE${NC}"
    ((ERRORS++))
fi

echo -n "helm disponible... "
if docker exec rhdemo-jenkins which helm > /dev/null 2>&1; then
    HELM_VERSION=$(docker exec rhdemo-jenkins helm version --short 2>/dev/null | head -1 || echo "unknown")
    echo -e "${GREEN}✅ OK ($HELM_VERSION)${NC}"
else
    echo -e "${RED}❌ NON DISPONIBLE${NC}"
    ((ERRORS++))
fi

echo -n "kind disponible... "
if docker exec rhdemo-jenkins which kind > /dev/null 2>&1; then
    KIND_VERSION=$(docker exec rhdemo-jenkins kind --version 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✅ OK ($KIND_VERSION)${NC}"
else
    echo -e "${RED}❌ NON DISPONIBLE${NC}"
    ((ERRORS++))
fi

echo -n "docker disponible... "
if docker exec rhdemo-jenkins docker --version > /dev/null 2>&1; then
    DOCKER_VERSION=$(docker exec rhdemo-jenkins docker --version | cut -d' ' -f3 | tr -d ',')
    echo -e "${GREEN}✅ OK (v$DOCKER_VERSION)${NC}"
else
    echo -e "${RED}❌ NON DISPONIBLE${NC}"
    ((ERRORS++))
fi
echo ""

# ────────────────────────────────────────────────────────────────
# 4. Tests fonctionnels
# ────────────────────────────────────────────────────────────────

echo -e "${YELLOW}▶ Tests fonctionnels${NC}"

echo -n "Lister les nodes Kubernetes... "
if docker exec rhdemo-jenkins kubectl get nodes 2>&1 | grep -q "rhdemo-control-plane"; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ ÉCHEC${NC}"
    ((ERRORS++))
fi

echo -n "Accès au namespace rhdemo-stagingkub... "
if docker exec rhdemo-jenkins kubectl get namespace rhdemo-stagingkub 2>/dev/null | grep -q "rhdemo-stagingkub"; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${YELLOW}⚠️  Namespace non créé (normal si init pas encore lancé)${NC}"
fi

echo -n "Lister les images du registry... "
if [ -n "$REGISTRY_NAME" ]; then
    if docker exec rhdemo-jenkins curl -sf http://$REGISTRY_NAME:5000/v2/_catalog 2>&1 | grep -q "repositories"; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${RED}❌ ÉCHEC${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}⚠️  Registry non disponible${NC}"
fi

echo -n "Push test vers le registry... "
if [ -n "$REGISTRY_NAME" ]; then
    # Créer une petite image de test
    docker exec rhdemo-jenkins sh -c "echo 'FROM alpine' | docker build -t test:latest - > /dev/null 2>&1"
    docker exec rhdemo-jenkins docker tag test:latest localhost:5000/test:latest > /dev/null 2>&1

    if docker exec rhdemo-jenkins docker push localhost:5000/test:latest > /dev/null 2>&1; then
        echo -e "${GREEN}✅ OK${NC}"
        # Nettoyer
        docker exec rhdemo-jenkins docker rmi test:latest localhost:5000/test:latest > /dev/null 2>&1 || true
    else
        echo -e "${RED}❌ ÉCHEC${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}⚠️  Registry non disponible${NC}"
fi

echo ""

# ────────────────────────────────────────────────────────────────
# 5. Résumé
# ────────────────────────────────────────────────────────────────

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ TOUS LES TESTS SONT PASSÉS${NC}"
    echo ""
    echo -e "${GREEN}Jenkins est correctement configuré pour déployer sur stagingkub !${NC}"
    echo ""
    echo -e "${YELLOW}Prochaines étapes :${NC}"
    echo "  1. Lancez un build Jenkins avec DEPLOY_ENV=stagingkub"
    echo "  2. Le pipeline configurera automatiquement kubectl au démarrage"
    echo "  3. Surveillez les logs dans la console Jenkins"
else
    echo -e "${RED}❌ $ERRORS ERREUR(S) DÉTECTÉE(S)${NC}"
    echo ""
    echo -e "${YELLOW}Actions recommandées :${NC}"
    echo "  1. Vérifiez que le cluster KinD est initialisé : ./scripts/init-stagingkub.sh"
    echo "  2. Vérifiez les logs Jenkins : docker logs rhdemo-jenkins"
    echo "  3. Consultez JENKINS-NETWORK-ANALYSIS.md pour le dépannage"
fi
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

exit $ERRORS
