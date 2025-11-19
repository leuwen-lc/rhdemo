#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Script d'initialisation de l'environnement de staging RHDemo
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██████╗ ██╗  ██╗██████╗ ███████╗███╗   ███╗ ██████╗        ║
║   ██╔══██╗██║  ██║██╔══██╗██╔════╝████╗ ████║██╔═══██╗       ║
║   ██████╔╝███████║██║  ██║█████╗  ██╔████╔██║██║   ██║       ║
║   ██╔══██╗██╔══██║██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║       ║
║   ██║  ██║██║  ██║██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝       ║
║   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝        ║
║                                                               ║
║        Initialisation environnement de STAGING                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Fonction pour générer un mot de passe aléatoire
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Fonction pour demander confirmation
confirm() {
    local message=$1
    read -p "$(echo -e "${YELLOW}${message}${NC} (y/N)") " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# Vérification des prérequis
echo -e "${BLUE}[1/6] Vérification des prérequis...${NC}"

# Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker n'est pas installé${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker: $(docker --version)${NC}"

# Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ Docker Compose n'est pas installé${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose installé${NC}"

# OpenSSL
if ! command -v openssl &> /dev/null; then
    echo -e "${RED}✗ OpenSSL n'est pas installé${NC}"
    exit 1
fi
echo -e "${GREEN}✓ OpenSSL: $(openssl version)${NC}"

echo

# Configuration du fichier .env
echo -e "${BLUE}[2/6] Configuration des variables d'environnement...${NC}"

if [ -f "${ENV_FILE}" ]; then
    echo -e "${YELLOW}⚠ Le fichier .env existe déjà${NC}"
    if confirm "Voulez-vous le régénérer ?"; then
        rm "${ENV_FILE}"
    else
        echo -e "${GREEN}✓ Conservation du fichier .env existant${NC}"
        ENV_EXISTS=true
    fi
fi

if [ ! -v ENV_EXISTS ]; then
    if [ ! -f "${ENV_EXAMPLE}" ]; then
        echo -e "${RED}✗ Fichier .env.example introuvable${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}→ Génération du fichier .env avec mots de passe aléatoires...${NC}"
    
    RHDEMO_DB_PWD=$(generate_password)
    KEYCLOAK_DB_PWD=$(generate_password)
    KEYCLOAK_ADMIN_PWD=$(generate_password)
    CLIENT_SECRET=$(generate_password)
    
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"
    
    # Remplacement des valeurs
    sed -i "s/changeme_rhdemo_db/${RHDEMO_DB_PWD}/" "${ENV_FILE}"
    sed -i "s/changeme_keycloak_db/${KEYCLOAK_DB_PWD}/" "${ENV_FILE}"
    sed -i "s/changeme_admin/${KEYCLOAK_ADMIN_PWD}/" "${ENV_FILE}"
    sed -i "s/changeme_client_secret/${CLIENT_SECRET}/" "${ENV_FILE}"
    
    echo -e "${GREEN}✓ Fichier .env créé${NC}"
    echo
    echo -e "${YELLOW}Credentials générés:${NC}"
    echo -e "  KEYCLOAK_ADMIN_PASSWORD=${GREEN}${KEYCLOAK_ADMIN_PWD}${NC}"
    echo -e "  RHDEMO_DB_PASSWORD=${GREEN}${RHDEMO_DB_PWD}${NC}"
    echo -e "  KEYCLOAK_DB_PASSWORD=${GREEN}${KEYCLOAK_DB_PWD}${NC}"
    echo -e "  RHDEMO_CLIENT_SECRET=${GREEN}${CLIENT_SECRET}${NC}"
    echo
    echo -e "${YELLOW}⚠ SAUVEGARDEZ ces informations dans un gestionnaire de mots de passe !${NC}"
    echo
fi

# Génération des certificats SSL
echo -e "${BLUE}[3/6] Génération des certificats SSL...${NC}"

cd "${SCRIPT_DIR}/nginx"
if [ -f "generate-certs.sh" ]; then
    bash generate-certs.sh
else
    echo -e "${RED}✗ Script generate-certs.sh introuvable${NC}"
    exit 1
fi
cd "${SCRIPT_DIR}"

echo

# Vérification de l'image Docker
echo -e "${BLUE}[4/6] Vérification de l'image Docker...${NC}"

APP_VERSION=$(grep "^APP_VERSION=" "${ENV_FILE}" | cut -d'=' -f2)
IMAGE_NAME="rhdemo-api:${APP_VERSION}"

if ! docker images "${IMAGE_NAME}" | grep -q "${APP_VERSION}"; then
    echo -e "${YELLOW}⚠ Image ${IMAGE_NAME} introuvable${NC}"
    
    if confirm "Voulez-vous la construire maintenant ?"; then
        echo -e "${YELLOW}→ Construction de l'image avec Paketo Buildpacks...${NC}"
        cd ../..
        ./mvnw clean spring-boot:build-image
        cd "${SCRIPT_DIR}"
        echo -e "${GREEN}✓ Image construite${NC}"
    else
        echo -e "${YELLOW}⚠ Vous devrez construire l'image manuellement:${NC}"
        echo -e "  cd /home/leno-vo/git/repository/rhDemo"
        echo -e "  ./mvnw spring-boot:build-image"
    fi
else
    echo -e "${GREEN}✓ Image Docker ${IMAGE_NAME} trouvée${NC}"
fi

echo

# Configuration /etc/hosts
echo -e "${BLUE}[5/6] Configuration DNS locale...${NC}"

NGINX_DOMAIN=$(grep "^NGINX_DOMAIN=" "${ENV_FILE}" | cut -d'=' -f2)
KEYCLOAK_DOMAIN=$(grep "^KEYCLOAK_DOMAIN=" "${ENV_FILE}" | cut -d'=' -f2)

if ! grep -q "${NGINX_DOMAIN}" /etc/hosts || ! grep -q "${KEYCLOAK_DOMAIN}" /etc/hosts; then
    echo -e "${YELLOW}⚠ Les entrées DNS ne sont pas configurées dans /etc/hosts${NC}"
    echo
    echo -e "Ajoutez ces lignes à votre fichier /etc/hosts:"
    echo -e "${GREEN}127.0.0.1  ${NGINX_DOMAIN}${NC}"
    echo -e "${GREEN}127.0.0.1  ${KEYCLOAK_DOMAIN}${NC}"
    echo
    
    if confirm "Voulez-vous que je les ajoute automatiquement (sudo requis) ?"; then
        echo "127.0.0.1  ${NGINX_DOMAIN}" | sudo tee -a /etc/hosts > /dev/null
        echo "127.0.0.1  ${KEYCLOAK_DOMAIN}" | sudo tee -a /etc/hosts > /dev/null
        echo -e "${GREEN}✓ Entrées DNS ajoutées${NC}"
    else
        echo -e "${YELLOW}⚠ Vous devrez configurer /etc/hosts manuellement${NC}"
    fi
else
    echo -e "${GREEN}✓ Entrées DNS déjà configurées${NC}"
fi

echo

# Démarrage des services
echo -e "${BLUE}[6/6] Démarrage des services Docker...${NC}"

if confirm "Voulez-vous démarrer les services maintenant ?"; then
    echo -e "${YELLOW}→ Démarrage de la stack Docker Compose...${NC}"
    docker compose up -d
    
    echo
    echo -e "${YELLOW}→ Attente du démarrage des services (healthchecks)...${NC}"
    echo -e "${YELLOW}  Cela peut prendre 60-120 secondes pour Keycloak...${NC}"
    
    sleep 5
    
    for i in {1..60}; do
        HEALTHY=$(docker compose ps --format json | jq -r 'select(.Health == "healthy") | .Name' 2>/dev/null | wc -l)
        TOTAL=$(docker compose ps --format json | jq -r '.Name' 2>/dev/null | wc -l)
        
        echo -ne "\r${YELLOW}  Services healthy: ${GREEN}${HEALTHY}${YELLOW}/${TOTAL}${NC}  "
        
        if [ "$HEALTHY" -eq "$TOTAL" ]; then
            echo
            echo -e "${GREEN}✓ Tous les services sont démarrés !${NC}"
            break
        fi
        
        sleep 2
    done
    
    echo
    echo -e "${GREEN}✓ Stack démarrée${NC}"
else
    echo -e "${YELLOW}⚠ Services non démarrés${NC}"
    echo -e "Démarrage manuel: ${BLUE}docker compose up -d${NC}"
fi

echo
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Initialisation terminée !${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo
echo -e "${BLUE}Accès aux services:${NC}"
echo -e "  Application:     ${GREEN}https://${NGINX_DOMAIN}${NC}"
echo -e "  Keycloak Admin:  ${GREEN}https://${KEYCLOAK_DOMAIN}${NC}"
echo -e "  Actuator:        ${GREEN}https://${NGINX_DOMAIN}/actuator${NC}"
echo
echo -e "${YELLOW}Credentials Keycloak Admin:${NC}"
echo -e "  Username: ${GREEN}$(grep "^KEYCLOAK_ADMIN_USER=" "${ENV_FILE}" | cut -d'=' -f2)${NC}"
echo -e "  Password: ${GREEN}$(grep "^KEYCLOAK_ADMIN_PASSWORD=" "${ENV_FILE}" | cut -d'=' -f2)${NC}"
echo
echo -e "${BLUE}Commandes utiles:${NC}"
echo -e "  Logs:            ${GREEN}docker compose logs -f${NC}"
echo -e "  Status:          ${GREEN}docker compose ps${NC}"
echo -e "  Arrêt:           ${GREEN}docker compose down${NC}"
echo -e "  Restart:         ${GREEN}docker compose restart${NC}"
echo
echo -e "${YELLOW}⚠ Prochaines étapes:${NC}"
echo -e "  1. Configurer Keycloak (realm, client, users)"
echo -e "  2. Mettre à jour RHDEMO_CLIENT_SECRET dans .env"
echo -e "  3. Redémarrer l'application: docker compose restart rhdemo-app"
echo
echo -e "${YELLOW}📖 Documentation complète: ${BLUE}README.md${NC}"
echo
