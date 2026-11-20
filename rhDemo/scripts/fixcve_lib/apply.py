"""Étape 5 — application déterministe du plan (remplace la phase 3 /fixcve-auto-apply).

Modifie uniquement les fichiers de remédiation (pom.xml, frontend/package*.json, références
d'image, owasp-suppressions.xml, .trivyignore.yaml, docs/SECURITY_ADVISORIES.md). Ne touche ni à
git ni au journal versionné : les événements d'audit sont écrits dans le dossier de cycle et
ajoutés au journal par le poller, après la vérification locale (étape 6).
"""
import datetime
import os

from . import advisories, edits, suppressions
from .common import clean_text
from .policy import downgrade_failed_upgrade


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def key_of(action):
    return f"{action['finding_id']}|{action['package_name']}"


class Applier:
    def __init__(self, plan, registry, image_refs, downgrade=(), log=None):
        self.plan = plan
        self.build = plan["jenkins_build"]
        self.stage = plan["stage"]
        self.registry = registry
        self.image_refs = image_refs
        self.downgrade = set(downgrade)
        self.log = log or (lambda msg: None)
        self.events = []
        self.baseline_pom = _read(edits.POM)
        self.changed = set()
        self.final = []
        self.resolved = []

    # --- montées de version --------------------------------------------------------------
    def _upgrade_group(self, group):
        a0 = group[0]
        if a0["image"] != "rhdemo-app":
            current = self.image_refs.get(a0["image"])
            if current is None:
                return "failed", f"reference d'image {a0['image']} introuvable dans Jenkinsfile-CI"
            return edits.image_upgrade(a0["image"], current, a0["target_version"], a0["target_digest"])
        ids = sorted({i for a in group for i in a["ids"]})
        if a0["ecosystem"] == "npm":
            return edits.npm_upgrade(a0["package_name"], a0["target_version"])
        return edits.maven_upgrade(a0["package_name"], a0["installed_version"], a0["target_version"],
                                   ids, self.registry, baseline_pom=self.baseline_pom)

    def _apply_upgrades(self, actions):
        groups = {}
        for a in actions:
            if a["action"] == "upgrade":
                gkey = a["image"] if a["image"] != "rhdemo-app" else a["package_name"]
                groups.setdefault(gkey, []).append(a)
        out = []
        for a in actions:
            if a["action"] != "upgrade":
                out.append(a)
        for gkey, group in groups.items():
            status, detail = self._upgrade_group(group)
            self.log(f"montee {gkey} : {status} - {detail}")
            for a in group:
                if status == "applied":
                    version = edits.installed_npm_version(a["package_name"]) if (
                        a["ecosystem"] == "npm" and a["image"] == "rhdemo-app") else a["target_version"]
                    out.append(dict(a, applied_detail=detail, applied_version=version))
                    self._touch_for(a)
                elif status == "already":
                    out.append(dict(a, action="already", outcome_code="already_fixed", reason=detail))
                else:
                    out.append(downgrade_failed_upgrade(dict(a, reason=detail)))
        return out

    def _touch_for(self, action):
        if action["image"] != "rhdemo-app":
            self.changed.update(p for p in edits.IMAGE_FILES if os.path.exists(p))
        elif action["ecosystem"] == "npm":
            self.changed.update(["frontend/package.json", "frontend/package-lock.json"])
        else:
            self.changed.add(edits.POM)

    # --- suppressions --------------------------------------------------------------------
    def _apply_suppressions(self, actions):
        owasp = _read(suppressions.OWASP_FILE)
        trivy = _read(suppressions.TRIVY_FILE)
        for a in actions:
            if a["action"] not in ("suppress_permanent", "suppress_temporary"):
                continue
            note = advisories.suppression_note(a, self.build)
            if self.stage == "owasp":
                owasp, added = suppressions.add_owasp(owasp, a["ecosystem"], a["package_name"], a["ids"], note)
                if added:
                    self.changed.add(suppressions.OWASP_FILE)
                else:
                    a.update(action="already", outcome_code="already_fixed",
                             reason="deja couvert par une suppression existante")
            else:
                token = suppressions.osv_token(a.get("os_family"), a.get("os_name"))
                statement = note
                if token and a["action"] == "suppress_temporary":
                    # Jeton lu par la revérification des paquets système (avis de la distribution).
                    statement = note.replace("[PENDING_UPSTREAM_FIX]", f"[PENDING_UPSTREAM_FIX] {token}", 1)
                comment = f"{a['finding_id']} - {a['package_name']} (image {a['image']}), fixcve-auto build #{self.build}"
                trivy, added = suppressions.add_trivy(trivy, a["finding_id"], a["package_name"], statement, comment)
                if added:
                    self.changed.add(suppressions.TRIVY_FILE)
                else:
                    a.update(action="already", outcome_code="already_fixed",
                             reason="deja couvert par une suppression existante")
        if suppressions.OWASP_FILE in self.changed:
            _write(suppressions.OWASP_FILE, owasp)
        if suppressions.TRIVY_FILE in self.changed:
            _write(suppressions.TRIVY_FILE, trivy)

    # --- acceptations temporaires désormais corrigées --------------------------------------
    def _apply_pending(self):
        for p in self.plan.get("pending_reverified", []):
            eco = "maven" if ":" in p["package"] else "npm"
            before = _read(suppressions.OWASP_FILE)
            text, touched = suppressions.remove_owasp(before, eco, p["package"], [p["cve_id"]])
            if not touched:
                continue
            if eco == "npm":
                status, detail = edits.npm_upgrade(p["package"], p["new_fixed_version"])
            else:
                status, detail = edits.maven_upgrade(p["package"], "?", p["new_fixed_version"],
                                                     [p["cve_id"]], self.registry)
            if status == "failed":
                self.log(f"cloture {p['cve_id']} {p['package']} abandonnee : {detail}")
                continue
            _write(suppressions.OWASP_FILE, text)
            self.changed.add(suppressions.OWASP_FILE)
            if status == "applied":
                self.changed.update(["frontend/package.json", "frontend/package-lock.json"] if eco == "npm" else [edits.POM])
            self.resolved.append(p)
            self.events.append({"timestamp": _now(), "event": "pending_fix_resolved", "jenkins_build": self.build,
                                "stage": self.stage, "cves": [p["cve_id"]], "package": p["package"],
                                "new_version": p["new_fixed_version"], "outcome_code": "fixed"})

    # --- journal et documentation --------------------------------------------------------
    def _record(self, actions):
        applied = [a for a in actions if a["action"] == "upgrade"]
        accepted = [a for a in actions if a["action"] in ("suppress_permanent", "suppress_temporary")]
        blocked = [a for a in actions if a["action"] == "blocked"]
        transient = [a for a in actions if a["action"] == "transient"]
        if applied:
            self.events.append({"timestamp": _now(), "event": "remediation_applied", "jenkins_build": self.build,
                                "stage": self.stage, "cves": sorted({i for a in applied for i in a["ids"]}),
                                "actions": [clean_text(a.get("applied_detail", ""), 200) for a in applied],
                                "outcome_code": "fixed"})
        for a in accepted:
            event = "risk_accepted_permanent" if a["action"] == "suppress_permanent" else "risk_accepted_pending_upstream_fix"
            self.events.append({"timestamp": _now(), "event": event, "jenkins_build": self.build, "stage": self.stage,
                                "cves": a["ids"], "package": a["package_name"], "cvss": a["cvss"],
                                "criterion": a["criterion"], "justification": clean_text(a["reason"], 300),
                                "outcome_code": a["outcome_code"]})
        if blocked:
            self.events.append({"timestamp": _now(), "event": "findings_blocked", "jenkins_build": self.build,
                                "stage": self.stage, "outcome_code": "blocked_no_fix_ge9",
                                "findings": [{"cves": a["ids"], "package": a["package_name"], "cvss": a["cvss"],
                                              "reason": clean_text(a["reason"], 200)} for a in blocked]})
        if transient:
            self.events.append({"timestamp": _now(), "event": "lookup_transient", "jenkins_build": self.build,
                                "stage": self.stage, "outcome_code": "transient",
                                "findings": [{"cves": a["ids"], "package": a["package_name"], "cvss": a["cvss"]}
                                             for a in transient]})
        if applied or accepted or self.resolved:
            doc = _read(advisories.ADVISORIES_FILE)
            if doc:
                _write(advisories.ADVISORIES_FILE, advisories.insert_section(
                    doc, advisories.section(self.build, self.stage, applied, accepted, blocked, self.resolved)))
                self.changed.add(advisories.ADVISORIES_FILE)
        return applied, accepted, blocked, transient

    def commit_message(self, applied, accepted):
        parts = []
        if applied or self.resolved:
            names = sorted({a["package_name"].split(":")[-1] for a in applied} | {p["package"].split(":")[-1] for p in self.resolved})
            parts.append("corriger " + _short(names))
        if accepted:
            parts.append("accepter " + _short(sorted({a["package_name"].split(":")[-1] for a in accepted})))
        return f"fix(security): {', '.join(parts)} (remédiation automatique build #{self.build})"

    def run(self):
        actions = [downgrade_failed_upgrade(a) if key_of(a) in self.downgrade and a["action"] == "upgrade" else a
                   for a in self.plan["actions"]]
        self._apply_pending()
        actions = self._apply_upgrades(actions)
        self._apply_suppressions(actions)
        applied, accepted, blocked, transient = self._record(actions)
        self.final = actions
        if self.changed:
            result, reason = "APPLIED", str(len(self.changed))
        elif blocked or transient:
            result, reason = "NO_ACTION", "transient" if transient and not blocked else "cve_bloquante_sans_upgrade_disponible"
        elif any(a["action"] == "already" for a in actions):
            result, reason = "NO_ACTION", "deja_corrige_sur_head"
        else:
            result, reason = "NO_ACTION", "rien_a_appliquer"
        return {"result": result, "reason": reason, "changed_files": sorted(self.changed),
                "commit_message": self.commit_message(applied, accepted) if self.changed else None,
                "actions": actions, "pending_resolved": self.resolved, "events": self.events}


def _short(names):
    return ", ".join(names[:4]) + (f" et {len(names) - 4} autres" if len(names) > 4 else "")
