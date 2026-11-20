"""Outils communs des tests fixcve (hors réseau : OSV, registres et npm sont injectés)."""
import atexit
import json
import os
import shutil
import sys
import tempfile

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
sys.path.insert(0, SCRIPTS)

from fixcve_lib.osv import OsvClient  # noqa: E402
from fixcve_lib.registry import Registry  # noqa: E402
from fixcve_lib.resolve import Context  # noqa: E402


def osv_doc(name, *ranges, ecosystem="npm", vid=None, aliases=()):
    """Avis OSV minimal : une entrée `affected` par plage (introduced, fixed)."""
    osv_ecosystem = {"npm": "npm", "maven": "Maven"}[ecosystem]
    doc = {"affected": [{"package": {"name": name, "ecosystem": osv_ecosystem},
                         "ranges": [{"type": "SEMVER" if ecosystem == "npm" else "ECOSYSTEM",
                                     "events": [{"introduced": i}, {"fixed": f}]}]}
                        for (i, f) in ranges]}
    if vid:
        doc["id"] = vid
    if aliases:
        doc["aliases"] = list(aliases)
    return doc


def audit(**vulns):
    return {"auditReportVersion": 2, "vulnerabilities": {n: {"name": n, "fixAvailable": fa} for n, fa in vulns.items()}}


def finding(fid, pkg, version, ecosystem="npm", image="rhdemo-app", cvss=7.5, vector=None, **extra):
    f = {"finding_id": fid, "package_name": pkg, "installed_version": version, "ecosystem": ecosystem,
         "image": image, "cvss": cvss,
         "cvss_vector": vector or "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"}
    f.update(extra)
    return f


class OsvDir:
    """Dossier temporaire d'avis OSV : <id>.json, <id>.error, query-*.json."""

    def __init__(self, docs=None, errors=(), queries=None):
        self.path = tempfile.mkdtemp(prefix="fixcve-osv-")
        atexit.register(shutil.rmtree, self.path, True)
        for vid, doc in (docs or {}).items():
            with open(os.path.join(self.path, vid + ".json"), "w") as fh:
                json.dump(dict(doc, id=doc.get("id", vid)), fh)
        for vid in errors:
            open(os.path.join(self.path, vid + ".error"), "w").close()
        for name, doc in (queries or {}).items():
            with open(os.path.join(self.path, f"query-{name}.json"), "w") as fh:
                json.dump(doc, fh)

    def client(self):
        return OsvClient(self.path)


def context(osv_dir, registry=None, audit_doc=None, fix_doc=None, lock=None, maven_deps=None, image_refs=None):
    return Context(osv=osv_dir.client(), registry=Registry(registry or {}),
                   audit=lambda: audit_doc, dry_run=lambda: fix_doc or {"change": [], "add": []},
                   lock_index=lock or {}, maven_deps=maven_deps or {}, image_refs=image_refs or {})


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)
