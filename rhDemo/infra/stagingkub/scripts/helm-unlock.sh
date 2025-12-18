#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════
# Script de déblocage des verrous Helm
# ═══════════════════════════════════════════════════════════════════════════
#
# USAGE:
#   ./helm-unlock.sh [NAMESPACE] [RELEASE_NAME]
#
# EXEMPLES:
#   ./helm-unlock.sh rhdemo-stagingkub rhdemo
#   ./helm-unlock.sh                              # Utilise les valeurs par défaut
#
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Configuration par défaut
DEFAULT_NAMESPACE="rhdemo-stagingkub"
DEFAULT_RELEASE="rhdemo"

NAMESPACE="${1:-$DEFAULT_NAMESPACE}"
RELEASE_NAME="${2:-$DEFAULT_RELEASE}"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                 DÉBLOCAGE VERROU HELM                         ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Configuration:"
echo "   Namespace: $NAMESPACE"
echo "   Release: $RELEASE_NAME"
echo ""

# Vérifier que kubectl est disponible
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl n'est pas installé ou pas dans le PATH"
    exit 1
fi

# Vérifier que le namespace existe
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo "❌ Le namespace '$NAMESPACE' n'existe pas"
    exit 1
fi

# Lister tous les secrets Helm pour ce release
echo "🔍 Recherche des secrets Helm pour le release '$RELEASE_NAME'..."
SECRETS=$(kubectl get secrets -n "$NAMESPACE" -l owner=helm,name="$RELEASE_NAME" -o name 2>/dev/null)

if [ -z "$SECRETS" ]; then
    echo "❌ Aucun release Helm trouvé pour '$RELEASE_NAME' dans '$NAMESPACE'"
    exit 1
fi

echo "✅ Secrets trouvés:"
echo "$SECRETS" | sed 's/^/   - /'
echo ""

# Vérifier l'état de chaque secret
echo "🔍 Vérification de l'état des releases..."
FOUND_PENDING=false
PENDING_SECRETS=()

for SECRET in $SECRETS; do
    SECRET_NAME=$(echo "$SECRET" | sed 's|secret/||')
    VERSION=$(echo "$SECRET_NAME" | grep -oP 'v\d+$' || echo "?")

    # Extraire le statut (avec gestion d'erreur robuste)
    STATUS=$(kubectl get "$SECRET" -n "$NAMESPACE" \
        -o jsonpath='{.data.release}' 2>/dev/null \
        | base64 -d 2>/dev/null \
        | base64 -d 2>/dev/null \
        | gzip -d 2>/dev/null \
        | jq -r '.info.status' 2>/dev/null || echo "unknown")

    if [[ "$STATUS" == "pending-"* ]]; then
        FOUND_PENDING=true
        PENDING_SECRETS+=("$SECRET_NAME:$STATUS")
        echo "   🔒 $SECRET_NAME ($VERSION) - État: $STATUS"
    else
        echo "   ✓ $SECRET_NAME ($VERSION) - État: $STATUS"
    fi
done

echo ""

if [ "$FOUND_PENDING" = false ]; then
    echo "✅ Aucune release bloquée trouvée"
    echo ""
    echo "État actuel du release:"
    helm status "$RELEASE_NAME" -n "$NAMESPACE" 2>&1 | head -10 || echo "   Release non trouvé"
    exit 0
fi

# Demander confirmation
echo "⚠️  Releases bloquées détectées:"
for item in "${PENDING_SECRETS[@]}"; do
    echo "   - ${item%%:*} (${item##*:})"
done
echo ""

if [ -t 0 ]; then
    # Mode interactif
    read -p "Voulez-vous supprimer ces releases bloquées ? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Opération annulée"
        exit 0
    fi
else
    # Mode non-interactif (appelé depuis un script)
    echo "⚠️  Mode non-interactif: suppression automatique"
fi

# Supprimer les releases bloquées
echo ""
echo "🗑️  Suppression des releases bloquées..."
DELETED_COUNT=0

for item in "${PENDING_SECRETS[@]}"; do
    SECRET_NAME="${item%%:*}"
    STATUS="${item##*:}"

    echo "   ➤ Suppression de $SECRET_NAME..."

    if kubectl delete secret "$SECRET_NAME" -n "$NAMESPACE" 2>/dev/null; then
        echo "      ✅ Supprimé"
        DELETED_COUNT=$((DELETED_COUNT + 1))
    else
        echo "      ❌ Échec de la suppression"
    fi
done

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                    RÉSULTAT                                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Statistiques:"
echo "   Releases bloquées trouvées: ${#PENDING_SECRETS[@]}"
echo "   Releases supprimées: $DELETED_COUNT"
echo ""

if [ $DELETED_COUNT -gt 0 ]; then
    echo "✅ Déblocage terminé avec succès"
    echo ""
    echo "📋 État actuel du release:"
    helm status "$RELEASE_NAME" -n "$NAMESPACE" 2>&1 | head -10 || echo "   Release non trouvé ou partiellement nettoyé"
    echo ""
    echo "🚀 Vous pouvez maintenant relancer le déploiement Helm"
else
    echo "⚠️  Aucune release n'a pu être supprimée"
    exit 1
fi
