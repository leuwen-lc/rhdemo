"""Tests de la rotation de l'admin Grafana (méthode grafana-admin) et de
openbao-setup.py observability : faux OpenBao et faux Grafana HTTP locaux, kubectl et
port-forward simulés. Aucun accès réseau, aucun cluster."""
import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import helpers  # noqa: F401  (ajoute scripts/ au chemin)
from test_openbao import Base, load_setup

from rotation_lib import rotations, tools
from rotation_lib.common import RotationError

ENTRY = {"id": "grafana-admin", "rotation": {
    "method": "grafana-admin", "kv_path": "observability/grafana", "kv_key": "admin_password",
    "user_key": "admin_user", "namespace": "loki-stack", "external_secrets": ["grafana-admin"],
    "k8s_secret": "grafana-admin", "k8s_key": "admin-password", "restart": ["deployment/grafana"],
    "service": "service/grafana"}}


class FakeGrafana:
    """Mot de passe admin courant : celui du Secret au dernier redémarrage."""

    def __init__(self):
        self.password = "g-old"
        self.reject = False


def make_grafana_handler(st):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            auth = self.headers.get("Authorization", "")
            ok = auth == "Basic " + base64.b64encode(f"admin:{st.password}".encode()).decode()
            code = 200 if ok and not st.reject and self.path == "/api/user" else 401
            body = json.dumps({"login": "admin"} if code == 200 else {}).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    return H


class GrafanaKubectl:
    """force-sync recopie le KV dans le Secret ; un redémarrage applique le Secret à Grafana."""

    def __init__(self, bao, grafana, fail_rollout=False):
        self.bao, self.grafana = bao, grafana
        self.secret = "g-old"
        self.calls = []
        self.fail_rollout = fail_rollout

    def __call__(self, *args, stdin=None, timeout=300):
        self.calls.append(args)
        if args[0] == "annotate":
            self.secret = self.bao.kv["observability/grafana"][-1]["admin_password"]
        elif args[:2] == ("get", "secret"):
            return base64.b64encode(self.secret.encode()).decode()
        elif args[:2] == ("rollout", "restart"):
            if self.fail_rollout:
                raise RotationError("kubectl rollout restart : échec")
            self.grafana.password = self.secret
        return ""


class GrafanaBase(Base):
    def setUp(self):
        super().setUp()
        self.gf = FakeGrafana()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_grafana_handler(self.gf))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        url = f"http://127.0.0.1:{srv.server_address[1]}"

        class StubForward:
            def __init__(self, ns, target, port):
                self.url = url

            def close(self):
                pass

        self._patch(tools, "PortForward", StubForward)
        self.admin().kv_put("observability/grafana", {"admin_user": "admin", "admin_password": "g-old"})

    def _patch(self, obj, name, value):
        old = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, old)

    def run_with(self, kubectl, dry_run=False):
        self._patch(tools, "kubectl", kubectl)
        ctx = self.ctx(dry_run=dry_run)
        try:
            return rotations.rotate_grafana_admin(ctx, ENTRY)
        finally:
            ctx.close()


class GrafanaRotationTest(GrafanaBase):
    def test_rotation_complete(self):
        k = GrafanaKubectl(self.st, self.gf)
        detail = self.run_with(k)
        new = self.st.kv["observability/grafana"][-1]["admin_password"]
        self.assertNotEqual(new, "g-old")
        self.assertEqual(self.gf.password, new)                 # Grafana redémarré avec
        verbs = [c[0] for c in k.calls]
        self.assertLess(verbs.index("annotate"), verbs.index("rollout"))
        for args in k.calls:
            self.assertNotIn(new, " ".join(args))
        self.assertNotIn(new, detail)

    def test_connexion_refusee_retour_arriere(self):
        self.gf.reject = True
        k = GrafanaKubectl(self.st, self.gf)
        with self.assertRaises(RotationError):
            self.run_with(k)
        self.assertEqual(self.st.kv["observability/grafana"][-1]["admin_password"], "g-old")
        self.assertEqual(self.gf.password, "g-old")              # redémarré avec l'ancien

    def test_redemarrage_en_echec_kv_restaure(self):
        k = GrafanaKubectl(self.st, self.gf, fail_rollout=True)
        with self.assertRaises(RotationError):
            self.run_with(k)
        self.assertEqual(self.st.kv["observability/grafana"][-1]["admin_password"], "g-old")
        self.assertEqual(k.secret, "g-old")

    def test_dry_run(self):
        k = GrafanaKubectl(self.st, self.gf)
        self.assertIsNone(self.run_with(k, dry_run=True))
        self.assertEqual(len(self.st.kv["observability/grafana"]), 1)


class SetupObservabilityTest(Base):
    def test_generation_puis_conservation(self):
        m = load_setup()
        m.cmd_observability(self.ctx())
        data = self.st.kv["observability/grafana"][-1]
        self.assertEqual(data["admin_user"], "admin")
        self.assertGreaterEqual(len(data["admin_password"]), 40)
        m.cmd_observability(self.ctx())                          # relance : rien d'écrasé
        self.assertEqual(len(self.st.kv["observability/grafana"]), 1)


class InventoryGrafanaTest(Base):
    def test_entree(self):
        from rotation_lib import inventory as inv_mod
        e = inv_mod.by_id(inv_mod.load(), "grafana-admin")
        self.assertEqual(e["rotation"]["method"], "grafana-admin")
        self.assertIn("grafana-admin", rotations.METHODS)
