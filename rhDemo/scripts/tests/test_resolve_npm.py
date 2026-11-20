"""Recherche de correctif npm (fixcve_lib/resolve.py) : npm audit + repli sur l'avis OSV.

Chaque cas rejoue un trou réel ou potentiel de la règle « npm audit fait foi » ; le premier est
le build #914 (brace-expansion : fixAvailable vrai, dry-run muet -> lookup_failed à tort).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

from helpers import SCRIPTS, OsvDir, audit, context, finding, osv_doc
from fixcve_lib.registry import Registry
from fixcve_lib.resolve import harmonize_targets, resolve_finding


def resolve_all(findings, osv, **kw):
    ctx = context(osv, **kw)
    return {(e["finding_id"], e["package_name"]): e for e in harmonize_targets([resolve_finding(f, ctx) for f in findings])}


class ResolveNpmTest(unittest.TestCase):
    def test_build_914_fix_available_but_dry_run_silent(self):
        """fixAvailable vrai + dry-run vide : version tirée de l'avis ; deux GHSA -> la plus haute."""
        fs = [finding("GHSA-6j4f-fj2g-mc7p", "brace-expansion", "1.1.18"),
              finding("GHSA-qhr7-859c-m2p7", "brace-expansion", "1.1.18")]
        osv = OsvDir({"GHSA-6j4f-fj2g-mc7p": osv_doc("brace-expansion", ("0", "1.1.19"), ("2.0.0", "2.1.5")),
                      "GHSA-qhr7-859c-m2p7": osv_doc("brace-expansion", ("0", "1.1.20"), ("3.0.0", "3.0.8"))})
        out = resolve_all(fs, osv, audit_doc=audit(**{"brace-expansion": True}),
                          registry={"npm:brace-expansion": ["1.1.19", "1.1.20", "2.1.5"]})
        for e in out.values():
            self.assertEqual((e["fix_status"], e["target_version"], e["proof"]), ("fix_available", "1.1.20", "advisory"))

    def test_package_absent_from_npm_audit(self):
        osv = OsvDir({"GHSA-aaaa-bbbb-cccc": osv_doc("node-forge", ("0", "1.4.1"))})
        out = resolve_all([finding("GHSA-aaaa-bbbb-cccc", "node-forge", "1.4.0")], osv,
                          audit_doc=audit(), registry={"npm:node-forge": ["1.4.1"]})
        self.assertEqual(out[("GHSA-aaaa-bbbb-cccc", "node-forge")]["target_version"], "1.4.1")

    def test_fix_blocked_by_parent_but_version_exists_in_branch(self):
        osv = OsvDir({"GHSA-aaaa-bbbb-cccc": osv_doc("pkg", ("2.0.0", "2.3.5"))})
        out = resolve_all([finding("GHSA-aaaa-bbbb-cccc", "pkg", "2.3.0")], osv,
                          audit_doc=audit(pkg={"name": "parent", "version": "9.0.0", "isSemVerMajor": True}),
                          registry={"npm:pkg": ["2.3.5"]})
        e = out[("GHSA-aaaa-bbbb-cccc", "pkg")]
        self.assertEqual((e["fix_status"], e["target_version"]), ("fix_available", "2.3.5"))

    def test_major_bump_never_proposed(self):
        osv = OsvDir({"GHSA-aaaa-bbbb-cccc": osv_doc("pkg", ("0", "5.0.0"))})
        out = resolve_all([finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], osv,
                          audit_doc=audit(pkg=False), registry={"npm:pkg": ["5.0.0"]})
        self.assertEqual(out[("GHSA-aaaa-bbbb-cccc", "pkg")]["fix_status"], "no_fix_available")

    def test_version_missing_from_registry_keeps_audit_status(self):
        osv = OsvDir({"GHSA-aaaa-bbbb-cccc": osv_doc("pkg", ("0", "1.2.9"))})
        out = resolve_all([finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], osv,
                          audit_doc=audit(pkg=False), registry={"npm:pkg": ["1.2.1"]})
        self.assertEqual(out[("GHSA-aaaa-bbbb-cccc", "pkg")]["fix_status"], "no_fix_available")

    def test_audit_unusable_and_advisory_unreachable_is_lookup_failed(self):
        osv = OsvDir(errors=["GHSA-aaaa-bbbb-cccc"])
        out = resolve_all([finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], osv, audit_doc={"error": {}})
        self.assertEqual(out[("GHSA-aaaa-bbbb-cccc", "pkg")]["fix_status"], "lookup_failed")

    def test_audit_unusable_but_advisory_answers_is_not_transitory(self):
        osv = OsvDir({"GHSA-aaaa-bbbb-cccc": osv_doc("pkg", ("0", "3.0.0"))})
        out = resolve_all([finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], osv, audit_doc={"error": {}})
        self.assertEqual(out[("GHSA-aaaa-bbbb-cccc", "pkg")]["fix_status"], "no_fix_available")

    def test_audit_vide_et_avis_injoignable_jamais_sans_correctif(self):
        """npm audit hors ligne renvoie `vulnerabilities: {}` sans erreur : avec OSV injoignable,
        c'est une panne (transitoire), jamais « aucun correctif » (qui mènerait à une suppression)."""
        osv = OsvDir(errors=["GHSA-aaaa-bbbb-cccc"])
        out = resolve_all([finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], osv, audit_doc=audit())
        self.assertEqual(out[("GHSA-aaaa-bbbb-cccc", "pkg")]["fix_status"], "lookup_failed")

    def test_npm_audit_version_wins_even_if_advisory_unreachable(self):
        osv = OsvDir(errors=["GHSA-aaaa-bbbb-cccc"])
        out = resolve_all([finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], osv,
                          audit_doc=audit(pkg={"name": "pkg", "version": "1.2.4", "isSemVerMajor": False}))
        e = out[("GHSA-aaaa-bbbb-cccc", "pkg")]
        self.assertEqual((e["fix_status"], e["target_version"], e["proof"]), ("fix_available", "1.2.4", "npm_audit"))

    def test_secondary_id_finds_advisory_but_is_not_an_alias(self):
        """Un GHSA relevé dans les références (advisory_aliases) aide à trouver l'avis mais n'est
        jamais repris comme alias s'il désigne une autre faille (webpack-dev-middleware, #914)."""
        osv = OsvDir({"GHSA-g84c-rxfj-3j2c": osv_doc("wdm", ("0", "6.0.0"), aliases=["CVE-2026-76844"]),
                      "GHSA-wr3j-pwj9-hqq6": osv_doc("wdm", ("0", "5.3.4"), aliases=["CVE-2024-29180"])})
        f = finding("GHSA-g84c-rxfj-3j2c", "wdm", "5.3.4", advisory_aliases=["GHSA-wr3j-pwj9-hqq6"])
        out = resolve_all([f], osv, audit_doc=audit(wdm=False))
        self.assertEqual(out[("GHSA-g84c-rxfj-3j2c", "wdm")]["aliases"], ["CVE-2026-76844"])

    def test_dev_only_computed_from_lockfile(self):
        osv = OsvDir()
        lock = {"pkg": [("1.2.0", True), ("1.2.0", True)]}
        out = resolve_all([finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], osv, audit_doc=audit(), lock=lock)
        self.assertIs(out[("GHSA-aaaa-bbbb-cccc", "pkg")]["npm_dev_only"], True)


class RegistryNpmVersionsTest(unittest.TestCase):
    """npm view renvoie une chaîne pour une version unique et une liste sinon (constaté en réel)."""

    def test_string_or_list(self):
        reg = Registry()
        for out, expected in [('"1.1.19"', ["1.1.19"]), ('["1.1.19","1.1.20"]', ["1.1.19", "1.1.20"])]:
            with unittest.mock.patch("fixcve_lib.registry.run", return_value=(0, out, "")):
                self.assertEqual(reg.npm_versions("brace-expansion"), expected)


class ResolveCliTest(unittest.TestCase):
    def test_cli_writes_valid_lookup(self):
        with tempfile.TemporaryDirectory() as d:
            def w(name, doc):
                path = os.path.join(d, name)
                with open(path, "w") as fh:
                    json.dump(doc, fh)
                return path
            osv = os.path.join(d, "osv")
            os.mkdir(osv)
            w("osv/GHSA-aaaa-bbbb-cccc.json", dict(osv_doc("pkg", ("0", "1.2.3")), id="GHSA-aaaa-bbbb-cccc"))
            detected = w("detected.json", {"jenkins_build": 1, "stage": "owasp", "findings": [
                dict(finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0"), source="owasp", fixed_version_hint=None,
                     fixed_versions=[], title="t")]})
            lookup = os.path.join(d, "lookup.json")
            cmd = [sys.executable, "-I", os.path.join(SCRIPTS, "fixcve-resolve.py"), detected, lookup,
                   "--osv-dir", osv, "--audit-json", w("audit.json", audit(pkg=False)),
                   "--registry-json", w("reg.json", {"npm:pkg": ["1.2.3"]}),
                   "--lock-json", w("lock.json", {}), "--maven-deps-json", w("mvn.json", {}),
                   "--image-refs-json", w("img.json", {}), "--no-pending"]
            out = subprocess.run(cmd, capture_output=True, text=True, cwd=d)
            self.assertIn("FIXCVE_RESOLVE_RESULT: OK 1 fix=1", out.stdout, out.stderr)
            check = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "fixcve-validate-json.py"),
                                    "--schema", "lookup", "--cross-ref", detected, lookup],
                                   capture_output=True, text=True)
            self.assertIn('"ok": true', check.stdout, check.stdout)


if __name__ == "__main__":
    unittest.main()
