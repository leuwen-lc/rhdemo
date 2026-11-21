"""Tests des rotations Keycloak de stagingkub (rotation_lib/keycloak.py, méthodes
keycloak-client-secret, keycloak-admin, keycloak-users) : faux Keycloak et faux OpenBao HTTP
locaux, kubectl et port-forward simulés. Aucun accès réseau, aucun cluster."""
import base64
import json
import threading
import unittest
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import helpers  # noqa: F401  (ajoute scripts/ au chemin)
from test_openbao import Base

from rotation_lib import rotations, tools
from rotation_lib.common import RotationError


class FakeKc:
    def __init__(self):
        self.lock = threading.Lock()
        self.users = {"master": {"admin": "kc-old"},
                      "RHDemo": {"rhdemo-admin": "u1", "rhdemo-maj": "u2", "rhdemo-consult": "u3"}}
        self.clients = {"RHDemo": {"cid-1": {"id": "cid-1", "clientId": "RHDemo", "secret": "oidc-old"}}}
        self.tokens = set()
        self.fail_reset = set()     # utilisateurs dont le reset-password échoue
        self.reject_login = set()   # utilisateurs dont la connexion de vérification échoue
        self.required_action = set()


def make_kc_handler(st):
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
            raw = self.rfile.read(n) if n else b""
            url = urllib.parse.urlsplit(self.path)
            q = dict(urllib.parse.parse_qsl(url.query))
            parts = url.path.strip("/").split("/")
            with st.lock:
                if parts[0] == "realms" and parts[-1] == "token":
                    realm = parts[1]
                    form = dict(urllib.parse.parse_qsl(raw.decode()))
                    user = form["username"]
                    if st.users.get(realm, {}).get(user) != form["password"] or user in st.reject_login:
                        return self.reply(401, {"error": "invalid_grant"})
                    if user in st.required_action:
                        return self.reply(400, {"error": "invalid_grant",
                                                "error_description": "Account is not fully set up"})
                    tok = uuid.uuid4().hex
                    if realm == "master":
                        st.tokens.add(tok)
                    return self.reply(200, {"access_token": tok, "expires_in": 60})
                if self.headers.get("Authorization", "")[7:] not in st.tokens:
                    return self.reply(401, {})
                body = json.loads(raw) if raw else None
                realm = parts[2]
                if parts[3] == "users" and len(parts) == 4:
                    name = q["username"]
                    return self.reply(200, [{"id": f"id-{name}", "username": name}]
                                      if name in st.users[realm] else [])
                if parts[3] == "users" and parts[5] == "reset-password":
                    name = parts[4][3:]
                    if name in st.fail_reset:
                        return self.reply(500, {})
                    st.users[realm][name] = body["value"]
                    return self.reply(204)
                if parts[3] == "clients" and len(parts) == 4:
                    return self.reply(200, [dict(c) for c in st.clients[realm].values()
                                            if c["clientId"] == q["clientId"]])
                if parts[3] == "clients" and len(parts) == 5 and method == "PUT":
                    st.clients[realm][parts[4]] = body
                    return self.reply(204)
                if parts[3] == "clients" and parts[-1] == "client-secret":
                    return self.reply(200, {"type": "secret", "value": st.clients[realm][parts[4]]["secret"]})
                return self.reply(404, {})

        do_GET = lambda self: self.handle_any("GET")      # noqa: E731
        do_POST = lambda self: self.handle_any("POST")    # noqa: E731
        do_PUT = lambda self: self.handle_any("PUT")      # noqa: E731
    return H


class EsoKubectl:
    """kubectl simulé : force-sync recopie le KV dans le Secret (gabarit pour rhdemo-app-secrets)."""

    def __init__(self, bao, fail_rollout=False):
        self.bao = bao
        self.calls = []
        self.secrets = {}
        self.fail_rollout = fail_rollout

    def __call__(self, *args, stdin=None, timeout=300):
        self.calls.append(args)
        if args[0] == "annotate":
            es = args[2]
            if es == "rhdemo-app-secrets":
                kv = self.bao.kv["stagingkub/rhdemo"][-1]
                self.secrets[es] = f'secret: "{kv["oidc_client_secret"]}"\npg: "{kv["db_password"]}"\n'
            elif es == "keycloak-admin-secret":
                self.secrets[es] = self.bao.kv["stagingkub/keycloak"][-1]["admin_password"]
            return ""
        if args[:2] == ("get", "secret"):
            return base64.b64encode(self.secrets.get(args[2], "").encode()).decode()
        if args[0] == "rollout" and self.fail_rollout:
            raise RotationError("kubectl rollout restart : échec")
        return ""


class KcBase(Base):
    def setUp(self):
        super().setUp()
        self.kc = FakeKc()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_kc_handler(self.kc))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        kc_url = f"http://127.0.0.1:{srv.server_address[1]}"
        self.forwards = []
        test = self

        class StubForward:
            def __init__(self, ns, target, port):
                self.url, self.closed = kc_url, False
                test.forwards.append(self)

            def close(self):
                self.closed = True

        self._patch(tools, "PortForward", StubForward)
        self.inv["services"]["keycloak"] = {"namespace": "rhdemo-stagingkub", "target": "deployment/keycloak",
                                            "admin_kv_path": "stagingkub/keycloak"}
        ob = self.admin()
        ob.kv_put("stagingkub/keycloak", {"admin_user": "admin", "admin_password": "kc-old", "db_password": "d"})
        ob.kv_put("stagingkub/rhdemo", {"db_password": "pg", "oidc_client_secret": "oidc-old"})
        ob.kv_put("stagingkub-tests/users", {"iduseradmin": "rhdemo-admin", "pwduseradmin": "u1",
                                             "idusermaj": "rhdemo-maj", "pwdusermaj": "u2",
                                             "iduserconsult": "rhdemo-consult", "pwduserconsult": "u3"})
        self.kubectl = EsoKubectl(self.st)
        self._patch(tools, "kubectl", self.kubectl)

    def _patch(self, obj, name, value):
        old = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, old)

    def kv(self, path):
        return self.st.kv[path][-1]

    def run_entry(self, fn, entry, dry_run=False):
        ctx = self.ctx(dry_run=dry_run)
        try:
            return fn(ctx, entry)
        finally:
            ctx.close()


CLIENT = {"id": "stagingkub-oidc-client", "rotation": {
    "method": "keycloak-client-secret", "kv_path": "stagingkub/rhdemo", "kv_key": "oidc_client_secret",
    "realm": "RHDemo", "client_id": "RHDemo", "namespace": "rhdemo-stagingkub",
    "external_secrets": ["rhdemo-app-secrets"], "k8s_secret": "rhdemo-app-secrets",
    "k8s_key": "secrets-rhdemo.yml", "k8s_match": "contains", "restart": ["deployment/rhdemo-app"]}}

ADMIN = {"id": "stagingkub-keycloak-admin", "rotation": {
    "method": "keycloak-admin", "kv_path": "stagingkub/keycloak", "kv_key": "admin_password",
    "user_key": "admin_user", "realm": "master", "namespace": "rhdemo-stagingkub",
    "external_secrets": ["keycloak-admin-secret"], "k8s_secret": "keycloak-admin-secret"}}

USERS = {"id": "stagingkub-test-users", "rotation": {
    "method": "keycloak-users", "kv_path": "stagingkub-tests/users", "realm": "RHDemo",
    "users": [{"user_key": "iduseradmin", "password_key": "pwduseradmin"},
              {"user_key": "idusermaj", "password_key": "pwdusermaj"},
              {"user_key": "iduserconsult", "password_key": "pwduserconsult"}]}}


class ClientSecretTest(KcBase):
    def test_rotation_complete(self):
        detail = self.run_entry(rotations.rotate_keycloak_client_secret, CLIENT)
        new = self.kv("stagingkub/rhdemo")["oidc_client_secret"]
        self.assertNotEqual(new, "oidc-old")
        self.assertEqual(self.kv("stagingkub/rhdemo")["db_password"], "pg")
        self.assertEqual(self.kc.clients["RHDemo"]["cid-1"]["secret"], new)
        self.assertIn(new, self.kubectl.secrets["rhdemo-app-secrets"])
        verbs = [c[0] for c in self.kubectl.calls]
        self.assertLess(verbs.index("annotate"), verbs.index("rollout"))
        for args in self.kubectl.calls:
            self.assertNotIn(new, " ".join(args))
        self.assertNotIn(new, detail)
        self.assertTrue(all(f.closed for f in self.forwards))         # port-forward arrêté

    def test_echec_keycloak_retour_arriere(self):
        orig = rotations.Keycloak.set_client_secret
        calls = []

        def failing(kc, realm, cid, secret):
            calls.append(secret)
            if len(calls) == 1:
                raise RotationError("Keycloak : PUT refusé (500)")
            return orig(kc, realm, cid, secret)

        self._patch(rotations.Keycloak, "set_client_secret", failing)
        with self.assertRaises(RotationError):
            self.run_entry(rotations.rotate_keycloak_client_secret, CLIENT)
        self.assertEqual(self.kv("stagingkub/rhdemo")["oidc_client_secret"], "oidc-old")
        self.assertEqual(self.kc.clients["RHDemo"]["cid-1"]["secret"], "oidc-old")
        self.assertIn("oidc-old", self.kubectl.secrets["rhdemo-app-secrets"])
        self.assertFalse([c for c in self.kubectl.calls if c[0] == "rollout"])

    def test_dry_run(self):
        self.assertIsNone(self.run_entry(rotations.rotate_keycloak_client_secret, CLIENT, dry_run=True))
        self.assertEqual(len(self.st.kv["stagingkub/rhdemo"]), 1)
        self.assertEqual(self.kc.clients["RHDemo"]["cid-1"]["secret"], "oidc-old")


class AdminTest(KcBase):
    def test_rotation_complete(self):
        self.run_entry(rotations.rotate_keycloak_admin, ADMIN)
        new = self.kv("stagingkub/keycloak")["admin_password"]
        self.assertNotEqual(new, "kc-old")
        self.assertEqual(self.kc.users["master"]["admin"], new)
        self.assertEqual(self.kv("stagingkub/keycloak")["db_password"], "d")
        self.assertEqual(self.kubectl.secrets["keycloak-admin-secret"], new)

    def test_verification_refusee_retour_arriere(self):
        self.kc.reject_login.add("admin")
        with self.assertRaises(RotationError):
            # la connexion initiale échoue aussi : rien ne doit changer
            self.run_entry(rotations.rotate_keycloak_admin, ADMIN)
        self.assertEqual(self.kv("stagingkub/keycloak")["admin_password"], "kc-old")
        self.assertEqual(self.kc.users["master"]["admin"], "kc-old")

    def test_connexion_apres_reset_refusee_retour_arriere(self):
        def refuse(kc, realm, user, password):
            raise RotationError("Keycloak : connexion refusée (401)")
        self._patch(rotations.Keycloak, "check_login", refuse)
        with self.assertRaises(RotationError):
            self.run_entry(rotations.rotate_keycloak_admin, ADMIN)
        self.assertEqual(self.kv("stagingkub/keycloak")["admin_password"], "kc-old")
        self.assertEqual(self.kc.users["master"]["admin"], "kc-old")

    def test_reset_refuse_kv_restaure(self):
        self.kc.fail_reset.add("admin")
        with self.assertRaises(RotationError):
            self.run_entry(rotations.rotate_keycloak_admin, ADMIN)
        self.assertEqual(self.kv("stagingkub/keycloak")["admin_password"], "kc-old")
        self.assertEqual(self.kc.users["master"]["admin"], "kc-old")


class UsersTest(KcBase):
    def test_rotation_complete(self):
        self.kc.required_action.add("rhdemo-consult")        # accepté avec avertissement
        detail = self.run_entry(rotations.rotate_keycloak_users, USERS)
        data = self.kv("stagingkub-tests/users")
        for name, key, old in (("rhdemo-admin", "pwduseradmin", "u1"), ("rhdemo-maj", "pwdusermaj", "u2"),
                               ("rhdemo-consult", "pwduserconsult", "u3")):
            self.assertNotEqual(data[key], old)
            self.assertEqual(self.kc.users["RHDemo"][name], data[key])
        self.assertIn("rhdemo-consult", detail)
        for key in ("pwduseradmin", "pwdusermaj", "pwduserconsult"):
            self.assertEqual(len(data[key]), 12)

    def test_longueur_configurable(self):
        entry = {**USERS, "rotation": {**USERS["rotation"], "password": {"length": 16}}}
        self.run_entry(rotations.rotate_keycloak_users, entry)
        self.assertEqual(len(self.kv("stagingkub-tests/users")["pwduseradmin"]), 16)

    def test_longueur_trop_courte_rien_change(self):
        entry = {**USERS, "rotation": {**USERS["rotation"], "password": {"length": 6}}}
        with self.assertRaisesRegex(RotationError, "inférieure à 8"):
            self.run_entry(rotations.rotate_keycloak_users, entry)
        self.assertEqual(len(self.st.kv["stagingkub-tests/users"]), 1)

    def test_echec_au_milieu(self):
        self.kc.fail_reset.add("rhdemo-maj")
        with self.assertRaisesRegex(RotationError, "déjà renouvelés : rhdemo-admin"):
            self.run_entry(rotations.rotate_keycloak_users, USERS)
        data = self.kv("stagingkub-tests/users")
        self.assertEqual(self.kc.users["RHDemo"]["rhdemo-admin"], data["pwduseradmin"])
        self.assertNotEqual(data["pwduseradmin"], "u1")
        self.assertEqual(data["pwdusermaj"], "u2")
        self.assertEqual(self.kc.users["RHDemo"]["rhdemo-maj"], "u2")
        self.assertEqual(data["pwduserconsult"], "u3")

    def test_utilisateur_absent_rien_change(self):
        del self.kc.users["RHDemo"]["rhdemo-consult"]
        with self.assertRaisesRegex(RotationError, "absent"):
            self.run_entry(rotations.rotate_keycloak_users, USERS)
        self.assertEqual(len(self.st.kv["stagingkub-tests/users"]), 1)


class SimplePasswordTest(unittest.TestCase):
    def test_classes_et_alphabet(self):
        import string
        from rotation_lib.common import SIMPLE_PUNCTUATION, simple_password
        allowed = set(string.ascii_letters + string.digits + SIMPLE_PUNCTUATION)
        for _ in range(500):
            pw = simple_password()
            self.assertEqual(len(pw), 12)
            self.assertTrue(pw[0].isalpha())
            self.assertTrue(set(pw) <= allowed)
            self.assertTrue(any(c.isupper() for c in pw) and any(c.islower() for c in pw))
            self.assertTrue(any(c.isdigit() for c in pw) and any(c in SIMPLE_PUNCTUATION for c in pw))


class InventoryKeycloakTest(unittest.TestCase):
    def test_entrees(self):
        from rotation_lib import inventory as inv_mod
        inv = inv_mod.load()
        methods = {e["id"]: e["rotation"]["method"] for e in inv["secrets"]}
        self.assertEqual(methods["stagingkub-oidc-client"], "keycloak-client-secret")
        self.assertEqual(methods["stagingkub-keycloak-admin"], "keycloak-admin")
        self.assertEqual(methods["stagingkub-test-users"], "keycloak-users")
        self.assertNotIn("stagingkub-app-secrets", methods)
        self.assertIn("keycloak", inv["services"])


if __name__ == "__main__":
    unittest.main()
