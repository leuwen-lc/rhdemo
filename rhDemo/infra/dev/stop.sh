#!/bin/bash

# Script d'arrêt de l'environnement de développement local
# Usage: ./stop.sh [--clean]

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

# Vérifier l'option --clean
CLEAN_ALL=false
if [ "$1" = "--clean" ]; then
    CLEAN_ALL=true
    warning "Mode nettoyage complet activé (suppression des volumes)"
fi

info "Arrêt de l'environnement de développement rhDemo..."

if [ "$CLEAN_ALL" = true ]; then
    # Arrêt complet avec suppression des volumes
    info "Suppression des containers et volumes..."
    docker-compose down -v
    success "Environnement complètement supprimé (données PostgreSQL effacées)"
else
    # Arrêt simple
    info "Arrêt des containers (données conservées)..."
    docker-compose stop
    success "Containers arrêtés (les données PostgreSQL sont conservées)"
    echo ""
    info "Pour redémarrer: ./start.sh"
    info "Pour supprimer les containers: docker-compose down"
    info "Pour tout nettoyer (⚠️ perte de données): ./stop.sh --clean"
fi
