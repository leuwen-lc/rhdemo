"""Avis OSV.dev : version corrigée de la branche installée et alias (CVE <-> GHSA).

Source commune à npm et Maven (proposition L) : l'avis dit quelle version corrige, par branche ;
le registre ne sert plus qu'à confirmer qu'elle est publiée. Hôte et verbes figés ici, aucune URL
fournie par l'appelant.

Injection pour les tests (`fixture_dir`) : `<id>.json` = avis, `<id>.error` = réseau en panne,
fichier absent = 404 ; `query-<ecosystem>-<nom>-<version>.json` = réponse de /v1/query.
"""
import json
import os
import re
import urllib.error
import urllib.request

from .common import compare, load_json, version_key

OSV_API = "https://api.osv.dev/v1"
TIMEOUT_SECONDS = 15
VULN_ID_RE = re.compile(r"^(CVE-\d{4}-\d{4,7}|GHSA-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{4})$")
# Écosystèmes OSV correspondant au champ `ecosystem` de detected.json.
ECOSYSTEMS = {"npm": "npm", "maven": "Maven"}


class OsvError(Exception):
    """Réseau ou réponse inexploitable : cas transitoire, jamais une conclusion."""


class OsvClient:
    def __init__(self, fixture_dir=None):
        self.fixture_dir = fixture_dir
        self._cache = {}

    def get(self, vuln_id):
        """-> avis (dict) ou None si inconnu (404). Lève OsvError si injoignable."""
        if not VULN_ID_RE.match(vuln_id or ""):
            return None
        if vuln_id in self._cache:
            return self._cache[vuln_id]
        if self.fixture_dir is not None:
            if os.path.exists(os.path.join(self.fixture_dir, vuln_id + ".error")):
                raise OsvError(f"{vuln_id} : panne simulée")
            doc = load_json(os.path.join(self.fixture_dir, vuln_id + ".json"))
        else:
            doc = self._http("GET", f"{OSV_API}/vulns/{vuln_id}")
        self._cache[vuln_id] = doc if isinstance(doc, dict) else None
        return self._cache[vuln_id]

    def query(self, ecosystem, name, version):
        """Avis affectant `name@version` (liste, éventuellement vide). Lève OsvError si injoignable."""
        osv_eco = ECOSYSTEMS.get(ecosystem)
        if osv_eco is None:
            return []
        if self.fixture_dir is not None:
            safe = re.sub(r"[^A-Za-z0-9.@_-]", "_", f"{osv_eco}-{name}-{version}")
            path = os.path.join(self.fixture_dir, f"query-{safe}.json")
            if os.path.exists(path + ".error"):
                raise OsvError("panne simulée")
            doc = load_json(path) or {}
        else:
            body = {"version": version, "package": {"name": name, "ecosystem": osv_eco}}
            doc = self._http("POST", f"{OSV_API}/query", body) or {}
        vulns = doc.get("vulns") or []
        return [v for v in vulns if isinstance(v, dict)]

    @staticmethod
    def _http(method, url, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # NOSONAR hôte figé
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise OsvError(f"HTTP {e.code} sur {url}") from e
        except (OSError, ValueError) as e:
            raise OsvError(f"{url} : {e}") from e


def aliases(doc):
    """Identifiants CVE/GHSA d'un avis (id + aliases), triés."""
    ids = {doc.get("id", "")} | set(doc.get("aliases") or [])
    return sorted(i for i in ids if VULN_ID_RE.match(i))


def fixed_in_branch(doc, ecosystem, name, installed):
    """Plus petite version `fixed` d'une plage de `doc` qui contient `installed`, ou None.

    Plages SEMVER (npm) ou ECOSYSTEM (Maven) : suites d'événements introduced / fixed /
    last_affected. Une plage sans `fixed` (last_affected seul) ne donne aucun correctif."""
    osv_eco = ECOSYSTEMS.get(ecosystem)
    inst = version_key(installed)
    if inst is None or osv_eco is None:
        return None
    best = None
    for aff in doc.get("affected") or []:
        pkg = aff.get("package") or {}
        if pkg.get("ecosystem") != osv_eco or pkg.get("name") != name:
            continue
        for rng in aff.get("ranges") or []:
            if rng.get("type") not in ("SEMVER", "ECOSYSTEM"):
                continue
            introduced = None
            for ev in rng.get("events") or []:
                if "introduced" in ev:
                    introduced = ev["introduced"]
                elif "fixed" in ev:
                    fixed = ev["fixed"]
                    low_ok = introduced in (None, "0") or (
                        version_key(introduced) is not None and version_key(introduced) <= inst)
                    fk = version_key(fixed)
                    if low_ok and fk is not None and inst < fk:
                        if best is None or compare(fixed, best) < 0:
                            best = fixed
                    introduced = None
    return best


def describes(doc, ecosystem, name):
    """L'avis a-t-il une entrée `affected` pour ce paquet ? (les fiches CVE importées du NVD n'en
    ont pas : seule la fiche GHSA alias porte les plages par paquet)."""
    osv_eco = ECOSYSTEMS.get(ecosystem)
    return any((a.get("package") or {}).get("ecosystem") == osv_eco and (a.get("package") or {}).get("name") == name
               for a in doc.get("affected") or [])


def advisory_fix(client, ids, ecosystem, name, installed):
    """Version corrigée de la branche installée d'après les avis.

    Lit chaque identifiant (finding_id d'abord) et suit les alias des fiches lues (une fiche CVE
    renvoie vers sa fiche GHSA) ; seules les fiches qui décrivent CE paquet comptent. À défaut,
    interroge /v1/query par paquet + version et retient les avis dont un identifiant recoupe les
    formes connues de la faille.
    -> (kind, version, aliases) avec kind :
       'fix'     version corrigée trouvée dans la branche installée ;
       'none'    avis du paquet lu, aucune plage corrigée pour la branche installée ;
       'unknown' aucun avis du paquet (OSV ne le relie pas à la faille) ;
       'error'   OSV injoignable et aucun avis du paquet lu (transitoire)."""
    primary = ids[0] if ids else None
    errored = False
    fetched = {}
    queue = [i for i in ids if i]
    while queue:
        vid = queue.pop(0)
        if vid in fetched:
            continue
        try:
            doc = client.get(vid)
        except OsvError:
            errored = True
            fetched[vid] = None
            continue
        fetched[vid] = doc
        # Une fiche du finding (ou de ses alias) qui ne décrit pas le paquet : suivre ses alias.
        if doc and not describes(doc, ecosystem, name) and (vid == primary or primary in aliases(doc)):
            queue.extend(a for a in aliases(doc) if a not in fetched)
    docs = [d for d in fetched.values() if d]
    # Formes de LA faille du finding : fiches qui contiennent `primary` (identifiants secondaires =
    # simples indices, potentiellement des failles voisines, jamais supprimés par ricochet).
    same = [d for d in docs if primary in aliases(d)]
    all_aliases = set([primary] if primary else [])
    for d in same:
        all_aliases |= set(aliases(d))
    relevant = [d for d in docs if describes(d, ecosystem, name)]
    if not relevant:
        try:
            for doc in client.query(ecosystem, name, installed):
                if all_aliases & set(aliases(doc)) or set(ids) & set(aliases(doc)):
                    relevant.append(doc)
                    if primary in aliases(doc):
                        all_aliases |= set(aliases(doc))
        except OsvError:
            errored = True
    fixes = [f for f in (fixed_in_branch(d, ecosystem, name, installed) for d in relevant) if f]
    if fixes:
        # Plusieurs avis pour la même faille (CVE et GHSA) : la version la plus haute les couvre tous.
        best = fixes[0]
        for f in fixes[1:]:
            if compare(f, best) > 0:
                best = f
        return "fix", best, sorted(all_aliases)
    if not relevant:
        return ("error" if errored else "unknown"), None, sorted(all_aliases)
    return "none", None, sorted(all_aliases)
