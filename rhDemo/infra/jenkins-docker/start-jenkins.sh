#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# SCRIPT DE DÉMARRAGE JENKINS
# Usage: ./start-jenkins.sh [OPTIONS]
#
# Options:
#   --rebuild        Force la reconstruction de l'image même si à jour
#   --clean-plugins  Supprime les plugins du volume avant rebuild
#                    (utile après modification de plugins.txt)
#
# Exemples:
#   ./start-jenkins.sh                      # Démarrage normal
#   ./start-jenkins.sh --rebuild            # Force rebuild image
#   ./start-jenkins.sh --clean-plugins      # Nettoie plugins + rebuild
#   ./start-jenkins.sh --rebuild --clean-plugins  # Les deux
# ═══════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Démarrage de Jenkins pour RHDemo"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ────────────────────────────────────────────────────────────────
# VÉRIFICATIONS PRÉALABLES
# ────────────────────────────────────────────────────────────────

echo "📋 Vérifications préalables..."

# Vérifier que Docker est installé et en cours d'exécution
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Veuillez installer Docker."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker n'est pas en cours d'exécution. Veuillez démarrer Docker."
    exit 1
fi

echo "✅ Docker est installé et en cours d'exécution"

# Vérifier que docker compose est installé
if ! command -v docker compose &> /dev/null; then
    echo "❌ docker compose n'est pas installé. Veuillez installer docker compose."
    exit 1
fi

echo "✅ docker compose est installé"

# ────────────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────────────

echo ""
echo "⚙️  Configuration..."

# Copier le fichier .env.example si .env n'existe pas
if [ ! -f .env ]; then
    echo "📝 Création du fichier .env depuis .env.example"
    cp .env.example .env
    echo "⚠️  IMPORTANT : Éditez le fichier .env avec vos valeurs réelles !"
    echo ""
    read -p "Voulez-vous éditer le fichier .env maintenant ? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} .env
    fi
fi

# ────────────────────────────────────────────────────────────────
# BUILD DE L'IMAGE JENKINS PERSONNALISÉE
# ────────────────────────────────────────────────────────────────

echo ""
echo "🔨 Build de l'image Jenkins personnalisée..."

# Gestion de l'option --rebuild-plugins
FORCE_REBUILD=false
CLEAN_PLUGINS=false
for arg in "$@"; do
    case $arg in
        --rebuild)
            FORCE_REBUILD=true
            ;;
        --clean-plugins)
            CLEAN_PLUGINS=true
            ;;
    esac
done

if [ -f Dockerfile.jenkins ]; then
    # Calculer le hash combiné du Dockerfile ET de plugins.txt
    DOCKERFILE_HASH=$(md5sum Dockerfile.jenkins | cut -d' ' -f1)
    PLUGINS_HASH=$(md5sum plugins.txt 2>/dev/null | cut -d' ' -f1 || echo "")
    COMBINED_HASH="${DOCKERFILE_HASH}-${PLUGINS_HASH}"

    # Vérifier si l'image existe déjà
    if docker image inspect rhdemo-jenkins:latest &> /dev/null; then
        echo "ℹ️  Image Jenkins existante trouvée"

        # Vérifier si le Dockerfile OU plugins.txt a changé depuis le dernier build
        IMAGE_HASH=$(docker image inspect rhdemo-jenkins:latest --format '{{.Config.Labels.config_hash}}' 2>/dev/null || echo "")

        if [ "$FORCE_REBUILD" = true ]; then
            echo "🔄 Rebuild forcé demandé (--rebuild)..."
            NEED_REBUILD=true
        elif [ "$COMBINED_HASH" != "$IMAGE_HASH" ]; then
            echo "🔄 Configuration modifiée (Dockerfile ou plugins.txt), rebuild nécessaire..."
            NEED_REBUILD=true
        else
            echo "✅ Image Jenkins à jour, pas de rebuild nécessaire"
            NEED_REBUILD=false
        fi

        if [ "$NEED_REBUILD" = true ]; then
            # Nettoyer les plugins si demandé ou si plugins.txt a changé
            if [ "$CLEAN_PLUGINS" = true ]; then
                echo "🧹 Nettoyage du répertoire plugins Jenkins (--clean-plugins)..."
                docker run --rm -v rhdemo-jenkins-home:/var/jenkins_home alpine sh -c "rm -rf /var/jenkins_home/plugins/* 2>/dev/null || true"
                echo "✅ Répertoire plugins nettoyé"
            fi

            docker build -f Dockerfile.jenkins --label config_hash=$COMBINED_HASH -t rhdemo-jenkins:latest .
            echo "✅ Image Jenkins reconstruite avec succès"
        fi
    else
        echo "📦 Première construction de l'image..."
        docker build -f Dockerfile.jenkins --label config_hash=$COMBINED_HASH -t rhdemo-jenkins:latest .
        echo "✅ Image Jenkins construite avec succès"
    fi

    # Afficher les versions des outils installés
    echo ""
    echo "📦 Outils Kubernetes installés dans Jenkins:"
    docker run --rm rhdemo-jenkins:latest sh -c "
        (kubectl version --client --short 2>/dev/null || echo '  kubectl: non installé') &&
        (helm version --short 2>/dev/null || echo '  helm: non installé') &&
        (kind --version 2>/dev/null || echo '  kind: non installé')
    " 2>/dev/null || echo "  ℹ️  Vérification des outils ignorée"
else
    echo "⚠️  Dockerfile.jenkins non trouvé, utilisation de l'image officielle"
fi

# ────────────────────────────────────────────────────────────────
# DÉMARRAGE DES CONTENEURS
# ────────────────────────────────────────────────────────────────

echo ""
echo "🚀 Démarrage des conteneurs Docker..."

docker compose up -d

echo ""
echo "⏳ Attente du démarrage de Jenkins (peut prendre 1-2 minutes)..."

# Attendre que Jenkins soit prêt
MAX_WAIT=120
WAIT_TIME=0
while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    if docker compose exec -T jenkins curl -s http://localhost:8080/login > /dev/null 2>&1; then
        echo "✅ Jenkins est démarré et prêt !"
        break
    fi
    echo -n "."
    sleep 5
    WAIT_TIME=$((WAIT_TIME + 5))
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo ""
    echo "⚠️  Jenkins met du temps à démarrer. Vérifiez les logs avec:"
    echo "   docker compose logs -f jenkins"
fi

# ────────────────────────────────────────────────────────────────
# RÉCUPÉRATION DU MOT DE PASSE INITIAL (si nécessaire)
# ────────────────────────────────────────────────────────────────

echo ""
echo "🔑 Informations de connexion:"
echo "   URL: http://localhost:8080"
echo "   Utilisateur: admin"
echo "   Mot de passe: (défini dans .env ou admin123 par défaut)"
echo ""

# Si la configuration JCasC n'a pas fonctionné, afficher le mot de passe initial
if docker compose exec -T jenkins test -f /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null; then
    INITIAL_PASSWORD=$(docker compose exec -T jenkins cat /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null || echo "")
    if [ -n "$INITIAL_PASSWORD" ]; then
        echo "⚠️  Mot de passe initial Jenkins (première installation):"
        echo "   $INITIAL_PASSWORD"
        echo ""
    fi
fi

# ────────────────────────────────────────────────────────────────
# INFORMATIONS COMPLÉMENTAIRES
# ────────────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════════"
echo "✅ Jenkins est démarré avec succès !"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📚 Commandes utiles:"
echo "   • Voir les logs:        docker compose logs -f jenkins"
echo "   • Arrêter Jenkins:      docker compose stop"
echo "   • Redémarrer Jenkins:   docker compose restart jenkins"
echo "   • Arrêter tout:         docker compose down"
echo "   • Tout supprimer:       docker compose down -v"
echo ""
echo "🔧 Options de rebuild:"
echo "   • ./start-jenkins.sh --rebuild            # Force rebuild de l'image"
echo "   • ./start-jenkins.sh --clean-plugins      # Nettoie plugins + rebuild"
echo ""
echo "🌐 Services disponibles:"
echo "   • Jenkins:              http://localhost:8080"
echo "   • SonarQube:            http://localhost:9020"
echo "   • Docker Registry:      http://localhost:5000"
echo ""
echo "📖 Documentation:"
echo "   • README.md dans ce répertoire"
echo "   • Jenkinsfile à la racine du projet"
echo ""
echo "🔧 Prochaines étapes:"
echo "   1. Connectez-vous à Jenkins: http://localhost:8080"
echo "   2. Configurez les credentials manquants si nécessaire"
echo "   3. Créez un nouveau job Pipeline pointant vers le Jenkinsfile"
echo ""
