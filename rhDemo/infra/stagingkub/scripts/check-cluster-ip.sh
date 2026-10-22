#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Contrôle au démarrage : changement d'IP du nœud KinD
#
# Après un redémarrage de Docker/de la machine, le conteneur du nœud
# peut récupérer une autre IP sur le réseau docker "kind". Cilium garde
# alors des CiliumEndpoint avec l'ancienne IP ("could not take ownership
# of existing ciliumendpoint"), le DNS du cluster ne répond plus et les
# initContainers wait-for-db restent bloqués.
#
# Le script détecte cette situation et redémarre Cilium puis CoreDNS.
# Sans effet si le cluster est sain.
#
# Usage : ./check-cluster-ip.sh [--check]
#   --check : diagnostic seul, aucune action (code retour 1 si anomalie)
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-rhdemo}"
NODE_CONTAINER="${CLUSTER_NAME}-control-plane"
KUBE_CONTEXT="${K8S_CONTEXT:-kind-${CLUSTER_NAME}}"
CILIUM_NAMESPACE="${CILIUM_NAMESPACE:-cilium-system}"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-300s}"

CHECK_ONLY=false
[ "${1:-}" = "--check" ] && CHECK_ONLY=true

log() { echo "[check-cluster-ip] $*"; }
k() { kubectl --context "$KUBE_CONTEXT" "$@"; }

# Attendre que le conteneur du nœud et l'API répondent (démarrage de la machine)
for _ in $(seq 1 60); do
    k get nodes >/dev/null 2>&1 && break
    sleep 5
done
k get nodes >/dev/null 2>&1 || { log "API Kubernetes injoignable (contexte $KUBE_CONTEXT)"; exit 2; }

DOCKER_IP=$(docker inspect "$NODE_CONTAINER" --format '{{ (index .NetworkSettings.Networks "kind").IPAddress }}')
log "IP du nœud (docker) : $DOCKER_IP"

PROBLEMS=()

# 1. Pods en cours d'exécution dont le hostIP ne correspond plus à l'IP du nœud
STALE=$(k get pods -A --field-selector=status.phase=Running \
    -o jsonpath='{range .items[*]}{.status.hostIP}{" "}{.metadata.namespace}/{.metadata.name}{"\n"}{end}' \
    | awk -v ip="$DOCKER_IP" '$1 != "" && $1 != ip {print $2}')
if [ -n "$STALE" ]; then
    PROBLEMS+=("pods avec un hostIP périmé : $(echo "$STALE" | head -5 | tr '\n' ' ')")
fi

# 2. Le DNS du cluster répond-il depuis un pod ?
DNS_POD=$(k -n rhdemo-stagingkub get pods -l app=postgresql-rhdemo -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$DNS_POD" ] && ! k -n rhdemo-stagingkub exec "$DNS_POD" -c postgresql -- \
        nslookup kubernetes.default.svc.cluster.local >/dev/null 2>&1; then
    PROBLEMS+=("résolution DNS en échec depuis $DNS_POD")
fi

if [ ${#PROBLEMS[@]} -eq 0 ]; then
    log "OK : aucune anomalie détectée"
    exit 0
fi

for p in "${PROBLEMS[@]}"; do log "ANOMALIE : $p"; done
$CHECK_ONLY && exit 1

log "Redémarrage de Cilium..."
k -n "$CILIUM_NAMESPACE" rollout restart ds/cilium
k -n "$CILIUM_NAMESPACE" rollout status ds/cilium --timeout="$ROLLOUT_TIMEOUT"

log "Redémarrage de CoreDNS..."
k -n kube-system rollout restart deploy/coredns
k -n kube-system rollout status deploy/coredns --timeout="$ROLLOUT_TIMEOUT"

log "Terminé. Les pods bloqués en initContainer reprendront d'eux-mêmes."
