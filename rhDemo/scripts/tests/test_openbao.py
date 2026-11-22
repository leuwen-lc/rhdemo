"""Tests de l'intégration OpenBao (rotation_lib/openbao.py, méthodes openbao-approle et
postgres-password, openbao-setup.py) : faux OpenBao HTTP local, kubectl simulé.
Aucun accès réseau, aucun cluster."""
import base64
import importlib.util
import json
import os
import shutil
import tempfile
import threading
import unittest
import uuid
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import helpers  # noqa: F401  (ajoute scripts/ au chemin)

from rotation_lib import inventory as inv_mod
from rotation_lib import rotations, tools
from rotation_lib.common import Journal, RotationError
from rotation_lib.openbao import OpenBao

ADMIN_PW = "admin-pw"


class FakeBao:
    def __init__(self):
        self.lock = threading.Lock()
        self.sealed = False
        self.kv = {}            # path -> list de versions (dict)
        self.tokens = {"root-token"}
        self.role_ids = {"fixcve": "role-fixcve", "jenkins": "role-jenkins"}
        self.secret_ids = {}    # accessor -> (role, secret_id)
        self.requests = []


def make_handler(st):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, code, body=None):
            data = json.dumps(body).encode() if body is not None else b""
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def handle_any(self, method):
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n)) if n else {}
            path = self.path.split("?")[0]
            with st.lock:
                st.requests.append((method, path, body))
                if st.sealed:
                    return self.reply(503, {"errors": ["Vault is sealed"]})
                if path.startswith("/v1/auth/userpass/login/"):
                    if body.get("password") != ADMIN_PW:
                        return self.reply(400, {"errors": ["invalid username or password"]})
                    tok = f"s.{uuid.uuid4().hex}"
                    st.tokens.add(tok)
                    return self.reply(200, {"auth": {"client_token": tok}})
                if path == "/v1/auth/approle/login":
                    for role, sid in st.secret_ids.values():
                        if st.role_ids.get(role) == body.get("role_id") and sid == body.get("secret_id"):
                            tok = f"s.{uuid.uuid4().hex}"
                            st.tokens.add(tok)
                            return self.reply(200, {"auth": {"client_token": tok}})
                    return self.reply(400, {"errors": ["invalid secret id"]})
                if self.headers.get("X-Vault-Token") not in st.tokens:
                    return self.reply(403, {"errors": ["permission denied"]})
                if path == "/v1/auth/token/revoke-self":
                    st.tokens.discard(self.headers.get("X-Vault-Token"))
                    return self.reply(204)
                if path.startswith("/v1/kv/data/"):
                    p = path[len("/v1/kv/data/"):]
                    if method == "GET":
                        if p not in st.kv:
                            return self.reply(404, {"errors": []})
                        return self.reply(200, {"data": {"data": st.kv[p][-1]}})
                    cas = (body.get("options") or {}).get("cas")
                    if cas is not None and cas != len(st.kv.get(p, [])):
                        return self.reply(400, {"errors": ["check-and-set parameter did not match"]})
                    st.kv.setdefault(p, []).append(body["data"])
                    return self.reply(200, {"data": {"version": len(st.kv[p])}})
                if path.startswith("/v1/kv/metadata/"):
                    p = path[len("/v1/kv/metadata/"):]
                    if p not in st.kv:
                        return self.reply(404, {"errors": []})
                    return self.reply(200, {"data": {"current_version": len(st.kv[p])}})
                parts = path.split("/")
                if path.startswith("/v1/auth/approle/role/"):
                    role = parts[5]
                    tail = "/".join(parts[6:])
                    if tail == "role-id":
                        return self.reply(200, {"data": {"role_id": st.role_ids[role]}})
                    if tail == "secret-id" and method == "POST":
                        acc, sid = uuid.uuid4().hex, uuid.uuid4().hex
                        st.secret_ids[acc] = (role, sid)
                        return self.reply(200, {"data": {"secret_id": sid, "secret_id_accessor": acc}})
                    if tail == "secret-id" and method == "LIST":
                        keys = [a for a, (r, _) in st.secret_ids.items() if r == role]
                        return self.reply(200, {"data": {"keys": keys}}) if keys else self.reply(404, {})
                    if tail == "secret-id-accessor/destroy":
                        st.secret_ids.pop(body["secret_id_accessor"], None)
                        return self.reply(204)
                return self.reply(404, {"errors": ["unsupported path"]})

        do_GET = lambda self: self.handle_any("GET")      # noqa: E731
        do_POST = lambda self: self.handle_any("POST")    # noqa: E731
        do_LIST = lambda self: self.handle_any("LIST")    # noqa: E731
    return H


class StubPrompter:
    def __init__(self, secrets=None):
        self.secrets = {"openbao": ADMIN_PW, **(secrets or {})}

    def secret(self, key, label):
        return self.secrets[key]

    def text(self, label):
        return self.secrets["text"]

    def confirm(self, q):
        return False

    def forget(self):
        pass


class Base(unittest.TestCase):
    def setUp(self):
        self.st = FakeBao()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.st))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.inv = {"periods": {"C": 90, "H": 180, "M": 365}, "secrets": [],
                    "services": {"openbao": {"url": self.url, "admin_user": "admin"}}}

    def ctx(self, dry_run=False):
        return rotations.Context(self.inv, StubPrompter(), Journal(os.path.join(self.tmp, "j.jsonl")),
                                 dry_run=dry_run)

    def admin(self):
        return OpenBao(self.url).login_userpass("admin", ADMIN_PW)


class ClientTest(Base):
    def test_kv_set_conserve_les_autres_cles(self):
        ob = self.admin()
        ob.kv_put("fixcve/codeberg", {"user": "bot", "token": "old"})
        ob.kv_set("fixcve/codeberg", "token", "new")
        self.assertEqual(ob.kv_read("fixcve/codeberg"), {"user": "bot", "token": "new"})
        writes = [r for r in self.st.requests if r[0] == "POST" and r[1] == "/v1/kv/data/fixcve/codeberg"]
        self.assertEqual(writes[-1][2]["options"]["cas"], 1)              # contrôle de version

    def test_kv_set_chemin_absent_cree(self):
        ob = self.admin()
        ob.kv_set("jenkins/x", "value", "v")
        self.assertEqual(ob.kv_read("jenkins/x"), {"value": "v"})
        self.assertIsNone(ob.kv_read("jenkins/absent", missing_ok=True))

    def test_scelle_message_explicite(self):
        ob = self.admin()
        self.st.sealed = True
        with self.assertRaisesRegex(RotationError, "scellé"):
            ob.kv_read("jenkins/x")

    def test_erreur_sans_valeur(self):
        with self.assertRaises(RotationError) as cm:
            OpenBao(self.url).login_userpass("admin", "mauvais-mot-de-passe-0123456789")
        self.assertNotIn("mauvais-mot-de-passe", str(cm.exception))

    def test_close_revoque_la_session(self):
        ctx = self.ctx()
        token = ctx.openbao().token
        ctx.close()
        self.assertNotIn(token, self.st.tokens)


class TargetsTest(Base):
    def test_cible_openbao(self):
        self.admin().kv_put("jenkins/ci", {"value": "old", "keep": "x"})
        ctx = self.ctx()
        entry = {"targets": [{"kind": "openbao", "path": "jenkins/ci", "key": "value"}]}
        rotations.check_targets(ctx, entry)
        self.assertEqual(rotations.propagate(ctx, entry, "tok"), ["OpenBao kv/jenkins/ci value"])
        self.assertEqual(self.admin().kv_read("jenkins/ci"), {"value": "tok", "keep": "x"})

    def test_cible_openbao_absente(self):
        with self.assertRaisesRegex(RotationError, "absent"):
            rotations.check_targets(self.ctx(), {"targets": [{"kind": "openbao", "path": "jenkins/z", "key": "v"}]})


class ApproleRotationTest(Base):
    def entry(self, path):
        return {"id": "openbao-approle-fixcve", "rotation": {"method": "openbao-approle", "role": "fixcve"},
                "targets": [{"kind": "approle-file", "file": path}]}

    def test_rotation_complete(self):
        ob = self.admin()
        old_sid, old_acc = ob.new_secret_id("fixcve")
        path = os.path.join(self.tmp, "ar.json")
        tools.approle_file_write(path, "role-fixcve", old_sid)
        detail = rotations.rotate_openbao_approle(self.ctx(), self.entry(path))
        data = tools.approle_file_read(path)
        self.assertNotEqual(data["secret_id"], old_sid)
        self.assertNotIn(old_acc, self.st.secret_ids)                 # ancien détruit
        self.assertEqual(len(self.st.secret_ids), 1)
        ob.approle_login(data["role_id"], data["secret_id"])          # nouveau valide
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertNotIn(data["secret_id"], detail)

    def test_cible_illisible_rien_cree(self):
        with self.assertRaisesRegex(RotationError, "illisible"):
            rotations.rotate_openbao_approle(self.ctx(), self.entry(os.path.join(self.tmp, "absent.json")))
        self.assertEqual(self.st.secret_ids, {})

    def test_dry_run(self):
        path = os.path.join(self.tmp, "ar.json")
        tools.approle_file_write(path, "role-fixcve", "x")
        self.assertIsNone(rotations.rotate_openbao_approle(self.ctx(dry_run=True), self.entry(path)))
        self.assertEqual(self.st.secret_ids, {})


class FakeKubectl:
    """kubectl simulé : un Secret par ExternalSecret, recopié depuis le KV à chaque force-sync."""

    def __init__(self, bao, fail_exec=False):
        self.bao = bao
        self.calls = []
        self.fail_exec = fail_exec
        self.secret = {}

    def __call__(self, *args, stdin=None, timeout=300):
        self.calls.append((args, stdin))
        if args[0] == "annotate":
            self.secret["rhdemo-db-secret"] = self.bao.kv["stagingkub/rhdemo"][-1]["db_password"]
            return ""
        if args[:2] == ("get", "secret"):
            return base64.b64encode(self.secret.get(args[2], "").encode()).decode()
        if args[0] == "exec" and self.fail_exec:
            raise RotationError("kubectl exec : échec (psql)")
        return ""


class PostgresRotationTest(Base):
    def entry(self):
        return {"id": "stagingkub-rhdemo-db", "rotation": {
            "method": "postgres-password", "kv_path": "stagingkub/rhdemo", "kv_key": "db_password",
            "namespace": "rhdemo-stagingkub", "pod": "postgresql-rhdemo-0", "db_user": "rhdemo",
            "database": "rhdemo", "external_secrets": ["rhdemo-db-secret", "rhdemo-app-secrets"],
            "k8s_secret": "rhdemo-db-secret",
            "restart": ["statefulset/postgresql-rhdemo", "deployment/rhdemo-app"]}}

    def run_with(self, fake):
        old = tools.kubectl
        tools.kubectl = fake
        self.addCleanup(setattr, tools, "kubectl", old)
        return rotations.rotate_postgres_password(self.ctx(), self.entry())

    def test_ordre_et_mot_de_passe_hors_arguments(self):
        self.admin().kv_put("stagingkub/rhdemo", {"db_password": "old", "oidc_client_secret": "c"})
        fake = FakeKubectl(self.st)
        self.run_with(fake)
        new = self.st.kv["stagingkub/rhdemo"][-1]["db_password"]
        self.assertNotEqual(new, "old")
        self.assertEqual(self.st.kv["stagingkub/rhdemo"][-1]["oidc_client_secret"], "c")
        verbs = [c[0][0] for c in fake.calls]
        self.assertLess(verbs.index("annotate"), verbs.index("exec"))      # Secret à jour avant ALTER
        self.assertLess(verbs.index("exec"), verbs.index("rollout"))       # ALTER avant redémarrage
        exec_call = next(c for c in fake.calls if c[0][0] == "exec")
        self.assertIn(new, exec_call[1])                                   # sur l'entrée standard
        for args, _ in fake.calls:
            self.assertNotIn(new, " ".join(args))                          # jamais en argument
        restarted = [c[0][2] for c in fake.calls if c[0][:2] == ("rollout", "restart")]
        self.assertEqual(restarted, ["statefulset/postgresql-rhdemo", "deployment/rhdemo-app"])

    def test_echec_alter_role_retour_arriere(self):
        self.admin().kv_put("stagingkub/rhdemo", {"db_password": "old", "oidc_client_secret": "c"})
        fake = FakeKubectl(self.st, fail_exec=True)
        with self.assertRaises(RotationError):
            self.run_with(fake)
        self.assertEqual(self.st.kv["stagingkub/rhdemo"][-1]["db_password"], "old")
        self.assertEqual(fake.secret["rhdemo-db-secret"], "old")
        self.assertFalse([c for c in fake.calls if c[0][0] == "rollout"])


def load_setup():
    spec = importlib.util.spec_from_file_location("openbao_setup",
                                                  os.path.join(helpers.SCRIPTS, "openbao-setup.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class StubJenkins:
    def __init__(self, creds, fail_tags=()):
        self.creds = dict(creds)
        self.fail = fail_tags
        self.calls = []

    def exists(self, cid):
        return cid in self.creds

    def config_xml(self, cid):
        return self.creds[cid]

    def _store(self, verb, xml):
        root = ET.fromstring(xml)
        self.calls.append((verb, root.tag))
        if any(t in root.tag for t in self.fail):
            raise RotationError(f"Jenkins : {verb} refusé (500)")
        self.creds[root.find("id").text] = xml

    def replace(self, cid, xml):
        self._store("replace", xml)

    def create(self, xml):
        self._store("create", xml)


class MigrateTest(unittest.TestCase):
    OLD = ("<org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl><scope>GLOBAL</scope>"
           "<id>notification-email</id><secret>{AQAAABAAAAAQ}</secret>"
           "</org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl>")

    def setUp(self):
        self.m = load_setup()

    def test_xml_reference_openbao(self):
        root = ET.fromstring(self.m.vault_credential_xml("a&b", "string", "desc <x>"))
        self.assertTrue(root.tag.endswith("VaultStringCredentialImpl"))
        self.assertEqual(root.find("path").text, "kv/jenkins/a&b")
        self.assertEqual(root.find("vaultKey").text, "value")
        self.assertEqual(root.find("engineVersion").text, "2")
        up = ET.fromstring(self.m.vault_credential_xml("d", "username-password", "x"))
        self.assertEqual((up.find("usernameKey").text, up.find("passwordKey").text), ("username", "password"))

    def test_remplacement_en_place_sans_suppression(self):
        jk = StubJenkins({"notification-email": self.OLD})
        xml = self.m.vault_credential_xml("notification-email", "string", "d")
        self.m.replace_credential(jk, "notification-email", xml, "VaultStringCredentialImpl")
        self.assertIn("VaultStringCredentialImpl", jk.creds["notification-email"])
        self.assertEqual([c[0] for c in jk.calls], ["replace"])

    def test_creation_si_absent(self):
        jk = StubJenkins({})
        self.m.replace_credential(jk, "openbao-approle",
                                  self.m.approle_credential_xml("openbao-approle", "d", "r", "s"),
                                  "VaultAppRoleCredential")
        self.assertEqual([c[0] for c in jk.calls], ["create"])

    def test_echec_remplacement_ancien_intact(self):
        jk = StubJenkins({"notification-email": self.OLD}, fail_tags=("Vault",))
        xml = self.m.vault_credential_xml("notification-email", "string", "d")
        with self.assertRaises(RotationError):
            self.m.replace_credential(jk, "notification-email", xml, "VaultStringCredentialImpl")
        self.assertEqual(jk.creds["notification-email"], self.OLD)

    def test_perimetre_jenkins(self):
        self.assertNotIn("smtp-infomaniak-credentials", self.m.JENKINS_CREDENTIALS)
        self.assertIn("notification-email", self.m.JENKINS_CREDENTIALS)


class SetupStagingkubTest(Base):
    def setUp(self):
        super().setUp()
        self.inv = {**inv_mod.load(), "services": self.inv["services"]}
        self.m = load_setup()

    def test_generation_complete(self):
        self.m.cmd_stagingkub(self.ctx())
        rh, kc = self.st.kv["stagingkub/rhdemo"][-1], self.st.kv["stagingkub/keycloak"][-1]
        users = self.st.kv["stagingkub-tests/users"][-1]
        self.assertEqual(set(rh), {"db_password", "oidc_client_secret"})
        self.assertEqual(kc["admin_user"], "admin")
        self.assertGreaterEqual(len(kc["admin_password"]), 40)
        self.assertNotEqual(rh["db_password"], kc["db_password"])
        self.assertEqual(users["iduseradmin"], "rhdemo-admin")
        self.assertEqual(len(users["pwduserconsult"]), 12)

    def test_valeurs_existantes_conservees(self):
        self.admin().kv_put("stagingkub/rhdemo", {"db_password": "garde", "oidc_client_secret": "garde2"})
        self.m.cmd_stagingkub(self.ctx())
        self.assertEqual(len(self.st.kv["stagingkub/rhdemo"]), 1)
        self.assertIn("stagingkub/keycloak", self.st.kv)

    def test_dry_run(self):
        self.m.cmd_stagingkub(self.ctx(dry_run=True))
        self.assertNotIn("stagingkub/rhdemo", self.st.kv)


class SetupFixcveTest(unittest.TestCase):
    """fixcve-auto tourne dans Jenkins : ses credentials sont des références OpenBao kv/jenkins/*."""

    def test_credentials_fixcve_dans_le_perimetre_jenkins(self):
        m = load_setup()
        self.assertEqual(m.JENKINS_CREDENTIALS["fixcve-forgejo-token"][0], "string")
        self.assertEqual(m.JENKINS_CREDENTIALS["fixcve-jenkins-api"][0], "username-password")
        self.assertFalse(hasattr(m, "cmd_fixcve"))

    def test_token_codeberg_cible_kv_jenkins(self):
        e = inv_mod.by_id(inv_mod.load(), "fixcve-forgejo-token")
        self.assertEqual(e["targets"], [{"kind": "openbao", "path": "jenkins/fixcve-forgejo-token", "key": "value"}])
        ids = {x["id"] for x in inv_mod.load()["secrets"]}
        self.assertNotIn("openbao-approle-fixcve", ids)


class InventoryOpenBaoTest(unittest.TestCase):
    def test_nouvelles_methodes_et_cibles(self):
        inv = inv_mod.load()
        methods = {e["id"]: e["rotation"]["method"] for e in inv["secrets"]}
        self.assertEqual(methods["stagingkub-rhdemo-db"], "postgres-password")
        self.assertEqual(methods["openbao-approle-jenkins"], "openbao-approle")
        kinds = {t["kind"] for e in inv["secrets"] for t in e.get("targets", [])}
        self.assertIn("openbao", kinds)
        self.assertNotIn("sops", kinds)                  # plus aucune cible SOPS

    def test_validation_cibles_incompletes(self):
        inv = inv_mod.load()
        inv["secrets"].append({"id": "x", "num": "99", "label": "", "criticality": "C", "exposure": "local",
                               "rotation": {"method": "postgres-password", "kv_path": "a"},
                               "targets": [{"kind": "openbao", "path": "p"}]})
        errors = "\n".join(inv_mod.validate(inv))
        self.assertIn("postgres-password exige", errors)
        self.assertIn("cible openbao incomplète", errors)


if __name__ == "__main__":
    unittest.main()
