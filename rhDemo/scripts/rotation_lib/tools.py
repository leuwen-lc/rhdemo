"""Outils locaux : GPG (trousseau temporaire), kubectl, port-forward, fichier AppRole."""
import contextlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time

from .common import RotationError

def memory_tmp_dir():
    """Répertoire en mémoire pour les fichiers secrets temporaires, ou None (défaut de tempfile).

    XDG_RUNTIME_DIR d'abord (tmpfs privé à l'utilisateur, mode 700). À défaut /dev/shm, partagé
    mais sans risque ici : mkstemp/mkdtemp y créent un nom imprévisible (O_EXCL) en mode 600/700."""
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    try:
        st = os.stat(runtime) if runtime else None
    except OSError:
        st = None
    if st and stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() and not st.st_mode & 0o077:
        return runtime
    shm = "/dev/shm"  # NOSONAR repli en mémoire, noms imprévisibles et modes 600/700 (voir ci-dessus)
    return shm if os.path.isdir(shm) else None


@contextlib.contextmanager
def gpg_home():
    """Trousseau jetable, en mémoire quand c'est possible (memory_tmp_dir), détruit à la sortie."""
    home = tempfile.mkdtemp(prefix="rot-gpg-", dir=memory_tmp_dir())
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


# --- kubectl (contexte courant de l'utilisateur, jamais une valeur en argument) ------------

def kubectl(*args, stdin=None, timeout=300):
    """Lance kubectl ; une valeur secrète ne passe que par `stdin`. Renvoie stdout (texte)."""
    proc = subprocess.run(["kubectl", *args], input=stdin.encode("utf-8") if stdin else None,
                          capture_output=True, check=False, timeout=timeout)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
        raise RotationError(f"kubectl {args[0]} {args[1] if len(args) > 1 else ''} : échec ({err[0][:200]})")
    return proc.stdout.decode("utf-8")



class PortForward:
    """`kubectl port-forward` vers un port local libre choisi par kubectl, arrêté par close()."""

    def __init__(self, namespace, target, remote_port, timeout=30):
        self.proc = subprocess.Popen(
            ["kubectl", "port-forward", "--address", "127.0.0.1", "-n", namespace, target, f":{remote_port}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.port = None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                break
            m = re.search(r"127\.0\.0\.1:(\d+)", line)
            if m:
                self.port = int(m.group(1))
                return
        err = (self.proc.stderr.read() if self.proc.poll() is not None else "").strip().splitlines()[-1:] or [""]
        self.close()
        raise RotationError(f"kubectl port-forward {target} : échec ({err[0][:200]})")

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# --- fichier AppRole local (cible « approle-file » de l'inventaire, aucune utilisée à ce jour) ----

def approle_file_read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise RotationError(f"fichier AppRole {path} illisible ({type(exc).__name__})") from None
    if not data.get("role_id") or "secret_id" not in data:
        raise RotationError(f"fichier AppRole {path} incomplet (role_id, secret_id)")
    return data


def approle_file_write(path, role_id, secret_id):
    """Écriture atomique, mode 600."""
    tmp = f"{path}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"role_id": role_id, "secret_id": secret_id}, fh)
    os.replace(tmp, path)
