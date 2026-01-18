#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Script de vérification de la configuration du registry Docker
# ═══════════════════════════════════════════════════════════════

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Vérification de la Configuration du Registry Docker${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# 1. Vérifier qu'un registry tourne sur le port 5000
echo -e "${YELLOW}1. Vérification du registry sur le port 5000...${NC}"
REGISTRY=$(docker ps --filter "publish=5000" --format '{{.Names}}' | head -n 1)

if [ -z "$REGISTRY" ]; then
    echo -e "${RED}❌ Aucun registry actif sur le port 5000${NC}"
    echo -e "${YELLOW}💡 Démarrez le registry avec:${NC}"
    echo "   cd rhDemo/infra/jenkins-docker && docker-compose up -d registry"
    exit 1
fi

echo -e "${GREEN}✅ Registry actif: ${REGISTRY}${NC}"

# 2. Vérifier le certificat du registry
echo ""
echo -e "${YELLOW}2. Vérification du certificat HTTPS...${NC}"
REGISTRY_CERT="/etc/docker/certs.d/localhost:5000/ca.crt"
if [ -f "$REGISTRY_CERT" ]; then
    echo -e "${GREEN}✅ Certificat trouvé: ${REGISTRY_CERT}${NC}"
else
    echo -e "${RED}❌ Certificat manquant: ${REGISTRY_CERT}${NC}"
    echo -e "${YELLOW}💡 Générez les certificats avec:${NC}"
    echo "   cd rhDemo/infra/jenkins-docker && ./init-registry-certs.sh"
    exit 1
fi

# 3. Vérifier le nom du registry
echo ""
echo -e "${YELLOW}3. Vérification du nom du registry...${NC}"
if [ "$REGISTRY" = "kind-registry" ]; then
    echo -e "${GREEN}✅ Nom correct: kind-registry${NC}"
else
    echo -e "${YELLOW}⚠️  Nom actuel: ${REGISTRY}${NC}"
    echo -e "${YELLOW}   Nom attendu: kind-registry${NC}"
    echo -e "${YELLOW}💡 Pour corriger, exécutez:${NC}"
    echo "   docker stop $REGISTRY && docker rm $REGISTRY"
    echo "   cd rhDemo/infra/jenkins-docker && docker-compose up -d registry"
fi

# 4. Vérifier l'accessibilité HTTPS
echo ""
echo -e "${YELLOW}4. Test d'accessibilité HTTPS...${NC}"
if curl -sf --cacert "$REGISTRY_CERT" https://localhost:5000/v2/_catalog > /dev/null; then
    echo -e "${GREEN}✅ Registry accessible sur https://localhost:5000${NC}"

    # Afficher les images
    IMAGES=$(curl -s --cacert "$REGISTRY_CERT" https://localhost:5000/v2/_catalog | jq -r '.repositories[]' 2>/dev/null || echo "")
    if [ -n "$IMAGES" ]; then
        echo -e "${BLUE}   Images disponibles:${NC}"
        echo "$IMAGES" | while read img; do
            TAGS=$(curl -s --cacert "$REGISTRY_CERT" https://localhost:5000/v2/$img/tags/list | jq -r '.tags[]' 2>/dev/null | head -3)
            echo -e "     • $img"
            echo "$TAGS" | while read tag; do
                echo -e "       - $tag"
            done
        done
    else
        echo -e "${YELLOW}   (Aucune image dans le registry)${NC}"
    fi
else
    echo -e "${RED}❌ Registry inaccessible${NC}"
    exit 1
fi

# 5. Vérifier la connexion au réseau kind
echo ""
echo -e "${YELLOW}5. Vérification de la connexion au réseau 'kind'...${NC}"
if docker network inspect kind 2>/dev/null | grep -q "\"$REGISTRY\""; then
    echo -e "${GREEN}✅ Registry connecté au réseau 'kind'${NC}"

    # Afficher l'IP
    IP=$(docker inspect $REGISTRY | jq -r '.[0].NetworkSettings.Networks.kind.IPAddress' 2>/dev/null)
    if [ -n "$IP" ]; then
        echo -e "${BLUE}   IP sur réseau kind: ${IP}${NC}"
    fi
else
    echo -e "${RED}❌ Registry NON connecté au réseau 'kind'${NC}"
    echo -e "${YELLOW}💡 Pour connecter:${NC}"
    echo "   docker network connect kind $REGISTRY --alias kind-registry"
    exit 1
fi

# 6. Vérifier l'alias DNS 'kind-registry'
echo ""
echo -e "${YELLOW}6. Vérification de l'alias DNS 'kind-registry'...${NC}"
if docker network inspect kind | grep -q "\"kind-registry\""; then
    echo -e "${GREEN}✅ Alias 'kind-registry' configuré${NC}"
else
    echo -e "${RED}❌ Alias 'kind-registry' manquant${NC}"
    echo -e "${YELLOW}💡 Pour ajouter l'alias:${NC}"
    echo "   docker network disconnect kind $REGISTRY 2>/dev/null || true"
    echo "   docker network connect kind $REGISTRY --alias kind-registry"
    exit 1
fi

# 7. Vérifier la résolution DNS depuis Kind
echo ""
echo -e "${YELLOW}7. Test de résolution DNS depuis Kind...${NC}"
if kind get clusters | grep -q "^rhdemo$"; then
    if docker exec rhdemo-control-plane getent hosts kind-registry &> /dev/null; then
        KIND_RESOLVED=$(docker exec rhdemo-control-plane getent hosts kind-registry | awk '{print $1}')
        echo -e "${GREEN}✅ 'kind-registry' résolvable depuis Kind: ${KIND_RESOLVED}${NC}"
    else
        echo -e "${RED}❌ 'kind-registry' NON résolvable depuis Kind${NC}"
        exit 1
    fi

    # Test HTTPS depuis Kind
    echo ""
    echo -e "${YELLOW}   Test HTTPS depuis Kind...${NC}"
    if docker exec rhdemo-control-plane curl -sf https://kind-registry:5000/v2/_catalog > /dev/null; then
        echo -e "${GREEN}✅ Registry accessible depuis Kind via HTTPS${NC}"
    else
        echo -e "${RED}❌ Registry inaccessible depuis Kind via HTTPS${NC}"
        echo -e "${YELLOW}💡 Vérifiez que le certificat est installé dans le nœud Kind${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Cluster Kind 'rhdemo' non trouvé, test ignoré${NC}"
fi

# 8. Vérifier la configuration containerd
echo ""
echo -e "${YELLOW}8. Vérification de la configuration containerd dans Kind...${NC}"
if kind get clusters | grep -q "^rhdemo$"; then
    if docker exec rhdemo-control-plane cat /etc/containerd/config.toml 2>/dev/null | \
       grep -A1 "localhost:5000" | grep -q "https://kind-registry:5000"; then
        echo -e "${GREEN}✅ Containerd configuré pour rediriger localhost:5000 → https://kind-registry:5000${NC}"
    else
        echo -e "${RED}❌ Configuration containerd incorrecte ou manquante${NC}"
        echo -e "${YELLOW}💡 Vérifiez kind-config.yaml:${NC}"
        echo "   containerdConfigPatches:"
        echo "   - |"
        echo "     [plugins.\"io.containerd.grpc.v1.cri\".registry.mirrors.\"localhost:5000\"]"
        echo "       endpoint = [\"https://kind-registry:5000\"]"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Cluster Kind 'rhdemo' non trouvé, test ignoré${NC}"
fi

# 9. Test de pull d'image depuis Kubernetes (optionnel)
echo ""
echo -e "${YELLOW}9. Test de pull d'image depuis Kubernetes...${NC}"
if kind get clusters | grep -q "^rhdemo$" && [ -n "$IMAGES" ]; then
    TEST_IMAGE=$(echo "$IMAGES" | head -1)
    if [ -n "$TEST_IMAGE" ]; then
        TEST_TAG=$(curl -s --cacert "$REGISTRY_CERT" https://localhost:5000/v2/$TEST_IMAGE/tags/list | jq -r '.tags[0]' 2>/dev/null)

        if [ -n "$TEST_TAG" ] && [ "$TEST_TAG" != "null" ]; then
            echo -e "${BLUE}   Test avec: localhost:5000/${TEST_IMAGE}:${TEST_TAG}${NC}"

            # Créer un pod de test
            if kubectl run test-registry-pull \
                --image=localhost:5000/${TEST_IMAGE}:${TEST_TAG} \
                --restart=Never \
                --namespace=default \
                --command -- sleep 10 &> /dev/null; then

                # Attendre que le pod démarre ou échoue
                sleep 5
                POD_STATUS=$(kubectl get pod test-registry-pull -n default -o jsonpath='{.status.phase}' 2>/dev/null || echo "Failed")

                if [ "$POD_STATUS" = "Running" ] || [ "$POD_STATUS" = "Succeeded" ]; then
                    echo -e "${GREEN}✅ Image pullée avec succès depuis Kubernetes${NC}"
                else
                    echo -e "${YELLOW}⚠️  Pod de test en statut: ${POD_STATUS}${NC}"
                fi

                # Nettoyer
                kubectl delete pod test-registry-pull -n default --force --grace-period=0 &> /dev/null || true
            else
                echo -e "${YELLOW}⚠️  Impossible de créer le pod de test${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  Aucune image avec tag disponible pour le test${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  Test ignoré (cluster absent ou aucune image)${NC}"
fi

# Résumé
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Vérification terminée avec succès !${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Configuration du registry:${NC}"
echo -e "  • Nom:        ${REGISTRY}"
echo -e "  • Port:       5000"
echo -e "  • Protocole:  HTTPS"
echo -e "  • Réseau:     kind (avec alias 'kind-registry')"
echo -e "  • URL Host:   https://localhost:5000"
echo -e "  • URL Kind:   https://kind-registry:5000"
echo -e "  • Redirect:   localhost:5000 → https://kind-registry:5000 (via containerd)"
echo ""
