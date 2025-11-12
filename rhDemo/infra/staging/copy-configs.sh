#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Script de copie des configurations dans les conteneurs Docker
# 
# Ce script copie les fichiers de configuration dans les conteneurs
# au lieu d'utiliser des bind mounts, pour éviter les problèmes
# de layers Docker corrompus dans certains environnements CI/CD.
#
# Usage: ./copy-configs.sh
# Pré-requis: Les conteneurs doivent être démarrés
# ═══════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "  Copie des configurations dans les conteneurs Docker"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Vérifier que les conteneurs existent
if ! docker ps -a --format '{{.Names}}' | grep -q "rhdemo-staging-nginx"; then
    echo "❌ Erreur: Le conteneur nginx n'existe pas"
    echo "   Exécutez 'docker-compose up -d' d'abord"
    exit 1
fi

if ! docker ps -a --format '{{.Names}}' | grep -q "rhdemo-staging-db"; then
    echo "❌ Erreur: Le conteneur rhdemo-db n'existe pas"
    echo "   Exécutez 'docker-compose up -d' d'abord"
    exit 1
fi

echo "→ Copie des fichiers nginx..."

# Copier nginx.conf
echo "  • nginx.conf"
docker cp nginx/nginx.conf rhdemo-staging-nginx:/etc/nginx/nginx.conf

# Copier conf.d/
echo "  • conf.d/"
docker cp nginx/conf.d/. rhdemo-staging-nginx:/etc/nginx/conf.d/

# Copier certificats SSL
if [ -d "certs" ]; then
    echo "  • certs/ → /etc/nginx/ssl/"
    docker cp certs/. rhdemo-staging-nginx:/etc/nginx/ssl/
else
    echo "  ⚠️  Répertoire certs/ introuvable - nginx démarrera sans SSL"
fi

echo "✅ Fichiers nginx copiés"
echo ""

# Attendre que PostgreSQL soit prêt
echo "→ Attente PostgreSQL ready..."
timeout=30
while [ $timeout -gt 0 ]; do
    if docker exec rhdemo-staging-db pg_isready -U rhdemo >/dev/null 2>&1; then
        echo "✅ PostgreSQL ready"
        break
    fi
    sleep 2
    timeout=$((timeout - 2))
done

if [ $timeout -le 0 ]; then
    echo "❌ Timeout: PostgreSQL n'est pas prêt après 30s"
    exit 1
fi

echo ""
echo "→ Copie et exécution du schéma PostgreSQL..."

# Copier pgddl.sql
PGDDL_PATH="../../pgddl.sql"
if [ ! -f "$PGDDL_PATH" ]; then
    echo "❌ Erreur: Fichier pgddl.sql introuvable à $PGDDL_PATH"
    exit 1
fi

echo "  • Copie pgddl.sql → /tmp/schema.sql"
docker cp "$PGDDL_PATH" rhdemo-staging-db:/tmp/schema.sql

echo "  • Exécution du script SQL..."
docker exec rhdemo-staging-db psql -U rhdemo -d rhdemo -f /tmp/schema.sql

echo "✅ Schéma PostgreSQL initialisé"
echo ""

echo "→ Attente que rhdemo-app soit opérationnel..."
# Attendre que le conteneur rhdemo-app soit en état "healthy" ou "running"
timeout=60
while [ $timeout -gt 0 ]; do
    if docker ps --format '{{.Names}}\t{{.Status}}' | grep -q "rhdemo-staging-app.*Up"; then
        echo "✅ rhdemo-app démarré"
        break
    fi
    sleep 2
    timeout=$((timeout - 2))
done

if [ $timeout -le 0 ]; then
    echo "⚠️  Timeout: rhdemo-app n'est pas prêt - nginx peut échouer à résoudre le DNS"
fi

echo ""
echo "→ Redémarrage nginx pour charger la config..."
docker restart rhdemo-staging-nginx >/dev/null

# Attendre que nginx redémarre
sleep 3

if docker ps --format '{{.Names}}' | grep -q "rhdemo-staging-nginx"; then
    echo "✅ Nginx redémarré"
else
    echo "❌ Erreur: Nginx n'a pas redémarré correctement"
    echo "   Vérifiez les logs: docker logs rhdemo-staging-nginx"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Configurations copiées avec succès !"
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo "📋 État des services:"
docker-compose ps
