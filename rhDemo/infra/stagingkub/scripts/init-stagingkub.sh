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

# Vérifier que le cluster KinD 'rhdemo' existe
echo -e "${YELLOW}▶ Vérification du cluster KinD 'rhdemo'...${NC}"
if ! kind get clusters | grep -q "^rhdemo$"; then
    echo -e "${RED}❌ Le cluster KinD 'rhdemo' n'existe pas.${NC}"
    echo -e "${YELLOW}Création du cluster KinD 'rhdemo'...${NC}"

    # Créer un fichier de configuration KinD temporaire
    cat <<EOF > /tmp/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: rhdemo
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30080
    hostPort: 80
    protocol: TCP
  - containerPort: 30443
    hostPort: 443
    protocol: TCP
EOF

    kind create cluster --config /tmp/kind-config.yaml
    rm /tmp/kind-config.yaml
    echo -e "${GREEN}✅ Cluster KinD 'rhdemo' créé${NC}"
else
    echo -e "${GREEN}✅ Cluster KinD 'rhdemo' trouvé${NC}"
fi

# Définir le contexte kubectl
kubectl config use-context kind-rhdemo

# Installer Nginx Ingress Controller si nécessaire
echo -e "${YELLOW}▶ Vérification de Nginx Ingress Controller...${NC}"
if ! kubectl get namespace ingress-nginx &> /dev/null; then
    echo -e "${YELLOW}Installation de Nginx Ingress Controller...${NC}"
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

    # Attendre que l'Ingress Controller soit prêt
    echo -e "${YELLOW}Attente du démarrage de Nginx Ingress Controller...${NC}"
    kubectl wait --namespace ingress-nginx \
      --for=condition=ready pod \
      --selector=app.kubernetes.io/component=controller \
      --timeout=90s
    echo -e "${GREEN}✅ Nginx Ingress Controller installé${NC}"
else
    echo -e "${GREEN}✅ Nginx Ingress Controller déjà installé${NC}"
fi

# Charger les secrets depuis SOPS si disponibles
echo -e "${YELLOW}▶ Chargement des secrets...${NC}"
SECRETS_FILE="$RHDEMO_ROOT/secrets/secrets-staging.yml"
SECRETS_DECRYPTED="/tmp/secrets-staging-decrypted.yml"

if [ -f "$SECRETS_FILE" ]; then
    # Déchiffrer les secrets avec SOPS
    if command -v sops &> /dev/null; then
        echo -e "${YELLOW}Déchiffrement des secrets avec SOPS...${NC}"
        sops -d "$SECRETS_FILE" > "$SECRETS_DECRYPTED"

        # Extraire les mots de passe depuis le fichier déchiffré
        RHDEMO_DB_PASSWORD=$(grep 'rhdemo-db-password:' "$SECRETS_DECRYPTED" | awk '{print $2}')
        KEYCLOAK_DB_PASSWORD=$(grep 'keycloak-db-password:' "$SECRETS_DECRYPTED" | awk '{print $2}')
        KEYCLOAK_ADMIN_PASSWORD=$(grep 'keycloak-admin-password:' "$SECRETS_DECRYPTED" | awk '{print $2}')

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

# Créer le namespace si nécessaire
echo -e "${YELLOW}▶ Création du namespace rhdemo-staging...${NC}"
kubectl create namespace rhdemo-staging --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✅ Namespace créé${NC}"

# Créer les secrets Kubernetes
echo -e "${YELLOW}▶ Création des secrets Kubernetes...${NC}"

# Secret pour rhdemo-db
kubectl create secret generic rhdemo-db-secret \
  --from-literal=password="$RHDEMO_DB_PASSWORD" \
  --namespace rhdemo-staging \
  --dry-run=client -o yaml | kubectl apply -f -

# Secret pour keycloak-db
kubectl create secret generic keycloak-db-secret \
  --from-literal=password="$KEYCLOAK_DB_PASSWORD" \
  --namespace rhdemo-staging \
  --dry-run=client -o yaml | kubectl apply -f -

# Secret pour keycloak admin
kubectl create secret generic keycloak-admin-secret \
  --from-literal=password="$KEYCLOAK_ADMIN_PASSWORD" \
  --namespace rhdemo-staging \
  --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}✅ Secrets créés${NC}"

# Créer le secret pour secrets-rhdemo.yml (sera mis à jour par Jenkins)
echo -e "${YELLOW}▶ Création du secret pour secrets-rhdemo.yml...${NC}"
SECRETS_RHDEMO_FILE="$RHDEMO_ROOT/secrets/secrets-rhdemo.yml"
if [ -f "$SECRETS_RHDEMO_FILE" ]; then
    kubectl create secret generic rhdemo-app-secrets \
      --from-file=secrets-rhdemo.yml="$SECRETS_RHDEMO_FILE" \
      --namespace rhdemo-staging \
      --dry-run=client -o yaml | kubectl apply -f -
    echo -e "${GREEN}✅ Secret secrets-rhdemo.yml créé${NC}"
else
    echo -e "${YELLOW}⚠️  Fichier secrets-rhdemo.yml non trouvé, création d'un secret vide${NC}"
    echo "# Placeholder" > /tmp/secrets-rhdemo.yml
    kubectl create secret generic rhdemo-app-secrets \
      --from-file=secrets-rhdemo.yml=/tmp/secrets-rhdemo.yml \
      --namespace rhdemo-staging \
      --dry-run=client -o yaml | kubectl apply -f -
    rm /tmp/secrets-rhdemo.yml
fi

# Générer les certificats SSL
echo -e "${YELLOW}▶ Génération des certificats SSL...${NC}"
CERTS_DIR="$STAGINGKUB_DIR/certs"
mkdir -p "$CERTS_DIR"

if [ ! -f "$CERTS_DIR/tls.crt" ]; then
    # Générer un certificat self-signed
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout "$CERTS_DIR/tls.key" \
      -out "$CERTS_DIR/tls.crt" \
      -subj "/CN=*.staging.local/O=RHDemo" \
      -addext "subjectAltName=DNS:rhdemo.staging.local,DNS:keycloak.staging.local"
    echo -e "${GREEN}✅ Certificats SSL générés${NC}"
else
    echo -e "${GREEN}✅ Certificats SSL déjà existants${NC}"
fi

# Créer le secret TLS
kubectl create secret tls rhdemo-tls-cert \
  --cert="$CERTS_DIR/tls.crt" \
  --key="$CERTS_DIR/tls.key" \
  --namespace rhdemo-staging \
  --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✅ Secret TLS créé${NC}"

# Mettre à jour /etc/hosts si nécessaire
echo -e "${YELLOW}▶ Vérification de /etc/hosts...${NC}"
if ! grep -q "rhdemo.staging.local" /etc/hosts; then
    echo -e "${YELLOW}Ajout des entrées DNS dans /etc/hosts (nécessite sudo)...${NC}"
    echo "127.0.0.1 rhdemo.staging.local" | sudo tee -a /etc/hosts
    echo "127.0.0.1 keycloak.staging.local" | sudo tee -a /etc/hosts
    echo -e "${GREEN}✅ Entrées DNS ajoutées${NC}"
else
    echo -e "${GREEN}✅ Entrées DNS déjà présentes${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Initialisation de stagingkub terminée${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Prochaines étapes :${NC}"
echo -e "  1. Construire l'image Docker de l'application"
echo -e "  2. Charger l'image dans KinD : ${BLUE}kind load docker-image rhdemo-api:VERSION --name rhdemo${NC}"
echo -e "  3. Déployer avec Helm : ${BLUE}helm install rhdemo $HELM_CHART_DIR -n rhdemo-staging${NC}"
echo ""
