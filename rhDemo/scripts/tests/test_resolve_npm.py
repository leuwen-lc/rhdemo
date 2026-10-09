#!/usr/bin/env python3
"""Tests de fixcve-npm-lookup.py — recherche de correctif npm (npm audit + repli sur l'avis OSV).

Déterministe et hors réseau : sorties npm audit, avis OSV et registre sont injectés
(--audit-json, --audit-fix-json, --osv-dir, --registry-json). Chaque cas reproduit un trou réel
ou potentiel de la règle « npm audit fait foi » (voir l'en-tête du script) ; le premier est le
build #914 (brace-expansion : fixAvailable vrai, dry-run muet -> lookup_failed à tort).

Usage : rhDemo/scripts/tests/fixcve-npm-lookup.test.py   (depuis n'importe où)
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixcve-npm-lookup.py")


def osv(name, *ranges):
    """Avis OSV minimal : une entrée `affected` par (introduced, fixed)."""
    return {"affected": [
        {"package": {"name": name, "ecosystem": "npm"},
         "ranges": [{"type": "SEMVER", "events": [{"introduced": i}, {"fixed": f}]}]}
        for (i, f) in ranges]}


def audit(**vulns):
    return {"auditReportVersion": 2, "vulnerabilities": {
        n: {"name": n, "fixAvailable": fa} for n, fa in vulns.items()}}


def finding(fid, pkg, version, aliases=None):
    f = {"finding_id": fid, "package_name": pkg, "installed_version": version, "ecosystem": "npm"}
    if aliases:
        f["advisory_aliases"] = aliases
    return f


class NpmLookupTest(unittest.TestCase):
    def run_lookup(self, findings, audit_doc, fix_doc=None, osv_docs=None, osv_errors=(),
                   registry=None):
        with tempfile.TemporaryDirectory() as d:
            def w(name, doc):
                path = os.path.join(d, name)
                with open(path, "w") as fh:
                    json.dump(doc, fh)
                return path
            osv_dir = os.path.join(d, "osv")
            os.mkdir(osv_dir)
            for vid, doc in (osv_docs or {}).items():
                w(f"osv/{vid}.json", doc)
            for vid in osv_errors:
                open(os.path.join(osv_dir, vid + ".error"), "w").close()
            detected = w("detected.json", {"findings": findings})
            lookup = w("lookup.json", {"findings": [], "pending_reverified": []})
            cmd = [sys.executable, "-I", SCRIPT, detected, lookup,
                   "--audit-json", w("audit.json", audit_doc if audit_doc is not None else {"error": {}}),
                   "--audit-fix-json", w("fix.json", fix_doc or {"change": [], "add": []}),
                   "--osv-dir", osv_dir, "--registry-json", w("reg.json", registry or {})]
            out = subprocess.run(cmd, capture_output=True, text=True, cwd=d)
            self.assertEqual(out.returncode, 0, out.stderr)
            with open(lookup) as fh:
                entries = {(e["finding_id"], e["package_name"]): e for e in json.load(fh)["findings"]}
            return entries, out.stdout.strip().splitlines()[-1]

    def test_build_914_fix_available_but_dry_run_silent(self):
        """fixAvailable vrai + dry-run vide : la version vient de l'avis ; 2 GHSA -> la plus haute."""
        fs = [finding("GHSA-6j4f-fj2g-mc7p", "brace-expansion", "1.1.18"),
              finding("GHSA-qhr7-859c-m2p7", "brace-expansion", "1.1.18")]
        entries, line = self.run_lookup(
            fs, audit(**{"brace-expansion": True}),
            osv_docs={
                "GHSA-6j4f-fj2g-mc7p": osv("brace-expansion", ("0", "1.1.19"), ("2.0.0", "2.1.5")),
                "GHSA-qhr7-859c-m2p7": osv("brace-expansion", ("0", "1.1.20"), ("3.0.0", "3.0.8")),
            },
            registry={"brace-expansion": ["1.1.19", "1.1.20", "2.1.5"]})
        for e in entries.values():
            self.assertEqual((e["fix_status"], e["target_version"]), ("fix_available", "1.1.20"))
        self.assertIn("advisory_fix=2", line)

    def test_package_absent_from_npm_audit(self):
        entries, _ = self.run_lookup(
            [finding("GHSA-aaaa-bbbb-cccc", "node-forge", "1.4.0")], audit(),
            osv_docs={"GHSA-aaaa-bbbb-cccc": osv("node-forge", ("0", "1.4.1"))},
            registry={"node-forge": ["1.4.1"]})
        self.assertEqual(entries[("GHSA-aaaa-bbbb-cccc", "node-forge")]["target_version"], "1.4.1")

    def test_fix_blocked_by_parent_but_version_exists_in_branch(self):
        entries, _ = self.run_lookup(
            [finding("GHSA-aaaa-bbbb-cccc", "pkg", "2.3.0")],
            audit(pkg={"name": "parent", "version": "9.0.0", "isSemVerMajor": True}),
            osv_docs={"GHSA-aaaa-bbbb-cccc": osv("pkg", ("2.0.0", "2.3.5"))},
            registry={"pkg": ["2.3.5"]})
        e = entries[("GHSA-aaaa-bbbb-cccc", "pkg")]
        self.assertEqual((e["fix_status"], e["target_version"]), ("fix_available", "2.3.5"))

    def test_major_bump_never_proposed(self):
        entries, _ = self.run_lookup(
            [finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], audit(pkg=False),
            osv_docs={"GHSA-aaaa-bbbb-cccc": osv("pkg", ("0", "5.0.0"))},
            registry={"pkg": ["5.0.0"]})
        self.assertEqual(entries[("GHSA-aaaa-bbbb-cccc", "pkg")]["fix_status"], "no_fix_available")

    def test_version_missing_from_registry_keeps_audit_status(self):
        entries, _ = self.run_lookup(
            [finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], audit(pkg=False),
            osv_docs={"GHSA-aaaa-bbbb-cccc": osv("pkg", ("0", "1.2.9"))}, registry={"pkg": ["1.2.1"]})
        self.assertEqual(entries[("GHSA-aaaa-bbbb-cccc", "pkg")]["fix_status"], "no_fix_available")

    def test_no_fix_anywhere(self):
        entries, _ = self.run_lookup(
            [finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], audit(pkg=False), osv_docs={})
        self.assertEqual(entries[("GHSA-aaaa-bbbb-cccc", "pkg")]["fix_status"], "no_fix_available")

    def test_audit_unusable_and_advisory_unreachable_is_lookup_failed(self):
        entries, line = self.run_lookup(
            [finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], None,
            osv_errors=["GHSA-aaaa-bbbb-cccc"])
        self.assertEqual(entries[("GHSA-aaaa-bbbb-cccc", "pkg")]["fix_status"], "lookup_failed")
        self.assertIn("advisory_unreachable=1", line)

    def test_audit_unusable_but_advisory_answers_is_not_transitory(self):
        entries, _ = self.run_lookup(
            [finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")], None, osv_docs={})
        self.assertEqual(entries[("GHSA-aaaa-bbbb-cccc", "pkg")]["fix_status"], "no_fix_available")

    def test_npm_audit_version_is_used_without_consulting_advisory(self):
        entries, line = self.run_lookup(
            [finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.2.0")],
            audit(pkg={"name": "pkg", "version": "1.2.4", "isSemVerMajor": False}),
            osv_errors=["GHSA-aaaa-bbbb-cccc"])
        e = entries[("GHSA-aaaa-bbbb-cccc", "pkg")]
        self.assertEqual((e["fix_status"], e["target_version"]), ("fix_available", "1.2.4"))
        self.assertIn("advisory_fix=0 advisory_unreachable=0", line)

    def test_alias_used_when_primary_id_has_no_advisory(self):
        entries, _ = self.run_lookup(
            [finding("CVE-2026-0001", "pkg", "1.2.0", aliases=["GHSA-aaaa-bbbb-cccc"])],
            audit(pkg=False),
            osv_docs={"GHSA-aaaa-bbbb-cccc": osv("pkg", ("0", "1.2.3"))}, registry={"pkg": ["1.2.3"]})
        self.assertEqual(entries[("CVE-2026-0001", "pkg")]["target_version"], "1.2.3")


class VersionExistsTest(unittest.TestCase):
    """npm view renvoie tantôt "1.1.19", tantôt ["1.1.19"] (constaté en réel) : les deux formes
    doivent être acceptées, sinon le repli sur l'avis ne se déclenche jamais."""
    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("npmlookup", SCRIPT)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def check(self, npm_output, expected):
        self.mod.run_npm_json = lambda args: npm_output
        self.assertEqual(self.mod.version_exists("p", "1.1.19"), expected)

    def test_string(self):
        self.check("1.1.19", True)

    def test_list(self):
        self.check(["1.1.19"], True)

    def test_other_version_or_failure(self):
        self.check(["1.1.20"], False)
        self.check(None, False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
