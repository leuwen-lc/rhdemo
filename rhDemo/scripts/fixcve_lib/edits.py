"""Application des montées de version, chacune contrôlée par son effet réel.

Une montée n'est retenue que si l'artefact résolu change vraiment : toutes les copies npm
au moins à la version cible dans package-lock.json, propriété Maven effectivement posée,
référence d'image remplacée dans Jenkinsfile-CI. Sinon les fichiers sont restaurés et la
montée est déclarée en échec (le finding retombe dans la branche « sans correctif » de la
politique). Chemins relatifs au répertoire `rhDemo/`.

Résultats : ("applied", détail) | ("already", détail) si HEAD est déjà à jour (finding vu sur un
build plus ancien) | ("failed", raison).
"""
import json
import os
import re

from . import npm as npm_mod
from .common import compare, run, version_key
from .registry import IMAGES, RegistryError

POM = "pom.xml"
# Fichiers portant une référence d'image épinglée `dépôt:tag@sha256:...` (même liste que l'ancien
# skill fixcve-auto-apply) ; la référence complète est remplacée telle quelle, partout.
IMAGE_FILES = ["Jenkinsfile-CI", "infra/ephemere/docker-compose.yml", "infra/dev/docker-compose.yml",
               "infra/stagingkub/helm/rhdemo/values.yaml", "infra/stagingkub/scripts/init-stagingkub.sh"]
M2_BOOT_BOM = os.path.expanduser(
    "~/.m2/repository/org/springframework/boot/spring-boot-dependencies/{v}/spring-boot-dependencies-{v}.pom")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class Snapshot:
    """Sauvegarde/restauration de fichiers autour d'une tentative."""

    def __init__(self, paths):
        self.saved = {p: (_read(p) if os.path.exists(p) else None) for p in paths}

    def restore(self):
        for path, text in self.saved.items():
            if text is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                _write(path, text)


# ----------------------------------------------------------------------------------------------
# npm
# ----------------------------------------------------------------------------------------------

def _npm(args, timeout=600):
    return run([npm_mod.NPM, "--prefix", "frontend", *args], timeout=timeout)


def installed_npm_version(name):
    versions = sorted({v for (v, _) in npm_mod.load_lock_index().get(name, []) if version_key(v)}, key=version_key)
    return "/".join(versions) or "?"


def npm_upgrade(name, target):
    """update (lockfile seul) -> install exact si dépendance directe -> overrides si transitive."""
    index = npm_mod.load_lock_index()
    if npm_mod.all_copies_at_least(index, name, target):
        return "already", f"{name} deja >= {target} dans package-lock.json"
    snap = Snapshot([npm_mod.PACKAGE_JSON, npm_mod.LOCKFILE])
    _npm(["update", name, "--package-lock-only"])
    if npm_mod.all_copies_at_least(npm_mod.load_lock_index(), name, target):
        return "applied", f"{name} -> {installed_npm_version(name)} (npm update, lockfile seul)"
    pkg = json.loads(_read(npm_mod.PACKAGE_JSON))
    if name in (pkg.get("dependencies") or {}) or name in (pkg.get("devDependencies") or {}):
        flags = ["--save-exact"] + (["--save-dev"] if name in (pkg.get("devDependencies") or {}) else [])
        _npm(["install", f"{name}@{target}", "--package-lock-only", *flags])
        how = "npm install (dependance directe)"
    else:
        overrides = pkg.setdefault("overrides", {})
        overrides[name] = target
        _write(npm_mod.PACKAGE_JSON, json.dumps(pkg, indent=2, ensure_ascii=False) + "\n")
        _npm(["install", "--package-lock-only"])
        how = "overrides (dependance transitive)"
    if npm_mod.all_copies_at_least(npm_mod.load_lock_index(), name, target):
        return "applied", f"{name} -> {installed_npm_version(name)} ({how})"
    snap.restore()
    return "failed", f"{name} : aucune copie amenee a {target} ({how} sans effet sur l'arbre resolu)"


# ----------------------------------------------------------------------------------------------
# Maven
# ----------------------------------------------------------------------------------------------

def boot_version(pom_text):
    m = re.search(r"<parent>.*?<artifactId>spring-boot-starter-parent</artifactId>\s*<version>([^<]+)</version>",
                  pom_text, re.S)
    return m.group(1).strip() if m else None


def bom_property_map(bom_text):
    """-> (exact {(g, a): prop}, imports [(g, a, prop)]) depuis spring-boot-dependencies."""
    exact, imports = {}, []
    for block in re.findall(r"<dependency>(.*?)</dependency>", bom_text, re.S):
        g = re.search(r"<groupId>([^<]+)</groupId>", block)
        a = re.search(r"<artifactId>([^<]+)</artifactId>", block)
        v = re.search(r"<version>\$\{([^}]+)\}</version>", block)
        if not (g and a and v):
            continue
        if "<scope>import</scope>" in block:
            imports.append((g.group(1), a.group(1), v.group(1)))
        else:
            exact[(g.group(1), a.group(1))] = v.group(1)
    return exact, imports


def managing_property(group, artifact, bom_text):
    """Propriété du BOM Spring Boot qui fixe la version de group:artifact -> (prop, bom_ga|None)."""
    exact, imports = bom_property_map(bom_text)
    if (group, artifact) in exact:
        return exact[(group, artifact)], None
    best = None
    for g, a, prop in imports:
        if group == g or group.startswith(g + "."):
            if best is None or len(g) > len(best[0]):
                best = (g, a, prop)
    return (best[2], f"{best[0]}:{best[1]}") if best else (None, None)


def _set_property(pom_text, prop, value, comment):
    """Pose <prop>value</prop> dans <properties> (remplace, ou ajoute avant </properties>)."""
    # Seul un commentaire « Fix ... » juste au-dessus est remplacé (jamais un commentaire descriptif).
    existing = re.search(rf"(\n([ \t]*)(?:<!-- Fix [^\n]*-->\n[ \t]*)?)<{re.escape(prop)}>([^<]*)</{re.escape(prop)}>", pom_text)
    if existing:
        indent = existing.group(2)
        repl = f"\n{indent}<!-- {comment} -->\n{indent}<{prop}>{value}</{prop}>"
        return pom_text[:existing.start()] + repl + pom_text[existing.end():], existing.group(3).strip()
    m = re.search(r"\n([ \t]*)</properties>", pom_text)
    if not m:
        raise ValueError("pom.xml : </properties> introuvable")
    indent = m.group(1) + "\t"
    insert = f"\n{indent}<!-- {comment} -->\n{indent}<{prop}>{value}</{prop}>"
    return pom_text[:m.start()] + insert + pom_text[m.start():], None


def maven_upgrade(package_name, installed, target, ids, registry, bom_path_pattern=None, baseline_pom=None):
    """`baseline_pom` : pom.xml d'avant le cycle. Une propriété déjà montée PAR CE CYCLE (deux
    artefacts du même BOM, ex. jackson-core et jackson-databind) compte comme « applied »."""
    group, _, artifact = package_name.partition(":")
    pom = _read(POM)
    boot = boot_version(pom)
    bom_path = (bom_path_pattern or M2_BOOT_BOM).format(v=boot) if boot else None
    if not bom_path or not os.path.exists(bom_path):
        return "failed", f"BOM Spring Boot {boot} introuvable dans ~/.m2"
    prop, bom_ga = managing_property(group, artifact, _read(bom_path))
    if prop is None:
        return "failed", f"{package_name} : version non geree par une propriete du BOM Spring Boot"
    value = target
    if bom_ga:
        # Propriété d'un BOM importé : la version cible doit exister comme version du BOM.
        try:
            bom_versions = registry.maven_versions(*bom_ga.split(":")) or []
        except RegistryError as e:
            return "failed", f"versions de {bom_ga} illisibles : {e}"
        if target not in bom_versions:
            return "failed", f"{bom_ga} {target} non publie (propriete {prop})"
    current = re.search(rf"<{re.escape(prop)}>([^<]+)</{re.escape(prop)}>", pom)
    if current and version_key(current.group(1)) and compare(current.group(1).strip(), value) >= 0:
        before = re.search(rf"<{re.escape(prop)}>([^<]+)</{re.escape(prop)}>", baseline_pom or pom)
        if baseline_pom is not None and (before is None or (version_key(before.group(1))
                                                            and compare(before.group(1).strip(), value) < 0)):
            return "applied", f"{prop} = {current.group(1).strip()} (monte par ce cycle, couvre {package_name})"
        return "already", f"{prop} deja a {current.group(1).strip()} (>= {value})"
    comment = f"Fix {', '.join(ids)} : {artifact} {installed} -> {value}"
    new_pom, _ = _set_property(pom, prop, value, comment)
    _write(POM, new_pom)
    return "applied", f"{prop} = {value} ({package_name} {installed} -> {value})"


# ----------------------------------------------------------------------------------------------
# Images tierces
# ----------------------------------------------------------------------------------------------

def image_upgrade(token, current_ref, target_tag, target_digest):
    """Remplace `dépôt:tag@digest` courant par la cible dans IMAGE_FILES."""
    repo = IMAGES[token]["repository"]
    cur_tag, cur_digest = current_ref
    if version_key(cur_tag) and version_key(target_tag) and compare(cur_tag, target_tag) >= 0:
        return "already", f"{repo} deja en {cur_tag}"
    old = f"{repo}:{cur_tag}@{cur_digest}"
    new = f"{repo}:{target_tag}@{target_digest}"
    changed = []
    for path in IMAGE_FILES:
        if not os.path.exists(path):
            continue
        text = _read(path)
        if old in text:
            _write(path, text.replace(old, new))
            changed.append(path)
    if "Jenkinsfile-CI" not in changed:
        for path in changed:
            _write(path, _read(path).replace(new, old))
        return "failed", f"reference {old} introuvable dans Jenkinsfile-CI"
    return "applied", f"{repo} {cur_tag} -> {target_tag} ({', '.join(changed)})"
