#!/bin/bash

# Script de démarrage de l'environnement de développement local
# Usage: ./start.sh [options]

set -e

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour afficher les messages
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
    error "Erreur: docker-compose.yml introuvable. Veuillez exécuter ce script depuis infra/dev/"
    exit 1
fi

info "Démarrage de l'environnement de développement rhDemo..."

# Vérifier si .env existe, sinon créer depuis le template
if [ ! -f ".env" ]; then
    warning "Fichier .env introuvable"
    if [ -f ".env.template" ]; then
        info "Création de .env depuis .env.template..."
        cp .env.template .env
        success ".env créé avec les valeurs par défaut"
        warning "Vous pouvez éditer .env pour personnaliser les mots de passe"
    else
        error ".env.template introuvable"
        exit 1
    fi
fi

# Démarrer les services
info "Démarrage des containers Docker..."
docker-compose up -d

# Attendre que les services soient prêts
info "Attente du démarrage de PostgreSQL..."
timeout=30
while [ $timeout -gt 0 ]; do
    if docker exec rhdemo-dev-db pg_isready -U dbrhdemo >/dev/null 2>&1; then
        success "PostgreSQL prêt"
        break
    fi
    sleep 2
    timeout=$((timeout - 2))
done

if [ $timeout -le 0 ]; then
    warning "Timeout: PostgreSQL n'est pas encore prêt (peut prendre plus de temps au premier démarrage)"
fi

info "Attente du démarrage de Keycloak..."
timeout=60
while [ $timeout -gt 0 ]; do
    if docker exec keycloak-dev curl -sf http://localhost:8080/health/ready >/dev/null 2>&1; then
        success "Keycloak prêt"
        break
    fi
    sleep 3
    timeout=$((timeout - 3))
done

if [ $timeout -le 0 ]; then
    warning "Timeout: Keycloak n'est pas encore prêt (peut prendre plus de temps au premier démarrage)"
fi

# Afficher l'état des services
echo ""
info "État des services:"
docker-compose ps

# Afficher les URLs d'accès
echo ""
success "Environnement de développement démarré!"
echo ""
echo "📍 Accès aux services:"
echo "   • Keycloak Admin Console: ${BLUE}http://localhost:6090${NC}"
echo "   • PostgreSQL: ${BLUE}localhost:5432${NC} (dbrhdemo/changeme)"
echo ""
echo "📋 Prochaines étapes:"
echo "   1. Initialiser Keycloak avec rhDemoInitKeycloak"
echo "   2. Initialiser la base de données: docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < ../../pgddl.sql"
echo "   3. Configurer secrets/secrets-rhdemo.yml"
echo "   4. Démarrer l'application rhDemo: cd ../../ && ./mvnw spring-boot:run"
echo ""
echo "📖 Pour plus d'informations: cat README.md"
echo ""
info "Logs: docker-compose logs -f"
info "Arrêter: docker-compose stop"
info "Tout supprimer: docker-compose down -v"
