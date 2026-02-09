#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# SCRIPT DE TEST JENKINS - Vérification complète
# ═══════════════════════════════════════════════════════════════════

set -e

echo "🧪 Tests de l'infrastructure Jenkins RHDemo"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ────────────────────────────────────────────────────────────────
# TEST 1 : Conteneurs en cours d'exécution
# ────────────────────────────────────────────────────────────────

echo "1️⃣  Vérification des conteneurs Docker..."
if docker compose ps | grep -q "Up"; then
    echo "✅ Conteneurs en cours d'exécution"
    docker compose ps
else
    echo "❌ Aucun conteneur en cours d'exécution"
    exit 1
fi

echo ""

# ────────────────────────────────────────────────────────────────
# TEST 2 : Jenkins accessible
# ────────────────────────────────────────────────────────────────

echo "2️⃣  Vérification de l'accès à Jenkins..."
if curl -sf http://localhost:8080/login > /dev/null; then
    echo "✅ Jenkins accessible sur http://localhost:8080"
else
    echo "❌ Jenkins non accessible"
    echo "   Vérifiez les logs: docker compose logs jenkins"
    exit 1
fi

echo ""

# ────────────────────────────────────────────────────────────────
# TEST 3 : Outils installés dans l'agent (builder)
# ────────────────────────────────────────────────────────────────

echo "3️⃣  Vérification des outils dans l'agent builder..."

if docker compose ps jenkins-agent | grep -q "Up"; then
    echo "   ☕ Java version:"
    docker compose exec -T jenkins-agent /opt/java/temurin-25/bin/java --version 2>&1 | head -1

    echo "   📦 Maven version:"
    docker compose exec -T jenkins-agent mvn -version 2>&1 | head -1

    echo "   🐳 Docker version:"
    docker compose exec -T jenkins-agent docker --version

    echo "   🐳 Docker Compose version:"
    docker compose exec -T jenkins-agent docker-compose --version

    echo "   ☸️  kubectl version:"
    docker compose exec -T jenkins-agent kubectl version --client --short 2>&1 | head -1

    echo "   ⎈  Helm version:"
    docker compose exec -T jenkins-agent helm version --short 2>&1 | head -1

    echo "✅ Tous les outils sont installés dans l'agent"
else
    echo "⚠️  L'agent builder n'est pas démarré"
    echo "   Configurez JENKINS_SECRET dans .env puis: docker compose up -d jenkins-agent"
fi

echo ""

# ────────────────────────────────────────────────────────────────
# TEST 4 : Docker-in-Docker fonctionnel (sur l'agent)
# ────────────────────────────────────────────────────────────────

echo "4️⃣  Test Docker-in-Docker (agent)..."

if docker compose exec -T jenkins-agent docker ps > /dev/null 2>&1; then
    echo "✅ Docker-in-Docker fonctionne sur l'agent"
    echo "   Conteneurs visibles depuis l'agent:"
    docker compose exec -T jenkins-agent docker ps --format "table {{.Names}}\t{{.Status}}" | head -5
else
    echo "⚠️  Docker-in-Docker ne fonctionne pas sur l'agent"
    echo "   Vérifiez les permissions du socket Docker et le GID docker (984)"
fi

echo ""

# ────────────────────────────────────────────────────────────────
# TEST 5 : Volumes persistants
# ────────────────────────────────────────────────────────────────

echo "5️⃣  Vérification des volumes..."

VOLUMES=$(docker volume ls | grep rhdemo-jenkins | wc -l)
if [ "$VOLUMES" -ge 2 ]; then
    echo "✅ Volumes persistants créés ($VOLUMES volumes)"
    docker volume ls | grep rhdemo-jenkins
else
    echo "⚠️  Volumes manquants"
fi

echo ""

# ────────────────────────────────────────────────────────────────
# TEST 6 : Plugins Jenkins
# ────────────────────────────────────────────────────────────────

echo "6️⃣  Vérification des plugins Jenkins..."

PLUGINS_COUNT=$(docker compose exec -T jenkins jenkins-plugin-cli --list 2>/dev/null | wc -l || echo "0")
if [ "$PLUGINS_COUNT" -gt 50 ]; then
    echo "✅ Plugins installés: $PLUGINS_COUNT plugins"
else
    echo "⚠️  Peu de plugins installés ($PLUGINS_COUNT)"
    echo "   Les plugins peuvent encore être en cours d'installation"
fi

echo ""

# ────────────────────────────────────────────────────────────────
# TEST 7 : Configuration JCasC
# ────────────────────────────────────────────────────────────────

echo "7️⃣  Vérification Configuration as Code..."

if docker compose exec -T jenkins test -f /var/jenkins_home/casc_configs/jenkins.yaml; then
    echo "✅ Fichier JCasC présent"
else
    echo "⚠️  Fichier JCasC manquant"
fi

echo ""

# ────────────────────────────────────────────────────────────────
# TEST 8 : Réseau Docker
# ────────────────────────────────────────────────────────────────

echo "8️⃣  Vérification du réseau Docker..."

if docker network ls | grep -q "rhdemo-jenkins-network"; then
    echo "✅ Réseau Docker créé"
    docker network inspect rhdemo-jenkins-network --format '{{len .Containers}} conteneurs connectés'
else
    echo "❌ Réseau Docker manquant"
fi

echo ""

# ────────────────────────────────────────────────────────────────
# TEST 9 : Test de compilation Maven simple
# ────────────────────────────────────────────────────────────────

echo "9️⃣  Test Maven sur l'agent (version uniquement)..."

if docker compose exec -T jenkins-agent mvn --version > /dev/null 2>&1; then
    echo "✅ Maven opérationnel sur l'agent"
else
    echo "⚠️  Maven non disponible (agent pas démarré ou problème)"
fi

echo ""

# ────────────────────────────────────────────────────────────────
# TEST 10 : Healthcheck
# ────────────────────────────────────────────────────────────────

echo "🔟 Vérification du healthcheck..."

HEALTH=$(docker inspect --format='{{.State.Health.Status}}' rhdemo-jenkins 2>/dev/null || echo "unknown")
echo "   Status: $HEALTH"

if [ "$HEALTH" = "healthy" ]; then
    echo "✅ Jenkins est en bonne santé"
elif [ "$HEALTH" = "starting" ]; then
    echo "⏳ Jenkins est en cours de démarrage"
else
    echo "⚠️  Healthcheck: $HEALTH"
fi

echo ""

# ────────────────────────────────────────────────────────────────
# RÉSUMÉ
# ────────────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════════"
echo "✅ Tests terminés !"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📊 Résumé:"
echo "   • Jenkins: http://localhost:8080"
echo "   • Registry: http://localhost:5000"
echo ""
echo "🎯 Prochaines étapes:"
echo "   1. Se connecter à Jenkins"
echo "   2. Créer un pipeline pour RHDemo"
echo "   3. Lancer un build de test"
echo ""
echo "📚 Documentation: cat README.md"
echo ""
