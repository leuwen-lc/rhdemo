"""Tests de rotate-secrets.py : faux Codeberg, faux Jenkins et faux Infomaniak en local,
vrais gpg sur des clés jetables. Aucun accès réseau."""
import base64
import copy
import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import helpers  # noqa: F401  (ajoute scripts/ au chemin)

from rotation_lib import inventory as inv_mod
from rotation_lib import tools
from rotation_lib.common import Journal, RotationError
from rotation_lib.rotations import Context, rotate_forgejo_gpg, rotate_forgejo_token, rotate_manual_value

ADMIN = ("admin", "jenkins-pw")
BOT = ("bot-ci", "bot-pw")
OTP = "123456"
STRING_TAG = "org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl"
UP_TAG = "com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl"


def basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


class FakeState:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = []
        # Forgejo
        self.tokens = {}         # id -> {name, scopes, sha1, user}
        self.next_id = 100
        self.gpg_keys = {}       # id -> {key_id, public, signature}
        self.push = True
        # Jenkins
        self.creds = {}          # id -> xml
        self.fail_post = False
        self.charset = "utf-8"
        # Infomaniak
        self.accesses = {}       # id -> {label, password}


def make_handler(state):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, code, body=b"", ctype="application/json"):
            data = json.dumps(body).encode() if isinstance(body, (dict, list)) else (
                body.encode() if isinstance(body, str) else body)
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(n) if n else b""

        def handle_any(self, method):
            path = self.path
            raw = self.body()
            with state.lock:
                state.requests.append((method, path, dict(self.headers), raw))
                if path.startswith("/api/v1"):
                    return self.forgejo(method, path[7:], raw)
                if path.startswith("/1/mail_hostings"):
                    return self.infomaniak(method, path, raw)
                return self.jenkins(method, path, raw)

        do_GET = lambda self: self.handle_any("GET")        # noqa: E731
        do_POST = lambda self: self.handle_any("POST")      # noqa: E731
        do_DELETE = lambda self: self.handle_any("DELETE")  # noqa: E731

        # --- Forgejo ---
        def basic_ok(self):
            return (self.headers.get("Authorization") == basic(*BOT)
                    and self.headers.get("X-Forgejo-OTP") == OTP)

        def token_user(self):
            auth = self.headers.get("Authorization") or ""
            for t in state.tokens.values():
                if auth == f"token {t['sha1']}":
                    return t["user"]
            return None

        def forgejo(self, method, path, raw):
            p = path.split("?")[0]
            m = re.match(r"^/users/([^/]+)/tokens(?:/(\d+))?$", p)
            if m:
                if not self.basic_ok() or m.group(1) != BOT[0]:
                    pw = base64.b64decode(self.headers.get("Authorization", "Basic ")[6:]).decode().split(":", 1)[-1]
                    return self.reply(401, {"message": f"access token does not exist [sha: {pw}]\n"
                                                       "user's password is invalid"})
                if method == "GET":
                    return self.reply(200, [{"id": i, "name": t["name"], "scopes": t["scopes"]}
                                            for i, t in state.tokens.items()])
                if method == "POST":
                    req = json.loads(raw)
                    state.next_id += 1
                    sha = f"tok{state.next_id:037d}"
                    state.tokens[state.next_id] = {"name": req["name"], "scopes": req["scopes"],
                                                   "sha1": sha, "user": BOT[0]}
                    return self.reply(201, {"id": state.next_id, "name": req["name"], "sha1": sha})
                if method == "DELETE":
                    state.tokens.pop(int(m.group(2)), None)
                    return self.reply(204)
            if p == "/user" and self.headers.get("Authorization", "").startswith("token "):
                user = self.token_user()
                if not user:
                    return self.reply(401, {})
                tok = next(t for t in state.tokens.values() if self.headers["Authorization"] == f"token {t['sha1']}")
                if not any(s.endswith(":user") for s in tok["scopes"]):     # comme Codeberg
                    return self.reply(403, {"message": "token does not have at least one of required scope(s)"})
                return self.reply(200, {"login": user})
            if p == "/repos/owner/repo":
                return self.reply(200, {"permissions": {"push": state.push}}) if self.token_user() else self.reply(404, {})
            # endpoints authentifiés par mot de passe (clés GPG)
            if not self.basic_ok():
                return self.reply(401, {"message": "unauthorized"})
            if p == "/user":
                return self.reply(200, {"login": BOT[0], "email": "bot@example.org"})
            if p == "/user/gpg_key_token":
                return self.reply(200, "verif-token-abc", "text/plain")
            if p == "/user/gpg_keys" and method == "GET":
                return self.reply(200, [{"id": i, "key_id": k["key_id"]} for i, k in state.gpg_keys.items()])
            if p == "/user/gpg_keys" and method == "POST":
                req = json.loads(raw)
                state.next_id += 1
                state.gpg_keys[state.next_id] = {"key_id": f"NEW{state.next_id}",
                                                 "public": req["armored_public_key"],
                                                 "signature": req.get("armored_signature")}
                return self.reply(201, {"id": state.next_id, "key_id": f"NEW{state.next_id}"})
            m = re.match(r"^/user/gpg_keys/(\d+)$", p)
            if m and method == "DELETE":
                state.gpg_keys.pop(int(m.group(1)), None)
                return self.reply(204)
            return self.reply(404, {})

        # --- Jenkins ---
        def jenkins(self, method, path, raw):
            if self.headers.get("Authorization") != basic(*ADMIN):
                return self.reply(401, "")
            if path == "/whoAmI/api/json":
                return self.reply(200, {"authenticated": True, "anonymous": False, "name": "admin"})
            if path == "/crumbIssuer/api/json":
                return self.send_crumb()
            m = re.match(r"^/credentials/store/system/domain/_/credential/([^/]+)/config.xml$", path)
            if not m or m.group(1) not in state.creds:
                return self.reply(404, "")
            if method == "GET":
                # Jenkins réel : déclaration UTF-8 mais corps parfois en Latin-1 (accents)
                return self.reply(200, ("<?xml version='1.1' encoding='UTF-8'?>\n" + state.creds[m.group(1)])
                                  .encode(state.charset), "application/xml")
            if self.headers.get("Jenkins-Crumb") != "crumb-1" or "JSESSIONID=s1" not in (self.headers.get("Cookie") or ""):
                return self.reply(403, "No valid crumb")
            if state.fail_post:
                return self.reply(500, "boom")
            if not raw.startswith(b"<?xml version='1.1' encoding='UTF-8'?>"):
                return self.reply(400, "déclaration XML attendue")
            state.creds[m.group(1)] = re.sub(r"^<\?xml[^>]*\?>\s*", "", raw.decode("utf-8"))
            return self.reply(200, "")

        def send_crumb(self):
            data = json.dumps({"crumbRequestField": "Jenkins-Crumb", "crumb": "crumb-1"}).encode()
            self.send_response(200)
            self.send_header("Set-Cookie", "JSESSIONID=s1; Path=/")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        # --- Infomaniak ---
        def infomaniak(self, method, path, raw):
            if self.headers.get("Authorization") != "Bearer ik-token":
                return self.reply(401, {"result": "error"})
            p = path.split("?")[0]
            m = re.match(r"^/1/mail_hostings/42/mailboxes/notif/accesses/devices(?:/(\d+))?$", p)
            if not m:
                return self.reply(404, {"result": "error"})
            if method == "GET":
                return self.reply(200, {"result": "success", "data": [
                    {"id": i, "device": {"label": a["label"]}} for i, a in state.accesses.items()]})
            if method == "POST" and not m.group(1):
                req = json.loads(raw)
                state.next_id += 1
                state.accesses[state.next_id] = {"label": req["label"], "password": req["password"]}
                return self.reply(200, {"result": "success", "data": {"password": req["password"]}})
            if method == "DELETE":
                state.accesses.pop(int(m.group(1)), None)
                return self.reply(200, {"result": "success", "data": True})
            return self.reply(404, {"result": "error"})
    return H


class StubPrompter:
    def __init__(self, secrets, confirm=False):
        self.secrets = secrets
        self.answer = confirm
        self.asked = []

    def secret(self, key, label):
        return self.secrets[key]

    def otp(self, user, fresh=False):
        self.otp_calls = getattr(self, "otp_calls", 0) + 1
        return OTP

    def drop(self, key):
        self.dropped = key

    def text(self, label):
        return self.secrets["text"]

    def confirm(self, question):
        self.asked.append(question)
        return self.answer

    def forget(self):
        pass


def string_cred(cid, secret="old"):
    return (f"<{STRING_TAG} plugin=\"plain-credentials\"><scope>GLOBAL</scope><id>{cid}</id>"
            f"<description>desc {cid}</description><secret>{secret}</secret></{STRING_TAG}>")


def up_cred(cid, user, pw="old"):
    return (f"<{UP_TAG}><scope>GLOBAL</scope><id>{cid}</id><description>smtp</description>"
            f"<username>{user}</username><password>{pw}</password></{UP_TAG}>")


def field(xml, name):
    return ET.fromstring(xml).find(name).text


class Base(unittest.TestCase):
    def setUp(self):
        self.state = FakeState()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.state))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.inv = {"periods": {"C": 90, "H": 180, "M": 365},
                    "services": {"jenkins": {"url": self.url, "admin_user": "admin"},
                                 "forgejo": {"url": self.url, "repo": "owner/repo"},
                                 "smtp": {"host": "smtp.test", "port": 465}},
                    "secrets": []}
        os.environ.pop("JENKINS_ADMIN_USER", None)

    def ctx(self, confirm=False, dry_run=False):
        prompter = StubPrompter({"jenkins": ADMIN[1], f"codeberg:{BOT[0]}": BOT[1],
                                 "infomaniak": "ik-token", "text": "42"}, confirm)
        self.journal = Journal(os.path.join(self.tmp, "journal.jsonl"))
        return Context(self.inv, prompter, self.journal, dry_run=dry_run)


class TokenRotationTest(Base):
    def entry(self):
        return {"id": "ci", "num": "3", "label": "x", "criticality": "C", "exposure": "internet",
                "rotation": {"method": "forgejo-token", "account": BOT[0], "token_prefix": "rhdemo-ci",
                             "scopes": ["write:issue", "write:repository"]},
                "targets": [{"kind": "jenkins", "credential": "ci-token", "type": "string"}]}

    def seed(self):
        self.state.creds["ci-token"] = string_cred("ci-token")
        self.state.tokens[1] = {"name": "rhdemo-ci-20260101-000000", "scopes": ["write:issue", "write:repository"],
                                "sha1": "old-managed", "user": BOT[0]}
        self.state.tokens[2] = {"name": "hand-made", "scopes": ["write:issue", "write:repository"],
                                "sha1": "old-hand", "user": BOT[0]}

    def test_rotation_complete(self):
        self.seed()
        detail = rotate_forgejo_token(self.ctx(confirm=False), self.entry())
        names = {t["name"] for t in self.state.tokens.values()}
        self.assertNotIn("rhdemo-ci-20260101-000000", names)       # géré : révoqué
        self.assertIn("hand-made", names)                          # non géré, refusé : conservé
        new = [t for t in self.state.tokens.values() if t["name"].startswith("rhdemo-ci-2") and t["sha1"] != "old-managed"]
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["scopes"], ["write:issue", "write:repository"])
        xml = self.state.creds["ci-token"]
        self.assertEqual(field(xml, "secret"), new[0]["sha1"])
        self.assertEqual(field(xml, "description"), "desc ci-token")   # reste du credential conservé
        self.assertIn("révoqués", detail)
        self.assertNotIn(new[0]["sha1"], detail)

    def test_xml_jenkins_en_latin1_accents_preserves(self):
        self.seed()
        self.state.charset = "iso-8859-1"
        self.state.creds["ci-token"] = string_cred("ci-token").replace("desc ci-token", "clé privée")
        rotate_forgejo_token(self.ctx(), self.entry())
        self.assertEqual(field(self.state.creds["ci-token"], "description"), "clé privée")
        self.assertNotEqual(field(self.state.creds["ci-token"], "secret"), "old")

    def test_mot_de_passe_refuse_jamais_recopie(self):
        self.seed()
        ctx = self.ctx()
        leaked = "0123456789abcdef0123456789abcdef01234567"  # valeur fictive
        ctx.prompter.secrets[f"codeberg:{BOT[0]}"] = leaked     # valeur fausse, recopiée par Forgejo
        with self.assertRaises(RotationError) as cm:
            rotate_forgejo_token(ctx, self.entry())
        self.assertNotIn(leaked, str(cm.exception))
        self.assertIn("mot de passe incorrect", str(cm.exception))
        self.assertEqual(ctx.prompter.otp_calls, 1)               # TOTP pas redemandé
        self.assertEqual(ctx.prompter.dropped, f"codeberg:{BOT[0]}")

    def test_token_avec_portee_user_identite_verifiee(self):
        self.seed()
        entry = self.entry()
        entry["rotation"]["scopes"] = ["write:issue", "write:repository", "write:user"]
        for t in self.state.tokens.values():
            t["scopes"] = list(entry["rotation"]["scopes"])
        rotate_forgejo_token(self.ctx(), entry)
        self.assertTrue(any(r[1] == "/api/v1/user" for r in self.state.requests))

    def test_revocation_token_non_gere_confirmee(self):
        self.seed()
        rotate_forgejo_token(self.ctx(confirm=True), self.entry())
        self.assertEqual({t["name"] for t in self.state.tokens.values()} & {"hand-made", "rhdemo-ci-20260101-000000"}, set())

    def test_echec_propagation_supprime_le_nouveau_token(self):
        self.seed()
        self.state.fail_post = True
        with self.assertRaises(RotationError):
            rotate_forgejo_token(self.ctx(), self.entry())
        self.assertEqual(set(self.state.tokens), {1, 2})            # rien de créé, rien de révoqué
        self.assertEqual(field(self.state.creds["ci-token"], "secret"), "old")

    def test_token_sans_droit_ecriture_supprime(self):
        self.seed()
        self.state.push = False
        with self.assertRaisesRegex(RotationError, "écriture"):
            rotate_forgejo_token(self.ctx(), self.entry())
        self.assertEqual(set(self.state.tokens), {1, 2})

    def test_cible_absente_aucune_creation(self):
        self.seed()
        del self.state.creds["ci-token"]
        with self.assertRaisesRegex(RotationError, "introuvable"):
            rotate_forgejo_token(self.ctx(), self.entry())
        self.assertFalse([r for r in self.state.requests if r[0] == "POST"])

    def test_portees_divergentes_abandon(self):
        self.seed()
        self.state.tokens[1]["scopes"] = ["write:repository"]
        with self.assertRaisesRegex(RotationError, "portées"):
            rotate_forgejo_token(self.ctx(confirm=False), self.entry())
        self.assertEqual(set(self.state.tokens), {1, 2})

    def test_dry_run(self):
        self.seed()
        self.assertIsNone(rotate_forgejo_token(self.ctx(dry_run=True), self.entry()))
        self.assertEqual(set(self.state.tokens), {1, 2})
        self.assertFalse([r for r in self.state.requests if r[0] in ("POST", "DELETE")])


class ManualSmtpTest(Base):
    def entry(self):
        return {"id": "smtp", "num": "12", "label": "x", "criticality": "H", "exposure": "internet",
                "rotation": {"method": "manual-value", "verify": "smtp", "smtp_credential": "smtp-cred",
                             "procedure": "créer", "revoke": "supprimer l'ancien"},
                "targets": [{"kind": "jenkins", "credential": "smtp-cred", "type": "username-password"}]}

    def setUp(self):
        super().setUp()
        self.state.creds["smtp-cred"] = up_cred("smtp-cred", "notif@example.org")
        self.smtp_calls = []

    def ctx_with(self, value):
        ctx = self.ctx()
        ctx.prompter.secrets["value:smtp"] = value
        return ctx

    def test_valeur_testee_puis_propagee(self):
        ctx = self.ctx_with("nouveau-mot-de-passe-app")
        ctx.smtp_check = lambda h, p, u, pw: self.smtp_calls.append((h, p, u, pw))
        rotate_manual_value(ctx, self.entry())
        self.assertEqual(self.smtp_calls, [("smtp.test", 465, "notif@example.org", "nouveau-mot-de-passe-app")])
        xml = self.state.creds["smtp-cred"]
        self.assertEqual(field(xml, "password"), "nouveau-mot-de-passe-app")
        self.assertEqual(field(xml, "username"), "notif@example.org")

    def test_echec_smtp_jenkins_inchange(self):
        ctx = self.ctx_with("mauvais")

        def refuse(*a):
            raise RotationError("SMTP refusé")
        ctx.smtp_check = refuse
        with self.assertRaises(RotationError):
            rotate_manual_value(ctx, self.entry())
        self.assertEqual(field(self.state.creds["smtp-cred"], "password"), "old")
        self.assertFalse([r for r in self.state.requests if r[0] == "POST"])

    def test_dry_run_ne_demande_pas_la_valeur(self):
        ctx = self.ctx(dry_run=True)                      # aucune valeur fournie : KeyError si demandée
        self.assertIsNone(rotate_manual_value(ctx, self.entry()))


@unittest.skipUnless(shutil.which("gpg") and shutil.which("gpgconf"), "gpg absent")
class GpgRotationTest(Base):
    def test_rotation_complete(self):
        self.state.creds["gpg-cred"] = string_cred("gpg-cred")
        self.state.gpg_keys[5] = {"key_id": "OLDKEY", "public": "", "signature": None}
        entry = {"id": "gpg", "num": "7", "label": "x", "criticality": "H", "exposure": "internet",
                 "rotation": {"method": "forgejo-gpg", "account": BOT[0], "uid_name": "Bot",
                              "algo": "ed25519", "expire": "1y"},
                 "targets": [{"kind": "jenkins", "credential": "gpg-cred", "type": "string"}]}
        rotate_forgejo_gpg(self.ctx(), entry)
        self.assertNotIn(5, self.state.gpg_keys)
        (key,) = self.state.gpg_keys.values()
        self.assertIn("BEGIN PGP PUBLIC KEY BLOCK", key["public"])
        self.assertIn("BEGIN PGP SIGNATURE", key["signature"])
        private = base64.b64decode(field(self.state.creds["gpg-cred"], "secret")).decode()
        self.assertIn("BEGIN PGP PRIVATE KEY BLOCK", private)
        # la signature envoyée vérifie bien le jeton avec la clé publique envoyée
        with tools.gpg_home() as home:
            subprocess.run(["gpg", "--homedir", home, "--batch", "--import"], input=key["public"].encode(),
                           capture_output=True, check=True)
            sig = os.path.join(home, "s.asc")
            with open(sig, "w") as fh:
                fh.write(key["signature"])
            ok = subprocess.run(["gpg", "--homedir", home, "--batch", "--verify", sig, "-"],
                                input=b"verif-token-abc", capture_output=True)
            self.assertEqual(ok.returncode, 0, ok.stderr)


class InventoryTest(unittest.TestCase):
    def test_inventaire_du_depot_valide(self):
        inv = inv_mod.load()
        ids = [e["id"] for e in inv["secrets"]]
        self.assertEqual(len(ids), len(set(ids)))
        nums = {e["num"] for e in inv["secrets"]}
        # #1 (clé AGE de SOPS, abandonnée) et #19 (token API Infomaniak) retirés
        for n in [str(i) for i in range(2, 19)] + ["6b"]:
            self.assertIn(n, nums, f"secret #{n} de l'étude absent de l'inventaire")
        self.assertNotIn("1", nums)

    def test_validation_detecte_les_erreurs(self):
        inv = inv_mod.load()
        bad = copy.deepcopy(inv)
        bad["secrets"][0]["rotation"].pop("scopes")
        bad["secrets"][1]["exposure"] = "cloud"
        bad["secrets"].append(copy.deepcopy(bad["secrets"][2]))
        errors = "\n".join(inv_mod.validate(bad))
        self.assertIn("exige scopes", errors)
        self.assertIn("exposition cloud", errors)
        self.assertIn("en double", errors)

    def test_per_build_sans_cible(self):
        inv = inv_mod.load()
        self.assertEqual(inv_mod.by_id(inv, "ephemere-secrets")["rotation"]["method"], "per-build")
        bad = copy.deepcopy(inv)
        e = inv_mod.by_id(bad, "ephemere-secrets")
        e["targets"] = [{"kind": "openbao", "path": "x", "key": "y"}]
        e["rotation"].pop("note")
        errors = "\n".join(inv_mod.validate(bad))
        self.assertIn("per-build n'admet aucune cible", errors)
        self.assertIn("per-build exige note", errors)

    def test_ordre_urgence(self):
        inv = inv_mod.load()
        expo = [e["exposure"] for e in inv_mod.ordered(inv["secrets"])]
        self.assertEqual(expo, sorted(expo, key=inv_mod.EXPOSURE_ORDER.get))


def _load_cli():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rotate_secrets", os.path.join(helpers.SCRIPTS, "rotate-secrets.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CheckTest(unittest.TestCase):
    def test_retard_et_journal_sans_valeur(self):
        mod = _load_cli()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        journal = Journal(os.path.join(tmp, "j.jsonl"))
        inv = {"periods": {"C": 90, "H": 180, "M": 365}, "secrets": [
            {"id": "a", "num": "1", "label": "", "criticality": "C", "exposure": "internet", "rotation": {"method": "manual"}},
            {"id": "b", "num": "2", "label": "", "criticality": "M", "exposure": "local", "rotation": {"method": "manual"}}]}
        journal.append("a", "rotated", "token x")
        journal.append("b", "failed", "erreur")
        later = datetime.datetime.now().astimezone() + datetime.timedelta(days=100)
        self.assertEqual(mod.cmd_check(inv, journal, today=later), 1)          # a en retard, b jamais
        soon = datetime.datetime.now().astimezone() + datetime.timedelta(days=10)
        journal.append("b", "recorded", "")
        self.assertEqual(mod.cmd_check(inv, journal, today=soon), 0)
        self.assertEqual(os.stat(journal.path).st_mode & 0o777, 0o600)

    def test_bloquant_signale_et_en_retard_avant_expiration(self):
        mod = _load_cli()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        journal = Journal(os.path.join(tmp, "j.jsonl"))
        inv = {"periods": {"C": 90, "H": 180, "M": 365}, "secrets": [
            {"id": "s", "num": "14", "label": "", "criticality": "M", "exposure": "local",
             "blocking": True, "lifetime_days": 100, "rotation": {"method": "manual"}},
            {"id": "h", "num": "1", "label": "", "criticality": "M", "exposure": "local",
             "rotation": {"method": "manual"}}]}
        journal.append("s", "recorded", "")
        journal.append("h", "recorded", "")
        now = datetime.datetime.now().astimezone()

        def run(days):
            with mock.patch.object(mod, "log") as log:
                rc = mod.cmd_check(inv, journal, today=now + datetime.timedelta(days=days))
            lines = [c.args[0] for c in log.call_args_list]
            return rc, next(line for line in lines if " s " in line), lines[-1]

        rc, line, total = run(10)                       # limite : 100 - 14 = 86 j
        self.assertEqual(rc, 0)
        self.assertTrue(line.endswith("ok, 76 j restants (bloquant)"), line)
        rc, line, total = run(90)                       # dans la marge, avant l'expiration
        self.assertEqual(rc, 1)
        self.assertIn("EN RETARD (expire dans 10 j) (bloquant)", line)
        self.assertIn("1 secret(s) en retard", total)
        self.assertIn("dont 1 bloquant(s)", total)
        rc, line, _ = run(120)
        self.assertIn("EXPIRÉ (120 j > 100 j) (bloquant)", line)

    def test_chaque_methode_a_une_sorte(self):
        self.assertEqual(set(inv_mod.METHOD_KINDS), set(inv_mod.METHOD_KEYS))
        self.assertEqual(inv_mod.METHOD_KINDS["manual-value"], "semi-manuelle")

    def test_list_affiche_sorte_methode_et_bloquant(self):
        mod = _load_cli()
        inv = {"secrets": [
            {"id": "s", "num": "14", "label": "", "criticality": "M", "exposure": "local",
             "blocking": True, "rotation": {"method": "manual-value"}},
            {"id": "p", "num": "9", "label": "", "criticality": "H", "exposure": "local",
             "rotation": {"method": "planned", "phase": 4}}]}
        with mock.patch.object(mod, "log") as log:
            mod.cmd_list(inv)
        lines = [c.args[0] for c in log.call_args_list]
        self.assertTrue(lines[0].endswith("rotation"))
        self.assertTrue(any(line.endswith("semi-manuelle (manual-value), bloquant") for line in lines), lines)
        self.assertTrue(any(line.endswith("prévue (planned, phase 4)") for line in lines), lines)

    def test_inventaire_bloquant_valide(self):
        base = {"periods": {}, "services": {}, "secrets": []}

        def errors(**extra):
            e = {"id": "x", "num": "1", "label": "", "criticality": "M", "exposure": "local",
                 "rotation": {"method": "manual", "procedure": "p"}, **extra}
            return inv_mod.validate({**base, "secrets": [e]})

        self.assertEqual(errors(blocking=True, lifetime_days=100), [])
        self.assertEqual(errors(blocking=True), [])
        self.assertTrue(errors(lifetime_days=100))                 # sans blocking: true
        self.assertTrue(errors(blocking=True, lifetime_days=10))   # pas plus long que la marge
        self.assertTrue(errors(blocking="oui"))

    def test_per_build_jamais_en_retard_ni_tracable(self):
        mod = _load_cli()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        journal = Journal(os.path.join(tmp, "j.jsonl"))
        inv = {"periods": {"C": 90, "H": 180, "M": 365}, "secrets": [
            {"id": "e", "num": "16", "label": "", "criticality": "M", "exposure": "local",
             "rotation": {"method": "per-build", "note": "jetable"}}]}
        self.assertEqual(mod.cmd_check(inv, journal), 0)
        self.assertEqual(mod.cmd_rotate(None, inv["secrets"]), 0)
        with mock.patch.object(mod, "Journal", lambda: journal):
            self.assertEqual(mod.main(["--record", "ephemere-secrets"]), 2)
        self.assertFalse(os.path.exists(journal.path))


if __name__ == "__main__":
    unittest.main()
