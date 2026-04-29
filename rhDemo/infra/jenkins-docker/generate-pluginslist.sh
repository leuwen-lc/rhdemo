#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# GÉNÉRATION DU LOCKFILE plugins.txt DEPUIS L'INSTANCE JENKINS
#
# Usage: ./generate-pluginslist.sh [--dry-run]
#
# Options:
#   --dry-run  Affiche les changements sans modifier plugins.txt
#
# Lit les versions directement depuis les manifestes dans le volume
# Jenkins (/var/jenkins_home/plugins/) via docker compose exec —
# sans passer par l'API HTTP, donc sans problème d'authentification.
# ═══════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DRY_RUN=false
for arg in "$@"; do
    [ "$arg" = "--dry-run" ] && DRY_RUN=true
done

# ────────────────────────────────────────────────────────────────
# Vérification que le conteneur Jenkins tourne
# ────────────────────────────────────────────────────────────────
if ! docker compose ps jenkins 2>/dev/null | grep -q "Up"; then
    echo "❌ Le conteneur Jenkins n'est pas en cours d'exécution."
    echo "   Lancez d'abord : ./start-jenkins.sh"
    exit 1
fi

echo "▶ Lecture des versions depuis /var/jenkins_home/plugins/..."
[ "$DRY_RUN" = true ] && echo "   (mode --dry-run : aucun fichier ne sera modifié)"

# ────────────────────────────────────────────────────────────────
# Lecture des manifestes dans le conteneur
# ────────────────────────────────────────────────────────────────
PLUGIN_VERSIONS=$(docker compose exec -T jenkins bash -c '
    find /var/jenkins_home/plugins -maxdepth 3 -name MANIFEST.MF \
    | while read f; do
        id=$(grep "^Short-Name:" "$f" | tr -d "\r" | sed "s/Short-Name: //")
        ver=$(grep "^Plugin-Version:" "$f" | tr -d "\r" | sed "s/Plugin-Version: //")
        [ -n "$id" ] && [ -n "$ver" ] && echo "$id:$ver"
    done | sort
')

if [ -z "$PLUGIN_VERSIONS" ]; then
    echo "❌ Aucun plugin trouvé. Jenkins a-t-il fini de démarrer ?"
    exit 1
fi

echo "✅ ${#PLUGIN_VERSIONS} plugins lus"

# ────────────────────────────────────────────────────────────────
# Mise à jour de plugins.txt
# ────────────────────────────────────────────────────────────────
python3 - "$DRY_RUN" << PYEOF
import re, sys
from datetime import date

dry_run = sys.argv[1] == "true"

plugin_versions_raw = """$PLUGIN_VERSIONS"""

# version_jenkins[plugin-name] = version lue depuis le manifeste
version_jenkins = {}
for line in plugin_versions_raw.strip().splitlines():
    line = line.strip()
    if ':' in line:
        name, ver = line.split(':', 1)
        version_jenkins[name.strip()] = ver.strip()

with open("plugins.txt") as f:
    content = f.read()

plugins_in_file = set(re.findall(r'^([a-z][a-z0-9._-]+):', content, re.MULTILINE))

updates = []

def replace_version(match):
    name = match.group(1)
    old  = match.group(2)
    new  = version_jenkins.get(name, old)
    if new != old:
        updates.append((name, old, new))
    return f"{name}:{new}"

updated = re.sub(
    r'^([a-z][a-z0-9._-]+):([^\s#\n]+)',
    replace_version,
    content,
    flags=re.MULTILINE
)

today = date.today().strftime("%Y-%m-%d")
updated = re.sub(
    r"(# Versions pinnées depuis l'instance Jenkins le )\d{4}-\d{2}-\d{2}",
    rf"\g<1>{today}",
    updated
)

if updates:
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Versions mises à jour :")
    for name, old, new in sorted(updates):
        print(f"  {name}: {old} → {new}")
else:
    print("\n✅ Toutes les versions sont déjà à jour dans plugins.txt")

missing = sorted(version_jenkins.keys() - plugins_in_file)
if missing:
    print(f"\n⚠️  Plugins présents dans Jenkins mais absents de plugins.txt :")
    print("   (ajoutez-les manuellement dans la section dépendances transitives)")
    for name in missing:
        print(f"  {name}:{version_jenkins[name]}")

if not dry_run:
    with open("plugins.txt", "w") as f:
        f.write(updated)
    if updates:
        print(f"\n✅ plugins.txt mis à jour ({len(updates)} version(s) modifiée(s))")
PYEOF

echo ""
if [ "$DRY_RUN" = false ]; then
    echo "📋 Pensez à committer plugins.txt pour tracer les changements de versions."
fi
