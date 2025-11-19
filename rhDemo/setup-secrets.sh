#!/bin/bash
# Script d'initialisation des secrets pour RHDemo
# Usage: ./setup-secrets.sh

set -e  # Arrêter en cas d'erreur

SECRETS_DIR="secrets"
SECRETS_FILE="$SECRETS_DIR/secrets.yml"
SECRETS_TEMPLATE="$SECRETS_DIR/secrets.yml.template"
SECRETS_DEV="$SECRETS_DIR/secrets-dev.yml"

echo "🔐 Configuration des secrets RHDemo"
echo "===================================="
echo ""

# Vérifier que nous sommes à la racine du projet
if [ ! -f "pom.xml" ]; then
    echo "❌ Erreur : Ce script doit être exécuté depuis la racine du projet rhDemo"
    exit 1
fi

# Créer le répertoire secrets s'il n'existe pas
if [ ! -d "$SECRETS_DIR" ]; then
    echo "📁 Création du répertoire secrets/"
    mkdir -p "$SECRETS_DIR"
fi

# Vérifier si secrets.yml existe déjà
if [ -f "$SECRETS_FILE" ]; then
    echo "⚠️  Le fichier secrets.yml existe déjà !"
    echo ""
    read -p "Voulez-vous le remplacer ? (y/N) : " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "✅ Conservation du fichier existant"
        exit 0
    fi
    echo "📝 Création d'une sauvegarde : secrets.yml.backup"
    cp "$SECRETS_FILE" "$SECRETS_FILE.backup"
fi

# Copier le template
if [ -f "$SECRETS_TEMPLATE" ]; then
    echo "📄 Copie du template vers secrets.yml"
    cp "$SECRETS_TEMPLATE" "$SECRETS_FILE"
else
    echo "❌ Erreur : Template non trouvé ($SECRETS_TEMPLATE)"
    exit 1
fi

echo ""
echo "✅ Fichier secrets.yml créé avec succès !"
echo ""
echo "📝 Prochaines étapes :"
echo ""
echo "1. Éditer le fichier avec vos secrets réels :"
echo "   nano $SECRETS_FILE"
echo ""
echo "2. Définir les permissions restrictives :"
echo "   chmod 600 $SECRETS_FILE"
echo ""
echo "3. Vérifier que secrets.yml est dans .gitignore :"
echo "   grep 'secrets.yml' .gitignore"
echo ""
echo "4. Tester l'application :"
echo "   ./mvnw spring-boot:run"
echo ""
echo "⚠️  ATTENTION : Ne jamais commiter secrets.yml sur Git !"
echo ""
echo "📚 Documentation complète : voir SECRETS_MANAGEMENT.md"
