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

    CLUSTER_CREATED=false
fi

# ═══════════════════════════════════════════════════════════════
# Configuration HTTPS du registry dans le nœud KinD
# ═══════════════════════════════════════════════════════════════
echo -e "${YELLOW}▶ Configuration du certificat HTTPS dans le nœud KinD...${NC}"

# Copier le certificat CA dans le nœud KinD
docker cp "$REGISTRY_CERT" rhdemo-control-plane:/usr/local/share/ca-certificates/kind-registry.crt

# Mettre à jour les CA du nœud
docker exec rhdemo-control-plane update-ca-certificates > /dev/null 2>&1

# Vérifier si containerd utilise encore HTTP
if docker exec rhdemo-control-plane grep -q "http://kind-registry:5000" /etc/containerd/config.toml 2>/dev/null; then
    echo -e "${YELLOW}  - Mise à jour de containerd pour HTTPS...${NC}"
    docker exec rhdemo-control-plane sed -i 's|http://kind-registry:5000|https://kind-registry:5000|g' /etc/containerd/config.toml
    docker exec rhdemo-control-plane systemctl restart containerd
    echo -e "${GREEN}✅ Containerd configuré pour HTTPS${NC}"
else
    echo -e "${GREEN}✅ Containerd déjà configuré pour HTTPS${NC}"
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
  - name: jenkins-rhdemo-stagingkub
    context:
      cluster: kind-rhdemo
      namespace: rhdemo-stagingkub
      user: jenkins-deployer

current-context: jenkins-rhdemo-stagingkub

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

    # Vérifier le NON-accès aux autres namespaces
    if ! kubectl auth can-i get pods -n kube-system --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer > /dev/null 2>&1; then
        echo -e "${GREEN}    ✓ Pas d'accès à kube-system (sécurité OK)${NC}"
    else
        echo -e "${YELLOW}    ⚠ Accès à kube-system détecté${NC}"
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
echo -e "${YELLOW}🔐 Configuration Jenkins (RBAC) :${NC}"
echo -e "  Le kubeconfig RBAC a été généré avec des permissions limitées."
echo -e "  Pour configurer Jenkins :"
echo -e ""
echo -e "  1. ${BLUE}Accédez à Jenkins > Manage Jenkins > Credentials${NC}"
echo -e "  2. ${BLUE}Ajoutez un credential de type 'Secret file'${NC}"
echo -e "  3. ${BLUE}ID: kubeconfig-stagingkub${NC}"
echo -e "  4. ${BLUE}Fichier: $STAGINGKUB_DIR/jenkins-kubeconfig/kubeconfig-jenkins-rbac.yaml${NC}"
echo ""
echo -e "  Documentation: ${BLUE}$RBAC_DIR/README.md${NC}"
echo ""
