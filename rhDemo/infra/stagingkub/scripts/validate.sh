#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Script de validation de l'environnement stagingkub
# ═══════════════════════════════════════════════════════════════

set -e

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Validation de l'environnement stagingkub${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Fonction pour vérifier une commande
check_command() {
    local cmd=$1
    local name=$2
    echo -n "Vérification de $name... "
    if command -v $cmd &> /dev/null; then
        echo -e "${GREEN}✅ OK${NC} ($(command -v $cmd))"
    else
        echo -e "${RED}❌ MANQUANT${NC}"
        ((ERRORS++))
    fi
}

# Fonction pour vérifier une ressource Kubernetes
check_k8s_resource() {
    local type=$1
    local name=$2
    local namespace=$3
    echo -n "Vérification $type/$name... "
    if kubectl get $type $name -n $namespace &> /dev/null; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${RED}❌ MANQUANT${NC}"
        ((ERRORS++))
    fi
}

# 1. Vérification des outils
echo -e "${YELLOW}▶ Vérification des outils requis${NC}"
check_command "docker" "Docker"
check_command "kubectl" "kubectl"
check_command "helm" "Helm"
check_command "kind" "KinD"
echo ""

# 2. Vérification du registry local
echo -e "${YELLOW}▶ Vérification du registry Docker local${NC}"

# Détecter le registry sur le port 5000
REGISTRY_NAME=$(docker ps --filter "publish=5000" --format '{{.Names}}' | head -n 1)

echo -n "Vérification du registry sur le port 5000... "
if [ -n "$REGISTRY_NAME" ]; then
    echo -e "${GREEN}✅ OK (en cours d'exécution: $REGISTRY_NAME)${NC}"
else
    # Chercher un registry arrêté
    STOPPED_REGISTRY=$(docker ps -a --filter "publish=5000" --format '{{.Names}}' | head -n 1)
    if [ -n "$STOPPED_REGISTRY" ]; then
        echo -e "${YELLOW}⚠️  Registry existe mais n'est pas démarré: $STOPPED_REGISTRY${NC}"
        echo -e "${YELLOW}Démarrez-le avec: docker start $STOPPED_REGISTRY${NC}"
        REGISTRY_NAME="$STOPPED_REGISTRY"
        ((ERRORS++))
    else
        echo -e "${RED}❌ MANQUANT${NC}"
        echo -e "${YELLOW}Exécutez: ./scripts/init-stagingkub.sh${NC}"
        ((ERRORS++))
    fi
fi

echo -n "Vérification de l'accessibilité du registry... "
if curl -f http://localhost:5000/v2/ &> /dev/null; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ Non accessible${NC}"
    if [ -n "$REGISTRY_NAME" ]; then
        echo -e "${YELLOW}Vérifiez les logs: docker logs $REGISTRY_NAME${NC}"
    fi
    ((ERRORS++))
fi

if [ -n "$REGISTRY_NAME" ]; then
    echo -n "Vérification de la connexion au réseau kind... "
    if docker network inspect kind 2>/dev/null | grep -q "$REGISTRY_NAME"; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${RED}❌ Registry non connecté au réseau kind${NC}"
        echo -e "${YELLOW}Connectez-le avec: docker network connect kind $REGISTRY_NAME${NC}"
        ((ERRORS++))
    fi
fi
echo ""

# 3. Vérification du cluster KinD
echo -e "${YELLOW}▶ Vérification du cluster KinD${NC}"
echo -n "Vérification du cluster 'rhdemo'... "
if kind get clusters | grep -q "^rhdemo$"; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ MANQUANT${NC}"
    echo -e "${YELLOW}Exécutez: ./scripts/init-stagingkub.sh${NC}"
    ((ERRORS++))
fi

echo -n "Vérification du contexte kubectl... "
if kubectl config current-context | grep -q "kind-rhdemo"; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${YELLOW}⚠️  Pas sur le bon contexte${NC}"
    echo -e "${YELLOW}Exécutez: kubectl config use-context kind-rhdemo${NC}"
fi
echo ""

# 3. Vérification des nodes
echo -e "${YELLOW}▶ Vérification des nodes Kubernetes${NC}"
echo -n "Vérification du node control-plane... "
if kubectl get nodes 2>/dev/null | grep -q "control-plane.*Ready"; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ ERREUR${NC}"
    ((ERRORS++))
fi
echo ""

# 4. Vérification de Nginx Ingress
echo -e "${YELLOW}▶ Vérification de Nginx Ingress Controller${NC}"
echo -n "Vérification du namespace ingress-nginx... "
if kubectl get namespace ingress-nginx &> /dev/null; then
    echo -e "${GREEN}✅ OK${NC}"

    echo -n "Vérification du controller... "
    if kubectl get pods -n ingress-nginx -l app.kubernetes.io/component=controller 2>/dev/null | grep -q "Running"; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${RED}❌ Pas en Running${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${RED}❌ MANQUANT${NC}"
    echo -e "${YELLOW}Exécutez: ./scripts/init-stagingkub.sh${NC}"
    ((ERRORS++))
fi
echo ""

# 5. Vérification du namespace rhdemo-staging
echo -e "${YELLOW}▶ Vérification du namespace rhdemo-staging${NC}"
echo -n "Vérification du namespace... "
if kubectl get namespace rhdemo-staging &> /dev/null; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ MANQUANT${NC}"
    echo -e "${YELLOW}Exécutez: ./scripts/init-stagingkub.sh${NC}"
    ((ERRORS++))
fi
echo ""

# 6. Vérification des secrets
echo -e "${YELLOW}▶ Vérification des secrets Kubernetes${NC}"
check_k8s_resource "secret" "rhdemo-db-secret" "rhdemo-staging"
check_k8s_resource "secret" "keycloak-db-secret" "rhdemo-staging"
check_k8s_resource "secret" "keycloak-admin-secret" "rhdemo-staging"
check_k8s_resource "secret" "rhdemo-app-secrets" "rhdemo-staging"
check_k8s_resource "secret" "rhdemo-tls-cert" "rhdemo-staging"
echo ""

# 7. Vérification du déploiement Helm (si existe)
echo -e "${YELLOW}▶ Vérification du déploiement Helm (optionnel)${NC}"
echo -n "Vérification de la release 'rhdemo'... "
if helm list -n rhdemo-staging 2>/dev/null | grep -q "rhdemo"; then
    echo -e "${GREEN}✅ OK${NC}"

    # Vérification des ressources déployées
    echo -e "${YELLOW}▶ Vérification des ressources déployées${NC}"
    check_k8s_resource "statefulset" "postgresql-rhdemo" "rhdemo-staging"
    check_k8s_resource "statefulset" "postgresql-keycloak" "rhdemo-staging"
    check_k8s_resource "deployment" "keycloak" "rhdemo-staging"
    check_k8s_resource "deployment" "rhdemo-app" "rhdemo-staging"
    check_k8s_resource "service" "postgresql-rhdemo" "rhdemo-staging"
    check_k8s_resource "service" "postgresql-keycloak" "rhdemo-staging"
    check_k8s_resource "service" "keycloak" "rhdemo-staging"
    check_k8s_resource "service" "rhdemo-app" "rhdemo-staging"
    check_k8s_resource "ingress" "rhdemo-ingress" "rhdemo-staging"

    # Vérification du statut des pods
    echo ""
    echo -e "${YELLOW}▶ Statut des pods${NC}"
    kubectl get pods -n rhdemo-staging
else
    echo -e "${YELLOW}⚠️  Pas encore déployé${NC}"
    echo -e "${YELLOW}Exécutez: ./scripts/deploy.sh VERSION${NC}"
fi
echo ""

# 8. Vérification de /etc/hosts
echo -e "${YELLOW}▶ Vérification de /etc/hosts${NC}"
echo -n "Vérification de rhdemo.staging.local... "
if grep -q "rhdemo.staging.local" /etc/hosts; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ MANQUANT${NC}"
    echo -e "${YELLOW}Ajoutez: echo '127.0.0.1 rhdemo.staging.local' | sudo tee -a /etc/hosts${NC}"
    ((ERRORS++))
fi

echo -n "Vérification de keycloak.staging.local... "
if grep -q "keycloak.staging.local" /etc/hosts; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ MANQUANT${NC}"
    echo -e "${YELLOW}Ajoutez: echo '127.0.0.1 keycloak.staging.local' | sudo tee -a /etc/hosts${NC}"
    ((ERRORS++))
fi
echo ""

# 9. Vérification des certificats
echo -e "${YELLOW}▶ Vérification des certificats SSL${NC}"
CERTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/certs"
echo -n "Vérification de tls.crt... "
if [ -f "$CERTS_DIR/tls.crt" ]; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ MANQUANT${NC}"
    echo -e "${YELLOW}Exécutez: ./scripts/init-stagingkub.sh${NC}"
    ((ERRORS++))
fi

echo -n "Vérification de tls.key... "
if [ -f "$CERTS_DIR/tls.key" ]; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ MANQUANT${NC}"
    echo -e "${YELLOW}Exécutez: ./scripts/init-stagingkub.sh${NC}"
    ((ERRORS++))
fi
echo ""

# 10. Résumé
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ Validation réussie ! L'environnement stagingkub est prêt.${NC}"
else
    echo -e "${RED}❌ Validation échouée avec $ERRORS erreur(s).${NC}"
    echo -e "${YELLOW}Veuillez corriger les erreurs ci-dessus.${NC}"
    exit 1
fi
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
