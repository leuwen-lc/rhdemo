"""Cycle de rotation par méthode : contrôler les cibles, créer, vérifier, propager, révoquer.

Ordre retenu (mode normal) : le nouveau secret est vérifié auprès du fournisseur AVANT d'être
propagé, et l'ancien n'est révoqué qu'après une propagation réussie. Si la vérification ou la
propagation échoue sans qu'aucune cible n'ait été modifiée, le nouveau secret est supprimé.

Mode urgence (--emergency, ctx.emergency) : pour les méthodes dont l'ancien secret se révoque à
part (tokens et clé Codeberg, secret_id AppRole, tokens Kubernetes), la révocation passe AVANT la
création : mieux vaut une CI cassée qu'un attaquant actif. Tous les tokens d'un compte bot sont
alors révoqués, sans confirmation. Les mots de passe changés en place (PostgreSQL, Keycloak,
Grafana) invalident l'ancien dès le changement ; un échec ramène l'ancien, signalé comme tel.
"""
import base64
import os
import time

from .common import (SIMPLE_PUNCTUATION, RotationError, Skipped, http, log, new_password,
                     simple_password, stamp, warn)
from .forgejo import Forgejo
from .smtp import smtp_login
from .jenkins import Jenkins
from .keycloak import Keycloak
from .openbao import OpenBao
from . import k8s, tools


class Context:
    """Clients et paramètres partagés par les rotations d'une session (créés à la demande)."""

    def __init__(self, inventory, prompter, journal, dry_run=False, if_missing=False, emergency=False):
        self.inv = inventory
        self.prompter = prompter
        self.journal = journal
        self.dry_run = dry_run
        self.if_missing = if_missing   # k8s-sa-token : ne créer un token que s'il n'y en a aucun
        self.emergency = emergency     # révoquer l'ancien avant de créer le nouveau
        self._jenkins = None
        self._forgejo = None
        self._openbao = None
        self._keycloak = None
        self._port_forward = None
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

    def keycloak(self):
        """Session d'administration Keycloak de stagingkub : identifiants lus dans OpenBao,
        accès par port-forward (arrêté par close())."""
        if self._keycloak is None:
            cfg = self.services["keycloak"]
            creds = self.openbao().kv_read(cfg["admin_kv_path"])
            self._port_forward = tools.PortForward(cfg["namespace"], cfg["target"], cfg.get("port", 8080))
            client = Keycloak(self._port_forward.url, creds["admin_user"], creds["admin_password"],
                              cfg.get("admin_realm", "master"))
            client.token()
            self._keycloak = client
        return self._keycloak

    def forget_session(self, name):
        """Après le changement manuel d'un identifiant maître (rotation: session), le
        redemander à la prochaine connexion."""
        if name == "jenkins":
            self._jenkins = None
            self.prompter.drop("jenkins")

    def close(self):
        if self._port_forward is not None:
            self._port_forward.close()
            self._port_forward = None
            self._keycloak = None
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
        elif t["kind"] == "openbao":
            if ctx.openbao().kv_read(t["path"], missing_ok=True) is None:
                raise RotationError(f"OpenBao : kv/{t['path']} absent (scripts/openbao-setup.py)")
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


def _revoke_first(items, revoke, name):
    """Urgence : révoque les anciens secrets avant toute création."""
    for item in items:
        revoke(item)
        log(f"  révoqué (urgence) : {name(item)}")


# --- méthodes ------------------------------------------------------------------------------

def rotate_forgejo_token(ctx, entry):
    r = entry["rotation"]
    user, prefix, scopes = r["account"], r["token_prefix"], r["scopes"]
    repo = ctx.services["forgejo"].get("repo") if r.get("needs_push", True) else None
    fj = ctx.forgejo()

    check_targets(ctx, entry)
    tokens = fj.list_tokens(user)
    managed = [t for t in tokens if t["name"].startswith(prefix + "-")]
    revoke = list(tokens) if ctx.emergency else list(managed)   # urgence : tout token du bot
    for t in tokens:
        if t in revoke:
            continue
        if ctx.prompter.confirm(f"{user} : token non géré « {t['name']} » "
                                f"({', '.join(t.get('scopes') or [])}), le révoquer aussi ?"):
            revoke.append(t)
    for t in revoke if not ctx.emergency else []:
        old_scopes = set(t.get("scopes") or [])
        if old_scopes and old_scopes != set(scopes):
            if not ctx.prompter.confirm(f"{user} : « {t['name']} » a les portées "
                                        f"{', '.join(sorted(old_scopes))}, l'inventaire demande "
                                        f"{', '.join(sorted(scopes))}. Continuer avec l'inventaire ?"):
                raise RotationError(f"portées divergentes pour {user} : corriger l'inventaire")
    name = f"{prefix}-{stamp()}"
    log(f"  nouveau token {name} ({', '.join(scopes)}) → {_targets_text(entry)}")
    log(f"  à révoquer{' AVANT la création (urgence)' if ctx.emergency else ''} : "
        f"{', '.join(t['name'] for t in revoke) or 'aucun'}")
    if ctx.dry_run:
        return None

    if ctx.emergency:
        _revoke_first(revoke, lambda t: fj.delete_token(user, t["id"]), lambda t: t["name"])
    token_id, value = fj.create_token(user, name, scopes)

    def rollback():
        fj.delete_token(user, token_id)

    try:
        fj.check_token(value, user, repo)
    except RotationError:
        rollback()
        state = "anciens tokens déjà révoqués" if ctx.emergency else "rien d'autre n'a changé"
        warn(f"token {name} supprimé (vérification échouée, {state})")
        raise
    _propagate_or_rollback(ctx, entry, value, rollback, f"token {name}")
    for t in revoke if not ctx.emergency else []:
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
    log(f"  clés à retirer de Codeberg{' AVANT la création (urgence)' if ctx.emergency else ''} : "
        f"{', '.join(k['key_id'] for k in old_keys) or 'aucune'}")
    if ctx.dry_run:
        return None
    if ctx.emergency:
        _revoke_first(old_keys, lambda k: fj.delete_gpg_key(user, k["id"]), lambda k: k["key_id"])

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
    for k in old_keys if not ctx.emergency else []:
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
    if ctx.emergency and r.get("revoke"):
        warn(f"urgence, à faire D'ABORD : {r['revoke']}")
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
    if r.get("revoke") and not ctx.emergency:
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
    log(f"  secret_id à détruire {'AVANT la création (urgence)' if ctx.emergency else 'ensuite'} : {len(old)}")
    if ctx.dry_run:
        return None
    if ctx.emergency:
        _revoke_first(old, lambda acc: ob.destroy_secret_id(role, acc), lambda acc: "secret_id")
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
    for acc in old if not ctx.emergency else []:
        ob.destroy_secret_id(role, acc)
    return f"secret_id renouvelé pour {role}, {len(old)} ancien(s) détruit(s)"


def _secret_value(namespace, name, key):
    jkey = key.replace(".", "\\.")
    out = tools.kubectl("get", "secret", name, "-n", namespace, "-o", f"jsonpath={{.data.{jkey}}}")
    return base64.b64decode(out.strip()).decode("utf-8") if out.strip() else ""


def _force_sync(r, wait_value, timeout=90, poll=3):
    """Force la synchronisation ESO et attend que le Secret porte la nouvelle valeur
    (égalité, ou présence dans un fichier généré par gabarit si k8s_match: contains)."""
    ns = r["namespace"]
    for es in r["external_secrets"]:
        tools.kubectl("annotate", "externalsecret", es, "-n", ns, f"force-sync={time.time_ns()}",
                      "--overwrite")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = _secret_value(ns, r["k8s_secret"], r.get("k8s_key", "password"))
        if current == wait_value or (r.get("k8s_match") == "contains" and wait_value in current):
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
    failed = _restart(ns, r["restart"])
    if failed:
        raise RotationError(f"mot de passe changé, mais redémarrage à terminer à la main : {', '.join(failed)}")
    return f"mot de passe {r['db_user']} renouvelé, {', '.join(r['restart'])} redémarrés"


def _kv_value(ob, path, key):
    value = (ob.kv_read(path) or {}).get(key)
    if value is None:
        raise RotationError(f"OpenBao : kv/{path} ({key}) absent")
    return value


def _restart(ns, targets):
    failed = []
    for target in targets:
        try:
            tools.kubectl("rollout", "restart", target, "-n", ns)
            tools.kubectl("rollout", "status", target, "-n", ns, "--timeout=300s", timeout=330)
            log(f"  ✓ {target} redémarré")
        except RotationError as exc:
            failed.append(target)
            warn(f"{target} : {exc}")
    return failed


def rotate_keycloak_client_secret(ctx, entry):
    """Secret du client OIDC : KV, synchronisation ESO forcée, valeur imposée dans Keycloak,
    redémarrage de l'application. Retour arrière (Keycloak puis KV) en cas d'échec."""
    r = entry["rotation"]
    ob = ctx.openbao()
    ns = r["namespace"]
    old = _kv_value(ob, r["kv_path"], r["kv_key"])
    for es in r["external_secrets"]:
        tools.kubectl("get", "externalsecret", es, "-n", ns)
    kc = ctx.keycloak()
    if kc.client_secret(r["realm"], r["client_id"]) != old:
        warn(f"le secret du client {r['client_id']} diffère déjà de kv/{r['kv_path']} : "
             "la rotation réaligne les deux")
    log(f"  kv/{r['kv_path']} {r['kv_key']} → ESO ({', '.join(r['external_secrets'])}) → "
        f"client {r['client_id']} ({r['realm']}) → redémarrage {', '.join(r['restart'])}")
    if ctx.dry_run:
        return None
    new = new_password()

    ob.kv_set(r["kv_path"], r["kv_key"], new)
    try:
        _force_sync(r, new)
        kc.set_client_secret(r["realm"], r["client_id"], new)
    except RotationError:
        warn("échec : retour à l'ancien secret dans Keycloak et OpenBao")
        for step in (lambda: kc.set_client_secret(r["realm"], r["client_id"], old),
                     lambda: ob.kv_set(r["kv_path"], r["kv_key"], old),
                     lambda: _force_sync(r, old)):
            try:
                step()
            except RotationError as exc:
                warn(f"retour arrière incomplet ({exc}) : comparer kv/{r['kv_path']} et le client {r['client_id']}")
        raise
    log("  ✓ secret changé dans OpenBao, le Secret et Keycloak")
    failed = _restart(ns, r["restart"])
    if failed:
        raise RotationError(f"secret changé, mais redémarrage à terminer à la main : {', '.join(failed)}")
    return f"secret du client {r['client_id']} renouvelé, {', '.join(r['restart'])} redémarrés"


def _rotate_keycloak_password(ctx, kc, realm, username, kv_path, kv_key, old, generate=new_password):
    """Un mot de passe Keycloak : KV d'abord (OpenBao garde toujours une valeur connue),
    puis Keycloak, puis connexion de vérification. Sinon retour à l'ancien des deux côtés."""
    ob = ctx.openbao()
    new = generate()
    is_admin = realm == kc.admin_realm and username.lower() == kc.admin_user.lower()
    ob.kv_set(kv_path, kv_key, new)
    changed = False
    try:
        kc.set_password(realm, username, new)
        changed = True
        if is_admin:
            kc.admin_password = new   # jetons suivants, retour arrière compris
        if not kc.check_login(realm, username, new):
            warn(f"{username} : mot de passe accepté, mais une action requise est en attente dans Keycloak")
    except RotationError:
        warn(f"{username} : échec, retour à l'ancien mot de passe")
        try:
            if changed:
                kc.set_password(realm, username, old)
                if is_admin:
                    kc.admin_password = old
        except RotationError as exc:
            warn(f"Keycloak : retour arrière impossible ({exc}) : mot de passe de {username} à "
                 f"redéfinir dans la console, la nouvelle valeur reste dans kv/{kv_path}")
            raise
        try:
            ob.kv_set(kv_path, kv_key, old)
        except RotationError as exc:
            warn(f"retour arrière incomplet ({exc}) : comparer kv/{kv_path} ({kv_key}) et Keycloak")
        raise
    return new


def rotate_keycloak_admin(ctx, entry):
    """Administrateur Keycloak : KEYCLOAK_ADMIN_PASSWORD ne sert qu'au premier démarrage, le
    mot de passe est donc changé par l'API, puis le Secret resynchronisé pour rester cohérent."""
    r = entry["rotation"]
    ob = ctx.openbao()
    creds = ob.kv_read(r["kv_path"]) or {}
    user, old = creds.get(r["user_key"]), creds.get(r["kv_key"])
    if not user or old is None:
        raise RotationError(f"OpenBao : kv/{r['kv_path']} ({r['user_key']}, {r['kv_key']}) absent")
    for es in r["external_secrets"]:
        tools.kubectl("get", "externalsecret", es, "-n", r["namespace"])
    kc = ctx.keycloak()          # connexion avec l'ancien mot de passe : valeur du KV vérifiée
    log(f"  kv/{r['kv_path']} {r['kv_key']} → Keycloak {user} ({r['realm']}) → ESO "
        f"({', '.join(r['external_secrets'])})")
    if ctx.dry_run:
        return None
    new = _rotate_keycloak_password(ctx, kc, r["realm"], user, r["kv_path"], r["kv_key"], old)
    log(f"  ✓ mot de passe de {user} changé dans OpenBao et Keycloak")
    try:
        _force_sync(r, new)
    except RotationError as exc:
        warn(f"{exc} : le Secret se resynchronisera seul (refreshInterval)")
        return f"mot de passe {user} renouvelé, Secret non encore resynchronisé"
    return f"mot de passe {user} renouvelé"


def rotate_keycloak_users(ctx, entry):
    """Utilisateurs de test : un mot de passe par utilisateur, chacun vérifié par une connexion."""
    r = entry["rotation"]
    ob = ctx.openbao()
    data = ob.kv_read(r["kv_path"]) or {}
    users = []
    for u in r["users"]:
        name, old = data.get(u["user_key"]), data.get(u["password_key"])
        if not name or old is None:
            raise RotationError(f"OpenBao : kv/{r['kv_path']} ({u['user_key']}, {u['password_key']}) absent")
        users.append((name, u["password_key"], old))
    kc = ctx.keycloak()
    for name, _, _ in users:
        kc.user_id(r["realm"], name)
    spec = r.get("password") or {}
    length = int(spec.get("length", 12))
    punctuation = spec.get("punctuation", SIMPLE_PUNCTUATION)

    def generate():
        return simple_password(length, punctuation)

    generate()   # paramètres invalides détectés avant toute modification
    log(f"  kv/{r['kv_path']} → Keycloak ({r['realm']}) : {', '.join(n for n, _, _ in users)} "
        f"({length} caractères)")
    if ctx.dry_run:
        return None
    done = []
    for name, key, old in users:
        try:
            _rotate_keycloak_password(ctx, kc, r["realm"], name, r["kv_path"], key, old, generate)
        except RotationError as exc:
            raise RotationError(f"{exc} (déjà renouvelés : {', '.join(done) or 'aucun'})") from None
        done.append(name)
        log(f"  ✓ {name}")
    return f"mots de passe renouvelés : {', '.join(done)}"


def _grafana_login(r, user, password):
    """Connexion à l'API de Grafana (port-forward vers son Service) avec ces identifiants."""
    pf = tools.PortForward(r["namespace"], r["service"], r.get("port", 80))
    try:
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        status, _ = http("GET", f"{pf.url}/api/user", {"Authorization": f"Basic {token}"})
    finally:
        pf.close()
    if status != 200:
        raise RotationError(f"Grafana : connexion de {user} refusée ({status})")


def rotate_grafana_admin(ctx, entry):
    """Admin de Grafana : KV, synchronisation ESO forcée, redémarrage (sans stockage persistant,
    Grafana reprend le mot de passe du Secret à chaque démarrage), connexion de vérification.
    Retour à l'ancien mot de passe en cas d'échec."""
    r = entry["rotation"]
    ob = ctx.openbao()
    ns = r["namespace"]
    data = ob.kv_read(r["kv_path"]) or {}
    user, old = data.get(r["user_key"]), data.get(r["kv_key"])
    if not user or old is None:
        raise RotationError(f"OpenBao : kv/{r['kv_path']} ({r['user_key']}, {r['kv_key']}) absent")
    for es in r["external_secrets"]:
        tools.kubectl("get", "externalsecret", es, "-n", ns)
    for target in r["restart"]:
        tools.kubectl("get", target, "-n", ns)
    log(f"  kv/{r['kv_path']} {r['kv_key']} → ESO ({', '.join(r['external_secrets'])}) → "
        f"redémarrage {', '.join(r['restart'])} → connexion de {user}")
    if ctx.dry_run:
        return None
    new = new_password()
    ob.kv_set(r["kv_path"], r["kv_key"], new)
    try:
        _force_sync(r, new)
        failed = _restart(ns, r["restart"])
        if failed:
            raise RotationError(f"redémarrage en échec : {', '.join(failed)}")
        _grafana_login(r, user, new)
    except RotationError:
        warn("échec : retour à l'ancien mot de passe dans OpenBao, resynchronisation et redémarrage")
        try:
            ob.kv_set(r["kv_path"], r["kv_key"], old)
            _force_sync(r, old)
            _restart(ns, r["restart"])
        except RotationError as exc:
            warn(f"retour arrière incomplet ({exc}) : comparer kv/{r['kv_path']} et le Secret {r['k8s_secret']}")
        raise
    return f"mot de passe {user} de Grafana renouvelé"


def rotate_k8s_sa_token(ctx, entry):
    """Token d'un ServiceAccount de stagingkub, propagé en kubeconfig dans un credential Jenkins
    « Secret file » : nouveau Secret de token, vérification (identité et droits attendus), mise à
    jour (ou création) du credential, puis suppression des anciens Secrets du même compte.
    Aucun kubeconfig n'est écrit sur le disque. Avec --if-missing (init-stagingkub.sh), ne fait
    rien si un token existe déjà."""
    r = entry["rotation"]
    ns, sa = r["namespace"], r["service_account"]
    if r.get("kube_context") and k8s.current_context() != r["kube_context"]:
        raise RotationError(f"contexte kubectl courant différent de {r['kube_context']} "
                            f"(kubectl config use-context {r['kube_context']})")
    old = k8s.token_secrets(ns, sa)
    if ctx.if_missing and old:
        return Skipped(f"token existant ({', '.join(old)}), rien à faire")
    jk = ctx.jenkins()
    missing = []
    for t in entry["targets"]:
        if jk.exists(t["credential"]):
            jk.read(t["credential"], "file")
        else:
            missing.append(t["credential"])
    name = f"{r['secret_prefix']}-{stamp()}"
    log(f"  nouveau Secret {name} (ServiceAccount {sa}) → vérification → {_targets_text(entry)}"
        + (f" (à créer : {', '.join(missing)})" if missing else ""))
    log(f"  Secrets à supprimer {'AVANT la création (urgence)' if ctx.emergency else 'ensuite'} : "
        f"{', '.join(old) or 'aucun'}")
    if ctx.dry_run:
        return None

    if ctx.emergency:
        _revoke_first(old, lambda n: k8s.delete_secret(ns, n), lambda n: f"Secret {n}")
    k8s.create_token_secret(ns, sa, name)

    def rollback():
        k8s.delete_secret(ns, name)

    try:
        token, ca = k8s.wait_token(ns, name)
        probe = k8s.kubeconfig(k8s.admin_server(), ca, token, sa, ns, r["cluster"])
        k8s.verify(probe, ns, sa, r.get("allowed", []), r.get("denied", []))
    except RotationError:
        rollback()
        warn(f"Secret {name} supprimé (vérification échouée, rien d'autre n'a changé)")
        raise
    log(f"  ✓ token vérifié : {sa}, {len(r.get('allowed', []))} droit(s) accordé(s), "
        f"{len(r.get('denied', []))} refusé(s) comme attendu")
    header = (f"# Kubeconfig du ServiceAccount {sa}, généré par rotate-secrets.py "
              f"({entry['id']}, Secret {name}).\n")
    text = k8s.kubeconfig(r["server"], ca, token, sa, ns, r["cluster"], header)
    updated = []
    try:
        for t in entry["targets"]:
            if t["credential"] in missing:
                jk.create_file(t["credential"], entry["label"], "kubeconfig", text)
            else:
                jk.update(t["credential"], "file", text)
            updated.append(f"Jenkins {t['credential']}")
    except RotationError:
        if updated:
            warn(f"propagation partielle ({', '.join(updated)}) : Secret {name} conservé, "
                 "anciens Secrets NON supprimés, terminer à la main")
        else:
            rollback()
            warn(f"Secret {name} supprimé (aucune cible modifiée)")
        raise
    for n in old if not ctx.emergency else []:
        k8s.delete_secret(ns, n)
        log(f"  supprimé : Secret {n} (ancien token invalide)")
    return f"Secret {name}, supprimés : {', '.join(old) or 'aucun'}"


METHODS = {
    "forgejo-token": rotate_forgejo_token,
    "forgejo-gpg": rotate_forgejo_gpg,
    "manual-value": rotate_manual_value,
    "openbao-approle": rotate_openbao_approle,
    "postgres-password": rotate_postgres_password,
    "keycloak-client-secret": rotate_keycloak_client_secret,
    "keycloak-admin": rotate_keycloak_admin,
    "keycloak-users": rotate_keycloak_users,
    "grafana-admin": rotate_grafana_admin,
    "k8s-sa-token": rotate_k8s_sa_token,
}
