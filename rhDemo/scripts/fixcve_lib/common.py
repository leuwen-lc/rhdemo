"""Utilitaires communs : comparaison de versions, JSON, sous-processus."""
import json
import os
import re
import subprocess
import tempfile
import unicodedata

# Pré-versions : jamais une cible de remédiation.
_PRERELEASE_RE = re.compile(
    r"(?i)(alpha|beta|snapshot|preview|nightly|[.-]rc[.-]?\d*$|[.-]rc\d|[.-]cr\d*$|[.-]m\d+$|[.-]ea$)"
)
_NUMERIC_PREFIX_RE = re.compile(r"^v?(\d+(?:\.\d+)*)")


def numeric(version):
    """'7.4.11.Final' -> (7, 4, 11) ; '1.1.21' -> (1, 1, 21) ; None si pas de préfixe numérique."""
    m = _NUMERIC_PREFIX_RE.match(version or "")
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split("."))


def version_key(version):
    """Clé de tri : préfixe numérique complété à 4 champs, une pré-version passant avant la
    version finale de même numéro."""
    n = numeric(version)
    if n is None:
        return None
    padded = tuple(n) + (0,) * (4 - len(n)) if len(n) < 4 else tuple(n)
    return padded + (0 if is_prerelease(version) else 1,)


def is_prerelease(version):
    return bool(_PRERELEASE_RE.search(version or ""))


def compare(a, b):
    """-1, 0, 1 ; lève ValueError si l'une des versions n'est pas comparable."""
    ka, kb = version_key(a), version_key(b)
    if ka is None or kb is None:
        raise ValueError(f"versions non comparables : {a!r}, {b!r}")
    return (ka > kb) - (ka < kb)


def major(version):
    n = numeric(version)
    return n[0] if n else None


def same_minor(a, b):
    na, nb = numeric(a), numeric(b)
    return bool(na and nb and na[:2] == nb[:2])


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path, doc):
    """Écriture atomique (fichier temporaire du même dossier puis rename)."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=True)
        fh.write("\n")
    os.replace(tmp, path)


def run(cmd, timeout=180, cwd=None, env=None):
    """-> (code, stdout, stderr). Ne lève jamais : un échec est un code non nul."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout après {timeout}s"
    except OSError as e:
        return 127, "", str(e)


_ASCII_RE = re.compile(r"[^\x20-\x7E]")


def ascii_text(text, limit=200):
    """Texte libre réduit à l'ASCII imprimable sur une ligne (schémas de fixcve-validate-json.py),
    accents translittérés (é -> e) plutôt que supprimés."""
    text = unicodedata.normalize("NFKD", re.sub(r"\s+", " ", text or "").strip())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return _ASCII_RE.sub("", text)[:limit]


_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(text, limit=1000):
    """Texte libre sur une ligne, accents conservés, sans caractère de contrôle (notes, statements)."""
    text = re.sub(r"\s+", " ", text or "").strip()
    return _CONTROL_RE.sub("", text)[:limit]
