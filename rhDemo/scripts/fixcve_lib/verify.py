"""Étape 6 — vérification locale avant tout push, avec les vrais outils.

  1. Syntaxe : pom.xml, owasp-suppressions.xml, .trivyignore.yaml, package*.json.
  2. npm : chaque montée appliquée est effective (toutes les copies >= cible) et `npm audit`
     ne signale plus la faille pour ce paquet.
  3. OWASP Dependency-Check (stage owasp, clé NVD disponible) : rescan du projet ; aucun finding
     traité ne doit subsister, aucun nouveau finding sur un paquet monté par ce cycle.
     OSS Index désactivé (quota partagé avec RHDemo-CI) ; clé NVD lue dans l'environnement par le
     plugin (`nvdApiKeyEnvironmentVariable`), jamais en ligne de commande.

-> {"ok", "failed_upgrades": [clés], "errors": [...], "incomplete": [...]}.
Une montée en échec n'invalide que sa clé (le poller la fait basculer en « sans correctif » et
réapplique) ; une erreur de syntaxe ou une suppression sans effet invalide le cycle.
"""
import json
import os
import xml.etree.ElementTree as ET

from . import npm as npm_mod
from .common import load_json, run

ODC_REPORT = "target/dependency-check-report.json"
CVSS_THRESHOLD = 7.0


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
    upgrades = [a for a in actions if a["action"] == "upgrade" and a["ecosystem"] == "npm" and a["image"] == "rhdemo-app"]
    if not upgrades:
        return failed
    index = npm_mod.load_lock_index()
    audit = npm_mod.usable_audit(audit_doc if audit_doc is not None else npm_mod.run_npm_json(["audit", "--json"]))
    for a in upgrades:
        if not npm_mod.all_copies_at_least(index, a["package_name"], a["target_version"]):
            failed.append(key_of(a))
        elif audit is not None and npm_mod.audit_still_reports(audit, a["package_name"], a["ids"]):
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
    """-> (failed_upgrades, errors) : findings traités encore présents, régressions sur paquets montés."""
    remaining = odc_findings(report)
    failed, errors = [], []
    upgraded_packages = {a["package_name"] for a in actions if a["action"] == "upgrade"}
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
    for vid, pkg in sorted(remaining - known):
        if pkg in upgraded_packages:
            errors.append(f"regression : {vid} sur {pkg} apparu apres la montee")
    return failed, errors


def run_odc():
    """Rescan Dependency-Check local -> rapport JSON, ou None si impossible (raison)."""
    if not os.environ.get("NVD_API_KEY"):
        return None, "cle_nvd_absente"
    code, _, err = run(["./mvnw", "-q", "-B", "org.owasp:dependency-check-maven:check",
                        "-DnvdApiKeyEnvironmentVariable=NVD_API_KEY", "-DossIndexAnalyzerEnabled=false",
                        "-DfailBuildOnCVSS=11"], timeout=3600)
    report = load_json(ODC_REPORT)
    if report is None:
        return None, f"rapport_odc_absent (code {code} : {err.strip()[-200:]})"
    return report, None


def verify(apply_result, detected, stage, audit_doc=None, odc_report=None, run_odc_scan=True):
    actions = apply_result["actions"]
    errors = check_syntax(apply_result["changed_files"])
    failed = check_npm(actions, audit_doc)
    incomplete = []
    if stage == "owasp" and not errors:
        report, why = (odc_report, None) if odc_report is not None else (run_odc() if run_odc_scan else (None, "desactive"))
        if report is None:
            incomplete.append(f"dependency_check_local:{why}")
        else:
            f2, e2 = compare_odc(actions, detected, report)
            failed += [k for k in f2 if k not in failed]
            errors += e2
    if stage == "trivy" and any(a["action"] == "upgrade" for a in actions):
        incomplete.append("trivy_local:non_disponible (preuve par le build CI)")
    return {"ok": not errors and not failed, "failed_upgrades": failed, "errors": errors, "incomplete": incomplete}
