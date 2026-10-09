"""Générateurs owasp-suppressions.xml / .trivyignore.yaml (fixcve_lib/suppressions.py)."""
import unittest
import xml.etree.ElementTree as ET

import yaml

import helpers  # noqa: F401 - chemin vers fixcve_lib
from fixcve_lib import suppressions as s

BASE = """<?xml version="1.0" encoding="UTF-8"?>
<suppressions xmlns="https://jeremylong.github.io/DependencyCheck/dependency-suppression.1.3.xsd">

    <!--
        Commentaire historique conservé tel quel.
    -->
    <suppress>
        <notes>CVE-2026-90711 : proxy-addr (critère A).</notes>
        <packageUrl regex="true">^pkg:npm/proxy-addr@.*$</packageUrl>
        <cve>CVE-2026-90711</cve>
    </suppress>

    <suppress>
        <notes>[PENDING_UPSTREAM_FIX] spring-security.</notes>
        <packageUrl regex="true">^pkg:maven/org\\.springframework\\.security/.*$</packageUrl>
        <cve>CVE-2026-47842</cve>
    </suppress>

</suppressions>
"""


class OwaspTest(unittest.TestCase):
    def test_double_inscription_et_xml_valide(self):
        text, added = s.add_owasp(BASE, "npm", "node-forge", ["GHSA-86w9-cpqp-85rv", "CVE-2026-33894"],
                                  "Note avec -- deux tirets & <chevrons>")
        self.assertTrue(added)
        ET.fromstring(text.encode())
        self.assertIn("<cve>CVE-2026-33894</cve>", text)
        self.assertIn("<vulnerabilityName>GHSA-86w9-cpqp-85rv</vulnerabilityName>", text)
        self.assertIn("Commentaire historique conservé tel quel.", text)
        self.assertIn("&amp; &lt;chevrons&gt;", text)

    def test_forme_manquante_ajoutee_au_bloc_existant(self):
        """Renovate #123 : CVE inscrit, GHSA (Node Audit) manquant -> ajouté dans le même bloc."""
        text, added = s.add_owasp(BASE, "npm", "proxy-addr", ["CVE-2026-90711", "GHSA-jqcg-44mw-7w3h"], "x")
        self.assertTrue(added)
        self.assertEqual(text.count("<suppress>"), 2)
        self.assertIn("<vulnerabilityName>GHSA-jqcg-44mw-7w3h</vulnerabilityName>", text)
        ET.fromstring(text.encode())

    def test_deja_couvert_rien_a_faire(self):
        self.assertEqual(s.add_owasp(BASE, "npm", "proxy-addr", ["CVE-2026-90711"], "x"), (BASE, False))

    def test_groupe_entier_pour_cpe_generique(self):
        self.assertEqual(s.package_regex("maven", "org.apache.tomcat.embed:tomcat-embed-core"),
                         r"^pkg:maven/org\.apache\.tomcat\.embed/.*$")
        self.assertEqual(s.package_regex("maven", "org.hibernate.orm:hibernate-core"),
                         r"^pkg:maven/org\.hibernate\.orm/hibernate-core@.*$")
        self.assertTrue(s.is_suppressed(BASE, "maven", "org.springframework.security:spring-security-web",
                                        ["CVE-2026-47842"]))

    def test_retrait_complet_et_partiel(self):
        text, n = s.remove_owasp(BASE, "npm", "proxy-addr", ["CVE-2026-90711"])
        self.assertEqual((n, text.count("<suppress>")), (1, 1))
        both, _ = s.add_owasp(BASE, "npm", "proxy-addr", ["GHSA-jqcg-44mw-7w3h"], "x")
        partial, n = s.remove_owasp(both, "npm", "proxy-addr", ["CVE-2026-90711"])
        self.assertIn("GHSA-jqcg-44mw-7w3h", partial)
        self.assertNotIn("<cve>CVE-2026-90711</cve>", partial)
        ET.fromstring(partial.encode())

    def test_lecture_des_suppressions_temporaires(self):
        pending = [b for b in s.parse_owasp(BASE) if b["pending"]]
        self.assertEqual([(b["ecosystem"], b["package"]) for b in pending],
                         [("maven", "org.springframework.security:*")])


class TrivyTest(unittest.TestCase):
    BASE = "vulnerabilities:\n\n  # commentaire\n  - id: CVE-2025-68121\n    pkg-name: gosu\n    statement: \"x\"\n"

    def test_ajout_valide_et_idempotent(self):
        text, added = s.add_trivy(self.BASE, "CVE-2026-8763", "org.bouncycastle:bcprov-jdk18on",
                                  '[PENDING_UPSTREAM_FIX] [OSV:ALPINE:v3.23] "guillemets"', "commentaire")
        self.assertTrue(added)
        doc = yaml.safe_load(text)
        self.assertEqual(len(doc["vulnerabilities"]), 2)
        self.assertEqual(s.add_trivy(text, "CVE-2026-8763", "org.bouncycastle:bcprov-jdk18on", "y", "c")[1], False)
        entry = [e for e in s.parse_trivy(text) if e["id"] == "CVE-2026-8763"][0]
        self.assertEqual((entry["pending"], entry["osv"]), (True, {"distro": "ALPINE", "branch": "v3.23"}))

    def test_retrait(self):
        text, n = s.remove_trivy(self.BASE, "CVE-2025-68121", "gosu")
        self.assertEqual(n, 1)
        self.assertEqual(yaml.safe_load(text)["vulnerabilities"], None)

    def test_jeton_osv(self):
        self.assertEqual(s.osv_token("alpine", "3.23.3"), "[OSV:ALPINE:v3.23]")
        self.assertEqual(s.osv_token("debian", "12.5"), "[OSV:DEBIAN:12]")
        self.assertEqual(s.osv_token("ubuntu", "24.04"), "[OSV:UBUNTU:24.04]")
        self.assertEqual(s.osv_token("redhat", "9"), "")


if __name__ == "__main__":
    unittest.main()
