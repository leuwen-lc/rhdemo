"""Tests de docs-lint.py sur un mini-dépôt temporaire (hors réseau, hors git)."""
import importlib.util
import os
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("docs_lint", os.path.join(HERE, "..", "docs-lint.py"))
docs_lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs_lint)

FM = "---\nstatut: %s\nverifie_le: 2026-10-22\nsources:%s\n---\n\n"
INDEX = """---
statut: actif
verifie_le: 2026-10-22
sources: []
---

| Document | Statut | Résumé |
| --- | --- | --- |
%s
"""
LOG = "---\nstatut: journal\nverifie_le: 2026-10-22\nsources: []\n---\n\n%s\n"


class DocsLintTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.docs = os.path.join(self.root, "rhDemo", "docs")
        os.makedirs(self.docs)
        open(os.path.join(self.root, "pom.xml"), "w").close()

    def write(self, name, content):
        with open(os.path.join(self.docs, name), "w", encoding="utf-8") as f:
            f.write(content)

    def messages(self, level=None):
        return [i["message"] for i in docs_lint.lint(self.root).items if level in (None, i["niveau"])]

    def base(self, rows="| [a.md](a.md) | actif | A |", log="## [2026-10-22] lint | x", a_body="Texte."):
        self.write("a.md", FM % ("actif", "\n  - pom.xml") + a_body + "\n")
        self.write("index.md", INDEX % rows)
        self.write("log.md", LOG % log)

    def test_depot_sain(self):
        self.base()
        self.assertEqual(self.messages(), [])

    def test_statut_invalide_et_source_inexistante(self):
        self.base()
        self.write("a.md", FM % ("bizarre", "\n  - nope.xml") + "Texte.\n")
        msgs = self.messages("ERREUR")
        self.assertTrue(any("statut invalide" in m for m in msgs))
        self.assertTrue(any("source inexistante : nope.xml" in m for m in msgs))

    def test_document_absent_de_l_index_et_statut_divergent(self):
        self.base(rows="| [a.md](a.md) | historique | A |")
        self.write("b.md", FM % ("actif", " []") + "B.\n")
        msgs = self.messages("ERREUR")
        self.assertTrue(any("statut de a.md : index=historique, document=actif" in m for m in msgs))
        self.assertTrue(any("absent de l'index : b.md" in m for m in msgs))

    def test_lien_casse_hors_blocs_de_code(self):
        self.base(a_body="[ok](index.md) [mort](absent.md)\n```\n[code](faux.md)\n```\n`[inline](faux2.md)`")
        msgs = self.messages("ERREUR")
        self.assertEqual([m for m in msgs if "lien cassé" in m], ["lien cassé : absent.md"])

    def test_lien_mort_dans_doc_historique_est_un_avertissement(self):
        self.base(rows="| [a.md](a.md) | historique | A |")
        self.write("a.md", FM % ("historique", " []") + "[mort](absent.md)\n")
        self.assertEqual(self.messages("ERREUR"), [])
        self.assertIn("lien cassé : absent.md", self.messages("AVERTISSEMENT"))

    def test_reference_md_introuvable(self):
        self.base(a_body="Voir ANCIEN_NOM.md et index.md.")
        self.assertEqual(self.messages("AVERTISSEMENT"),
                         ["fichier .md cité mais introuvable dans le dépôt : ANCIEN_NOM.md"])

    def test_fichiers_sans_frontmatter_attendus(self):
        self.base(rows="| [a.md](a.md) | actif | A |\n| [fixcve-audit.md](fixcve-audit.md) | journal | J |")
        self.write("fixcve-audit.md", "# Journal généré\n")
        self.assertEqual(self.messages("ERREUR"), [])
        self.write("fixcve-audit.md", FM % ("journal", " []") + "# Journal\n")
        self.assertTrue(any("ne doit pas avoir de frontmatter" in m for m in self.messages("ERREUR")))

    def test_journal_format_ordre_et_operation(self):
        self.base(log="## [2026-10-22] lint | ok\n## [2026-10-21] lint | trop tôt\n"
                      "## [2026-10-23] inconnu | op\n## [2026-10-24] mal formé")
        msgs = self.messages("ERREUR")
        self.assertTrue(any("antérieure à la précédente" in m for m in msgs))
        self.assertTrue(any("opération inconnue : inconnu" in m for m in msgs))
        self.assertTrue(any("mauvais format" in m for m in msgs))


if __name__ == "__main__":
    unittest.main()
