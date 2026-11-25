"""Règles métier isolées (fixcve_lib/rules.py) et table de décision pure (policy.decide)."""
import glob
import io
import os
import tokenize
import unittest

from helpers import SCRIPTS, finding
from test_outcomes_schema_detect import load_script
from fixcve_lib.policy import build_plan, classify, decide
from fixcve_lib.rules import (CVSS_BLOCKING, CVSS_FAIL_THRESHOLD, KINDS, PROJECT_IMAGE, kind_name,
                              stage_type)

LOCAL = "CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
NETWORK = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


class LiteralsTest(unittest.TestCase):
    """P2 : aucun seuil ni nom d'image du projet recopié hors de rules.py."""

    def test_aucune_constante_metier_hors_de_rules(self):
        forbidden_strings = {repr(PROJECT_IMAGE), f'"{PROJECT_IMAGE}"'}
        forbidden_numbers = {str(CVSS_BLOCKING), str(CVSS_FAIL_THRESHOLD)}
        files = glob.glob(os.path.join(SCRIPTS, "fixcve*.py")) + glob.glob(os.path.join(SCRIPTS, "fixcve_lib", "*.py"))
        offenders = []
        for path in files:
            if path.endswith(os.path.join("fixcve_lib", "rules.py")):
                continue
            with open(path, encoding="utf-8") as fh:
                for tok in tokenize.generate_tokens(io.StringIO(fh.read()).readline):
                    if (tok.type == tokenize.STRING and tok.string in forbidden_strings) or \
                            (tok.type == tokenize.NUMBER and tok.string in forbidden_numbers):
                        offenders.append(f"{os.path.basename(path)}:{tok.start[0]} {tok.string}")
        self.assertEqual(offenders, [])


class KindTest(unittest.TestCase):
    """P1 : nature du composant, calculée à un seul endroit."""

    def test_table_des_natures(self):
        cases = {("maven", PROJECT_IMAGE): "project_maven", ("npm", PROJECT_IMAGE): "project_npm",
                 ("javascript", PROJECT_IMAGE): "jar_embedded_js", ("docker", "nginx"): "image_os",
                 ("docker", PROJECT_IMAGE): "image_os", ("maven", "keycloak"): "image_embedded_jar"}
        for (eco, image), expected in cases.items():
            self.assertEqual(kind_name(eco, image), expected, (eco, image))

    def test_stage_type(self):
        self.assertEqual(stage_type("Scan Sécurité Images Docker (Trivy) :: x"), "trivy")
        self.assertEqual(stage_type("OWASP Dependency-Check"), "owasp")
        self.assertIsNone(stage_type("Tests Selenium"))

    def test_812_jar_image_tierce_ne_passe_pas_pour_le_pom(self):
        """keycloak-services (image keycloak) étiqueté dépendance du projet : rejeté par le validateur."""
        schema = load_script("fixcve-validate-json.py")
        f = dict(finding("CVE-2026-18963", "org.keycloak:keycloak-services", "26.6.3", ecosystem="maven",
                         image="keycloak", cvss=9.1), source="trivy", fixed_version_hint=None,
                 fixed_versions=[], title="t", component_kind="project_maven")
        with self.assertRaises(schema.SchemaError):
            schema.validate_detect({"jenkins_build": 812, "stage": "trivy", "findings": [f]})
        f["component_kind"] = "image_embedded_jar"
        self.assertEqual(schema.validate_detect({"jenkins_build": 812, "stage": "trivy", "findings": [f]}), 1)

    def test_plan_montee_impossible_pour_lib_js_embarquee(self):
        schema = load_script("fixcve-validate-json.py")
        detected = {"jenkins_build": 1, "stage": "owasp",
                    "findings": [finding("CVE-2026-116804", "DOMPurify", "3.4.13", ecosystem="javascript")]}
        plan = build_plan(detected, {"findings": []})
        plan["actions"][0].update(action="upgrade", target_version="3.4.14", outcome_code="fixed")
        with self.assertRaises(schema.SchemaError):
            schema.validate_plan(plan, detected)

    def test_plan_nature_differente_du_finding_rejetee(self):
        schema = load_script("fixcve-validate-json.py")
        detected = {"jenkins_build": 1, "stage": "trivy",
                    "findings": [finding("CVE-2026-1", "g:a", "1.0.0", ecosystem="maven", image="keycloak")]}
        plan = build_plan(detected, {"findings": [{"finding_id": "CVE-2026-1", "package_name": "g:a",
                                                   "fix_status": "no_fix_available"}]})
        self.assertEqual(plan["actions"][0]["component_kind"], "image_embedded_jar")
        plan["actions"][0]["component_kind"] = "project_maven"
        with self.assertRaises(schema.SchemaError):
            schema.validate_plan(plan, detected)

    def test_detect_porte_la_nature(self):
        detect = load_script("fixcve-detect.py")
        vuln = {"VulnerabilityID": "CVE-2026-1", "PkgName": "x", "InstalledVersion": "1.0", "Severity": "CRITICAL",
                "PkgIdentifier": {"PURL": "pkg:maven/org.keycloak/keycloak-services@26.6.3"}, "CVSS": {}}
        self.assertEqual(detect._trivy_finding(vuln, "jar", "keycloak")["component_kind"], "image_embedded_jar")


class DecideTest(unittest.TestCase):
    """P4 : la table de décision sur des valeurs simples, lisible comme celle de la documentation."""

    def test_table(self):
        maven, npm, image_jar = KINDS["project_maven"], KINDS["project_npm"], KINDS["image_embedded_jar"]
        cases = [
            # (nature, statut, cvss, vecteur, portées, dev_only) -> (action, critère)
            ((maven, "fix_available", 9.8, NETWORK, None, None), ("upgrade", None)),
            ((maven, "lookup_failed", 9.8, NETWORK, None, None), ("transient", None)),
            ((maven, "no_fix_available", 9.8, LOCAL, None, None), ("suppress_permanent", "A:local_vector")),
            ((maven, "no_fix_available", 9.8, NETWORK, ["test"], None), ("suppress_permanent", "A:maven_scope_test")),
            ((maven, "no_fix_available", 9.8, NETWORK, ["compile", "test"], None), ("blocked", None)),
            ((npm, "no_fix_available", 9.3, NETWORK, None, True), ("suppress_permanent", "A:npm_dev_only")),
            ((npm, "no_fix_available", 9.3, NETWORK, None, None), ("blocked", None)),
            ((image_jar, "no_fix_available", 9.1, NETWORK, ["test"], None), ("blocked", None)),
            ((image_jar, "no_fix_available", 8.9, NETWORK, None, None), ("suppress_temporary", "B")),
            ((maven, "no_fix_available", CVSS_BLOCKING, NETWORK, None, None), ("blocked", None)),
        ]
        for args, expected in cases:
            self.assertEqual(decide(*args), expected, args)

    def test_classify_reprend_decide(self):
        f = finding("CVE-2026-1", "g:a", "1.0.0", ecosystem="maven", cvss=9.8)
        a = classify(f, {"fix_status": "no_fix_available", "maven_scopes": ["provided"]})
        self.assertEqual((a["action"], a["criterion"], a["component_kind"]),
                         ("suppress_permanent", "A:maven_scope_provided", "project_maven"))


if __name__ == "__main__":
    unittest.main()
