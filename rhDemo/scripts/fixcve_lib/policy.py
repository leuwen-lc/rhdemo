"""Étape 3 — classification déterministe de chaque finding (remplace le jugement de la phase 3 LLM).

Table de décision (dans l'ordre) :
  fix_status=fix_available                         -> upgrade
  fix_status=lookup_failed                         -> transient   (jamais supprimé ; retenté)
  critère A vérifié                                -> suppress_permanent
  CVSS < 9.0                                       -> suppress_temporary (critère B, [PENDING_UPSTREAM_FIX])
  sinon                                            -> blocked     (seul échec conforme à l'objectif)

Critère A (inexposition objective, prime sur le CVSS) :
  - npm : `npm_dev_only` vrai (toutes les copies `dev` dans package-lock.json, calculé par script) ;
  - Maven du projet : toutes les portées sont `test` ou `provided` (mvnw dependency:list) ;
  - vecteur CVSS `AV:L` ou `AV:P`.
Un jugement contextuel (« le code vulnérable n'est pas atteint dans notre configuration ») n'est
jamais automatique : il reste une décision humaine, comme pour les jars des images tierces.
"""
CVSS_BLOCKING = 9.0

# Codes de résultat par finding (indicateur K, voir outcomes.py).
OUTCOME = {
    "upgrade": "fixed",
    "suppress_permanent": "accepted_permanent",
    "suppress_temporary": "accepted_temporary",
    "blocked": "blocked_no_fix_ge9",
    "transient": "transient",
}


def criterion_a(finding, lookup):
    """-> code du critère A vérifié, ou None."""
    vector = finding.get("cvss_vector") or ""
    if "/AV:L" in vector or "/AV:P" in vector:
        return "A:local_vector"
    if finding["ecosystem"] == "npm" and lookup.get("npm_dev_only") is True:
        return "A:npm_dev_only"
    scopes = lookup.get("maven_scopes") or []
    if (finding["ecosystem"] == "maven" and finding.get("image") == "rhdemo-app" and scopes
            and all(s in ("test", "provided") for s in scopes)):
        return "A:maven_scope_" + "_".join(sorted(set(scopes)))
    return None


def classify(finding, lookup):
    status = lookup.get("fix_status")
    # Identifiants inscrits dans une suppression : la faille du finding et ses vrais alias (avis
    # OSV), jamais les GHSA voisins relevés dans les références du rapport (`advisory_aliases`).
    ids = sorted({finding["finding_id"], *lookup.get("aliases", [])})
    base = {"finding_id": finding["finding_id"], "package_name": finding["package_name"],
            "ecosystem": finding["ecosystem"], "image": finding["image"],
            "installed_version": finding["installed_version"], "cvss": finding["cvss"],
            "cvss_vector": finding.get("cvss_vector"), "ids": ids,
            "target_version": None, "target_digest": None, "criterion": None,
            # Gardés pour pouvoir reclasser sans relire lookup.json (downgrade_failed_upgrade).
            "npm_dev_only": lookup.get("npm_dev_only"), "maven_scopes": lookup.get("maven_scopes"),
            # Paquet système d'image : distribution, pour le jeton [OSV:...] d'une suppression Trivy.
            "os_family": finding.get("os_family"), "os_name": finding.get("os_name")}
    if status == "fix_available":
        action = "upgrade"
        base.update(target_version=lookup.get("target_version"), target_digest=lookup.get("target_digest"))
        reason = f"version corrigee {lookup.get('target_version')} ({lookup.get('proof') or lookup.get('source_checked')})"
    elif status == "lookup_failed":
        action, reason = "transient", "recherche de correctif en echec (panne), nouvel essai"
    else:
        crit = criterion_a(finding, lookup)
        if crit:
            action, reason = "suppress_permanent", f"aucun correctif, critere {crit}"
            base["criterion"] = crit
        elif finding["cvss"] < CVSS_BLOCKING:
            action, reason = "suppress_temporary", f"aucun correctif, CVSS {finding['cvss']} < {CVSS_BLOCKING}"
            base["criterion"] = "B"
        else:
            action, reason = "blocked", f"aucun correctif, CVSS {finding['cvss']} >= {CVSS_BLOCKING}, sans critere A"
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


def downgrade_failed_upgrade(action):
    """Une montée qui n'a pas pu être appliquée ou vérifiée retombe dans la branche « sans correctif »
    de la table (A, B ou blocage) — jamais une deuxième tentative de montée dans le même cycle."""
    fallback = dict(action, target_version=None, target_digest=None)
    lookup = {"fix_status": "no_fix_available", "npm_dev_only": action.get("npm_dev_only"),
              "maven_scopes": action.get("maven_scopes"), "aliases": action["ids"]}
    finding = {"finding_id": action["finding_id"], "package_name": action["package_name"],
               "ecosystem": action["ecosystem"], "image": action["image"],
               "installed_version": action["installed_version"], "cvss": action["cvss"],
               "cvss_vector": action.get("cvss_vector"),
               "os_family": action.get("os_family"), "os_name": action.get("os_name")}
    redone = classify(finding, lookup)
    fallback.update(action=redone["action"], outcome_code=redone["outcome_code"],
                    criterion=redone["criterion"],
                    reason="montee impossible a appliquer/verifier ; " + redone["reason"])
    return fallback
