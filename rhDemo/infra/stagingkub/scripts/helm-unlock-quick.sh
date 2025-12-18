#!/bin/bash
# Quick unlock - supprime automatiquement tous les verrous pending sans confirmation
NAMESPACE="${1:-rhdemo-stagingkub}"
RELEASE="${2:-rhdemo}"
kubectl get secrets -n "$NAMESPACE" -l owner=helm,name="$RELEASE" -o name | while read secret; do
    status=$(kubectl get "$secret" -n "$NAMESPACE" -o jsonpath='{.data.release}' 2>/dev/null | base64 -d 2>/dev/null | base64 -d 2>/dev/null | gzip -d 2>/dev/null | jq -r '.info.status' 2>/dev/null)
    if [[ "$status" == "pending-"* ]]; then
        echo "🗑️  Suppression de $secret (état: $status)"
        kubectl delete "$secret" -n "$NAMESPACE"
    fi
done && echo "✅ Verrous Helm supprimés" || echo "❌ Aucun verrou trouvé"
