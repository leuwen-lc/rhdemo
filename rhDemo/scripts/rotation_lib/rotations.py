"""Cycle de rotation par méthode : contrôler les cibles, créer, vérifier, propager, révoquer.

Ordre retenu (mode normal) : le nouveau secret est vérifié auprès du fournisseur AVANT d'être
propagé, et l'ancien n'est révoqué qu'après une propagation réussie. Si la vérification ou la
propagation échoue sans qu'aucune cible n'ait été modifiée, le nouveau secret est supprimé.
"""
import base64
import os

from .common import RotationError, log, new_password, stamp, warn
from .forgejo import Forgejo
from .smtp import smtp_login
from .jenkins import Jenkins
from . import tools


class Context:
    """Clients et paramètres partagés par les rotations d'une session (créés à la demande)."""

    def __init__(self, inventory, prompter, journal, dry_run=False):
        self.inv = inventory
        self.prompter = prompter
        self.journal = journal
        self.dry_run = dry_run
        self._jenkins = None
        self._forgejo = None
        self.smtp_check = smtp_login

    @property
    def services(self):
        return self.inv["services"]

    def jenkins(self):
        if self._jenkins is None:
            cfg = self.services["jenkins"]
            user = os.environ.get("JENKINS_ADMIN_USER", cfg.get("admin_user", "admin"))
            password = self.prompter.secret("jenkins", f"Mot de passe Jenkins de {user}")
            client = Jenkins(cfg["url"], user, password)
            client.login()
            self._jenkins = client
        return self._jenkins

    def forgejo(self):
        if self._forgejo is None:
            self._forgejo = Forgejo(self.services["forgejo"]["url"], self.prompter)
        return self._forgejo



# --- cibles (consommateurs du secret) ------------------------------------------------------

def check_targets(ctx, entry):
    """Échoue avant toute création si une cible est inaccessible ou de mauvais type."""
    for t in entry.get("targets", []):
        if t["kind"] == "jenkins":
            ctx.jenkins().read(t["credential"], t["type"])
        elif t["kind"] == "sops":
            tools.sops_get(os.path.expanduser(t["file"]), t["key"])
        else:
            raise RotationError(f"cible inconnue : {t['kind']}")


def propagate(ctx, entry, value):
    """Écrit la nouvelle valeur dans chaque cible. Renvoie la liste des cibles modifiées ;
    en cas d'échec, l'exception porte cette liste (attribut `updated`)."""
    updated = []
    try:
        for t in entry.get("targets", []):
            if t["kind"] == "jenkins":
                ctx.jenkins().update(t["credential"], t["type"], value)
                updated.append(f"Jenkins {t['credential']}")
            elif t["kind"] == "sops":
                tools.sops_set(os.path.expanduser(t["file"]), t["key"], value)
                updated.append(f"SOPS {t['file']} {t['key']}")
    except RotationError as exc:
        exc.updated = updated
        raise
    return updated


def _targets_text(entry):
    parts = []
    for t in entry.get("targets", []):
        parts.append(f"Jenkins {t['credential']}" if t["kind"] == "jenkins"
                     else f"SOPS {t['file']} {t['key']}")
    return ", ".join(parts)


def _propagate_or_rollback(ctx, entry, value, rollback, what):
    try:
        return propagate(ctx, entry, value)
    except RotationError as exc:
        if getattr(exc, "updated", None):
            warn(f"propagation partielle ({', '.join(exc.updated)}) : {what} conservé, "
                 "ancien secret NON révoqué, terminer à la main")
        else:
            rollback()
            warn(f"{what} supprimé (aucune cible modifiée)")
        raise


# --- méthodes ------------------------------------------------------------------------------

def rotate_forgejo_token(ctx, entry):
    r = entry["rotation"]
    user, prefix, scopes = r["account"], r["token_prefix"], r["scopes"]
    repo = ctx.services["forgejo"].get("repo") if r.get("needs_push", True) else None
    fj = ctx.forgejo()

    check_targets(ctx, entry)
    tokens = fj.list_tokens(user)
    managed = [t for t in tokens if t["name"].startswith(prefix + "-")]
    revoke = list(managed)
    for t in tokens:
        if t in managed:
            continue
        if ctx.prompter.confirm(f"{user} : token non géré « {t['name']} » "
                                f"({', '.join(t.get('scopes') or [])}), le révoquer aussi ?"):
            revoke.append(t)
    for t in revoke:
        old_scopes = set(t.get("scopes") or [])
        if old_scopes and old_scopes != set(scopes):
            if not ctx.prompter.confirm(f"{user} : « {t['name']} » a les portées "
                                        f"{', '.join(sorted(old_scopes))}, l'inventaire demande "
                                        f"{', '.join(sorted(scopes))}. Continuer avec l'inventaire ?"):
                raise RotationError(f"portées divergentes pour {user} : corriger l'inventaire")
    name = f"{prefix}-{stamp()}"
    log(f"  nouveau token {name} ({', '.join(scopes)}) → {_targets_text(entry)}")
    log(f"  à révoquer : {', '.join(t['name'] for t in revoke) or 'aucun'}")
    if ctx.dry_run:
        return None

    token_id, value = fj.create_token(user, name, scopes)

    def rollback():
        fj.delete_token(user, token_id)

    try:
        fj.check_token(value, user, repo)
    except RotationError:
        rollback()
        warn(f"token {name} supprimé (vérification échouée, rien d'autre n'a changé)")
        raise
    _propagate_or_rollback(ctx, entry, value, rollback, f"token {name}")
    for t in revoke:
        fj.delete_token(user, t["id"])
        log(f"  révoqué : {t['name']}")
    return f"token {name}, révoqués : {', '.join(t['name'] for t in revoke) or 'aucun'}"


def rotate_forgejo_gpg(ctx, entry):
    r = entry["rotation"]
    user = r["account"]
    fj = ctx.forgejo()

    check_targets(ctx, entry)
    old_keys = fj.list_gpg_keys(user)
    email = fj.user_email(user)
    if not email:
        raise RotationError(f"Codeberg : adresse mail de {user} introuvable")
    uid = f"{r.get('uid_name', user)} <{email}>"
    log(f"  nouvelle clé {r.get('algo', 'rsa4096')} pour {r.get('uid_name', user)}, "
        f"expiration {r.get('expire', '2y')} → {_targets_text(entry)}")
    log(f"  clés à retirer de Codeberg : {', '.join(k['key_id'] for k in old_keys) or 'aucune'}")
    if ctx.dry_run:
        return None

    with tools.gpg_home() as home:
        fpr, public, private = tools.gpg_generate(home, uid, r.get("algo", "rsa4096"),
                                                  r.get("expire", "2y"))
        signature = tools.gpg_sign(home, fpr, fj.gpg_key_token(user))
    try:
        added = fj.add_gpg_key(user, public, signature)
    except RotationError as exc:
        warn(f"ajout avec preuve de possession refusé ({exc}) : nouvel essai sans signature, "
             "la clé apparaîtra non vérifiée sur Codeberg")
        added = fj.add_gpg_key(user, public)
    new_id = added["id"]

    def rollback():
        fj.delete_gpg_key(user, new_id)

    value = base64.b64encode(private.encode("ascii")).decode("ascii")
    _propagate_or_rollback(ctx, entry, value, rollback, f"clé {fpr[-16:]}")
    for k in old_keys:
        fj.delete_gpg_key(user, k["id"])
        log(f"  retirée de Codeberg : {k['key_id']}")
    return f"clé {fpr[-16:]}, retirées : {', '.join(k['key_id'] for k in old_keys) or 'aucune'}"



def rotate_manual_value(ctx, entry):
    """Valeur créée à la main chez le fournisseur (pas d'API, ou API sans révocation), saisie,
    vérifiée si possible, puis propagée. La révocation de l'ancienne reste manuelle.

    verify: smtp -> connexion SMTP avec le nom d'utilisateur du credential Jenkins
    `smtp_credential` et la nouvelle valeur, avant toute propagation."""
    r = entry["rotation"]
    check_targets(ctx, entry)
    username = None
    if r.get("verify") == "smtp":
        username = ctx.jenkins().username(r["smtp_credential"])
        if not username:
            raise RotationError(f"Jenkins : nom d'utilisateur de {r['smtp_credential']} absent")
    log(f"  procédure : {r.get('procedure', '')}")
    log(f"  → {'test SMTP, puis ' if username else ''}{_targets_text(entry)}")
    if ctx.dry_run:
        return None
    value = ctx.prompter.secret(f"value:{entry['id']}", f"Nouvelle valeur de {entry['id']}")
    if value != value.strip() or any(c.isspace() for c in value):
        warn("la valeur saisie contient des espaces : vérifier le copier-coller "
             "(un mot de passe affiché par groupes se colle sans espaces ?)")
    if username:
        smtp = ctx.services["smtp"]
        log(f"  test SMTP avec l'identifiant {username} (jusqu'à une minute)…")
        ctx.smtp_check(smtp["host"], int(smtp["port"]), username, value)
        log("  ✓ connexion SMTP acceptée avec la nouvelle valeur")
    propagate(ctx, entry, value)
    if r.get("revoke"):
        warn(f"à faire maintenant : {r['revoke']}")
    return "valeur saisie" + (", testée en SMTP" if username else "") + " et propagée"


METHODS = {
    "forgejo-token": rotate_forgejo_token,
    "forgejo-gpg": rotate_forgejo_gpg,
    "manual-value": rotate_manual_value,
}
