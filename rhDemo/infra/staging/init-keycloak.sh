#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Script d'initialisation de Keycloak pour l'environnement staging
# USAGE MANUEL LOCAL UNIQUEMENT
#
# Pour CI/CD Jenkins: l'initialisation est gérée directement dans Jenkinsfile
# (génération application-staging.yml + exécution JAR)
#
# Utilise le projet rhDemoInitKeycloak pour créer le realm, 
# le client et les utilisateurs
#
# Usage:
#   ./init-keycloak.sh
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RHDEMO_INIT_KEYCLOAK_DIR="${SCRIPT_DIR}/../../../rhDemoInitKeycloak"
ENV_FILE="${SCRIPT_DIR}/.env"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Initialisation Keycloak pour RHDemo Staging (mode manuel)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo

# Charger les variables depuis .env (créé par init-staging.sh)
if [ ! -f "${ENV_FILE}" ]; then
    echo -e "${RED}✗ Fichier .env introuvable${NC}"
    echo -e "Exécutez d'abord: ./init-staging.sh"
    exit 1
fi

source "${ENV_FILE}"
echo -e "${GREEN}✓ Variables chargées depuis .env${NC}"

# Vérifier que Keycloak est accessible (via HTTPS nginx)
KEYCLOAK_URL="https://${KEYCLOAK_DOMAIN}"
echo -e "${YELLOW}→ Vérification de l'accessibilité de Keycloak...${NC}"

MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Mode manuel : accès HTTPS via nginx (-k pour certificat auto-signé)
    if curl -k -s -o /dev/null -w "%{http_code}" ${KEYCLOAK_URL} | grep -q "200\|301\|302\|404"; then
        echo -e "${GREEN}✓ Keycloak est accessible${NC}"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -ne "\r${YELLOW}  Attente de Keycloak... (${RETRY_COUNT}/${MAX_RETRIES})${NC}  "
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo
    echo -e "${RED}✗ Keycloak n'est pas accessible après ${MAX_RETRIES} tentatives${NC}"
    echo -e "Vérifiez que Keycloak est démarré: ${BLUE}sudo docker compose ps keycloak${NC}"
    exit 1
fi

echo
echo -e "${YELLOW}→ Attente supplémentaire de 10 secondes pour la stabilisation...${NC}"
sleep 10

# Vérifier que le projet rhDemoInitKeycloak existe
if [ ! -d "${RHDEMO_INIT_KEYCLOAK_DIR}" ]; then
    echo -e "${RED}✗ Projet rhDemoInitKeycloak introuvable: ${RHDEMO_INIT_KEYCLOAK_DIR}${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Projet rhDemoInitKeycloak trouvé${NC}"
echo

# Copier la configuration pour le staging
echo -e "${YELLOW}→ Préparation de la configuration Keycloak...${NC}"

CONFIG_FILE="${RHDEMO_INIT_KEYCLOAK_DIR}/src/main/resources/application-staging.yml"

cat > "${CONFIG_FILE}" << EOF
# ========================================
# Configuration Keycloak Server - STAGING
# Générée automatiquement par init-keycloak.sh
# ========================================
keycloak:
  server-url: ${KEYCLOAK_URL}
  
  admin:
    realm: master
    username: ${KEYCLOAK_ADMIN_USER}
    password: ${KEYCLOAK_ADMIN_PASSWORD}
  
  # ========================================
  # Configuration du Realm RHDemo
  # ========================================
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
  
  # ========================================
  # Configuration du Client RHDemo
  # ========================================
  client:
    client-id: RHDemo
    name: RHDemo
    secret: ${RHDEMO_CLIENT_SECRET}
    root-url: https://${NGINX_DOMAIN}/
    base-url: ''
    admin-url: ''
    redirect-uris:
      - https://${NGINX_DOMAIN}/*
      - http://localhost:9000/*
    web-origins:
      - https://${NGINX_DOMAIN}
      - http://localhost:9000
    roles:
      - ROLE_admin
      - ROLE_consult
      - ROLE_MAJ
  
  # ========================================
  # Configuration des Utilisateurs de test
  # ========================================
  users:
    - username: admin
      password: admin123
      email: admin@rhdemo.local
      first-name: Admin
      last-name: RHDemo
      roles:
        - ROLE_admin
    
    - username: consultant
      password: consult123
      email: consultant@rhdemo.local
      first-name: Jean
      last-name: Consultant
      roles:
        - ROLE_consult
    
    - username: manager
      password: manager123
      email: manager@rhdemo.local
      first-name: Marie
      last-name: Manager
      roles:
        - ROLE_consult
        - ROLE_MAJ
EOF

echo -e "${GREEN}✓ Configuration générée: ${CONFIG_FILE}${NC}"
echo

# Exécuter l'initialisation Keycloak (mode manuel uniquement)
echo -e "${YELLOW}→ Initialisation de Keycloak (realm, client, utilisateurs)...${NC}"
echo -e "${YELLOW}  Cela peut prendre 30-60 secondes...${NC}"
echo

cd "${RHDEMO_INIT_KEYCLOAK_DIR}"

# Utiliser Maven wrapper pour exécution en mode dev
if ./mvnw spring-boot:run -Dspring-boot.run.profiles=staging -q; then
    echo
    echo -e "${GREEN}✓ Keycloak initialisé avec succès !${NC}"
else
    echo
    echo -e "${RED}✗ Erreur lors de l'initialisation de Keycloak${NC}"
    exit 1
fi

cd "${SCRIPT_DIR}"

echo
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Initialisation Keycloak terminée !${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo
echo -e "${BLUE}Realm créé:${NC} RHDemo"
echo -e "${BLUE}Client créé:${NC} RHDemo (secret: ${RHDEMO_CLIENT_SECRET})"
echo
echo -e "${BLUE}Utilisateurs créés:${NC}"
echo -e "  ${GREEN}admin${NC} / admin123 (roles: admin, consult, MAJ)"
echo -e "  ${GREEN}consultant${NC} / consult123 (roles: consult)"
echo -e "  ${GREEN}manager${NC} / manager123 (roles: consult, MAJ)"
echo
echo -e "${YELLOW}Prochaine étape:${NC}"
echo -e "  Redémarrez l'application RHDemo:"
echo -e "  ${BLUE}sudo docker compose restart rhdemo-app${NC}"
echo
echo -e "${YELLOW}Accès Keycloak Admin:${NC}"
echo -e "  URL: ${GREEN}https://${KEYCLOAK_DOMAIN}${NC}"
echo -e "  User: ${GREEN}${KEYCLOAK_ADMIN_USER}${NC}"
echo -e "  Pass: ${GREEN}${KEYCLOAK_ADMIN_PASSWORD}${NC}"
echo
