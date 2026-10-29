"""Indicateur K (outcomes.py), schéma du plan (fixcve-validate-json.py), détection (fixcve-detect.py)."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

from helpers import SCRIPTS, finding, load_fixture
from fixcve_lib.outcomes import legacy_outcome, stats
from fixcve_lib.policy import build_plan


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(SCRIPTS, name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class OutcomesTest(unittest.TestCase):
    def test_classement_des_anciens_evenements(self):
        self.assertEqual(legacy_outcome({"event": "validation_failed_rollback"}), "bad_fix")
        self.assertEqual(legacy_outcome({"event": "blocked_needs_human", "cvss": 9.1}), "blocked_no_fix_ge9")
        self.assertEqual(legacy_outcome({"event": "blocked_needs_human", "cvss": 8.7,
                                         "justification": "fix_status=lookup_failed"}), "lookup_gap")
        self.assertEqual(legacy_outcome({"event": "blocked_needs_human", "cvss": 7.5}), "policy")
        self.assertIsNone(legacy_outcome({"event": "validation_success"}))

    def test_taux_par_mois(self):
        events = [
            {"timestamp": "2026-10-01T00:00:00Z", "jenkins_build": 1, "event": "remediation_applied", "outcome_code": "fixed"},
            {"timestamp": "2026-10-01T00:00:00Z", "jenkins_build": 2, "event": "findings_blocked", "outcome_code": "blocked_no_fix_ge9"},
            {"timestamp": "2026-10-02T00:00:00Z", "jenkins_build": 3, "event": "cycle_failed", "outcome_code": "tooling"},
            {"timestamp": "2026-10-02T00:00:00Z", "jenkins_build": 4, "event": "skipped_infra_failure"},
            # Cycle à la fois corrigé et en défaut : le défaut l'emporte.
            {"timestamp": "2026-10-03T00:00:00Z", "jenkins_build": 5, "event": "remediation_applied", "outcome_code": "fixed"},
            {"timestamp": "2026-10-03T00:00:00Z", "jenkins_build": 6, "event": "validation_failed_rollback", "original_build": 5},
        ]
        row = stats(events)[0]
        self.assertEqual((row["cycles"], row["success"], row["conforming"], row["infra"]), (4, 1, 1, 1))
        self.assertEqual(row["failures"], {"bad_fix": 1, "tooling": 1})
        self.assertEqual(row["failure_rate"], 0.5)

    def test_journal_reel_lisible(self):
        path = os.path.join(SCRIPTS, "..", "docs", "fixcve-audit.jsonl")
        with open(path, encoding="utf-8") as fh:
            events = [json.loads(line) for line in fh if line.strip()]
        self.assertTrue(stats(events))


class PlanSchemaTest(unittest.TestCase):
    def validate(self, plan, detected):
        with tempfile.TemporaryDirectory() as d:
            p, q = os.path.join(d, "plan.json"), os.path.join(d, "detected.json")
            for path, doc in ((p, plan), (q, detected)):
                with open(path, "w") as fh:
                    json.dump(doc, fh)
            out = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "fixcve-validate-json.py"),
                                  "--schema", "plan", "--cross-ref", q, p], capture_output=True, text=True)
            return json.loads(out.stdout)

    def test_plan_reel_914_valide(self):
        detected = load_fixture("build-914-detected.json")
        plan = build_plan(detected, load_fixture("build-914-lookup.json"))
        self.assertTrue(self.validate(plan, detected)["ok"])

    def test_critere_b_interdit_au_dessus_de_9(self):
        detected = {"jenkins_build": 1, "stage": "owasp", "findings": [finding("CVE-2026-10001", "p", "1.0.0", cvss=9.5)]}
        plan = build_plan(detected, {"findings": [{"finding_id": "CVE-2026-10001", "package_name": "p",
                                                   "fix_status": "no_fix_available"}]})
        self.assertEqual(plan["actions"][0]["action"], "blocked")
        plan["actions"][0].update(action="suppress_temporary", criterion="B", outcome_code="accepted_temporary")
        self.assertFalse(self.validate(plan, detected)["ok"])

    def test_finding_sans_action_rejete(self):
        detected = {"jenkins_build": 1, "stage": "owasp", "findings": [finding("CVE-2026-10001", "p", "1.0.0")]}
        plan = {"jenkins_build": 1, "stage": "owasp", "actions": [], "pending_reverified": []}
        self.assertFalse(self.validate(plan, detected)["ok"])


class DetectTest(unittest.TestCase):
    detect = load_script("fixcve-detect.py")

    def test_894_doublon_trivy_dedoublonne(self):
        """Même jar à deux emplacements de l'image : un seul finding (build #894)."""
        invalid = load_fixture("build-894-detected-invalid.json")
        keys = [(f["finding_id"], f["package_name"]) for f in invalid["findings"]]
        self.assertGreater(len(keys), len(set(keys)))
        deduped = self.detect.dedupe_findings(invalid["findings"])
        self.assertEqual(len(deduped), len(set(keys)))

    def test_trivy_paquet_systeme(self):
        vuln = {"VulnerabilityID": "CVE-2026-32767", "PkgName": "libexpat", "InstalledVersion": "2.7.4-r0",
                "FixedVersion": "2.7.5-r0", "Severity": "CRITICAL", "Title": "t",
                "CVSS": {"nvd": {"V3Score": 9.8, "V3Vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}}}
        f = self.detect._trivy_finding(vuln, "alpine", "nginx")
        self.assertEqual((f["ecosystem"], f["fixed_versions"]), ("docker", ["2.7.5-r0"]))

    @staticmethod
    def _owasp_html(severity, name="follow-redirects", ver="1.16.0", ghsa="GHSA-8r9p-f939-6h3c"):
        return (
            f'<h3 class="subsectionheader "><a name="l1"></a>{name}:{ver}</h3>'
            f'<p><b><a target="_blank" href="https://github.com/advisories/{ghsa}">{ghsa} (NPM)</a></b>'
            f'<button data-pkgurl="pkg:npm/{name}@{ver}">suppress</button></p>'
            f'<p><pre>desc</pre> CWE-185<br/> Unscored: <ul><li>Severity: {severity}</li></ul> <br/>References:'
        )

    def test_934_finding_node_audit_sans_cvss_bloquant(self):
        """GHSA 'Unscored high' (follow-redirects, build #934) : bloquant pour dependency-check, donc détecté."""
        self.detect.fetch = lambda path: self._owasp_html("high")
        found = self.detect.detect_owasp(934)
        self.assertEqual([(f["finding_id"], f["package_name"], f["cvss"], f["cvss_vector"]) for f in found],
                         [("GHSA-8r9p-f939-6h3c", "follow-redirects", 10.0, None)])

    def test_finding_node_audit_sans_cvss_faible_ignore(self):
        self.detect.fetch = lambda path: self._owasp_html("moderate")
        self.assertEqual(self.detect.detect_owasp(934), [])

    def test_972_finding_retirejs_javascript_detecte(self):
        """DOMPurify embarqué dans swagger-ui (RetireJS, pkg:javascript/, build #972) : ni ignoré ni inclassable."""
        html = (
            '<h3 class="subsectionheader "><a name="l1"></a>swagger-ui-5.32.14.jar: swagger-ui-bundle.js</h3>'
            '<p>pkg:javascript/DOMPurify@3.4.13</p>'
            '<p><span class="underline"><b>CVE-2026-116804</b>&nbsp;(RETIREJS)</span>'
            '<button data-pkgurl="pkg:javascript/DOMPurify@3.4.13">suppress</button></p>'
            '<p><pre>desc</pre> Unscored: <ul><li>Severity: critical</li></ul> <br/>References:'
        )
        self.detect.fetch = lambda path: html
        found = self.detect.detect_owasp(972)
        self.assertEqual([(f["finding_id"], f["ecosystem"], f["package_name"], f["installed_version"], f["cvss"])
                          for f in found],
                         [("CVE-2026-116804", "javascript", "DOMPurify", "3.4.13", 10.0)])
        schema = load_script("fixcve-validate-json.py")
        doc = {"jenkins_build": 972, "stage": "owasp", "findings": found}
        schema.validate_detect(doc)


if __name__ == "__main__":
    unittest.main()
