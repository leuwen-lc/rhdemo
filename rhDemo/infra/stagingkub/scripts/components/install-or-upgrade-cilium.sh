#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# Installation ou mise à jour en place de Cilium (CNI)
# ═══════════════════════════════════════════════════════════════
# Idempotent (helm upgrade --install) : appelé aussi bien lors d'une
# reconstruction complète (init-stagingkub.sh) que lors d'une mise à
# jour en place (pipeline Jenkins RHDemo-Stagingkub-Upgrade-Deploy,
# ServiceAccount jenkins-infra-upgrader).
#
# Contrainte Cilium : une seule version mineure à la fois
# (https://docs.cilium.io/en/stable/operations/upgrade/) — tout saut
# de version est refusé. Un job de preflight-check est exécuté avant
# l'upgrade réel pour valider la compatibilité des CRDs Cilium.
#
# Vérifié lors de la première exécution réelle (upgrade 1.18.6 → 1.19.5) :
# `helm upgrade` seul échoue avec "has no deployed releases" puisque la
# release cilium-preflight n'existe jamais entre deux upgrades (supprimée en
# fin de step) — `--install` est donc requis.
#
# Mode validation (HELM_DRY_RUN=true) : utilisé par la boucle de
# validation pré-merge de Jenkinsfile-Renovate — `helm upgrade
# --dry-run=server` uniquement, sans preflight (mutant) ni attente de
# rollout. Voir docs/STAGINGKUB_REBUILD_PIPELINE.md étape 4.
# ═══════════════════════════════════════════════════════════════

HELM_DRY_RUN="${HELM_DRY_RUN:-false}"

# renovate: datasource=helm depName=cilium registryUrl=https://helm.cilium.io/
CILIUM_VERSION="1.19.5"

# Namespace où vivent réellement les ressources Cilium (DaemonSet, Deployment,
# ConfigMap, ServiceAccounts...) — inchangé, c'est toujours kube-system.
CILIUM_NAMESPACE="kube-system"

# Namespace où Helm stocke l'état de la release (secrets sh.helm.release.v1.*,
# noms auto-incrémentés à chaque révision). Distinct de kube-system car RBAC
# Kubernetes ne permet pas de restreindre `list`/`get` sur secrets par
# resourceNames pour un nom qui change à chaque révision — accorder cet accès
# dans kube-system exposerait tous ses secrets (tokens bootstrap, certs
# kubeadm...) à jenkins-infra-upgrader. `namespaceOverride` (supporté par le
# chart Cilium) redirige les ressources réelles vers kube-system tout en
# gardant le stockage Helm dans ce namespace dédié à usage unique — voir
# jenkins-infra-upgrader-cilium-release-role.yaml.
CILIUM_HELM_NAMESPACE="cilium-release"

CILIUM_K8S_API_SERVER="rhdemo-control-plane"
CILIUM_K8S_API_PORT="6443"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}▶ Installation/mise à jour de Cilium ${CILIUM_VERSION}...${NC}"

if ! helm repo list 2>/dev/null | grep -q "^cilium"; then
    helm repo add cilium https://helm.cilium.io/
fi
helm repo update cilium > /dev/null

# ─── Contrainte de version : pas de saut de plus d'une version mineure ───
CURRENT_VERSION=$(helm list -n "${CILIUM_HELM_NAMESPACE}" -f '^cilium$' -o json 2>/dev/null | grep -o '"app_version":"[^"]*"' | cut -d'"' -f4 || true)

if [ -n "$CURRENT_VERSION" ] && [ "$CURRENT_VERSION" != "$CILIUM_VERSION" ]; then
    CURRENT_MINOR=$(echo "$CURRENT_VERSION" | cut -d. -f1-2 | tr -d '.')
    TARGET_MINOR=$(echo "$CILIUM_VERSION" | cut -d. -f1-2 | tr -d '.')
    DIFF=$((TARGET_MINOR - CURRENT_MINOR))
    if [ "$DIFF" -gt 1 ] || [ "$DIFF" -lt 0 ]; then
        echo -e "${RED}❌ Saut de version Cilium refusé : ${CURRENT_VERSION} → ${CILIUM_VERSION}${NC}"
        echo -e "${YELLOW}   Cilium impose une montée de version mineure à la fois. Passez par les versions intermédiaires.${NC}"
        exit 1
    fi

    if [ "$HELM_DRY_RUN" = "true" ]; then
        echo -e "${YELLOW}  - Mode validation : preflight-check (mutant) ignoré${NC}"
    else
        echo -e "${YELLOW}  - Exécution du preflight-check Cilium (${CURRENT_VERSION} → ${CILIUM_VERSION})...${NC}"
        helm upgrade --install cilium-preflight cilium/cilium --version "${CILIUM_VERSION}" \
            --namespace "${CILIUM_HELM_NAMESPACE}" \
            --create-namespace \
            --set namespaceOverride="${CILIUM_NAMESPACE}" \
            --set preflight.enabled=true \
            --set agent=false \
            --set operator.enabled=false \
            --wait --timeout 3m

        kubectl rollout status daemonset/cilium-pre-flight-check -n "${CILIUM_NAMESPACE}" --timeout=180s || {
            echo -e "${RED}❌ Preflight-check Cilium en échec — upgrade annulé${NC}"
            helm delete cilium-preflight -n "${CILIUM_HELM_NAMESPACE}" 2>/dev/null || true
            exit 1
        }
        helm delete cilium-preflight -n "${CILIUM_HELM_NAMESPACE}"
        echo -e "${GREEN}  ✓ Preflight-check Cilium OK${NC}"
    fi
fi

# ─── operator.replicas=1 : le chart Cilium fixe 2 réplicas par défaut, mais
# le cluster KinD n'a qu'un seul nœud control-plane — la 2e réplique ne peut
# jamais se scheduler (conflit de port), donc `--wait` attend une
# disponibilité 2/2 qui n'arrivera jamais et finit par expirer (vérifié lors
# de la première exécution réelle : timeout 5 min, rollback --atomic propre).
#
# ─── operator.affinity=null : même classe de problème rencontrée sur le
# gateway Loki (cf. install-or-upgrade-loki.sh) — le chart pose par défaut un
# podAntiAffinity requiredDuringScheduling sur cilium-operator ("In HA mode,
# cilium-operator pods must not be scheduled on the same node"), incompatible
# avec un cluster à un seul nœud : le pod surnuméraire du rolling update
# (maxSurge) ne pourrait jamais se scheduler à côté de l'ancien. Neutralisé
# préventivement avant qu'un bump de version Cilium ne déclenche le rollout.
# ─── Upgrade/installation réelle (ou validation dry-run=server) ───
if [ "$HELM_DRY_RUN" = "true" ]; then
    HELM_MODE_ARGS="--dry-run=server"
else
    HELM_MODE_ARGS="--atomic --wait --timeout 5m"
fi

helm upgrade --install cilium cilium/cilium --version "${CILIUM_VERSION}" \
    --namespace "${CILIUM_HELM_NAMESPACE}" \
    --create-namespace \
    --set namespaceOverride="${CILIUM_NAMESPACE}" \
    --set kubeProxyReplacement=true \
    --set k8sServiceHost="${CILIUM_K8S_API_SERVER}" \
    --set k8sServicePort="${CILIUM_K8S_API_PORT}" \
    --set hubble.enabled=false \
    --set ipam.mode=kubernetes \
    --set operator.replicas=1 \
    --set operator.affinity=null \
    ${HELM_MODE_ARGS}

if [ "$HELM_DRY_RUN" = "true" ]; then
    echo -e "${GREEN}✅ Validation dry-run Cilium ${CILIUM_VERSION} OK (aucune mutation du cluster)${NC}"
else
    kubectl rollout status daemonset/cilium -n "${CILIUM_NAMESPACE}" --timeout=300s
    echo -e "${GREEN}✅ Cilium ${CILIUM_VERSION} opérationnel${NC}"
fi
