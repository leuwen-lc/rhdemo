"""Tests du mode --emergency de rotate-secrets.py : révocation avant création (tokens Codeberg,
tokens Kubernetes, secret_id AppRole), ordre d'urgence, procédures manuelles tracées une à une.
Faux Codeberg, Jenkins et OpenBao locaux, kubectl simulé : aucun réseau, aucun cluster."""
import copy
import json
import os
from unittest import mock

import helpers  # noqa: F401  (ajoute scripts/ au chemin)
import test_k8s_rotation as k8s_tests
import test_openbao as bao_tests
import test_rotation as rot
from test_rotation import Base, _load_cli, field

from rotation_lib import inventory as inv_mod
from rotation_lib import rotations, tools
from rotation_lib.common import Journal, RotationError
from rotation_lib.rotations import rotate_forgejo_token


def emergency(ctx):
    ctx.emergency = True
    return ctx


class ForgejoEmergencyTest(Base):
    entry = rot.TokenRotationTest.entry
    seed = rot.TokenRotationTest.seed

    def token_calls(self):
        return [r[0] for r in self.state.requests if "/tokens" in r[1] and r[0] in ("POST", "DELETE")]

    def test_tous_les_tokens_revoques_avant_creation_sans_question(self):
        self.seed()
        self.state.tokens[1]["scopes"] = ["write:repository"]      # portées divergentes : sans effet
        ctx = emergency(self.ctx(confirm=False))
        detail = rotate_forgejo_token(ctx, self.entry())
        self.assertEqual(ctx.prompter.asked, [])
        self.assertEqual(self.token_calls(), ["DELETE", "DELETE", "POST"])
        (new,) = self.state.tokens.values()
        self.assertEqual(field(self.state.creds["ci-token"], "secret"), new["sha1"])
        self.assertIn("hand-made", detail)

    def test_echec_verification_compte_sans_token(self):
        self.seed()
        self.state.push = False
        ctx = emergency(self.ctx())
        entry = self.entry()
        with self.assertRaisesRegex(RotationError, "écriture"):
            rotate_forgejo_token(ctx, entry)
        self.assertEqual(self.state.tokens, {})                     # anciens révoqués, nouveau supprimé
        self.assertEqual(field(self.state.creds["ci-token"], "secret"), "old")

    def test_dry_run_ne_revoque_rien(self):
        self.seed()
        self.assertIsNone(rotate_forgejo_token(emergency(self.ctx(dry_run=True)), self.entry()))
        self.assertEqual(set(self.state.tokens), {1, 2})


class K8sEmergencyTest(k8s_tests.K8sBase):
    def test_ancien_secret_supprime_avant_creation(self):
        rotations.rotate_k8s_sa_token(emergency(self.ctx()), k8s_tests.ENTRY)
        verbs = [c[0] for c in self.cluster.calls if c[0] in ("create", "delete")]
        self.assertEqual(verbs, ["delete", "create"])
        self.assertIn(f"token: tok-{self.new_secrets()[0]}", self.cred_content())

    def test_droit_inattendu_ancien_deja_supprime(self):
        self.cluster.rights[k8s_tests.SA].add("get pods -n kube-system")
        ctx = emergency(self.ctx())
        with self.assertRaises(RotationError):
            rotations.rotate_k8s_sa_token(ctx, k8s_tests.ENTRY)
        self.assertNotIn("jenkins-deployer-token", self.cluster.secrets)
        self.assertEqual(self.new_secrets(), [])


class ApproleEmergencyTest(bao_tests.Base):
    entry = bao_tests.ApproleRotationTest.entry

    def test_ancien_detruit_avant_le_nouveau(self):
        old_sid, _ = self.admin().new_secret_id("jenkins-cosign")
        path = os.path.join(self.tmp, "ar.json")
        tools.approle_file_write(path, "role-cosign", old_sid)
        rotations.rotate_openbao_approle(emergency(self.ctx()), self.entry(path))
        calls = [r[1].rsplit("/", 1)[-1] for r in self.st.requests
                 if r[1].endswith(("/secret-id", "/destroy")) and r[0] == "POST"]
        self.assertEqual(calls[-2:], ["destroy", "secret-id"])
        self.assertEqual(len(self.st.secret_ids), 1)
        self.assertNotEqual(tools.approle_file_read(path)["secret_id"], old_sid)


class OrderTest(Base):
    def test_ordre_et_compromission(self):
        inv = inv_mod.load()
        normal = [e["id"] for e in inv_mod.emergency_order(inv)]
        self.assertNotIn("ephemere-secrets", normal)
        self.assertEqual(normal[:1], ["ci-bot-forgejo-token"])
        first = [e["id"] for e in inv_mod.emergency_order(inv, compromised=True)]
        self.assertEqual(first[:2], inv["emergency_first"])
        self.assertEqual(sorted(first), sorted(normal))
        self.assertEqual(inv_mod.by_id(inv, "jenkins-admin-password")["rotation"]["session"], "jenkins")

    def test_validation(self):
        inv = copy.deepcopy(inv_mod.load())
        inv["emergency_first"] = ["inconnu"]
        inv["secrets"][0]["rotation"]["session"] = "codeberg"
        errors = "\n".join(inv_mod.validate(inv))
        self.assertIn("emergency_first : secret inconnu inconnu", errors)
        self.assertIn("session codeberg inconnue", errors)


class CliEmergencyTest(Base):
    def manual(self, sid, **extra):
        return {"id": sid, "num": "10", "label": sid, "criticality": "C", "exposure": "local",
                "rotation": {"method": "manual", "procedure": f"faire {sid}", **extra}}

    def journal_lines(self):
        with open(self.journal.path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh]

    def test_procedures_manuelles_tracees_une_a_une(self):
        mod = _load_cli()
        ctx = emergency(self.ctx(confirm=True))
        ctx._jenkins = object()                                      # session Jenkins ouverte
        entries = [self.manual("jenkins-admin-password", session="jenkins"), self.manual("autre")]
        self.assertEqual(mod.cmd_rotate(ctx, entries), 0)
        self.assertIsNone(ctx._jenkins)                              # mot de passe redemandé ensuite
        self.assertEqual(ctx.prompter.dropped, "jenkins")
        self.assertEqual([(j["id"], j["action"]) for j in self.journal_lines()],
                         [("jenkins-admin-password", "recorded"), ("autre", "recorded")])

    def test_procedure_non_faite_reste_a_faire(self):
        mod = _load_cli()
        ctx = emergency(self.ctx(confirm=False))
        with mock.patch.object(mod, "warn") as warned:
            self.assertEqual(mod.cmd_rotate(ctx, [self.manual("autre")]), 1)
        self.assertTrue(any("restent à faire : autre" in c.args[0] for c in warned.call_args_list))
        self.assertFalse(os.path.exists(self.journal.path))

    def test_abandon_sans_confirmation_et_options_incompatibles(self):
        mod = _load_cli()
        journal = os.path.join(self.tmp, "j.jsonl")
        with mock.patch.object(mod, "Journal", return_value=Journal(journal)), \
                mock.patch("builtins.input", return_value="n"):
            self.assertEqual(mod.main(["--emergency"]), 1)
        self.assertFalse(os.path.exists(journal))
        for argv in (["--emergency", "grafana-admin"], ["--emergency", "--no"], ["--compromised", "x"]):
            with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
                mod.main(argv)

    def test_hors_urgence_procedure_seulement_affichee(self):
        mod = _load_cli()
        ctx = self.ctx(confirm=True)
        self.assertEqual(mod.cmd_rotate(ctx, [self.manual("autre")]), 0)
        self.assertEqual(ctx.prompter.asked, [])
