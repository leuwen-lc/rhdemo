#!/usr/bin/env -S python3 -I
"""Migration des secrets vers OpenBao (docs/OPENBAO.md, ETUDE_OPENBAO.md §7).

Exécuté sur le poste, comme rotate-secrets.py. Mot de passe de l'utilisateur admin d'OpenBao
et mot de passe admin Jenkins demandés au lancement ; aucune valeur affichée ni écrite sur
le disque (sauf le fichier AppRole de fixcve-auto, mode 600).

Usage :
  openbao-migrate.py jenkins-approle        étape 1 : crée ou renouvelle le credential Jenkins
                                            « openbao-approle » (AppRole jenkins)
  openbao-migrate.py jenkins [ID...]        étape 1 : secrets des pipelines Renovate et des
                                            notifications → kv/jenkins/<ID>, puis credential
                                            Jenkins remplacé par une référence OpenBao (même ID)
  openbao-migrate.py fixcve                 étape 1 bis : credentials.sops.yaml → kv/fixcve/*,
                                            fichier AppRole ~/.config/rhdemo-fixcve/openbao-approle.json
  openbao-migrate.py cosign-approle         étape 2 : credential Jenkins « openbao-cosign-approle »
  openbao-migrate.py stagingkub             étape 3 : secrets-stagingkub.yml (SOPS) → kv/stagingkub/*
                                            et kv/stagingkub-tests/users
Options : --dry-run (lectures seulement), --inventory.

Les tokens Codeberg et la clé GPG ne sont pas recopiés (leur valeur n'est lisible que par
Jenkins) : ils sont renouvelés directement vers OpenBao par les méthodes de rotate-secrets.py.
"""
import argparse
import os
import subprocess
import sys
import xml.sax.saxutils as su

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rotation_lib import inventory as inv_mod  # noqa: E402
from rotation_lib import tools  # noqa: E402
from rotation_lib.common import Journal, Prompter, RotationError, log, warn  # noqa: E402
from rotation_lib.rotations import METHODS, Context  # noqa: E402

RHDEMO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VAULT_PKG = "com.datapipe.jenkins.vault.credentials"
FIXCVE_DIR = os.path.expanduser("~/.config/rhdemo-fixcve")

# Credentials Jenkins migrés à l'étape 1 : id -> (type, description). Les valeurs vont dans
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
    ctx.journal.append(f"openbao-approle-{role}", "rotated", f"credential Jenkins {cred_id} créé par openbao-migrate.py")
    log(f"  ✓ {cred_id} prêt, anciens secret_id détruits")


def cmd_jenkins(ctx, ids):
    ob, jk = ctx.openbao(), ctx.jenkins()
    for cred_id in ids or list(JENKINS_CREDENTIALS):
        if cred_id not in JENKINS_CREDENTIALS:
            raise RotationError(f"{cred_id} : hors du périmètre de l'étape 1 ({', '.join(JENKINS_CREDENTIALS)})")
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
                ctx.journal.append(cred_id, "rotated", f"migration OpenBao : {detail}")
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


def cmd_fixcve(ctx):
    ob = ctx.openbao()
    creds = os.path.join(FIXCVE_DIR, "credentials.sops.yaml")
    approle_path = os.path.join(FIXCVE_DIR, "openbao-approle.json")
    log("── fixcve-auto : credentials.sops.yaml → kv/fixcve/{jenkins,codeberg,nvd}")
    if ctx.dry_run:
        return
    data = yaml.safe_load(sops_decrypt(creds))
    ob.kv_put("fixcve/jenkins", {"user": data["jenkins"]["user"], "token": data["jenkins"]["token"]})
    ob.kv_put("fixcve/codeberg", {"user": data["codeberg"]["user"], "token": data["codeberg"]["token"]})
    nvd = (data.get("nvd") or {}).get("api_key")
    if nvd:
        ob.kv_put("fixcve/nvd", {"api_key": nvd})
    role_id = ob.role_id("fixcve")
    secret_id, accessor = ob.new_secret_id("fixcve")
    try:
        ob.approle_login(role_id, secret_id)
        os.makedirs(FIXCVE_DIR, mode=0o700, exist_ok=True)
        tools.approle_file_write(approle_path, role_id, secret_id)
    except (RotationError, OSError):
        ob.destroy_secret_id("fixcve", accessor)
        raise
    ctx.journal.append("openbao-approle-fixcve", "rotated", "fichier AppRole créé par openbao-migrate.py")
    log(f"  ✓ kv/fixcve/* écrit{'' if nvd else ' (pas de clé NVD)'}, {approle_path} créé (mode 600)")
    log("  Ensuite : rhDemo/scripts/fixcve-install.sh --trust (scripts modifiés), puis vérifier un")
    log("  cycle ; credentials.sops.yaml peut être supprimé après un cycle réussi (docs/OPENBAO.md).")


def cmd_stagingkub(ctx):
    ob = ctx.openbao()
    src = os.path.join(RHDEMO, "secrets", "secrets-stagingkub.yml")
    log("── stagingkub : secrets-stagingkub.yml → kv/stagingkub/{rhdemo,keycloak}, kv/stagingkub-tests/users")
    if ctx.dry_run:
        return
    d = yaml.safe_load(sops_decrypt(src))
    rh, kc = d["rhdemo"], d["keycloak"]
    ob.kv_put("stagingkub/rhdemo", {
        "db_password": rh["datasource"]["password"]["pg"],
        "oidc_client_secret": rh["client"]["registration"]["keycloak"]["client"]["secret"],
    })
    ob.kv_put("stagingkub/keycloak", {
        "db_password": kc["db"]["password"],
        "admin_user": kc["admin"].get("user") or "admin",
        "admin_password": kc["admin"]["password"],
    })
    ob.kv_put("stagingkub-tests/users", {k: str(v) for k, v in (rh.get("test") or {}).items()})
    log("  ✓ écrit. Ces valeurs figurent (chiffrées) dans l'historique Git public : les renouveler")
    log("    une fois ESO en place (rotate-secrets.py stagingkub-rhdemo-db stagingkub-keycloak-db")
    log("    stagingkub-oidc-client stagingkub-keycloak-admin stagingkub-test-users).")


def sops_decrypt(path):
    proc = subprocess.run(["sops", "decrypt", path], capture_output=True, check=False,
                          env={**os.environ, "SOPS_AGE_KEY_FILE": tools.AGE_KEY_FILE})
    if proc.returncode != 0:
        raise RotationError(f"SOPS : déchiffrement de {path} impossible")
    return proc.stdout.decode("utf-8")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["jenkins-approle", "jenkins", "fixcve", "cosign-approle", "stagingkub"])
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
