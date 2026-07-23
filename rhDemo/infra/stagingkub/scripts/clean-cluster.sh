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
# Note : pas de nettoyage manuel de /var/local-path-provisioner dans le
# conteneur avant `kind delete cluster` — le conteneur (et son filesystem
# éphémère, y compris les PVC en provisioning dynamique comme Loki/
# Prometheus/AlertManager) est détruit dans la foulée, donc ce nettoyage
# était sans effet. Les données PostgreSQL/Keycloak, elles, ne sont de toute
# façon jamais concernées : PersistentVolume hostPath statique + Retain
# (rhDemo/infra/stagingkub/helm/rhdemo/templates/postgresql-persistentvolumes.yaml),
# stocké hors du conteneur via les extraMounts KinD.
echo -e "${YELLOW}▶ Suppression du cluster KinD 'rhdemo'...${NC}"
if kind get clusters | grep -q "^rhdemo$"; then
    # Arrêt propre de PostgreSQL avant `kind delete cluster` : ce dernier
    # supprime directement les conteneurs de nœuds (pas de passage par l'API
    # Kubernetes, donc pas de drain/SIGTERM géré normalement) — équivalent à
    # un `docker rm -f`. Sans risque de corruption grâce au WAL (fsync par
    # défaut, non désactivé dans ce projet), mais un scale à 0 fait passer
    # PostgreSQL par un arrêt "fast" propre (checkpoint + flush WAL) plutôt
    # que par une récupération après crash au redémarrage suivant.
    if kubectl get statefulset postgresql-rhdemo postgresql-keycloak \
        -n rhdemo-stagingkub --context kind-rhdemo &>/dev/null; then
        echo -e "${YELLOW}  - Arrêt propre de PostgreSQL (scale à 0)...${NC}"
        kubectl scale statefulset postgresql-rhdemo postgresql-keycloak \
            -n rhdemo-stagingkub --context kind-rhdemo --replicas=0 &>/dev/null || true
        kubectl wait --for=delete pod -l app=postgresql-rhdemo \
            -n rhdemo-stagingkub --context kind-rhdemo --timeout=60s &>/dev/null || \
            echo -e "${YELLOW}    ⚠ Timeout sur l'arrêt de postgresql-rhdemo, suppression forcée du cluster quand même${NC}"
        kubectl wait --for=delete pod -l app=postgresql-keycloak \
            -n rhdemo-stagingkub --context kind-rhdemo --timeout=60s &>/dev/null || \
            echo -e "${YELLOW}    ⚠ Timeout sur l'arrêt de postgresql-keycloak, suppression forcée du cluster quand même${NC}"
        echo -e "${GREEN}  ✅ PostgreSQL arrêté proprement${NC}"
    else
        echo -e "${YELLOW}  ℹ️  StatefulSets PostgreSQL absents (application jamais déployée), rien à arrêter${NC}"
    fi

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

    # `docker image prune -a` supprime toute image non référencée par un
    # conteneur (même arrêté). rhdemo-jenkins-agent (jenkins-docker/) sert de
    # template Docker Cloud aux agents éphémères CI/CD : entre deux builds
    # aucun conteneur n'existe dessus, donc elle est éligible au prune alors
    # que ce script ne concerne que le cluster KinD stagingkub. On la protège
    # en lui attachant temporairement un conteneur arrêté (jamais démarré) le
    # temps du prune.
    GUARD_CONTAINER=""
    if docker image inspect rhdemo-jenkins-agent:latest &>/dev/null; then
        GUARD_CONTAINER=$(docker create rhdemo-jenkins-agent:latest true 2>/dev/null) || GUARD_CONTAINER=""
    fi

    docker image prune -a -f

    if [[ -n "$GUARD_CONTAINER" ]]; then
        docker rm "$GUARD_CONTAINER" &>/dev/null || true
    fi

    echo -e "${GREEN}✅ Images Docker nettoyées (rhdemo-jenkins-agent préservée)${NC}"
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
