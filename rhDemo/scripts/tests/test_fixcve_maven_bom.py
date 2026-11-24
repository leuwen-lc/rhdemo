"""Montées Maven selon le BOM Spring Boot (fixcve_lib/edits.py) et nettoyage des surcharges périmées.

Cas de l'incident du build #1097 : `spring-boot-security` (module de Spring Boot, version écrite en
dur dans le BOM) n'est montable que par le parent ; l'ancien code le rattachait par préfixe au BOM
de Spring Framework et concluait « aucun correctif ». Dossier temporaire, aucun réseau, Maven simulé.
"""
import os
import tempfile
import unittest
import unittest.mock

from helpers import finding
from fixcve_lib import edits, outcomes
from fixcve_lib.apply import Applier
from fixcve_lib.policy import classify, downgrade_failed_upgrade
from fixcve_lib.registry import Registry

PARENT = "<parent>\n\t\t<groupId>org.springframework.boot</groupId>\n\t\t<artifactId>spring-boot-starter-parent</artifactId>\n\t\t<version>{boot}</version>\n\t</parent>"
POM = """<project>
\t{parent}
\t<properties>
\t\t<java.version>25</java.version>
\t\t<!-- Description à garder -->
\t\t<!-- Fix CVE-2026-1 : tomcat-embed-core 11.0.20 -> 11.0.25 -->
\t\t<tomcat.version>11.0.25</tomcat.version>
\t\t<!-- Fix CVE-2026-2 : hibernate-core 7.4.5.Final -> 7.4.20.Final -->
\t\t<hibernate.version>7.4.20.Final</hibernate.version>
\t\t<!-- Compatibilité springdoc -->
\t\t<!-- Fix CVE-2026-3 : swagger-ui 5.0 -> 5.1 -->
\t\t<springdoc-openapi.version>3.2.0</springdoc-openapi.version>
\t\t<keep.version>1.0</keep.version>
\t</properties>

\t<dependencies>
\t\t<dependency>
\t\t\t<groupId>org.springdoc</groupId>
\t\t\t<artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
\t\t\t<version>${{springdoc-openapi.version}}</version>
\t\t</dependency>
\t\t<dependency>
\t\t\t<groupId>com.example</groupId>
\t\t\t<artifactId>en-dur</artifactId>
\t\t\t<version>1.0.0</version>
\t\t</dependency>
\t</dependencies>
</project>
"""


def bom(boot, tomcat="11.0.27", hibernate="7.4.15.Final"):
    return f"""<project><properties>
<tomcat.version>{tomcat}</tomcat.version><hibernate.version>{hibernate}</hibernate.version>
<spring-framework.version>7.0.11</spring-framework.version><jackson-bom.version>3.1.8</jackson-bom.version>
</properties><dependencyManagement><dependencies>
<dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-security</artifactId><version>{boot}</version></dependency>
<dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-actuator</artifactId><version>{boot}</version></dependency>
<dependency><groupId>org.apache.tomcat.embed</groupId><artifactId>tomcat-embed-core</artifactId><version>${{tomcat.version}}</version></dependency>
<dependency><groupId>org.hibernate.orm</groupId><artifactId>hibernate-core</artifactId><version>${{hibernate.version}}</version></dependency>
<dependency><groupId>org.springframework</groupId><artifactId>spring-framework-bom</artifactId><version>${{spring-framework.version}}</version><type>pom</type><scope>import</scope></dependency>
<dependency><groupId>tools.jackson</groupId><artifactId>jackson-bom</artifactId><version>${{jackson-bom.version}}</version><type>pom</type><scope>import</scope></dependency>
</dependencies></dependencyManagement></project>"""


SPRING_BOM = "<project><dependencyManagement><dependencies><dependency><groupId>org.springframework</groupId><artifactId>spring-core</artifactId><version>7.0.12</version></dependency></dependencies></dependencyManagement></project>"
JACKSON_BOM = "<project><dependencyManagement><dependencies><dependency><groupId>tools.jackson.core</groupId><artifactId>jackson-databind</artifactId><version>3.1.9</version></dependency></dependencies></dependencyManagement></project>"


def registry(**extra):
    return Registry({"maven:org.springframework.boot:spring-boot-starter-parent": ["4.1.2", "4.1.3", "4.2.0"],
                     "pom:org.springframework.boot:spring-boot-dependencies:4.1.3": bom("4.1.3"),
                     "maven:org.springframework:spring-framework-bom": ["7.0.11", "7.0.12", "4.1.3.RELEASE"],
                     "pom:org.springframework:spring-framework-bom:7.0.12": SPRING_BOM,
                     "maven:tools.jackson:jackson-bom": ["3.1.8", "3.1.9"],
                     "pom:tools.jackson:jackson-bom:3.1.9": JACKSON_BOM, **extra})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.old)
        os.makedirs("docs")
        self.write("pom.xml", POM.format(parent=PARENT.format(boot="4.1.2")))
        self.write("bom-4.1.2.pom", bom("4.1.2"))
        self.write("owasp-suppressions.xml", '<?xml version="1.0"?>\n<suppressions>\n</suppressions>\n')
        self.write("docs/SECURITY_ADVISORIES.md", "# Avis\n\nIntro.\n\n---\n")
        p = unittest.mock.patch.object(edits, "M2_BOOT_BOM", os.path.join(self.tmp.name, "bom-{v}.pom"))
        p.start()
        self.addCleanup(p.stop)

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def pom(self):
        with open("pom.xml", encoding="utf-8") as fh:
            return fh.read()

    def upgrade(self, package, installed, target, reg=None, baseline=None):
        return edits.maven_upgrade(package, installed, target, ["CVE-2026-59414"], reg or registry(),
                                   baseline_pom=baseline)


class BootModuleTest(Base):
    def test_module_spring_boot_monte_le_parent(self):
        status, detail = self.upgrade("org.springframework.boot:spring-boot-security", "4.1.2", "4.1.3")
        self.assertEqual(status, "applied", detail)
        self.assertEqual(edits.boot_version(self.pom()), "4.1.3")
        self.assertIn("<spring-framework.version>", bom("x"))          # rien posé sur Spring Framework :
        self.assertNotIn("<spring-framework.version>", self.pom())     # le défaut du build #1097

    def test_deuxieme_module_du_meme_cycle(self):
        baseline = self.pom()
        self.upgrade("org.springframework.boot:spring-boot-security", "4.1.2", "4.1.3", baseline=baseline)
        status, detail = self.upgrade("org.springframework.boot:spring-boot-actuator", "4.1.2", "4.1.3",
                                      baseline=baseline)
        self.assertEqual(status, "applied")
        self.assertIn("monte par ce cycle", detail)

    def test_hors_branche_mineure_refuse(self):
        status, detail = self.upgrade("org.springframework.boot:spring-boot-security", "4.1.2", "4.2.0")
        self.assertEqual(status, "failed")
        self.assertIn("hors de la branche", detail)
        self.assertEqual(edits.boot_version(self.pom()), "4.1.2")

    def test_parent_non_publie(self):
        reg = registry(**{"maven:org.springframework.boot:spring-boot-starter-parent": ["4.1.2"]})
        status, _ = self.upgrade("org.springframework.boot:spring-boot-security", "4.1.2", "4.1.3", reg)
        self.assertEqual(status, "failed")

    def test_bom_du_nouveau_parent_lu_sur_maven_central(self):
        """Après la montée du parent, le BOM 4.1.3 n'est pas dans ~/.m2 : lu par le registre."""
        self.upgrade("org.springframework.boot:spring-boot-security", "4.1.2", "4.1.3")
        status, detail = self.upgrade("org.apache.tomcat.embed:tomcat-embed-core", "11.0.27", "11.0.28")
        self.assertEqual(status, "applied", detail)
        self.assertIn("<tomcat.version>11.0.28</tomcat.version>", self.pom())


class ImportedBomTest(Base):
    def test_artefact_liste_par_le_bom_importe(self):
        status, detail = self.upgrade("org.springframework:spring-core", "7.0.11", "7.0.12")
        self.assertEqual(status, "applied", detail)
        self.assertIn("<spring-framework.version>7.0.12</spring-framework.version>", self.pom())

    def test_prefixe_sans_appartenance_epingle(self):
        """org.springframework.boot:inconnu commence par org.springframework : jamais rattaché au
        BOM de Spring Framework s'il ne le liste pas."""
        status, detail = self.upgrade("org.springframework.boot:inconnu", "7.0.11", "7.0.12")
        self.assertEqual(status, "applied", detail)
        self.assertNotIn("<spring-framework.version>", self.pom())
        self.assertIn("<artifactId>inconnu</artifactId>", self.pom())

    def test_bom_importe_illisible(self):
        status, _ = self.upgrade("tools.jackson.core:jackson-databind", "3.1.8", "3.1.9",
                                 registry(**{"pom:tools.jackson:jackson-bom:3.1.9": "error"}))
        self.assertEqual(status, "failed")


class PinTest(Base):
    def test_epinglage_insere_puis_remplace(self):
        status, _ = self.upgrade("org.webjars:swagger-ui", "5.32.10", "5.32.11")
        self.assertEqual(status, "applied")
        pom = self.pom()
        self.assertLess(pom.index("<dependencyManagement>"), pom.index("\t<dependencies>\n\t\t<dependency>\n\t\t\t<groupId>org.springdoc"))
        status, _ = self.upgrade("org.webjars:swagger-ui", "5.32.11", "5.32.12")
        self.assertEqual(status, "applied")
        pom = self.pom()
        self.assertEqual(pom.count("<artifactId>swagger-ui</artifactId>"), 1)
        self.assertEqual(pom.count("Fix CVE-2026-59414 : swagger-ui"), 1)
        self.assertIn("<version>5.32.12</version>", pom)
        self.assertEqual(self.upgrade("org.webjars:swagger-ui", "5.32.10", "5.32.11")[0], "already")

    def test_dependance_directe_par_propriete(self):
        status, _ = self.upgrade("org.springdoc:springdoc-openapi-starter-webmvc-ui", "3.2.0", "3.2.1")
        self.assertEqual(status, "applied")
        self.assertIn("<springdoc-openapi.version>3.2.1</springdoc-openapi.version>", self.pom())
        self.assertIn("<!-- Compatibilité springdoc -->", self.pom())
        self.assertNotIn("<dependencyManagement>", self.pom())

    def test_dependance_directe_en_dur_refusee(self):
        status, detail = self.upgrade("com.example:en-dur", "1.0.0", "1.0.1")
        self.assertEqual(status, "failed")
        self.assertIn("ecrite en dur", detail)


class CleanupTest(Base):
    def cleanup(self, resolved=None):
        return edits.cleanup_stale_overrides(registry(), lambda pom: resolved)

    def test_proprietes_perimees_retirees_les_autres_gardees(self):
        removed, _ = self.cleanup()
        pom = self.pom()
        self.assertNotIn("<tomcat.version>", pom)                    # 11.0.25 <= 11.0.27 du BOM
        self.assertNotIn("Fix CVE-2026-1", pom)
        self.assertIn("<hibernate.version>7.4.20.Final</hibernate.version>", pom)   # > BOM : utile
        self.assertIn("<springdoc-openapi.version>3.2.0", pom)       # inconnue du BOM : gardée
        self.assertIn("<!-- Description à garder -->", pom)
        self.assertIn("<keep.version>1.0</keep.version>", pom)
        self.assertEqual(removed, ["tomcat.version 11.0.25 retire (BOM Spring Boot 4.1.2 : 11.0.27)"])

    def test_epinglages_selon_la_resolution_sans_eux(self):
        self.upgrade("org.webjars:swagger-ui", "5.32.10", "5.32.11")
        self.upgrade("com.example:lib", "2.0.0", "2.0.5")
        self.upgrade("com.example:sortie", "1.0.0", "1.0.1")
        removed, _ = self.cleanup({"org.webjars:swagger-ui": "5.33.0", "com.example:lib": "2.0.0"})
        pom = self.pom()
        self.assertNotIn("<artifactId>swagger-ui</artifactId>", pom)   # amené plus haut sans lui
        self.assertNotIn("sortie", pom)                              # plus dans l'arbre
        self.assertIn("<artifactId>lib</artifactId>", pom)           # toujours nécessaire
        self.assertEqual(len([r for r in removed if r.startswith("epinglage")]), 2)

    def test_dependency_management_vide_retire(self):
        self.upgrade("org.webjars:swagger-ui", "5.32.10", "5.32.11")
        self.cleanup({"org.webjars:swagger-ui": "5.33.0"})
        self.assertNotIn("dependencyManagement", self.pom())
        self.assertIn("</properties>\n\n\t<dependencies>", self.pom())   # mise en page d'origine

    def test_resolution_impossible_epinglages_gardes(self):
        self.upgrade("org.webjars:swagger-ui", "5.32.10", "5.32.11")
        _, warnings = self.cleanup(None)
        self.assertIn("<artifactId>swagger-ui</artifactId>", self.pom())
        self.assertTrue(warnings)

    def test_pom_sans_epinglage_pour_maven(self):
        self.upgrade("org.webjars:swagger-ui", "5.32.10", "5.32.11")
        seen = {}

        def fake(pom_file=None):
            with open(pom_file, encoding="utf-8") as fh:
                seen["pom"] = fh.read()
            return {"org.webjars:swagger-ui": [("5.33.0", "compile")]}
        with unittest.mock.patch.object(edits, "default_maven_deps", fake):
            self.assertEqual(edits.unpinned_versions(self.pom()), {"org.webjars:swagger-ui": "5.33.0"})
        self.assertNotIn("<artifactId>swagger-ui</artifactId>", seen["pom"])
        self.assertFalse(os.path.exists(edits.UNPINNED_POM))


class IncidentCycleTest(Base):
    def test_cycle_du_build_1097(self):
        """spring-boot-security sans avis OSV, montée heuristique 4.1.3 : parent monté, tomcat
        périmé retiré, plus aucune trace de « aucun correctif »."""
        f = finding("CVE-2026-59414", "org.springframework.boot:spring-boot-security", "4.1.2",
                    ecosystem="maven", cvss=9.1)
        plan = {"jenkins_build": 1099, "stage": "owasp", "pending_reverified": [],
                "actions": [classify(f, {"fix_status": "fix_available", "target_version": "4.1.3",
                                         "proof": "heuristic", "maven_scopes": ["compile"]})]}
        result = Applier(plan, registry(), {}, resolve_unpinned=lambda pom: {}).run()
        self.assertEqual(result["result"], "APPLIED")
        self.assertEqual(edits.boot_version(self.pom()), "4.1.3")
        self.assertNotIn("<tomcat.version>", self.pom())
        events = {e["event"]: e for e in result["events"]}
        self.assertEqual(events["remediation_applied"]["outcome_code"], "fixed")
        self.assertIn("tomcat.version 11.0.25 retire (BOM Spring Boot 4.1.3 : 11.0.27)",
                      events["stale_overrides_removed"]["removed"])
        self.assertIn("retirer tomcat.version (surcharges perimees)", result["commit_message"])
        self.assertIsNone(outcomes.outcome_of(events["stale_overrides_removed"]))

    def test_pas_de_nettoyage_si_pom_inchange(self):
        f = finding("CVE-2026-9", "com.example:x", "1.0.0", ecosystem="maven", cvss=7.5)
        plan = {"jenkins_build": 1, "stage": "owasp", "pending_reverified": [],
                "actions": [classify(f, {"fix_status": "no_fix_available", "maven_scopes": ["compile"]})]}
        Applier(plan, registry(), {}, resolve_unpinned=lambda pom: {}).run()
        self.assertIn("<tomcat.version>11.0.25", self.pom())


class PolicyCauseTest(unittest.TestCase):
    def test_cause_gardee_et_compte_comme_defaut(self):
        f = finding("CVE-2026-59414", "org.springframework.boot:spring-boot-security", "4.1.2",
                    ecosystem="maven", cvss=9.1)
        action = classify(f, {"fix_status": "fix_available", "target_version": "4.1.3", "maven_scopes": ["compile"]})
        down = downgrade_failed_upgrade(action, cause="parent non publie")
        self.assertEqual(down["action"], "blocked")
        self.assertEqual(down["outcome_code"], "tooling")
        self.assertIn("correctif 4.1.3 publie mais montee impossible (parent non publie)", down["reason"])
        self.assertNotIn("aucun correctif", down["reason"])
        # Bascule demandée par la vérification (le correctif n'efface pas la faille) : échec conforme.
        self.assertEqual(downgrade_failed_upgrade(action)["outcome_code"], "blocked_no_fix_ge9")
