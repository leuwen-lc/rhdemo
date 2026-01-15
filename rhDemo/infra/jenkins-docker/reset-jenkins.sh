#!/bin/bash

##############################################################################
# Script de reset complet et relancement Jenkins
##############################################################################

set -e

echo "🛑 Arrêt des conteneurs Jenkins..."
docker compose down 2>/dev/null || true

echo "🗑️  Suppression des volumes (reset complet)..."
docker volume rm rhdemo-jenkins-home 2>/dev/null || true
docker volume rm rhdemo-maven-repository 2>/dev/null || true
docker volume rm rhdemo-jenkins-agent-workspace 2>/dev/null || true
docker volume rm rhdemo-sonarqube-data 2>/dev/null || true
docker volume rm rhdemo-sonarqube-extensions 2>/dev/null || true
docker volume rm rhdemo-sonarqube-logs 2>/dev/null || true
docker volume rm rhdemo-sonarqube-db 2>/dev/null || true
docker volume rm kind-registry-data 2>/dev/null || true

echo "🧹 Nettoyage des images Jenkins..."
docker rmi rhdemo-jenkins:latest 2>/dev/null || true

echo "🔨 Build de l'image Jenkins personnalisée..."
docker compose build --no-cache jenkins

echo "🚀 Démarrage de Jenkins..."
docker compose up -d jenkins

echo ""
echo "✅ Jenkins redémarré avec configuration fraîche"
echo ""
echo "📍 URL: http://localhost:8080"
echo "👤 Utilisateur: admin"
echo "🔑 Mot de passe: admin123"
echo ""
echo "⏳ Attendez 1-2 minutes que Jenkins démarre complètement..."
echo ""
echo "📋 Vérifier les logs:"
echo "   docker compose logs -f jenkins"
