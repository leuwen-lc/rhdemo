"""Client OpenBao minimal (API HTTP, bibliothèque standard) : connexion userpass de
l'administrateur, KV v2, AppRole. Voir docs/OPENBAO.md.

TLS vérifié avec l'autorité locale (certs/ca/root-ca.crt) ; jamais de désactivation.
Les messages d'erreur ne reprennent jamais une valeur (corps masqué par `short`).
"""
import json
import os
import ssl
import urllib.parse
import urllib.request

from .common import RotationError, http, short


class OpenBao:
    def __init__(self, url, ca_cert=None, token=None):
        self.url = url.rstrip("/")
        self.token = token
        ctx = None
        if self.url.startswith("https://"):
            ctx = ssl.create_default_context(cafile=os.path.expanduser(ca_cert) if ca_cert else None)
        self._opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx)) \
            if ctx else urllib.request.build_opener()

    # --- bas niveau ------------------------------------------------------------------------

    def _call(self, method, path, body=None, ok=(200, 204)):
        headers = {"X-Vault-Token": self.token} if self.token else {}
        status, raw = http(method, f"{self.url}/v1/{path}", headers, body, opener=self._opener)
        if status == 503:
            raise RotationError("OpenBao est scellé : le déverrouiller (infra/jenkins-docker/openbao/unseal.sh)")
        if status not in ok:
            raise RotationError(f"OpenBao : {method} {path} refusé ({status}) {short(raw)}")
        return json.loads(raw) if raw.strip() else {}

    def login_userpass(self, user, password):
        data = self._call("POST", f"auth/userpass/login/{urllib.parse.quote(user, safe='')}",
                          {"password": password})
        self.token = data["auth"]["client_token"]
        return self

    def revoke_self(self):
        if self.token:
            try:
                self._call("POST", "auth/token/revoke-self")
            finally:
                self.token = None

    # --- KV v2 (montage kv/) ---------------------------------------------------------------

    def kv_read(self, path, missing_ok=False):
        """Données de la dernière version, ou None si absent et `missing_ok`."""
        headers = {"X-Vault-Token": self.token}
        status, raw = http("GET", f"{self.url}/v1/kv/data/{path}", headers, opener=self._opener)
        if status == 404 and missing_ok:
            return None
        if status == 503:
            raise RotationError("OpenBao est scellé : le déverrouiller (infra/jenkins-docker/openbao/unseal.sh)")
        if status != 200:
            raise RotationError(f"OpenBao : lecture de kv/{path} refusée ({status}) {short(raw)}")
        return json.loads(raw)["data"]["data"]

    def kv_meta_version(self, path):
        status, raw = http("GET", f"{self.url}/v1/kv/metadata/{path}", {"X-Vault-Token": self.token},
                           opener=self._opener)
        if status == 404:
            return 0
        if status != 200:
            raise RotationError(f"OpenBao : métadonnées de kv/{path} refusées ({status})")
        return json.loads(raw)["data"]["current_version"]

    def kv_set(self, path, key, value):
        """Remplace une clé en conservant les autres (lecture puis écriture avec contrôle de
        version : échoue si quelqu'un a écrit entre-temps)."""
        version = self.kv_meta_version(path)
        data = dict(self.kv_read(path, missing_ok=True) or {}) if version else {}
        data[key] = value
        self._call("POST", f"kv/data/{path}", {"options": {"cas": version}, "data": data})
        if self.kv_read(path).get(key) != value:
            raise RotationError(f"OpenBao : relecture de kv/{path} ({key}) incohérente")

    def kv_put(self, path, data):
        """Écrit toutes les clés d'un coup (nouvelle version)."""
        self._call("POST", f"kv/data/{path}", {"data": data})

    # --- AppRole ---------------------------------------------------------------------------

    def role_id(self, role):
        return self._call("GET", f"auth/approle/role/{role}/role-id")["data"]["role_id"]

    def new_secret_id(self, role):
        """Renvoie (secret_id, accessor)."""
        data = self._call("POST", f"auth/approle/role/{role}/secret-id", {})["data"]
        return data["secret_id"], data["secret_id_accessor"]

    def secret_id_accessors(self, role):
        status, raw = http("LIST", f"{self.url}/v1/auth/approle/role/{role}/secret-id",
                           {"X-Vault-Token": self.token}, opener=self._opener)
        if status == 404:
            return []
        if status != 200:
            raise RotationError(f"OpenBao : liste des secret_id de {role} refusée ({status})")
        return json.loads(raw)["data"]["keys"]

    def destroy_secret_id(self, role, accessor):
        self._call("POST", f"auth/approle/role/{role}/secret-id-accessor/destroy",
                   {"secret_id_accessor": accessor})

    def approle_login(self, role_id, secret_id):
        """Vérifie qu'un couple role_id/secret_id ouvre bien une session (jeton révoqué aussitôt)."""
        probe = OpenBao.__new__(OpenBao)
        probe.url, probe._opener, probe.token = self.url, self._opener, None
        auth = probe._call("POST", "auth/approle/login", {"role_id": role_id, "secret_id": secret_id})
        probe.token = auth["auth"]["client_token"]
        probe.revoke_self()
