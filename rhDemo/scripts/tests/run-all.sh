#!/usr/bin/env bash
#
# Lance tous les tests des scripts (hors réseau, sans Jenkins ni git distant). Les essais du
# poller lui-même se font dans Jenkins (job RHDemo-FixCVE, paramètre DRY_RUN).
# Usage : rhDemo/scripts/tests/run-all.sh [-v]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
python3 -I -m unittest discover -s . -p 'test_*.py' -t . "$@"
for f in ../fixcve-auto-poll.sh ../fixcve-state.sh ../fixcve-git-sync.sh; do bash -n "$f" && echo "$(basename "$f") : syntaxe bash OK"; done
