"""Outils locaux : SOPS (valeur passée sur l'entrée standard) et GPG (trousseau temporaire)."""
import contextlib
import json
import os
import shutil
import subprocess
import tempfile

from .common import RotationError

AGE_KEY_FILE = os.path.expanduser(os.environ.get("SOPS_AGE_KEY_FILE", "~/.config/sops/age/keys.txt"))


def _sops_env():
    return {**os.environ, "SOPS_AGE_KEY_FILE": AGE_KEY_FILE}


def sops_get(path, key_path):
    """Valeur d'une clé d'un fichier SOPS, `key_path` au format SOPS : ["a"]["b"]."""
    proc = subprocess.run(["sops", "decrypt", "--extract", key_path, path], capture_output=True,
                          env=_sops_env(), check=False)
    if proc.returncode != 0:
        raise RotationError(f"SOPS : lecture de {key_path} dans {path} impossible")
    return proc.stdout.decode("utf-8")


def sops_set(path, key_path, value):
    proc = subprocess.run(["sops", "set", "--value-stdin", path, key_path],
                          input=json.dumps(value).encode("utf-8"), capture_output=True,
                          env=_sops_env(), check=False)
    if proc.returncode != 0:
        raise RotationError(f"SOPS : écriture de {key_path} dans {path} impossible")
    if sops_get(path, key_path) != value:
        raise RotationError(f"SOPS : relecture de {key_path} dans {path} incohérente")


@contextlib.contextmanager
def gpg_home():
    """Trousseau jetable, en mémoire (/dev/shm) quand c'est possible, détruit à la sortie."""
    base = "/dev/shm" if os.path.isdir("/dev/shm") else None
    home = tempfile.mkdtemp(prefix="rot-gpg-", dir=base)
    os.chmod(home, 0o700)
    try:
        yield home
    finally:
        subprocess.run(["gpgconf", "--homedir", home, "--kill", "all"], capture_output=True,
                       check=False)
        shutil.rmtree(home, ignore_errors=True)


def _gpg(home, *args, stdin=None):
    cmd = ["gpg", "--homedir", home, "--batch", "--pinentry-mode", "loopback", "--passphrase", "",
           *args]
    proc = subprocess.run(cmd, input=stdin, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RotationError(f"gpg {args[0]} : échec ({proc.stderr.decode('utf-8', 'replace')[-200:].strip()})")
    return proc.stdout


def gpg_generate(home, uid, algo="rsa4096", expire="2y"):
    """Clé de signature sans phrase de passe (importée telle quelle par Renovate).
    Renvoie (empreinte, clé publique armurée, clé privée armurée)."""
    _gpg(home, "--quick-gen-key", uid, algo, "sign", expire)
    fpr = None
    for line in _gpg(home, "--with-colons", "--list-secret-keys").decode().splitlines():
        if line.startswith("fpr:"):
            fpr = line.split(":")[9]
            break
    if not fpr:
        raise RotationError("gpg : empreinte de la nouvelle clé introuvable")
    public = _gpg(home, "--armor", "--export", fpr).decode("ascii")
    private = _gpg(home, "--armor", "--export-secret-keys", fpr).decode("ascii")
    return fpr, public, private


def gpg_sign(home, fpr, text):
    return _gpg(home, "--local-user", fpr, "--armor", "--detach-sign",
                stdin=text.encode("utf-8")).decode("ascii")
