"""Générateurs et lecteurs de owasp-suppressions.xml et .trivyignore.yaml.

Édition textuelle (les commentaires et la mise en forme existants sont préservés), puis
validation syntaxique par un vrai parseur (verify.py). Règles écrites UNE fois ici au lieu
d'être répétées comme consignes à un LLM :
  - double inscription : `<cve>` pour un CVE, `<vulnerabilityName>` pour un GHSA, toutes les
    formes connues de la faille (OSS Index nomme par CVE, Node Audit par GHSA) ;
  - portée `groupId` entier pour les groupes publiant plusieurs jars sous un même CPE générique
    (une CVE se réattache sinon au jar frère au scan suivant) ;
  - justification dans `<notes>`, jamais dans un commentaire XML (un `--` y casse le fichier) ;
  - jeton `[PENDING_UPSTREAM_FIX]` pour le critère B, `[OSV:<DISTRO>:<branche>]` pour un paquet
    système d'image (revérification automatique).
"""
import re
from xml.sax.saxutils import escape

from .common import clean_text

OWASP_FILE = "owasp-suppressions.xml"
TRIVY_FILE = ".trivyignore.yaml"
PENDING_TOKEN = "[PENDING_UPSTREAM_FIX]"

# Groupes Maven dont une CVE à CPE générique touche plusieurs jars.
GROUP_WIDE = {
    "org.apache.tomcat.embed", "org.apache.logging.log4j", "org.springframework.security",
    "org.springframework", "io.netty", "com.fasterxml.jackson.core", "tools.jackson.core",
    "org.eclipse.jetty",
}

_BLOCK_RE = re.compile(r"[ \t]*<suppress\b[^>]*>.*?</suppress>[ \t]*\n?", re.S)
_TAG_RE = {
    "notes": re.compile(r"<notes>(.*?)</notes>", re.S),
    "packageUrl": re.compile(r"<packageUrl[^>]*>(.*?)</packageUrl>", re.S),
    "cve": re.compile(r"<cve>(.*?)</cve>", re.S),
    "vulnerabilityName": re.compile(r"<vulnerabilityName[^>]*>(.*?)</vulnerabilityName>", re.S),
}
_OSV_TOKEN_RE = re.compile(r"\[OSV:(ALPINE|DEBIAN|UBUNTU):([A-Za-z0-9.]+)\]")


# ----------------------------------------------------------------------------------------------
# OWASP Dependency-Check
# ----------------------------------------------------------------------------------------------

def package_regex(ecosystem, package_name):
    """Expression packageUrl pour un finding (npm : nom exact ; Maven : artefact, ou groupe entier)."""
    if ecosystem == "npm":
        return "^pkg:npm/" + re.escape(package_name).replace("\\-", "-") + "@.*$"
    group, _, artifact = package_name.partition(":")
    group_re = re.escape(group).replace("\\-", "-")
    if group in GROUP_WIDE or not artifact:
        return f"^pkg:maven/{group_re}/.*$"
    return f"^pkg:maven/{group_re}/" + re.escape(artifact).replace("\\-", "-") + "@.*$"


def parse_package_regex(regex):
    """Inverse approché de package_regex -> (ecosystem, nom) ; nom Maven « groupe:* » si groupe entier."""
    plain = (regex or "").replace("\\.", ".").replace("\\-", "-")
    m = re.match(r"^\^?pkg:npm/(.+?)@", plain)
    if m:
        return "npm", m.group(1)
    m = re.match(r"^\^?pkg:maven/([^/]+)/(.+?)@", plain)
    if m:
        return "maven", f"{m.group(1)}:{m.group(2)}"
    m = re.match(r"^\^?pkg:maven/([^/]+)/", plain)
    if m:
        return "maven", f"{m.group(1)}:*"
    return None, None


def parse_owasp(text):
    """Blocs <suppress> -> liste de dicts {start, end, notes, package_regex, ecosystem, package, ids}."""
    blocks = []
    for m in _BLOCK_RE.finditer(text):
        body = m.group(0)
        notes = _first(_TAG_RE["notes"], body)
        purl = _first(_TAG_RE["packageUrl"], body)
        ids = [i.strip() for i in _TAG_RE["cve"].findall(body) + _TAG_RE["vulnerabilityName"].findall(body)]
        eco, pkg = parse_package_regex(purl)
        blocks.append({"start": m.start(), "end": m.end(), "notes": notes, "package_regex": purl,
                       "ecosystem": eco, "package": pkg, "ids": ids,
                       "pending": PENDING_TOKEN in (notes or "")})
    return blocks


def _first(regex, text):
    m = regex.search(text)
    return m.group(1).strip() if m else None


def _covers(block, ecosystem, package_name):
    if block["ecosystem"] != ecosystem or not block["package"]:
        return False
    if block["package"] == package_name:
        return True
    return ecosystem == "maven" and block["package"].endswith(":*") and \
        package_name.split(":")[0] == block["package"].split(":")[0]


def is_suppressed(text, ecosystem, package_name, ids):
    """Une suppression existante couvre-t-elle déjà ce paquet pour l'un de ces identifiants ?"""
    wanted = set(ids)
    return any(_covers(b, ecosystem, package_name) and wanted & set(b["ids"]) for b in parse_owasp(text))


def owasp_block(ecosystem, package_name, ids, notes):
    """Bloc <suppress> prêt à insérer (4 espaces d'indentation, comme le fichier existant)."""
    lines = ["    <suppress>",
             f"        <notes>{escape(clean_text(notes, 1000))}</notes>",
             f'        <packageUrl regex="true">{escape(package_regex(ecosystem, package_name))}</packageUrl>']
    for vid in sorted(set(ids), key=lambda i: (not i.startswith("CVE-"), i)):
        tag = "cve" if vid.startswith("CVE-") else "vulnerabilityName"
        lines.append(f"        <{tag}>{escape(vid)}</{tag}>")
    lines.append("    </suppress>")
    return "\n".join(lines) + "\n"


def add_owasp(text, ecosystem, package_name, ids, notes):
    """Ajoute la suppression avant </suppressions>. Si un bloc couvre déjà ce paquet pour une partie
    des identifiants, les formes manquantes (ex. le GHSA d'un CVE déjà inscrit) y sont ajoutées.
    -> (texte, modifié?) ; non modifié = toutes les formes déjà couvertes."""
    wanted = set(ids)
    covering = [b for b in parse_owasp(text) if _covers(b, ecosystem, package_name) and wanted & set(b["ids"])]
    if covering:
        missing = wanted - {i for b in covering for i in b["ids"]}
        if not missing:
            return text, False
        block = covering[0]
        body = text[block["start"]:block["end"]]
        extra = "".join(f"        <{'cve' if v.startswith('CVE-') else 'vulnerabilityName'}>{escape(v)}"
                        f"</{'cve' if v.startswith('CVE-') else 'vulnerabilityName'}>\n" for v in sorted(missing))
        body = re.sub(r"([ \t]*</suppress>)", lambda m: extra + m.group(1), body, count=1)
        return text[:block["start"]] + body + text[block["end"]:], True
    idx = text.rfind("</suppressions>")
    if idx < 0:
        raise ValueError(f"{OWASP_FILE} : balise </suppressions> introuvable")
    head = text[:idx].rstrip("\n") + "\n\n"
    return head + owasp_block(ecosystem, package_name, ids, notes) + "\n" + text[idx:], True


def remove_owasp(text, ecosystem, package_name, ids):
    """Retire les identifiants `ids` des suppressions couvrant ce paquet ; un bloc vidé est supprimé.
    -> (texte, nombre de blocs touchés)."""
    wanted = set(ids)
    touched = 0
    for block in sorted(parse_owasp(text), key=lambda b: b["start"], reverse=True):
        if not (_covers(block, ecosystem, package_name) and wanted & set(block["ids"])):
            continue
        touched += 1
        body = text[block["start"]:block["end"]]
        if set(block["ids"]) <= wanted:
            text = text[:block["start"]] + text[block["end"]:]
            continue
        for vid in wanted:
            body = re.sub(r"[ \t]*<(cve|vulnerabilityName)[^>]*>" + re.escape(vid) + r"</\1>[ \t]*\n?", "", body)
        text = text[:block["start"]] + body + text[block["end"]:]
    return re.sub(r"\n{4,}", "\n\n\n", text), touched


# ----------------------------------------------------------------------------------------------
# Trivy
# ----------------------------------------------------------------------------------------------

_TRIVY_ENTRY_RE = re.compile(
    r"(?P<comments>(?:[ \t]*#[^\n]*\n)*)"
    r"[ \t]*- id: (?P<id>[^\n]+)\n"
    r"(?:[ \t]+pkg-name: (?P<pkg>[^\n]+)\n)?"
    r"(?:[ \t]+statement: (?P<statement>[^\n]+)\n)?")


def parse_trivy(text):
    entries = []
    for m in _TRIVY_ENTRY_RE.finditer(text):
        statement = (m.group("statement") or "").strip().strip('"')
        osv = _OSV_TOKEN_RE.search(statement)
        entries.append({"start": m.start(), "end": m.end(), "id": m.group("id").strip(),
                        "package": (m.group("pkg") or "").strip(), "statement": statement,
                        "pending": PENDING_TOKEN in statement,
                        "osv": {"distro": osv.group(1), "branch": osv.group(2)} if osv else None,
                        "embedded": "embarqu" in (m.group("comments") + statement).lower()})
    return entries


def trivy_entry(vuln_id, package_name, statement, comment):
    safe = clean_text(statement, 600).replace("\\", "/").replace('"', "'")
    return (f"\n  # {clean_text(comment, 150)}\n"
            f"  - id: {vuln_id}\n"
            f"    pkg-name: {package_name}\n"
            f'    statement: "{safe}"\n')


def add_trivy(text, vuln_id, package_name, statement, comment):
    if any(e["id"] == vuln_id and e["package"] == package_name for e in parse_trivy(text)):
        return text, False
    return text.rstrip("\n") + "\n" + trivy_entry(vuln_id, package_name, statement, comment), True


def remove_trivy(text, vuln_id, package_name):
    touched = 0
    for e in sorted(parse_trivy(text), key=lambda x: x["start"], reverse=True):
        if e["id"] == vuln_id and e["package"] == package_name:
            text = text[:e["start"]] + text[e["end"]:]
            touched += 1
    return text, touched


def osv_token(os_family, os_name):
    """Jeton [OSV:<DISTRO>:<branche>] à partir des métadonnées Trivy (Metadata.OS), ou ''."""
    family = (os_family or "").lower()
    name = os_name or ""
    if family == "alpine":
        m = re.match(r"^(\d+)\.(\d+)", name)
        return f"[OSV:ALPINE:v{m.group(1)}.{m.group(2)}]" if m else ""
    if family == "debian":
        m = re.match(r"^(\d+)", name)
        return f"[OSV:DEBIAN:{m.group(1)}]" if m else ""
    if family == "ubuntu":
        m = re.match(r"^(\d+\.\d+)", name)
        return f"[OSV:UBUNTU:{m.group(1)}]" if m else ""
    return ""
