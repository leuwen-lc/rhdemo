"""Étape 3 — classification déterministe de chaque finding (remplace le jugement de la phase 3 LLM).

Table de décision (dans l'ordre) :
  fix_status=fix_available                         -> upgrade
  fix_status=lookup_failed                         -> transient   (jamais supprimé ; retenté)
  critère A vérifié                                -> suppress_permanent
  CVSS < CVSS_BLOCKING (rules.py)                  -> suppress_temporary (critère B, [PENDING_UPSTREAM_FIX])
  sinon                                            -> blocked     (seul échec conforme à l'objectif)

Critère A (inexposition objective, prime sur le CVSS) :
  - npm : `npm_dev_only` vrai (toutes les copies `dev` dans package-lock.json, calculé par script) ;
  - Maven du projet : toutes les portées sont `test` ou `provided` (mvnw dependency:list) ;
  - vecteur CVSS `AV:L` ou `AV:P`.
Un jugement contextuel (« le code vulnérable n'est pas atteint dans notre configuration ») n'est
jamais automatique : il reste une décision humaine, comme pour les jars des images tierces.
"""
from .rules import CVSS_BLOCKING, kind_of

# Codes de résultat par finding (indicateur K, voir outcomes.py).
OUTCOME = {
    "upgrade": "fixed",
    "suppress_permanent": "accepted_permanent",
    "suppress_temporary": "accepted_temporary",
    "blocked": "blocked_no_fix_ge9",
    "transient": "transient",
}


def criterion_a(kind, cvss_vector, maven_scopes, npm_dev_only):
    """-> code du critère A vérifié, ou None. `kind` : rules.Kind du composant."""
    vector = cvss_vector or ""
    if "/AV:L" in vector or "/AV:P" in vector:
        return "A:local_vector"
    if kind.dev_only_criterion and npm_dev_only is True:
        return "A:npm_dev_only"
    scopes = maven_scopes or []
    if kind.scope_criterion and scopes and all(s in ("test", "provided") for s in scopes):
        return "A:maven_scope_" + "_".join(sorted(set(scopes)))
    return None


def decide(kind, fix_status, cvss, cvss_vector=None, maven_scopes=None, npm_dev_only=None):
    """Table de décision, sur des valeurs simples -> (action, critère ou None)."""
    if fix_status == "fix_available":
        return "upgrade", None
    if fix_status == "lookup_failed":
        return "transient", None
    crit = criterion_a(kind, cvss_vector, maven_scopes, npm_dev_only)
    if crit:
        return "suppress_permanent", crit
    if cvss < CVSS_BLOCKING:
        return "suppress_temporary", "B"
    return "blocked", None


def _reason(action, criterion, cvss, target_version=None, proof=None):
    if action == "upgrade":
        return f"version corrigee {target_version} ({proof})"
    if action == "transient":
        return "recherche de correctif en echec (panne), nouvel essai"
    if action == "suppress_permanent":
        return f"aucun correctif, critere {criterion}"
    if action == "suppress_temporary":
        return f"aucun correctif, CVSS {cvss} < {CVSS_BLOCKING}"
    return f"aucun correctif, CVSS {cvss} >= {CVSS_BLOCKING}, sans critere A"


def classify(finding, lookup):
    kind = kind_of(finding)
    # Identifiants inscrits dans une suppression : la faille du finding et ses vrais alias (avis
    # OSV), jamais les GHSA voisins relevés dans les références du rapport (`advisory_aliases`).
    ids = sorted({finding["finding_id"], *lookup.get("aliases", [])})
    action, criterion = decide(kind, lookup.get("fix_status"), finding["cvss"], finding.get("cvss_vector"),
                               lookup.get("maven_scopes"), lookup.get("npm_dev_only"))
    base = {"finding_id": finding["finding_id"], "package_name": finding["package_name"],
            "ecosystem": finding["ecosystem"], "image": finding["image"], "component_kind": kind.name,
            "installed_version": finding["installed_version"], "cvss": finding["cvss"],
            "cvss_vector": finding.get("cvss_vector"), "ids": ids,
            "target_version": None, "target_digest": None, "criterion": criterion,
            # Gardés pour pouvoir reclasser sans relire lookup.json (downgrade_failed_upgrade).
            "npm_dev_only": lookup.get("npm_dev_only"), "maven_scopes": lookup.get("maven_scopes"),
            # Paquet système d'image : distribution, pour le jeton [OSV:...] d'une suppression Trivy.
            "os_family": finding.get("os_family"), "os_name": finding.get("os_name")}
    if action == "upgrade":
        base.update(target_version=lookup.get("target_version"), target_digest=lookup.get("target_digest"))
    reason = _reason(action, criterion, finding["cvss"], lookup.get("target_version"),
                     lookup.get("proof") or lookup.get("source_checked"))
    base.update(action=action, outcome_code=OUTCOME[action], reason=reason)
    return base


def build_plan(detected, lookup):
    by_key = {(e["finding_id"], e["package_name"]): e for e in lookup.get("findings", [])}
    actions = []
    for f in detected.get("findings", []):
        entry = by_key.get((f["finding_id"], f["package_name"]))
        if entry is None:
            entry = {"fix_status": "lookup_failed"}
        actions.append(classify(f, entry))
    return {"jenkins_build": detected.get("jenkins_build"), "stage": detected.get("stage"),
            "actions": actions, "pending_reverified": lookup.get("pending_reverified", [])}


def downgrade_failed_upgrade(action, cause=None):
    """Une montée qui n'a pas pu être appliquée ou vérifiée retombe dans la branche « sans correctif »
    de la table (A, B ou blocage) — jamais une deuxième tentative de montée dans le même cycle.
    `cause` (raison de l'échec) reste dans le journal : un correctif publié mais inapplicable ne
    doit jamais se lire « aucun correctif »."""
    redone, criterion = decide(kind_of(action), "no_fix_available", action["cvss"], action.get("cvss_vector"),
                               action.get("maven_scopes"), action.get("npm_dev_only"))
    # Correctif publié mais montée impossible à appliquer : défaut de la procédure (tooling),
    # jamais un « échec conforme » (blocked_no_fix_ge9 suppose qu'aucun correctif n'existe).
    outcome = "tooling" if cause and redone == "blocked" else OUTCOME[redone]
    reason = _reason(redone, criterion, action["cvss"])
    return dict(action, target_version=None, target_digest=None, action=redone, outcome_code=outcome,
                criterion=criterion,
                reason=(f"correctif {action.get('target_version')} publie mais montee impossible "
                        f"({cause or 'non confirmee par la verification'}) ; "
                        + reason.replace("aucun correctif", "traite comme sans correctif", 1)))
