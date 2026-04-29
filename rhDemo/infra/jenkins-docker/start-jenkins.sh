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

# Vérifier que les certificats du registry existent
# Les certificats peuvent être soit dans ./certs/registry/ soit déjà copiés dans /etc/docker/certs.d/
CERTS_LOCAL="./certs/registry/registry.crt"
CERTS_DOCKER="/etc/docker/certs.d/localhost:5000/ca.crt"

if [ -f "$CERTS_LOCAL" ] && [ -f "./certs/registry/registry.key" ]; then
    echo "✅ Certificats du registry présents (locaux)"

    # Proposer de copier vers Docker daemon si pas encore fait
    if [ ! -f "$CERTS_DOCKER" ]; then
        echo ""
        echo "⚠️  Le Docker daemon n'est pas configuré pour faire confiance au registry."
        echo ""
        echo "   Exécutez les commandes suivantes (avec sudo):"
        echo ""
        echo "   sudo mkdir -p /etc/docker/certs.d/localhost:5000"
        echo "   sudo cp $(pwd)/certs/registry/registry.crt /etc/docker/certs.d/localhost:5000/ca.crt"
        echo "   sudo systemctl restart docker"
        echo ""
        read -p "Voulez-vous exécuter ces commandes maintenant ? (Y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            sudo mkdir -p /etc/docker/certs.d/localhost:5000
            sudo cp "$(pwd)/certs/registry/registry.crt" /etc/docker/certs.d/localhost:5000/ca.crt
            echo "✅ Certificat copié. Redémarrage de Docker..."
            sudo systemctl restart docker
            echo "✅ Docker redémarré"
        else
            echo "⚠️  Le push vers le registry pourrait échouer sans cette configuration."
        fi
    fi
elif [ -f "$CERTS_DOCKER" ]; then
    # Les certificats sont déjà dans /etc/docker/certs.d/ mais pas en local
    # On peut les copier depuis là pour que le registry et Jenkins les utilisent
    echo "✅ Certificats du registry détectés dans Docker daemon"

    if [ ! -f "$CERTS_LOCAL" ]; then
        echo ""
        echo "ℹ️  Les certificats ne sont pas dans ./certs/registry/"
        echo "   Le registry et Jenkins en ont besoin pour démarrer."
        echo ""
        read -p "Voulez-vous copier le certificat depuis /etc/docker/certs.d/ ? (Y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            mkdir -p ./certs/registry
            sudo cp "$CERTS_DOCKER" "$CERTS_LOCAL"
            # Générer aussi la clé si elle n'existe pas (nécessaire pour le registry)
            if [ ! -f "./certs/registry/registry.key" ]; then
                echo "⚠️  La clé privée n'existe pas. Régénération des certificats..."
                ./init-registry-certs.sh
            else
                echo "✅ Certificat copié dans ./certs/registry/"
            fi
        else
            echo "⚠️  Le registry ne démarrera pas sans certificats dans ./certs/registry/"
            echo "   Vous pouvez les générer avec: ./init-registry-certs.sh"
        fi
    fi
else
    # Aucun certificat trouvé
    echo ""
    echo "⚠️  Certificats du registry manquants."
    echo "   Exécutez d'abord: ./init-registry-certs.sh"
    echo ""
    read -p "Voulez-vous générer les certificats maintenant ? (Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        ./init-registry-certs.sh
    else
        echo "⚠️  Le registry ne démarrera pas sans certificats."
        echo "   Vous pourrez les générer plus tard avec: ./init-registry-certs.sh"
    fi
fi

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
# BUILD DES IMAGES JENKINS (CONTROLLER + AGENT)
# ────────────────────────────────────────────────────────────────

echo ""
echo "🔨 Build des images Jenkins..."

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

# --- Build de l'image Controller ---
if [ -f Dockerfile.jenkins ]; then
    # Calculer le hash combiné du Dockerfile ET de plugins.txt
    DOCKERFILE_HASH=$(md5sum Dockerfile.jenkins | cut -d' ' -f1)
    PLUGINS_HASH=$(md5sum plugins.txt 2>/dev/null | cut -d' ' -f1 || echo "")
    COMBINED_HASH="${DOCKERFILE_HASH}-${PLUGINS_HASH}"

    # Vérifier si l'image existe déjà
    if docker image inspect rhdemo-jenkins:latest &> /dev/null; then
        echo "ℹ️  Image controller existante trouvée"

        # Vérifier si le Dockerfile OU plugins.txt a changé depuis le dernier build
        IMAGE_HASH=$(docker image inspect rhdemo-jenkins:latest --format '{{.Config.Labels.config_hash}}' 2>/dev/null || echo "")

        if [ "$FORCE_REBUILD" = true ]; then
            echo "🔄 Rebuild forcé demandé (--rebuild)..."
            NEED_REBUILD=true
        elif [ "$CLEAN_PLUGINS" = true ]; then
            echo "🔄 Mise à jour des plugins demandée (--clean-plugins)..."
            NEED_REBUILD=true
        elif [ "$COMBINED_HASH" != "$IMAGE_HASH" ]; then
            echo "🔄 Configuration modifiée (Dockerfile ou plugins.txt), rebuild nécessaire..."
            NEED_REBUILD=true
        else
            echo "✅ Image controller à jour, pas de rebuild nécessaire"
            NEED_REBUILD=false
        fi

        if [ "$NEED_REBUILD" = true ]; then
            # Nettoyer les plugins si demandé
            if [ "$CLEAN_PLUGINS" = true ]; then
                echo "🧹 Nettoyage du répertoire plugins Jenkins (--clean-plugins)..."
                docker run --rm -v rhdemo-jenkins-home:/var/jenkins_home alpine sh -c "rm -rf /var/jenkins_home/plugins/* 2>/dev/null || true"
                echo "✅ Répertoire plugins nettoyé"
                # --no-cache obligatoire : sans lui, Docker réutilise la couche RUN jenkins-plugin-cli
                # cachée et ne re-télécharge pas les versions à jour des plugins (:latest)
                docker build --no-cache -f Dockerfile.jenkins --label config_hash=$COMBINED_HASH -t rhdemo-jenkins:latest .
            else
                docker build -f Dockerfile.jenkins --label config_hash=$COMBINED_HASH -t rhdemo-jenkins:latest .
            fi
            echo "✅ Image controller reconstruite avec succès"
        fi
    else
        echo "📦 Première construction de l'image controller..."
        docker build -f Dockerfile.jenkins --label config_hash=$COMBINED_HASH -t rhdemo-jenkins:latest .
        echo "✅ Image controller construite avec succès"
    fi
else
    echo "⚠️  Dockerfile.jenkins non trouvé, utilisation de l'image officielle"
fi

# --- Build de l'image Agent ---
if [ -f Dockerfile.agent ]; then
    AGENT_HASH=$(md5sum Dockerfile.agent | cut -d' ' -f1)

    if docker image inspect rhdemo-jenkins-agent:latest &> /dev/null; then
        AGENT_IMAGE_HASH=$(docker image inspect rhdemo-jenkins-agent:latest --format '{{.Config.Labels.config_hash}}' 2>/dev/null || echo "")

        if [ "$FORCE_REBUILD" = true ]; then
            echo "🔄 Rebuild agent forcé (--rebuild)..."
            NEED_AGENT_REBUILD=true
        elif [ "$AGENT_HASH" != "$AGENT_IMAGE_HASH" ]; then
            echo "🔄 Dockerfile.agent modifié, rebuild nécessaire..."
            NEED_AGENT_REBUILD=true
        else
            echo "✅ Image agent à jour, pas de rebuild nécessaire"
            NEED_AGENT_REBUILD=false
        fi

        if [ "$NEED_AGENT_REBUILD" = true ]; then
            docker build -f Dockerfile.agent --label config_hash=$AGENT_HASH -t rhdemo-jenkins-agent:latest .
            echo "✅ Image agent reconstruite avec succès"
        fi
    else
        echo "📦 Première construction de l'image agent..."
        docker build -f Dockerfile.agent --label config_hash=$AGENT_HASH -t rhdemo-jenkins-agent:latest .
        echo "✅ Image agent construite avec succès"
    fi

    # Afficher les versions des outils installés dans l'agent
    echo ""
    echo "📦 Outils de build installés dans l'agent:"
    docker run --rm rhdemo-jenkins-agent:latest sh -c "
        echo \"  Java: \$(/opt/java/temurin-25/bin/java --version 2>&1 | head -1)\" &&
        echo \"  Maven: \$(mvn --version 2>&1 | head -1)\" &&
        (kubectl version --client --short 2>/dev/null || echo '  kubectl: non installé') &&
        (helm version --short 2>/dev/null || echo '  helm: non installé')
    " 2>/dev/null || echo "  ℹ️  Vérification des outils ignorée"
else
    echo "⚠️  Dockerfile.agent non trouvé"
fi

# ────────────────────────────────────────────────────────────────
# DÉMARRAGE DES CONTENEURS
# ────────────────────────────────────────────────────────────────

echo ""
echo "🚀 Démarrage des conteneurs Docker..."

# Le registry kind-registry est partagé entre KinD (stagingkub) et Jenkins.
# Si le conteneur existe déjà (créé par KinD), on démarre tout sauf le registry
# puis on connecte le registry existant au réseau Jenkins.
if docker ps -q -f name=^/kind-registry$ | grep -q .; then
    echo "ℹ️  Registry kind-registry déjà actif (partagé avec KinD), réutilisation..."
    docker compose up -d --no-deps jenkins docker-socket-proxy sonarqube sonarqube-db
    # S'assurer que le registry existant est connecté au réseau Jenkins
    docker network connect rhdemo-jenkins-network kind-registry 2>/dev/null || true
else
    docker compose up -d
fi

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
echo "   • Voir les logs:           docker compose logs -f jenkins"
echo "   • Logs agent (en cours):   docker logs \$(docker ps --filter ancestor=rhdemo-jenkins-agent --format '{{.Names}}' | head -n1)"
echo "   • Arrêter Jenkins:         docker compose stop"
echo "   • Redémarrer Jenkins:      docker compose restart jenkins"
echo "   • Arrêter tout:            docker compose down"
echo "   • Tout supprimer:          docker compose down -v"
echo ""
echo "🔧 Options de rebuild:"
echo "   • ./start-jenkins.sh --rebuild            # Force rebuild des images"
echo "   • ./start-jenkins.sh --clean-plugins      # Nettoie plugins + rebuild"
echo ""
echo "🌐 Services disponibles:"
echo "   • Jenkins:              http://localhost:8080"
echo "   • SonarQube:            http://localhost:9020"
echo "   • Docker Registry:      https://localhost:5000"
echo ""
echo "📖 Documentation:"
echo "   • README.md dans ce répertoire"
echo "   • QUICKSTART.md pour le guide de démarrage rapide"
echo ""
echo "🔧 Prochaines étapes:"
echo "   1. Connectez-vous à Jenkins: http://localhost:8080"
echo "   2. Vérifiez le Docker Cloud: Manage Jenkins > Clouds > docker-local > Test Connection"
echo "   3. Configurez les credentials (SOPS, SonarQube, etc.) - voir QUICKSTART.md"
echo "   4. Lancez un build : les agents éphémères sont créés automatiquement"
echo ""
