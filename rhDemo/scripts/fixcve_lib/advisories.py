"""Entrée de docs/SECURITY_ADVISORIES.md et justifications des suppressions (modèles fixes).

Les textes sont construits à partir des champs structurés du plan : aucune rédaction libre,
donc aucun contenu externe (titre de CVE) recopié dans un fichier versionné.
"""
import datetime

ADVISORIES_FILE = "docs/SECURITY_ADVISORIES.md"

_CRITERION_TEXT = {
    "A:npm_dev_only": "toutes les copies installées sont marquées dev=true dans frontend/package-lock.json : "
                      "chaîne de build uniquement, jamais dans le bundle de production",
    "A:local_vector": "vecteur CVSS local ou physique (AV:L/AV:P) : non exploitable à distance",
    "A:decision_humaine": "décision humaine (skill /fixcve), justification détaillée ci-dessous",
}


def criterion_text(criterion):
    if criterion in _CRITERION_TEXT:
        return _CRITERION_TEXT[criterion]
    if criterion and criterion.startswith("A:maven_scope_"):
        return f"portée Maven {criterion[len('A:maven_scope_'):]} uniquement : absent de l'artefact livré"
    return ""


def suppression_note(action, build):
    """Texte de <notes> (OWASP) ou de `statement` (Trivy)."""
    ids = " / ".join(action["ids"])
    head = f"{ids} : {action['package_name']} {action['installed_version']} (CVSS {action['cvss']})."
    if action["action"] == "suppress_permanent":
        body = f"Critère A ({action['criterion']}) : {criterion_text(action['criterion'])}. Aucun correctif publié dans la branche installée."
    else:
        body = ("Critère B : aucun correctif publié dans la branche installée (avis OSV + registre), "
                "CVSS < 9.0 ; acceptation temporaire revérifiée à chaque cycle.")
        head = "[PENDING_UPSTREAM_FIX] " + head
    return f"{head} {body} Remédiation automatique build #{build}."


def _bullets(items):
    return "\n".join(f"  - {i}" for i in items)


def section(build, stage, applied, accepted, blocked, resolved, today=None):
    """Section Markdown d'un cycle. Chaque liste contient des actions du plan (déjà appliquées)."""
    today = today or datetime.date.today().isoformat()
    tool = "Trivy" if stage == "trivy" else "OWASP Dependency-Check"
    packages = sorted({a["package_name"] for a in applied + accepted + blocked} |
                      {p["package"] for p in resolved})
    title = ", ".join(packages[:4]) + (" ..." if len(packages) > 4 else "")
    lines = [f"## {title} (build #{build})", "",
             f"- **Date** : {today} — **Outil** : {tool} — **Source** : `fixcve-auto` (procédure déterministe)"]
    if applied:
        lines.append("- **Remédiation automatique** :")
        by_pkg = {}
        for a in applied:
            entry = by_pkg.setdefault(a["package_name"], {"a": a, "ids": set(), "cvss": 0.0})
            entry["ids"].update(a["ids"])
            entry["cvss"] = max(entry["cvss"], a["cvss"])
        lines.append(_bullets(
            f"`{name}` {e['a']['installed_version']} → {e['a'].get('applied_version') or e['a']['target_version']} "
            f"({', '.join(sorted(e['ids']))}, CVSS {e['cvss']})" for name, e in sorted(by_pkg.items())))
    if resolved:
        lines.append("- **Remédiation automatique — clôture d'acceptations temporaires** :")
        lines.append(_bullets(f"`{p['package']}` {p['cve_id']} : correctif publié ({p['new_fixed_version']}), "
                              "suppression retirée" for p in resolved))
    perm = [a for a in accepted if a["action"] == "suppress_permanent"]
    temp = [a for a in accepted if a["action"] == "suppress_temporary"]
    if perm:
        lines.append("- **Remédiation automatique — risque accepté (permanent)** :")
        lines.append(_bullets(f"`{a['package_name']}` {a['installed_version']} ({', '.join(a['ids'])}, "
                              f"CVSS {a['cvss']}) — critère A : {criterion_text(a['criterion'])}" for a in perm))
    if temp:
        lines.append("- **Remédiation automatique — risque accepté (temporaire, en attente de correctif upstream)** :")
        lines.append(_bullets(f"`{a['package_name']}` {a['installed_version']} ({', '.join(a['ids'])}, "
                              f"CVSS {a['cvss']}) — critère B, `[PENDING_UPSTREAM_FIX]`" for a in temp))
    if blocked:
        lines.append("- **Non traité (bloqué, revue humaine requise)** :")
        lines.append(_bullets(f"`{a['package_name']}` {a['installed_version']} ({', '.join(a['ids'])}, "
                              f"CVSS {a['cvss']}) — {a['reason']}" for a in blocked))
    return "\n".join(lines) + "\n"


def insert_section(doc_text, section_text):
    """Insère la section en tête (après le premier séparateur `---` du document)."""
    marker = "\n---\n"
    idx = doc_text.find(marker)
    if idx < 0:
        return doc_text.rstrip("\n") + "\n\n---\n\n" + section_text
    pos = idx + len(marker)
    return doc_text[:pos] + "\n" + section_text + "\n---\n" + doc_text[pos:]
