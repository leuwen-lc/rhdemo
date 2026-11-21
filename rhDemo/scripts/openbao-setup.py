#!/usr/bin/env -S python3 -I
"""Alimentation initiale d'OpenBao (docs/OPENBAO.md, installation) : credentials Jenkins,
fixcve-auto, secrets de stagingkub.

Exécuté sur le poste, comme rotate-secrets.py. Mot de passe de l'utilisateur admin d'OpenBao
(et admin Jenkins pour les commandes Jenkins) demandé au lancement ; aucune valeur affichée
ni écrite sur le disque (sauf le fichier AppRole de fixcve-auto, mode 600). Idempotent : une
valeur déjà présente dans OpenBao n'est jamais écrasée (la renouveler : rotate-secrets.py).

Usage :
  openbao-setup.py jenkins-approle        crée ou renouvelle le credential Jenkins
                                          « openbao-approle » (AppRole jenkins)
  openbao-setup.py cosign-approle         crée ou renouvelle le credential Jenkins
                                          « openbao-cosign-approle » (AppRole jenkins-cosign)
  openbao-setup.py jenkins [ID...]        secrets des pipelines Renovate et des notifications :
                                          valeur dans kv/jenkins/<ID> (demandée, ou token/clé
                                          émis directement sur Codeberg), credential Jenkins
                                          référence OpenBao du même ID (créé ou remplacé)
  openbao-setup.py fixcve                 kv/fixcve/{jenkins,codeberg,nvd} (token Jenkins demandé,
                                          token Codeberg émis), fichier AppRole
                                          ~/.config/rhdemo-fixcve/openbao-approle.json
  openbao-setup.py fixcve-nvd             ajoute ou remplace la clé API NVD (kv/fixcve/nvd)
  openbao-setup.py stagingkub             génère les secrets de stagingkub (kv/stagingkub/*,
                                          kv/stagingkub-tests/users), avant init-stagingkub.sh
  openbao-setup.py observability          génère l'admin de Grafana (kv/observability/grafana),
                                          avant install-observability.sh
Options : --dry-run (lectures seulement), --inventory.
"""
import argparse
import os
import re
import sys
import xml.sax.saxutils as su

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rotation_lib import inventory as inv_mod  # noqa: E402
from rotation_lib import tools  # noqa: E402
from rotation_lib.common import (Journal, Prompter, RotationError, log, new_password,  # noqa: E402
                                 simple_password, warn)
from rotation_lib.rotations import METHODS, Context  # noqa: E402

VAULT_PKG = "com.datapipe.jenkins.vault.credentials"
FIXCVE_DIR = os.path.expanduser("~/.config/rhdemo-fixcve")

# Credentials Jenkins lus par les pipelines via OpenBao : id -> (type, description). Les valeurs vont dans
# kv/jenkins/<id> (clé « value », ou « username »/« password »).
JENKINS_CREDENTIALS = {
    "ci-bot-forgejo-token": ("string", "Token Codeberg du bot CI (OpenBao)"),
    "renovate-forgejo-token": ("string", "Token Codeberg du bot Renovate (OpenBao)"),
    "renovate-gpg-key": ("string", "Clé GPG des commits Renovate, base64 (OpenBao)"),
    "renovate-github-token": ("string", "Token GitHub en lecture seule pour Renovate (OpenBao)"),
    "dockerhub-renovate-readonly": ("username-password", "Docker Hub en lecture seule pour Renovate (OpenBao)"),
    "notification-email": ("string", "Destinataire des notifications des pipelines (OpenBao)"),
}


def esc(text):
    return su.escape(str(text))


def vault_credential_xml(cred_id, kind, description):
    """XML d'un credential du plugin HashiCorp Vault pointant vers kv/jenkins/<id> (KV v2)."""
    common = (f"<scope>GLOBAL</scope><id>{esc(cred_id)}</id><description>{esc(description)}</description>"
              f"<path>kv/jenkins/{esc(cred_id)}</path><engineVersion>2</engineVersion>")
    if kind == "string":
        tag = f"{VAULT_PKG}.common.VaultStringCredentialImpl"
        return f"<{tag}>{common}<vaultKey>value</vaultKey></{tag}>"
    tag = f"{VAULT_PKG}.common.VaultUsernamePasswordCredentialImpl"
    return f"<{tag}>{common}<usernameKey>username</usernameKey><passwordKey>password</passwordKey></{tag}>"


def approle_credential_xml(cred_id, description, role_id, secret_id):
    tag = f"{VAULT_PKG}.VaultAppRoleCredential"
    return (f"<{tag}><scope>GLOBAL</scope><id>{esc(cred_id)}</id><description>{esc(description)}</description>"
            f"<roleId>{esc(role_id)}</roleId><secretId>{esc(secret_id)}</secretId><path>approle</path></{tag}>")


def username_password_xml(cred_id, description, username, password):
    tag = "com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl"
    return (f"<{tag}><scope>GLOBAL</scope><id>{esc(cred_id)}</id><description>{esc(description)}</description>"
            f"<username>{esc(username)}</username><password>{esc(password)}</password></{tag}>")


def replace_credential(jenkins, cred_id, new_xml, check_tag):
    """Remplace un credential en place (POST de son config.xml, changement de type accepté
    par Jenkins, vérifié le 2026-11-21), ou le crée s'il n'existe pas. Pas de suppression
    préalable : en cas d'échec, l'ancien reste intact. (Une sauvegarde par config.xml ne
    permettrait pas de le restaurer : Jenkins y masque les secrets, <secret-redacted/>.)"""
    if jenkins.exists(cred_id):
        jenkins.replace(cred_id, new_xml)
    else:
        jenkins.create(new_xml)
    if check_tag not in jenkins.config_xml(cred_id):
        raise RotationError(f"Jenkins : {cred_id} a un type inattendu après remplacement "
                            "(plugin HashiCorp Vault installé ?)")


def cmd_jenkins_approle(ctx, role="jenkins", cred_id="openbao-approle", vault_type=True):
    ob, jk = ctx.openbao(), ctx.jenkins()
    exists = jk.exists(cred_id)
    log(f"── credential Jenkins {cred_id} (AppRole {role}) : {'remplacé' if exists else 'créé'}")
    if ctx.dry_run:
        return
    role_id = ob.role_id(role)
    secret_id, accessor = ob.new_secret_id(role)
    try:
        ob.approle_login(role_id, secret_id)
        if vault_type:
            xml = approle_credential_xml(cred_id, f"AppRole OpenBao {role} (secret_id renouvelé par rotate-secrets.py)",
                                         role_id, secret_id)
            replace_credential(jk, cred_id, xml, "VaultAppRoleCredential")
        else:
            xml = username_password_xml(cred_id, f"AppRole OpenBao {role} : role_id / secret_id", role_id, secret_id)
            replace_credential(jk, cred_id, xml, "UsernamePasswordCredentialsImpl")
    except RotationError:
        ob.destroy_secret_id(role, accessor)
        raise
    for acc in ob.secret_id_accessors(role):
        if acc != accessor:
            ob.destroy_secret_id(role, acc)
    ctx.journal.append(f"openbao-approle-{role}", "rotated", f"credential Jenkins {cred_id} créé par openbao-setup.py")
    log(f"  ✓ {cred_id} prêt, anciens secret_id détruits")


def cmd_jenkins(ctx, ids):
    ob, jk = ctx.openbao(), ctx.jenkins()
    for cred_id in ids or list(JENKINS_CREDENTIALS):
        if cred_id not in JENKINS_CREDENTIALS:
            raise RotationError(f"{cred_id} : credential non géré ({', '.join(JENKINS_CREDENTIALS)})")
        kind, description = JENKINS_CREDENTIALS[cred_id]
        path = f"jenkins/{cred_id}"
        log(f"\n── {cred_id} → kv/{path}")
        stored = ob.kv_read(path, missing_ok=True)
        entry = next((e for e in ctx.inv["secrets"] if e["id"] == cred_id), None)
        automated = entry is not None and entry["rotation"]["method"] in ("forgejo-token", "forgejo-gpg")
        if ctx.dry_run:
            log(f"  {'déjà dans OpenBao' if stored else ('renouvelé vers OpenBao' if automated else 'valeur demandée')}"
                f", puis credential Jenkins remplacé par une référence OpenBao")
            continue
        if not stored or not any(stored.values()):
            if automated:
                # La valeur actuelle n'est lisible que par Jenkins : nouveau token/clé émis
                # directement vers OpenBao (cible openbao de l'inventaire).
                ob.kv_put(path, {"value": ""})
                detail = METHODS[entry["rotation"]["method"]](ctx, entry)
                ctx.journal.append(cred_id, "rotated", f"création dans OpenBao : {detail}")
            elif kind == "username-password":
                user = ctx.prompter.text(f"Nom d'utilisateur de {cred_id}")
                pw = ctx.prompter.secret(f"value:{cred_id}", f"Mot de passe ou jeton de {cred_id}")
                ob.kv_put(path, {"username": user, "password": pw})
            else:
                ob.kv_put(path, {"value": ctx.prompter.secret(f"value:{cred_id}", f"Valeur de {cred_id}")})
            log(f"  ✓ kv/{path} écrit")
        replace_credential(jk, cred_id, vault_credential_xml(cred_id, kind, description),
                           "VaultStringCredentialImpl" if kind == "string" else "VaultUsernamePasswordCredentialImpl")
        log(f"  ✓ credential Jenkins {cred_id} → OpenBao")


def _missing(ob, path, key):
    """Vrai si kv/<path> n'a pas de valeur pour `key` (absent, ou laissé vide par un échec)."""
    data = ob.kv_read(path, missing_ok=True) or {}
    if data.get(key):
        log(f"  kv/{path} déjà présent : conservé (renouvellement : rotate-secrets.py)")
        return False
    return True


def cmd_fixcve(ctx):
    ob = ctx.openbao()
    approle_path = os.path.join(FIXCVE_DIR, "openbao-approle.json")
    log("── fixcve-auto : kv/fixcve/{jenkins,codeberg,nvd}, fichier AppRole")
    if ctx.dry_run:
        return
    if _missing(ob, "fixcve/jenkins", "token"):
        # Token API du compte Jenkins dédié : créé à la main dans Jenkins (FIXCVE_AUTO.md §3)
        user = ctx.prompter.text("Utilisateur Jenkins de fixcve-auto [claude]") or "claude"
        token = ctx.prompter.secret("value:fixcve-jenkins", f"Token API Jenkins de {user}")
        ob.kv_put("fixcve/jenkins", {"user": user, "token": token})
        log("  ✓ kv/fixcve/jenkins écrit")
    if _missing(ob, "fixcve/codeberg", "token"):
        entry = inv_mod.by_id(ctx.inv, "fixcve-forgejo-token")
        # Token émis directement sur Codeberg vers kv/fixcve/codeberg (cible de l'inventaire)
        ob.kv_put("fixcve/codeberg", {"user": entry["rotation"]["account"], "token": ""})
        detail = METHODS[entry["rotation"]["method"]](ctx, entry)
        ctx.journal.append(entry["id"], "rotated", f"création dans OpenBao : {detail}")
        log("  ✓ kv/fixcve/codeberg écrit")
    if ob.kv_read("fixcve/nvd", missing_ok=True) is None and \
            ctx.prompter.confirm("Enregistrer une clé API NVD (vérification locale Dependency-Check) ?"):
        cmd_fixcve_nvd(ctx)
    if os.path.exists(approle_path):
        log(f"  {approle_path} déjà présent : conservé (renouvellement : rotate-secrets.py openbao-approle-fixcve)")
    else:
        role_id = ob.role_id("fixcve")
        secret_id, accessor = ob.new_secret_id("fixcve")
        try:
            ob.approle_login(role_id, secret_id)
            os.makedirs(FIXCVE_DIR, mode=0o700, exist_ok=True)
            tools.approle_file_write(approle_path, role_id, secret_id)
        except (RotationError, OSError):
            ob.destroy_secret_id("fixcve", accessor)
            raise
        ctx.journal.append("openbao-approle-fixcve", "rotated", "fichier AppRole créé par openbao-setup.py")
        log(f"  ✓ {approle_path} créé (mode 600)")
    log("  Ensuite : rhDemo/scripts/fixcve-install.sh (provisionnement, --trust).")


def cmd_fixcve_nvd(ctx):
    ob = ctx.openbao()
    log("── clé API NVD → kv/fixcve/nvd (https://nvd.nist.gov/developers/request-an-api-key)")
    if ctx.dry_run:
        return
    key = ctx.prompter.secret("value:fixcve-nvd", "Clé API NVD")
    if not re.fullmatch(r"[A-Za-z0-9-]{20,64}", key):
        raise RotationError("format de clé NVD inattendu")
    ob.kv_put("fixcve/nvd", {"api_key": key})
    log("  ✓ kv/fixcve/nvd écrit")


# Utilisateurs de test de stagingkub (realm RHDemo), créés par init-keycloak-stagingkub.sh
TEST_USERS = {"admin": "rhdemo-admin", "maj": "rhdemo-maj", "consult": "rhdemo-consult"}


def cmd_stagingkub(ctx):
    """Valeurs générées, jamais saisies. À lancer avant le premier déploiement : PostgreSQL ne
    prend son mot de passe qu'à l'initialisation de sa base, Keycloak son admin au premier
    démarrage."""
    ob = ctx.openbao()
    entry = inv_mod.by_id(ctx.inv, "stagingkub-test-users")
    length = int((entry["rotation"].get("password") or {}).get("length", 12))
    log("── stagingkub : génération de kv/stagingkub/{rhdemo,keycloak}, kv/stagingkub-tests/users")
    if ctx.dry_run:
        return
    if _missing(ob, "stagingkub/rhdemo", "db_password"):
        ob.kv_put("stagingkub/rhdemo", {"db_password": new_password(), "oidc_client_secret": new_password()})
        log("  ✓ kv/stagingkub/rhdemo généré")
    if _missing(ob, "stagingkub/keycloak", "admin_password"):
        ob.kv_put("stagingkub/keycloak", {"db_password": new_password(), "admin_user": "admin",
                                          "admin_password": new_password()})
        log("  ✓ kv/stagingkub/keycloak généré")
    if _missing(ob, "stagingkub-tests/users", "pwduseradmin"):
        users = {}
        for role, name in TEST_USERS.items():
            users[f"iduser{role}"] = name
            users[f"pwduser{role}"] = simple_password(length)
        ob.kv_put("stagingkub-tests/users", users)
        log("  ✓ kv/stagingkub-tests/users généré")
    log("  Ensuite : infra/stagingkub/scripts/init-stagingkub.sh (ESO recopie ces valeurs dans le cluster).")


def cmd_observability(ctx):
    """Admin de Grafana, recopié dans le Secret grafana-admin de loki-stack par ESO."""
    ob = ctx.openbao()
    log("── observabilité : génération de kv/observability/grafana")
    if ctx.dry_run:
        return
    if _missing(ob, "observability/grafana", "admin_password"):
        ob.kv_put("observability/grafana", {"admin_user": "admin", "admin_password": new_password()})
        log("  ✓ kv/observability/grafana généré")
    log("  Ensuite : infra/stagingkub/scripts/components/install-external-secrets.sh (Secret grafana-admin),")
    log("  puis install-observability.sh ou install-or-upgrade-grafana.sh.")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["jenkins-approle", "cosign-approle", "jenkins", "fixcve", "fixcve-nvd",
                                       "stagingkub", "observability"])
    p.add_argument("ids", nargs="*")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--inventory", default=inv_mod.DEFAULT_PATH)
    args = p.parse_args(argv)
    prompter = Prompter()
    try:
        inv = inv_mod.load(args.inventory)
        ctx = Context(inv, prompter, Journal(), dry_run=args.dry_run)
        try:
            if args.command == "jenkins-approle":
                cmd_jenkins_approle(ctx)
            elif args.command == "cosign-approle":
                cmd_jenkins_approle(ctx, role="jenkins-cosign", cred_id="openbao-cosign-approle", vault_type=False)
            elif args.command == "jenkins":
                cmd_jenkins(ctx, args.ids)
            elif args.command == "fixcve":
                cmd_fixcve(ctx)
            elif args.command == "fixcve-nvd":
                cmd_fixcve_nvd(ctx)
            elif args.command == "observability":
                cmd_observability(ctx)
            else:
                cmd_stagingkub(ctx)
        finally:
            ctx.close()
            prompter.forget()
    except RotationError as exc:
        warn(str(exc))
        return 2
    except KeyboardInterrupt:
        warn("interrompu")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
