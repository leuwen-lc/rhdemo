#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Autorité locale RHDemo et certificat TLS d'OpenBao
# (docs/OPENBAO.md, ETUDE_OPENBAO.md §4.3)
# ═══════════════════════════════════════════════════════════════════
#
# Usage :
#   ./init-local-ca.sh ca        crée la racine (clé chiffrée par phrase de passe)
#                                et l'intermédiaire ; à faire une seule fois
#   ./init-local-ca.sh openbao   émet ou renouvelle le certificat d'OpenBao (1 an)
#
# Fichiers (certs/, ignoré par Git) :
#   certs/ca/root-ca.crt            racine, à distribuer (clients, navigateurs)
#   certs/ca/root-ca.key            clé racine CHIFFRÉE : à copier dans KeePassXC
#                                   puis à supprimer du poste (hors ligne)
#   certs/ca/intermediate.{crt,key} intermédiaire (passera dans le moteur PKI à l'étape 5)
#   certs/ca/ca-chain.crt           intermédiaire + racine
#   certs/openbao/openbao.{crt,key} certificat d'OpenBao (chaîne complète dans .crt)
#
# Le certificat d'OpenBao n'est jamais émis par OpenBao : il doit rester valide
# même quand OpenBao est scellé (§4.3).
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${CERTS_DIR:-${SCRIPT_DIR}/../certs}"
CA_DIR="${CERTS_DIR}/ca"
BAO_DIR="${CERTS_DIR}/openbao"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

umask 077

# Name Constraints (RFC 5280 §4.2.1.10), sur la racine ET l'intermédiaire : l'autorité ne peut
# signer que des noms internes. Un certificat émis pour un autre nom (codeberg.org…) avec une
# clé volée est refusé par les clients (Java, Go, OpenSSL, navigateurs), même si la racine est
# dans leur magasin de confiance. Une contrainte DNS couvre le nom et ses sous-domaines.
# Les ajouter ici AVANT de créer l'autorité : impossible de contraindre une racine existante.
NAME_CONSTRAINTS="nameConstraints=critical,\
permitted;DNS:openbao,permitted;DNS:localhost,permitted;DNS:kind-registry,\
permitted;DNS:intra.leuwen-lc.fr,\
permitted;IP:127.0.0.0/255.0.0.0,permitted;IP:172.16.0.0/255.240.0.0"

# Tests automatisés uniquement : phrase de passe lue dans un fichier au lieu du terminal.
PASSOUT=(); PASSIN=()
if [ -n "${CA_PASSFILE:-}" ]; then
    PASSOUT=(-passout "file:${CA_PASSFILE}"); PASSIN=(-passin "file:${CA_PASSFILE}")
fi

cmd_ca() {
    mkdir -p "${CA_DIR}"
    if [ -f "${CA_DIR}/root-ca.crt" ]; then
        echo "❌ Racine déjà présente (${CA_DIR}/root-ca.crt) : rien n'est écrasé."
        exit 1
    fi
    echo "▶ Racine RHDemo (10 ans, ECDSA P-384). Choisir une phrase de passe forte :"
    echo "  elle protège la clé racine, à ranger dans KeePassXC avec la phrase."
    openssl ecparam -name secp384r1 -genkey -noout \
        | openssl ec -aes256 "${PASSOUT[@]}" -out "${CA_DIR}/root-ca.key"
    openssl req -x509 -new -key "${CA_DIR}/root-ca.key" "${PASSIN[@]}" -sha384 -days 3650 \
        -subj "/O=RHDemo/CN=RHDemo Root CA" \
        -addext "basicConstraints=critical,CA:TRUE" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" \
        -addext "${NAME_CONSTRAINTS}" \
        -addext "subjectKeyIdentifier=hash" \
        -out "${CA_DIR}/root-ca.crt"

    echo "▶ Intermédiaire (5 ans, signé par la racine : la phrase est redemandée)"
    openssl ecparam -name prime256v1 -genkey -noout -out "${CA_DIR}/intermediate.key"
    openssl req -new -key "${CA_DIR}/intermediate.key" \
        -subj "/O=RHDemo/CN=RHDemo Intermediate CA" -out "${CA_DIR}/intermediate.csr"
    openssl x509 -req -in "${CA_DIR}/intermediate.csr" \
        -CA "${CA_DIR}/root-ca.crt" -CAkey "${CA_DIR}/root-ca.key" "${PASSIN[@]}" -CAcreateserial \
        -days 1825 -sha384 -out "${CA_DIR}/intermediate.crt" \
        -extfile <(printf '%s\n' \
            "basicConstraints=critical,CA:TRUE,pathlen:0" \
            "keyUsage=critical,keyCertSign,cRLSign" \
            "${NAME_CONSTRAINTS}" \
            "subjectKeyIdentifier=hash" \
            "authorityKeyIdentifier=keyid:always")
    rm -f "${CA_DIR}/intermediate.csr"
    cat "${CA_DIR}/intermediate.crt" "${CA_DIR}/root-ca.crt" > "${CA_DIR}/ca-chain.crt"
    chmod 644 "${CA_DIR}/root-ca.crt" "${CA_DIR}/intermediate.crt" "${CA_DIR}/ca-chain.crt"

    cat <<EOF

✅ Autorité locale créée dans ${CA_DIR}
   À faire maintenant :
   1. copier root-ca.key (chiffrée) et sa phrase de passe dans KeePassXC ;
   2. supprimer la clé du poste : shred -u ${CA_DIR}/root-ca.key
      (elle ne resservira que pour signer un nouvel intermédiaire) ;
   3. émettre le certificat d'OpenBao : $0 openbao
EOF
}

cmd_openbao() {
    [ -f "${CA_DIR}/intermediate.key" ] || { echo "❌ Intermédiaire absent : lancer d'abord $0 ca"; exit 1; }
    mkdir -p "${BAO_DIR}"
    local ip san
    ip="$(openbao_kind_ip 2>/dev/null || true)"
    # Noms : réseau Jenkins (agents, contrôleur), hôte (scripts du poste), réseau kind (ESO).
    san="DNS:openbao,DNS:localhost,IP:127.0.0.1"
    [ -n "${ip}" ] && san="${san},IP:${ip}"
    echo "▶ Certificat OpenBao (1 an), SAN : ${san}"
    [ -n "${ip}" ] || echo "⚠️  Réseau Docker « kind » absent : pas d'IP kind dans le SAN (réémettre après init-stagingkub.sh)."

    openssl ecparam -name prime256v1 -genkey -noout -out "${BAO_DIR}/openbao.key.new"
    openssl req -new -key "${BAO_DIR}/openbao.key.new" -subj "/O=RHDemo/CN=openbao" \
        -out "${BAO_DIR}/openbao.csr"
    openssl x509 -req -in "${BAO_DIR}/openbao.csr" \
        -CA "${CA_DIR}/intermediate.crt" -CAkey "${CA_DIR}/intermediate.key" -CAcreateserial \
        -days 365 -sha256 -out "${BAO_DIR}/openbao.leaf.crt" \
        -extfile <(printf '%s\n' \
            "basicConstraints=critical,CA:FALSE" \
            "keyUsage=critical,digitalSignature" \
            "extendedKeyUsage=serverAuth" \
            "subjectAltName=${san}" \
            "authorityKeyIdentifier=keyid")
    cat "${BAO_DIR}/openbao.leaf.crt" "${CA_DIR}/intermediate.crt" > "${BAO_DIR}/openbao.crt.new"
    rm -f "${BAO_DIR}/openbao.csr" "${BAO_DIR}/openbao.leaf.crt"
    mv "${BAO_DIR}/openbao.key.new" "${BAO_DIR}/openbao.key"
    mv "${BAO_DIR}/openbao.crt.new" "${BAO_DIR}/openbao.crt"
    # Lecture par l'utilisateur du conteneur (uid 100, gid 1000, §7.2) : groupe 1000.
    chmod 750 "${BAO_DIR}"
    chmod 640 "${BAO_DIR}/openbao.key"
    chmod 644 "${BAO_DIR}/openbao.crt"
    if [ "$(id -g)" != "1000" ]; then
        echo "⚠️  Groupe courant ≠ 1000 : rendre la clé lisible par le conteneur :"
        echo "   sudo chgrp -R 1000 ${BAO_DIR}"
    fi
    openssl x509 -in "${BAO_DIR}/openbao.crt" -noout -subject -enddate -ext subjectAltName | sed 's/^/   /'
    echo "✅ Certificat émis. Recharger OpenBao : docker compose restart openbao (puis déverrouiller)."
}

case "${1:-}" in
    ca) cmd_ca ;;
    openbao) cmd_openbao ;;
    *) sed -n '2,25p' "$0"; exit 2 ;;
esac
