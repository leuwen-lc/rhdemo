#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Garde de RHDemo-Renovate avant d'exécuter le script d'une PR d'infra avec le
# credential kubeconfig-stagingkub-infra-upgrader (équivalent administrateur du
# cluster : il met à jour Cilium, et ses règles miroir des charts couvrent les
# Secrets et les StatefulSets de tout le cluster).
#
# Le script et les manifestes de la PR viennent d'une branche non revue : ils ne
# sont exécutés avec ce credential que si le diff par rapport à la base se limite à
# ce que Renovate produit pour une montée de composant :
#   1. dans les install-or-upgrade-*.sh, des lignes VAR="version" (valeur limitée à
#      [A-Za-z0-9._+-], commentaire de fin inchangé), une ligne retirée pour une
#      ligne ajoutée, même variable ;
#   2. pour NGF, le manifeste gateway-api-crds/v<nouvelle NGF_VERSION>/crds.yaml,
#      identique à celui que produit vendor-gateway-api-crds.sh (de la BASE,
#      variable VENDOR_SCRIPT) depuis les sources officielles, et la suppression
#      des manifestes des versions précédentes.
# Tout autre changement : refus, la PR reste ouverte pour une revue humaine (une
# fusion automatique déclencherait RHDemo-Stagingkub-Upgrade-Deploy avec le même
# credential).
#
# Usage : VENDOR_SCRIPT=<vendor-gateway-api-crds.sh de la base> \
#         renovate-infra-gate.sh <base-ref> <head-ref>      (depuis la racine du dépôt)
# Code retour : 0 conforme, 1 non conforme (raisons sur la sortie), 2 erreur.
# Jenkinsfile-Renovate exécute la version de ce script prise sur la branche de base.
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

BASE="${1:?Usage: renovate-infra-gate.sh <base-ref> <head-ref>}"
HEAD="${2:?Usage: renovate-infra-gate.sh <base-ref> <head-ref>}"
VENDOR="${VENDOR_SCRIPT:-}"

COMP_RE='^rhDemo/infra/stagingkub/scripts/components/install-or-upgrade-[a-z0-9-]+\.sh$'
CRD_RE='^rhDemo/infra/stagingkub/gateway-api-crds/v([0-9]+\.[0-9]+\.[0-9]+)/crds\.yaml$'
LINE_RE='^([A-Za-z_][A-Za-z0-9_]*)="([A-Za-z0-9._+-]+)"(([[:space:]]+#.*)?)$'
NGF_FILE='rhDemo/infra/stagingkub/scripts/components/install-or-upgrade-ngf.sh'

refus=()
refuse() { refus+=("$1"); }

# Lignes retirées et ajoutées d'un script de composant : uniquement des affectations
# de version, appariées par nom de variable, commentaire de fin identique.
check_component() {
    local file="$1" line kind name value trail
    declare -A old=() new=()
    while IFS= read -r line; do
        case "$line" in
            '--- '*|'+++ '*) continue ;;
            -*) kind=old; line="${line:1}" ;;
            +*) kind=new; line="${line:1}" ;;
            *) continue ;;
        esac
        if ! [[ "$line" =~ $LINE_RE ]]; then
            refuse "$file : ligne modifiée hors version : ${line:0:120}"
            continue
        fi
        name="${BASH_REMATCH[1]}"; value="${BASH_REMATCH[2]}"; trail="${BASH_REMATCH[3]}"
        if [ "$kind" = old ]; then
            [ -z "${old[$name]+x}" ] || refuse "$file : $name retirée plusieurs fois"
            old[$name]="$trail"
        else
            [ -z "${new[$name]+x}" ] || refuse "$file : $name ajoutée plusieurs fois"
            new[$name]="$trail"
            [ "$file" = "$NGF_FILE" ] && [ "$name" = NGF_VERSION ] && NEW_NGF="$value"
        fi
    done < <(git diff -U0 --no-renames "$BASE...$HEAD" -- "$file")
    for name in "${!old[@]}"; do
        if [ -z "${new[$name]+x}" ]; then
            refuse "$file : $name retirée sans être remplacée"
        elif [ "${old[$name]}" != "${new[$name]}" ]; then
            refuse "$file : commentaire de fin de $name modifié"
        fi
    done
    for name in "${!new[@]}"; do
        [ -n "${old[$name]+x}" ] || refuse "$file : $name ajoutée sans ligne remplacée"
    done
    [ "${#new[@]}" -gt 0 ] || refuse "$file : aucune ligne de version modifiée"
}

# Manifeste de CRD ajouté : retéléchargé par le script de vendoring de la base, comparé
# octet par octet.
check_crd() {
    local file="$1" version="$2" tmp
    if [ -z "$VENDOR" ] || [ ! -f "$VENDOR" ]; then
        refuse "$file : VENDOR_SCRIPT absent, manifeste non vérifiable"
        return
    fi
    tmp="$(mktemp -d)"
    mkdir -p "$tmp/scripts"
    cp "$VENDOR" "$tmp/scripts/vendor-gateway-api-crds.sh"
    if ! bash "$tmp/scripts/vendor-gateway-api-crds.sh" "$version" > "$tmp/vendor.log" 2>&1; then
        refuse "$file : vendoring de référence en échec ($(tail -1 "$tmp/vendor.log"))"
    elif ! git show "$HEAD:$file" | cmp -s - "$tmp/gateway-api-crds/v$version/crds.yaml"; then
        refuse "$file : différent du manifeste officiel de Gateway API pour NGF $version"
    fi
    rm -rf "$tmp"
}

NEW_NGF=""
crd_added=()
nb=0
while IFS=$'\t' read -r status file; do
    [ -n "$status" ] || continue
    nb=$((nb + 1))
    if [[ "$file" =~ $COMP_RE ]] && [ "$status" = M ]; then
        check_component "$file"
    elif [[ "$file" =~ $CRD_RE ]] && [ "$status" = A ]; then
        crd_added+=("$file|${BASH_REMATCH[1]}")
    elif [[ "$file" =~ $CRD_RE ]] && [ "$status" = D ]; then
        :   # ancienne version supprimée par le vendoring ; contrôlée avec l'ajout ci-dessous
    else
        refuse "$file : fichier hors périmètre ($status)"
    fi
done < <(git diff --no-renames --name-status "$BASE...$HEAD")

[ "$nb" -gt 0 ] || refuse "aucun fichier modifié"
if [ "${#crd_added[@]}" -gt 1 ]; then
    refuse "plusieurs manifestes de CRD ajoutés"
fi
for entry in "${crd_added[@]}"; do
    file="${entry%|*}"; version="${entry#*|}"
    if [ -z "$NEW_NGF" ] || [ "$version" != "$NEW_NGF" ]; then
        refuse "$file : ne correspond pas à la nouvelle NGF_VERSION (${NEW_NGF:-inchangée})"
    else
        check_crd "$file" "$version"
    fi
done
if [ -n "$NEW_NGF" ] && [ "${#crd_added[@]}" -eq 0 ]; then
    refuse "NGF_VERSION modifiée sans manifeste gateway-api-crds/v$NEW_NGF/crds.yaml"
fi
if git diff --no-renames --name-status "$BASE...$HEAD" | grep -qE $'^D\t.*/gateway-api-crds/' \
        && [ "${#crd_added[@]}" -eq 0 ]; then
    refuse "manifeste de CRD supprimé sans remplacement"
fi

if [ "${#refus[@]}" -gt 0 ]; then
    echo "❌ Garde Renovate : diff hors du périmètre autorisé pour le credential d'infra"
    printf '   - %s\n' "${refus[@]}"
    exit 1
fi
echo "✅ Garde Renovate : diff limité aux lignes de version${NEW_NGF:+ et au manifeste officiel des CRD (NGF $NEW_NGF)}"
