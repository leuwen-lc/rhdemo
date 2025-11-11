#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Génération de certificats SSL auto-signés pour staging
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSL_DIR="${SCRIPT_DIR}/ssl"

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Génération des certificats SSL pour staging${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"

# Créer le répertoire SSL s'il n'existe pas
mkdir -p "${SSL_DIR}"

# Fonction pour générer un certificat
generate_cert() {
    local domain=$1
    local cert_file="${SSL_DIR}/${domain}.crt"
    local key_file="${SSL_DIR}/${domain}.key"
    
    if [ -f "${cert_file}" ] && [ -f "${key_file}" ]; then
        echo -e "${YELLOW}⚠ Les certificats pour ${domain} existent déjà${NC}"
        read -p "Voulez-vous les régénérer ? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${GREEN}✓ Conservation des certificats existants pour ${domain}${NC}"
            return
        fi
    fi
    
    echo -e "${GREEN}→ Génération du certificat pour ${domain}...${NC}"
    
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "${key_file}" \
        -out "${cert_file}" \
        -subj "/C=FR/ST=France/L=Paris/O=RHDemo/OU=Staging/CN=${domain}" \
        -addext "subjectAltName=DNS:${domain},DNS:*.${domain},DNS:localhost"
    
    # Permissions appropriées
    chmod 644 "${cert_file}"
    chmod 600 "${key_file}"
    
    echo -e "${GREEN}✓ Certificat généré pour ${domain}${NC}"
    echo -e "  - Certificat: ${cert_file}"
    echo -e "  - Clé privée: ${key_file}"
    echo
}

# Générer les certificats pour chaque domaine
generate_cert "rhdemo"
generate_cert "keycloak"

echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Génération terminée !${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo
echo -e "${YELLOW}IMPORTANT:${NC}"
echo -e "Ces certificats sont auto-signés et destinés uniquement au staging."
echo -e "Pour un environnement de production, utilisez Let's Encrypt ou des"
echo -e "certificats émis par une autorité de certification reconnue."
echo
echo -e "${YELLOW}Configuration /etc/hosts requise:${NC}"
echo -e "Ajoutez ces lignes à votre fichier /etc/hosts :"
echo -e "${GREEN}127.0.0.1  rhdemo.staging.local${NC}"
echo -e "${GREEN}127.0.0.1  keycloak.staging.local${NC}"
echo
