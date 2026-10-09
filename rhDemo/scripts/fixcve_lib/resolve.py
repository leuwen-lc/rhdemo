"""Étape 2 — recherche de correctif, par finding, sans LLM (remplace la phase 2 /fixcve-auto-lookup).

Règle commune : l'avis (OSV) dit quelle version corrige, branche par branche ; le registre confirme
qu'elle est publiée. Jamais de montée de version majeure. `lookup_failed` est réservé aux pannes
réelles (OSV et registre injoignables) : c'est un état transitoire, jamais une conclusion.

Sortie : lookup.json (schéma « lookup » de fixcve-validate-json.py), entrées enrichies de champs
optionnels : `aliases` (toutes les formes CVE/GHSA connues), `proof` (d'où vient la version
cible), `npm_dev_only`, `maven_scopes`.
"""
import html
import os
import re

from . import npm as npm_mod
from .common import ascii_text, compare, is_prerelease, major, numeric, run, same_minor, version_key
from .osv import OsvError, advisory_fix
from .registry import IMAGES, RegistryError
from .suppressions import OWASP_FILE, TRIVY_FILE, parse_owasp, parse_trivy

JENKINSFILE = "Jenkinsfile-CI"


class Context:
    """Accès externes injectables (tests hors réseau)."""

    def __init__(self, osv, registry, audit=None, dry_run=None, lock_index=None,
                 maven_deps=None, image_refs=None, log=None):
        self.osv = osv
        self.registry = registry
        self._audit = audit                # callable -> doc npm audit (ou None)
        self._dry_run = dry_run            # callable -> doc `npm audit fix --dry-run`
        self._lock_index = lock_index      # dict ou callable
        self._maven_deps = maven_deps      # callable -> {g:a: [(version, scope)]}
        self._image_refs = image_refs      # callable -> {jeton: (tag, digest)}
        self.log = log or (lambda msg: None)
        self._cache = {}

    def _memo(self, key, producer):
        if key not in self._cache:
            self._cache[key] = producer() if callable(producer) else producer
        return self._cache[key]

    def audit(self):
        return self._memo("audit", lambda: npm_mod.usable_audit(self._audit() if self._audit else None))

    def dry_run_versions(self):
        return self._memo("dry", lambda: npm_mod.dry_run_versions(self._dry_run() if self._dry_run else None))

    def lock_index(self):
        return self._memo("lock", self._lock_index if self._lock_index is not None else {})

    def maven_deps(self):
        return self._memo("mvn", self._maven_deps if self._maven_deps is not None else {})

    def image_refs(self):
        return self._memo("img", self._image_refs if self._image_refs is not None else {})


# ----------------------------------------------------------------------------------------------
# Accès par défaut (production)
# ----------------------------------------------------------------------------------------------

def default_maven_deps():
    """{groupId:artifactId: [(version, scope)]} via `mvnw dependency:list` (toutes portées)."""
    out_file = os.path.abspath(".fixcve-cycle/dependency-list.txt")
    code, _, err = run(["./mvnw", "-q", "-B", "dependency:list", "-DincludeScope=test",
                        f"-DoutputFile={out_file}", "-DoutputAbsoluteArtifactFilename=false"], timeout=600)
    deps = {}
    if code != 0 or not os.path.exists(out_file):
        raise RegistryError(f"mvnw dependency:list en échec : {err.strip()[-300:]}")
    with open(out_file, encoding="utf-8") as fh:
        for line in fh:
            parts = line.strip().split(":")
            # groupId:artifactId:type[:classifier]:version:scope[ -- module ...]
            if len(parts) >= 5:
                scope = parts[-1].split()[0]
                deps.setdefault(f"{parts[0]}:{parts[1]}", []).append((parts[-2], scope))
    return deps


def default_image_refs(path=JENKINSFILE):
    """{jeton: (tag, digest)} lus dans les variables *_IMAGE de Jenkinsfile-CI."""
    refs = {}
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return refs
    for token, image in IMAGES.items():
        m = re.search(rf'{image["variable"]}\s*=\s*"{re.escape(image["repository"])}:([^@"]+)@(sha256:[0-9a-f]{{64}})"', text)
        if m:
            refs[token] = (m.group(1), m.group(2))
    return refs


# ----------------------------------------------------------------------------------------------
# Par écosystème
# ----------------------------------------------------------------------------------------------

def _entry(finding, status, target=None, digest=None, source="osv", proof=None, aliases=None, **extra):
    entry = {"finding_id": finding["finding_id"], "package_name": finding["package_name"],
             "fix_status": status, "target_version": target, "target_digest": digest,
             "source_checked": source}
    if proof:
        entry["proof"] = proof
    if aliases:
        entry["aliases"] = sorted(set(aliases) - {finding["finding_id"]})
    entry.update({k: v for k, v in extra.items() if v is not None})
    return entry


def _ids(finding):
    return [finding["finding_id"], *finding.get("advisory_aliases", [])]


def resolve_npm(finding, ctx):
    name, installed = finding["package_name"], finding["installed_version"]
    dev_only = npm_mod.npm_dev_only(ctx.lock_index(), name, installed)
    status, target = npm_mod.classify_audit(name, ctx.audit(), ctx.dry_run_versions)
    kind, fixed, aliases = advisory_fix(ctx.osv, _ids(finding), "npm", name, installed)
    if status == "fix_available":
        return _entry(finding, status, target, source="npm_audit", proof="npm_audit",
                      aliases=aliases, npm_dev_only=dev_only)
    if kind == "fix" and major(fixed) == major(installed):
        try:
            published = fixed in (ctx.registry.npm_versions(name) or [])
        except RegistryError:
            published = False
        if published:
            return _entry(finding, "fix_available", fixed, source="osv", proof="advisory",
                          aliases=aliases, npm_dev_only=dev_only)
    if kind == "error":
        # OSV injoignable : jamais de conclusion « sans correctif ». npm audit hors ligne renvoie un
        # rapport vide d'apparence valide (constaté dans le bac à sable) : seul, il ne prouve rien.
        return _entry(finding, "lookup_failed", source="npm_audit", aliases=aliases, npm_dev_only=dev_only)
    # Avis lu ou npm audit concluant : aucun correctif automatisable dans la branche.
    return _entry(finding, "no_fix_available", source="osv" if kind in ("fix", "none") else "npm_audit",
                  aliases=aliases, npm_dev_only=dev_only)


def _maven_scopes(ctx, package_name):
    try:
        return sorted({scope for (_, scope) in ctx.maven_deps().get(package_name, [])}) or None
    except RegistryError:
        return None


def resolve_maven_project(finding, ctx):
    """Dépendance du pom.xml du projet (image rhdemo-app)."""
    name, installed = finding["package_name"], finding["installed_version"]
    group, _, artifact = name.partition(":")
    scopes = _maven_scopes(ctx, name)
    try:
        published = ctx.registry.maven_versions(group, artifact)
    except RegistryError:
        published = None
    if published is not None and installed not in published:
        # Garde-fou : une liste qui ne contient pas la version installée est incohérente.
        return _entry(finding, "lookup_failed", source="maven_central", maven_scopes=scopes)
    kind, fixed, aliases = advisory_fix(ctx.osv, _ids(finding), "maven", name, installed)
    if kind == "fix":
        if major(fixed) != major(installed):
            return _entry(finding, "no_fix_available", aliases=aliases, maven_scopes=scopes)
        if published is None:
            return _entry(finding, "lookup_failed", source="maven_central", aliases=aliases, maven_scopes=scopes)
        if fixed in published:
            return _entry(finding, "fix_available", fixed, proof="advisory", aliases=aliases, maven_scopes=scopes)
        # Version corrigée annoncée mais pas (encore) publiée : aucun correctif aujourd'hui.
        return _entry(finding, "no_fix_available", aliases=aliases, maven_scopes=scopes)
    if kind == "none":
        return _entry(finding, "no_fix_available", aliases=aliases, maven_scopes=scopes)
    if published is None:
        return _entry(finding, "lookup_failed", source="maven_central", aliases=aliases, maven_scopes=scopes)
    # Avis inconnu d'OSV (ou OSV injoignable) : heuristique historique, dernière version stable de la
    # même branche mineure. Non prouvée : la vérification locale (étape 6) puis la CI tranchent.
    candidates = [v for v in published if not is_prerelease(v) and version_key(v)
                  and same_minor(v, installed) and compare(v, installed) > 0]
    if candidates:
        best = max(candidates, key=version_key)
        return _entry(finding, "fix_available", best, source="maven_central", proof="heuristic",
                      aliases=aliases, maven_scopes=scopes)
    return _entry(finding, "no_fix_available", source="maven_central", aliases=aliases, maven_scopes=scopes)


def _tag_suffix(tag):
    """Suffixe de variante d'un tag ('1.31.3-alpine' -> '-alpine', '18.4-alpine3.22' -> '-alpine3.22')."""
    m = re.match(r"^v?\d+(?:\.\d+)*(.*)$", tag or "")
    return m.group(1) if m else ""


def resolve_image(finding, ctx):
    """Composant d'une image tierce (paquet système, ou jar embarqué) : seul un nouveau tag corrige.

    Candidates = versions corrigées annoncées par Trivy (`fixed_versions`) supérieures à la version
    installée, même branche mineure d'abord ; retenue = la 1re qui existe en tag (avec le suffixe de
    variante du tag courant) ET est plus récente que le tag courant. Un numéro de bibliothèque
    (bcprov 1.85) n'est jamais un tag : no_fix_available, décision humaine (incidents #812-#823)."""
    token = finding["image"]
    current = ctx.image_refs().get(token)
    if finding["ecosystem"] == "docker":
        # Paquet système : `fixed_versions` = version de paquet de la distribution (ex. 2.7.5-r0),
        # jamais un tag d'image ; quel tag l'embarque n'est pas lisible sans scanner l'image.
        return _entry(finding, "no_fix_available", source="trivy_report")
    if token not in IMAGES or current is None:
        return _entry(finding, "no_fix_available", source="docker_registry")
    current_tag, _ = current
    installed = finding["installed_version"]
    fixed_versions = [v for v in finding.get("fixed_versions") or [] if version_key(v)]
    candidates = [v for v in fixed_versions if version_key(installed) and compare(v, installed) > 0]
    candidates.sort(key=lambda v: (not same_minor(v, installed), version_key(v)))
    suffix = _tag_suffix(current_tag)
    try:
        for cand in candidates:
            for tag in ([cand + suffix, cand] if suffix else [cand]):
                if version_key(tag) is None or compare(tag, current_tag) <= 0:
                    continue
                digest = ctx.registry.image_digest(token, tag)
                if digest:
                    return _entry(finding, "fix_available", tag, digest, source="docker_registry",
                                  proof="trivy_fixed_versions")
    except RegistryError:
        return _entry(finding, "lookup_failed", source="docker_registry")
    return _entry(finding, "no_fix_available", source="docker_registry")


def resolve_finding(finding, ctx):
    try:
        if finding["image"] != "rhdemo-app" or finding["ecosystem"] == "docker":
            return resolve_image(finding, ctx)
        if finding["ecosystem"] == "npm":
            return resolve_npm(finding, ctx)
        if finding["ecosystem"] == "maven":
            return resolve_maven_project(finding, ctx)
    except OsvError:
        return _entry(finding, "lookup_failed")
    return _entry(finding, "no_fix_available")


def harmonize_targets(entries):
    """Une seule montée par paquet : tous ses findings prennent la version cible la plus haute."""
    highest = {}
    for e in entries:
        if e["fix_status"] == "fix_available" and e.get("target_digest") is None and version_key(e["target_version"]):
            cur = highest.get(e["package_name"])
            if cur is None or compare(e["target_version"], cur) > 0:
                highest[e["package_name"]] = e["target_version"]
    for e in entries:
        if e["fix_status"] == "fix_available" and e["package_name"] in highest and e.get("target_digest") is None:
            e["target_version"] = highest[e["package_name"]]
    return entries


# ----------------------------------------------------------------------------------------------
# Revérification des suppressions temporaires [PENDING_UPSTREAM_FIX]
# ----------------------------------------------------------------------------------------------

def reverify_pending(ctx, owasp_text, trivy_text):
    """Suppressions temporaires dont un correctif est désormais publié -> entrées pending_reverified.

    Couvert : dépendances npm et Maven du projet. Non couvert (journalisé seulement, décision
    humaine) : jars embarqués dans une image tierce, paquets système d'image."""
    out = []
    lock = ctx.lock_index()
    for block in parse_owasp(owasp_text or ""):
        if not block["pending"] or not block["ecosystem"]:
            continue
        if block["ecosystem"] == "npm":
            installed = sorted({v for (v, _) in lock.get(block["package"], []) if version_key(v)}, key=version_key)
            targets = [(block["package"], installed[0])] if installed else []
        else:
            group, _, artifact = block["package"].partition(":")
            try:
                deps = ctx.maven_deps()
            except RegistryError:
                ctx.log(f"revérification {block['package']} impossible (dependency:list)")
                continue
            targets = [(ga, vs[0][0]) for ga, vs in deps.items()
                       if ga.split(":")[0] == group and (artifact in ("*", "") or ga.split(":")[1] == artifact)]
        for vid in block["ids"]:
            for package, installed in targets:
                try:
                    kind, fixed, vuln_aliases = advisory_fix(ctx.osv, [vid], block["ecosystem"], package, installed)
                except OsvError:
                    kind, fixed, vuln_aliases = "error", None, []
                if kind != "fix" or major(fixed) != major(installed):
                    continue
                try:
                    published = (ctx.registry.npm_versions(package) if block["ecosystem"] == "npm"
                                 else ctx.registry.maven_versions(*package.split(":", 1))) or []
                except RegistryError:
                    continue
                if fixed in published:
                    # Toutes les formes de la faille présentes dans le bloc (CVE + GHSA) : en retirer une
                    # seule laisserait la suppression active pour l'autre.
                    for same in [i for i in block["ids"] if i == vid or i in vuln_aliases]:
                        out.append({"cve_id": same, "package": package,
                                    "previous_note": ascii_text(html.unescape(block["notes"] or "")) or "(sans note)",
                                    "new_fixed_version": fixed})
    for entry in parse_trivy(trivy_text or ""):
        if entry["pending"]:
            ctx.log(f"suppression Trivy temporaire {entry['id']} ({entry['package']}) : revérification "
                    "manuelle (composant d'image tierce, voir docs/SECURITY_ADVISORIES.md)")
    # Dédoublonnage (un même CVE peut figurer dans deux blocs).
    seen, unique = set(), []
    for e in out:
        key = (e["cve_id"], e["package"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def resolve(detected, ctx, owasp_text=None, trivy_text=None):
    entries = harmonize_targets([resolve_finding(f, ctx) for f in detected.get("findings", [])])
    pending = reverify_pending(ctx, owasp_text, trivy_text)
    return {"jenkins_build": detected.get("jenkins_build"), "findings": entries, "pending_reverified": pending}


def read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


__all__ = ["Context", "resolve", "resolve_finding", "default_maven_deps", "default_image_refs",
           "read_text", "OWASP_FILE", "TRIVY_FILE", "numeric"]
