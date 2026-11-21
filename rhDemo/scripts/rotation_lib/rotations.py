"""Cycle de rotation par méthode : contrôler les cibles, créer, vérifier, propager, révoquer.

Ordre retenu (mode normal) : le nouveau secret est vérifié auprès du fournisseur AVANT d'être
propagé, et l'ancien n'est révoqué qu'après une propagation réussie. Si la vérification ou la
propagation échoue sans qu'aucune cible n'ait été modifiée, le nouveau secret est supprimé.
"""
import base64
import os
import time

from .common import RotationError, log, new_password, stamp, warn
from .forgejo import Forgejo
from .smtp import smtp_login
from .jenkins import Jenkins
from .openbao import OpenBao
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
        self._openbao = None
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

    def openbao(self):
        """Session administrateur (userpass, jeton d'une heure), révoquée par close()."""
        if self._openbao is None:
            cfg = self.services["openbao"]
            user = cfg.get("admin_user", "admin")
            client = OpenBao(cfg["url"], openbao_ca(cfg))
            password = self.prompter.secret("openbao", f"Mot de passe OpenBao de {user}")
            client.login_userpass(user, password)
            self._openbao = client
        return self._openbao

    def close(self):
        if self._openbao is not None:
            try:
                self._openbao.revoke_self()
            except RotationError:
                pass
            self._openbao = None


def openbao_ca(cfg):
    """Chemin de l'autorité locale : absolu, ou relatif à la racine rhDemo/."""
    ca = os.path.expanduser(cfg.get("ca_cert", ""))
    if ca and not os.path.isabs(ca):
        ca = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ca)
    return ca or None



# --- cibles (consommateurs du secret) ------------------------------------------------------

def check_targets(ctx, entry):
    """Échoue avant toute création si une cible est inaccessible ou de mauvais type."""
    for t in entry.get("targets", []):
        if t["kind"] == "jenkins":
            ctx.jenkins().read(t["credential"], t["type"])
        elif t["kind"] == "sops":
            tools.sops_get(os.path.expanduser(t["file"]), t["key"])
        elif t["kind"] == "openbao":
            if ctx.openbao().kv_read(t["path"], missing_ok=True) is None:
                raise RotationError(f"OpenBao : kv/{t['path']} absent (migration faite ? scripts/openbao-migrate.py)")
        elif t["kind"] == "approle-file":
            tools.approle_file_read(os.path.expanduser(t["file"]))
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
            elif t["kind"] == "openbao":
                ctx.openbao().kv_set(t["path"], t["key"], value)
                updated.append(f"OpenBao kv/{t['path']} {t['key']}")
            elif t["kind"] == "approle-file":
                path = os.path.expanduser(t["file"])
                current = tools.approle_file_read(path)
                tools.approle_file_write(path, current["role_id"], value)
                updated.append(f"fichier AppRole {t['file']}")
    except RotationError as exc:
        exc.updated = updated
        raise
    return updated


def _target_text(t):
    if t["kind"] == "jenkins":
        return f"Jenkins {t['credential']}"
    if t["kind"] == "sops":
        return f"SOPS {t['file']} {t['key']}"
    if t["kind"] == "openbao":
        return f"OpenBao kv/{t['path']} {t['key']}"
    return f"fichier AppRole {t['file']}"


def _targets_text(entry):
    return ", ".join(_target_text(t) for t in entry.get("targets", []))


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


def rotate_openbao_approle(ctx, entry):
    """Nouveau secret_id AppRole : émis par OpenBao, vérifié par une connexion, propagé
    (credential Jenkins « Vault App Role » ou fichier local), puis les anciens détruits."""
    role = entry["rotation"]["role"]
    ob = ctx.openbao()
    check_targets(ctx, entry)
    role_id = ob.role_id(role)
    old = ob.secret_id_accessors(role)
    log(f"  nouveau secret_id pour l'AppRole {role} → {_targets_text(entry)}")
    log(f"  secret_id à détruire ensuite : {len(old)}")
    if ctx.dry_run:
        return None
    secret_id, accessor = ob.new_secret_id(role)

    def rollback():
        ob.destroy_secret_id(role, accessor)

    try:
        ob.approle_login(role_id, secret_id)
    except RotationError:
        rollback()
        warn("secret_id détruit (connexion de vérification refusée, rien d'autre n'a changé)")
        raise
    _propagate_or_rollback(ctx, entry, secret_id, rollback, "secret_id")
    for acc in old:
        ob.destroy_secret_id(role, acc)
    return f"secret_id renouvelé pour {role}, {len(old)} ancien(s) détruit(s)"


def _secret_value(namespace, name, key):
    out = tools.kubectl("get", "secret", name, "-n", namespace, "-o", f"jsonpath={{.data.{key}}}")
    return base64.b64decode(out.strip()).decode("utf-8") if out.strip() else ""


def _force_sync(r, wait_value, timeout=90, poll=3):
    """Force la synchronisation ESO et attend que le Secret porte la nouvelle valeur."""
    ns = r["namespace"]
    for es in r["external_secrets"]:
        tools.kubectl("annotate", "externalsecret", es, "-n", ns, f"force-sync={time.time_ns()}",
                      "--overwrite")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _secret_value(ns, r["k8s_secret"], r.get("k8s_key", "password")) == wait_value:
            return
        time.sleep(poll)
    raise RotationError(f"ESO : Secret {r['k8s_secret']} non synchronisé après {timeout} s")


def _alter_role(r, password):
    """ALTER ROLE par le socket local du pod (authentification locale du conteneur
    PostgreSQL), mot de passe passé sur l'entrée standard de psql, jamais en argument."""
    sql = f'ALTER ROLE "{r["db_user"]}" PASSWORD \'{password}\';\n'
    tools.kubectl("exec", "-i", "-n", r["namespace"], r["pod"], "-c", r.get("container", "postgresql"),
                  "--", "psql", "-v", "ON_ERROR_STOP=1", "-q", "-U", r["db_user"], "-d", r["database"],
                  stdin=sql)


def rotate_postgres_password(ctx, entry):
    """Étape 4 d'ETUDE_OPENBAO (§7.2) : KV, synchronisation ESO forcée, ALTER ROLE, redémarrages."""
    r = entry["rotation"]
    ob = ctx.openbao()
    ns = r["namespace"]
    old = (ob.kv_read(r["kv_path"]) or {}).get(r["kv_key"])
    if old is None:
        raise RotationError(f"OpenBao : kv/{r['kv_path']} ({r['kv_key']}) absent")
    tools.kubectl("get", "pod", r["pod"], "-n", ns)
    for es in r["external_secrets"]:
        tools.kubectl("get", "externalsecret", es, "-n", ns)
    log(f"  kv/{r['kv_path']} {r['kv_key']} → ESO ({', '.join(r['external_secrets'])}) → "
        f"ALTER ROLE {r['db_user']} ({r['pod']}) → redémarrage {', '.join(r['restart'])}")
    if ctx.dry_run:
        return None
    new = new_password()   # URL-safe : aucun guillemet à échapper dans le SQL

    def revert(reason):
        warn(f"{reason} : retour à l'ancien mot de passe dans OpenBao et resynchronisation")
        try:
            ob.kv_set(r["kv_path"], r["kv_key"], old)
            _force_sync(r, old)
        except RotationError as exc:
            warn(f"retour arrière incomplet ({exc}) : vérifier kv/{r['kv_path']} et le Secret {r['k8s_secret']}")

    ob.kv_set(r["kv_path"], r["kv_key"], new)
    try:
        _force_sync(r, new)
        _alter_role(r, new)
    except RotationError:
        revert("échec avant ou pendant ALTER ROLE")
        raise
    log("  ✓ mot de passe changé dans OpenBao, le Secret et PostgreSQL")
    failed = []
    for target in r["restart"]:
        try:
            tools.kubectl("rollout", "restart", target, "-n", ns)
            tools.kubectl("rollout", "status", target, "-n", ns, "--timeout=300s", timeout=330)
            log(f"  ✓ {target} redémarré")
        except RotationError as exc:
            failed.append(target)
            warn(f"{target} : {exc}")
    if failed:
        raise RotationError(f"mot de passe changé, mais redémarrage à terminer à la main : {', '.join(failed)}")
    return f"mot de passe {r['db_user']} renouvelé, {', '.join(r['restart'])} redémarrés"


METHODS = {
    "forgejo-token": rotate_forgejo_token,
    "forgejo-gpg": rotate_forgejo_gpg,
    "manual-value": rotate_manual_value,
    "openbao-approle": rotate_openbao_approle,
    "postgres-password": rotate_postgres_password,
}
