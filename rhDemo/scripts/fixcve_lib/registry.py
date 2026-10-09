"""Versions publiées : Maven Central, registre npm, registres d'images.

Hôtes, dépôts et verbes figés ici : l'appelant ne fournit qu'un identifiant validé par regex
(groupId/artifactId, nom npm, jeton d'image d'une liste blanche), jamais une URL.

Injection pour les tests : `Registry(fixtures={...})` avec les clés `maven:<g>:<a>` (liste de
versions), `npm:<nom>` (liste de versions), `tags:<jeton>` (liste de tags), `digest:<jeton>:<tag>`
(digest) ; une clé absente = artefact inconnu, la valeur "error" = panne simulée.
"""
import json
import re
import urllib.error
import urllib.request

from .common import is_prerelease, run, version_key

TIMEOUT_SECONDS = 15
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_NPM_NAME_RE = re.compile(r"^(@[a-z0-9._-]+/)?[a-z0-9._-]+$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9._+-]{1,60}$")
_TAG_RE = re.compile(r"^v?[0-9][A-Za-z0-9._-]{0,127}$")

# Jeton d'image (champ `image` de detected.json) -> dépôt de registre. Doit rester aligné sur
# TRIVY_IMAGES de fixcve-detect.py et sur les variables *_IMAGE de Jenkinsfile-CI.
IMAGES = {
    "keycloak": {"registry": "quay.io", "path": "keycloak/keycloak",
                 "repository": "quay.io/keycloak/keycloak", "variable": "KEYCLOAK_IMAGE"},
    "nginx": {"registry": "registry-1.docker.io", "path": "library/nginx",
              "repository": "nginx", "variable": "NGINX_IMAGE"},
    "postgres": {"registry": "registry-1.docker.io", "path": "library/postgres",
                 "repository": "postgres", "variable": "POSTGRES_IMAGE"},
    "nginx-gateway-fabric": {"registry": "ghcr.io", "path": "nginx/nginx-gateway-fabric",
                             "repository": "ghcr.io/nginx/nginx-gateway-fabric", "variable": "NGF_IMAGE"},
}

_MANIFEST_ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])


class RegistryError(Exception):
    """Réseau ou réponse inexploitable : cas transitoire, jamais une conclusion."""


class Registry:
    def __init__(self, fixtures=None, npm_bin="frontend/node/npm"):
        self.fixtures = fixtures
        self.npm_bin = npm_bin

    def _fixture(self, key):
        value = self.fixtures.get(key)
        if value == "error":
            raise RegistryError(f"{key} : panne simulée")
        return value

    # --- Maven Central -------------------------------------------------------------------
    def maven_versions(self, group_id, artifact_id):
        """Toutes les versions publiées (maven-metadata.xml), ou None si l'artefact est inconnu."""
        if not (_ID_RE.match(group_id) and _ID_RE.match(artifact_id)):
            raise RegistryError(f"coordonnées Maven invalides : {group_id}:{artifact_id}")
        if self.fixtures is not None:
            return self._fixture(f"maven:{group_id}:{artifact_id}")
        url = (f"https://repo1.maven.org/maven2/{group_id.replace('.', '/')}/"
               f"{artifact_id}/maven-metadata.xml")
        body = _http_get(url)
        if body is None:
            return None
        # Regex plutôt qu'un parseur XML : contenu externe, 1 balise lue, aucune entité/DTD.
        versions = [v.strip() for v in re.findall(r"<version>([^<]*)</version>", body.decode("utf-8", "replace"))]
        return [v for v in versions if _VERSION_RE.match(v)]

    # --- npm -----------------------------------------------------------------------------
    def npm_versions(self, name):
        if not _NPM_NAME_RE.match(name or ""):
            raise RegistryError(f"nom npm invalide : {name}")
        if self.fixtures is not None:
            return self._fixture(f"npm:{name}")
        code, out, err = run([self.npm_bin, "--prefix", "frontend", "view", name, "versions", "--json"])
        if code != 0:
            raise RegistryError(f"npm view {name} : {err.strip()[:200]}")
        try:
            doc = json.loads(out)
        except ValueError as e:
            raise RegistryError(f"npm view {name} : JSON illisible") from e
        # npm renvoie une chaîne quand il n'y a qu'une version.
        return [doc] if isinstance(doc, str) else [v for v in doc if isinstance(v, str)]

    # --- Images --------------------------------------------------------------------------
    def image_tags(self, token):
        """Tags « version stable » publiés, triés décroissant."""
        image = IMAGES.get(token)
        if image is None:
            raise RegistryError(f"jeton d'image non supporté : {token}")
        if self.fixtures is not None:
            tags = self._fixture(f"tags:{token}") or []
        else:
            tags = _list_tags(image)
        tags = [t for t in tags if _TAG_RE.match(t) and not is_prerelease(t) and version_key(t)]
        return sorted(set(tags), key=version_key, reverse=True)

    def image_digest(self, token, tag):
        """Digest `sha256:...` du manifeste (index multi-architecture) de `token:tag`, ou None."""
        image = IMAGES.get(token)
        if image is None or not _TAG_RE.match(tag or ""):
            raise RegistryError(f"image/tag invalide : {token}:{tag}")
        if self.fixtures is not None:
            return self._fixture(f"digest:{token}:{tag}")
        url = f"https://{image['registry']}/v2/{image['path']}/manifests/{tag}"
        headers = _registry_request(url, image, method="HEAD")
        if headers is None:
            return None
        digest = headers.get("Docker-Content-Digest", "")
        return digest if re.match(r"^sha256:[0-9a-f]{64}$", digest) else None


def _http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # NOSONAR hôte figé
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise RegistryError(f"HTTP {e.code} sur {url}") from e
    except OSError as e:
        raise RegistryError(f"{url} : {e}") from e


def _bearer_token(www_authenticate):
    """Jeton anonyme à partir de l'en-tête WWW-Authenticate (Bearer realm=...,service=...,scope=...)."""
    params = dict(re.findall(r'(\w+)="([^"]*)"', www_authenticate or ""))
    realm = params.pop("realm", "")
    if not realm.startswith("https://"):
        raise RegistryError("en-tête WWW-Authenticate inattendu")
    query = "&".join(f"{k}={v}" for k, v in params.items())
    body = _http_get(f"{realm}?{query}" if query else realm)
    if body is None:
        raise RegistryError("jeton de registre introuvable")
    doc = json.loads(body.decode("utf-8"))
    return doc.get("token") or doc.get("access_token")


def _registry_request(url, image, method="GET"):
    """Requête sur l'API v2 d'un registre, jeton anonyme obtenu à la volée.
    -> en-têtes (insensibles à la casse), ou None (404)."""
    headers = {"Accept": _MANIFEST_ACCEPT}
    for attempt in range(2):
        req = urllib.request.Request(url, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # NOSONAR hôte figé
                # Message HTTP insensible à la casse (Docker Hub : en-têtes en minuscules).
                return resp.headers
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 401 and attempt == 0:
                headers["Authorization"] = "Bearer " + _bearer_token(e.headers.get("WWW-Authenticate"))
                continue
            raise RegistryError(f"HTTP {e.code} sur {url}") from e
        except OSError as e:
            raise RegistryError(f"{url} : {e}") from e
    raise RegistryError(f"authentification refusée sur {url}")


def _list_tags(image):
    """Liste des tags par l'API propre au registre (une page de 100, les plus récents)."""
    if image["registry"] == "quay.io":
        body = _http_get(f"https://quay.io/api/v1/repository/{image['path']}/tag/?onlyActiveTags=true&limit=100")
        return [t.get("name", "") for t in json.loads(body or b"{}").get("tags", [])]
    if image["registry"] == "registry-1.docker.io":
        body = _http_get(f"https://hub.docker.com/v2/repositories/{image['path']}/tags"
                         "?page_size=100&ordering=last_updated")
        return [r.get("name", "") for r in json.loads(body or b"{}").get("results", [])]
    url = f"https://{image['registry']}/v2/{image['path']}/tags/list"
    try:
        body = _http_get(url)
    except RegistryError:
        body = None
    if body is None:
        # ghcr.io : jeton anonyme requis.
        token = _bearer_token(f'Bearer realm="https://ghcr.io/token",service="ghcr.io",'
                              f'scope="repository:{image["path"]}:pull"')
        body = _http_get(url, headers={"Authorization": f"Bearer {token}"})
    return list(json.loads(body or b"{}").get("tags") or [])
