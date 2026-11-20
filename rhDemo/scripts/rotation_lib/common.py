"""Outils communs : erreurs, saisies, HTTP, journal local, configuration locale."""
import datetime
import getpass
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request

STATE_DIR = os.path.expanduser(os.environ.get("ROTATION_STATE_DIR", "~/.config/rhdemo-rotation"))


class RotationError(Exception):
    """Échec d'une rotation : le message ne contient jamais de valeur secrète."""


def log(msg=""):
    print(msg, flush=True)


def new_password():
    """43 caractères URL-safe (256 bits)."""
    return secrets.token_urlsafe(32)


def stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_state_dir():
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)


class Prompter:
    """Saisies interactives. Les secrets saisis restent en mémoire pour la session."""

    OTP_REUSE_SECONDS = 25

    def __init__(self, assume_no=False):
        self._secrets = {}
        self._otp = {}
        self.assume_no = assume_no

    def secret(self, key, label):
        if key not in self._secrets:
            value = getpass.getpass(f"{label} : ")
            if not value:
                raise RotationError(f"saisie vide : {label}")
            self._secrets[key] = value
        return self._secrets[key]

    def otp(self, user, fresh=False):
        """Code TOTP, réutilisé quelques secondes pour limiter les saisies (Forgejo ne refuse pas
        la réutilisation d'un code sur l'API). Vide si le compte n'a pas de 2FA."""
        cached = self._otp.get(user)
        if cached and not fresh and time.monotonic() - cached[1] < self.OTP_REUSE_SECONDS:
            return cached[0]
        code = input(f"Code TOTP de {user} (vide si pas de 2FA) : ").strip()
        self._otp[user] = (code, time.monotonic())
        return code

    def drop(self, key):
        """Oublie un secret refusé, pour qu'il soit redemandé."""
        self._secrets.pop(key, None)

    def text(self, label):
        return input(f"{label} : ").strip()

    def confirm(self, question):
        if self.assume_no:
            return False
        return input(f"{question} [o/N] ").strip().lower() in ("o", "oui", "y", "yes")

    def forget(self):
        self._secrets.clear()
        self._otp.clear()


def http(method, url, headers=None, body=None, opener=None, timeout=30):
    """Requête HTTP. Renvoie (statut, octets du corps) sans lever sur les codes d'erreur."""
    headers = dict(headers or {})
    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with (opener or urllib.request.build_opener()).open(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        with exc:
            return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise RotationError(f"{method} {url.split('?')[0]} : {exc.reason}") from None


# Chaîne longue sans espace (token, mot de passe généré, empreinte) : jamais recopiée telle
# quelle. Forgejo, par exemple, renvoie la valeur saisie dans son message d'erreur 401.
_LONG_TOKEN = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")


def redact(text):
    return _LONG_TOKEN.sub("[masqué]", text)


def short(body):
    """Extrait lisible et masqué d'une réponse d'erreur (tronqué)."""
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    return redact(" ".join(text.split()))[:300]


class Journal:
    """Journal local des rotations (JSON lines), jamais de valeur."""

    def __init__(self, path=None):
        self.path = path or os.path.join(STATE_DIR, "journal.jsonl")

    def append(self, secret_id, action, detail=""):
        ensure_state_dir()
        entry = {"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                 "id": secret_id, "action": action, "detail": detail}
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def last_rotations(self):
        last = {}
        if not os.path.exists(self.path):
            return last
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                    if e.get("action") not in ("rotated", "recorded"):
                        continue
                    ts = datetime.datetime.fromisoformat(e["ts"])
                except (ValueError, KeyError):
                    continue
                if e["id"] not in last or ts > last[e["id"]]:
                    last[e["id"]] = ts
        return last



def warn(msg):
    print(f"⚠️  {msg}", file=sys.stderr, flush=True)
