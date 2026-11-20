"""Codeberg (Forgejo) : tokens d'accès et clés GPG des comptes bots.

La gestion des tokens exige une authentification par mot de passe (un token ne peut pas en créer
un autre) et, avec la 2FA, le code TOTP dans l'en-tête X-Forgejo-OTP.
"""
import base64
import json
import urllib.parse

from .common import RotationError, http, short


class Forgejo:
    def __init__(self, url, prompter):
        self.url = url.rstrip("/")
        self.prompter = prompter

    @staticmethod
    def _decode(body):
        if not body:
            return None
        try:
            return json.loads(body)
        except ValueError:
            return body.decode("utf-8", "replace")

    def basic(self, method, path, user, body=None, expect=(200,)):
        """Appel authentifié par le mot de passe du compte (+ TOTP).

        Sur un 401, le corps de la réponse n'est jamais affiché : Forgejo y recopie la valeur
        saisie. Seul un refus explicite du code TOTP fait redemander un code."""
        key = f"codeberg:{user}"
        password = self.prompter.secret(key, f"Mot de passe Codeberg de {user}")
        cred = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        status, data = None, b""
        for attempt in range(2):
            headers = {"Authorization": f"Basic {cred}", "Accept": "application/json"}
            otp = self.prompter.otp(user, fresh=attempt > 0)
            if otp:
                headers["X-Forgejo-OTP"] = otp
                headers["X-Gitea-OTP"] = otp
            status, data = http(method, self.url + "/api/v1" + path, headers, body)
            if status != 401:
                break
            if b"otp" not in (data or b"").lower():
                self.prompter.drop(key)
                raise RotationError(f"Codeberg : authentification de {user} refusée "
                                    "(mot de passe incorrect ?)")
        if status == 401:
            raise RotationError(f"Codeberg : code TOTP de {user} refusé")
        if status not in expect:
            raise RotationError(f"Codeberg : {method} {path} ({user}) → {status} {short(data)}")
        return self._decode(data)

    def with_token(self, method, path, token, body=None):
        headers = {"Authorization": f"token {token}", "Accept": "application/json"}
        status, data = http(method, self.url + "/api/v1" + path, headers, body)
        return status, self._decode(data)

    # --- tokens ---------------------------------------------------------------------------

    def list_tokens(self, user):
        return self.basic("GET", f"/users/{urllib.parse.quote(user)}/tokens?limit=50", user) or []

    def create_token(self, user, name, scopes):
        data = self.basic("POST", f"/users/{urllib.parse.quote(user)}/tokens", user,
                          {"name": name, "scopes": scopes}, expect=(201,))
        if not isinstance(data, dict) or not data.get("sha1"):
            raise RotationError("Codeberg : réponse de création de token sans valeur")
        return data["id"], data["sha1"]

    def delete_token(self, user, token_id):
        self.basic("DELETE", f"/users/{urllib.parse.quote(user)}/tokens/{token_id}", user,
                   expect=(204,))

    def check_token(self, token, user, repo=None):
        """Le token est valide et, si `repo`, a le droit d'écriture sur ce dépôt.

        GET /user exige une portée `user` : sans elle (403), l'identité n'est pas vérifiable
        et seul le droit sur le dépôt fait foi. Un 401 signifie un token invalide."""
        status, data = self.with_token("GET", "/user", token)
        if status == 401:
            raise RotationError("Codeberg : le nouveau token est refusé (401)")
        if status == 200 and (not isinstance(data, dict) or data.get("login") != user):
            raise RotationError(f"Codeberg : le nouveau token n'authentifie pas {user}")
        if status not in (200, 403):
            raise RotationError(f"Codeberg : vérification du nouveau token impossible ({status})")
        if status == 403 and not repo:
            raise RotationError("Codeberg : nouveau token invérifiable (ni portée user, ni dépôt)")
        if repo:
            status, data = self.with_token("GET", f"/repos/{repo}", token)
            if status != 200 or not (data.get("permissions") or {}).get("push"):
                raise RotationError(f"Codeberg : le nouveau token n'a pas l'écriture sur {repo} ({status})")

    # --- clés GPG -------------------------------------------------------------------------

    def user_email(self, user):
        data = self.basic("GET", "/user", user)
        return data.get("email")

    def list_gpg_keys(self, user):
        return self.basic("GET", "/user/gpg_keys?limit=50", user) or []

    def gpg_key_token(self, user):
        data = self.basic("GET", "/user/gpg_key_token", user)
        return data if isinstance(data, str) else str(data)

    def add_gpg_key(self, user, armored_public, armored_signature=None):
        body = {"armored_public_key": armored_public}
        if armored_signature:
            body["armored_signature"] = armored_signature
        return self.basic("POST", "/user/gpg_keys", user, body, expect=(201,))

    def delete_gpg_key(self, user, key_id):
        self.basic("DELETE", f"/user/gpg_keys/{key_id}", user, expect=(204,))
