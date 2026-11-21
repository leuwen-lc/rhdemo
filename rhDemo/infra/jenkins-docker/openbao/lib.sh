#!/bin/bash
# Fonctions partagées par les scripts OpenBao (sourcé, jamais exécuté seul).
# Utilisé aussi par infra/stagingkub/scripts (raccordement au réseau kind, NetworkPolicy d'ESO).

OPENBAO_CONTAINER="${OPENBAO_CONTAINER:-rhdemo-openbao}"
OPENBAO_KIND_NETWORK="${OPENBAO_KIND_NETWORK:-kind}"
# Décalage de l'IP fixe d'OpenBao dans le sous-réseau IPv4 du réseau kind : loin des
# adresses attribuées dans l'ordre par Docker (.2, .3…). Doit rester stable : il figure
# dans le SAN du certificat et dans la NetworkPolicy de sortie d'ESO.
OPENBAO_KIND_IP_OFFSET="${OPENBAO_KIND_IP_OFFSET:-250}"

# IP fixe d'OpenBao sur le réseau kind (ex. 172.18.0.250), calculée depuis le sous-réseau.
openbao_kind_ip() {
    local subnet
    subnet="$(docker network inspect "${OPENBAO_KIND_NETWORK}" \
        --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null | tr ' ' '\n' | grep -m1 '\.')" || return 1
    [ -n "${subnet}" ] || return 1
    python3 -I -c 'import ipaddress,sys; n=ipaddress.ip_network(sys.argv[1]); print(n.network_address + int(sys.argv[2]))' \
        "${subnet}" "${OPENBAO_KIND_IP_OFFSET}"
}

# Raccorde OpenBao au réseau kind avec son IP fixe (non persistant : à refaire après
# recréation du cluster ou du conteneur, comme kind-registry). Idempotent.
openbao_connect_kind() {
    local ip current
    docker inspect "${OPENBAO_CONTAINER}" >/dev/null 2>&1 || { echo "OpenBao (${OPENBAO_CONTAINER}) absent"; return 1; }
    ip="$(openbao_kind_ip)" || { echo "réseau ${OPENBAO_KIND_NETWORK} absent"; return 1; }
    current="$(docker inspect "${OPENBAO_CONTAINER}" \
        --format "{{with index .NetworkSettings.Networks \"${OPENBAO_KIND_NETWORK}\"}}{{.IPAddress}}{{end}}")"
    if [ "${current}" = "${ip}" ]; then
        return 0
    fi
    [ -n "${current}" ] && docker network disconnect "${OPENBAO_KIND_NETWORK}" "${OPENBAO_CONTAINER}"
    docker network connect --ip "${ip}" --alias openbao "${OPENBAO_KIND_NETWORK}" "${OPENBAO_CONTAINER}"
}

# État de scellement sans jeton (sys/seal-status est public) : sealed | unsealed | uninitialized | down
# BAO_ADDR et BAO_CACERT sont définis dans le conteneur (docker-compose.yml).
openbao_seal_state() {
    local out
    out="$(docker exec "${OPENBAO_CONTAINER}" bao status -format=json 2>/dev/null)"
    case "${out}" in
        *'"initialized": false'*) echo uninitialized ;;
        *'"sealed": true'*) echo sealed ;;
        *'"sealed": false'*) echo unsealed ;;
        *) echo down ;;
    esac
}

# Session administrateur pour les scripts du poste (init-keycloak-stagingkub.sh…) :
# mot de passe de l'utilisateur admin saisi en masqué, jeton exporté dans BAO_TOKEN.
# À révoquer en fin de script : openbao_admin_logout.
openbao_admin_login() {
    local pw
    [ -n "${BAO_TOKEN:-}" ] && return 0
    read -r -s -p "Mot de passe OpenBao de admin : " pw; echo
    BAO_TOKEN="$(printf '%s' "${pw}" | docker exec -i "${OPENBAO_CONTAINER}" \
        bao write -field=token auth/userpass/login/admin password=-)" || return 1
    export BAO_TOKEN
}

openbao_admin_logout() {
    [ -n "${BAO_TOKEN:-}" ] && docker exec -e BAO_TOKEN "${OPENBAO_CONTAINER}" bao token revoke -self >/dev/null 2>&1
    unset BAO_TOKEN
}

# Valeur d'un champ KV v2 (montage kv/) sur la sortie standard.
openbao_kv_get() {   # openbao_kv_get <chemin> <champ>
    docker exec -e BAO_TOKEN "${OPENBAO_CONTAINER}" bao kv get -mount=kv -field="$2" "$1" </dev/null
}
