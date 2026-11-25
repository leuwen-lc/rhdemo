#!/usr/bin/env bash
#
# Lance tous les tests des scripts (hors réseau : faux Jenkins HTTP local, dépôts git locaux).
# Le poller fixcve-auto y est exécuté de bout en bout (test_poller.py). Lancé aussi par le job
# RHDemo-Scripts (Jenkinsfile-Scripts), avec mesure de couverture.
# Usage : rhDemo/scripts/tests/run-all.sh [-v]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
python3 -I -m unittest discover -s . -p 'test_*.py' -t . "$@"
