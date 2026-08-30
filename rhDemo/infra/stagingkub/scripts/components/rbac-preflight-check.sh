#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Préflight RBAC — à sourcer depuis chaque install-or-upgrade-*.sh
# ═══════════════════════════════════════════════════════════════
# Rendu à part, ce garde-fou comble un angle mort constaté deux fois en
# exploitation (Loki puis kube-prometheus-stack 87.17.0 et 87.19.0, cf.
# STAGINGKUB_REBUILD_PIPELINE.md) : `helm upgrade --dry-run=server` ne
# déclenche PAS le contrôle natif Kubernetes anti-élévation RBAC (« attempting
# to grant RBAC permissions not currently held ») sur les objets
# Role/ClusterRole/RoleBinding/ClusterRoleBinding qu'un chart embarque — un
# `kubectl apply --server-side --dry-run=server` sur ces mêmes objets, lui,
# le déclenche correctement (vérifié empiriquement). Sans ce préflight, une
# PR Renovate qui élargit les règles RBAC d'un ClusterRole tiers (ex:
# kube-state-metrics ajoutant de nouvelles ressources scrutées d'une version
# à l'autre) passe la validation pré-merge alors que l'upgrade réel échoue.
#
# Usage : source rbac-preflight-check.sh, puis appeler
#   rbac_preflight_check <release> <namespace> <chart-ref> [args helm template...]
# avec exactement les mêmes arguments (--version, -f, --set...) que l'appel
# `helm upgrade --install` qui suit, pour rendre le manifeste identique.
# ═══════════════════════════════════════════════════════════════

rbac_preflight_check() {
    local release="$1" namespace="$2" chart="$3"
    shift 3

    local manifest
    manifest="$(mktemp)"
    trap 'rm -f "$manifest"' RETURN

    helm template "$release" "$chart" --namespace "$namespace" "$@" 2>/dev/null | awk '
        BEGIN { doc = "" }
        /^---/ {
            test = doc "\n"
            if (test ~ /\nkind: (Cluster)?Role(Binding)?\n/) print doc "\n---"
            doc = ""
            next
        }
        { doc = doc "\n" $0 }
        END {
            test = doc "\n"
            if (test ~ /\nkind: (Cluster)?Role(Binding)?\n/) print doc
        }
    ' > "$manifest"

    if [ ! -s "$manifest" ]; then
        echo -e "${YELLOW}  - Préflight RBAC : aucun objet Role/ClusterRole rendu par ce chart, rien à vérifier${NC}"
        return 0
    fi

    echo -e "${YELLOW}  - Préflight RBAC : vérification que jenkins-infra-upgrader détient déjà toutes les règles Role/ClusterRole rendues par ce chart...${NC}"

    local apply_err other_err
    apply_err="$(kubectl apply --server-side --dry-run=server --force-conflicts -f "$manifest" 2>&1 >/dev/null || true)"

    if [ -z "$apply_err" ]; then
        echo -e "${GREEN}  ✓ Préflight RBAC OK${NC}"
        return 0
    fi

    # Le seul échec que ce garde-fou doit intercepter est l'anti-élévation RBAC
    # native de Kubernetes (« attempting to grant RBAC permissions not currently
    # held »). Sur une reconstruction complète depuis un cluster vierge
    # (init-stagingkub.sh), les namespaces cibles namespacés du chart n'existent
    # pas encore → « namespaces "X" not found » : ce n'est pas un problème de
    # droits, le `helm upgrade --install --create-namespace` qui suit les créera,
    # et le contrôle anti-élévation natif s'appliquera de toute façon au apply
    # réel. On ne fait donc échouer le préflight que sur les AUTRES erreurs.
    other_err="$(printf '%s\n' "$apply_err" | grep -vE '^[[:space:]]*$' | grep -vE 'namespaces?\s+"[^"]+"\s+not found' || true)"

    if [ -z "$other_err" ]; then
        echo -e "${YELLOW}  ⚠ Préflight RBAC ignoré : namespace(s) cible(s) pas encore créé(s) (reconstruction complète). Le contrôle anti-élévation RBAC natif s'appliquera au « helm upgrade » réel.${NC}"
        return 0
    fi

    echo -e "${RED}❌ Préflight RBAC échoué : ce chart requiert des permissions Role/ClusterRole que jenkins-infra-upgrader ne détient pas encore (ou erreur inattendue de kubectl apply --dry-run=server).${NC}"
    echo -e "${YELLOW}   Mettez à jour rhDemo/infra/stagingkub/rbac/jenkins-infra-upgrader-clusterrole.yaml (ou le Role namespacé concerné) avant de rejouer.${NC}"
    printf '%s\n' "$other_err" | sed 's/^/     /'
    return 1
}
