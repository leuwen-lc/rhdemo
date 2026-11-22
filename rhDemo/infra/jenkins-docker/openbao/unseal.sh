#!/bin/bash
# Déverrouillage manuel d'OpenBao après un démarrage du poste, du démon Docker ou du
# conteneur (docs/OPENBAO.md, ETUDE_OPENBAO.md §5) : la clé est collée depuis KeePassXC
# dans la saisie masquée de « bao operator unseal », jamais passée en argument.
# Raccorde ensuite OpenBao au réseau kind avec son IP fixe s'il l'a perdu (conteneur recréé) :
# sans lui, External Secrets ne joint plus OpenBao et la CD refuse de déployer.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

state="$(openbao_seal_state)"
case "${state}" in
    unsealed) echo "✅ OpenBao est déjà déverrouillé." ;;
    sealed)
        echo "▶ Coller la clé de déverrouillage (KeePassXC, entrée OpenBao) :"
        docker exec -it "${OPENBAO_CONTAINER}" bao operator unseal
        [ "$(openbao_seal_state)" = "unsealed" ] && echo "✅ OpenBao déverrouillé." \
            || { echo "❌ Toujours scellé (clé incorrecte ?)"; exit 1; }
        ;;
    uninitialized) echo "❌ OpenBao n'est pas initialisé : ./configure-openbao.sh init"; exit 1 ;;
    *) echo "❌ OpenBao injoignable : cd .. && docker compose up -d openbao"; exit 1 ;;
esac

# --- Réseau kind (stagingkub) : raccordement perdu à chaque recréation du conteneur ---
if docker network inspect "${OPENBAO_KIND_NETWORK}" >/dev/null 2>&1; then
    before="$(docker inspect "${OPENBAO_CONTAINER}" \
        --format "{{with index .NetworkSettings.Networks \"${OPENBAO_KIND_NETWORK}\"}}{{.IPAddress}}{{end}}")"
    if openbao_connect_kind; then
        ip="$(openbao_kind_ip)"
        if [ "${before}" = "${ip}" ]; then
            echo "✅ Réseau ${OPENBAO_KIND_NETWORK} : déjà raccordé (${ip})."
        else
            echo "✅ Réseau ${OPENBAO_KIND_NETWORK} : raccordé (${ip})."
            # Les SecretStore d'ESO restés en erreur ne se revalident qu'avec un délai croissant :
            # on force leur réconciliation (une annotation suffit), sans rien modifier d'autre.
            if command -v kubectl >/dev/null 2>&1 && kubectl config get-contexts kind-rhdemo >/dev/null 2>&1; then
                kubectl --context kind-rhdemo get secretstore -A --no-headers \
                    -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name 2>/dev/null \
                | while read -r ns name; do
                    kubectl --context kind-rhdemo annotate secretstore "${name}" -n "${ns}" \
                        force-sync="$(date +%s)" --overwrite >/dev/null && echo "   ↻ SecretStore ${ns}/${name}"
                done
                # Puis, une fois les SecretStore prêts (30 s au plus), resynchronisation des secrets.
                for _ in $(seq 1 10); do
                    kubectl --context kind-rhdemo get secretstore -A --no-headers \
                        -o custom-columns=R:.status.conditions[0].status 2>/dev/null | grep -qv True || break
                    sleep 3
                done
                kubectl --context kind-rhdemo get externalsecret -A --no-headers \
                    -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name 2>/dev/null \
                | while read -r ns name; do
                    kubectl --context kind-rhdemo annotate externalsecret "${name}" -n "${ns}" \
                        force-sync="$(date +%s)" --overwrite >/dev/null && echo "   ↻ ExternalSecret ${ns}/${name}"
                done
            fi
        fi
    else
        echo "⚠️  Raccordement au réseau ${OPENBAO_KIND_NETWORK} impossible : infra/stagingkub/scripts/repair-cluster-after-restart.sh"
    fi
fi
