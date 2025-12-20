#!/bin/bash
# Script: cleanup-secrets.sh
# Description: Nettoie de manière sécurisée les fichiers contenant des secrets
# Usage: ./cleanup-secrets.sh

set -euo pipefail

echo "🧹 Nettoyage sécurisé des fichiers de secrets..."

# Liste des fichiers de secrets à nettoyer
SECRET_FILES=(
    "rhDemo/secrets/env-vars.sh"
    "rhDemo/secrets/secrets-rhdemo.yml"
    "rhDemo/secrets/secrets-decrypted.yml"
    "rhDemoInitKeycloak/src/main/resources/application-ephemere.yml"
)

# Fonction pour supprimer un fichier de manière sécurisée
secure_delete() {
    local file="$1"

    if [ -f "$file" ]; then
        # Écraser avec des zéros avant suppression (sécurité supplémentaire)
        if command -v shred >/dev/null 2>&1; then
            shred -vfz -n 3 "$file" 2>/dev/null || rm -f "$file"
        else
            # Si shred n'est pas disponible, utiliser dd
            dd if=/dev/zero of="$file" bs=4096 count=$(stat --format='%s' "$file" 2>/dev/null | awk '{print int($1/4096)+1}') 2>/dev/null || true
            rm -f "$file"
        fi
        echo "✅ $file supprimé de manière sécurisée"
    else
        echo "ℹ️  $file n'existe pas (rien à supprimer)"
    fi
}

# Supprimer tous les fichiers de secrets
for file in "${SECRET_FILES[@]}"; do
    secure_delete "$file"
done

echo "✅ Nettoyage terminé"
