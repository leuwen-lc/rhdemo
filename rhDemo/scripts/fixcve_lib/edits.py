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
from .common import compare, major, run, same_minor, version_key
from .registry import IMAGES, RegistryError
from .resolve import default_maven_deps

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

BOOT_GROUP = "org.springframework.boot"
BOOT_PARENT = (BOOT_GROUP, "spring-boot-starter-parent")
BOOT_BOM = (BOOT_GROUP, "spring-boot-dependencies")
UNPINNED_POM = ".fixcve-cycle/pom-sans-epinglages.xml"
_FIX_COMMENT = r"<!-- Fix [^\n]*-->"


def boot_version(pom_text):
    m = re.search(r"<parent>.*?<artifactId>spring-boot-starter-parent</artifactId>\s*<version>([^<]+)</version>",
                  pom_text, re.S)
    return m.group(1).strip() if m else None


def boot_bom_text(boot, registry, bom_path_pattern=None):
    """BOM Spring Boot de cette version : cache Maven local, sinon Maven Central (après une
    montée du parent dans ce cycle, le nouveau BOM n'est pas encore dans ~/.m2)."""
    path = (bom_path_pattern or M2_BOOT_BOM).format(v=boot)
    if os.path.exists(path):
        return _read(path)
    try:
        return registry.maven_pom(*BOOT_BOM, boot)
    except RegistryError:
        return None


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


def bom_literal_versions(bom_text):
    """{(g, a): version} des entrées à version écrite en dur (modules de Spring Boot)."""
    out = {}
    for block in re.findall(r"<dependency>(.*?)</dependency>", bom_text, re.S):
        g = re.search(r"<groupId>([^<]+)</groupId>", block)
        a = re.search(r"<artifactId>([^<]+)</artifactId>", block)
        v = re.search(r"<version>([^<$]+)</version>", block)
        if g and a and v:
            out[(g.group(1), a.group(1))] = v.group(1).strip()
    return out


def bom_properties(bom_text):
    """{propriété: valeur} du bloc <properties> du BOM (versions par défaut)."""
    m = re.search(r"<properties>(.*?)</properties>", bom_text, re.S)
    return dict(re.findall(r"<([A-Za-z0-9._-]+)>([^<]*)</\1>", m.group(1))) if m else {}


def lists_artifact(pom_text, group, artifact):
    return bool(re.search(rf"<groupId>{re.escape(group)}</groupId>\s*<artifactId>{re.escape(artifact)}</artifactId>",
                          pom_text or ""))


def imported_candidates(group, bom_text):
    """BOM importés dont le groupe préfixe celui de l'artefact, du plus précis au moins précis."""
    _, imports = bom_property_map(bom_text)
    found = [(g, a, prop) for g, a, prop in imports if group == g or group.startswith(g + ".")]
    return [(prop, f"{g}:{a}") for g, a, prop in sorted(found, key=lambda x: -len(x[0]))]


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


def _raised_by_cycle(baseline, value):
    """Version courante >= cible : vrai si elle a été montée par ce cycle (avant lui, < cible)."""
    return bool(version_key(baseline)) and compare(baseline, value) < 0


def maven_upgrade(package_name, installed, target, ids, registry, bom_path_pattern=None, baseline_pom=None):
    """Monte group:artifact à `target` par le moyen que le BOM Spring Boot impose :
      - module de Spring Boot (version écrite en dur, celle du parent) : version du parent ;
      - propriété du BOM, ou d'un BOM importé qui liste vraiment l'artefact et publie `target` ;
      - sinon : épinglage dans <dependencyManagement> (ou version de la dépendance directe).
    `baseline_pom` : pom.xml d'avant le cycle. Une version déjà montée PAR CE CYCLE (deux
    artefacts du même BOM, ex. jackson-core et jackson-databind) compte comme « applied »."""
    group, _, artifact = package_name.partition(":")
    pom = _read(POM)
    boot = boot_version(pom)
    bom = boot_bom_text(boot, registry, bom_path_pattern) if boot else None
    if bom is None:
        return "failed", f"BOM Spring Boot {boot} introuvable (~/.m2 et Maven Central)"
    if group == BOOT_GROUP and bom_literal_versions(bom).get((group, artifact)) == boot:
        return boot_upgrade(pom, boot, target, package_name, registry, baseline_pom)
    exact, _ = bom_property_map(bom)
    prop = exact.get((group, artifact))
    if prop is None:
        for cand_prop, bom_ga in imported_candidates(group, bom):
            try:
                bom_versions = registry.maven_versions(*bom_ga.split(":")) or []
                listed = target in bom_versions and lists_artifact(
                    registry.maven_pom(*bom_ga.split(":"), target), group, artifact)
            except RegistryError as e:
                return "failed", f"{bom_ga} illisible : {e}"
            if listed:
                prop = cand_prop
                break
    if prop is None:
        return pin_upgrade(pom, group, artifact, installed, target, ids, baseline_pom)
    current = re.search(rf"<{re.escape(prop)}>([^<]+)</{re.escape(prop)}>", pom)
    if current and version_key(current.group(1)) and compare(current.group(1).strip(), target) >= 0:
        before = re.search(rf"<{re.escape(prop)}>([^<]+)</{re.escape(prop)}>", baseline_pom or pom)
        if baseline_pom is not None and (before is None or _raised_by_cycle(before.group(1).strip(), target)):
            return "applied", f"{prop} = {current.group(1).strip()} (monte par ce cycle, couvre {package_name})"
        return "already", f"{prop} deja a {current.group(1).strip()} (>= {target})"
    comment = f"Fix {', '.join(ids)} : {artifact} {installed} -> {target}"
    new_pom, _ = _set_property(pom, prop, target, comment)
    _write(POM, new_pom)
    return "applied", f"{prop} = {target} ({package_name} {installed} -> {target})"


def boot_upgrade(pom, boot, target, package_name, registry, baseline_pom):
    """Module de Spring Boot : seule la version du parent le monte (jamais un module isolé),
    dans la même branche mineure."""
    if not version_key(target) or not same_minor(target, boot):
        return "failed", f"{package_name} {target} hors de la branche {boot} du parent Spring Boot"
    if compare(boot, target) >= 0:
        before = boot_version(baseline_pom) if baseline_pom is not None else None
        if before and _raised_by_cycle(before, target):
            return "applied", f"spring-boot-starter-parent = {boot} (monte par ce cycle, couvre {package_name})"
        return "already", f"spring-boot-starter-parent deja a {boot} (>= {target})"
    try:
        published = registry.maven_versions(*BOOT_PARENT) or []
    except RegistryError as e:
        return "failed", f"versions de spring-boot-starter-parent illisibles : {e}"
    if target not in published:
        return "failed", f"spring-boot-starter-parent {target} non publie"
    new_pom = re.sub(r"(<parent>.*?<artifactId>spring-boot-starter-parent</artifactId>\s*<version>)[^<]+(</version>)",
                     rf"\g<1>{target}\g<2>", pom, count=1, flags=re.S)
    _write(POM, new_pom)
    return "applied", f"spring-boot-starter-parent = {target} ({package_name} {boot} -> {target}, module Spring Boot)"


def _dependency_blocks(text):
    """[(début, fin, groupId, artifactId, version|None)] des <dependency> de `text`."""
    out = []
    for m in re.finditer(r"<dependency>(.*?)</dependency>", text, re.S):
        g = re.search(r"<groupId>([^<]+)</groupId>", m.group(1))
        a = re.search(r"<artifactId>([^<]+)</artifactId>", m.group(1))
        v = re.search(r"<version>([^<]+)</version>", m.group(1))
        if g and a:
            out.append((m.start(), m.end(), g.group(1).strip(), a.group(1).strip(), v.group(1).strip() if v else None))
    return out


def _management_span(pom):
    m = re.search(r"<dependencyManagement>.*?</dependencyManagement>", pom, re.S)
    return (m.start(), m.end()) if m else None


def pin_upgrade(pom, group, artifact, installed, target, ids, baseline_pom):
    """Artefact que le BOM Spring Boot ne gère pas (ou pas à cette version) : version de la
    dépendance directe si le pom la fixe, sinon épinglage commenté « Fix » dans
    <dependencyManagement> (impose la version, y compris à une dépendance transitive)."""
    if installed != "?" and major(target) != major(installed):
        return "failed", f"{group}:{artifact} {target} change de version majeure ({installed})"
    comment = f"Fix {', '.join(ids)} : {artifact} {installed} -> {target}"
    span = _management_span(pom)
    for start, end, g, a, v in _dependency_blocks(pom):
        if (g, a) != (group, artifact) or v is None or (span and span[0] <= start < span[1]):
            continue
        prop = re.fullmatch(r"\$\{([^}]+)\}", v)
        if prop:   # version de la dépendance directe portée par une propriété du projet
            current = re.search(rf"<{re.escape(prop.group(1))}>([^<]+)</", pom)
            if current and version_key(current.group(1)) and compare(current.group(1), target) >= 0:
                return "already", f"{prop.group(1)} deja a {current.group(1)} (>= {target})"
            _write(POM, _set_property(pom, prop.group(1), target, comment)[0])
            return "applied", f"{prop.group(1)} = {target} ({group}:{artifact} {installed} -> {target})"
        return "failed", f"{group}:{artifact} : version {v} ecrite en dur dans <dependencies>, montee manuelle"
    if span:
        for start, end, g, a, v in _dependency_blocks(pom[span[0]:span[1]]):
            if (g, a) != (group, artifact) or v is None:
                continue
            if version_key(v) and compare(v, target) >= 0:
                before = [b[4] for b in _dependency_blocks(baseline_pom or "") if b[2:4] == (g, a)]
                if baseline_pom is not None and (not before or _raised_by_cycle(before[0], target)):
                    return "applied", f"epinglage {group}:{artifact} = {v} (monte par ce cycle)"
                return "already", f"epinglage {group}:{artifact} deja a {v} (>= {target})"
            block_start, block_end = span[0] + start, span[0] + end
            line = pom.rfind("\n", 0, block_start) + 1
            indent = pom[line:block_start]
            prev = pom.rfind("\n", 0, line - 1) + 1
            if re.fullmatch(r"[ \t]*" + _FIX_COMMENT + r"[ \t]*\n", pom[prev:line]):
                line = prev   # commentaire « Fix » de l'épinglage remplacé, jamais un autre
            block = pom[block_start:block_end].replace(f"<version>{v}</version>", f"<version>{target}</version>")
            _write(POM, f"{pom[:line]}{indent}<!-- {comment} -->\n{indent}{block}{pom[block_end:]}")
            return "applied", f"epinglage {group}:{artifact} = {target} ({installed} -> {target}, dependencyManagement)"
    _write(POM, _insert_pin(pom, group, artifact, target, comment))
    return "applied", f"epinglage {group}:{artifact} = {target} ({installed} -> {target}, dependencyManagement)"


def _insert_pin(pom, group, artifact, version, comment):
    m = re.search(r"\n([ \t]*)</properties>", pom)
    base = m.group(1) if m else "\t"
    i1, i2, i3 = base + "\t", base + "\t\t", base + "\t\t\t"
    dep = (f"{i2}<!-- {comment} -->\n{i2}<dependency>\n{i3}<groupId>{group}</groupId>\n"
           f"{i3}<artifactId>{artifact}</artifactId>\n{i3}<version>{version}</version>\n{i2}</dependency>\n")
    span = _management_span(pom)
    if span:
        close = pom.rfind("</dependencies>", span[0], span[1])
        if close < 0:
            raise ValueError("pom.xml : <dependencyManagement> sans <dependencies>")
        line = pom.rfind("\n", 0, close) + 1
        return pom[:line] + dep + pom[line:]
    block = f"{base}<dependencyManagement>\n{i1}<dependencies>\n{dep}{i1}</dependencies>\n{base}</dependencyManagement>\n\n"
    top = re.search(rf"\n{re.escape(base)}<dependencies>", pom)
    at = top.start() + 1 if top else pom.rindex("</project>")
    return pom[:at] + block + pom[at:]


def _fix_pins(pom):
    """Épinglages « Fix » de <dependencyManagement> -> [(début, fin, g, a, version)] ; début
    inclut la ligne du commentaire."""
    span = _management_span(pom)
    if not span:
        return []
    out = []
    for start, end, g, a, v in _dependency_blocks(pom[span[0]:span[1]]):
        s = span[0] + start
        line = pom.rfind("\n", 0, s)
        prev = pom.rfind("\n", 0, line)
        if v and re.fullmatch(r"[ \t]*" + _FIX_COMMENT + r"[ \t]*", pom[prev + 1:line]):
            out.append((prev, span[0] + end, g, a, v))
    return out


def _without(pom, spans):
    for start, end in sorted(spans, reverse=True):
        pom = pom[:start] + pom[end:]
    # <dependencyManagement> vidé : retiré en entier.
    return re.sub(r"\n[ \t]*<dependencyManagement>\s*<dependencies>\s*</dependencies>\s*</dependencyManagement>[ \t]*\n?(?:[ \t]*\n)?",
                  "\n", pom)


def unpinned_versions(pom_text):
    """{g:a: version} résolues par Maven sans les épinglages « Fix », ou None si la résolution
    échoue (rien n'est alors retiré). pom temporaire dans le dossier de cycle, même projet."""
    os.makedirs(os.path.dirname(UNPINNED_POM), exist_ok=True)
    pom = _read(POM)
    _write(UNPINNED_POM, _without(pom, [(s, e) for s, e, *_ in _fix_pins(pom)]))
    try:
        deps = default_maven_deps(pom_file=UNPINNED_POM)
    except RegistryError:
        return None
    finally:
        os.remove(UNPINNED_POM)
    return {ga: vs[0][0] for ga, vs in deps.items() if vs}


def cleanup_stale_overrides(registry, resolve_unpinned=unpinned_versions, bom_path_pattern=None):
    """Retire les surcharges « Fix » devenues inutiles : la version effective ne baisse jamais.
      - propriété : valeur par défaut du BOM Spring Boot >= valeur posée ;
      - épinglage <dependencyManagement> : version que Maven résout sans lui >= version épinglée,
        ou artefact sorti de l'arbre. Résolution impossible : épinglages conservés.
    -> (retraits [texte], avertissements [texte])."""
    pom = _read(POM)
    boot = boot_version(pom)
    bom = boot_bom_text(boot, registry, bom_path_pattern) if boot else None
    if bom is None:
        return [], [f"BOM Spring Boot {boot} introuvable : surcharges non examinees"]
    defaults = bom_properties(bom)
    removed, warnings, spans = [], [], []
    for m in re.finditer(r"\n[ \t]*" + _FIX_COMMENT + r"\n[ \t]*<([A-Za-z0-9._-]+)>([^<]+)</\1>", pom):
        prop, value = m.group(1), m.group(2).strip()
        default = defaults.get(prop)
        if default and version_key(default) and version_key(value) and compare(default, value) >= 0:
            spans.append((m.start(), m.end()))
            removed.append(f"{prop} {value} retire (BOM Spring Boot {boot} : {default})")
    pins = _fix_pins(pom)
    if pins:
        resolved = resolve_unpinned(pom)
        if resolved is None:
            warnings.append("resolution Maven sans epinglages impossible : epinglages conserves")
        else:
            for start, end, g, a, v in pins:
                now = resolved.get(f"{g}:{a}")
                if now is None or (version_key(now) and version_key(v) and compare(now, v) >= 0):
                    spans.append((start, end))
                    removed.append(f"epinglage {g}:{a} {v} retire ("
                                   + (f"resolu sans lui : {now})" if now else "absent de l'arbre)"))
    if spans:
        _write(POM, _without(pom, spans))
    return removed, warnings


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
