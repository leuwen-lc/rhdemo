#!/bin/bash

# ═══════════════════════════════════════════════════════════════════
# Script de configuration de la clé API NVD pour OWASP Dependency-Check
# ═══════════════════════════════════════════════════════════════════

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonctions d'affichage
info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

success() {
    echo -e "${GREEN}✅${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}❌${NC} $1"
}

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "docker-compose.yml" ]; then
    error "Erreur: docker-compose.yml introuvable"
    echo "Veuillez exécuter ce script depuis infra/jenkins-docker/"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Configuration de la clé API NVD pour OWASP Dependency-Check"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Vérifier si .env existe
if [ ! -f ".env" ]; then
    error "Fichier .env introuvable"
    info "Création de .env depuis .env.example..."
    cp .env.example .env
    success ".env créé"
    echo ""
fi

# Demander si l'utilisateur a déjà une clé
echo "Avez-vous déjà une clé API NVD ?"
echo "  1. Oui, j'ai déjà une clé"
echo "  2. Non, j'ai besoin d'en obtenir une"
echo ""
read -p "Votre choix [1/2]: " choice

case $choice in
    1)
        # L'utilisateur a déjà une clé
        echo ""
        info "Entrez votre clé API NVD (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"
        read -p "Clé API NVD : " nvd_key

        # Validation basique du format
        if [[ ! $nvd_key =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
            warning "Format de clé invalide (attendu: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"
            warning "Je vais quand même continuer, mais vérifiez votre clé..."
        fi

        # Ajouter/mettre à jour la clé dans .env
        if grep -q "^NVD_API_KEY=" .env; then
            # La clé existe déjà, la remplacer
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' "s|^NVD_API_KEY=.*|NVD_API_KEY=$nvd_key|" .env
            else
                # Linux
                sed -i "s|^NVD_API_KEY=.*|NVD_API_KEY=$nvd_key|" .env
            fi
            success "Clé API NVD mise à jour dans .env"
        else
            # Ajouter la clé
            echo "" >> .env
            echo "# OWASP Dependency-Check" >> .env
            echo "NVD_API_KEY=$nvd_key" >> .env
            success "Clé API NVD ajoutée dans .env"
        fi

        echo ""
        success "Configuration terminée !"
        echo ""
        info "Prochaines étapes :"
        echo "  1. Redémarrez Jenkins : docker-compose restart jenkins"
        echo "  2. Dans Jenkins UI, allez dans Manage Jenkins → Manage Credentials"
        echo "  3. Ajoutez un credential 'Secret text' avec :"
        echo "     - ID: nvd-api-key"
        echo "     - Secret: $nvd_key"
        echo "  4. Le Jenkinsfile utilisera automatiquement cette clé"
        echo ""
        ;;

    2)
        # L'utilisateur doit obtenir une clé
        echo ""
        info "Pour obtenir une clé API NVD gratuite :"
        echo ""
        echo "  1. Allez sur : https://nvd.nist.gov/developers/request-an-api-key"
        echo "  2. Remplissez le formulaire avec votre email professionnel"
        echo "  3. Cochez 'I am not a robot'"
        echo "  4. Cliquez sur 'Request an API Key'"
        echo "  5. Vérifiez votre boîte mail et confirmez la demande"
        echo "  6. Vous recevrez votre clé API dans un second email"
        echo ""
        info "Une fois que vous avez votre clé, relancez ce script et choisissez l'option 1"
        echo ""

        read -p "Voulez-vous ouvrir le formulaire NVD dans votre navigateur ? [o/N] " open_browser

        if [[ $open_browser =~ ^[oO]$ ]]; then
            if command -v xdg-open &> /dev/null; then
                xdg-open "https://nvd.nist.gov/developers/request-an-api-key"
            elif command -v open &> /dev/null; then
                open "https://nvd.nist.gov/developers/request-an-api-key"
            else
                warning "Impossible d'ouvrir le navigateur automatiquement"
                echo "Ouvrez manuellement : https://nvd.nist.gov/developers/request-an-api-key"
            fi
        fi
        echo ""
        ;;

    *)
        error "Choix invalide"
        exit 1
        ;;
esac

# Informations supplémentaires
echo ""
info "ℹ️  Informations sur la clé API NVD :"
echo ""
echo "  Sans clé API :"
echo "    • Limite : 10 requêtes / 30 secondes"
echo "    • Risque de timeout au premier scan (~2-3 GB de données NVD)"
echo ""
echo "  Avec clé API :"
echo "    • Limite : 50 requêtes / 30 secondes"
echo "    • Scans plus rapides et fiables"
echo "    • Mises à jour NVD sans interruption"
echo ""
echo "  Documentation complète :"
echo "    • ../../docs/OWASP_JENKINS_PLUGIN.md"
echo "    • ../../docs/JENKINS_OWASP_SETUP.md"
echo ""
