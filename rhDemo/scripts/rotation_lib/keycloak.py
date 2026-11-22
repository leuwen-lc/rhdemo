"""Client minimal de l'API d'administration Keycloak (bibliothèque standard).

Utilisé à travers un `kubectl port-forward` vers le pod Keycloak de stagingkub (même accès
que init-keycloak-stagingkub.sh). Les mots de passe ne passent que dans le corps des requêtes,
jamais en argument de commande ; les messages d'erreur sont masqués (`short`).
"""
import json
import time
import urllib.parse

from .common import RotationError, http, short

# Keycloak ne renvoie cette erreur qu'après avoir validé le mot de passe : l'utilisateur a une
# action requise (profil à compléter…), mais les identifiants sont bons.
NOT_FULLY_SET_UP = "Account is not fully set up"


class Keycloak:
    def __init__(self, url, admin_user, admin_password, admin_realm="master"):
        self.url = url.rstrip("/")
        self.admin_user = admin_user
        self.admin_password = admin_password
        self.admin_realm = admin_realm
        self._token = None
        self._expires = 0.0

    # --- jetons ----------------------------------------------------------------------------

    def _password_grant(self, realm, user, password):
        body = urllib.parse.urlencode({"grant_type": "password", "client_id": "admin-cli",
                                       "username": user, "password": password})
        status, raw = http("POST", f"{self.url}/realms/{urllib.parse.quote(realm)}/protocol/openid-connect/token",
                           {"Content-Type": "application/x-www-form-urlencoded"}, body)
        return status, raw

    def token(self):
        """Jeton d'administration, renouvelé avant expiration (60 s par défaut dans master)."""
        if self._token is None or time.monotonic() > self._expires:
            status, raw = self._password_grant(self.admin_realm, self.admin_user, self.admin_password)
            if status != 200:
                raise RotationError(f"Keycloak : connexion de {self.admin_user} refusée ({status}) {short(raw)}")
            data = json.loads(raw)
            self._token = data["access_token"]
            self._expires = time.monotonic() + max(int(data.get("expires_in", 60)) - 15, 5)
        return self._token

    def check_login(self, realm, user, password):
        """Vérifie un couple identifiant / mot de passe (client admin-cli du realm)."""
        status, raw = self._password_grant(realm, user, password)
        if status == 200:
            return True
        if status == 400 and NOT_FULLY_SET_UP.encode() in raw:
            return False   # mot de passe accepté, action requise en attente
        raise RotationError(f"Keycloak : connexion de {user} ({realm}) refusée ({status}) {short(raw)}")

    def _call(self, method, path, body=None, ok=(200, 204)):
        status, raw = http(method, f"{self.url}/admin/realms/{path}",
                           {"Authorization": f"Bearer {self.token()}"}, body)
        if status not in ok:
            raise RotationError(f"Keycloak : {method} {path.split('?')[0]} refusé ({status}) {short(raw)}")
        return json.loads(raw) if raw.strip() else None

    # --- utilisateurs ----------------------------------------------------------------------

    def user_id(self, realm, username):
        q = urllib.parse.urlencode({"username": username, "exact": "true"})
        users = self._call("GET", f"{urllib.parse.quote(realm)}/users?{q}") or []
        for u in users:
            if (u.get("username") or "").lower() == username.lower():
                return u["id"]
        raise RotationError(f"Keycloak : utilisateur {username} absent du realm {realm}")

    def set_password(self, realm, username, password):
        uid = self.user_id(realm, username)
        self._call("PUT", f"{urllib.parse.quote(realm)}/users/{uid}/reset-password",
                   {"type": "password", "value": password, "temporary": False})

    # --- clients ---------------------------------------------------------------------------

    def client(self, realm, client_id):
        q = urllib.parse.urlencode({"clientId": client_id})
        found = self._call("GET", f"{urllib.parse.quote(realm)}/clients?{q}") or []
        for c in found:
            if c.get("clientId") == client_id:
                return c
        raise RotationError(f"Keycloak : client {client_id} absent du realm {realm}")

    def set_client_secret(self, realm, client_id, secret):
        """Impose la valeur du secret (l'API « regenerate » ne permet pas de la choisir)."""
        rep = self.client(realm, client_id)
        rep["secret"] = secret
        self._call("PUT", f"{urllib.parse.quote(realm)}/clients/{rep['id']}", rep)
        if self.client_secret(realm, client_id) != secret:
            raise RotationError(f"Keycloak : relecture du secret de {client_id} incohérente")

    def client_secret(self, realm, client_id):
        rep = self.client(realm, client_id)
        data = self._call("GET", f"{urllib.parse.quote(realm)}/clients/{rep['id']}/client-secret") or {}
        return data.get("value")
