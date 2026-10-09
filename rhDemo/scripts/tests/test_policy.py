"""Table de décision (fixcve_lib/policy.py) rejouée sur les findings réels des incidents."""
import unittest

from helpers import finding, load_fixture
from fixcve_lib.policy import build_plan, classify, downgrade_failed_upgrade


def by_pkg(plan):
    return {a["package_name"]: a for a in plan["actions"]}


class IncidentsTest(unittest.TestCase):
    def test_882_critere_a_prime_sur_cvss_9(self):
        """proxy-addr CVSS 9.3, dev=true : supprimé (critère A), ne bloque plus les 19 autres findings."""
        detected = load_fixture("build-882-detected.json")
        lookup = {"findings": [dict(e, fix_status="no_fix_available", npm_dev_only=(e["package_name"] == "proxy-addr"))
                               for e in load_fixture("build-882-lookup.json")["findings"]]}
        plan = build_plan(detected, lookup)
        proxy = by_pkg(plan)["proxy-addr"]
        self.assertEqual((proxy["action"], proxy["criterion"]), ("suppress_permanent", "A:npm_dev_only"))
        self.assertEqual(len(plan["actions"]), len(detected["findings"]))
        self.assertNotIn("transient", {a["action"] for a in plan["actions"]})

    def test_895_jars_embarques_cvss_9_sans_correctif_bloques(self):
        """bcprov / freemarker 9.1 dans l'image Keycloak, aucun tag corrigé : seul échec conforme."""
        detected = load_fixture("build-895-detected.json")
        lookup = {"findings": [{"finding_id": f["finding_id"], "package_name": f["package_name"],
                                "fix_status": "no_fix_available"} for f in detected["findings"]]}
        for a in build_plan(detected, lookup)["actions"]:
            self.assertEqual((a["action"], a["outcome_code"]), ("blocked", "blocked_no_fix_ge9"))

    def test_914_lookup_reel(self):
        detected = load_fixture("build-914-detected.json")
        lookup = load_fixture("build-914-lookup.json")
        plan = by_pkg(build_plan(detected, lookup))
        self.assertEqual(plan["node-forge"]["action"], "suppress_permanent")
        self.assertEqual(plan["webpack-dev-middleware"]["action"], "suppress_permanent")
        # lookup_failed (ancienne recherche npm) : transitoire, jamais supprimé ni bloqué définitivement.
        self.assertEqual(plan["brace-expansion"]["action"], "transient")


class DecisionTableTest(unittest.TestCase):
    def test_tomcat_735_cvss_7_5_sans_correctif_critere_b(self):
        """#735-#745 : tomcat 7.5 sans correctif a bloqué 11 cycles ; c'est un critère B."""
        f = finding("CVE-2026-66299", "org.apache.tomcat.embed:tomcat-embed-core", "11.0.24", ecosystem="maven")
        a = classify(f, {"fix_status": "no_fix_available", "maven_scopes": ["compile"]})
        self.assertEqual((a["action"], a["criterion"]), ("suppress_temporary", "B"))

    def test_scope_test_critere_a(self):
        f = finding("CVE-2026-10002", "com.h2database:h2", "2.4.240", ecosystem="maven", cvss=9.8)
        a = classify(f, {"fix_status": "no_fix_available", "maven_scopes": ["test"]})
        self.assertEqual((a["action"], a["criterion"]), ("suppress_permanent", "A:maven_scope_test"))

    def test_scope_mixte_pas_de_critere_a(self):
        f = finding("CVE-2026-10002", "g:a", "1.0.0", ecosystem="maven", cvss=9.8)
        a = classify(f, {"fix_status": "no_fix_available", "maven_scopes": ["compile", "test"]})
        self.assertEqual(a["action"], "blocked")

    def test_vecteur_local_critere_a(self):
        f = finding("CVE-2026-10002", "g:a", "1.0.0", ecosystem="maven", cvss=9.0,
                    vector="CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
        self.assertEqual(classify(f, {"fix_status": "no_fix_available"})["criterion"], "A:local_vector")

    def test_jar_image_tierce_jamais_critere_scope(self):
        f = finding("CVE-2026-10002", "g:a", "1.0.0", ecosystem="maven", image="keycloak", cvss=9.1)
        self.assertEqual(classify(f, {"fix_status": "no_fix_available", "maven_scopes": ["test"]})["action"], "blocked")

    def test_npm_dev_only_inconnu_pas_de_critere_a(self):
        f = finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.0.0", cvss=9.3)
        self.assertEqual(classify(f, {"fix_status": "no_fix_available", "npm_dev_only": None})["action"], "blocked")

    def test_correctif_disponible_upgrade(self):
        a = classify(finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.0.0", cvss=9.9),
                     {"fix_status": "fix_available", "target_version": "1.0.1", "aliases": ["CVE-2026-10001"]})
        self.assertEqual((a["action"], a["target_version"]), ("upgrade", "1.0.1"))
        self.assertEqual(a["ids"], ["CVE-2026-10001", "GHSA-aaaa-bbbb-cccc"])

    def test_alias_de_reference_non_inscrit(self):
        """advisory_aliases (GHSA relevés dans le rapport) n'entrent pas dans les identifiants."""
        f = finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.0.0", advisory_aliases=["GHSA-zzzz-zzzz-zzzz"])
        self.assertEqual(classify(f, {"fix_status": "no_fix_available", "npm_dev_only": True})["ids"],
                         ["GHSA-aaaa-bbbb-cccc"])

    def test_montee_echouee_retombe_dans_la_table(self):
        up = classify(finding("CVE-2026-10001", "pkg", "1.0.0", cvss=7.5),
                      {"fix_status": "fix_available", "target_version": "1.0.1", "npm_dev_only": False})
        down = downgrade_failed_upgrade(up)
        self.assertEqual((down["action"], down["criterion"], down["target_version"]), ("suppress_temporary", "B", None))
        up9 = dict(up, cvss=9.5)
        self.assertEqual(downgrade_failed_upgrade(up9)["action"], "blocked")

    def test_finding_absent_du_lookup_transitoire(self):
        plan = build_plan({"jenkins_build": 1, "stage": "owasp", "findings": [finding("CVE-2026-10001", "p", "1.0.0")]},
                          {"findings": []})
        self.assertEqual(plan["actions"][0]["action"], "transient")


if __name__ == "__main__":
    unittest.main()
