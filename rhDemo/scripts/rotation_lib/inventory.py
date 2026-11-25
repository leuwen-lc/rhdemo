"""Lecture et contrôle de secrets/inventory.yaml."""
import os

import yaml

from .common import RotationError

DEFAULT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "secrets",
                                            "inventory.yaml"))
LEVELS = ("C", "H", "M")
LEVEL_LABELS = {"C": "critique", "H": "élevée", "M": "moyenne"}
EXPOSURES = ("internet", "lan", "local")
EXPOSURE_ORDER = {e: i for i, e in enumerate(EXPOSURES)}
TARGET_KEYS = {"jenkins": {"credential", "type"},
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
    "grafana-admin": {"kv_path", "kv_key", "user_key", "namespace", "external_secrets", "k8s_secret",
                      "k8s_key", "restart", "service"},
    "k8s-sa-token": {"namespace", "service_account", "secret_prefix", "server", "cluster"},
    "planned": {"phase"},
    "per-build": {"note"},
}
# Sorte de rotation affichée par --list (vocabulaire de docs/ROTATION_SECRETS.md) : toute méthode
# de METHOD_KEYS doit y figurer (contrôlé par les tests).
METHOD_KINDS = {
    "forgejo-token": "automatique", "forgejo-gpg": "automatique",
    "openbao-approle": "automatique", "postgres-password": "automatique",
    "keycloak-client-secret": "automatique", "keycloak-admin": "automatique",
    "keycloak-users": "automatique", "grafana-admin": "automatique", "k8s-sa-token": "automatique",
    "manual-value": "semi-manuelle",
    "manual": "manuelle",
    "per-build": "à chaque build",
    "planned": "prévue",
}
NEEDS_TARGETS = {"forgejo-token", "forgejo-gpg", "manual-value", "openbao-approle", "k8s-sa-token"}
# Secrets régénérés à chaque build (ephemere) : rien à renouveler, rien à tracer, aucune cible.
NO_ROTATION = {"per-build"}
# Secret bloquant (blocking: true) : il cesse de fonctionner s'il n'est pas renouvelé à temps
# (durée de vie imposée par le fournisseur, lifetime_days si elle est connue). --check le
# signale en retard EXPIRY_MARGIN_DAYS jours avant son expiration.
EXPIRY_MARGIN_DAYS = 14
# rotation.session : identifiant maître de la session du script changé par cette procédure
# manuelle ; en urgence, le script l'oublie ensuite et le redemande à la connexion suivante.
SESSIONS = ("jenkins",)


def load(path=DEFAULT_PATH):
    with open(path, encoding="utf-8") as fh:
        inv = yaml.safe_load(fh)
    errors = validate(inv)
    if errors:
        raise RotationError("inventaire invalide :\n  " + "\n  ".join(errors))
    return inv


def validate(inv):
    errors = [f"clé racine « {key} » absente" for key in ("periods", "services", "secrets") if key not in (inv or {})]
    if errors:
        return errors
    seen = set()
    for e in inv["secrets"]:
        sid = e.get("id", "?")
        if sid in seen:
            errors.append(f"{sid} : identifiant en double")
        seen.add(sid)
        errors += _validate_description(e, sid)
        method = (e.get("rotation") or {}).get("method")
        if method not in METHOD_KEYS:
            errors.append(f"{sid} : méthode {method} inconnue")
            continue
        errors += _validate_rotation(e, sid, method)
        errors += _validate_lifecycle(e, sid, method)
        errors += _validate_targets(e, sid, method)
    return errors + _validate_emergency(inv)


def _validate_description(e, sid):
    """Champs obligatoires, criticité et exposition."""
    errors = [f"{sid} : champ « {k} » absent" for k in ("num", "label", "criticality", "exposure", "rotation")
              if k not in e]
    if e.get("criticality") not in LEVELS:
        errors.append(f"{sid} : criticité {e.get('criticality')} inconnue")
    if e.get("exposure") not in EXPOSURES:
        errors.append(f"{sid} : exposition {e.get('exposure')} inconnue")
    return errors


def _validate_rotation(e, sid, method):
    """Paramètres exigés par la méthode, vérification après rotation."""
    errors = []
    rotation = e["rotation"]
    missing = METHOD_KEYS[method] - set(rotation)
    if missing:
        errors.append(f"{sid} : {method} exige {', '.join(sorted(missing))}")
    if rotation.get("verify") not in (None, "smtp"):
        errors.append(f"{sid} : vérification {rotation['verify']} inconnue")
    if rotation.get("verify") == "smtp" and "smtp_credential" not in rotation:
        errors.append(f"{sid} : verify smtp exige smtp_credential")
    return errors


def _validate_lifecycle(e, sid, method):
    """Secret bloquant, durée de vie, session à oublier en urgence."""
    errors = []
    if not isinstance(e.get("blocking", False), bool):
        errors.append(f"{sid} : blocking doit valoir true ou false")
    life = e.get("lifetime_days")
    if life is not None:
        if isinstance(life, bool) or not isinstance(life, int) or life <= EXPIRY_MARGIN_DAYS:
            errors.append(f"{sid} : lifetime_days doit être un entier > {EXPIRY_MARGIN_DAYS}")
        if e.get("blocking") is not True:
            errors.append(f"{sid} : lifetime_days exige blocking: true")
    if e["rotation"].get("session") not in (None, *SESSIONS):
        errors.append(f"{sid} : session {e['rotation']['session']} inconnue")
    if method in NO_ROTATION and e.get("blocking"):
        errors.append(f"{sid} : {method} ne peut pas être bloquant")
    return errors


def _validate_targets(e, sid, method):
    """Cibles exigées ou interdites par la méthode, puis chaque cible."""
    errors = []
    targets = e.get("targets") or []
    if method in NEEDS_TARGETS and not targets:
        errors.append(f"{sid} : {method} exige au moins une cible")
    if method == "k8s-sa-token":
        errors += _validate_k8s_sa_token(e, sid, method, targets)
    if method in NO_ROTATION and targets:
        errors.append(f"{sid} : {method} n'admet aucune cible")
    for t in targets:
        kind = t.get("kind")
        if kind not in TARGET_KEYS:
            errors.append(f"{sid} : cible {kind} inconnue")
        elif TARGET_KEYS[kind] - set(t):
            errors.append(f"{sid} : cible {kind} incomplète")
        elif kind == "jenkins" and t["type"] not in JENKINS_TYPES:
            errors.append(f"{sid} : type Jenkins {t['type']} inconnu")
    return errors


def _validate_k8s_sa_token(e, sid, method, targets):
    errors = []
    if any(t.get("kind") != "jenkins" or t.get("type") != "file" for t in targets):
        errors.append(f"{sid} : {method} n'admet que des cibles jenkins de type file")
    for k in ("allowed", "denied"):
        if not all(isinstance(c, str) and c.strip() for c in e["rotation"].get(k, [])):
            errors.append(f"{sid} : {k} doit être une liste de vérifications auth can-i")
    return errors


def _validate_emergency(inv):
    ids = {e.get("id") for e in inv["secrets"]}
    first = inv.get("emergency_first", [])
    if not isinstance(first, list):
        return ["emergency_first doit être une liste d'identifiants"]
    return [f"emergency_first : secret inconnu {sid}" for sid in first if sid not in ids]


def by_id(inv, sid):
    for e in inv["secrets"]:
        if e["id"] == sid:
            return e
    raise RotationError(f"secret inconnu : {sid} (voir --list)")


def ordered(entries):
    """Ordre d'urgence de l'étude (§3.3) : exposition, puis criticité."""
    return sorted(entries, key=lambda e: (EXPOSURE_ORDER[e["exposure"]], LEVELS.index(e["criticality"])))


def emergency_order(inv, compromised=False):
    """Tout le périmètre renouvelable dans l'ordre d'urgence. Si Jenkins ou le poste sont
    compromis, les secrets de emergency_first d'abord (ils donnent accès aux autres)."""
    entries = ordered(e for e in inv["secrets"] if e["rotation"]["method"] not in NO_ROTATION)
    if not compromised:
        return entries
    first = [by_id(inv, sid) for sid in inv.get("emergency_first", [])]
    return first + [e for e in entries if e not in first]
