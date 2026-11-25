"""Règles de cycle du poller (P3 de docs/etudes/FIXCVE_REGLES_METIER.md) : fonctions pures.

Chaque fonction reçoit l'état (`state.json`), une observation (build, sha du code source, verdict...)
et l'heure, et rend une décision : le nouvel état et ce que le poller doit faire (pousser le journal,
s'arrêter, notifier). Le poller (poller.py) exécute les effets (git, Jenkins) puis écrit le
nouvel état : un push en échec laisse l'état inchangé et le passage suivant
recommence.

Une seule mémoire « même cause » (`same_cause`) remplace `blocked_confirmed` et
`no_action_confirmed` : {kind, source_sha, since, recheck_seconds, attempts}, avec kind parmi
  blocked    findings bloqués confirmés : silence sur le même code source, revérification à 48 h ;
  transient  recherche de correctif en panne : nouvel essai à 1 h, au plus 3 fois, puis 48 h ;
  no_action  stage Trivy/OWASP en échec sans CVE exploitable : notifié une fois par code source.
"""
import datetime
import re

from .rules import (BLOCKED_RECHECK_SECONDS, MAX_CONSECUTIVE_NO_ACTION_PUSHES,
                    MAX_CONSECUTIVE_PREPUSH_FAILURES, MAX_CONSECUTIVE_ROLLBACKS, STAGE_ORDER,
                    TRANSIENT_MAX_ATTEMPTS, TRANSIENT_RECHECK_SECONDS, stage_type)

INITIAL_STATE = {"last_processed_build": 0, "status": "idle", "pending": None, "consecutive_rollbacks": 0,
                 "consecutive_prepush_failures": 0, "consecutive_no_action_pushes": 0, "same_cause": None}
# Mémoires levées par un correctif poussé ou un stage redevenu propre (pas no_action, levée
# seulement par un build vert).
BLOCKING_KINDS = ("blocked", "transient")


def iso(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch_of(text):
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc).timestamp()
    except (TypeError, ValueError):
        return 0


def normalize(state):
    """État complet au format courant ; lit l'ancien format (blocked_confirmed, no_action_confirmed)."""
    out = dict(INITIAL_STATE)
    out.update({k: v for k, v in (state or {}).items() if k not in ("blocked_confirmed", "no_action_confirmed")})
    if "same_cause" not in (state or {}):
        blocked = (state or {}).get("blocked_confirmed")
        no_action = (state or {}).get("no_action_confirmed")
        if blocked:
            attempts = blocked.get("attempts") or 0
            recheck = blocked.get("recheck_seconds") or BLOCKED_RECHECK_SECONDS
            kind = "transient" if attempts and recheck == TRANSIENT_RECHECK_SECONDS else "blocked"
            out["same_cause"] = {"kind": kind, "source_sha": blocked.get("source_sha") or "",
                                 "since": blocked.get("since"), "recheck_seconds": recheck, "attempts": attempts}
        elif no_action:
            out["same_cause"] = {"kind": "no_action", "source_sha": no_action.get("source_sha") or "",
                                 "since": no_action.get("since"), "recheck_seconds": None, "attempts": 0}
    for counter in ("consecutive_rollbacks", "consecutive_prepush_failures", "consecutive_no_action_pushes"):
        out[counter] = int(out.get(counter) or 0)
    return out


def _cause(kind, sha, now, recheck=None, attempts=0):
    return {"kind": kind, "source_sha": sha or "", "since": iso(now), "recheck_seconds": recheck,
            "attempts": attempts}


def _clear_blocking(state):
    if (state.get("same_cause") or {}).get("kind") in BLOCKING_KINDS:
        state["same_cause"] = None


def _decision(state, **effects):
    out = {"state": state, "push_journal": False, "halt": False, "halt_reason": None, "notify": None, "log": None}
    out.update(effects)
    return out


# ----------------------------------------------------------------------------------------------
# Phase A — nouveau build terminé
# ----------------------------------------------------------------------------------------------

def on_build_not_failed(state, build):
    """Build repassé au vert (ou instable) : la cause « no action » mémorisée n'est plus d'actualité."""
    s = normalize(state)
    s["last_processed_build"] = build
    s["consecutive_no_action_pushes"] = 0
    if (s["same_cause"] or {}).get("kind") == "no_action":
        s["same_cause"] = None
    return _decision(s)


def on_out_of_scope(state, build):
    """Échec hors Trivy/OWASP : jamais journalisé en git (boucle des builds #772/#774, #796/#797)."""
    s = normalize(state)
    s["last_processed_build"] = build
    return _decision(s)


def check_same_cause(state, build, source_sha, now):
    """Avant détection : blocage (ou panne) déjà constaté sur ce même code source et délai non
    écoulé -> cycle ignoré, sans commit ni push (boucle des builds #735-#744)."""
    s = normalize(state)
    cause = s["same_cause"]
    if not cause or cause["kind"] not in BLOCKING_KINDS or cause["source_sha"] != source_sha:
        return _decision(s, skip=False)
    recheck = cause.get("recheck_seconds") or BLOCKED_RECHECK_SECONDS
    elapsed = now - epoch_of(cause.get("since"))
    if elapsed < recheck:
        s["last_processed_build"] = build
        return _decision(s, skip=True, minutes_left=int((recheck - elapsed) // 60), since=cause.get("since"))
    return _decision(s, skip=False, log=f"délai écoulé depuis {cause.get('since')} : nouvelle vérification")


def on_detect_no_action(state, build, source_sha, now):
    """Stage Trivy/OWASP en échec, détection sans CVE exploitable : journalisé une fois par code
    source, halte au-delà de MAX_CONSECUTIVE_NO_ACTION_PUSHES pushes (builds #799-#802)."""
    s = normalize(state)
    cause = s["same_cause"]
    s["last_processed_build"] = build
    if cause and cause["kind"] == "no_action" and cause["source_sha"] == source_sha:
        s["consecutive_prepush_failures"] = 0
        return _decision(s)
    pushes = s["consecutive_no_action_pushes"] + 1
    s["consecutive_no_action_pushes"] = pushes
    s["same_cause"] = _cause("no_action", source_sha, now)
    if pushes >= MAX_CONSECUTIVE_NO_ACTION_PUSHES:
        s["status"] = "halted"
        return _decision(s, push_journal=True, halt=True, halt_reason="max_consecutive_no_action_pushes",
                         notify=f"Halte : {MAX_CONSECUTIVE_NO_ACTION_PUSHES} push(es) \"no action\" consécutifs "
                                f"(build #{build}). Reprise : paramètre ACTION=resume du job.")
    s["consecutive_prepush_failures"] = 0
    return _decision(s, push_journal=True)


def on_prepush_failure(state, build, step):
    """Étape en échec avant tout push de correctif : halte au 2e cycle consécutif."""
    s = normalize(state)
    n = s["consecutive_prepush_failures"] + 1
    s["consecutive_prepush_failures"] = n
    s["last_processed_build"] = build
    if n >= MAX_CONSECUTIVE_PREPUSH_FAILURES:
        s["status"] = "halted"
        return _decision(s, halt=True, halt_reason="max_consecutive_prepush_failures",
                         notify=f"Halte : {MAX_CONSECUTIVE_PREPUSH_FAILURES} échecs pré-push consécutifs "
                                f"(dernier : phase {step}, build #{build}). Reprise : paramètre ACTION=resume du job.")
    return _decision(s)


def on_fix_pushed(state, build, fix_sha, stage, original_findings):
    s = normalize(state)
    s.update(status="pending_validation", consecutive_prepush_failures=0,
             pending={"original_build": build, "fix_commit_sha": fix_sha, "trigger_build_seen": build,
                      "stage_type": stage, "original_findings": list(original_findings)})
    _clear_blocking(s)
    return _decision(s)


def on_apply_no_change(state, build, reason, source_sha, now):
    """Plan appliqué sans fichier modifié : findings bloqués, recherche en panne, ou déjà corrigé."""
    s = normalize(state)
    s["consecutive_prepush_failures"] = 0
    if reason == "cve_bloquante_sans_upgrade_disponible":
        # Échec conforme : journalisé une fois, puis silence 48 h sur ce même code source.
        s["last_processed_build"] = build
        s["same_cause"] = _cause("blocked", source_sha, now, BLOCKED_RECHECK_SECONDS)
        return _decision(s, push_journal=True,
                         notify=f"Build #{build} : findings bloqués (sans correctif, CVSS >= 9) — revue humaine "
                                "requise (voir fixcve-audit.md).")
    if reason == "transient":
        prev = s["same_cause"] or {}
        attempts = (prev.get("attempts") or 0) if (prev.get("kind") in BLOCKING_KINDS
                                                   and prev.get("source_sha") == source_sha) else 0
        attempts += 1
        exhausted = attempts >= TRANSIENT_MAX_ATTEMPTS
        recheck = BLOCKED_RECHECK_SECONDS if exhausted else TRANSIENT_RECHECK_SECONDS
        # build - 1 : le même build sera repris au prochain essai.
        s["last_processed_build"] = build - 1
        s["same_cause"] = _cause("transient", source_sha, now, recheck, attempts)
        if exhausted:
            return _decision(s, push_journal=True, attempts=attempts,
                             log=f"ALERTE : recherche de correctif en panne {attempts} fois de suite "
                                 f"(build #{build}) — prochain essai dans 48h.")
        return _decision(s, attempts=attempts,
                         log=f"Build #{build} : recherche de correctif en panne (essai {attempts}/"
                             f"{TRANSIENT_MAX_ATTEMPTS}) — nouvel essai dans 1h.")
    # deja_corrige_sur_head / rien_a_appliquer : rien à committer (un push relancerait un build).
    s["last_processed_build"] = build
    _clear_blocking(s)
    return _decision(s)


# ----------------------------------------------------------------------------------------------
# Phase B — validation d'un correctif poussé
# ----------------------------------------------------------------------------------------------

def partial_verdict(stage, original, detect, current=(), failing_stage=None, failure_detail=None,
                    fix_only_suppressions=False):
    """Build de validation en échec : garder le correctif, passer au stage suivant ou l'annuler.

    `detect` : "ok" (findings lus : `current`), "error", "invalid", ou "no_action:<raison>".
    -> (verdict keep|next_stage|rollback, raison, retirés, restants, stage suivant).
    Tout doute => rollback. Incidents : #890 (stage propre, échec Trivy suivant), #972 (finding non
    lu par le détecteur), #975 (CVE nouvelle indépendante d'un correctif de suppressions)."""
    original = list(original)
    if detect == "error":
        return "rollback", "detection_impossible", [], [], None
    if detect == "invalid":
        return "rollback", "rapport_de_validation_invalide", [], [], None
    if detect.startswith("no_action"):
        reason = f"aucun_finding_{stage}_dans_le_build_de_validation"
        if detect not in ("no_action:owasp_no_finding_above_threshold", "no_action:trivy_no_critical_finding"):
            return "rollback", reason, [], [], None
        failing = stage_type(failing_stage)
        if failing and STAGE_ORDER[failing] > STAGE_ORDER.get(stage, 0):
            return "next_stage", f"stage_{stage}_propre_echec_sur_{failing}", original, [], failing
        if failing == stage:
            detail = failure_detail or "non disponible"
            # Identifiant entier (CVE-2026-1160 n'est pas CVE-2026-116804) ; avant, sous-chaîne.
            still = any(re.search(r"(?<![\w-])" + re.escape(key.split("|")[0]) + r"(?![\w-])", detail)
                        for key in original)
            if not still and detail != "non disponible":
                return "keep", f"stage_{stage}_en_echec_sur_finding_non_detecte", original, [], None
        return "rollback", reason, [], [], None
    current = list(current)
    added = [k for k in current if k not in original]
    removed = [k for k in original if k not in current]
    if added:
        if fix_only_suppressions and len(removed) == len(original):
            return "next_stage", "correctif_suppression_nouvelle_cve_independante", removed, current, stage
        return "rollback", "nouvelle_cve_apres_correctif", removed, current, None
    if not removed:
        return "rollback", "aucun_progres", removed, current, None
    return "keep", "progres_sans_regression", removed, current, None


def on_validation(state, build, verdict, source_sha, now):
    """Issue de la phase B. `verdict` : success, next_stage, keep, rollback, rollback_conflict."""
    s = normalize(state)
    s.update(status="idle", pending=None, last_processed_build=build)
    if verdict == "success":
        s["consecutive_rollbacks"] = 0
    elif verdict == "next_stage":
        # build - 1 : la phase A traitera ce build comme une panne du stage suivant.
        s.update(consecutive_rollbacks=0, last_processed_build=build - 1)
        _clear_blocking(s)
    elif verdict == "keep":
        # Les findings restants sont ceux jugés bloqués : même silence qu'un blocage confirmé.
        s["consecutive_rollbacks"] = 0
        s["same_cause"] = _cause("blocked", source_sha, now, BLOCKED_RECHECK_SECONDS)
    elif verdict == "rollback_conflict":
        s["same_cause"] = _cause("blocked", source_sha, now, BLOCKED_RECHECK_SECONDS)
    elif verdict == "rollback":
        n = s["consecutive_rollbacks"] + 1
        s["consecutive_rollbacks"] = n
        if n >= MAX_CONSECUTIVE_ROLLBACKS:
            s["status"] = "halted"
            return _decision(s, halt=True, halt_reason="max_consecutive_rollbacks",
                             notify=f"Halte : {MAX_CONSECUTIVE_ROLLBACKS} rollbacks consécutifs. "
                                    "Reprise : paramètre ACTION=resume du job.")
    else:
        raise ValueError(f"verdict inconnu : {verdict}")
    return _decision(s)
