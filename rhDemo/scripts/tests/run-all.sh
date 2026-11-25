#!/usr/bin/env bash
#
# Lance tous les tests des scripts (hors réseau : faux Jenkins HTTP local, dépôts git locaux).
# Le poller fixcve-auto y est exécuté de bout en bout (test_poller.py). Lancé aussi par le stage
# « Tests des scripts » de Jenkinsfile-CI.
# Usage : rhDemo/scripts/tests/run-all.sh [-v]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
python3 -I -m unittest discover -s . -p 'test_*.py' -t . "$@"
