#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Rotation du journal d'audit d'OpenBao (docs/OPENBAO.md, « Journal d'audit »)
# ═══════════════════════════════════════════════════════════════════
#
# Usage : ./rotate-audit.sh          (lancé chaque semaine par cron, voir docs/OPENBAO.md)
#
# Renomme audit.log en audit-<horodatage UTC>.log, envoie SIGHUP à OpenBao, qui ferme le fichier
# renommé et en rouvre un neuf (aucune ligne perdue, contrairement à une copie suivie d'une
# troncature), puis compresse l'archive et ne garde que les KEEP plus récentes, dans le même
# volume (rhdemo-openbao-audit). Les archives contiennent les mêmes HMAC que le journal : aucun
# secret en clair. Ne demande ni jeton ni déverrouillage.
#
# Variables : KEEP (archives conservées, défaut 12, soit trois mois en hebdomadaire),
#             MIN_BYTES (pas de rotation en dessous, défaut 1 Mo).
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

CONTAINER="rhdemo-openbao"
DIR="/openbao/logs"
KEEP="${KEEP:-12}"
MIN_BYTES="${MIN_BYTES:-1048576}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
ob() { docker exec "${CONTAINER}" sh -c "$1"; }

if [ "$(docker inspect -f '{{.State.Running}}' "${CONTAINER}" 2>/dev/null)" != "true" ]; then
    log "${CONTAINER} arrêté : pas de rotation."
    exit 0
fi

size="$(ob "wc -c < ${DIR}/audit.log" 2>/dev/null || echo 0)"
if [ "${size}" -lt "${MIN_BYTES}" ]; then
    log "audit.log : ${size} octets, sous le seuil (${MIN_BYTES}) : pas de rotation."
    exit 0
fi

archive="audit-$(date -u +%Y%m%dT%H%M%SZ).log"
ob "mv ${DIR}/audit.log ${DIR}/${archive} && pkill -HUP -x bao"

# OpenBao recrée audit.log en traitant le signal. Sans lui, il écrit encore dans l'archive : on ne
# la compresse pas (elle serait tronquée), on la laisse telle quelle et on le signale.
for _ in $(seq 1 10); do
    ob "test -f ${DIR}/audit.log" && break
    sleep 1
done
if ! ob "test -f ${DIR}/audit.log"; then
    log "ALERTE : audit.log non recréé après SIGHUP (OpenBao scellé ou signal ignoré) ; ${archive} laissé non compressé."
    exit 1
fi

ob "gzip ${DIR}/${archive}"
ob "ls -1t ${DIR}/audit-*.log.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f"
log "audit.log archivé dans ${archive}.gz (${size} octets avant compression), ${KEEP} archives au plus."
