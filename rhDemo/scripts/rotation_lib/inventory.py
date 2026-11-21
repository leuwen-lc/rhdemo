"""Lecture et contrôle de secrets/inventory.yaml."""
import os

import yaml

from .common import RotationError

DEFAULT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "secrets",
                                            "inventory.yaml"))
LEVELS = ("C", "H", "M")
EXPOSURES = ("internet", "lan", "local")
EXPOSURE_ORDER = {e: i for i, e in enumerate(EXPOSURES)}
TARGET_KEYS = {"jenkins": {"credential", "type"}, "sops": {"file", "key"},
               "openbao": {"path", "key"}, "approle-file": {"file"}}
JENKINS_TYPES = ("string", "username-password", "file", "vault-approle")
METHOD_KEYS = {
    "forgejo-token": {"account", "token_prefix", "scopes"},
    "forgejo-gpg": {"account"},
    "manual-value": {"procedure"},
    "manual": {"procedure"},
    "openbao-approle": {"role"},
    "postgres-password": {"kv_path", "kv_key", "namespace", "pod", "db_user", "database",
                          "external_secrets", "k8s_secret", "restart"},
    "keycloak-client-secret": {"kv_path", "kv_key", "realm", "client_id", "namespace",
                               "external_secrets", "k8s_secret", "k8s_key", "restart"},
    "keycloak-admin": {"kv_path", "kv_key", "user_key", "realm", "namespace", "external_secrets",
                       "k8s_secret"},
    "keycloak-users": {"kv_path", "realm", "users"},
    "planned": {"phase"},
}
NEEDS_TARGETS = {"forgejo-token", "forgejo-gpg", "manual-value", "openbao-approle"}


def load(path=DEFAULT_PATH):
    with open(path, encoding="utf-8") as fh:
        inv = yaml.safe_load(fh)
    errors = validate(inv)
    if errors:
        raise RotationError("inventaire invalide :\n  " + "\n  ".join(errors))
    return inv


def validate(inv):
    errors = []
    for key in ("periods", "services", "secrets"):
        if key not in (inv or {}):
            errors.append(f"clé racine « {key} » absente")
    if errors:
        return errors
    seen = set()
    for e in inv["secrets"]:
        sid = e.get("id", "?")
        if sid in seen:
            errors.append(f"{sid} : identifiant en double")
        seen.add(sid)
        for k in ("num", "label", "criticality", "exposure", "rotation"):
            if k not in e:
                errors.append(f"{sid} : champ « {k} » absent")
        if e.get("criticality") not in LEVELS:
            errors.append(f"{sid} : criticité {e.get('criticality')} inconnue")
        if e.get("exposure") not in EXPOSURES:
            errors.append(f"{sid} : exposition {e.get('exposure')} inconnue")
        method = (e.get("rotation") or {}).get("method")
        if method not in METHOD_KEYS:
            errors.append(f"{sid} : méthode {method} inconnue")
            continue
        missing = METHOD_KEYS[method] - set(e["rotation"])
        if missing:
            errors.append(f"{sid} : {method} exige {', '.join(sorted(missing))}")
        if e["rotation"].get("verify") not in (None, "smtp"):
            errors.append(f"{sid} : vérification {e['rotation']['verify']} inconnue")
        if e["rotation"].get("verify") == "smtp" and "smtp_credential" not in e["rotation"]:
            errors.append(f"{sid} : verify smtp exige smtp_credential")
        targets = e.get("targets") or []
        if method in NEEDS_TARGETS and not targets:
            errors.append(f"{sid} : {method} exige au moins une cible")
        for t in targets:
            kind = t.get("kind")
            if kind not in TARGET_KEYS:
                errors.append(f"{sid} : cible {kind} inconnue")
            elif TARGET_KEYS[kind] - set(t):
                errors.append(f"{sid} : cible {kind} incomplète")
            elif kind == "jenkins" and t["type"] not in JENKINS_TYPES:
                errors.append(f"{sid} : type Jenkins {t['type']} inconnu")
    return errors


def by_id(inv, sid):
    for e in inv["secrets"]:
        if e["id"] == sid:
            return e
    raise RotationError(f"secret inconnu : {sid} (voir --list)")


def ordered(entries):
    """Ordre d'urgence de l'étude (§3.3) : exposition, puis criticité."""
    return sorted(entries, key=lambda e: (EXPOSURE_ORDER[e["exposure"]], LEVELS.index(e["criticality"])))
