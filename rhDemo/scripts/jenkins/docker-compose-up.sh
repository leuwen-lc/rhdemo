#!/bin/bash
# Script: docker-compose-up.sh
# Description: Démarre l'environnement Docker Compose pour ephemere
# Usage: ./docker-compose-up.sh <compose_project> <ephemere_path>

set -euo pipefail

COMPOSE_PROJECT="${1:-}"
EPHEMERE_PATH="${2:-}"

if [ -z "$COMPOSE_PROJECT" ] || [ -z "$EPHEMERE_PATH" ]; then
    echo "❌ Usage: $0 <compose_project> <ephemere_path>"
    exit 1
fi

echo "🐳 Démarrage de l'environnement Docker Compose"
echo "   Projet: $COMPOSE_PROJECT"
echo "   Path: $EPHEMERE_PATH"

# SÉCURITÉ: Désactiver l'écho des commandes pour ne pas exposer les secrets
set +x

# Source les secrets générés par Jenkinsfile-CI (stage « Génération Secrets ephemere »)
if [ -f "rhDemo/secrets/env-vars.sh" ]; then
    . rhDemo/secrets/env-vars.sh
else
    echo "⚠️  Fichier de secrets non trouvé: rhDemo/secrets/env-vars.sh"
fi

cd "$EPHEMERE_PATH"

# Variables d'environnement pour Docker Compose
export APP_VERSION="${APP_VERSION:-build-${BUILD_NUMBER:-unknown}}"
export WORKSPACE=$(pwd)

# Export explicite des variables critiques (pour éviter que .env les écrase)
export RHDEMO_DB_PASSWORD="${RHDEMO_DATASOURCE_PASSWORD_PG}"
export KEYCLOAK_DB_PASSWORD="${KEYCLOAK_DB_PASSWORD}"
export KEYCLOAK_ADMIN_USER="${KEYCLOAK_ADMIN_USER}"
export KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD}"
export RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET="${RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET}"

# Réactiver l'écho APRÈS les exports de secrets
set -x

# Confirmation (sans afficher les secrets)
echo "✅ Secrets exportés avec succès (secrets non affichés pour sécurité)"

# IMPORTANT: Nettoyage forcé des conteneurs existants pour éviter les conflits de noms
echo "🧹 Nettoyage des conteneurs ephemere existants..."
docker rm -f keycloak-ephemere-db rhdemo-ephemere-db keycloak-ephemere rhdemo-ephemere-app rhdemo-ephemere-nginx 2>/dev/null || true
echo "✅ Conteneurs existants supprimés"

# Démarrer les conteneurs
echo "🚀 Démarrage des conteneurs Docker..."
docker-compose -f docker-compose.yml -p "$COMPOSE_PROJECT" up -d

# Connecter Jenkins au réseau ephemere pour accès direct aux services
echo "🔗 Connexion de Jenkins au réseau ephemere..."
# Trouver le conteneur Jenkins principal (pas l'agent)
JENKINS_CONTAINER=$(docker ps --filter "name=jenkins" --format "{{.Names}}" | grep -v agent | head -n 1)
echo "Conteneur Jenkins trouvé: $JENKINS_CONTAINER"

if [ -n "$JENKINS_CONTAINER" ]; then
    docker network connect rhdemo-ephemere-network "$JENKINS_CONTAINER" 2>/dev/null || echo "⚠️  Jenkins déjà connecté au réseau"
    echo "✅ Jenkins ($JENKINS_CONTAINER) connecté au réseau rhdemo-ephemere-network"
else
    echo "❌ ERREUR: Conteneur Jenkins introuvable!"
    docker ps --filter "name=jenkins"
fi

# Attendre que les conteneurs démarrent (augmenté pour Keycloak)
echo "⏳ Attente démarrage conteneurs (20s)..."
sleep 20

# Copier les configurations nginx et certificats SSL
echo "📋 Copie des configurations nginx..."
docker cp nginx/nginx.conf rhdemo-ephemere-nginx:/etc/nginx/nginx.conf
docker cp nginx/conf.d/. rhdemo-ephemere-nginx:/etc/nginx/conf.d/

if [ -d "certs" ]; then
    docker cp certs/. rhdemo-ephemere-nginx:/etc/nginx/ssl/
    echo "✅ Configurations nginx et certificats copiés"
else
    echo "✅ Configurations nginx copiées (certificats manquants)"
fi

# Recharger la configuration nginx pour appliquer les changements
echo "🔄 Rechargement de la configuration nginx..."
docker exec rhdemo-ephemere-nginx nginx -t  # Test de la config
docker exec rhdemo-ephemere-nginx nginx -s reload  # Reload
echo "✅ Nginx rechargé avec la nouvelle configuration HTTPS"

# Vérifier que nginx écoute réellement sur le port 443
echo "🔍 Vérification que nginx écoute sur le port 443..."
if docker exec rhdemo-ephemere-nginx netstat -tuln | grep -q ':443'; then
    echo "✅ Nginx écoute sur le port 443 (HTTPS)"
else
    echo "❌ ERREUR: Nginx n'écoute PAS sur le port 443!"
    echo "Ports écoutés par nginx:"
    docker exec rhdemo-ephemere-nginx netstat -tuln
    exit 1
fi

echo "✅ Environnement Docker opérationnel:"
docker-compose -p "$COMPOSE_PROJECT" ps
