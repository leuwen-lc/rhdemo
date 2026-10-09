"""Codes de résultat (`outcome_code`) et taux d'échec du journal (indicateur K).

Objectif mesuré : un cycle n'échoue que face à une CVE sans correctif, CVSS >= 9 et sans
critère A (`blocked_no_fix_ge9`, « échec conforme »). Tout autre échec est un défaut.
"""
import collections
import json

SUCCESS = {"fixed", "already_fixed", "accepted_permanent", "accepted_temporary"}
CONFORMING = {"blocked_no_fix_ge9"}
# Défauts de la procédure, comptés dans le taux d'échec.
FAILURES = {"lookup_gap", "policy", "bad_fix", "tooling", "needs_reasoning", "transient"}
# Pannes d'environnement (étape 0) : suivies à part, hors taux d'échec de la remédiation.
INFRA = {"infra"}
ALL_CODES = SUCCESS | CONFORMING | FAILURES | INFRA

# Événements sans portée « résultat de cycle » (validation d'un cycle précédent, halte...).
_NEUTRAL_EVENTS = {"validation_success", "validation_partial", "validation_stage_cleared",
                   "automation_halted", "local_validation_incomplete", "skipped_local_validation_nvd_sync",
                   "validation_kept_despite_failure", "skipped_out_of_scope"}


def legacy_outcome(event):
    """Code déduit d'un événement antérieur au champ outcome_code (classement approximatif)."""
    kind = event.get("event")
    text = json.dumps(event, ensure_ascii=False).lower()
    if kind in _NEUTRAL_EVENTS:
        return None
    if kind in ("remediation_applied", "pending_fix_resolved"):
        return "fixed"
    if kind == "risk_accepted_permanent":
        return "accepted_permanent"
    if kind == "risk_accepted_pending_upstream_fix":
        return "accepted_temporary"
    if kind == "validation_failed_rollback":
        return "bad_fix"
    if kind in ("detect_phase_failed", "lookup_phase_failed", "claude_invocation_no_result"):
        return "tooling"
    if kind == "skipped_infra_failure":
        return "infra"
    if kind == "blocked_needs_human":
        if "lookup_failed" in text or "introuvable" in text:
            return "lookup_gap"
        cvss = event.get("cvss")
        if isinstance(cvss, (int, float)) and cvss >= 9.0:
            return "blocked_no_fix_ge9"
        return "policy"
    return None


def outcome_of(event):
    code = event.get("outcome_code")
    return code if code in ALL_CODES else legacy_outcome(event)


def cycle_results(events):
    """{build: code du cycle} : défaut prioritaire, puis échec conforme, puis succès, puis infra."""
    per_build = collections.defaultdict(set)
    builds_month = {}
    for e in events:
        # Un rollback compte contre le cycle qui a poussé le correctif, pas contre le build de validation.
        if e.get("event") == "validation_failed_rollback" and e.get("original_build"):
            build = e["original_build"]
        else:
            build = e.get("jenkins_build") or e.get("original_build")
        code = outcome_of(e)
        if build is None or code is None:
            continue
        per_build[build].add(code)
        builds_month.setdefault(build, (e.get("timestamp") or "")[:7])
    results = {}
    for build, codes in per_build.items():
        failures = sorted(codes & FAILURES)
        if failures:
            results[build] = failures[0]
        elif codes & CONFORMING:
            results[build] = "blocked_no_fix_ge9"
        elif codes & SUCCESS:
            results[build] = "success"
        else:
            results[build] = "infra"
    return results, builds_month


def stats(events):
    """Par mois : cycles, succès, échecs conformes, défauts (par code), infra, taux d'échec."""
    results, months = cycle_results(events)
    table = collections.OrderedDict()
    for build in sorted(results, key=lambda b: (months.get(b, ""), b)):
        month = months.get(build, "?")
        row = table.setdefault(month, collections.Counter())
        row[results[build]] += 1
    out = []
    for month, row in table.items():
        cycles = sum(n for code, n in row.items() if code != "infra")
        failures = sum(n for code, n in row.items() if code in FAILURES)
        out.append({"month": month, "cycles": cycles, "success": row["success"],
                    "conforming": row["blocked_no_fix_ge9"], "infra": row["infra"],
                    "failures": {c: row[c] for c in sorted(FAILURES) if row[c]},
                    "failure_rate": round(failures / cycles, 2) if cycles else 0.0})
    return out
