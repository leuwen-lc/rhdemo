#!/usr/bin/env python3
"""Contrôle de cohérence de la documentation (wiki rhDemo/docs) — lecture seule.

Vérifie, sans rien modifier :
  - frontmatter (statut, verifie_le, sources) de chaque document, et existence des sources ;
  - présence de chaque document dans index.md, statut identique, liens de l'index valides ;
  - liens Markdown relatifs cassés (docs, documents hors docs/ référencés par l'index, README.md, CLAUDE.md) ;
  - frontmatter facultatif des documents hors docs/ : s'il est présent, mêmes contrôles qu'un doc de docs/ ;
  - noms de fichiers .md cités en texte qui n'existent plus (docs actifs et propositions) ;
  - sources modifiées dans git après la date `verifie_le` (docs actifs) ;
  - format et ordre chronologique de log.md ;
  - rangement : docs/ ne contient que des docs actifs ou journaux, docs/etudes/ que des
    historiques ou propositions.

Usage : python3 -I rhDemo/scripts/docs-lint.py [--root RACINE_DEPOT] [--json]
Code retour : 1 s'il y a au moins une ERREUR, 0 sinon (les AVERTISSEMENTS n'échouent pas).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

STATUTS = ("actif", "historique", "proposition", "journal")
OPERATIONS = ("ingest", "lint", "restructure", "query")
# Documents modifiés automatiquement par fixcve-auto : pas de frontmatter (voir index.md).
SANS_FRONTMATTER = {"fixcve-audit.md": "journal", "SECURITY_ADVISORIES.md": "journal"}
ETUDES = "etudes"  # sous-répertoire des études (migrations, refontes, propositions)
STATUTS_ETUDES = ("historique", "proposition")
DOCS_VIVANTS = ("actif", "proposition")  # statuts pour lesquels une référence morte est signalée
FRESHNESS_DAYS = 180
INDEX_MD = "index.md"  # catalogue des docs
LOG_MD = "log.md"  # journal des opérations sur les docs
EXCLUDED_DIRS = {"node_modules", "target", ".git", "dist", "node"}

RE_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
RE_MD_NAME = re.compile(r"(?<![\w/.-])([A-Za-z0-9][A-Za-z0-9_-]*\.md)\b")
RE_FENCE = re.compile(r"^(```|~~~)")
RE_LOG_ENTRY = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] (\w+) \| (.+)$")


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, where, message):
        item = {"niveau": level, "fichier": where, "message": message}
        if item not in self.items:
            self.items.append(item)

    def count(self, level):
        return sum(1 for i in self.items if i["niveau"] == level)


def strip_code(text):
    """Retire blocs de code et spans inline : leurs crochets et noms ne sont pas des références."""
    out, in_fence = [], False
    for line in text.splitlines():
        if RE_FENCE.match(line.strip()):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(out)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def parse_frontmatter(text):
    """Retourne (dict, erreur). Sous-ensemble YAML : clés scalaires et liste `sources`."""
    if not text.startswith("---\n"):
        return None, None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, "frontmatter non fermé"
    data, current = {}, None
    for raw in text[4:end].splitlines():
        if not raw.strip():
            continue
        m = re.match(r"^(\w+):\s*(.*)$", raw)
        if m:
            key, value = m.group(1), m.group(2).split(" #")[0].strip()
            if key == "sources":
                data[key] = [] if value in ("", "[]") else None
                current = key if value == "" else None
            else:
                data[key] = value
                current = None
        elif current == "sources" and raw.lstrip().startswith("- "):
            data.setdefault("sources", []).append(raw.lstrip()[2:].strip())
        else:
            return None, "ligne de frontmatter non reconnue : %r" % raw
    if data.get("sources") is None:
        data["sources"] = []
    return data, None


def git_last_date(root, path):
    try:
        out = subprocess.run(["git", "-C", root, "log", "-1", "--format=%cs", "--", path],
                             capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def all_md_names(root):
    names = set()
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        names.update(f for f in files if f.endswith(".md"))
    return names


def check_links(report, root, rel_path, text, level="ERREUR"):
    base = os.path.dirname(os.path.join(root, rel_path))
    for target in RE_LINK.findall(strip_code(text)):
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        path = target.split("#")[0]
        if path and not os.path.exists(os.path.normpath(os.path.join(base, path))):
            report.add(level, rel_path, "lien cassé : %s" % target)


def parse_index(docs, index_text):
    """Retourne {chemin normalisé: statut} d'après les lignes de tableau de l'index."""
    entries = {}
    for line in index_text.splitlines():
        m = re.match(r"^\|\s*\[[^\]]*\]\(([^)\s#]+)\)\s*\|\s*(\w+)\s*\|", line)
        if m:
            entries[os.path.normpath(os.path.join(docs, m.group(1)))] = m.group(2)
    return entries


def lint(root):
    report = Report()
    docs = os.path.join(root, "rhDemo", "docs")
    rel_docs = "rhDemo/docs/"
    today = datetime.date.today()
    md_names = all_md_names(root)
    statuts = {}

    names = sorted(f for f in os.listdir(docs) if f.endswith(".md") and f not in (INDEX_MD, LOG_MD))
    if os.path.isdir(os.path.join(docs, ETUDES)):
        names += sorted(ETUDES + "/" + f for f in os.listdir(os.path.join(docs, ETUDES)) if f.endswith(".md"))
    def check_doc(rel, text, name=None):
        """Contrôles d'un document ; name = chemin relatif à docs/ (None hors docs/). Retourne le statut."""
        statut = None
        fm, err = parse_frontmatter(text)
        if err:
            report.add("ERREUR", rel, err)
        if name in SANS_FRONTMATTER:
            if fm is not None:
                report.add("ERREUR", rel, "ne doit pas avoir de frontmatter (modifié automatiquement par fixcve-auto)")
            statut = SANS_FRONTMATTER[name]
        elif fm is None:
            # Hors docs/, le frontmatter est facultatif : seul le statut de l'index s'applique.
            if not err and name is not None:
                report.add("ERREUR", rel, "frontmatter absent")
        else:
            s = fm.get("statut", "")
            if s not in STATUTS:
                report.add("ERREUR", rel, "statut invalide : %r (attendu : %s)" % (s, ", ".join(STATUTS)))
            else:
                statut = s
            verifie = fm.get("verifie_le", "")
            try:
                verifie_date = datetime.date.fromisoformat(verifie)
            except ValueError:
                report.add("ERREUR", rel, "verifie_le invalide : %r (attendu AAAA-MM-JJ)" % verifie)
                verifie_date = None
            if "sources" not in fm:
                report.add("ERREUR", rel, "champ sources absent")
            for src in fm.get("sources", []):
                if not os.path.exists(os.path.join(root, src)):
                    report.add("ERREUR", rel, "source inexistante : %s" % src)
            if s == "actif" and verifie_date:
                if (today - verifie_date).days > FRESHNESS_DAYS:
                    report.add("AVERTISSEMENT", rel, "non revérifié depuis %s (plus de %d jours)" % (verifie, FRESHNESS_DAYS))
                for src in fm.get("sources", []):
                    last = git_last_date(root, src)
                    if last and last > verifie:
                        report.add("AVERTISSEMENT", rel, "source modifiée le %s après verifie_le (%s) : %s" % (last, verifie, src))
        if name is not None and statut and name.startswith(ETUDES + "/") != (statut in STATUTS_ETUDES):
            report.add("ERREUR", rel, "statut %s : le document doit être dans %s" % (
                statut, rel_docs + ETUDES + "/" if statut in STATUTS_ETUDES else rel_docs))
        # Un doc historique ou journal n'est pas réécrit : son lien mort est signalé sans échouer.
        check_links(report, root, rel, text,
                    "ERREUR" if statut in DOCS_VIVANTS + (None,) else "AVERTISSEMENT")
        if statut in DOCS_VIVANTS:
            for ref in sorted(set(RE_MD_NAME.findall(strip_code(text)))):
                if ref not in md_names:
                    report.add("AVERTISSEMENT", rel, "fichier .md cité mais introuvable dans le dépôt : %s" % ref)
        return statut

    for name in names + [INDEX_MD, LOG_MD]:
        s = check_doc(rel_docs + name, read(os.path.join(docs, name)), name)
        if s:
            statuts[name] = s

    # --- index
    index = parse_index(docs, read(os.path.join(docs, INDEX_MD)))
    for name in names:
        key = os.path.normpath(os.path.join(docs, name))
        if key not in index:
            report.add("ERREUR", rel_docs + INDEX_MD, "document absent de l'index : %s" % name)
        elif name in statuts and index[key] != statuts[name]:
            report.add("ERREUR", rel_docs + INDEX_MD,
                       "statut de %s : index=%s, document=%s" % (name, index[key], statuts[name]))
    checked = set()
    for key in sorted(index):
        rel = os.path.relpath(key, root)
        if not os.path.exists(key):
            report.add("ERREUR", rel_docs + INDEX_MD, "entrée sans fichier : %s" % rel)
        elif not key.startswith(os.path.normpath(docs) + os.sep) and key.endswith(".md"):
            # Document hors docs/ référencé par l'index : mêmes contrôles, frontmatter facultatif.
            checked.add(rel)
            s = check_doc(rel, read(key))
            if s and s != index[key]:
                report.add("ERREUR", rel_docs + INDEX_MD,
                           "statut de %s : index=%s, document=%s" % (rel, index[key], s))
    for rel in ("README.md", "CLAUDE.md"):
        if rel not in checked and os.path.exists(os.path.join(root, rel)):
            check_links(report, root, rel, read(os.path.join(root, rel)))

    # --- journal
    last_date = None
    for n, line in enumerate(read(os.path.join(docs, LOG_MD)).splitlines(), 1):
        if not line.startswith("## ["):
            continue
        m = RE_LOG_ENTRY.match(line)
        if not m:
            report.add("ERREUR", rel_docs + LOG_MD, "ligne %d : entrée au mauvais format : %s" % (n, line[:60]))
            continue
        if m.group(2) not in OPERATIONS:
            report.add("ERREUR", rel_docs + LOG_MD, "ligne %d : opération inconnue : %s" % (n, m.group(2)))
        if last_date and m.group(1) < last_date:
            report.add("ERREUR", rel_docs + LOG_MD, "ligne %d : entrée antérieure à la précédente (%s < %s)" % (n, m.group(1), last_date))
        last_date = m.group(1)
    return report


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=os.path.abspath(os.path.join(here, "..", "..")),
                        help="racine du dépôt (défaut : déduite de l'emplacement du script)")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    args = parser.parse_args(argv)
    report = lint(os.path.abspath(args.root))
    if args.json:
        print(json.dumps(report.items, ensure_ascii=False, indent=2))
    else:
        for level in ("ERREUR", "AVERTISSEMENT"):
            for item in (i for i in report.items if i["niveau"] == level):
                print("%-13s %s : %s" % (level, item["fichier"], item["message"]))
        print("\n%d erreur(s), %d avertissement(s)" % (report.count("ERREUR"), report.count("AVERTISSEMENT")))
    return 1 if report.count("ERREUR") else 0


if __name__ == "__main__":
    sys.exit(main())
