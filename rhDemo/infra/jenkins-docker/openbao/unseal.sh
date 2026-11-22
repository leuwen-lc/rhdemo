#!/bin/bash
# Déverrouillage manuel d'OpenBao après un démarrage du poste, du démon Docker ou du
# conteneur (docs/OPENBAO.md, ETUDE_OPENBAO.md §5) : la clé est collée depuis KeePassXC
# dans la saisie masquée de « bao operator unseal », jamais passée en argument.
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
