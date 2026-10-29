#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Réparation du cluster KinD après redémarrage (Docker, machine, mise à jour OS)
#
# Contrôle l’IP du nœud (changée → Cilium/CoreDNS périmés) et ajoute :
#   - le raccordement du registre local `kind-registry` au réseau docker
#     `kind` : la connexion n'est pas persistante, elle saute quand le
#     registre est recréé (compose Jenkins). Le nœud ne résout alors plus
#     `kind-registry` et les pods passent en ImagePullBackOff ;
#   - le redémarrage des pods en ImagePullBackOff / ErrImagePull une fois
#     le registre à nouveau joignable (évite d'attendre le backoff).
#
# Idempotent, sans effet si le cluster est sain.
#
# Usage : ./repair-cluster-after-restart.sh [--check]
#   --check : diagnostic seul, aucune action (code retour 1 si anomalie)
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-rhdemo}"
NODE_CONTAINER="${CLUSTER_NAME}-control-plane"
KUBE_CONTEXT="${K8S_CONTEXT:-kind-${CLUSTER_NAME}}"
KIND_NETWORK="${KIND_NETWORK:-kind}"
REGISTRY_CONTAINER="${REGISTRY_CONTAINER:-kind-registry}"
CILIUM_NAMESPACE="${CILIUM_NAMESPACE:-cilium-system}"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-300s}"

CHECK_ONLY=false
[ "${1:-}" = "--check" ] && CHECK_ONLY=true

log() { echo "[repair-cluster] $*"; }
k() { kubectl --context "$KUBE_CONTEXT" "$@"; }

PROBLEMS=()
FIX_CILIUM=false
FIX_REGISTRY=false

# 0. Conteneurs docker : nœud KinD et registre démarrés ?
for c in "$NODE_CONTAINER" "$REGISTRY_CONTAINER"; do
    state=$(docker inspect "$c" --format '{{.State.Status}}' 2>/dev/null || echo absent)
    if [ "$state" != "running" ]; then
        PROBLEMS+=("conteneur $c : état '$state'")
        if [ "$state" = "exited" ] || [ "$state" = "created" ]; then
            if $CHECK_ONLY; then continue; fi
            log "Démarrage de $c..."
            docker start "$c" >/dev/null
        fi
    fi
done

# Attendre que l'API réponde (démarrage de la machine)
if ! $CHECK_ONLY; then
    for _ in $(seq 1 60); do
        k get nodes >/dev/null 2>&1 && break
        sleep 5
    done
fi
k get nodes >/dev/null 2>&1 || { log "API Kubernetes injoignable (contexte $KUBE_CONTEXT)"; exit 2; }

# 1. Registre local raccordé au réseau docker "kind" ?
if docker inspect "$REGISTRY_CONTAINER" >/dev/null 2>&1; then
    if ! docker inspect "$REGISTRY_CONTAINER" \
            --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' \
            | grep -qx "$KIND_NETWORK"; then
        PROBLEMS+=("$REGISTRY_CONTAINER absent du réseau docker '$KIND_NETWORK' (pull d'images impossible)")
        FIX_REGISTRY=true
    fi
else
    PROBLEMS+=("conteneur $REGISTRY_CONTAINER introuvable (voir infra/jenkins-docker)")
fi

# 2. IP du nœud : pods en cours d'exécution dont le hostIP est périmé
DOCKER_IP=$(docker inspect "$NODE_CONTAINER" --format "{{ (index .NetworkSettings.Networks \"$KIND_NETWORK\").IPAddress }}")
log "IP du nœud (docker) : $DOCKER_IP"

STALE=$(k get pods -A --field-selector=status.phase=Running \
    -o jsonpath='{range .items[*]}{.status.hostIP}{" "}{.metadata.namespace}/{.metadata.name}{"\n"}{end}' \
    | awk -v ip="$DOCKER_IP" '$1 != "" && $1 != ip {print $2}')
if [ -n "$STALE" ]; then
    PROBLEMS+=("pods avec un hostIP périmé : $(echo "$STALE" | head -5 | tr '\n' ' ')")
    FIX_CILIUM=true
fi

# 3. Le DNS du cluster répond-il depuis un pod ?
DNS_POD=$(k -n rhdemo-stagingkub get pods -l app=postgresql-rhdemo -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$DNS_POD" ] && ! k -n rhdemo-stagingkub exec "$DNS_POD" -c postgresql -- \
        nslookup kubernetes.default.svc.cluster.local >/dev/null 2>&1; then
    PROBLEMS+=("résolution DNS en échec depuis $DNS_POD")
    FIX_CILIUM=true
fi

# 4. Pods en échec de pull d'image
PULL_FAIL=$(k get pods -A \
    -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{" "}{range .status.containerStatuses[*]}{.state.waiting.reason}{" "}{end}{range .status.initContainerStatuses[*]}{.state.waiting.reason}{" "}{end}{"\n"}{end}' \
    | awk '/ImagePullBackOff|ErrImagePull/ {print $1}')
if [ -n "$PULL_FAIL" ]; then
    PROBLEMS+=("pods en échec de pull d'image : $(echo "$PULL_FAIL" | head -5 | tr '\n' ' ')")
fi

if [ ${#PROBLEMS[@]} -eq 0 ]; then
    log "OK : aucune anomalie détectée"
    exit 0
fi

for p in "${PROBLEMS[@]}"; do log "ANOMALIE : $p"; done
$CHECK_ONLY && exit 1

# ─── Correctifs ───────────────────────────────────────────────

if $FIX_REGISTRY; then
    log "Raccordement de $REGISTRY_CONTAINER au réseau $KIND_NETWORK..."
    docker network connect "$KIND_NETWORK" "$REGISTRY_CONTAINER" --alias "$REGISTRY_CONTAINER"
    if docker exec "$NODE_CONTAINER" getent hosts "$REGISTRY_CONTAINER" >/dev/null 2>&1; then
        log "Le nœud résout $REGISTRY_CONTAINER"
    else
        log "ATTENTION : le nœud ne résout toujours pas $REGISTRY_CONTAINER"
    fi
fi

if $FIX_CILIUM; then
    log "Redémarrage de Cilium..."
    k -n "$CILIUM_NAMESPACE" rollout restart ds/cilium
    k -n "$CILIUM_NAMESPACE" rollout status ds/cilium --timeout="$ROLLOUT_TIMEOUT"

    log "Redémarrage de CoreDNS..."
    k -n kube-system rollout restart deploy/coredns
    k -n kube-system rollout status deploy/coredns --timeout="$ROLLOUT_TIMEOUT"
fi

if [ -n "$PULL_FAIL" ]; then
    log "Recréation des pods en échec de pull (le contrôleur les relance sans backoff)..."
    for ref in $PULL_FAIL; do
        k -n "${ref%%/*}" delete pod "${ref##*/}" --wait=false
    done
fi

log "Terminé. Contrôle : kubectl --context $KUBE_CONTEXT get pods -A | grep -v -E 'Running|Completed'"
