#!/usr/bin/env bash
#
# Lance tous les tests de fixcve-auto (hors réseau, sans Jenkins ni git distant).
# Usage : rhDemo/scripts/tests/run-all.sh [-v]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
python3 -I -m unittest discover -s . -p 'test_*.py' -t . "$@"
bash -n ../fixcve-auto-poll.sh && echo "fixcve-auto-poll.sh : syntaxe bash OK"
