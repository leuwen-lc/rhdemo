"""Tests de la méthode k8s-sa-token (tokens des ServiceAccounts de Jenkins) : faux Jenkins HTTP
local (test_rotation), kubectl simulé (Secrets de token, auth whoami, auth can-i). Aucun cluster."""
import base64
import os
import re
from unittest import mock

import helpers  # noqa: F401  (ajoute scripts/ au chemin)
from test_rotation import Base, _load_cli, field

from rotation_lib import inventory as inv_mod
from rotation_lib import k8s, rotations, tools
from rotation_lib.common import RotationError, Skipped

FILE_TAG = "org.jenkinsci.plugins.plaincredentials.impl.FileCredentialsImpl"
NS, SA = "rhdemo-stagingkub", "jenkins-deployer"

ENTRY = {"id": "kubeconfig-stagingkub", "num": "9", "label": "Kubeconfig Jenkins jenkins-deployer",
         "criticality": "H", "exposure": "local",
         "rotation": {"method": "k8s-sa-token", "namespace": NS, "service_account": SA,
                      "secret_prefix": "jenkins-deployer-token", "kube_context": "kind-rhdemo",
                      "server": "https://rhdemo-control-plane:6443", "cluster": "kind-rhdemo",
                      "allowed": ["get pods -n rhdemo-stagingkub"],
                      "denied": ["get pods -n kube-system"]},
         "targets": [{"kind": "jenkins", "credential": "kubeconfig-stagingkub", "type": "file"}]}


def file_cred(cid, content=b"ancien kubeconfig"):
    return (f"<{FILE_TAG}><scope>GLOBAL</scope><id>{cid}</id><description>kube</description>"
            f"<fileName>kubeconfig</fileName><secretBytes>{base64.b64encode(content).decode()}"
            f"</secretBytes></{FILE_TAG}>")


class FakeCluster:
    """Secrets de token d'un namespace ; droits accordés par ServiceAccount."""

    def __init__(self):
        self.context = "kind-rhdemo"
        self.secrets = {"jenkins-deployer-token": SA, "autre-token": "autre-sa"}
        self.rights = {SA: {"get pods -n rhdemo-stagingkub"}}
        self.calls = []

    @staticmethod
    def token(name):
        return f"tok-{name}"

    def kubectl(self, *args, stdin=None, timeout=300):
        self.calls.append(args)
        if args[:2] == ("config", "current-context"):
            return self.context + "\n"
        if args[:2] == ("config", "view"):
            return "https://127.0.0.1:35541"
        if args[:2] == ("get", "secrets"):
            return "".join(f"{n}\t{sa}\n" for n, sa in self.secrets.items())
        if args[:3] == ("create", "-f", "-"):
            name = re.search(r"name: (\S+)", stdin).group(1)
            sa = re.search(r"service-account.name: (\S+)", stdin).group(1)
            self.secrets[name] = sa
            return ""
        if args[:2] == ("get", "secret"):
            name = args[2]
            if "token" in args[-1]:
                return base64.b64encode(self.token(name).encode()).decode()
            return "Q0EtREFUQQ=="
        if args[:2] == ("delete", "secret"):
            self.secrets.pop(args[2], None)
            return ""
        raise AssertionError(f"kubectl inattendu : {args}")

    def run(self, path, *args, timeout=30):
        """kubectl --kubeconfig <path> auth … : le token du fichier doit être celui d'un Secret."""
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        assert "server: https://127.0.0.1:35541" in text      # vérification vue du poste
        token = re.search(r"token: (\S+)", text).group(1)
        sa = next((s for n, s in self.secrets.items() if self.token(n) == token), None)
        ok = mock.Mock(returncode=0, stdout=f"system:serviceaccount:{NS}:{sa}".encode(), stderr=b"")
        if args[:2] == ("auth", "whoami"):
            return ok if sa else mock.Mock(returncode=1, stdout=b"", stderr=b"Unauthorized")
        if args[:2] == ("auth", "can-i"):
            granted = " ".join(args[2:]) in self.rights.get(sa, set())
            return mock.Mock(returncode=0 if granted else 1, stdout=b"", stderr=b"")
        raise AssertionError(f"kubectl --kubeconfig inattendu : {args}")


class K8sBase(Base):
    """Faux cluster et faux Jenkins, sans test (réutilisé par test_emergency_rotation)."""

    def setUp(self):
        super().setUp()
        self.cluster = FakeCluster()
        for target, fake in ((tools, "kubectl"), (k8s, "_run")):
            p = mock.patch.object(target, fake, self.cluster.kubectl if fake == "kubectl" else self.cluster.run)
            p.start()
            self.addCleanup(p.stop)
        self.inv["secrets"] = [ENTRY]
        self.state.creds["kubeconfig-stagingkub"] = file_cred("kubeconfig-stagingkub")

    def cred_content(self):
        return base64.b64decode(field(self.state.creds["kubeconfig-stagingkub"], "secretBytes")).decode()

    def new_secrets(self):
        return [n for n in self.cluster.secrets if n.startswith("jenkins-deployer-token-")]


class K8sTokenTest(K8sBase):
    def test_rotation_nominale(self):
        detail = rotations.rotate_k8s_sa_token(self.ctx(), ENTRY)
        [new] = self.new_secrets()
        self.assertNotIn("jenkins-deployer-token", self.cluster.secrets)   # ancien token invalidé
        self.assertIn("autre-token", self.cluster.secrets)                 # autre compte intact
        content = self.cred_content()
        self.assertIn("server: https://rhdemo-control-plane:6443", content)
        self.assertIn(f"token: tok-{new}", content)
        self.assertIn("certificate-authority-data: Q0EtREFUQQ==", content)
        self.assertIn(f"Secret {new}, supprimés : jenkins-deployer-token", detail)
        self.assertEqual([f for f in os.listdir("/dev/shm") if f.startswith("rot-kube-")]
                         if os.path.isdir("/dev/shm") else [], [])

    def test_droit_inattendu_annule_tout(self):
        self.cluster.rights[SA].add("get pods -n kube-system")
        with self.assertRaises(RotationError) as cm:
            rotations.rotate_k8s_sa_token(self.ctx(), ENTRY)
        self.assertIn("accordé : get pods -n kube-system", str(cm.exception))
        self.assertEqual(self.new_secrets(), [])
        self.assertIn("jenkins-deployer-token", self.cluster.secrets)
        self.assertEqual(self.cred_content(), "ancien kubeconfig")

    def test_echec_jenkins_supprime_le_nouveau_secret(self):
        self.state.fail_post = True
        with self.assertRaises(RotationError):
            rotations.rotate_k8s_sa_token(self.ctx(), ENTRY)
        self.assertEqual(self.new_secrets(), [])
        self.assertIn("jenkins-deployer-token", self.cluster.secrets)

    def test_if_missing_token_existant_rien_a_faire(self):
        ctx = self.ctx()
        ctx.if_missing = True
        result = rotations.rotate_k8s_sa_token(ctx, ENTRY)
        self.assertIsInstance(result, Skipped)
        self.assertEqual(self.state.requests, [])         # Jenkins pas même contacté
        self.assertEqual(self.new_secrets(), [])

    def test_if_missing_cree_token_et_credential(self):
        del self.cluster.secrets["jenkins-deployer-token"]
        del self.state.creds["kubeconfig-stagingkub"]
        ctx = self.ctx()
        ctx.if_missing = True
        rotations.rotate_k8s_sa_token(ctx, ENTRY)
        [new] = self.new_secrets()
        self.assertEqual(field(self.state.creds["kubeconfig-stagingkub"], "fileName"), "kubeconfig")
        self.assertIn(f"token: tok-{new}", self.cred_content())

    def test_mauvais_contexte_refuse_avant_tout(self):
        self.cluster.context = "autre-cluster"
        with self.assertRaises(RotationError):
            rotations.rotate_k8s_sa_token(self.ctx(), ENTRY)
        self.assertEqual(len(self.cluster.calls), 1)

    def test_dry_run_ne_modifie_rien(self):
        self.assertIsNone(rotations.rotate_k8s_sa_token(self.ctx(dry_run=True), ENTRY))
        self.assertEqual(self.new_secrets(), [])
        self.assertEqual(self.cred_content(), "ancien kubeconfig")

class K8sInventoryTest(Base):
    def test_cibles_jenkins_file_seulement(self):
        bad = {**ENTRY, "targets": [{"kind": "openbao", "path": "x", "key": "y"}]}
        errors = inv_mod.validate({"periods": {}, "services": {}, "secrets": [bad]})
        self.assertTrue(any("jenkins de type file" in e for e in errors), errors)
        self.assertEqual(inv_mod.validate({"periods": {}, "services": {}, "secrets": [ENTRY]}), [])

    def test_inventaire_reel_valide(self):
        inv = inv_mod.load()
        ids = {e["id"] for e in inv["secrets"] if e["rotation"]["method"] == "k8s-sa-token"}
        self.assertEqual(ids, {"kubeconfig-stagingkub", "kubeconfig-stagingkub-infra-upgrader"})

    def test_if_missing_reserve_aux_tokens_kubernetes(self):
        mod = _load_cli()
        self.assertEqual(mod.main(["--if-missing", "grafana-admin"]), 2)
        self.assertEqual(mod.main(["--if-missing", "--level", "C"]), 2)
