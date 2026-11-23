"""Credentials Jenkins : lecture et remplacement en place par l'API REST du plugin Credentials.

GET puis POST de .../credential/<id>/config.xml : seul le champ secret est remplacé, le reste
(description, nom d'utilisateur, portée) est conservé tel que Jenkins le renvoie.
"""
import base64
from http.cookiejar import CookieJar
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .common import RotationError, http, short

# type d'inventaire -> (balise racine Jenkins, champ secret)
CRED_TYPES = {
    "string": ("org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl", "secret"),
    "username-password": ("com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl",
                          "password"),
    "file": ("org.jenkinsci.plugins.plaincredentials.impl.FileCredentialsImpl", "secretBytes"),
    # Plugin HashiCorp Vault (OpenBao) : seul secret restant dans Jenkins pour OpenBao.
    "vault-approle": ("com.datapipe.jenkins.vault.credentials.VaultAppRoleCredential", "secretId"),
}

_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")
_XML_ENCODING = re.compile(rb"^\s*<\?xml[^>]*encoding=['\"]([A-Za-z0-9._-]+)['\"]")


def decode_xml(body):
    """Texte du XML renvoyé par Jenkins, qui n'est pas toujours en UTF-8 (description
    accentuée renvoyée en ISO-8859-1 observée) : encodage déclaré, puis UTF-8, puis Latin-1."""
    m = _XML_ENCODING.match(body)
    for enc in ([m.group(1).decode("ascii")] if m else []) + ["utf-8", "iso-8859-1"]:
        try:
            return _XML_DECL.sub("", body.decode(enc))
        except (LookupError, UnicodeDecodeError):
            continue
    raise RotationError("Jenkins : XML illisible")  # inatteignable : Latin-1 décode tout


class Jenkins:
    def __init__(self, url, user, password):
        self.url = url.rstrip("/")
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        self._auth = {"Authorization": f"Basic {token}"}
        # Le crumb CSRF est lié à la session : garder les cookies entre les requêtes.
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar()))
        self._crumb = None
        self.user = user

    def _get(self, path):
        return http("GET", self.url + path, self._auth, opener=self._opener)

    def _crumb_header(self):
        if self._crumb is None:
            status, body = self._get("/crumbIssuer/api/json")
            if status == 404:
                self._crumb = {}
            elif status != 200:
                raise RotationError(f"Jenkins : crumb refusé ({status})")
            else:
                data = json.loads(body)
                self._crumb = {data["crumbRequestField"]: data["crumb"]}
        return self._crumb

    def login(self):
        """Vérifie l'authentification (échoue tôt, avant toute création de secret)."""
        status, body = self._get("/whoAmI/api/json")
        if status != 200:
            raise RotationError(f"Jenkins : authentification refusée pour {self.user} ({status})")
        data = json.loads(body)
        if not data.get("authenticated") or data.get("anonymous"):
            raise RotationError(f"Jenkins : {self.user} n'est pas authentifié")
        self._crumb_header()

    @staticmethod
    def _path(cred_id):
        return f"/credentials/store/system/domain/_/credential/{urllib.parse.quote(cred_id, safe='')}/config.xml"

    def read(self, cred_id, kind):
        """Renvoie l'arbre XML du credential après contrôle de son type."""
        status, body = self._get(self._path(cred_id))
        if status == 404:
            raise RotationError(f"Jenkins : credential {cred_id} introuvable (domaine global)")
        if status != 200:
            raise RotationError(f"Jenkins : lecture de {cred_id} refusée ({status})")
        root = ET.fromstring(decode_xml(body))
        tag, field = CRED_TYPES[kind]
        if root.tag != tag:
            raise RotationError(f"Jenkins : {cred_id} est de type {root.tag}, attendu {tag}")
        if root.find(field) is None:
            raise RotationError(f"Jenkins : champ {field} absent de {cred_id}")
        return root

    def exists(self, cred_id):
        status, _ = self._get(self._path(cred_id))
        if status not in (200, 404):
            raise RotationError(f"Jenkins : lecture de {cred_id} refusée ({status})")
        return status == 200

    def config_xml(self, cred_id):
        """XML du credential, secrets masqués par Jenkins (<secret-redacted/>) : sert à
        contrôler le type, jamais à sauvegarder une valeur."""
        status, body = self._get(self._path(cred_id))
        if status != 200:
            raise RotationError(f"Jenkins : lecture de {cred_id} refusée ({status})")
        return decode_xml(body)

    def _post(self, path, body=None, ctype="application/xml; charset=utf-8"):
        headers = {**self._auth, **self._crumb_header()}
        if body is not None:
            headers["Content-Type"] = ctype
        return http("POST", self.url + path, headers, body, opener=self._opener)

    def replace(self, cred_id, xml):
        """Remplace entièrement un credential existant (le type peut changer)."""
        data = ("<?xml version='1.1' encoding='UTF-8'?>\n" + xml).encode("utf-8")
        status, body = self._post(self._path(cred_id), data)
        if status != 200:
            raise RotationError(f"Jenkins : remplacement de {cred_id} refusé ({status}) {short(body)}")

    def create(self, xml):
        """Crée un credential dans le domaine global à partir de son XML."""
        data = ("<?xml version='1.1' encoding='UTF-8'?>\n" + xml).encode("utf-8")
        status, body = self._post("/credentials/store/system/domain/_/createCredentials", data)
        if status != 200:
            raise RotationError(f"Jenkins : création de credential refusée ({status}) {short(body)}")

    def create_file(self, cred_id, description, file_name, content):
        """Crée un credential « Secret file » (installation : credential encore absent)."""
        root = ET.Element(CRED_TYPES["file"][0])
        for tag, text in (("scope", "GLOBAL"), ("id", cred_id), ("description", description),
                          ("fileName", file_name)):
            ET.SubElement(root, tag).text = text
        raw = content if isinstance(content, bytes) else content.encode("utf-8")
        ET.SubElement(root, "secretBytes").text = base64.b64encode(raw).decode("ascii")
        self.create(ET.tostring(root, encoding="unicode"))

    def username(self, cred_id):
        node = self.read(cred_id, "username-password").find("username")
        return node.text if node is not None else None

    def update(self, cred_id, kind, value):
        """Remplace le secret. `value` : str, ou bytes pour un credential fichier."""
        root = self.read(cred_id, kind)
        field = CRED_TYPES[kind][1]
        if kind == "file":
            raw = value if isinstance(value, bytes) else value.encode("utf-8")
            value = base64.b64encode(raw).decode("ascii")
        root.find(field).text = value
        # Déclaration explicite : Jenkins décode alors le corps en UTF-8 (accents préservés).
        xml = "<?xml version='1.1' encoding='UTF-8'?>\n" + ET.tostring(root, encoding="unicode")
        headers = {**self._auth, **self._crumb_header(),
                   "Content-Type": "application/xml; charset=utf-8"}
        status, body = http("POST", self.url + self._path(cred_id), headers, xml.encode("utf-8"),
                            opener=self._opener)
        if status != 200:
            raise RotationError(f"Jenkins : mise à jour de {cred_id} refusée ({status}) {short(body)}")
