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

# Créer et configurer le registry Docker local
echo -e "${YELLOW}▶ Configuration du registry Docker local...${NC}"
REGISTRY_NAME="kind-registry"
REGISTRY_PORT="5000"

# Vérifier si un registry tourne déjà sur le port 5000
EXISTING_REGISTRY=$(docker ps --filter "publish=${REGISTRY_PORT}" --format '{{.Names}}' | head -n 1)

if [ -n "$EXISTING_REGISTRY" ]; then
    echo -e "${GREEN}✅ Un registry Docker est déjà actif sur le port ${REGISTRY_PORT} : '${EXISTING_REGISTRY}'${NC}"
    REGISTRY_NAME="$EXISTING_REGISTRY"
else
    # Vérifier si le registry 'kind-registry' existe mais est arrêté
    if docker ps -a --format '{{.Names}}' | grep -q "^${REGISTRY_NAME}$"; then
        echo -e "${YELLOW}Registry '${REGISTRY_NAME}' existe mais est arrêté${NC}"
        echo -e "${YELLOW}Démarrage du registry...${NC}"
        docker start ${REGISTRY_NAME}
        sleep 2
        echo -e "${GREEN}✅ Registry Docker local démarré${NC}"
    else
        # Aucun registry n'existe, on en crée un nouveau
        echo -e "${YELLOW}Création du registry Docker local sur le port ${REGISTRY_PORT}...${NC}"
        if docker run -d \
            --name ${REGISTRY_NAME} \
            --restart=always \
            -p ${REGISTRY_PORT}:5000 \
            registry:2 > /dev/null; then
            sleep 2
            echo -e "${GREEN}✅ Registry Docker local créé et actif${NC}"
        else
            echo -e "${RED}❌ Erreur lors de la création du registry${NC}"
            echo -e "${YELLOW}Le port ${REGISTRY_PORT} est peut-être occupé. Vérifiez avec :${NC}"
            echo "  docker ps -a --filter 'publish=${REGISTRY_PORT}'"
            echo "  sudo ss -ltnp 'sport = :${REGISTRY_PORT}'"
            exit 1
        fi
    fi
fi

# Vérifier que le registry est accessible
echo -n "Vérification de l'accessibilité du registry... "
if curl -f http://localhost:${REGISTRY_PORT}/v2/ &> /dev/null; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ ERREUR${NC}"
    echo -e "${RED}Le registry n'est pas accessible sur http://localhost:${REGISTRY_PORT}${NC}"
    exit 1
fi

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

    kind create cluster --config "${KIND_CONFIG_FILE}"
    echo -e "${GREEN}✅ Cluster KinD 'rhdemo' créé avec persistance des données${NC}"

    # Connecter le registry au réseau KinD
    echo -e "${YELLOW}Connexion du registry au réseau KinD...${NC}"
    docker network connect kind ${REGISTRY_NAME} 2>/dev/null || echo "Registry déjà connecté au réseau kind"
    echo -e "${GREEN}✅ Registry connecté au cluster KinD${NC}"
else
    echo -e "${GREEN}✅ Cluster KinD 'rhdemo' trouvé${NC}"

    # Vérifier si le registry est connecté au réseau kind
    if ! docker network inspect kind | grep -q "${REGISTRY_NAME}"; then
        echo -e "${YELLOW}Connexion du registry au réseau KinD...${NC}"
        docker network connect kind ${REGISTRY_NAME}
        echo -e "${GREEN}✅ Registry connecté au cluster KinD${NC}"
    else
        echo -e "${GREEN}✅ Registry déjà connecté au réseau KinD${NC}"
    fi
fi

# Définir le contexte kubectl
kubectl config use-context kind-rhdemo

# Attendre que le nœud KinD soit prêt
echo -e "${YELLOW}▶ Attente que le nœud KinD soit prêt...${NC}"
kubectl wait --for=condition=ready node --all --timeout=120s
echo -e "${GREEN}✅ Nœud KinD prêt${NC}"

# Installer Nginx Ingress Controller si nécessaire
echo -e "${YELLOW}▶ Vérification de Nginx Ingress Controller...${NC}"
if ! kubectl get namespace ingress-nginx &> /dev/null; then
    echo -e "${YELLOW}Installation de Nginx Ingress Controller...${NC}"
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
    INGRESS_INSTALLED=true
else
    echo -e "${GREEN}✅ Nginx Ingress Controller déjà installé${NC}"
    INGRESS_INSTALLED=false
fi

# Attendre que l'Ingress Controller soit prêt (que ce soit une nouvelle installation ou existant)
echo -e "${YELLOW}Attente du démarrage de Nginx Ingress Controller (jusqu'à 3 minutes)...${NC}"

# Attendre d'abord que le pod existe (jusqu'à 2 minutes)
echo -n "  - Attente de la création du pod"
POD_FOUND=false
for i in {1..120}; do
    if kubectl get pod -l app.kubernetes.io/component=controller -n ingress-nginx &> /dev/null; then
        POD_FOUND=true
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

if [ "$POD_FOUND" = false ]; then
    echo -e "${RED}❌ Le pod Ingress Controller n'a pas été créé${NC}"
    kubectl get pods -n ingress-nginx
    exit 1
fi

# Maintenant attendre que le pod soit ready
echo "  - Attente que le pod soit prêt..."
if kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s > /dev/null 2>&1; then
    if [ "$INGRESS_INSTALLED" = true ]; then
        echo -e "${GREEN}✅ Nginx Ingress Controller installé et prêt${NC}"
    else
        echo -e "${GREEN}✅ Nginx Ingress Controller prêt${NC}"
    fi
else
    echo -e "${RED}❌ Timeout lors de l'attente de l'Ingress Controller${NC}"
    echo -e "${YELLOW}Vérification de l'état des pods...${NC}"
    kubectl get pods -n ingress-nginx
    kubectl describe pod -l app.kubernetes.io/component=controller -n ingress-nginx | tail -50
    exit 1
fi

# Configurer les NodePorts fixes pour l'Ingress Controller
# Ces NodePorts correspondent aux ports mappés dans la configuration KinD :
# - NodePort 31792 (HTTP) → Host port 80
# - NodePort 32616 (HTTPS) → Host port 443
echo -e "${YELLOW}▶ Configuration des NodePorts pour l'Ingress Controller...${NC}"
kubectl patch svc ingress-nginx-controller -n ingress-nginx -p '{"spec":{"type":"NodePort","ports":[{"name":"http","port":80,"protocol":"TCP","targetPort":"http","nodePort":31792},{"name":"https","port":443,"protocol":"TCP","targetPort":"https","nodePort":32616}]}}'
echo -e "${GREEN}✅ NodePorts configurés (HTTP: 31792→80, HTTPS: 32616→443)${NC}"

# Configurer nginx-ingress pour forcer les headers X-Forwarded-Port et X-Forwarded-Proto
# Ceci permet à Spring Boot de construire les URLs OAuth2 avec le bon port (443)
echo -e "${YELLOW}▶ Configuration des headers X-Forwarded-* dans nginx-ingress...${NC}"
kubectl patch configmap ingress-nginx-controller -n ingress-nginx --type merge -p '{"data":{"use-forwarded-headers":"true","compute-full-forwarded-for":"true","forwarded-for-header":"X-Forwarded-For"}}'

# Ajouter la configuration pour forcer X-Forwarded-Port à 443 pour HTTPS
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: ingress-nginx-controller
  namespace: ingress-nginx
data:
  use-forwarded-headers: "true"
  compute-full-forwarded-for: "true"
  forwarded-for-header: "X-Forwarded-For"
  http-snippet: |
    map \$server_port \$custom_forwarded_port {
      443 443;
      default \$server_port;
    }
  proxy-set-headers: "ingress-nginx/custom-headers"
EOF

# Créer une ConfigMap pour les headers personnalisés
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: custom-headers
  namespace: ingress-nginx
data:
  X-Forwarded-Port: "443"
  X-Forwarded-Proto: "https"
EOF

echo -e "${GREEN}✅ Headers X-Forwarded-* configurés dans nginx-ingress${NC}"

# Redémarrer le contrôleur nginx-ingress pour appliquer les changements
echo -e "${YELLOW}▶ Redémarrage du contrôleur nginx-ingress...${NC}"
kubectl rollout restart deployment ingress-nginx-controller -n ingress-nginx
kubectl rollout status deployment ingress-nginx-controller -n ingress-nginx --timeout=60s
echo -e "${GREEN}✅ Contrôleur nginx-ingress redémarré${NC}"

# Charger les secrets depuis SOPS si disponibles
echo -e "${YELLOW}▶ Chargement des secrets...${NC}"
SECRETS_FILE="$RHDEMO_ROOT/secrets/secrets-stagingkub.yml"
SECRETS_DECRYPTED="/tmp/secrets-stagingkub-decrypted.yml"

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



# Créer le namespace si nécessaire avec les labels Helm
echo -e "${YELLOW}▶ Création du namespace rhdemo-stagingkub...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: rhdemo-stagingkub
  labels:
    app.kubernetes.io/managed-by: Helm
  annotations:
    meta.helm.sh/release-name: rhdemo
    meta.helm.sh/release-namespace: rhdemo-stagingkub
EOF
echo -e "${GREEN}✅ Namespace créé avec labels Helm${NC}"

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

# Générer les certificats SSL
echo -e "${YELLOW}▶ Génération des certificats SSL...${NC}"
CERTS_DIR="$STAGINGKUB_DIR/certs"
mkdir -p "$CERTS_DIR"

if [ ! -f "$CERTS_DIR/tls.crt" ]; then
    # Générer un certificat self-signed
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout "$CERTS_DIR/tls.key" \
      -out "$CERTS_DIR/tls.crt" \
      -subj "/CN=*.stagingkub.local/O=RHDemo" \
      -addext "subjectAltName=DNS:rhdemo.stagingkub.local,DNS:keycloak.stagingkub.local"
    echo -e "${GREEN}✅ Certificats SSL générés${NC}"
else
    echo -e "${GREEN}✅ Certificats SSL déjà existants${NC}"
fi

# Créer le secret TLS
kubectl create secret tls rhdemo-tls-cert \
  --cert="$CERTS_DIR/tls.crt" \
  --key="$CERTS_DIR/tls.key" \
  --namespace rhdemo-stagingkub \
  --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✅ Secret TLS créé${NC}"

# Mettre à jour /etc/hosts si nécessaire
echo -e "${YELLOW}▶ Vérification de /etc/hosts...${NC}"
if ! grep -q "rhdemo.stagingkub.local" /etc/hosts; then
    echo -e "${YELLOW}Ajout des entrées DNS dans /etc/hosts (nécessite sudo)...${NC}"
    echo "127.0.0.1 rhdemo.stagingkub.local" | sudo tee -a /etc/hosts
    echo "127.0.0.1 keycloak.stagingkub.local" | sudo tee -a /etc/hosts
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
