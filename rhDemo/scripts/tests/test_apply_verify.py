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
from fixcve_lib import verify as verify_mod
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
KC_OLD = "keycloak/keycloak:26.6.2@sha256:" + "0" * 64
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

    def test_bom_importe_version_non_publiee_epinglage(self):
        """Version absente du BOM importé : l'artefact seul est épinglé (correctif unitaire)."""
        status, detail = edits.maven_upgrade("com.fasterxml.jackson.core:jackson-databind", "2.21.5", "2.21.6",
                                             ["CVE-2026-68497"], Registry({"maven:com.fasterxml.jackson:jackson-bom": ["2.21.5"]}),
                                             bom_path_pattern="bom.pom")
        self.assertEqual(status, "applied", detail)
        self.assertIn("<artifactId>jackson-databind</artifactId>\n\t\t\t\t<version>2.21.6</version>", self.read("pom.xml"))
        self.assertNotIn("jackson-2-bom.version", self.read("pom.xml"))

    def test_artefact_non_gere_epingle(self):
        status, _ = edits.maven_upgrade("com.example:inconnu", "1.0", "1.1", ["CVE-2026-10001"], Registry({}),
                                        bom_path_pattern="bom.pom")
        self.assertEqual(status, "applied")
        self.assertIn("<!-- Fix CVE-2026-10001 : inconnu 1.0 -> 1.1 -->", self.read("pom.xml"))

    def test_changement_de_majeure_refuse(self):
        status, detail = edits.maven_upgrade("com.example:inconnu", "1.0", "2.0", ["CVE-2026-10001"], Registry({}),
                                             bom_path_pattern="bom.pom")
        self.assertEqual(status, "failed")
        self.assertIn("majeure", detail)

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
            self.assertIn(f"keycloak/keycloak:26.7.2@{new}", self.read(path))

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
        self.assertTrue(verify(result, {"findings": []}, "owasp", run_odc_scan=False)["ok"])

    def test_tout_bloque_aucun_fichier(self):
        blocked = finding("CVE-2026-75595", "io.netty:netty-handler", "4.1.136", ecosystem="maven", cvss=9.8,
                          image="keycloak")
        result = Applier(plan_of((blocked, {"fix_status": "no_fix_available"})), Registry({}), {}).run()
        self.assertEqual((result["result"], result["reason"], result["changed_files"]),
                         ("NO_ACTION", "cve_bloquante_sans_upgrade_disponible", []))

    def test_montee_impossible_retombe_en_suppression(self):
        f = finding("CVE-2026-10001", "com.example:inconnu", "1.0.0", ecosystem="maven", cvss=7.5)
        result = Applier(plan_of((f, {"fix_status": "fix_available", "target_version": "2.0.1",
                                      "maven_scopes": ["compile"]})), Registry({}), {}).run()
        action = result["actions"][0]
        self.assertEqual((action["action"], action["criterion"]), ("suppress_temporary", "B"))
        self.assertIn("publie mais montee impossible (com.example:inconnu 2.0.1 change de version majeure",
                      action["reason"])
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
        failed, errors, new = compare_odc([up, sup], {"findings": []}, report)
        self.assertEqual(failed, ["CVE-2026-10001|g:a"])
        self.assertTrue(any("suppression sans effet" in e for e in errors))
        # CVE nouvelles, paquet monté ou non : remontées au poller pour être traitées dans le cycle.
        self.assertEqual({(f["finding_id"], f["package_name"], f["installed_version"]) for f in new},
                         {("CVE-2026-10003", "g:a", "1.0.1"), ("CVE-2026-10004", "g:c", "1.0.0")})

    def test_1102_cve_nouvelle_par_ricochet_retraitee(self):
        """Montée du parent : Tomcat passe en 11.0.27 sans être une montée du cycle ; sa CVE
        nouvelle n'est plus ignorée, elle est remontée au format detected.json."""
        import importlib.util
        up = classify(finding("CVE-2026-59414", "org.springframework.boot:spring-boot-security", "4.1.2",
                              ecosystem="maven", cvss=9.1),
                      {"fix_status": "fix_available", "target_version": "4.1.3"})
        report = self.report(("CVE-2026-116830", "pkg:maven/org.apache.tomcat.embed/tomcat-embed-core@11.0.27", 8.7))
        report["dependencies"][0]["vulnerabilities"][0].update(
            description="Missing release of resource\nafter effective lifetime (HTTP/2).",
            cvssv3={"baseScore": 8.7, "vectorString": "AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"})
        res = verify({"actions": [up], "changed_files": []}, {"findings": []}, "owasp", odc_report=report)
        self.assertFalse(res["ok"])
        self.assertEqual(res["errors"], [])
        (f,) = res["new_findings"]
        self.assertEqual((f["package_name"], f["installed_version"], f["cvss_vector"]),
                         ("org.apache.tomcat.embed:tomcat-embed-core", "11.0.27",
                          "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"))
        spec = importlib.util.spec_from_file_location("vj", os.path.join(os.path.dirname(edits.__file__), "..",
                                                                         "fixcve-validate-json.py"))
        vj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vj)
        vj.validate_detect({"jenkins_build": 1102, "stage": "owasp", "findings": res["new_findings"]})

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


class OdcRunTest(unittest.TestCase):
    """run_odc : un rapport périmé n'est jamais relu."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.cwd)
        os.makedirs("target")

    def test_rapport_perime_supprime_avant_le_scan(self):
        with open(verify_mod.ODC_REPORT, "w") as fh:
            json.dump({"dependencies": []}, fh)
        with unittest.mock.patch.dict(os.environ, {"NVD_API_KEY": "x"}), \
                unittest.mock.patch.object(verify_mod, "run", return_value=(124, "", "timeout")):
            report, why = verify_mod.run_odc()
        self.assertIsNone(report)
        self.assertIn("rapport_odc_absent", why)

    def test_oss_index_comme_en_ci_si_compte_present(self):
        """#1102-#1107 : faille vue par OSS Index seul ; le compte n'est jamais en argument."""
        os.makedirs(".mvn")
        open(verify_mod.CI_SETTINGS, "w").close()
        env = {"NVD_API_KEY": "x", "OSSINDEX_USER": "u", "OSSINDEX_PASSWORD": "secret-oss"}
        with unittest.mock.patch.dict(os.environ, env), \
                unittest.mock.patch.object(verify_mod, "run", return_value=(1, "", "")) as run:
            verify_mod.run_odc()
        args = run.call_args.args[0]
        self.assertIn("-DossIndexServerId=ossindex", args)
        self.assertNotIn("-DossIndexAnalyzerEnabled=false", args)
        self.assertFalse(any("secret-oss" in a or "u" == a for a in args))
        with unittest.mock.patch.dict(os.environ, {"OSSINDEX_USER": ""}):
            self.assertEqual(verify_mod.odc_source_args(), ["-DossIndexAnalyzerEnabled=false"])


if __name__ == "__main__":
    unittest.main()
