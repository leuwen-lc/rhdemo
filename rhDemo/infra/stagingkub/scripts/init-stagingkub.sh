#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Script d'initialisation de l'environnement stagingkub (KinD)
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGINGKUB_DIR="$(dirname "$SCRIPT_DIR")"
HELM_CHART_DIR="$STAGINGKUB_DIR/helm/rhdemo"
RHDEMO_ROOT="$(cd "$STAGINGKUB_DIR/../.." && pwd)"

# Couleurs pour les logs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Initialisation de l'environnement stagingkub (KinD)${NC}"
echo -e "${BLUE}  CNI: Cilium 1.18 | Gateway: NGINX Gateway Fabric 2.6.0${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Vérifier que KinD est installé
if ! command -v kind &> /dev/null; then
    echo -e "${RED}❌ KinD n'est pas installé. Veuillez installer KinD d'abord.${NC}"
    exit 1
fi

# Vérifier que kubectl est installé
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl n'est pas installé. Veuillez installer kubectl d'abord.${NC}"
    exit 1
fi

# Vérifier que Helm est installé
if ! command -v helm &> /dev/null; then
    echo -e "${RED}❌ Helm n'est pas installé. Veuillez installer Helm d'abord.${NC}"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════
# Prérequis système pour Cilium
# ═══════════════════════════════════════════════════════════════
echo -e "${YELLOW}▶ Vérification des prérequis système pour Cilium...${NC}"

# Vérifier les limites inotify (évite "too many open files" avec Cilium)
INOTIFY_WATCHES=$(cat /proc/sys/fs/inotify/max_user_watches 2>/dev/null || echo "0")
INOTIFY_INSTANCES=$(cat /proc/sys/fs/inotify/max_user_instances 2>/dev/null || echo "0")
INOTIFY_OK=true

if [ "$INOTIFY_WATCHES" -lt 524288 ]; then
    echo -e "${RED}❌ fs.inotify.max_user_watches insuffisant : ${INOTIFY_WATCHES} (minimum: 524288)${NC}"
    INOTIFY_OK=false
fi

if [ "$INOTIFY_INSTANCES" -lt 512 ]; then
    echo -e "${RED}❌ fs.inotify.max_user_instances insuffisant : ${INOTIFY_INSTANCES} (minimum: 512)${NC}"
    INOTIFY_OK=false
fi

if [ "$INOTIFY_OK" = false ]; then
    echo ""
    echo -e "${YELLOW}Cilium nécessite des limites inotify plus élevées.${NC}"
    echo -e "${YELLOW}Exécutez les commandes suivantes puis relancez ce script :${NC}"
    echo ""
    echo -e "${BLUE}  # Correction temporaire (jusqu'au prochain reboot)${NC}"
    echo "  sudo sysctl -w fs.inotify.max_user_watches=524288"
    echo "  sudo sysctl -w fs.inotify.max_user_instances=512"
    echo ""
    echo -e "${BLUE}  # Ou correction permanente${NC}"
    echo "  echo 'fs.inotify.max_user_watches=524288' | sudo tee -a /etc/sysctl.d/99-cilium.conf"
    echo "  echo 'fs.inotify.max_user_instances=512' | sudo tee -a /etc/sysctl.d/99-cilium.conf"
    echo "  sudo sysctl --system"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ Limites inotify OK (watches=${INOTIFY_WATCHES}, instances=${INOTIFY_INSTANCES})${NC}"

# ═══════════════════════════════════════════════════════════════
# Configuration du registry Docker local
# ═══════════════════════════════════════════════════════════════
echo -e "${YELLOW}▶ Configuration du registry Docker local...${NC}"
REGISTRY_PORT="5000"
REGISTRY_NAME="kind-registry"

# Détecter un registry actif sur le port 5000
ACTIVE_REGISTRY=$(docker ps --filter "publish=${REGISTRY_PORT}" --format '{{.Names}}' | head -n 1)

if [ -n "$ACTIVE_REGISTRY" ]; then
    echo -e "${GREEN}✅ Registry Docker actif sur le port ${REGISTRY_PORT}: '${ACTIVE_REGISTRY}'${NC}"
    REGISTRY_NAME="$ACTIVE_REGISTRY"
else
    # Chercher un registry existant mais arrêté
    STOPPED_REGISTRY=$(docker ps -a --filter "publish=${REGISTRY_PORT}" --format '{{.Names}}' | head -n 1)

    if [ -n "$STOPPED_REGISTRY" ]; then
        echo -e "${YELLOW}▶ Registry '${STOPPED_REGISTRY}' trouvé (arrêté), démarrage...${NC}"
        docker start ${STOPPED_REGISTRY}
        sleep 2
        REGISTRY_NAME="$STOPPED_REGISTRY"
        echo -e "${GREEN}✅ Registry démarré${NC}"
    else
        echo -e "${YELLOW}▶ Aucun registry trouvé, création de 'kind-registry'...${NC}"
        if docker run -d \
            --name kind-registry \
            --restart=always \
            -p ${REGISTRY_PORT}:5000 \
            registry:2 > /dev/null; then
            sleep 2
            echo -e "${GREEN}✅ Registry créé et actif${NC}"
        else
            echo -e "${RED}❌ Erreur lors de la création du registry${NC}"
            echo -e "${YELLOW}💡 Le port ${REGISTRY_PORT} est peut-être occupé. Démarrez d'abord Jenkins:${NC}"
            echo "     cd rhDemo/infra/jenkins-docker && docker-compose up -d registry"
            exit 1
        fi
    fi
fi

# Vérifier l'accessibilité (HTTPS avec certificat auto-signé)
REGISTRY_CERT="/etc/docker/certs.d/localhost:${REGISTRY_PORT}/ca.crt"
if [ ! -f "$REGISTRY_CERT" ]; then
    echo -e "${RED}❌ Certificat du registry non trouvé : ${REGISTRY_CERT}${NC}"
    echo -e "${YELLOW}   Générez les certificats avec :${NC}"
    echo -e "${YELLOW}   cd rhDemo/infra/jenkins-docker && ./init-registry-certs.sh${NC}"
    exit 1
fi

if ! curl -sf --cacert "$REGISTRY_CERT" https://localhost:${REGISTRY_PORT}/v2/ > /dev/null; then
    echo -e "${RED}❌ Registry inaccessible sur https://localhost:${REGISTRY_PORT}${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Registry accessible (HTTPS)${NC}"

# Vérifier que le cluster KinD 'rhdemo' existe
echo -e "${YELLOW}▶ Vérification du cluster KinD 'rhdemo'...${NC}"
if ! kind get clusters | grep -q "^rhdemo$"; then
    echo -e "${RED}❌ Le cluster KinD 'rhdemo' n'existe pas.${NC}"
    echo -e "${YELLOW}Création du cluster KinD 'rhdemo'...${NC}"

    # Créer le répertoire de persistance sur l'hôte
    PERSISTENCE_DIR="/home/leno-vo/kind-data/rhdemo-stagingkub"
    echo -e "${YELLOW}Création du répertoire de persistance : ${PERSISTENCE_DIR}${NC}"
    mkdir -p "${PERSISTENCE_DIR}"
    chmod 755 "${PERSISTENCE_DIR}"
    echo -e "${GREEN}✅ Répertoire de persistance créé${NC}"

    # Utiliser le fichier kind-config.yaml du répertoire stagingkub
    KIND_CONFIG_FILE="${STAGINGKUB_DIR}/kind-config.yaml"

    if [ ! -f "${KIND_CONFIG_FILE}" ]; then
        echo -e "${RED}❌ Fichier kind-config.yaml non trouvé : ${KIND_CONFIG_FILE}${NC}"
        exit 1
    fi

    echo -e "${YELLOW}Utilisation de la configuration : ${KIND_CONFIG_FILE}${NC}"
    echo -e "${BLUE}Configuration :${NC}"
    echo -e "${BLUE}  - Persistance des données : ${PERSISTENCE_DIR}${NC}"
    echo -e "${BLUE}  - Registry Docker : ${REGISTRY_NAME}:${REGISTRY_PORT}${NC}"
    echo -e "${BLUE}  - Ports mappés : 80 → 31792, 443 → 32616${NC}"

    kind create cluster --name rhdemo --config "${KIND_CONFIG_FILE}"
    echo -e "${GREEN}✅ Cluster KinD 'rhdemo' créé avec persistance des données${NC}"

    # Connecter le registry au réseau KinD avec alias
    echo -e "${YELLOW}▶ Connexion du registry au réseau KinD...${NC}"
    docker network disconnect kind ${REGISTRY_NAME} 2>/dev/null || true
    docker network connect kind ${REGISTRY_NAME} --alias kind-registry
    echo -e "${GREEN}✅ Registry connecté avec alias 'kind-registry'${NC}"

    # ═══════════════════════════════════════════════════════════════
    # Installation de Cilium (CNI) via le script composant partagé
    # ═══════════════════════════════════════════════════════════════
    # IMPORTANT: Cilium doit être installé AVANT d'attendre que le nœud soit prêt
    # car sans CNI, le nœud reste en état NotReady
    "${SCRIPT_DIR}/components/install-or-upgrade-cilium.sh"

    CLUSTER_CREATED=true
else
    echo -e "${GREEN}✅ Cluster KinD 'rhdemo' trouvé${NC}"

    # Vérifier et reconnecter avec alias si nécessaire
    if ! docker network inspect kind | grep -q "${REGISTRY_NAME}"; then
        echo -e "${YELLOW}▶ Connexion du registry au réseau KinD...${NC}"
        docker network connect kind ${REGISTRY_NAME} --alias kind-registry
        echo -e "${GREEN}✅ Registry connecté avec alias 'kind-registry'${NC}"
    else
        # Vérifier que l'alias existe
        echo -e "${YELLOW}▶ Vérification de l'alias 'kind-registry'...${NC}"
        docker network disconnect kind ${REGISTRY_NAME} 2>/dev/null || true
        docker network connect kind ${REGISTRY_NAME} --alias kind-registry
        echo -e "${GREEN}✅ Alias 'kind-registry' configuré${NC}"
    fi

    # Cilium : même script composant, en upgrade cette fois (idempotent,
    # convergence vers la version pinnée même si le cluster existait déjà)
    "${SCRIPT_DIR}/components/install-or-upgrade-cilium.sh"

    CLUSTER_CREATED=false
fi

# ═══════════════════════════════════════════════════════════════
# Configuration HTTPS du registry dans le nœud KinD
# ═══════════════════════════════════════════════════════════════
echo -e "${YELLOW}▶ Configuration du registry HTTPS dans le nœud KinD...${NC}"

# Copier le certificat CA dans le nœud KinD
docker cp "$REGISTRY_CERT" rhdemo-control-plane:/usr/local/share/ca-certificates/kind-registry.crt

# Mettre à jour les CA du nœud
docker exec rhdemo-control-plane update-ca-certificates > /dev/null 2>&1

# Configurer containerd pour utiliser le registry HTTPS
# On crée un fichier de configuration hosts.toml pour le registry
echo -e "${YELLOW}  - Configuration de containerd pour le registry...${NC}"

# Créer le répertoire de configuration pour le registry
docker exec rhdemo-control-plane mkdir -p /etc/containerd/certs.d/localhost:5000

# Créer le fichier hosts.toml pour configurer le registry avec HTTPS
docker exec rhdemo-control-plane bash -c 'cat > /etc/containerd/certs.d/localhost:5000/hosts.toml << EOF
server = "https://kind-registry:5000"

[host."https://kind-registry:5000"]
  ca = "/usr/local/share/ca-certificates/kind-registry.crt"
EOF'

echo -e "${GREEN}✅ Containerd configuré pour le registry HTTPS${NC}"

# Définir le contexte kubectl
kubectl config use-context kind-rhdemo

# Attendre que le nœud KinD soit prêt
echo -e "${YELLOW}▶ Attente que le nœud KinD soit prêt...${NC}"
kubectl wait --for=condition=ready node --all --timeout=120s
echo -e "${GREEN}✅ Nœud KinD prêt${NC}"

# ═══════════════════════════════════════════════════════════════
# ConfigMap pour la découverte du registry local (KEP-1755)
# ═══════════════════════════════════════════════════════════════
echo -e "${YELLOW}▶ Configuration de la ConfigMap local-registry-hosting...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REGISTRY_PORT}"
    hostFromContainerRuntime: "kind-registry:${REGISTRY_PORT}"
    hostFromClusterNetwork: "kind-registry:${REGISTRY_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF
echo -e "${GREEN}✅ ConfigMap local-registry-hosting créée${NC}"

# ═══════════════════════════════════════════════════════════════
# Installation de NGINX Gateway Fabric via le script composant partagé
# ═══════════════════════════════════════════════════════════════
# NGINX Gateway Fabric implémente Gateway API (gateway.networking.k8s.io/v1)
# Les headers X-Forwarded-* sont configurés automatiquement par NGF
# ProxySettingsPolicy remplace SnippetsFilter pour les proxy buffers
# Documentation: https://docs.nginx.com/nginx-gateway-fabric/
# ═══════════════════════════════════════════════════════════════

NGF_NAMESPACE="nginx-gateway"

"${SCRIPT_DIR}/components/install-or-upgrade-ngf.sh"

# Vérifier que le GatewayClass 'nginx' est créé
echo -e "${YELLOW}  - Vérification du GatewayClass...${NC}"
if kubectl get gatewayclass nginx &> /dev/null; then
    echo -e "${GREEN}    ✓ GatewayClass 'nginx' disponible${NC}"
else
    echo -e "${YELLOW}    ⚠ GatewayClass 'nginx' non trouvé, il sera créé par le chart Helm${NC}"
fi

# Note: Les headers X-Forwarded-* sont configurés automatiquement par NGF
# Pas besoin de ConfigMaps manuels comme avec nginx-ingress
echo -e "${GREEN}✅ Headers X-Forwarded-* configurés automatiquement par NGF${NC}"

# Charger les secrets depuis SOPS si disponibles
echo -e "${YELLOW}▶ Chargement des secrets...${NC}"
SECRETS_FILE="$RHDEMO_ROOT/secrets/secrets-stagingkub.yml"
SECRETS_DECRYPTED="/tmp/secrets-stagingkub-decrypted.yml"

if [ -f "$SECRETS_FILE" ]; then
    # Déchiffrer les secrets avec SOPS
    if command -v sops &> /dev/null; then
        echo -e "${YELLOW}Déchiffrement des secrets avec SOPS...${NC}"
        sops -d "$SECRETS_FILE" > "$SECRETS_DECRYPTED"

        # Extraire les mots de passe depuis le fichier déchiffré avec yq (version apt)
        RHDEMO_DB_PASSWORD=$(yq -r '.rhdemo.datasource.password.pg' "$SECRETS_DECRYPTED")
        KEYCLOAK_DB_PASSWORD=$(yq -r '.keycloak.db.password' "$SECRETS_DECRYPTED")
        KEYCLOAK_ADMIN_PASSWORD=$(yq -r '.keycloak.admin.password // "admin"' "$SECRETS_DECRYPTED")

        rm "$SECRETS_DECRYPTED"
        echo -e "${GREEN}✅ Secrets déchiffrés${NC}"
    else
        echo -e "${YELLOW}⚠️  SOPS non disponible, utilisation de mots de passe par défaut${NC}"
        RHDEMO_DB_PASSWORD="changeme"
        KEYCLOAK_DB_PASSWORD="changeme"
        KEYCLOAK_ADMIN_PASSWORD="admin"
    fi
else
    echo -e "${YELLOW}⚠️  Fichier de secrets non trouvé, utilisation de mots de passe par défaut${NC}"
    RHDEMO_DB_PASSWORD="changeme"
    KEYCLOAK_DB_PASSWORD="changeme"
    KEYCLOAK_ADMIN_PASSWORD="admin"
fi



# Créer le namespace si nécessaire avec les labels Helm et Pod Security Admission
echo -e "${YELLOW}▶ Création du namespace rhdemo-stagingkub...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: rhdemo-stagingkub
  labels:
    app.kubernetes.io/managed-by: Helm
    # Pod Security Admission - mode warn/audit uniquement (pas d'enforce)
    # Les violations sont journalisées dans l'audit log et affichées comme warnings
    # sans bloquer les déploiements. Permet d'identifier les non-conformités
    # avant de passer au mode enforce (Phase 5).
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: latest
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: latest
  annotations:
    meta.helm.sh/release-name: rhdemo
    meta.helm.sh/release-namespace: rhdemo-stagingkub
EOF
echo -e "${GREEN}✅ Namespace créé avec labels Helm et PSA warn/audit restricted${NC}"

# Créer les secrets Kubernetes
echo -e "${YELLOW}▶ Création des secrets Kubernetes...${NC}"

# Secret pour rhdemo-db
kubectl create secret generic rhdemo-db-secret \
  --from-literal=password="$RHDEMO_DB_PASSWORD" \
  --namespace rhdemo-stagingkub \
  --dry-run=client -o yaml | kubectl apply -f -

# Secret pour keycloak-db
kubectl create secret generic keycloak-db-secret \
  --from-literal=password="$KEYCLOAK_DB_PASSWORD" \
  --namespace rhdemo-stagingkub \
  --dry-run=client -o yaml | kubectl apply -f -

# Secret pour keycloak admin
kubectl create secret generic keycloak-admin-secret \
  --from-literal=password="$KEYCLOAK_ADMIN_PASSWORD" \
  --namespace rhdemo-stagingkub \
  --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}✅ Secrets créés${NC}"

# Créer le secret pour secrets-rhdemo.yml (sera mis à jour par Jenkins)
echo -e "${YELLOW}▶ Création du secret pour secrets-rhdemo.yml...${NC}"
SECRETS_RHDEMO_FILE="$RHDEMO_ROOT/secrets/secrets-rhdemo.yml"
if [ -f "$SECRETS_RHDEMO_FILE" ]; then
    kubectl create secret generic rhdemo-app-secrets \
      --from-file=secrets-rhdemo.yml="$SECRETS_RHDEMO_FILE" \
      --namespace rhdemo-stagingkub \
      --dry-run=client -o yaml | kubectl apply -f -
    echo -e "${GREEN}✅ Secret secrets-rhdemo.yml créé${NC}"
else
    echo -e "${YELLOW}⚠️  Fichier secrets-rhdemo.yml non trouvé, création d'un secret vide${NC}"
    echo "# Placeholder" > /tmp/secrets-rhdemo.yml
    kubectl create secret generic rhdemo-app-secrets \
      --from-file=secrets-rhdemo.yml=/tmp/secrets-rhdemo.yml \
      --namespace rhdemo-stagingkub \
      --dry-run=client -o yaml | kubectl apply -f -
    rm /tmp/secrets-rhdemo.yml
fi

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION RBAC POUR JENKINS (accès limité au namespace)
# ═══════════════════════════════════════════════════════════════
echo -e "${YELLOW}▶ Configuration RBAC pour Jenkins...${NC}"

RBAC_DIR="$STAGINGKUB_DIR/rbac"
JENKINS_KUBECONFIG_DIR="$STAGINGKUB_DIR/jenkins-kubeconfig"
mkdir -p "$JENKINS_KUBECONFIG_DIR"

if [ -d "$RBAC_DIR" ]; then
    # Créer le namespace monitoring si nécessaire (pour les ServiceMonitors)
    if ! kubectl get namespace monitoring > /dev/null 2>&1; then
        echo -e "${YELLOW}  - Création du namespace 'monitoring'...${NC}"
        kubectl create namespace monitoring
    fi

    # Appliquer les ressources RBAC
    echo -e "${YELLOW}  - Application des ressources RBAC...${NC}"

    # ServiceAccount et Secret
    kubectl apply -f "$RBAC_DIR/jenkins-serviceaccount.yaml"

    # Role et RoleBinding dans rhdemo-stagingkub
    kubectl apply -f "$RBAC_DIR/jenkins-role.yaml"
    kubectl apply -f "$RBAC_DIR/jenkins-rolebinding.yaml"

    # ClusterRole et ClusterRoleBinding (pour PersistentVolumes)
    kubectl apply -f "$RBAC_DIR/jenkins-clusterrole.yaml"
    kubectl apply -f "$RBAC_DIR/jenkins-clusterrolebinding.yaml"

    # Role et RoleBinding dans monitoring (pour ServiceMonitors)
    kubectl apply -f "$RBAC_DIR/jenkins-monitoring-role.yaml"

    echo -e "${GREEN}✅ Ressources RBAC appliquées${NC}"

    # Attendre que le token du ServiceAccount soit créé
    echo -e "${YELLOW}  - Attente du token du ServiceAccount...${NC}"
    for i in {1..30}; do
        SA_TOKEN=$(kubectl get secret jenkins-deployer-token -n rhdemo-stagingkub -o jsonpath='{.data.token}' 2>/dev/null | base64 -d || true)
        if [ -n "$SA_TOKEN" ]; then
            break
        fi
        sleep 1
    done

    if [ -z "$SA_TOKEN" ]; then
        echo -e "${RED}❌ Impossible de récupérer le token du ServiceAccount après 30 secondes${NC}"
        exit 1
    fi

    # Récupérer le certificat CA
    CA_CERT=$(kubectl get secret jenkins-deployer-token -n rhdemo-stagingkub -o jsonpath='{.data.ca\.crt}')

    # Récupérer l'URL du serveur API
    API_SERVER="https://rhdemo-control-plane:6443"

    # Générer le kubeconfig RBAC pour Jenkins
    JENKINS_KUBECONFIG="$JENKINS_KUBECONFIG_DIR/kubeconfig-jenkins-rbac.yaml"
    cat > "$JENKINS_KUBECONFIG" <<KUBECONFIG_EOF
# Kubeconfig RBAC pour Jenkins
# Ce fichier contient un token avec des permissions limitées au namespace rhdemo-stagingkub
# Généré automatiquement par init-stagingkub.sh
#
# IMPORTANT: Ce fichier doit être ajouté comme credential Jenkins
# de type "Secret file" avec l'ID: kubeconfig-stagingkub
#
apiVersion: v1
kind: Config
preferences: {}

clusters:
  - name: kind-rhdemo
    cluster:
      certificate-authority-data: $CA_CERT
      server: $API_SERVER

contexts:
  - name: kind-rhdemo
    context:
      cluster: kind-rhdemo
      namespace: rhdemo-stagingkub
      user: jenkins-deployer

current-context: kind-rhdemo

users:
  - name: jenkins-deployer
    user:
      token: $SA_TOKEN
KUBECONFIG_EOF

    chmod 600 "$JENKINS_KUBECONFIG"
    echo -e "${GREEN}✅ Kubeconfig RBAC généré : $JENKINS_KUBECONFIG${NC}"

    # Vérifier les permissions du ServiceAccount
    echo -e "${YELLOW}  - Vérification des permissions RBAC...${NC}"
    if kubectl auth can-i get pods -n rhdemo-stagingkub --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Accès aux pods${NC}"
    else
        echo -e "${RED}    ✗ Accès aux pods refusé${NC}"
    fi

    if kubectl auth can-i create secrets -n rhdemo-stagingkub --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Création des secrets${NC}"
    else
        echo -e "${RED}    ✗ Création des secrets refusée${NC}"
    fi

    if kubectl auth can-i create persistentvolumes --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Création des PersistentVolumes${NC}"
    else
        echo -e "${RED}    ✗ Création des PersistentVolumes refusée${NC}"
    fi

    # Vérifier les permissions Gateway API
    if kubectl auth can-i create gateways.gateway.networking.k8s.io -n rhdemo-stagingkub --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Création des Gateways (Gateway API)${NC}"
    else
        echo -e "${RED}    ✗ Création des Gateways refusée${NC}"
    fi

    if kubectl auth can-i create httproutes.gateway.networking.k8s.io -n rhdemo-stagingkub --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Création des HTTPRoutes (Gateway API)${NC}"
    else
        echo -e "${RED}    ✗ Création des HTTPRoutes refusée${NC}"
    fi

    if kubectl auth can-i create snippetsfilters.gateway.nginx.org -n rhdemo-stagingkub --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Création des SnippetsFilters (NGF)${NC}"
    else
        echo -e "${RED}    ✗ Création des SnippetsFilters refusée${NC}"
    fi

    if kubectl auth can-i create ratelimitpolicies.gateway.nginx.org -n rhdemo-stagingkub --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Création des RateLimitPolicies (NGF)${NC}"
    else
        echo -e "${RED}    ✗ Création des RateLimitPolicies refusée${NC}"
    fi

    # Vérifier le NON-accès aux autres namespaces
    if ! kubectl auth can-i get pods -n kube-system --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Pas d'accès à kube-system (sécurité OK)${NC}"
    else
        echo -e "${YELLOW}    ⚠ Accès à kube-system détecté${NC}"
    fi

    # ═══════════════════════════════════════════════════════════════
    # CONFIGURATION RBAC POUR JENKINS-INFRA-UPGRADER (mise à jour en place
    # des composants d'infra — Option 3, ServiceAccount dédié et distinct
    # de jenkins-deployer, cf. docs/STAGINGKUB_REBUILD_PIPELINE.md étape 3)
    # ═══════════════════════════════════════════════════════════════
    echo -e "${YELLOW}▶ Configuration RBAC pour jenkins-infra-upgrader...${NC}"

    # Namespaces nécessaires (monitoring déjà créé ci-dessus)
    # cilium-release : stockage dédié de l'état Helm de la release Cilium
    # (secrets sh.helm.release.v1.*), séparé de kube-system — voir
    # jenkins-infra-upgrader-cilium-release-role.yaml et
    # install-or-upgrade-cilium.sh.
    for ns in nginx-gateway loki-stack cilium-release; do
        if ! kubectl get namespace "$ns" > /dev/null 2>&1; then
            echo -e "${YELLOW}  - Création du namespace '$ns'...${NC}"
            kubectl create namespace "$ns"
        fi
    done

    kubectl apply -f "$RBAC_DIR/jenkins-infra-upgrader-serviceaccount.yaml"
    kubectl apply -f "$RBAC_DIR/jenkins-infra-upgrader-nginx-gateway-role.yaml"
    kubectl apply -f "$RBAC_DIR/jenkins-infra-upgrader-loki-stack-role.yaml"
    kubectl apply -f "$RBAC_DIR/jenkins-infra-upgrader-monitoring-role.yaml"
    kubectl apply -f "$RBAC_DIR/jenkins-infra-upgrader-kube-system-role.yaml"
    kubectl apply -f "$RBAC_DIR/jenkins-infra-upgrader-cilium-release-role.yaml"
    kubectl apply -f "$RBAC_DIR/jenkins-infra-upgrader-clusterrole.yaml"
    echo -e "${GREEN}✅ Ressources RBAC jenkins-infra-upgrader appliquées${NC}"

    echo -e "${YELLOW}  - Attente du token du ServiceAccount jenkins-infra-upgrader...${NC}"
    for i in {1..30}; do
        INFRA_SA_TOKEN=$(kubectl get secret jenkins-infra-upgrader-token -n rhdemo-stagingkub -o jsonpath='{.data.token}' 2>/dev/null | base64 -d || true)
        if [ -n "$INFRA_SA_TOKEN" ]; then
            break
        fi
        sleep 1
    done

    if [ -z "$INFRA_SA_TOKEN" ]; then
        echo -e "${RED}❌ Impossible de récupérer le token du ServiceAccount jenkins-infra-upgrader après 30 secondes${NC}"
        exit 1
    fi

    INFRA_CA_CERT=$(kubectl get secret jenkins-infra-upgrader-token -n rhdemo-stagingkub -o jsonpath='{.data.ca\.crt}')

    INFRA_JENKINS_KUBECONFIG="$JENKINS_KUBECONFIG_DIR/kubeconfig-jenkins-infra-upgrader-rbac.yaml"
    cat > "$INFRA_JENKINS_KUBECONFIG" <<KUBECONFIG_EOF
# Kubeconfig RBAC pour jenkins-infra-upgrader (mise à jour en place des
# composants d'infra — distinct de kubeconfig-jenkins-rbac.yaml/jenkins-deployer)
# Généré automatiquement par init-stagingkub.sh
#
# IMPORTANT: Ce fichier doit être ajouté comme credential Jenkins
# de type "Secret file" avec l'ID: kubeconfig-stagingkub-infra-upgrader
#
apiVersion: v1
kind: Config
preferences: {}

clusters:
  - name: kind-rhdemo
    cluster:
      certificate-authority-data: $INFRA_CA_CERT
      server: $API_SERVER

contexts:
  - name: kind-rhdemo
    context:
      cluster: kind-rhdemo
      namespace: rhdemo-stagingkub
      user: jenkins-infra-upgrader

current-context: kind-rhdemo

users:
  - name: jenkins-infra-upgrader
    user:
      token: $INFRA_SA_TOKEN
KUBECONFIG_EOF

    chmod 600 "$INFRA_JENKINS_KUBECONFIG"
    echo -e "${GREEN}✅ Kubeconfig RBAC jenkins-infra-upgrader généré : $INFRA_JENKINS_KUBECONFIG${NC}"

    # Vérification des permissions clés (accordées)
    echo -e "${YELLOW}  - Vérification des permissions RBAC jenkins-infra-upgrader...${NC}"
    if kubectl auth can-i update daemonsets/cilium -n kube-system --as=system:serviceaccount:rhdemo-stagingkub:jenkins-infra-upgrader > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Mise à jour du DaemonSet cilium (kube-system, nommé)${NC}"
    else
        echo -e "${RED}    ✗ Mise à jour du DaemonSet cilium refusée${NC}"
    fi

    if kubectl auth can-i create deployments -n nginx-gateway --as=system:serviceaccount:rhdemo-stagingkub:jenkins-infra-upgrader > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Gestion des Deployments (nginx-gateway)${NC}"
    else
        echo -e "${RED}    ✗ Gestion des Deployments (nginx-gateway) refusée${NC}"
    fi

    if kubectl auth can-i update customresourcedefinitions/httproutes.gateway.networking.k8s.io --as=system:serviceaccount:rhdemo-stagingkub:jenkins-infra-upgrader > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Mise à jour de la CRD httproutes.gateway.networking.k8s.io (nommée)${NC}"
    else
        echo -e "${RED}    ✗ Mise à jour de la CRD httproutes.gateway.networking.k8s.io refusée${NC}"
    fi

    if kubectl auth can-i list secrets -n cilium-release --as=system:serviceaccount:rhdemo-stagingkub:jenkins-infra-upgrader > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Gestion des secrets de release Helm Cilium (cilium-release)${NC}"
    else
        echo -e "${RED}    ✗ Gestion des secrets de release Helm Cilium (cilium-release) refusée${NC}"
    fi

    # Vérification des refus attendus (garde-fous)
    if ! kubectl auth can-i get pods -n rhdemo-stagingkub --as=system:serviceaccount:rhdemo-stagingkub:jenkins-infra-upgrader > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Pas d'accès à rhdemo-stagingkub (aucun composant géré n'y vit — sécurité OK)${NC}"
    else
        echo -e "${YELLOW}    ⚠ Accès à rhdemo-stagingkub détecté (inattendu)${NC}"
    fi

    # Note : get/list/watch sur pods et pods/log EST générique dans kube-system
    # (compromis assumé, cf. jenkins-infra-upgrader-kube-system-role.yaml) —
    # ce garde-fou porte donc sur les secrets, jamais accessibles sans
    # resourceNames dans kube-system (cf. namespace cilium-release ci-dessus).
    if ! kubectl auth can-i list secrets -n kube-system --as=system:serviceaccount:rhdemo-stagingkub:jenkins-infra-upgrader > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Pas d'accès générique aux secrets de kube-system (nommés uniquement)${NC}"
    else
        echo -e "${YELLOW}    ⚠ Accès générique aux secrets de kube-system détecté (inattendu)${NC}"
    fi

    if ! kubectl auth can-i create customresourcedefinitions --as=system:serviceaccount:rhdemo-stagingkub:jenkins-infra-upgrader > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Pas de création libre de CRD (sécurité OK)${NC}"
    else
        echo -e "${YELLOW}    ⚠ Création libre de CRD détectée (inattendu)${NC}"
    fi

    if ! kubectl auth can-i update clusterroles/jenkins-infra-upgrader-cluster-role --as=system:serviceaccount:rhdemo-stagingkub:jenkins-infra-upgrader > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Pas d'auto-modification de son propre ClusterRole (sécurité OK)${NC}"
    else
        echo -e "${RED}    ✗ Auto-modification de son propre ClusterRole possible — À CORRIGER${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Dossier RBAC non trouvé : $RBAC_DIR${NC}"
    echo -e "${YELLOW}   Les ressources RBAC ne seront pas créées${NC}"
fi

# Générer les certificats SSL
echo -e "${YELLOW}▶ Génération des certificats SSL...${NC}"
CERTS_DIR="$STAGINGKUB_DIR/certs"
mkdir -p "$CERTS_DIR"

if [ ! -f "$CERTS_DIR/tls.crt" ]; then
    # Générer un certificat self-signed pour le domaine intra.leuwen-lc.fr
    # Note: Ce certificat auto-signé est utilisé quand Let's Encrypt n'est pas disponible
    # Avec Let's Encrypt (cert-manager), le secret intra-wildcard-tls est utilisé à la place
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout "$CERTS_DIR/tls.key" \
      -out "$CERTS_DIR/tls.crt" \
      -subj "/CN=*.intra.leuwen-lc.fr/O=RHDemo" \
      -addext "subjectAltName=DNS:rhdemo-stagingkub.intra.leuwen-lc.fr,DNS:keycloak-stagingkub.intra.leuwen-lc.fr,DNS:grafana-stagingkub.intra.leuwen-lc.fr"
    echo -e "${GREEN}✅ Certificats SSL auto-signés générés${NC}"
else
    echo -e "${GREEN}✅ Certificats SSL déjà existants${NC}"
fi

# Créer le secret TLS dans nginx-gateway pour le Gateway partagé
kubectl create secret tls shared-tls-cert \
  --cert="$CERTS_DIR/tls.crt" \
  --key="$CERTS_DIR/tls.key" \
  --namespace nginx-gateway \
  --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✅ Secret TLS créé (nginx-gateway)${NC}"

# ═══════════════════════════════════════════════════════════════
# Création du Gateway partagé
# ═══════════════════════════════════════════════════════════════
# Ce Gateway est le point d'entrée unique pour tout le trafic HTTPS.
# Il permet aux HTTPRoutes de différents namespaces de l'utiliser.
# ═══════════════════════════════════════════════════════════════
echo -e "${YELLOW}▶ Création du Gateway partagé...${NC}"
SHARED_GATEWAY_FILE="$STAGINGKUB_DIR/shared-gateway.yaml"

if [ -f "$SHARED_GATEWAY_FILE" ]; then
    kubectl apply -f "$SHARED_GATEWAY_FILE"
    echo -e "${GREEN}✅ Gateway partagé créé${NC}"

    # Attendre que NGF crée le service shared-gateway-nginx (créé dynamiquement)
    echo -e "${YELLOW}  - Attente du service shared-gateway-nginx...${NC}"
    for i in {1..60}; do
        if kubectl get svc shared-gateway-nginx -n nginx-gateway &> /dev/null; then
            break
        fi
        echo -n "."
        sleep 1
    done
    echo ""

    # Patcher le NodePort pour correspondre au mapping KinD (hostPort 443 → containerPort 32616)
    # NGF crée un NodePort dynamique, mais KinD attend un port fixe configuré dans kind-config.yaml
    echo -e "${YELLOW}  - Configuration du NodePort HTTPS (32616)...${NC}"
    if kubectl get svc shared-gateway-nginx -n nginx-gateway &> /dev/null; then
        # Ciblage spécifique du port 443 pour éviter les erreurs d'index
        CURRENT_NODEPORT=$(kubectl get svc shared-gateway-nginx -n nginx-gateway -o jsonpath='{.spec.ports[?(@.port==443)].nodePort}')
        if [ "$CURRENT_NODEPORT" != "32616" ]; then
            # Patch JSON pour modifier le nodePort du premier (et seul) port
            # Note: --type='merge' ne fonctionne pas pour les éléments de liste
            kubectl patch svc shared-gateway-nginx -n nginx-gateway --type='json' \
                -p='[{"op":"replace","path":"/spec/ports/0/nodePort","value":32616}]'
            echo -e "${GREEN}    ✓ NodePort HTTPS patché (${CURRENT_NODEPORT} → 32616)${NC}"
        else
            echo -e "${GREEN}    ✓ NodePort HTTPS déjà configuré (32616)${NC}"
        fi
    else
        echo -e "${RED}    ✗ Service shared-gateway-nginx non trouvé${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Fichier shared-gateway.yaml non trouvé : $SHARED_GATEWAY_FILE${NC}"
fi

# Mettre à jour /etc/hosts si nécessaire
echo -e "${YELLOW}▶ Vérification de /etc/hosts...${NC}"
if ! grep -q "rhdemo-stagingkub.intra.leuwen-lc.fr" /etc/hosts; then
    echo -e "${YELLOW}Ajout des entrées DNS dans /etc/hosts (nécessite sudo)...${NC}"
    echo "127.0.0.1 rhdemo-stagingkub.intra.leuwen-lc.fr" | sudo tee -a /etc/hosts
    echo "127.0.0.1 keycloak-stagingkub.intra.leuwen-lc.fr" | sudo tee -a /etc/hosts
    echo -e "${GREEN}✅ Entrées DNS ajoutées${NC}"
else
    echo -e "${GREEN}✅ Entrées DNS déjà présentes${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Initialisation de stagingkub terminée${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}📦 Registry Docker local configuré :${NC}"
echo -e "  • Nom: ${BLUE}${REGISTRY_NAME}${NC}"
echo -e "  • URL: ${BLUE}http://localhost:${REGISTRY_PORT}${NC}"
echo -e "  • Status: ${GREEN}Actif et connecté au cluster KinD${NC}"
echo ""
echo -e "${YELLOW}Prochaines étapes :${NC}"
echo -e "  1. Construire l'image Docker de l'application"
echo -e "  2. Tagger pour le registry : ${BLUE}docker tag rhdemo-api:VERSION localhost:5000/rhdemo-api:VERSION${NC}"
echo -e "  3. Pousser vers le registry : ${BLUE}docker push localhost:5000/rhdemo-api:VERSION${NC}"
echo -e "  4. Déployer avec Helm : ${BLUE}./scripts/deploy.sh VERSION${NC}"
echo ""
echo -e "${YELLOW}💡 Commandes utiles du registry :${NC}"
echo -e "  • Voir les images : ${BLUE}curl http://localhost:5000/v2/_catalog${NC}"
echo -e "  • Voir les tags : ${BLUE}curl http://localhost:5000/v2/rhdemo-api/tags/list${NC}"
echo ""
echo -e "${YELLOW}🔐 Configuration Jenkins (RBAC) :${NC}"
echo -e "  Deux kubeconfigs RBAC ont été générés, avec des permissions limitées et distinctes."
echo -e "  Pour configurer Jenkins :"
echo -e ""
echo -e "  1. ${BLUE}Accédez à Jenkins > Manage Jenkins > Credentials${NC}"
echo -e "  2. ${BLUE}Ajoutez un credential de type 'Secret file'${NC}"
echo -e "  3. ${BLUE}ID: kubeconfig-stagingkub${NC} (déploiement applicatif, RHDemo-CD)"
echo -e "     ${BLUE}Fichier: $STAGINGKUB_DIR/jenkins-kubeconfig/kubeconfig-jenkins-rbac.yaml${NC}"
echo -e "  4. ${BLUE}ID: kubeconfig-stagingkub-infra-upgrader${NC} (mise à jour en place de l'infra, RHDemo-Stagingkub-Upgrade-Deploy)"
echo -e "     ${BLUE}Fichier: $STAGINGKUB_DIR/jenkins-kubeconfig/kubeconfig-jenkins-infra-upgrader-rbac.yaml${NC}"
echo ""
echo -e "  Documentation: ${BLUE}$RBAC_DIR/README.md${NC}"
echo ""
