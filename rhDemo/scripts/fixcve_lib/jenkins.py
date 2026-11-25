"""API Jenkins du poller (lecture seule) et extraction de la cause d'un échec de build.

Authentification par en-tête HTTP Basic : le jeton n'apparaît jamais dans les arguments d'une
commande (visibles dans `ps`), contrairement à l'ancien `curl -u` du poller Bash.
"""
import base64
import json
import re
import time
import urllib.error
import urllib.request

JOB = "RHDemo-CI"
TIMEOUT_SECONDS = 30
# Mêmes erreurs transitoires que `curl --retry 3 --retry-delay 2` : délai, 408, 429, 5xx.
RETRIES = 3
RETRY_DELAY_SECONDS = 2
_TRANSIENT_CODES = {408, 429, 500, 502, 503, 504}


class JenkinsError(Exception):
    """Appel en échec. `code` : statut HTTP, ou None si Jenkins est injoignable."""

    def __init__(self, url, code, cause=""):
        super().__init__(f"{url} : HTTP {code or '000'} {cause}".strip())
        self.url = url
        self.code = code


class Jenkins:
    def __init__(self, url, user, token, job=JOB, retry_delay=RETRY_DELAY_SECONDS):
        self.url = url.rstrip("/")
        self.job = job
        self.retry_delay = retry_delay
        self._auth = "Basic " + base64.b64encode(f"{user}:{token}".encode()).decode()

    def job_url(self, path):
        return f"{self.url}/job/{self.job}/{path}"

    def get(self, url):
        """Corps de la réponse (texte). Lève JenkinsError après les nouvelles tentatives."""
        last = None
        for attempt in range(RETRIES + 1):
            if attempt:
                time.sleep(self.retry_delay)
            req = urllib.request.Request(url, headers={"Authorization": self._auth})
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # NOSONAR URL du job
                    return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                e.close()
                last = JenkinsError(url, e.code)
                if e.code not in _TRANSIENT_CODES:
                    raise last from None
            except (urllib.error.URLError, OSError) as e:
                last = JenkinsError(url, None, str(getattr(e, "reason", e)))
        raise last

    def json(self, url):
        try:
            return json.loads(self.get(url))
        except ValueError:
            raise JenkinsError(url, 200, "réponse JSON illisible") from None

    def text_or_empty(self, url):
        """Best-effort : chaîne vide en cas d'échec (contexte d'un rollback)."""
        try:
            return self.get(url)
        except JenkinsError:
            return ""


# --- Cause réelle d'un build en échec (incident #819) --------------------------------------------
#  - wfapi/describe impute le FAILED au premier stage SAUTÉ ("skipped due to earlier failure(s)")
#    quand le vrai coupable lève error() dans un bloc script suivi d'un post{always} : ce stage-là
#    reste SUCCESS. On repart de la console : dernier stage entré avant la 1re ligne « skipped ».
#  - Un `[ERROR]` global ramasse du bruit (npm warn deprecated étiqueté [ERROR]) et rate les vraies
#    lignes d'échec ("ÉCHEC: 1 vulnérabilités CRITICAL détectées") : on isole le bloc du stage fautif.

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_FLOWNODE_RE = re.compile(r"ha:////[A-Za-z0-9+/=]*")
_SKIPPED_RE = re.compile(r'Stage "([^"]+)" skipped due to earlier failure')
_STAGE_RE = re.compile(r"\[Pipeline\] \{ \(.+\)\s*$")
_EXPLICIT_RE = re.compile(r"ÉCHEC|ERREUR|CRITICAL|BUILD FAILURE|Caused by:|error: |Error: ")
_BLOCK_END = {"[Pipeline] // stage", "[Pipeline] stage", "Post stage"}
DETAIL_LIMIT = 1200


def clean_console(console):
    lines = []
    for line in (console or "").split("\n"):
        line = _FLOWNODE_RE.sub("", _ANSI_RE.sub("", line))
        lines.append(line[:-1] if line.endswith("\r") else line)
    return lines


def _joined(lines):
    return "".join(line + " " for line in lines)[:DETAIL_LIMIT]


def _stage_before_first_skip(lines):
    prev = cur = ""
    for line in lines:
        if _STAGE_RE.search(line):
            name = re.sub(r"\)\s*$", "", line.rsplit("[Pipeline] { (", 1)[1])
            # Pseudo-stages : librairie (rhDemo/vars/x.groovy) et branches parallèles.
            if "/" in name or name.startswith("Branch: "):
                continue
            prev, cur = cur, name
        elif _SKIPPED_RE.search(line):
            return prev
    return ""


def failure_context(wfapi, console):
    """-> (stage fautif, extrait de log). `wfapi` : JSON de wfapi/describe (ou None)."""
    lines = clean_console(console)
    skipped = {m.group(1) for line in lines for m in _SKIPPED_RE.finditer(line)}
    failed = [s for s in ((wfapi or {}).get("stages") or []) if s.get("status") == "FAILED"]
    failed.sort(key=lambda s: (s.get("startTimeMillis") is not None, s.get("startTimeMillis") or 0))
    wf_stage = failed[0].get("name") or "" if failed else ""
    stage = wf_stage
    if not stage or stage in skipped:
        stage = _stage_before_first_skip(lines) or wf_stage
    stage = stage or "inconnu"

    detail = ""
    if stage != "inconnu":
        marker, capturing, block = f"[Pipeline] {{ ({stage})", False, []
        for line in lines:
            if marker in line:
                capturing = True
                continue
            if capturing and (_SKIPPED_RE.search(line) or line in _BLOCK_END):
                capturing = False
            if capturing and not line.startswith("[Pipeline]") and line.strip():
                block.append(line)
        detail = _joined(block[-12:])
    if not detail:
        detail = _joined([line for line in lines if _EXPLICIT_RE.search(line)][-8:])
    if not detail:
        detail = _joined([line for line in lines if "[ERROR]" in line][-8:])
    return stage, detail or "non disponible"
