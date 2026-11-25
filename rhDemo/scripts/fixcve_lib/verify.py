"""Étape 6 — vérification locale avant tout push, avec les vrais outils.

  1. Syntaxe : pom.xml, owasp-suppressions.xml, .trivyignore.yaml, package*.json.
  2. npm : chaque montée appliquée est effective (toutes les copies >= cible) et `npm audit`
     ne signale plus la faille pour ce paquet.
  3. OWASP Dependency-Check (stage owasp, clé NVD disponible) : rescan du projet ; aucun finding
     traité ne doit subsister, aucun nouveau finding sur un paquet monté par ce cycle.
     OSS Index activé si son compte est dans l'environnement (OSSINDEX_USER / OSSINDEX_PASSWORD,
     lus par .mvn/ci-settings.xml comme dans RHDemo-CI) : sans lui, une faille que seul OSS Index
     relie à la version passe jusqu'à la CI (Tomcat 11.0.27, builds #1102 à #1107). Cache OSS
     Index de 7 jours partagé avec la CI : les requêtes sont le plus souvent déjà en cache.
     Clé NVD lue dans l'environnement par le plugin (`nvdApiKeyEnvironmentVariable`), jamais en
     ligne de commande. La base NVD est celle
     de RHDemo-CI (volume Maven monté par l'agent Jenkins, jamais deux builds à la fois) : seul le
     delta depuis le dernier build CI est téléchargé. Un rapport antérieur au scan n'est jamais relu.

-> {"ok", "failed_upgrades": [clés], "new_findings": [findings], "errors": [...], "incomplete": [...]}.
Une montée en échec n'invalide que sa clé (le poller la fait basculer en « sans correctif » et
réapplique) ; une erreur de syntaxe ou une suppression sans effet invalide le cycle.
`new_findings` : CVE >= seuil absentes du build d'origine, sur n'importe quel paquet (une montée
du parent ou un nettoyage change des versions par ricochet : Tomcat 11.0.27 et CVE-2026-116830,
build #1102). Format de detected.json : le poller les ajoute au cycle et le retraite.
"""
import json
import os
import re
import xml.etree.ElementTree as ET

from . import npm as npm_mod
from .common import load_json, run
from .rules import CVSS_FAIL_THRESHOLD as CVSS_THRESHOLD, PROJECT_IMAGE, kind_name, kind_of

ODC_REPORT = "target/dependency-check-report.json"


def check_syntax(changed):
    errors = []
    for path in changed:
        if not os.path.exists(path):
            continue
        try:
            if path.endswith(".xml"):
                ET.parse(path)  # NOSONAR fichiers du dépôt, jamais du contenu externe
            elif path.endswith((".yaml", ".yml")):
                import yaml
                with open(path, encoding="utf-8") as fh:
                    yaml.safe_load(fh)
            elif path.endswith(".json"):
                with open(path, encoding="utf-8") as fh:
                    json.load(fh)
        except Exception as e:  # noqa: BLE001 - toute erreur de lecture invalide le fichier
            errors.append(f"{path} : syntaxe invalide ({type(e).__name__}: {str(e)[:150]})")
    return errors


def key_of(action):
    return f"{action['finding_id']}|{action['package_name']}"


def check_npm(actions, audit_doc=None):
    """Montées npm appliquées : effectives dans le lockfile et absentes de npm audit."""
    failed = []
    upgrades = [a for a in actions if a["action"] == "upgrade" and kind_of(a).fix_target == "npm"]
    if not upgrades:
        return failed
    index = npm_mod.load_lock_index()
    audit = npm_mod.usable_audit(audit_doc if audit_doc is not None else npm_mod.run_npm_json(["audit", "--json"]))
    for a in upgrades:
        if (not npm_mod.all_copies_at_least(index, a["package_name"], a["target_version"])
                or (audit is not None and npm_mod.audit_still_reports(audit, a["package_name"], a["ids"]))):
            failed.append(key_of(a))
    return failed


def _odc_package_name(dep):
    for pkg in dep.get("packages") or []:
        pid = pkg.get("id", "")
        if pid.startswith("pkg:maven/"):
            coords = pid[len("pkg:maven/"):].split("@")[0]
            group, _, artifact = coords.rpartition("/")
            return f"{group}:{artifact}"
        if pid.startswith("pkg:npm/"):
            return pid[len("pkg:npm/"):].rsplit("@", 1)[0].replace("%40", "@").replace("%2F", "/")
    return None


def _score(vuln):
    scores = [(vuln.get(k) or {}).get("baseScore") for k in ("cvssv3", "cvssv4")]
    scores = [s for s in scores if isinstance(s, (int, float))]
    return max(scores) if scores else 0.0


_ID_RE = re.compile(r"^(CVE-\d{4}-\d{4,}|GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4})$")
_VECTOR_RE = re.compile(r"^CVSS:[34]\.[0-9](/[A-Z]{1,3}:[A-Z])+$")
_PKG_ID_RE = re.compile(r"^pkg:(maven|npm)/(.+)@([A-Za-z0-9.:+~_-]+)$")


def _vector(vuln):
    for k in ("cvssv3", "cvssv4"):
        v = (vuln.get(k) or {}).get("vectorString") or ""
        if v and not v.startswith("CVSS:"):
            v = ("CVSS:3.1/" if k == "cvssv3" else "CVSS:4.0/") + v
        if _VECTOR_RE.match(v):
            return v
    return None


def _title(vuln):
    text = re.sub(r"\s+", " ", vuln.get("description") or vuln.get("name") or "").strip()
    return "".join(c for c in text if 0x20 <= ord(c) <= 0x7E)[:200]


def odc_new_findings(report, known):
    """Findings >= seuil du rapport ODC absents de `known` {(id, paquet)}, au format detected.json."""
    out, seen = [], set()
    for dep in (report or {}).get("dependencies") or []:
        name = _odc_package_name(dep)
        pid = next((p.get("id", "") for p in dep.get("packages") or [] if _PKG_ID_RE.match(p.get("id", ""))), "")
        m = _PKG_ID_RE.match(pid)
        if not name or not m:
            continue
        for vuln in dep.get("vulnerabilities") or []:
            vid = vuln.get("name", "")
            if _score(vuln) < CVSS_THRESHOLD or not _ID_RE.match(vid) or (vid, name) in known or (vid, name) in seen:
                continue
            seen.add((vid, name))
            out.append({"finding_id": vid, "source": "owasp", "ecosystem": m.group(1), "image": PROJECT_IMAGE,
                        "component_kind": kind_name(m.group(1), PROJECT_IMAGE),
                        "package_name": name, "installed_version": m.group(3), "cvss": round(_score(vuln), 1),
                        "cvss_vector": _vector(vuln), "fixed_version_hint": None, "fixed_versions": [],
                        "title": _title(vuln)})
    return out


def odc_findings(report):
    """{(nom de vulnérabilité, paquet)} non supprimés et >= seuil, depuis le rapport JSON d'ODC."""
    found = set()
    for dep in (report or {}).get("dependencies") or []:
        name = _odc_package_name(dep)
        if not name:
            continue
        for vuln in dep.get("vulnerabilities") or []:
            if _score(vuln) >= CVSS_THRESHOLD:
                found.add((vuln.get("name", ""), name))
    return found


def compare_odc(actions, detected, report):
    """-> (failed_upgrades, errors, new_findings) : findings traités encore présents, findings
    nouveaux (tout paquet)."""
    remaining = odc_findings(report)
    failed, errors = [], []
    known = {(i, f["package_name"]) for f in detected.get("findings", [])
             for i in [f["finding_id"], *f.get("advisory_aliases", [])]}
    for a in actions:
        known.update((i, a["package_name"]) for i in a["ids"])
    for a in actions:
        still = any((i, a["package_name"]) in remaining for i in a["ids"])
        if not still:
            continue
        if a["action"] == "upgrade":
            failed.append(key_of(a))
        elif a["action"] in ("suppress_permanent", "suppress_temporary"):
            errors.append(f"suppression sans effet : {a['package_name']} {', '.join(a['ids'])}")
    return failed, errors, odc_new_findings(report, known)


CI_SETTINGS = ".mvn/ci-settings.xml"


def odc_source_args():
    """OSS Index comme en CI (compte dans l'environnement, jamais en argument), sinon désactivé."""
    if os.environ.get("OSSINDEX_USER") and os.environ.get("OSSINDEX_PASSWORD") and os.path.exists(CI_SETTINGS):
        return ["-s", CI_SETTINGS, "-DossIndexServerId=ossindex"]
    return ["-DossIndexAnalyzerEnabled=false"]


def run_odc():
    """Rescan Dependency-Check local -> rapport JSON, ou None si impossible (raison)."""
    if not os.environ.get("NVD_API_KEY"):
        return None, "cle_nvd_absente"
    if odc_source_args()[0] != "-s":
        print("info: rescan local sans OSS Index (compte absent) : moins complet que RHDemo-CI")
    # Un rapport resté d'un scan antérieur serait relu comme s'il était frais : on le supprime.
    if os.path.exists(ODC_REPORT):
        os.remove(ODC_REPORT)
    code, _, err = run(["./mvnw", "-q", "-B", *odc_source_args(), "org.owasp:dependency-check-maven:check",
                        "-DnvdApiKeyEnvironmentVariable=NVD_API_KEY", "-DfailBuildOnCVSS=11"], timeout=3600)
    report = load_json(ODC_REPORT)
    if report is None:
        return None, f"rapport_odc_absent (code {code} : {err.strip()[-200:]})"
    return report, None


def verify(apply_result, detected, stage, audit_doc=None, odc_report=None, run_odc_scan=True):
    actions = apply_result["actions"]
    errors = check_syntax(apply_result["changed_files"])
    failed = check_npm(actions, audit_doc)
    incomplete, new = [], []
    if stage == "owasp" and not errors:
        if odc_report is not None:
            report, why = odc_report, None
        elif run_odc_scan:
            report, why = run_odc()
        else:
            report, why = None, "desactive"
        if report is None:
            incomplete.append(f"dependency_check_local:{why}")
        else:
            f2, e2, new = compare_odc(actions, detected, report)
            failed += [k for k in f2 if k not in failed]
            errors += e2
    if stage == "trivy" and any(a["action"] == "upgrade" for a in actions):
        incomplete.append("trivy_local:non_disponible (preuve par le build CI)")
    return {"ok": not errors and not failed and not new, "failed_upgrades": failed, "new_findings": new,
            "errors": errors, "incomplete": incomplete}
