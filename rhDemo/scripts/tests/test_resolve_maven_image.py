"""Recherche de correctif Maven et images tierces (fixcve_lib/resolve.py), hors réseau."""
import unittest

from helpers import OsvDir, context, finding, osv_doc
from fixcve_lib.resolve import resolve_finding, reverify_pending

JACKSON = "com.fasterxml.jackson.core:jackson-databind"


class MavenTest(unittest.TestCase):
    def test_884_fiche_cve_sans_paquet_suit_l_alias_ghsa(self):
        """Les fiches CVE d'OSV (import NVD) n'ont pas d'entrée par paquet : la plage corrigée est dans
        la fiche GHSA alias. Sans suivre l'alias, jackson était classé « sans correctif » à tort."""
        osv = OsvDir({
            "CVE-2026-68497": {"aliases": ["GHSA-q4xh-88c3-wmh7"], "affected": [{"ranges": []}]},
            "GHSA-q4xh-88c3-wmh7": osv_doc(JACKSON, ("2.0.0", "2.21.6"), ("3.0.0", "3.1.6"), ecosystem="maven",
                                           aliases=["CVE-2026-68497"]),
        })
        ctx = context(osv, registry={f"maven:{JACKSON.replace(':', ':')}": ["2.21.5", "2.21.6", "2.21.7"]},
                      maven_deps={JACKSON: [("2.21.5", "compile")]})
        e = resolve_finding(finding("CVE-2026-68497", JACKSON, "2.21.5", ecosystem="maven"), ctx)
        self.assertEqual((e["fix_status"], e["target_version"], e["proof"]), ("fix_available", "2.21.6", "advisory"))
        self.assertEqual(e["aliases"], ["GHSA-q4xh-88c3-wmh7"])
        self.assertEqual(e["maven_scopes"], ["compile"])

    def test_avis_inconnu_heuristique_meme_branche_mineure(self):
        ctx = context(OsvDir(), registry={"maven:org.hibernate.orm:hibernate-core":
                                          ["7.4.5.Final", "7.4.12.Final", "7.5.0.Final", "8.0.0.Beta1"]})
        e = resolve_finding(finding("CVE-2026-77874", "org.hibernate.orm:hibernate-core", "7.4.5.Final",
                                    ecosystem="maven"), ctx)
        self.assertEqual((e["fix_status"], e["target_version"], e["proof"]), ("fix_available", "7.4.12.Final", "heuristic"))

    def test_avis_lu_sans_correctif_dans_la_branche(self):
        osv = OsvDir({"CVE-2026-10001": osv_doc("g:a", ("0", "2.0.0"), ecosystem="maven")})
        ctx = context(osv, registry={"maven:g:a": ["1.0.0", "1.0.1", "2.0.0"]})
        e = resolve_finding(finding("CVE-2026-10001", "g:a", "1.0.0", ecosystem="maven"), ctx)
        self.assertEqual(e["fix_status"], "no_fix_available")

    def test_version_corrigee_annoncee_non_publiee(self):
        osv = OsvDir({"CVE-2026-10001": osv_doc("g:a", ("0", "1.0.5"), ecosystem="maven")})
        ctx = context(osv, registry={"maven:g:a": ["1.0.0", "1.0.4"]})
        self.assertEqual(resolve_finding(finding("CVE-2026-10001", "g:a", "1.0.0", ecosystem="maven"), ctx)["fix_status"],
                         "no_fix_available")

    def test_garde_fou_version_installee_absente_de_la_liste(self):
        """#884/#886 : une liste qui ne contient pas la version installée est incohérente."""
        ctx = context(OsvDir(), registry={"maven:g:a": ["6.6.18", "7.0.2"]})
        e = resolve_finding(finding("CVE-2026-10001", "g:a", "7.4.5", ecosystem="maven"), ctx)
        self.assertEqual(e["fix_status"], "lookup_failed")

    def test_osv_et_maven_central_injoignables(self):
        ctx = context(OsvDir(errors=["CVE-2026-10001"]), registry={"maven:g:a": "error"})
        self.assertEqual(resolve_finding(finding("CVE-2026-10001", "g:a", "1.0.0", ecosystem="maven"), ctx)["fix_status"],
                         "lookup_failed")


class ImageTest(unittest.TestCase):
    KEYCLOAK = finding("CVE-2026-18963", "org.keycloak:keycloak-services", "26.6.2", ecosystem="maven",
                       image="keycloak", cvss=9.1, fixed_versions=["26.4.15", "26.6.6", "26.7.2"])

    def test_823_premiere_candidate_publiee_en_tag(self):
        """#812-#823 : 26.4.15 rétrograde, 26.6.6 pas un tag, 26.7.2 est la bonne cible."""
        ctx = context(OsvDir(), registry={"digest:keycloak:26.7.2": "sha256:" + "a" * 64},
                      image_refs={"keycloak": ("26.6.2", "sha256:" + "0" * 64)})
        e = resolve_finding(self.KEYCLOAK, ctx)
        self.assertEqual((e["fix_status"], e["target_version"]), ("fix_available", "26.7.2"))
        self.assertEqual(e["target_digest"], "sha256:" + "a" * 64)

    def test_meme_branche_d_abord(self):
        ctx = context(OsvDir(), registry={"digest:keycloak:26.6.6": "sha256:" + "b" * 64,
                                          "digest:keycloak:26.7.2": "sha256:" + "a" * 64},
                      image_refs={"keycloak": ("26.6.2", "sha256:" + "0" * 64)})
        self.assertEqual(resolve_finding(self.KEYCLOAK, ctx)["target_version"], "26.6.6")

    def test_jamais_inferieur_au_tag_courant(self):
        ctx = context(OsvDir(), registry={"digest:keycloak:26.6.6": "sha256:" + "b" * 64},
                      image_refs={"keycloak": ("26.7.2", "sha256:" + "0" * 64)})
        self.assertEqual(resolve_finding(self.KEYCLOAK, ctx)["fix_status"], "no_fix_available")

    def test_suffixe_de_variante_conserve(self):
        f = finding("CVE-2026-10001", "x:y", "1.31.3", ecosystem="maven", image="nginx", cvss=9.8,
                    fixed_versions=["1.31.4"])
        ctx = context(OsvDir(), registry={"digest:nginx:1.31.4-alpine": "sha256:" + "c" * 64},
                      image_refs={"nginx": ("1.31.3-alpine", "sha256:" + "0" * 64)})
        self.assertEqual(resolve_finding(f, ctx)["target_version"], "1.31.4-alpine")

    def test_895_version_de_bibliotheque_jamais_un_tag(self):
        f = finding("CVE-2026-8763", "org.bouncycastle:bcprov-jdk18on", "1.84", ecosystem="maven",
                    image="keycloak", cvss=9.1, fixed_versions=["1.85"])
        ctx = context(OsvDir(), image_refs={"keycloak": ("26.7.2", "sha256:" + "0" * 64)})
        self.assertEqual(resolve_finding(f, ctx)["fix_status"], "no_fix_available")

    def test_paquet_systeme_sans_tag_deduisible(self):
        f = finding("CVE-2026-32767", "libexpat", "2.7.4-r0", ecosystem="docker", image="nginx", cvss=9.8,
                    fixed_versions=["2.7.5-r0"])
        self.assertEqual(resolve_finding(f, context(OsvDir()))["fix_status"], "no_fix_available")


class PendingTest(unittest.TestCase):
    OWASP = """<suppressions>
    <suppress>
        <notes>[PENDING_UPSTREAM_FIX] CVE-2026-93749 : source-map-js 1.2.1 (CVSS 8.7 &lt; 9.0).</notes>
        <packageUrl regex="true">^pkg:npm/source-map-js@.*$</packageUrl>
        <cve>CVE-2026-93749</cve>
        <vulnerabilityName>GHSA-68fv-2mgg-jv7q</vulnerabilityName>
    </suppress>
</suppressions>"""

    def test_914_correctif_publie_toutes_les_formes_retirees(self):
        osv = OsvDir({"CVE-2026-93749": osv_doc("source-map-js", ("0", "1.2.2"), aliases=["GHSA-68fv-2mgg-jv7q"])})
        ctx = context(osv, registry={"npm:source-map-js": ["1.2.1", "1.2.2"]},
                      lock={"source-map-js": [("1.2.1", False)]})
        out = reverify_pending(ctx, self.OWASP, "")
        self.assertEqual(sorted(p["cve_id"] for p in out), ["CVE-2026-93749", "GHSA-68fv-2mgg-jv7q"])
        self.assertTrue(all(p["new_fixed_version"] == "1.2.2" for p in out))
        self.assertIn("< 9.0", out[0]["previous_note"])

    def test_pas_encore_de_correctif(self):
        osv = OsvDir({"CVE-2026-93749": osv_doc("source-map-js", ("0", "1.2.2"))})
        ctx = context(osv, registry={"npm:source-map-js": ["1.2.1"]}, lock={"source-map-js": [("1.2.1", False)]})
        self.assertEqual(reverify_pending(ctx, self.OWASP, ""), [])


if __name__ == "__main__":
    unittest.main()
