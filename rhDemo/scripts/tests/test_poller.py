"""Poller fixcve-auto exécuté de bout en bout par son point d'entrée (fixcve-auto.py), hors réseau.

Tests de caractérisation : ils décrivent le comportement observable (état, commits poussés, journal
d'audit, notifications, code retour) et non l'implémentation. Ils ont été écrits et validés contre
l'ancien poller Bash (fixcve-auto-poll.sh) avant sa réécriture en Python.

- Jenkins : vrai serveur HTTP local (aucun faux `curl`), routes par sous-chaîne d'URL.
- Dépôt : clone local d'un dépôt nu servant d'origin.
- Étapes de remédiation : `fixcve-detect.py`, `-resolve.py`, `-apply.py` et `-verify.py` sont
  remplacés dans le clone par une étape simulée (STUB) qui rejoue des réponses écrites par le test.
  La classification et le validateur de schéma sont les vrais. Une détection sans réponse prévue
  pour le build exécute le vrai détecteur contre le faux Jenkins.

Chaque scénario renvoie à l'incident qui a motivé le garde-fou (docs/FIXCVE_AUTO_INCIDENTS.md).
"""
import copy
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

import helpers

BRANCH = "main"
BOT = "RHDemo FixCVE Bot"
OWASP = "OWASP Dependency-Check"
TRIVY = "Scan Sécurité Images Docker (Trivy)"
ENTRY = "fixcve-auto.py"
POM = "<project>\n  <version>1.0</version>\n  <dep>a 1.0</dep>\n</project>\n"
POM_FIXED = "<project>\n  <version>1.0</version>\n  <dep>a 1.1</dep>\n</project>\n"

STUB = r'''#!/usr/bin/env python3
"""Étape simulée (tests/test_poller.py) : réponses lues dans $FIXCVE_STUBS."""
import json, os, subprocess, sys, tempfile
STEP = os.path.basename(sys.argv[0])[len("fixcve-"):-len(".py")]
OUT_ARG = {"detect": 3, "resolve": 2, "apply": 2, "verify": 4}[STEP]
cfg_path = os.environ["FIXCVE_STUBS"]
with open(cfg_path) as fh:
    cfg = json.load(fh)
calls_path = cfg_path + ".calls"
done = 0
if os.path.exists(calls_path):
    with open(calls_path) as fh:
        done = sum(1 for line in fh if json.loads(line)["step"] == STEP)
with open(calls_path, "a") as fh:
    fh.write(json.dumps({"step": STEP, "argv": sys.argv[1:], "cwd": os.getcwd(),
                         "nvd": os.environ.get("NVD_API_KEY")}) + "\n")
if STEP == "detect":
    resp = (cfg.get("detect") or {}).get(sys.argv[1])
    if resp is None:
        real = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "fixcve-detect-real.py")
        os.execv(sys.executable, [sys.executable, real, *sys.argv[1:]])
else:
    responses = cfg[STEP]
    resp = responses[min(done, len(responses) - 1)]
if resp.get("origin_commit"):
    # Un tiers (Renovate, push manuel) fait avancer origin pendant le cycle.
    work = tempfile.mkdtemp()
    env = dict(os.environ, GIT_AUTHOR_NAME="Renovate Bot", GIT_AUTHOR_EMAIL="r@x",
               GIT_COMMITTER_NAME="Renovate Bot", GIT_COMMITTER_EMAIL="r@x")
    run = lambda *a: subprocess.run(["git", *a], cwd=work, env=env, check=True, capture_output=True)
    run("clone", "-q", "-b", cfg["branch"], cfg["origin"], ".")
    with open(os.path.join(work, "renovate.txt"), "w") as fh:
        fh.write("x")
    run("add", "renovate.txt")
    run("commit", "-q", "-m", "chore(deps): renovate")
    run("push", "-q", "origin", cfg["branch"])
for rel, content in (resp.get("files") or {}).items():
    with open(rel, "w") as fh:
        fh.write(content)
if resp.get("out") is not None:
    with open(sys.argv[OUT_ARG], "w") as fh:
        json.dump(resp["out"], fh)
sys.stdout.write(resp.get("stdout", ""))
sys.exit(resp.get("exit", 0))
'''


class HttpStatus:
    def __init__(self, code):
        self.code = code


class FakeJenkins:
    """Serveur HTTP local : la première route dont la clé est une sous-chaîne du chemin répond."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        jenkins = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                jenkins.requests.append((self.path, self.headers.get("Authorization")))
                for key, body in jenkins.routes.items():
                    if key in self.path:
                        if isinstance(body, HttpStatus):
                            self.send_response(body.code)
                            self.end_headers()
                            return
                        data = (body if isinstance(body, str) else json.dumps(body)).encode()
                        self.send_response(200)
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        return
                self.send_response(404)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def git(cwd, *args, author=None):
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null")
    if author:
        env.update(GIT_AUTHOR_NAME=author, GIT_AUTHOR_EMAIL="a@x", GIT_COMMITTER_NAME=author,
                   GIT_COMMITTER_EMAIL="a@x")
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, check=True,
                          env=env).stdout.strip()


def fixture(name, build=None):
    doc = copy.deepcopy(helpers.load_fixture(name))
    if build is not None:
        doc["jenkins_build"] = build
    return doc


def keys(detected):
    return [f["finding_id"] + "|" + f["package_name"] for f in detected["findings"]]


# --- Réponses des étapes simulées ------------------------------------------------------------

def detect_ok(build, name="build-914-detected.json"):
    doc = fixture(name, build)
    return {"stdout": f"FIXCVE_DETECT_RESULT: OK {len(doc['findings'])}\n", "out": doc}


def detect_no_action(reason):
    return {"stdout": f"FIXCVE_DETECT_RESULT: NO_ACTION {reason}\n", "out": {}}


def resolve_ok(name="build-914-lookup.json", lookup=None, build=11):
    doc = copy.deepcopy(lookup) if lookup else fixture(name)
    doc["jenkins_build"] = build
    return {"stdout": "info: recherche simulée\n"
                      f"FIXCVE_RESOLVE_RESULT: OK {len(doc['findings'])} fix=0 no_fix=0 lookup_failed=0 pending=0\n",
            "out": doc}


def apply_applied(message="fix(security): corriger a (remédiation automatique build #11)", events=(), **extra):
    out = {"result": "APPLIED", "reason": "1", "changed_files": ["pom.xml"], "commit_message": message,
           "actions": [], "pending_resolved": [], "events": list(events)}
    return dict({"stdout": "info: montee a : applied\nFIXCVE_APPLY_RESULT: APPLIED 1\n", "out": out,
                 "files": {"pom.xml": POM_FIXED}}, **extra)


def apply_no_action(reason, events=()):
    out = {"result": "NO_ACTION", "reason": reason, "changed_files": [], "commit_message": None,
           "actions": [], "pending_resolved": [], "events": list(events)}
    return {"stdout": f"FIXCVE_APPLY_RESULT: NO_ACTION {reason}\n", "out": out}


def verify_ok(incomplete=()):
    out = {"ok": True, "errors": [], "failed_upgrades": [], "new_findings": [], "incomplete": list(incomplete)}
    extra = f" incomplet={','.join(incomplete)}" if incomplete else ""
    return {"stdout": f"FIXCVE_VERIFY_RESULT: OK{extra}\n", "out": out}


def verify_fail(upgrades=(), errors=(), new=()):
    out = {"ok": False, "errors": list(errors), "failed_upgrades": list(upgrades), "new_findings": list(new),
           "incomplete": []}
    lines = "".join(f"erreur: {e}\n" for e in errors)
    return {"stdout": lines + f"FIXCVE_VERIFY_RESULT: FAIL upgrades={','.join(upgrades) or '-'} "
                              f"errors={len(errors)} new=-\n", "out": out}


class PollerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fixcve-poller-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.jenkins = FakeJenkins()
        self.addCleanup(self.jenkins.close)
        self.origin = os.path.join(self.tmp, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", BRANCH, self.origin], check=True)
        self.repo = os.path.join(self.tmp, "repo")
        git(self.tmp, "clone", "-q", self.origin, self.repo)
        scripts = os.path.join(self.repo, "rhDemo", "scripts")
        shutil.copytree(helpers.SCRIPTS, scripts, ignore=shutil.ignore_patterns("__pycache__", "tests"))
        os.rename(os.path.join(scripts, "fixcve-detect.py"), os.path.join(scripts, "fixcve-detect-real.py"))
        for step in ("detect", "resolve", "apply", "verify"):
            path = os.path.join(scripts, f"fixcve-{step}.py")
            with open(path, "w") as fh:
                fh.write(STUB)
            os.chmod(path, 0o755)
        self.write("rhDemo/docs/fixcve-audit.jsonl", "")
        self.write("rhDemo/docs/fixcve-audit.md", "")
        self.write("rhDemo/pom.xml", POM)
        self.write(".gitignore", "rhDemo/.fixcve-cycle/\nrhDemo/frontend/node/\n__pycache__/\n")
        self.write("rhDemo/frontend/node/npm", "#!/bin/sh\n")
        os.chmod(os.path.join(self.repo, "rhDemo/frontend/node/npm"), 0o755)
        for k, v in (("user.name", "t"), ("user.email", "t@example.invalid")):
            git(self.repo, "config", k, v)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "push", "-q", "origin", f"HEAD:{BRANCH}")
        self.base_sha = git(self.repo, "rev-parse", "HEAD")
        self.state_dir = os.path.join(self.tmp, "state")
        os.makedirs(self.state_dir)
        self.notify = os.path.join(self.tmp, "notify.txt")
        self.stubs_file = os.path.join(self.tmp, "stubs.json")

    # --- outils -------------------------------------------------------------------------------
    def write(self, rel, content):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)

    def write_state(self, **kw):
        from fixcve_lib.cycle import INITIAL_STATE
        with open(os.path.join(self.state_dir, "state.json"), "w") as fh:
            json.dump(dict(INITIAL_STATE, **kw), fh)

    def read_state(self):
        with open(os.path.join(self.state_dir, "state.json")) as fh:
            return json.load(fh)

    def run_poll(self, routes, action="poll", build=None, code=0, stubs=None, **extra_env):
        self.jenkins.routes = routes
        with open(self.stubs_file, "w") as fh:
            json.dump(dict(stubs or {}, origin=self.origin, branch=BRANCH), fh)
        env = dict(os.environ, FIXCVE_JENKINS_URL=self.jenkins.url, FIXCVE_STUBS=self.stubs_file,
                   FIXCVE_BRANCH=BRANCH, FIXCVE_STATE_DIR=self.state_dir, FIXCVE_REPO_DIR=self.repo,
                   FIXCVE_NOTIFY_FILE=self.notify, JENKINS_USER="u", JENKINS_TOKEN="jeton-jenkins",
                   CODEBERG_USER="u", CODEBERG_TOKEN="jeton-codeberg", GIT_CONFIG_GLOBAL="/dev/null",
                   **extra_env)
        env.pop("NVD_API_KEY", None) if "NVD_API_KEY" not in extra_env else None
        args = [action] + ([str(build)] if build is not None else [])
        r = subprocess.run(["python3", "-I", os.path.join(self.repo, "rhDemo", "scripts", ENTRY), *args],
                           env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, code, r.stdout[-1500:] + r.stderr[-3000:])
        return r.stdout + r.stderr

    def calls(self, step=None):
        path = self.stubs_file + ".calls"
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            calls = [json.loads(line) for line in fh]
        return [c for c in calls if step is None or c["step"] == step]

    def origin_log(self, n=5):
        return git(self.origin, "log", f"-{n}", "--format=%s", BRANCH).splitlines()

    def origin_head_subject(self):
        return self.origin_log(1)[0]

    def audit_events(self):
        path = os.path.join(self.repo, "rhDemo/docs/fixcve-audit.jsonl")
        with open(path) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def pushed_audit_events(self):
        text = git(self.origin, "show", f"{BRANCH}:rhDemo/docs/fixcve-audit.jsonl")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def notified(self):
        if not os.path.exists(self.notify):
            return ""
        with open(self.notify) as fh:
            return fh.read()

    def build(self, number, result, stage=None, sha=None):
        routes = {"lastCompletedBuild": {"number": number, "result": result}}
        if stage:
            routes[f"/{number}/wfapi/describe"] = {"stages": [{"name": "Build", "status": "SUCCESS"},
                                                              {"name": stage, "status": "FAILED"}]}
        if sha:
            routes[f"/{number}/api/json?tree=actions"] = {"actions": [{"lastBuiltRevision": {"SHA1": sha}}]}
        return routes

    def bot_fix(self, content=POM_FIXED):
        """Correctif du bot déjà poussé (phase B)."""
        self.write("rhDemo/pom.xml", content)
        git(self.repo, "add", "rhDemo/pom.xml")
        git(self.repo, "commit", "-q", "-m", "fix(security): corriger a (remédiation automatique build #10)",
            author=BOT)
        git(self.repo, "push", "-q", "origin", f"HEAD:{BRANCH}")
        return git(self.repo, "rev-parse", "HEAD")

    def pending(self, fix, original, stage="owasp", **kw):
        self.write_state(status="pending_validation", last_processed_build=10,
                         pending={"original_build": 10, "fix_commit_sha": fix, "trigger_build_seen": 10,
                                  "stage_type": stage, "original_findings": original}, **kw)


class ActionsTest(PollerTest):
    """Actions d'exploitation du job (paramètre ACTION)."""

    def test_status_affiche_l_etat(self):
        self.write_state(last_processed_build=42)
        out = self.run_poll({}, action="status")
        self.assertIn('"last_processed_build": 42', out)

    def test_resume_leve_la_halte(self):
        self.write_state(status="halted", consecutive_rollbacks=2, consecutive_prepush_failures=2,
                         consecutive_no_action_pushes=2, last_processed_build=11)
        self.run_poll(self.build(11, "SUCCESS"), action="resume")
        s = self.read_state()
        self.assertEqual((s["status"], s["consecutive_rollbacks"], s["consecutive_prepush_failures"],
                          s["consecutive_no_action_pushes"]), ("idle", 0, 0, 0))

    def test_clear_blocked_garde_une_cause_no_action(self):
        cause = {"kind": "no_action", "source_sha": "x", "since": "2026-01-01T00:00:00Z",
                 "recheck_seconds": None, "attempts": 0}
        self.write_state(last_processed_build=11, same_cause=cause)
        self.run_poll(self.build(11, "SUCCESS"), action="clear-blocked")
        self.assertEqual(self.read_state()["same_cause"], cause)

    def test_clear_blocked_efface_un_blocage(self):
        self.write_state(last_processed_build=11, same_cause={
            "kind": "blocked", "source_sha": "x", "since": "2026-01-01T00:00:00Z",
            "recheck_seconds": 172800, "attempts": 0})
        self.run_poll(self.build(11, "SUCCESS"), action="clear-blocked")
        self.assertIsNone(self.read_state()["same_cause"])

    def test_replay_sans_numero_refuse(self):
        """Erreur de la session du 2026-11-25 : BUILD_TO_REPLAY vide ou « #895 »."""
        self.write_state(last_processed_build=11)
        out = self.run_poll({}, action="replay", build="#895", code=2)
        self.assertIn("numéro de build attendu", out)

    def test_action_inconnue_refusee(self):
        out = self.run_poll({}, action="purge", code=2)
        self.assertIn("Action inconnue", out)

    def test_replay_hors_dry_run_remet_le_build_a_traiter(self):
        self.write_state(last_processed_build=11)
        self.run_poll(self.build(11, "SUCCESS"), action="replay", build=11)
        self.assertEqual(self.read_state()["last_processed_build"], 11)

    def test_halte_rien_n_est_fait(self):
        self.write_state(status="halted", last_processed_build=10)
        out = self.run_poll(self.build(11, "FAILURE", stage=OWASP))
        self.assertIn("halted", out)
        self.assertEqual(self.read_state()["last_processed_build"], 10)
        self.assertEqual(self.jenkins.requests, [])


class PhaseATest(PollerTest):
    def test_build_vert(self):
        self.write_state(last_processed_build=10, consecutive_no_action_pushes=1,
                         same_cause={"kind": "no_action", "source_sha": "x", "since": "2026-01-01T00:00:00Z",
                                     "recheck_seconds": None, "attempts": 0})
        self.run_poll(self.build(11, "SUCCESS"), FIXCVE_EXPECTED_BUILD="11")
        s = self.read_state()
        self.assertEqual((s["last_processed_build"], s["same_cause"], s["consecutive_no_action_pushes"]),
                         (11, None, 0))
        self.assertEqual(self.origin_head_subject(), "base", "rien n'est poussé")

    def test_authentification_jenkins_par_en_tete(self):
        self.write_state(last_processed_build=10)
        self.run_poll(self.build(11, "SUCCESS"))
        self.assertTrue(self.jenkins.requests)
        self.assertTrue(all((auth or "").startswith("Basic ") for _, auth in self.jenkins.requests))

    def test_rien_de_nouveau(self):
        self.write_state(last_processed_build=11)
        out = self.run_poll(self.build(11, "FAILURE", stage=OWASP))
        self.assertIn("Rien de nouveau", out)
        self.assertEqual(self.calls(), [])

    def test_jeton_jenkins_rejete_alerte(self):
        """#752/#753 et 2026-07-29 : un appel Jenkins en échec est visible, et un 401 est notifié."""
        self.write_state(last_processed_build=10)
        out = self.run_poll({"lastCompletedBuild": HttpStatus(401)}, code=1)
        self.assertIn("HTTP 401", out)
        self.assertIn("ALERTE", self.notified())
        self.assertEqual(self.read_state()["last_processed_build"], 10)

    def test_jenkins_injoignable_etat_inchange(self):
        self.write_state(last_processed_build=10)
        out = self.run_poll({"lastCompletedBuild": HttpStatus(503)}, code=1)
        self.assertIn("Échec de l'appel Jenkins", out)
        self.assertEqual(self.notified(), "")

    def test_echec_hors_perimetre_non_trace(self):
        """#772/#774, #796/#797 : un échec hors Trivy/OWASP n'est jamais journalisé en git."""
        self.write_state(last_processed_build=10)
        self.run_poll(self.build(11, "FAILURE", stage="Tests Selenium"))
        self.assertEqual(self.read_state()["last_processed_build"], 11)
        self.assertEqual(self.origin_head_subject(), "base")
        self.assertEqual(self.audit_events(), [])

    def test_premier_stage_en_echec_est_la_cause(self):
        """Cascade : seul le premier stage non SUCCESS compte (Selenium avant un Trivy jamais atteint)."""
        self.write_state(last_processed_build=10)
        routes = self.build(11, "FAILURE")
        routes["/11/wfapi/describe"] = {"stages": [{"name": "Tests Selenium", "status": "FAILED"},
                                                   {"name": TRIVY, "status": "NOT_EXECUTED"}]}
        self.run_poll(routes)
        self.assertEqual(self.calls(), [])

    def test_blocage_confirme_ancien_format_ignore(self):
        """#735-#744 : ancien state.json (blocked_confirmed) lu ; même code source : cycle ignoré sans push."""
        with open(os.path.join(self.state_dir, "state.json"), "w") as fh:
            json.dump({"last_processed_build": 10, "status": "idle", "pending": None, "consecutive_rollbacks": 0,
                       "consecutive_prepush_failures": 0, "consecutive_no_action_pushes": 0,
                       "blocked_confirmed": {"since": "2099-01-01T00:00:00Z", "source_sha": self.base_sha},
                       "no_action_confirmed": None}, fh)
        out = self.run_poll(self.build(11, "FAILURE", stage=TRIVY))
        self.assertIn("blocage déjà constaté", out)
        s = self.read_state()
        self.assertEqual((s["last_processed_build"], s["same_cause"]["kind"]), (11, "blocked"))
        self.assertNotIn("blocked_confirmed", s)
        self.assertEqual(self.origin_head_subject(), "base")

    def test_no_action_journalise_une_fois_par_code_source(self):
        """#799-#802 : détection sans CVE exploitable, notifiée une fois puis silence sur le même code."""
        self.write_state(last_processed_build=10)
        stubs = {"detect": {"11": detect_no_action("owasp_no_finding_above_threshold"),
                            "12": detect_no_action("owasp_no_finding_above_threshold")}}
        self.run_poll(self.build(11, "FAILURE", stage=OWASP), stubs=stubs)
        self.assertIn("détection sans CVE exploitable", self.origin_head_subject())
        self.assertEqual(self.pushed_audit_events()[-1]["event"], "skipped_infra_failure")
        pushed = self.origin_log(10)
        out = self.run_poll(self.build(12, "FAILURE", stage=OWASP), stubs=stubs)
        self.assertIn("déjà notifiée", out)
        self.assertEqual(self.origin_log(10), pushed)
        self.assertEqual(self.read_state()["last_processed_build"], 12)

    def test_halte_apres_pushes_no_action(self):
        """Vrai détecteur, rapport OWASP sans finding, 2e push consécutif : halte et notification."""
        self.write_state(last_processed_build=10, consecutive_no_action_pushes=1)
        routes = self.build(11, "FAILURE", stage=OWASP)
        routes["dependency-check-report.html"] = "<html></html>"
        self.run_poll(routes)
        s = self.read_state()
        self.assertEqual((s["status"], s["consecutive_no_action_pushes"], s["same_cause"]["kind"]),
                         ("halted", 2, "no_action"))
        self.assertIn("halte automatique", self.origin_head_subject())
        self.assertIn("Halte", self.notified())

    def test_detection_sans_ligne_de_resultat(self):
        """#710 : étape sans ligne de résultat = échec pré-push journalisé, pas un arrêt silencieux."""
        self.write_state(last_processed_build=10)
        self.run_poll(self.build(11, "FAILURE", stage=OWASP),
                      stubs={"detect": {"11": {"stdout": "Traceback...\n"}}})
        s = self.read_state()
        self.assertEqual((s["last_processed_build"], s["consecutive_prepush_failures"], s["status"]),
                         (11, 1, "idle"))
        ev = self.pushed_audit_events()[-1]
        self.assertEqual((ev["event"], ev["reason"]), ("detect_phase_failed", "no_result_line"))

    def test_detection_en_erreur_reessayee(self):
        """Crash du détecteur (Jenkins injoignable) : rien n'est écrit, nouvel essai au passage suivant."""
        self.write_state(last_processed_build=10)
        out = self.run_poll(self.build(11, "FAILURE", stage=OWASP), code=1,
                            stubs={"detect": {"11": {"stdout": "boom\n", "exit": 1}}})
        self.assertIn("fixcve-detect.py a échoué", out)
        self.assertEqual(self.read_state()["last_processed_build"], 10)
        self.assertEqual(self.origin_head_subject(), "base")

    def test_detected_invalide_puis_halte_pre_push(self):
        """#894 (schéma) puis 2e échec pré-push consécutif : halte."""
        self.write_state(last_processed_build=10, consecutive_prepush_failures=1)
        bad = {"stdout": "FIXCVE_DETECT_RESULT: OK 1\n", "out": fixture("build-894-detected-invalid.json", 11)}
        self.run_poll(self.build(11, "FAILURE", stage=TRIVY), stubs={"detect": {"11": bad}})
        s = self.read_state()
        self.assertEqual(s["status"], "halted")
        self.assertIn("halte automatique", self.origin_head_subject())
        reasons = [(e["event"], e.get("reason")) for e in self.pushed_audit_events()]
        self.assertIn(("detect_phase_failed", "schema_invalid"), reasons)
        self.assertIn(("automation_halted", "max_consecutive_prepush_failures"), reasons)
        self.assertTrue(os.path.exists(os.path.join(self.state_dir, "cycle/archive/11-detected-invalid.json")))
        self.assertIn("Halte", self.notified())

    def test_recherche_en_erreur_reessayee(self):
        self.write_state(last_processed_build=10)
        out = self.run_poll(self.build(11, "FAILURE", stage=OWASP), code=1,
                            stubs={"detect": {"11": detect_ok(11)}, "resolve": [{"stdout": "boom\n", "exit": 1}]})
        self.assertIn("fixcve-resolve.py a échoué", out)
        self.assertEqual(self.read_state()["last_processed_build"], 10)

    def test_lookup_incoherent_echec_pre_push(self):
        self.write_state(last_processed_build=10)
        lookup = fixture("build-914-lookup.json")
        lookup["findings"][0]["finding_id"] = "CVE-2026-0000"   # finding absent de detected.json
        self.run_poll(self.build(11, "FAILURE", stage=OWASP),
                      stubs={"detect": {"11": detect_ok(11)}, "resolve": [resolve_ok(lookup=lookup)]})
        ev = self.pushed_audit_events()[-1]
        self.assertEqual((ev["event"], ev["step"], ev["reason"], ev["outcome_code"]),
                         ("cycle_failed", "resolve", "schema_invalid", "tooling"))
        self.assertEqual(self.read_state()["consecutive_prepush_failures"], 1)
        self.assertTrue(os.path.exists(os.path.join(self.state_dir, "cycle/archive/11-lookup-invalid.json")))

    def remediation(self, apply, verify=(), build=11, **kw):
        stubs = {"detect": {str(build): detect_ok(build)}, "resolve": [resolve_ok(build=build)], "apply": list(apply),
                 "verify": list(verify) or [verify_ok()]}
        return self.run_poll(self.build(build, "FAILURE", stage=OWASP), stubs=stubs, **kw)

    def test_correctif_pousse_en_deux_commits(self):
        """Bac à sable 2026-10-09, #882 : correctif seul (annulable), puis journal committé à part."""
        self.write_state(last_processed_build=10)
        event = {"timestamp": "2026-11-25T00:00:00Z", "event": "remediation_applied", "jenkins_build": 11,
                 "stage": "owasp", "cves": ["CVE-1"], "actions": ["a 1.1"], "outcome_code": "fixed"}
        out = self.remediation([apply_applied(events=[event])], [verify_ok(incomplete=["odc"])])
        self.assertIn("Plan : OK 4", out)
        log = self.origin_log(3)
        self.assertTrue(log[0].startswith("chore(security): journal fixcve-auto - build #11 (correctif "))
        self.assertEqual(log[1], "fix(security): corriger a (remédiation automatique build #11)")
        fix = git(self.origin, "rev-parse", f"{BRANCH}~1")
        self.assertEqual(git(self.origin, "show", "--format=", "--name-only", fix), "rhDemo/pom.xml")
        self.assertEqual(git(self.origin, "log", "-1", "--format=%an", fix), BOT)
        s = self.read_state()
        self.assertEqual((s["status"], s["pending"]["fix_commit_sha"], s["pending"]["original_findings"],
                          s["pending"]["stage_type"], s["pending"]["trigger_build_seen"]),
                         ("pending_validation", fix, keys(fixture("build-914-detected.json")), "owasp", 11))
        events = [e["event"] for e in self.pushed_audit_events()]
        self.assertEqual(events, ["remediation_applied", "local_validation_incomplete"])
        self.assertIn("remediation_applied", git(self.origin, "show", f"{BRANCH}:rhDemo/docs/fixcve-audit.md"))
        for label in ("detected", "lookup", "plan", "apply"):
            self.assertTrue(os.path.exists(os.path.join(self.state_dir, f"cycle/archive/11-{label}.json")), label)

    def test_cle_nvd_reservee_a_la_verification(self):
        self.write_state(last_processed_build=10)
        self.remediation([apply_applied()], NVD_API_KEY="cle-nvd")
        self.assertEqual({c["step"]: c["nvd"] for c in self.calls()},
                         {"detect": None, "resolve": None, "apply": None, "verify": "cle-nvd"})

    def test_etapes_lancees_depuis_rhdemo(self):
        self.write_state(last_processed_build=10)
        self.remediation([apply_applied()])
        rhdemo = os.path.realpath(os.path.join(self.repo, "rhDemo"))
        for c in self.calls():
            if c["step"] != "detect":
                self.assertEqual(os.path.realpath(c["cwd"]), rhdemo, c["step"])

    def test_aucun_secret_en_argument_de_commande(self):
        """Invariant du projet : un secret n'est jamais un argument (visible dans `ps`). L'ancien
        poller passait le jeton Jenkins à `curl -u`."""
        self.write_state(last_processed_build=10)
        shims = os.path.join(self.tmp, "shims")
        os.makedirs(shims)
        argv_log = os.path.join(self.tmp, "argv.log")
        for tool in ("git", "curl"):
            real = shutil.which(tool)
            with open(os.path.join(shims, tool), "w") as fh:
                fh.write(f'#!/bin/sh\nprintf "%s\\n" "{tool} $*" >> {argv_log}\nexec {real} "$@"\n')
            os.chmod(os.path.join(shims, tool), 0o755)
        self.remediation([apply_applied(origin_commit=True)], NVD_API_KEY="cle-nvd",
                         PATH=shims + os.pathsep + os.environ["PATH"])
        with open(argv_log) as fh:
            commands = fh.read()
        self.assertIn("git push", commands)
        for secret in ("jeton-jenkins", "jeton-codeberg", "cle-nvd"):
            self.assertNotIn(secret, commands)

    def test_dry_run_rien_pousse_etat_reel_intact(self):
        self.write_state(last_processed_build=10)
        out = self.remediation([apply_applied()], FIXCVE_DRY_RUN="true")
        self.assertIn("DRY_RUN : push omis", out)
        self.assertIn("push omis.", out)
        self.assertEqual(self.origin_head_subject(), "base")
        self.assertEqual(self.read_state()["last_processed_build"], 10)

    def test_origin_avance_commits_du_bot_rejoues(self):
        """Push refusé (merge Renovate pendant le cycle) : commits du bot rejoués sur origin."""
        self.write_state(last_processed_build=10)
        self.remediation([apply_applied(origin_commit=True)])
        log = self.origin_log(3)
        self.assertEqual(log[1:], ["fix(security): corriger a (remédiation automatique build #11)",
                                   "chore(deps): renovate"])
        self.assertEqual(self.read_state()["pending"]["fix_commit_sha"], git(self.origin, "rev-parse", f"{BRANCH}~1"))

    def test_montee_non_confirmee_bascule_sans_correctif(self):
        """Montée refusée par la vérification : réappliquée une fois en « sans correctif »."""
        self.write_state(last_processed_build=10)
        self.remediation([apply_applied(), apply_applied()],
                         [verify_fail(upgrades=["GHSA-86w9-cpqp-85rv|node-forge"]), verify_ok()])
        applies = self.calls("apply")
        self.assertEqual(len(applies), 2)
        self.assertEqual(applies[1]["argv"][-2:], ["--downgrade", "GHSA-86w9-cpqp-85rv|node-forge"])
        self.assertEqual(self.read_state()["status"], "pending_validation")

    def test_verification_en_echec_annule_le_cycle(self):
        self.write_state(last_processed_build=10)
        self.remediation([apply_applied()], [verify_fail(errors=["owasp-suppressions.xml illisible"])])
        ev = self.pushed_audit_events()[-1]
        self.assertEqual((ev["event"], ev["step"], ev["reason"], ev["outcome_code"]),
                         ("cycle_failed", "verify", "verification_locale_en_echec", "bad_fix"))
        self.assertIn("illisible", ev["detail"])
        with open(os.path.join(self.repo, "rhDemo/pom.xml")) as fh:
            self.assertEqual(fh.read(), POM, "modification abandonnée")
        self.assertEqual(git(self.origin, "show", f"{BRANCH}:rhDemo/pom.xml") + "\n", POM)

    def test_cve_nouvelles_au_rescan_retraitees(self):
        """#1102 : CVE nouvelle au rescan local ajoutée au cycle, recherchée et classée une fois."""
        self.write_state(last_processed_build=10)
        new = fixture("build-882-detected.json")["findings"][0]
        lookup = fixture("build-914-lookup.json")
        lookup["findings"].append(fixture("build-882-lookup.json")["findings"][0])
        stubs = {"detect": {"11": detect_ok(11)}, "resolve": [resolve_ok(), resolve_ok(lookup=lookup)],
                 "apply": [apply_applied()], "verify": [verify_fail(new=[new]), verify_ok()]}
        out = self.run_poll(self.build(11, "FAILURE", stage=OWASP), stubs=stubs)
        self.assertIn("CVE nouvelles au rescan local", out)
        self.assertEqual(len(self.calls("resolve")), 2)
        self.assertIn(new["finding_id"] + "|" + new["package_name"], self.read_state()["pending"]["original_findings"])

    def test_deja_corrige_sur_head_sans_push(self):
        """Replay du #1097 : rien à committer, un push relancerait un build inutile."""
        self.write_state(last_processed_build=10)
        out = self.remediation([apply_no_action("deja_corrige_sur_head")])
        self.assertIn("aucune action (deja_corrige_sur_head)", out)
        self.assertEqual(self.origin_head_subject(), "base")
        s = self.read_state()
        self.assertEqual((s["last_processed_build"], s["status"]), (11, "idle"))

    def test_findings_bloques_puis_silence(self):
        """#895 puis #735-#744 : blocage journalisé et notifié une fois, cycle suivant ignoré."""
        self.write_state(last_processed_build=10)
        event = {"timestamp": "2026-11-25T00:00:00Z", "event": "findings_blocked", "jenkins_build": 11,
                 "stage": "owasp", "outcome_code": "blocked_no_fix_ge9", "findings": []}
        self.remediation([apply_no_action("cve_bloquante_sans_upgrade_disponible", events=[event])])
        self.assertIn("findings bloqués sans correctif", self.origin_head_subject())
        self.assertEqual(self.pushed_audit_events()[-1]["event"], "findings_blocked")
        self.assertIn("findings bloqués", self.notified())
        self.assertEqual(self.read_state()["same_cause"]["kind"], "blocked")
        pushed = self.origin_log(10)
        out = self.run_poll(self.build(12, "FAILURE", stage=OWASP))
        self.assertIn("blocage déjà constaté", out)
        self.assertEqual(self.origin_log(10), pushed)

    def test_recherche_transitoire_reessayee_sans_journal(self):
        self.write_state(last_processed_build=10)
        self.remediation([apply_no_action("transient")])
        self.assertEqual(self.origin_head_subject(), "base")
        s = self.read_state()
        self.assertEqual((s["last_processed_build"], s["same_cause"]["kind"], s["same_cause"]["attempts"]),
                         (10, "transient", 1))

    def test_application_sans_ligne_de_resultat(self):
        self.write_state(last_processed_build=10)
        self.remediation([{"stdout": "Traceback\n"}])
        ev = self.pushed_audit_events()[-1]
        self.assertEqual((ev["event"], ev["step"], ev["reason"]), ("cycle_failed", "apply", "no_result_line"))


class ReplayTest(PollerTest):
    def replay_routes(self):
        """Dernier build terminé vert (#20) ; build #11 en échec Trivy, scan raté (aucun rapport)."""
        routes = self.build(20, "SUCCESS")
        routes["/11/api/json?tree=number"] = {"number": 11, "result": "FAILURE"}
        routes["/11/wfapi/describe"] = {"stages": [{"name": TRIVY, "status": "FAILED"}]}
        routes["/11/api/json?tree=artifacts"] = {"artifacts": []}
        return routes

    def test_replay_dry_run_traite_le_build_demande(self):
        """DRY_RUN : replay d'un build ancien, traité à la place du dernier build terminé ; état réel intact."""
        self.write_state(last_processed_build=20, status="pending_validation",
                         pending={"original_build": 19, "fix_commit_sha": self.base_sha, "trigger_build_seen": 19,
                                  "stage_type": "owasp", "original_findings": []})
        out = self.run_poll(self.replay_routes(), action="replay", build=11, FIXCVE_DRY_RUN="true")
        self.assertIn("rejeu du build #11", out)
        self.assertIn("Build #11 en échec sur trivy", out)
        self.assertIn("DRY_RUN : push omis", out)
        self.assertEqual(self.read_state()["last_processed_build"], 20, "état réel inchangé")
        self.assertEqual(self.origin_head_subject(), "base")

    def test_replay_build_ignore_hors_dry_run(self):
        self.write_state(last_processed_build=19)
        out = self.run_poll(self.replay_routes(), FIXCVE_REPLAY_BUILD="11")
        self.assertNotIn("rejeu", out)
        self.assertEqual(self.read_state()["last_processed_build"], 20)


class PhaseBTest(PollerTest):
    def original(self):
        return keys(fixture("build-914-detected.json"))

    def test_attente_du_build_du_correctif(self):
        fix = self.bot_fix()
        self.pending(fix, self.original())
        out = self.run_poll(self.build(10, "FAILURE"))
        self.assertIn("En attente du build", out)
        self.assertEqual(self.read_state()["status"], "pending_validation")

    def test_build_intercale_ignore(self):
        """#749/#750 : le build suivant n'est pas bâti sur le correctif, ni validation ni rollback."""
        fix = self.bot_fix()
        self.pending(fix, self.original())
        out = self.run_poll(self.build(11, "FAILURE", sha=self.base_sha))
        self.assertIn("push intercalé", out)
        self.assertEqual(self.read_state()["status"], "pending_validation")
        self.assertEqual(self.calls(), [])

    def test_validation_reussie_pousse_le_journal(self):
        self.write_state(status="pending_validation", last_processed_build=10, consecutive_rollbacks=1,
                         pending={"original_build": 10, "fix_commit_sha": self.base_sha, "trigger_build_seen": 10,
                                  "stage_type": "owasp", "original_findings": ["CVE-2026-1|p"]})
        self.run_poll(self.build(11, "SUCCESS", sha=self.base_sha))
        s = self.read_state()
        self.assertEqual((s["status"], s["pending"], s["consecutive_rollbacks"], s["last_processed_build"]),
                         ("idle", None, 0, 11))
        self.assertIn("confirmation automatique du correctif", self.origin_head_subject())
        self.assertEqual(self.pushed_audit_events()[-1]["event"], "validation_success")

    def failing_console(self):
        return ("Started\n[Pipeline] { (Build)\nok\n[Pipeline] }\n"
                f"[Pipeline] {{ (rhDemo/vars/x.groovy)\n[Pipeline] {{ ({OWASP})\n"
                "\x1b[31m[ERROR] npm warn deprecated\x1b[0m\nÉCHEC: 3 vulnérabilités au-dessus du seuil\r\n"
                f"[Pipeline] }}\n[Pipeline] {{ ({TRIVY})\nStage \"{TRIVY}\" skipped due to earlier failure(s)\n")

    def failing_routes(self, fix, number=11):
        routes = self.build(number, "FAILURE", sha=fix)
        routes[f"/{number}/wfapi/describe"] = {"stages": [
            {"name": OWASP, "status": "SUCCESS", "startTimeMillis": 1},
            {"name": TRIVY, "status": "FAILED", "startTimeMillis": 2}]}
        routes[f"/{number}/consoleText"] = self.failing_console()
        return routes

    def test_rollback_avec_cause_reelle(self):
        """#760/#762, #819 : rollback ; stage fautif retrouvé dans la console, pas le stage sauté."""
        fix = self.bot_fix()
        self.pending(fix, self.original())
        self.run_poll(self.failing_routes(fix), stubs={"detect": {"11": detect_ok(11)}})
        log = self.origin_log(2)
        self.assertTrue(log[0].startswith("chore(security): journal fixcve-auto - rollback build #11"))
        self.assertTrue(log[1].startswith("Revert "))
        self.assertEqual(git(self.origin, "show", f"{BRANCH}:rhDemo/pom.xml") + "\n", POM)
        ev = self.pushed_audit_events()[-1]
        self.assertEqual((ev["event"], ev["failure_stage"], ev["partial_check"]),
                         ("validation_failed_rollback", OWASP, "aucun_progres"))
        self.assertIn("ÉCHEC: 3 vulnérabilités", ev["failure_detail"])
        self.assertNotIn("\x1b", ev["failure_detail"])
        s = self.read_state()
        self.assertEqual((s["status"], s["consecutive_rollbacks"], s["last_processed_build"]), ("idle", 1, 11))
        self.assertIn("Rollback du correctif", self.notified())

    def test_deuxieme_rollback_halte(self):
        fix = self.bot_fix()
        self.pending(fix, self.original(), consecutive_rollbacks=1)
        self.run_poll(self.failing_routes(fix), stubs={"detect": {"11": detect_ok(11)}})
        self.assertIn("halte automatique fixcve-auto après rollbacks répétés", self.origin_head_subject())
        self.assertEqual(self.read_state()["status"], "halted")
        self.assertIn("Halte", self.notified())

    def test_validation_partielle_garde_le_correctif(self):
        """#718/#734 : d'autres CVE restent rouges, mais aucune nouvelle et au moins une corrigée."""
        fix = self.bot_fix()
        self.pending(fix, self.original())
        partial = detect_ok(11)
        partial["out"]["findings"] = partial["out"]["findings"][1:]
        partial["stdout"] = "FIXCVE_DETECT_RESULT: OK 3\n"
        self.run_poll(self.failing_routes(fix), stubs={"detect": {"11": partial}})
        self.assertIn("validation partielle", self.origin_head_subject())
        ev = self.pushed_audit_events()[-1]
        self.assertEqual((ev["event"], ev["removed"]), ("validation_partial", self.original()[:1]))
        s = self.read_state()
        self.assertEqual((s["status"], s["same_cause"]["kind"]), ("idle", "blocked"))
        self.assertEqual(git(self.origin, "show", f"{BRANCH}:rhDemo/pom.xml") + "\n", POM_FIXED)

    def test_stage_owasp_en_echec_sans_finding_detecte_garde(self):
        """#972 : stage OWASP en échec sur un finding que le détecteur ne lit pas (extrait de console
        sans finding du correctif) : correctif gardé."""
        fix = self.bot_fix()
        self.pending(fix, self.original())
        self.run_poll(self.failing_routes(fix),
                      stubs={"detect": {"11": detect_no_action("owasp_no_finding_above_threshold")}})
        self.assertIn("validation partielle", self.origin_head_subject())
        self.assertEqual(self.read_state()["status"], "idle")

    def test_stage_propre_echec_suivant_sans_rollback(self):
        """#890 : OWASP propre, échec sur Trivy ensuite : correctif gardé, build remis à la phase A."""
        fix = self.bot_fix()
        self.pending(fix, self.original())
        routes = self.failing_routes(fix)
        routes["/11/consoleText"] = (f"[Pipeline] {{ ({OWASP})\nok\n[Pipeline] }}\n[Pipeline] {{ ({TRIVY})\n"
                                     "ÉCHEC: 1 vulnérabilités CRITICAL détectées\n[Pipeline] }\n")
        self.run_poll(routes,
                      stubs={"detect": {"11": detect_no_action("owasp_no_finding_above_threshold")}})
        self.assertIn("validé sur owasp, échec suivant sur trivy", self.origin_head_subject())
        ev = self.pushed_audit_events()[-1]
        self.assertEqual((ev["event"], ev["stage_cleared"], ev["next_failing_stage"]),
                         ("validation_stage_cleared", "owasp", "trivy"))
        s = self.read_state()
        self.assertEqual((s["status"], s["last_processed_build"]), ("idle", 10))

    def test_975_suppression_et_cve_nouvelle_independante(self):
        """#975 : correctif réduit à des suppressions, CVE nouvelle sans rapport : pas de rollback."""
        self.write("rhDemo/owasp-suppressions.xml", "<s>\n<a/>\n</s>\n")
        git(self.repo, "add", "rhDemo/owasp-suppressions.xml")
        git(self.repo, "commit", "-q", "-m", "fix(security): accepter a", author=BOT)
        git(self.repo, "push", "-q", "origin", f"HEAD:{BRANCH}")
        fix = git(self.repo, "rev-parse", "HEAD")
        self.pending(fix, self.original())
        self.run_poll(self.failing_routes(fix), stubs={"detect": {"11": detect_ok(11, "build-882-detected.json")}})
        ev = self.pushed_audit_events()[-1]
        self.assertEqual((ev["event"], ev["next_failing_stage"]), ("validation_stage_cleared", "owasp"))
        self.assertIn("<a/>", git(self.origin, "show", f"{BRANCH}:rhDemo/owasp-suppressions.xml"))

    def test_revert_en_conflit_correctif_garde(self):
        """#974/#975 : un commit voisin plus récent rend le revert conflictuel ; clone propre."""
        fix = self.bot_fix()
        self.write("rhDemo/pom.xml", POM_FIXED.replace("1.1", "1.2"))
        git(self.repo, "commit", "-q", "-am", "chore: voisin", author="Humain")
        git(self.repo, "push", "-q", "origin", f"HEAD:{BRANCH}")
        head = git(self.repo, "rev-parse", "HEAD")
        self.pending(fix, self.original())
        self.run_poll(self.failing_routes(head), stubs={"detect": {"11": detect_ok(11)}})
        self.assertIn("rollback impossible", self.origin_head_subject())
        ev = self.pushed_audit_events()[-1]
        self.assertEqual((ev["event"], ev["outcome_code"]), ("rollback_conflict", "bad_fix"))
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertIn("Rollback impossible", self.notified())
        self.assertEqual(self.read_state()["same_cause"]["kind"], "blocked")

    def test_revert_refuse_si_commit_humain(self):
        """État altéré désignant un commit humain : jamais annulé."""
        self.write("rhDemo/pom.xml", POM_FIXED)
        git(self.repo, "commit", "-q", "-am", "fix: humain", author="Humain")
        git(self.repo, "push", "-q", "origin", f"HEAD:{BRANCH}")
        human = git(self.repo, "rev-parse", "HEAD")
        self.pending(human, self.original())
        self.run_poll(self.failing_routes(human), stubs={"detect": {"11": detect_ok(11)}})
        self.assertEqual(git(self.origin, "show", f"{BRANCH}:rhDemo/pom.xml") + "\n", POM_FIXED)
        self.assertEqual(self.pushed_audit_events()[-1]["event"], "rollback_conflict")
        self.assertIn("ALERTE", self.notified())


if __name__ == "__main__":
    unittest.main()
