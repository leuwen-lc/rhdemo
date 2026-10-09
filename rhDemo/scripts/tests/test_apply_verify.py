"""Application (fixcve_lib/apply.py, edits.py) et vérification (verify.py) dans un dossier temporaire.

Le POM, les fichiers d'images et un BOM Spring Boot minimal sont recréés ; npm est simulé.
"""
import json
import os
import tempfile
import unittest
import unittest.mock

from helpers import finding
from fixcve_lib import edits, npm as npm_mod
from fixcve_lib.apply import Applier
from fixcve_lib.policy import classify
from fixcve_lib.registry import Registry
from fixcve_lib.verify import compare_odc, verify

POM = """<project>
\t<parent>
\t\t<groupId>org.springframework.boot</groupId>
\t\t<artifactId>spring-boot-starter-parent</artifactId>
\t\t<version>9.9.9</version>
\t</parent>
\t<properties>
\t\t<java.version>25</java.version>
\t\t<!-- Description à garder -->
\t\t<tomcat.version>11.0.24</tomcat.version>
\t</properties>
</project>
"""
BOM = """<project><dependencyManagement><dependencies>
<dependency><groupId>org.apache.tomcat.embed</groupId><artifactId>tomcat-embed-core</artifactId><version>${tomcat.version}</version></dependency>
<dependency><groupId>org.hibernate.orm</groupId><artifactId>hibernate-core</artifactId><version>${hibernate.version}</version></dependency>
<dependency><groupId>com.fasterxml.jackson</groupId><artifactId>jackson-bom</artifactId><version>${jackson-2-bom.version}</version><type>pom</type><scope>import</scope></dependency>
</dependencies></dependencyManagement></project>"""
KC_OLD = "quay.io/keycloak/keycloak:26.6.2@sha256:" + "0" * 64
ADVISORIES = "# Avis\n\nIntro.\n\n---\n\n## ancien (build #1)\n\n---\n"
OWASP = '<?xml version="1.0"?>\n<suppressions>\n</suppressions>\n'


def plan_of(*pairs, stage="owasp"):
    return {"jenkins_build": 42, "stage": stage, "pending_reverified": [],
            "actions": [classify(f, lk) for f, lk in pairs]}


class Workdir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.old)
        os.makedirs("docs")
        os.makedirs("frontend")
        os.makedirs("infra/dev")
        for path, text in [("pom.xml", POM), ("owasp-suppressions.xml", OWASP), ("docs/SECURITY_ADVISORIES.md", ADVISORIES),
                           ("Jenkinsfile-CI", f'KEYCLOAK_IMAGE = "{KC_OLD}"\n'),
                           ("infra/dev/docker-compose.yml", f"image: {KC_OLD}\n"),
                           ("bom.pom", BOM), ("frontend/package.json", '{"name": "f"}\n'),
                           ("frontend/package-lock.json", json.dumps({"packages": {
                               "node_modules/pkg": {"version": "1.0.0", "dev": True}}}))]:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        patcher = unittest.mock.patch.object(edits, "M2_BOOT_BOM", os.path.join(self.tmp.name, "bom.pom"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()


class MavenEditTest(Workdir):
    def test_propriete_existante_remplacee_commentaire_descriptif_garde(self):
        status, _ = edits.maven_upgrade("org.apache.tomcat.embed:tomcat-embed-core", "11.0.24", "11.0.25",
                                        ["CVE-2026-66299"], Registry({}), bom_path_pattern="bom.pom")
        pom = self.read("pom.xml")
        self.assertEqual(status, "applied")
        self.assertIn("<tomcat.version>11.0.25</tomcat.version>", pom)
        self.assertIn("<!-- Description à garder -->", pom)
        self.assertIn("<!-- Fix CVE-2026-66299 : tomcat-embed-core 11.0.24 -> 11.0.25 -->", pom)

    def test_propriete_absente_ajoutee(self):
        status, _ = edits.maven_upgrade("org.hibernate.orm:hibernate-core", "7.4.5.Final", "7.4.12.Final",
                                        ["CVE-2026-77874"], Registry({}), bom_path_pattern="bom.pom")
        self.assertEqual(status, "applied")
        self.assertIn("\t\t<hibernate.version>7.4.12.Final</hibernate.version>\n\t</properties>", self.read("pom.xml"))

    def test_bom_importe_version_non_publiee(self):
        status, detail = edits.maven_upgrade("com.fasterxml.jackson.core:jackson-databind", "2.21.5", "2.21.6",
                                             ["CVE-2026-68497"], Registry({"maven:com.fasterxml.jackson:jackson-bom": ["2.21.5"]}),
                                             bom_path_pattern="bom.pom")
        self.assertEqual(status, "failed")
        self.assertIn("non publie", detail)

    def test_artefact_non_gere(self):
        status, _ = edits.maven_upgrade("com.example:inconnu", "1.0", "1.1", ["CVE-2026-10001"], Registry({}),
                                        bom_path_pattern="bom.pom")
        self.assertEqual(status, "failed")

    def test_deja_a_jour(self):
        status, _ = edits.maven_upgrade("org.apache.tomcat.embed:tomcat-embed-core", "11.0.20", "11.0.21",
                                        ["CVE-2026-10001"], Registry({}), bom_path_pattern="bom.pom")
        self.assertEqual(status, "already")


class ImageEditTest(Workdir):
    def test_reference_remplacee_partout(self):
        new = "sha256:" + "a" * 64
        status, _ = edits.image_upgrade("keycloak", ("26.6.2", "sha256:" + "0" * 64), "26.7.2", new)
        self.assertEqual(status, "applied")
        for path in ("Jenkinsfile-CI", "infra/dev/docker-compose.yml"):
            self.assertIn(f"quay.io/keycloak/keycloak:26.7.2@{new}", self.read(path))

    def test_reference_absente(self):
        status, _ = edits.image_upgrade("keycloak", ("26.0.0", "sha256:" + "9" * 64), "26.7.2", "sha256:" + "a" * 64)
        self.assertEqual(status, "failed")


class ApplyTest(Workdir):
    def test_cycle_mixte(self):
        tomcat = finding("CVE-2026-66299", "org.apache.tomcat.embed:tomcat-embed-core", "11.0.24", ecosystem="maven")
        npm_dev = finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.0.0", cvss=9.3)
        spring = finding("CVE-2026-47842", "org.springframework.security:spring-security-crypto", "7.1.1",
                         ecosystem="maven", cvss=7.1)
        blocked = finding("CVE-2026-75595", "io.netty:netty-handler", "4.1.136", ecosystem="maven", cvss=9.8,
                          image="keycloak")
        plan = plan_of((tomcat, {"fix_status": "fix_available", "target_version": "11.0.25"}),
                       (npm_dev, {"fix_status": "no_fix_available", "npm_dev_only": True, "aliases": ["CVE-2026-90001"]}),
                       (spring, {"fix_status": "no_fix_available", "maven_scopes": ["compile"]}),
                       (blocked, {"fix_status": "no_fix_available"}))
        with unittest.mock.patch.object(edits, "M2_BOOT_BOM", "bom.pom"):
            result = Applier(plan, Registry({}), {}).run()
        self.assertEqual(result["result"], "APPLIED")
        self.assertEqual(set(result["changed_files"]),
                         {"pom.xml", "owasp-suppressions.xml", "docs/SECURITY_ADVISORIES.md"})
        owasp = self.read("owasp-suppressions.xml")
        self.assertIn("<vulnerabilityName>GHSA-aaaa-bbbb-cccc</vulnerabilityName>", owasp)
        self.assertIn("[PENDING_UPSTREAM_FIX] CVE-2026-47842", owasp)
        self.assertIn(r"^pkg:maven/org\.springframework\.security/.*$", owasp)
        events = {e["event"]: e for e in result["events"]}
        self.assertEqual(events["findings_blocked"]["outcome_code"], "blocked_no_fix_ge9")
        self.assertEqual(events["remediation_applied"]["outcome_code"], "fixed")
        adv = self.read("docs/SECURITY_ADVISORIES.md")
        self.assertLess(adv.index("build #42"), adv.index("build #1"))
        self.assertIn("Non traité (bloqué", adv)
        self.assertTrue(result["commit_message"].startswith("fix(security): corriger tomcat-embed-core, accepter "))
        self.assertEqual(verify(result, {"findings": []}, "owasp", run_odc_scan=False)["ok"], True)

    def test_tout_bloque_aucun_fichier(self):
        blocked = finding("CVE-2026-75595", "io.netty:netty-handler", "4.1.136", ecosystem="maven", cvss=9.8,
                          image="keycloak")
        result = Applier(plan_of((blocked, {"fix_status": "no_fix_available"})), Registry({}), {}).run()
        self.assertEqual((result["result"], result["reason"], result["changed_files"]),
                         ("NO_ACTION", "cve_bloquante_sans_upgrade_disponible", []))

    def test_montee_impossible_retombe_en_suppression(self):
        f = finding("CVE-2026-10001", "com.example:inconnu", "1.0.0", ecosystem="maven", cvss=7.5)
        result = Applier(plan_of((f, {"fix_status": "fix_available", "target_version": "1.0.1",
                                      "maven_scopes": ["compile"]})), Registry({}), {}).run()
        action = result["actions"][0]
        self.assertEqual((action["action"], action["criterion"]), ("suppress_temporary", "B"))
        self.assertIn("[PENDING_UPSTREAM_FIX] CVE-2026-10001", self.read("owasp-suppressions.xml"))

    def test_downgrade_force_par_la_verification(self):
        f = finding("GHSA-aaaa-bbbb-cccc", "pkg", "1.0.0", cvss=7.5)
        plan = plan_of((f, {"fix_status": "fix_available", "target_version": "1.0.1", "npm_dev_only": True}))
        result = Applier(plan, Registry({}), {}, downgrade=["GHSA-aaaa-bbbb-cccc|pkg"]).run()
        self.assertEqual(result["actions"][0]["action"], "suppress_permanent")

    def test_npm_montee_sans_effet_restauree(self):
        """#845/#847 : une montée npm sans effet sur l'arbre résolu n'est jamais conservée."""
        before = self.read("frontend/package-lock.json")
        with unittest.mock.patch.object(edits, "_npm", return_value=(0, "", "")):
            status, _ = edits.npm_upgrade("pkg", "1.0.1")
        self.assertEqual(status, "failed")
        self.assertEqual(self.read("frontend/package-lock.json"), before)
        self.assertNotIn("overrides", self.read("frontend/package.json"))

    def test_npm_montee_effective(self):
        def fake_npm(args, timeout=600):
            with open(npm_mod.LOCKFILE, "w") as fh:
                json.dump({"packages": {"node_modules/pkg": {"version": "1.0.2", "dev": True}}}, fh)
            return 0, "", ""
        with unittest.mock.patch.object(edits, "_npm", side_effect=fake_npm):
            status, detail = edits.npm_upgrade("pkg", "1.0.1")
        self.assertEqual(status, "applied")
        self.assertIn("1.0.2", detail)


class VerifyTest(Workdir):
    @staticmethod
    def report(*vulns):
        deps = {}
        for name, pkg, score in vulns:
            deps.setdefault(pkg, {"packages": [{"id": pkg}], "vulnerabilities": []})
            deps[pkg]["vulnerabilities"].append({"name": name, "cvssv3": {"baseScore": score}})
        return {"dependencies": list(deps.values())}

    def test_montee_sans_effet_et_regression(self):
        up = classify(finding("CVE-2026-10001", "g:a", "1.0.0", ecosystem="maven"),
                      {"fix_status": "fix_available", "target_version": "1.0.1"})
        sup = classify(finding("CVE-2026-10002", "g:b", "1.0.0", ecosystem="maven"),
                       {"fix_status": "no_fix_available", "maven_scopes": ["compile"]})
        report = self.report(("CVE-2026-10001", "pkg:maven/g/a@1.0.1", 8.0),
                             ("CVE-2026-10002", "pkg:maven/g/b@1.0.0", 8.0),
                             ("CVE-2026-10003", "pkg:maven/g/a@1.0.1", 7.5),
                             ("CVE-2026-10004", "pkg:maven/g/c@1.0.0", 9.0))
        failed, errors = compare_odc([up, sup], {"findings": []}, report)
        self.assertEqual(failed, ["CVE-2026-10001|g:a"])
        self.assertTrue(any("suppression sans effet" in e for e in errors))
        self.assertTrue(any("regression : CVE-2026-10003" in e for e in errors))
        self.assertFalse(any("CVE-2026-10004" in e for e in errors), "CVE d'un paquet non touché : pas une régression")

    def test_syntaxe_invalide(self):
        with open("owasp-suppressions.xml", "w") as fh:
            fh.write("<suppressions><!-- a -- b --></suppressions>")
        res = verify({"actions": [], "changed_files": ["owasp-suppressions.xml"]}, {"findings": []}, "owasp",
                     run_odc_scan=False)
        self.assertFalse(res["ok"])

    def test_sans_cle_nvd_incomplet(self):
        with unittest.mock.patch.dict(os.environ, {"NVD_API_KEY": ""}):
            res = verify({"actions": [], "changed_files": []}, {"findings": []}, "owasp")
        self.assertEqual((res["ok"], res["incomplete"]), (True, ["dependency_check_local:cle_nvd_absente"]))


if __name__ == "__main__":
    unittest.main()
