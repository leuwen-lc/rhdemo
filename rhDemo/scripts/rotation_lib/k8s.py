"""Tokens de ServiceAccount portés par des Secrets `kubernetes.io/service-account-token`.

Plusieurs Secrets peuvent porter un token pour le même ServiceAccount : un nouveau Secret est
créé (nouveau token, l'ancien reste valide), vérifié, propagé, puis les anciens Secrets sont
supprimés, ce qui invalide leurs tokens. Les valeurs ne passent que par la mémoire, l'entrée
standard de kubectl ou un fichier temporaire en mémoire (/dev/shm) le temps d'une vérification.
"""
import base64
import contextlib
import os
import subprocess
import tempfile
import time

from .common import RotationError
from . import tools

TOKEN_TYPE = "kubernetes.io/service-account-token"
SA_ANNOTATION = "kubernetes.io/service-account.name"


def current_context():
    return tools.kubectl("config", "current-context").strip()


def admin_server():
    """URL de l'API vue du poste (contexte courant), pour la vérification du nouveau token."""
    return tools.kubectl("config", "view", "--minify", "-o",
                         "jsonpath={.clusters[0].cluster.server}").strip()


def token_secrets(namespace, service_account):
    """Noms des Secrets qui portent un token de ce ServiceAccount (sans lire les valeurs)."""
    out = tools.kubectl(
        "get", "secrets", "-n", namespace, f"--field-selector=type={TOKEN_TYPE}", "-o",
        "jsonpath={range .items[*]}{.metadata.name}{'\\t'}"
        "{.metadata.annotations.kubernetes\\.io/service-account\\.name}{'\\n'}{end}")
    names = []
    for line in out.splitlines():
        name, _, sa = line.partition("\t")
        if name and sa.strip() == service_account:
            names.append(name.strip())
    return names


def create_token_secret(namespace, service_account, name):
    manifest = (
        "apiVersion: v1\nkind: Secret\n"
        f"metadata:\n  name: {name}\n  namespace: {namespace}\n"
        f"  annotations:\n    {SA_ANNOTATION}: {service_account}\n"
        f"  labels:\n    app.kubernetes.io/name: {service_account}\n"
        "    app.kubernetes.io/managed-by: rotate-secrets\n"
        f"type: {TOKEN_TYPE}\n")
    tools.kubectl("create", "-f", "-", stdin=manifest)


def delete_secret(namespace, name):
    tools.kubectl("delete", "secret", name, "-n", namespace, "--wait=true")


def wait_token(namespace, name, timeout=30, poll=1):
    """(token, ca.crt en base64) déposés par le contrôleur de tokens dans le Secret."""
    deadline = time.monotonic() + timeout
    while True:
        token = tools.kubectl("get", "secret", name, "-n", namespace, "-o",
                              "jsonpath={.data.token}").strip()
        if token:
            ca = tools.kubectl("get", "secret", name, "-n", namespace, "-o",
                               "jsonpath={.data.ca\\.crt}").strip()
            return base64.b64decode(token).decode("ascii"), ca
        if time.monotonic() >= deadline:
            raise RotationError(f"Kubernetes : aucun token déposé dans {name} après {timeout} s")
        time.sleep(poll)


def kubeconfig(server, ca_b64, token, user, namespace, cluster, header=""):
    """Kubeconfig à un seul contexte, au format de ceux qu'attendent les Jenkinsfile."""
    return (
        f"{header}"
        "apiVersion: v1\nkind: Config\npreferences: {}\n"
        f"clusters:\n  - name: {cluster}\n    cluster:\n"
        f"      certificate-authority-data: {ca_b64}\n      server: {server}\n"
        f"contexts:\n  - name: {cluster}\n    context:\n      cluster: {cluster}\n"
        f"      namespace: {namespace}\n      user: {user}\n"
        f"current-context: {cluster}\n"
        f"users:\n  - name: {user}\n    user:\n      token: {token}\n")


@contextlib.contextmanager
def temp_kubeconfig(text):
    """Fichier kubeconfig temporaire en mémoire (/dev/shm), mode 600, détruit à la sortie."""
    base = "/dev/shm" if os.path.isdir("/dev/shm") else None
    fd, path = tempfile.mkstemp(prefix="rot-kube-", suffix=".yaml", dir=base)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        yield path
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


def _run(path, *args, timeout=30):
    return subprocess.run(["kubectl", "--kubeconfig", path, *args], capture_output=True,
                          check=False, timeout=timeout)


def whoami(path):
    proc = _run(path, "auth", "whoami", "-o", "jsonpath={.status.userInfo.username}")
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
        raise RotationError(f"Kubernetes : le nouveau token n'authentifie pas ({err[0][:200]})")
    return proc.stdout.decode("utf-8").strip()


def can_i(path, check):
    """`kubectl auth can-i <check>` avec ce kubeconfig : True (yes), False (no)."""
    proc = _run(path, "auth", "can-i", *check.split())
    if proc.returncode in (0, 1):
        return proc.returncode == 0
    err = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
    raise RotationError(f"Kubernetes : auth can-i {check} impossible ({err[0][:200]})")


def verify(text, namespace, service_account, allowed=(), denied=()):
    """Le token authentifie bien le ServiceAccount et a exactement les droits attendus."""
    expected = f"system:serviceaccount:{namespace}:{service_account}"
    with temp_kubeconfig(text) as path:
        who = whoami(path)
        if who != expected:
            raise RotationError(f"Kubernetes : le token authentifie {who or '?'}, attendu {expected}")
        wrong = [f"refusé : {c}" for c in allowed if not can_i(path, c)]
        wrong += [f"accordé : {c}" for c in denied if can_i(path, c)]
    if wrong:
        raise RotationError("Kubernetes : droits inattendus du token (" + " ; ".join(wrong) + ")")
