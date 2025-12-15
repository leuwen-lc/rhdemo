#!/bin/bash

# ════════════════════════════════════════════════════════════════
# Script d'initialisation Keycloak pour l'environnement stagingkub
# ════════════════════════════════════════════════════════════════
#
# Ce script permet d'initialiser Keycloak dans l'environnement
# Kubernetes stagingkub en utilisant rhDemoInitKeycloak.
#
# Utilisation:
#   ./init-keycloak-stagingkub.sh
#
# Prérequis:
#   - Cluster Kubernetes stagingkub démarré
#   - Keycloak déployé et accessible
#   - SOPS installé pour déchiffrer les secrets
#   - Maven installé
# ════════════════════════════════════════════════════════════════

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RHDEMO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
INIT_KEYCLOAK_DIR="$(cd "${RHDEMO_ROOT}/../rhDemoInitKeycloak" && pwd)"
SECRETS_FILE="${RHDEMO_ROOT}/secrets/secrets-stagingkub.yml"
K8S_NAMESPACE="rhdemo-stagingkub"
K8S_CONTEXT="kind-rhdemo"

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Initialisation Keycloak - Environnement stagingkub${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# ════════════════════════════════════════════════════════════════
# Vérifications préalables
# ════════════════════════════════════════════════════════════════

echo -e "${YELLOW}▶ Vérification des prérequis...${NC}"

# Vérifier que le répertoire rhDemoInitKeycloak existe
if [ ! -d "${INIT_KEYCLOAK_DIR}" ]; then
    echo -e "${RED}✗ Répertoire rhDemoInitKeycloak non trouvé: ${INIT_KEYCLOAK_DIR}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Répertoire rhDemoInitKeycloak trouvé${NC}"

# Vérifier que le fichier de secrets existe
if [ ! -f "${SECRETS_FILE}" ]; then
    echo -e "${RED}✗ Fichier de secrets non trouvé: ${SECRETS_FILE}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Fichier de secrets trouvé${NC}"

# Vérifier que SOPS est installé
if ! command -v sops &> /dev/null; then
    echo -e "${RED}✗ SOPS n'est pas installé${NC}"
    echo -e "${YELLOW}  Installez SOPS: https://github.com/mozilla/sops${NC}"
    exit 1
fi
echo -e "${GREEN}✓ SOPS installé${NC}"

# Vérifier que kubectl est installé
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}✗ kubectl n'est pas installé${NC}"
    exit 1
fi
echo -e "${GREEN}✓ kubectl installé${NC}"

# Vérifier que le contexte Kubernetes existe
if ! kubectl config get-contexts "${K8S_CONTEXT}" &> /dev/null; then
    echo -e "${RED}✗ Contexte Kubernetes '${K8S_CONTEXT}' non trouvé${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Contexte Kubernetes '${K8S_CONTEXT}' trouvé${NC}"

# Utiliser le bon contexte
kubectl config use-context "${K8S_CONTEXT}" > /dev/null

# Vérifier que le namespace existe
if ! kubectl get namespace "${K8S_NAMESPACE}" &> /dev/null; then
    echo -e "${RED}✗ Namespace '${K8S_NAMESPACE}' non trouvé${NC}"
    echo -e "${YELLOW}  Exécutez d'abord: ./init-stagingkub.sh${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Namespace '${K8S_NAMESPACE}' existe${NC}"

# Vérifier que Keycloak est déployé et ready
echo -e "${YELLOW}▶ Vérification du statut de Keycloak...${NC}"
if ! kubectl get pod -l app=keycloak -n "${K8S_NAMESPACE}" &> /dev/null; then
    echo -e "${RED}✗ Keycloak n'est pas déployé dans le namespace${NC}"
    exit 1
fi

KEYCLOAK_READY=$(kubectl get pod -l app=keycloak -n "${K8S_NAMESPACE}" -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
if [ "${KEYCLOAK_READY}" != "True" ]; then
    echo -e "${RED}✗ Keycloak n'est pas prêt${NC}"
    echo -e "${YELLOW}  Attendez que Keycloak soit ready ou exécutez: kubectl wait --for=condition=ready pod -l app=keycloak -n ${K8S_NAMESPACE}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Keycloak est ready${NC}"

# Vérifier que Maven est installé
if ! command -v mvn &> /dev/null && [ ! -f "${INIT_KEYCLOAK_DIR}/mvnw" ]; then
    echo -e "${RED}✗ Maven n'est pas installé et mvnw n'est pas disponible${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Maven disponible${NC}"

echo ""

# ════════════════════════════════════════════════════════════════
# Déchiffrement et extraction des secrets
# ════════════════════════════════════════════════════════════════

echo -e "${YELLOW}▶ Déchiffrement et extraction des secrets...${NC}"

# Déchiffrer le fichier de secrets en mémoire
DECRYPTED_SECRETS=$(sops -d "${SECRETS_FILE}")

# Fonction pour extraire une valeur du YAML déchiffré
extract_secret() {
    local key=$1
    echo "$DECRYPTED_SECRETS" | grep "^[[:space:]]*${key}:" | sed 's/.*: *//' | tr -d '"' | tr -d "'"
}

# Extraction des secrets Keycloak admin
KEYCLOAK_ADMIN_USER=$(extract_secret "user")
KEYCLOAK_ADMIN_PASSWORD=$(extract_secret "password" | tail -1)  # Prendre le dernier (admin password)

# Extraction du secret client
KEYCLOAK_CLIENT_SECRET=$(extract_secret "secret")

# Extraction des utilisateurs de test
TEST_USER_ADMIN=$(extract_secret "iduseradmin")
TEST_PWD_ADMIN=$(extract_secret "pwduseradmin")
TEST_USER_MAJ=$(extract_secret "idusermaj")
TEST_PWD_MAJ=$(extract_secret "pwdusermaj")
TEST_USER_CONSULT=$(extract_secret "iduserconsult")
TEST_PWD_CONSULT=$(extract_secret "pwduserconsult")

# Vérification que les secrets ont été extraits
if [ -z "${KEYCLOAK_ADMIN_USER}" ] || [ -z "${KEYCLOAK_ADMIN_PASSWORD}" ] || [ -z "${KEYCLOAK_CLIENT_SECRET}" ]; then
    echo -e "${RED}✗ Impossible d'extraire les secrets Keycloak${NC}"
    echo -e "${YELLOW}  Secrets extraits:${NC}"
    echo -e "${YELLOW}    - admin user: ${KEYCLOAK_ADMIN_USER:-NON TROUVÉ}${NC}"
    echo -e "${YELLOW}    - admin password: ${KEYCLOAK_ADMIN_PASSWORD:+****}${KEYCLOAK_ADMIN_PASSWORD:-NON TROUVÉ}${NC}"
    echo -e "${YELLOW}    - client secret: ${KEYCLOAK_CLIENT_SECRET:+****}${KEYCLOAK_CLIENT_SECRET:-NON TROUVÉ}${NC}"
    exit 1
fi

if [ -z "${TEST_USER_ADMIN}" ] || [ -z "${TEST_PWD_ADMIN}" ] || \
   [ -z "${TEST_USER_MAJ}" ] || [ -z "${TEST_PWD_MAJ}" ] || \
   [ -z "${TEST_USER_CONSULT}" ] || [ -z "${TEST_PWD_CONSULT}" ]; then
    echo -e "${RED}✗ Impossible d'extraire tous les utilisateurs de test${NC}"
    echo -e "${YELLOW}  Vérifiez que le fichier de secrets contient rhdemo.test.* avec:${NC}"
    echo -e "${YELLOW}    - iduseradmin / pwduseradmin${NC}"
    echo -e "${YELLOW}    - idusermaj / pwdusermaj${NC}"
    echo -e "${YELLOW}    - iduserconsult / pwduserconsult${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Secrets extraits avec succès${NC}"
echo ""

# ════════════════════════════════════════════════════════════════
# Configuration du port-forward vers Keycloak
# ════════════════════════════════════════════════════════════════

echo -e "${YELLOW}▶ Configuration du port-forward vers Keycloak...${NC}"

# Trouver un port local disponible (on utilise 6090 comme dans la config par défaut)
LOCAL_PORT=6090

# Tuer tout port-forward existant sur ce port
pkill -f "kubectl.*port-forward.*keycloak.*${LOCAL_PORT}" 2>/dev/null || true
sleep 2

# Démarrer le port-forward en arrière-plan
KEYCLOAK_POD=$(kubectl get pod -l app=keycloak -n "${K8S_NAMESPACE}" -o jsonpath='{.items[0].metadata.name}')
kubectl port-forward "${KEYCLOAK_POD}" "${LOCAL_PORT}:8080" -n "${K8S_NAMESPACE}" > /dev/null 2>&1 &
PORT_FORWARD_PID=$!

# Attendre que le port-forward soit actif
sleep 3

# Vérifier que le port-forward fonctionne
if ! ps -p ${PORT_FORWARD_PID} > /dev/null 2>&1; then
    echo -e "${RED}✗ Échec du port-forward vers Keycloak${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Port-forward actif (PID: ${PORT_FORWARD_PID}, port: ${LOCAL_PORT})${NC}"
echo ""

# Fonction de nettoyage à la sortie
cleanup() {
    echo ""
    echo -e "${YELLOW}▶ Nettoyage...${NC}"
    if ps -p ${PORT_FORWARD_PID} > /dev/null 2>&1; then
        kill ${PORT_FORWARD_PID} 2>/dev/null || true
        echo -e "${GREEN}✓ Port-forward arrêté${NC}"
    fi
}
trap cleanup EXIT

# ════════════════════════════════════════════════════════════════
# Build de rhDemoInitKeycloak
# ════════════════════════════════════════════════════════════════

echo -e "${YELLOW}▶ Build de rhDemoInitKeycloak...${NC}"
cd "${INIT_KEYCLOAK_DIR}"

if [ -f "./mvnw" ]; then
    ./mvnw clean package -DskipTests
else
    mvn clean package -DskipTests
fi

echo ""
echo -e "${GREEN}✓ Build réussi${NC}"
echo ""

# ════════════════════════════════════════════════════════════════
# Création du fichier de configuration temporaire
# (APRÈS le build pour éviter que 'mvn clean' ne le supprime)
# ════════════════════════════════════════════════════════════════

echo -e "${YELLOW}▶ Création de la configuration pour stagingkub...${NC}"

TEMP_CONFIG="${INIT_KEYCLOAK_DIR}/target/application-stagingkub-temp.yml"
mkdir -p "${INIT_KEYCLOAK_DIR}/target"

# Déterminer les emails et noms basés sur les usernames
# Par défaut, on utilise le username comme base pour l'email
cat > "${TEMP_CONFIG}" <<EOF
# Configuration temporaire pour initialisation Keycloak stagingkub
# Générée automatiquement à partir des secrets de l'environnement
keycloak:
  server-url: http://localhost:${LOCAL_PORT}

  admin:
    realm: master
    username: ${KEYCLOAK_ADMIN_USER}
    password: ${KEYCLOAK_ADMIN_PASSWORD}

  realm:
    name: RHDemo
    display-name: RHDemo Application
    enabled: true
    registration-allowed: false
    registration-email-as-username: false
    reset-password-allowed: true
    edit-username-allowed: false
    login-with-email-allowed: true
    duplicate-emails-allowed: false
    remember-me: true
    sso-session-idle-timeout: 1800
    sso-session-max-lifespan: 36000
    access-token-lifespan: 300

  client:
    client-id: RHDemo
    name: RHDemo
    secret: ${KEYCLOAK_CLIENT_SECRET}
    root-url: https://rhdemo.stagingkub.local:58443/
    base-url: ''
    admin-url: ''
    redirect-uris:
      - https://rhdemo.stagingkub.local:58443/*
    web-origins:
      - https://rhdemo.stagingkub.local:58443
    roles:
      - ROLE_admin
      - ROLE_consult
      - ROLE_MAJ

  users:
    - username: ${TEST_USER_ADMIN}
      password: ${TEST_PWD_ADMIN}
      email: ${TEST_USER_ADMIN}@leuwen.fr
      first-name: Admin
      last-name: ${TEST_USER_ADMIN^}
      roles:
        - ROLE_admin

    - username: ${TEST_USER_CONSULT}
      password: ${TEST_PWD_CONSULT}
      email: ${TEST_USER_CONSULT}@leuwen.fr
      first-name: Consult
      last-name: ${TEST_USER_CONSULT^}
      roles:
        - ROLE_consult

    - username: ${TEST_USER_MAJ}
      password: ${TEST_PWD_MAJ}
      email: ${TEST_USER_MAJ}@leuwen.fr
      first-name: MAJ
      last-name: ${TEST_USER_MAJ^}
      roles:
        - ROLE_consult
        - ROLE_MAJ
EOF

echo -e "${GREEN}✓ Configuration créée: ${TEMP_CONFIG}${NC}"
echo -e "${GREEN}  Utilisateurs configurés:${NC}"
echo -e "${GREEN}    - ${TEST_USER_ADMIN} (ROLE_admin)${NC}"
echo -e "${GREEN}    - ${TEST_USER_CONSULT} (ROLE_consult)${NC}"
echo -e "${GREEN}    - ${TEST_USER_MAJ} (ROLE_consult, ROLE_MAJ)${NC}"
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Exécution de l'initialisation Keycloak${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Exécuter l'application avec le fichier de configuration temporaire
if [ -f "./mvnw" ]; then
    ./mvnw spring-boot:run -Dspring-boot.run.arguments="--spring.config.additional-location=file:${TEMP_CONFIG}"
else
    mvn spring-boot:run -Dspring-boot.run.arguments="--spring.config.additional-location=file:${TEMP_CONFIG}"
fi

INIT_EXIT_CODE=$?

echo ""
if [ ${INIT_EXIT_CODE} -eq 0 ]; then
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ Initialisation Keycloak réussie${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}Keycloak est maintenant configuré pour l'environnement stagingkub:${NC}"
    echo -e "  • Realm: RHDemo"
    echo -e "  • Client: RHDemo"
    echo -e "  • URL: https://keycloak.stagingkub.local"
    echo -e "  • Utilisateurs créés:"
    echo -e "      - ${TEST_USER_ADMIN} (ROLE_admin)"
    echo -e "      - ${TEST_USER_CONSULT} (ROLE_consult)"
    echo -e "      - ${TEST_USER_MAJ} (ROLE_consult + ROLE_MAJ)"
    echo ""
else
    echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  ✗ Échec de l'initialisation Keycloak${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    exit ${INIT_EXIT_CODE}
fi

# Le nettoyage (arrêt du port-forward) sera fait automatiquement par trap EXIT
