#!/bin/bash

#═══════════════════════════════════════════════════════════════
# Script de génération de certificats SSL auto-signés
# Pour l'environnement de test ephemere avec nginx
#
# Crée un certificat valide pour :
#   - rhdemo.ephemere.local
#   - keycloak.ephemere.local
#
# Usage:
#   ./generate-certs.sh
#   ./generate-certs.sh --domain custom.domain.local
#═══════════════════════════════════════════════════════════════

set -e

# Configuration par défaut
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${SCRIPT_DIR}/certs"
DEFAULT_DOMAIN="ephemere.local"
RHDEMO_DOMAIN="rhdemo.${DEFAULT_DOMAIN}"
KEYCLOAK_DOMAIN="keycloak.${DEFAULT_DOMAIN}"

# Parsing des arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DEFAULT_DOMAIN="$2"
            RHDEMO_DOMAIN="rhdemo.${DEFAULT_DOMAIN}"
            KEYCLOAK_DOMAIN="keycloak.${DEFAULT_DOMAIN}"
            shift 2
            ;;
        --rhdemo-domain)
            RHDEMO_DOMAIN="$2"
            shift 2
            ;;
        --keycloak-domain)
            KEYCLOAK_DOMAIN="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --domain DOMAIN          Domaine de base (default: ephemere.local)"
            echo "  --rhdemo-domain DOMAIN   Domaine RHDemo (default: rhdemo.ephemere.local)"
            echo "  --keycloak-domain DOMAIN Domaine Keycloak (default: keycloak.ephemere.local)"
            echo "  -h, --help               Afficher cette aide"
            echo ""
            echo "Example:"
            echo "  $0 --domain test.local"
            exit 0
            ;;
        *)
            echo "Option inconnue: $1"
            echo "Utilisez --help pour voir les options disponibles"
            exit 1
            ;;
    esac
done

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Génération de certificats SSL auto-signés${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Créer le répertoire certs s'il n'existe pas
mkdir -p "${CERTS_DIR}"

echo -e "${BLUE}→ Configuration:${NC}"
echo -e "   Domaine RHDemo: ${RHDEMO_DOMAIN}"
echo -e "   Domaine Keycloak: ${KEYCLOAK_DOMAIN}"
echo -e "   Répertoire: ${CERTS_DIR}"
echo ""

# Créer un fichier de configuration OpenSSL temporaire
OPENSSL_CNF="${CERTS_DIR}/openssl.cnf"

cat > "${OPENSSL_CNF}" <<EOF
[req]
default_bits       = 2048
default_md         = sha256
prompt             = no
encrypt_key        = no
distinguished_name = dn
req_extensions     = v3_req

[dn]
C  = FR
ST = Ile-de-France
L  = Paris
O  = RHDemo Ephemere
OU = IT Department
CN = ${RHDEMO_DOMAIN}

[v3_req]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = ${RHDEMO_DOMAIN}
DNS.2 = ${KEYCLOAK_DOMAIN}
DNS.3 = localhost
IP.1  = 127.0.0.1
EOF

echo -e "${BLUE}→ Génération de la clé privée...${NC}"
openssl genrsa \
    -out "${CERTS_DIR}/nginx.key" \
    2048 2>/dev/null

echo -e "${GREEN}✓ Clé privée générée: nginx.key${NC}"

echo -e "${BLUE}→ Génération de la requête de certificat (CSR)...${NC}"
openssl req \
    -new \
    -key "${CERTS_DIR}/nginx.key" \
    -out "${CERTS_DIR}/nginx.csr" \
    -config "${OPENSSL_CNF}" 2>/dev/null

echo -e "${GREEN}✓ CSR généré: nginx.csr${NC}"

echo -e "${BLUE}→ Génération du certificat auto-signé (valide 365 jours)...${NC}"
openssl x509 -req \
    -in "${CERTS_DIR}/nginx.csr" \
    -signkey "${CERTS_DIR}/nginx.key" \
    -out "${CERTS_DIR}/nginx.crt" \
    -days 365 \
    -extensions v3_req \
    -extfile "${OPENSSL_CNF}" 2>/dev/null

echo -e "${GREEN}✓ Certificat généré: nginx.crt${NC}"
echo ""

# Nettoyage des fichiers temporaires
rm -f "${OPENSSL_CNF}" "${CERTS_DIR}/nginx.csr"

# Afficher les informations du certificat
echo -e "${BLUE}→ Informations du certificat:${NC}"
openssl x509 -in "${CERTS_DIR}/nginx.crt" -noout -text | grep -E "Subject:|Issuer:|Not Before|Not After|DNS:" | sed 's/^/   /'
echo ""

# Vérifier les permissions
chmod 644 "${CERTS_DIR}/nginx.crt"
chmod 600 "${CERTS_DIR}/nginx.key"

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Certificats SSL générés avec succès !                    ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📁 Fichiers créés:${NC}"
echo -e "   ${CERTS_DIR}/nginx.key  (clé privée - 600)"
echo -e "   ${CERTS_DIR}/nginx.crt  (certificat - 644)"
echo ""
echo -e "${BLUE}📋 Domaines couverts:${NC}"
echo -e "   ✓ ${RHDEMO_DOMAIN}"
echo -e "   ✓ ${KEYCLOAK_DOMAIN}"
echo -e "   ✓ localhost"
echo -e "   ✓ 127.0.0.1"
echo ""
echo -e "${YELLOW}⚠️  Note: Certificat auto-signé - À utiliser uniquement en test/ephemere${NC}"
echo ""

