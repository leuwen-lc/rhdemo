#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Script de génération des certificats TLS pour le registry Docker
# ═══════════════════════════════════════════════════════════════════
#
# Ce script génère un certificat auto-signé pour le registry Docker
# local utilisé par Jenkins CI/CD.
#
# Usage: ./init-registry-certs.sh
#
# Les certificats sont générés dans ./certs/registry/
# ═══════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${SCRIPT_DIR}/certs/registry"

echo "═══════════════════════════════════════════════════════════════════"
echo " Génération des certificats TLS pour le registry Docker"
echo "═══════════════════════════════════════════════════════════════════"

# Créer le répertoire des certificats
mkdir -p "${CERTS_DIR}"

# Vérifier si les certificats existent déjà
if [ -f "${CERTS_DIR}/registry.crt" ] && [ -f "${CERTS_DIR}/registry.key" ]; then
    echo ""
    echo "⚠️  Les certificats existent déjà dans ${CERTS_DIR}"
    echo ""
    read -p "Voulez-vous les régénérer ? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Certificats conservés."
        exit 0
    fi
    echo "Régénération des certificats..."
fi

echo ""
echo "▶ Génération du certificat auto-signé..."

# Générer le certificat avec les SANs nécessaires
# - localhost: pour les accès depuis l'hôte
# - kind-registry: pour les accès depuis les conteneurs Docker
# - 127.0.0.1: pour les accès IP localhost
openssl req -x509 -newkey rsa:4096 \
    -keyout "${CERTS_DIR}/registry.key" \
    -out "${CERTS_DIR}/registry.crt" \
    -sha256 -days 3650 -nodes \
    -subj "/C=FR/ST=France/L=Paris/O=RHDemo/OU=DevOps/CN=kind-registry" \
    -addext "subjectAltName=DNS:localhost,DNS:kind-registry,IP:127.0.0.1"

# Définir les permissions appropriées
chmod 644 "${CERTS_DIR}/registry.crt"
chmod 600 "${CERTS_DIR}/registry.key"

echo ""
echo "✅ Certificats générés avec succès:"
echo "   - ${CERTS_DIR}/registry.crt (certificat public)"
echo "   - ${CERTS_DIR}/registry.key (clé privée)"
echo ""

# Afficher les informations du certificat
echo "▶ Informations du certificat:"
openssl x509 -in "${CERTS_DIR}/registry.crt" -noout -subject -dates -ext subjectAltName 2>/dev/null | sed 's/^/   /'

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo " Configuration Docker daemon requise"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Pour que Docker fasse confiance au certificat, exécutez:"
echo ""
echo "   sudo mkdir -p /etc/docker/certs.d/localhost:5000"
echo "   sudo cp ${CERTS_DIR}/registry.crt /etc/docker/certs.d/localhost:5000/ca.crt"
echo ""
echo "Puis redémarrez Docker:"
echo ""
echo "   sudo systemctl restart docker"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
