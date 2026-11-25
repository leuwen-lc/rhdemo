"""fixcve_lib/jenkins.py : cause réelle d'un build en échec (incident #819) et client HTTP."""
import unittest

import helpers  # noqa: F401  (chemin de fixcve_lib)
from fixcve_lib import jenkins
from test_poller import FakeJenkins, HttpStatus

OWASP = "OWASP Dependency-Check"
TRIVY = "Scan Sécurité Images Docker (Trivy)"


def wfapi(*stages):
    return {"stages": [{"name": n, "status": s, "startTimeMillis": i} for i, (n, s) in enumerate(stages)]}


class FailureContextTest(unittest.TestCase):
    def test_819_stage_saute_marque_failed_par_wfapi(self):
        """Le vrai coupable reste SUCCESS dans wfapi, le FAILED se reporte sur le stage sauté suivant."""
        console = (f"[Pipeline] {{ (Build)\nok\n[Pipeline] // stage\n[Pipeline] {{ ({OWASP})\n"
                   "[ERROR] npm warn deprecated\nÉCHEC: 3 vulnérabilités\n[Pipeline] }\n"
                   f"[Pipeline] {{ ({TRIVY})\nStage \"{TRIVY}\" skipped due to earlier failure(s)\n")
        stage, detail = jenkins.failure_context(wfapi((OWASP, "SUCCESS"), (TRIVY, "FAILED")), console)
        self.assertEqual(stage, OWASP)
        self.assertEqual(detail, "[ERROR] npm warn deprecated ÉCHEC: 3 vulnérabilités ")

    def test_stage_failed_reel_garde(self):
        console = f"[Pipeline] {{ ({TRIVY})\nÉCHEC: 1 vulnérabilités CRITICAL détectées\n[Pipeline] // stage\n"
        stage, detail = jenkins.failure_context(wfapi((OWASP, "SUCCESS"), (TRIVY, "FAILED")), console)
        self.assertEqual((stage, detail), (TRIVY, "ÉCHEC: 1 vulnérabilités CRITICAL détectées "))

    def test_plus_ancien_stage_failed(self):
        stage, _ = jenkins.failure_context(
            {"stages": [{"name": TRIVY, "status": "FAILED", "startTimeMillis": 9},
                        {"name": OWASP, "status": "FAILED", "startTimeMillis": 3}]}, "")
        self.assertEqual(stage, OWASP)

    def test_pseudo_stages_ignores(self):
        """Librairie partagée et branches parallèles ne sont pas des stages déclaratifs."""
        console = (f"[Pipeline] {{ ({OWASP})\nx\n[Pipeline] {{ (rhDemo/vars/scan.groovy)\n"
                   f"[Pipeline] {{ (Branch: Scan keycloak)\nStage \"{TRIVY}\" skipped due to earlier failure(s)\n")
        stage, _ = jenkins.failure_context(None, console)
        self.assertEqual(stage, "inconnu")

    def test_nettoyage_ansi_et_marqueurs(self):
        console = (f"\x1b[1mha:////ABC=[Pipeline] {{ ({OWASP})\x1b[0m\r\n\x1b[31mÉCHEC: x\x1b[0m\r\n"
                   "[Pipeline] // stage\n")
        stage, detail = jenkins.failure_context(wfapi((OWASP, "FAILED")), console)
        self.assertEqual((stage, detail), (OWASP, "ÉCHEC: x "))

    def test_repli_sur_les_lignes_explicites(self):
        console = "\n".join(["[ERROR] bruit"] * 3 + ["BUILD FAILURE", "Caused by: boom"])
        stage, detail = jenkins.failure_context(None, console)
        self.assertEqual((stage, detail), ("inconnu", "BUILD FAILURE Caused by: boom "))

    def test_repli_error_puis_non_disponible(self):
        self.assertEqual(jenkins.failure_context(None, "a\n[ERROR] x\n")[1], "[ERROR] x ")
        self.assertEqual(jenkins.failure_context(None, ""), ("inconnu", "non disponible"))

    def test_extrait_borne(self):
        console = f"[Pipeline] {{ ({OWASP})\n" + "\n".join(f"ligne {i} " + "x" * 200 for i in range(30))
        _, detail = jenkins.failure_context(wfapi((OWASP, "FAILED")), console)
        self.assertEqual(len(detail), jenkins.DETAIL_LIMIT)
        self.assertTrue(detail.startswith("ligne 18 "), "12 dernières lignes du bloc")


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.server = FakeJenkins()
        self.addCleanup(self.server.close)
        self.client = jenkins.Jenkins(self.server.url, "u", "secret", retry_delay=0)

    def test_authentification_basic(self):
        self.server.routes = {"lastCompletedBuild": {"number": 3}}
        self.assertEqual(self.client.json(self.client.job_url("lastCompletedBuild/api/json"))["number"], 3)
        self.assertEqual(self.server.requests[0], ("/job/RHDemo-CI/lastCompletedBuild/api/json", "Basic dTpzZWNyZXQ="))

    def test_crochets_non_interpretes(self):
        """#752/#753 : les crochets de tree=actions[...] partent tels quels."""
        self.server.routes = {"tree=actions[lastBuiltRevision[SHA1]]": {"actions": []}}
        self.assertEqual(self.client.json(self.client.job_url("5/api/json?tree=actions[lastBuiltRevision[SHA1]]")),
                         {"actions": []})

    def test_erreur_transitoire_reessayee_puis_code(self):
        self.server.routes = {"x": HttpStatus(503)}
        with self.assertRaises(jenkins.JenkinsError) as ctx:
            self.client.get(self.client.job_url("x"))
        self.assertEqual(ctx.exception.code, 503)
        self.assertEqual(len(self.server.requests), jenkins.RETRIES + 1)

    def test_401_sans_nouvel_essai(self):
        self.server.routes = {"x": HttpStatus(401)}
        with self.assertRaises(jenkins.JenkinsError) as ctx:
            self.client.get(self.client.job_url("x"))
        self.assertEqual((ctx.exception.code, len(self.server.requests)), (401, 1))

    def test_injoignable(self):
        client = jenkins.Jenkins("http://127.0.0.1:9", "u", "t", retry_delay=0)
        with self.assertRaises(jenkins.JenkinsError) as ctx:
            client.get(client.job_url("x"))
        self.assertIsNone(ctx.exception.code)

    def test_json_illisible(self):
        self.server.routes = {"x": "<html>"}
        with self.assertRaises(jenkins.JenkinsError):
            self.client.json(self.client.job_url("x"))
        self.assertEqual(self.client.text_or_empty(self.client.job_url("absent")), "")


if __name__ == "__main__":
    unittest.main()
