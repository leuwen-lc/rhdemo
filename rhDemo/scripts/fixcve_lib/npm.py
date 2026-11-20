"""npm : lecture de package-lock.json, règle `fixAvailable` de npm audit.

Chemins relatifs au répertoire `rhDemo/` (cwd de tous les scripts fixcve).
"""
import json
import os

from .common import load_json, run, version_key

NPM = "frontend/node/npm"
LOCKFILE = "frontend/package-lock.json"
PACKAGE_JSON = "frontend/package.json"


def run_npm_json(args, timeout=180):
    """Exécute npm et renvoie le JSON de stdout, ou None. `npm audit` sort en code 1 dès qu'il
    trouve une vulnérabilité : seul le contenu de stdout compte."""
    if not os.path.exists(NPM):
        return None
    _, out, _ = run([NPM, "--prefix", "frontend", *args], timeout=timeout)
    try:
        return json.loads(out)
    except ValueError:
        return None


def usable_audit(doc):
    """Un rapport `npm audit --json` valide porte `vulnerabilities` ; une erreur porte `error`."""
    if isinstance(doc, dict) and "error" not in doc and isinstance(doc.get("vulnerabilities"), dict):
        return doc
    return None


def lock_index(lock_doc):
    """{nom: [(version, dev_only_bool), ...]} pour chaque copie installée."""
    index = {}
    packages = (lock_doc or {}).get("packages") or {}
    for path, entry in packages.items():
        if "node_modules/" not in path or not isinstance(entry, dict):
            continue
        name = path.rsplit("node_modules/", 1)[1]
        index.setdefault(name, []).append((entry.get("version"), entry.get("dev") is True))
    return index


def load_lock_index(path=LOCKFILE):
    return lock_index(load_json(path))


def npm_dev_only(index, name, version):
    """True si TOUTES les copies installées de name@version sont `dev` ; None si introuvable."""
    copies = [dev for (v, dev) in index.get(name, []) if v == version]
    if not copies:
        return None
    return all(copies)


def all_copies_at_least(index, name, target):
    """Toutes les copies installées de `name` sont-elles >= target ? (False si aucune copie)."""
    versions = [v for (v, _) in index.get(name, [])]
    tk = version_key(target)
    if not versions or tk is None:
        return False
    return all(version_key(v) is not None and version_key(v) >= tk for v in versions)


def _name_version(node):
    """(nom, version) d'une entrée add/change de `npm audit fix --json` (formes variables selon npm)."""
    if not isinstance(node, dict):
        return None, None
    target = node.get("to", node)
    if isinstance(target, dict):
        return target.get("name"), target.get("version")
    return node.get("name"), None


def dry_run_versions(fix_doc):
    versions = {}
    if isinstance(fix_doc, dict):
        for key in ("change", "add"):
            for node in fix_doc.get(key) or []:
                name, version = _name_version(node)
                if name and version:
                    versions[name] = version
    return versions


def classify_audit(name, audit, get_dry_run_versions):
    """Règle « npm audit fait foi » -> (fix_status, target_version).

    Paquet absent / fixAvailable false / correctif majeur / correctif via un parent :
    no_fix_available. fixAvailable vrai : version lue dans le dry-run de `audit fix`
    (lookup_failed si muet, cas du build #914 rattrapé ensuite par l'avis OSV)."""
    if audit is None:
        return "lookup_failed", None
    vuln = audit["vulnerabilities"].get(name)
    if vuln is None:
        return "no_fix_available", None
    fix = vuln.get("fixAvailable")
    if fix is False or fix is None:
        return "no_fix_available", None
    if isinstance(fix, dict):
        if fix.get("isSemVerMajor") or fix.get("name") != name:
            return "no_fix_available", None
        version = fix.get("version")
        return ("fix_available", version) if version else ("lookup_failed", None)
    if fix is True:
        version = get_dry_run_versions().get(name)
        return ("fix_available", version) if version else ("lookup_failed", None)
    return "lookup_failed", None


def audit_still_reports(audit, name, ids):
    """npm audit signale-t-il encore `name` pour l'un des identifiants `ids` (CVE/GHSA) ?"""
    vuln = (audit or {}).get("vulnerabilities", {}).get(name)
    if not vuln:
        return False
    for via in vuln.get("via") or []:
        if isinstance(via, dict):
            url = via.get("url", "")
            if any(i and i in url for i in ids):
                return True
    return False
