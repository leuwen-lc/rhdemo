#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Initialisation et configuration d'OpenBao (docs/OPENBAO.md)
# ═══════════════════════════════════════════════════════════════════
#
# Usage :
#   ./configure-openbao.sh init            initialise (une seule fois) : affiche la clé de
#                                          déverrouillage et le jeton root, À COPIER DANS
#                                          KEEPASSXC ; rien n'est écrit sur le disque
#   ./configure-openbao.sh base            étape 1 : KV v2, AppRole jenkins,
#                                          utilisateur admin, politiques (jeton root demandé)
#   ./configure-openbao.sh cosign          étape 2 : moteur Transit et clé Cosign non
#                                          exportable, AppRole jenkins-cosign
#   ./configure-openbao.sh kubernetes      étape 3 : authentification Kubernetes pour ESO
#                                          (rhdemo-stagingkub et loki-stack)
#   ./configure-openbao.sh secret-id ROLE  émet un secret_id pour l'AppRole ROLE et affiche
#                                          role_id + secret_id une seule fois
#   ./configure-openbao.sh revoke-root     révoque le jeton root saisi (fin d'installation)
#   ./configure-openbao.sh generate-root   recrée un jeton root à partir de la clé de
#                                          déverrouillage (opération ponctuelle, à révoquer)
#
# Idempotent sauf « init ». Le jeton (root, ou admin pour secret-id/cosign/kubernetes)
# est demandé en saisie masquée et passé au conteneur par variable d'environnement,
# jamais en argument.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"
POLICIES_DIR="${SCRIPT_DIR}/policies"

# Durées (ETUDE_OPENBAO.md §7.1, §8) : jetons courts ; secret_id renouvelé par
# rotate-secrets.py (inventaire : openbao-approle-*), d'où une validité bornée.
TOKEN_TTL="15m"
SECRET_ID_TTL="2400h"   # 100 jours : période de rotation C (90 j, inventaire) + marge

bao() {      # sans entrée standard (ne consomme pas les saisies suivantes)
    docker exec -e BAO_TOKEN "${OPENBAO_CONTAINER}" bao "$@" </dev/null
}
bao_in() {   # avec entrée standard (politique, valeur passée par « champ=- »)
    docker exec -i -e BAO_TOKEN "${OPENBAO_CONTAINER}" bao "$@"
}

ask_token() {
    # Jeton fourni par BAO_TOKEN, saisi, ou obtenu par le mot de passe de l'utilisateur
    # admin (saisie vide) ; « base » exige le jeton root (l'utilisateur admin n'existe pas encore).
    local label="${1:-Jeton root ou admin}" pw
    if [ -z "${BAO_TOKEN:-}" ]; then
        read -r -s -p "${label} (vide = mot de passe de l'utilisateur admin) : " BAO_TOKEN; echo
        if [ -z "${BAO_TOKEN}" ]; then
            read -r -s -p "Mot de passe OpenBao de admin : " pw; echo
            BAO_TOKEN="$(printf '%s' "${pw}" | bao_in write -field=token auth/userpass/login/admin password=-)" \
                || { echo "❌ Connexion admin refusée"; exit 1; }
            unset pw
        fi
    fi
    export BAO_TOKEN
    bao token lookup >/dev/null || { echo "❌ Jeton refusé"; exit 1; }
}

require_unsealed() {
    local state
    state="$(openbao_seal_state)"
    if [ "${state}" != "unsealed" ]; then
        echo "❌ OpenBao est « ${state} » : démarrer le conteneur et le déverrouiller (unseal.sh)."
        exit 1
    fi
}

enabled() {   # enabled auth|secrets <chemin/>
    local kind="$1" path="$2"
    bao "${kind}" list -format=json | grep -q "\"${path}\""
}

write_policy() {
    bao_in policy write "$1" - < "${POLICIES_DIR}/$1.hcl"
    echo "  ✓ politique $1"
}

approle_role() {   # approle_role <rôle> <politique>
    bao write "auth/approle/role/$1" \
        token_policies="$2" token_ttl="${TOKEN_TTL}" token_max_ttl="${TOKEN_TTL}" \
        secret_id_ttl="${SECRET_ID_TTL}" secret_id_num_uses=0 token_type=service >/dev/null
    echo "  ✓ AppRole $1 (jeton ${TOKEN_TTL}, secret_id ${SECRET_ID_TTL})"
}

cmd_init() {
    local state
    state="$(openbao_seal_state)"
    if [ "${state}" != "uninitialized" ]; then
        echo "❌ OpenBao est « ${state} » : déjà initialisé ou arrêté."
        exit 1
    fi
    cat <<'EOF'
▶ Initialisation : une part de clé, seuil 1 (ETUDE_OPENBAO.md §5).
  La clé de déverrouillage (« Unseal Key 1 ») et le jeton root vont s'afficher UNE SEULE
  FOIS. Les copier dans KeePassXC (et la clé sur papier) avant de fermer ce terminal :
  leur perte rend les données irrécupérables.
EOF
    read -r -p "Prêt ? [o/N] " r
    [[ "${r}" =~ ^[oO]$ ]] || exit 1
    docker exec "${OPENBAO_CONTAINER}" bao operator init -key-shares=1 -key-threshold=1
    echo ""
    echo "Ensuite : ./unseal.sh, puis ./configure-openbao.sh base (avec le jeton root)."
}

cmd_base() {
    require_unsealed
    ask_token "Jeton root"
    echo "▶ Moteurs et méthodes d'authentification"
    enabled secrets kv/ || bao secrets enable -path=kv -version=2 kv
    enabled auth approle/ || bao auth enable approle
    enabled auth userpass/ || bao auth enable userpass
    echo "  ✓ kv/ (KV v2), approle/, userpass/"
    bao audit list | grep -q "^fichier/" && echo "  ✓ audit fichier actif (config.hcl)"

    echo "▶ Politiques"
    for p in admin jenkins jenkins-cosign eso-stagingkub; do
        write_policy "${p}"
    done

    echo "▶ AppRole"
    approle_role jenkins jenkins

    echo "▶ Utilisateur admin (remplace le jeton root, jeton d'une heure)"
    if bao read auth/userpass/users/admin >/dev/null 2>&1; then
        echo "  ✓ déjà présent (changer le mot de passe : bao write auth/userpass/users/admin/password)"
    else
        local pw pw2
        read -r -s -p "Mot de passe de l'utilisateur admin (à ranger dans KeePassXC) : " pw; echo
        read -r -s -p "Confirmation : " pw2; echo
        [ -n "${pw}" ] && [ "${pw}" = "${pw2}" ] || { echo "❌ Mots de passe vides ou différents"; exit 1; }
        printf '%s' "${pw}" | bao_in write auth/userpass/users/admin password=- \
            token_policies=admin token_ttl=1h token_max_ttl=4h >/dev/null
        echo "  ✓ utilisateur admin créé"
    fi
    cat <<EOF

✅ Configuration de base terminée.
   - secret_id du contrôleur Jenkins : ./configure-openbao.sh secret-id jenkins
   - alimentation des secrets       : rhDemo/scripts/openbao-setup.py (docs/OPENBAO.md)
   - en fin d'installation          : ./configure-openbao.sh revoke-root
EOF
}

cmd_cosign() {
    require_unsealed
    ask_token "Jeton root ou admin"
    echo "▶ Transit Cosign (ETUDE_OPENBAO.md §7.1)"
    enabled secrets cosign-transit/ || bao secrets enable -path=cosign-transit transit
    if bao read cosign-transit/keys/cosign >/dev/null 2>&1; then
        echo "  ✓ clé cosign déjà présente"
    else
        bao write -f cosign-transit/keys/cosign type=ecdsa-p256 exportable=false >/dev/null
        echo "  ✓ clé cosign créée (ecdsa-p256, non exportable)"
    fi
    write_policy jenkins-cosign
    bao write auth/approle/role/jenkins-cosign \
        token_policies=jenkins-cosign token_ttl=10m token_max_ttl=10m \
        secret_id_ttl="${SECRET_ID_TTL}" token_type=service >/dev/null
    echo "  ✓ AppRole jenkins-cosign (jeton 10 min)"
    echo ""
    # Clé publique de la dernière version de la clé Transit, écrite dans un fichier pour le
    # credential Jenkins « Secret file » cosign-public-key-transit (un « Secret text » tient
    # sur une ligne et casserait le PEM). Pas un secret ; certs/ est ignoré par Git.
    local pub_dir="${CERTS_DIR:-${SCRIPT_DIR}/../certs}/cosign" pub_file
    pub_file="${pub_dir}/cosign-transit.pub"
    mkdir -p "${pub_dir}"
    bao read -field=keys -format=json cosign-transit/keys/cosign \
        | python3 -I -c 'import json,sys; k=json.load(sys.stdin); print(k[str(max(map(int,k)))]["public_key"].strip())' \
        > "${pub_file}.new"
    openssl pkey -pubin -in "${pub_file}.new" -noout 2>/dev/null \
        || { rm -f "${pub_file}.new"; echo "❌ Clé publique illisible"; exit 1; }
    mv "${pub_file}.new" "${pub_file}"
    chmod 644 "${pub_file}"
    echo "  ✓ clé publique écrite dans $(cd "${pub_dir}" && pwd)/cosign-transit.pub"
    echo ""
    echo "Ensuite :"
    echo "  1. Jenkins : credential « Secret file » cosign-public-key-transit avec ce fichier"
    echo "     (après une rotation de la clé Transit, relancer cette commande et remplacer le fichier) ;"
    echo "  2. rhDemo/scripts/openbao-setup.py cosign-approle (credential openbao-cosign-approle)."
}

cmd_kubernetes() {
    require_unsealed
    ask_token "Jeton root ou admin"
    local cluster="${KIND_CLUSTER:-rhdemo}" ca
    echo "▶ Authentification Kubernetes (ESO de stagingkub, ETUDE_OPENBAO.md §7.2 étape 3)"
    openbao_connect_kind || { echo "❌ Raccordement au réseau kind impossible"; exit 1; }
    ca="$(kubectl config view --raw -o jsonpath="{.clusters[?(@.name==\"kind-${cluster}\")].cluster.certificate-authority-data}" | base64 -d)"
    [ -n "${ca}" ] || { echo "❌ Autorité du cluster kind-${cluster} introuvable dans le kubeconfig"; exit 1; }
    enabled auth kubernetes/ || bao auth enable kubernetes
    # Pas de token_reviewer_jwt : OpenBao relit le JWT présenté par ESO, dont le compte
    # porte system:auth-delegator (aucun jeton permanent stocké dans OpenBao).
    printf '%s' "${ca}" | bao_in write auth/kubernetes/config \
        kubernetes_host="https://${cluster}-control-plane:6443" \
        kubernetes_ca_cert=- disable_local_ca_jwt=true >/dev/null
    write_policy eso-stagingkub
    bao write auth/kubernetes/role/eso-stagingkub \
        bound_service_account_names=eso-openbao \
        bound_service_account_namespaces=rhdemo-stagingkub \
        token_policies=eso-stagingkub token_ttl="${TOKEN_TTL}" token_max_ttl="${TOKEN_TTL}" >/dev/null
    write_policy eso-observability
    bao write auth/kubernetes/role/eso-observability \
        bound_service_account_names=eso-openbao \
        bound_service_account_namespaces=loki-stack \
        token_policies=eso-observability token_ttl="${TOKEN_TTL}" token_max_ttl="${TOKEN_TTL}" >/dev/null
    echo "  ✓ kubernetes/ configuré, rôles eso-stagingkub (compte eso-openbao de rhdemo-stagingkub)"
    echo "    et eso-observability (compte eso-openbao de loki-stack)"
}

cmd_secret_id() {
    local role="${1:?rôle AppRole attendu (jenkins, jenkins-cosign)}"
    require_unsealed
    ask_token "Jeton root ou admin"
    local role_id secret_id
    role_id="$(bao read -field=role_id "auth/approle/role/${role}/role-id")"
    secret_id="$(bao write -f -field=secret_id "auth/approle/role/${role}/secret-id")"
    echo "role_id   : ${role_id}"
    echo "secret_id : ${secret_id}"
    echo "(affichés une seule fois ; les anciens secret_id restent valides jusqu'à expiration"
    echo " ou révocation : bao write auth/approle/role/${role}/secret-id-accessor/destroy …)"
}

cmd_revoke_root() {
    require_unsealed
    ask_token "Jeton root à révoquer"
    bao token lookup -format=json | grep -q '"root"' || { echo "❌ Ce n'est pas un jeton root"; exit 1; }
    bao token revoke -self
    echo "✅ Jeton root révoqué. Le régénérer au besoin : ./configure-openbao.sh generate-root (clé de déverrouillage)."
}

cmd_generate_root() {
    # bao operator generate-root sans jeton : la clé de déverrouillage suffit (une seule part).
    # L'OTP n'apparaît ni à l'écran ni en argument (-otp visible dans ps) : le jeton encodé
    # est déchiffré ici, par XOR avec l'OTP (même calcul que « generate-root -decode »).
    local status init nonce otp key enc token
    require_unsealed
    status="$(docker exec "${OPENBAO_CONTAINER}" bao operator generate-root -status -format=json </dev/null)"
    if printf '%s' "${status}" | grep -q '"started": *true'; then
        echo "⚠ Une génération de jeton root était en cours : annulée."
        docker exec "${OPENBAO_CONTAINER}" bao operator generate-root -cancel </dev/null >/dev/null
    fi
    init="$(docker exec "${OPENBAO_CONTAINER}" bao operator generate-root -init -format=json </dev/null)"
    nonce="$(printf '%s' "${init}" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["nonce"])')"
    otp="$(printf '%s' "${init}" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["otp"])')"
    unset init
    read -r -s -p "Clé de déverrouillage (Unseal Key 1, KeePassXC) : " key; echo
    if ! enc="$(printf '%s' "${key}" | docker exec -i "${OPENBAO_CONTAINER}" \
            bao operator generate-root -format=json -nonce="${nonce}" - \
            | python3 -I -c 'import json,sys; d=json.load(sys.stdin); print(d.get("encoded_token") or d.get("encoded_root_token") or "")' 2>/dev/null)" \
            || [ -z "${enc}" ]; then
        unset key otp
        docker exec "${OPENBAO_CONTAINER}" bao operator generate-root -cancel </dev/null >/dev/null 2>&1 || true
        echo "❌ Clé refusée : génération annulée"; exit 1
    fi
    unset key
    token="$(ENC="${enc}" OTP="${otp}" python3 -I -c '
import base64, os
enc, otp = os.environ["ENC"], os.environ["OTP"].encode()
raw = base64.b64decode(enc + "=" * (-len(enc) % 4))
if len(raw) != len(otp):
    raise SystemExit("longueur inattendue")
print(bytes(a ^ b for a, b in zip(raw, otp)).decode())')"
    unset enc otp
    BAO_TOKEN="${token}" bao token lookup -format=json | grep -q '"root"' \
        || { echo "❌ Jeton obtenu invalide"; exit 1; }
    echo
    echo "Jeton root (affiché une seule fois, ne pas le stocker) :"
    echo "  ${token}"
    echo
    echo "Après l'opération : ./configure-openbao.sh revoke-root"
}

case "${1:-}" in
    init) cmd_init ;;
    base) cmd_base ;;
    cosign) cmd_cosign ;;
    kubernetes) cmd_kubernetes ;;
    secret-id) shift; cmd_secret_id "$@" ;;
    revoke-root) cmd_revoke_root ;;
    generate-root) cmd_generate_root ;;
    *) sed -n '2,25p' "$0"; exit 2 ;;
esac
