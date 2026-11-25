"""fixcve-auto-poll.sh exécuté de bout en bout, hors réseau : faux Jenkins (curl simulé dans le PATH),
dépôt local servant d'origin. Vérifie le câblage des règles de cycle (fixcve-cycle.py) : état écrit
après les effets, journal poussé ou non, halte. Les étapes de remédiation ne sont pas exercées ici
(tests dédiés) : les scénarios s'arrêtent avant la détection ou en phase de validation."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import helpers

BRANCH = "main"
FAKE_CURL = r'''#!/usr/bin/env python3
import json, os, sys
url = [a for a in sys.argv[1:] if a.startswith("http")][-1]
routes = json.load(open(os.environ["FAKE_JENKINS"]))
for key, body in routes.items():
    if key in url:
        sys.stdout.write(body if isinstance(body, str) else json.dumps(body))
        sys.exit(0)
sys.exit(22)
'''


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, check=True).stdout.strip()


class PollSmokeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fixcve-poll-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.origin = os.path.join(self.tmp, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", BRANCH, self.origin], check=True)
        self.repo = os.path.join(self.tmp, "repo")
        git(self.tmp, "clone", "-q", self.origin, self.repo)
        shutil.copytree(helpers.SCRIPTS, os.path.join(self.repo, "rhDemo", "scripts"),
                        ignore=shutil.ignore_patterns("__pycache__", "tests"))
        docs = os.path.join(self.repo, "rhDemo", "docs")
        os.makedirs(docs)
        open(os.path.join(docs, "fixcve-audit.jsonl"), "w").close()
        open(os.path.join(docs, "fixcve-audit.md"), "w").close()
        for k, v in (("user.name", "t"), ("user.email", "t@example.invalid")):
            git(self.repo, "config", k, v)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "push", "-q", "origin", f"HEAD:{BRANCH}")
        self.base_sha = git(self.repo, "rev-parse", "HEAD")
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        with open(os.path.join(self.bin, "curl"), "w") as fh:
            fh.write(FAKE_CURL)
        os.chmod(os.path.join(self.bin, "curl"), 0o755)
        self.state_dir = os.path.join(self.tmp, "state")
        os.makedirs(self.state_dir)
        self.notify = os.path.join(self.tmp, "notify.txt")

    def write_state(self, **kw):
        from fixcve_lib.cycle import INITIAL_STATE
        with open(os.path.join(self.state_dir, "state.json"), "w") as fh:
            json.dump(dict(INITIAL_STATE, **kw), fh)

    def read_state(self):
        with open(os.path.join(self.state_dir, "state.json")) as fh:
            return json.load(fh)

    def run_poll(self, routes):
        routes_file = os.path.join(self.tmp, "routes.json")
        with open(routes_file, "w") as fh:
            json.dump(routes, fh)
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"], FAKE_JENKINS=routes_file,
                   FIXCVE_BRANCH=BRANCH, FIXCVE_STATE_DIR=self.state_dir, FIXCVE_REPO_DIR=self.repo,
                   FIXCVE_NOTIFY_FILE=self.notify, JENKINS_USER="u", JENKINS_TOKEN="t",
                   CODEBERG_USER="u", CODEBERG_TOKEN="t", GIT_CONFIG_GLOBAL="/dev/null")
        r = subprocess.run(["bash", os.path.join(self.repo, "rhDemo", "scripts", "fixcve-auto-poll.sh")],
                           env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return r.stderr

    def origin_head_subject(self):
        return git(self.origin, "log", "-1", "--format=%s", BRANCH)

    def build(self, number, result, stage=None):
        routes = {"lastCompletedBuild": {"number": number, "result": result}}
        if stage:
            routes[f"/{number}/wfapi/describe"] = {"stages": [{"name": "Build", "status": "SUCCESS"},
                                                              {"name": stage, "status": "FAILED"}]}
        return routes

    def test_build_vert(self):
        self.write_state(last_processed_build=10, consecutive_no_action_pushes=1,
                         same_cause={"kind": "no_action", "source_sha": "x", "since": "2026-01-01T00:00:00Z",
                                     "recheck_seconds": None, "attempts": 0})
        self.run_poll(self.build(11, "SUCCESS"))
        s = self.read_state()
        self.assertEqual((s["last_processed_build"], s["same_cause"], s["consecutive_no_action_pushes"]),
                         (11, None, 0))
        self.assertEqual(self.origin_head_subject(), "base", "rien n'est poussé")

    def test_echec_hors_perimetre_non_trace(self):
        self.write_state(last_processed_build=10)
        self.run_poll(self.build(11, "FAILURE", stage="Tests Selenium"))
        self.assertEqual(self.read_state()["last_processed_build"], 11)
        self.assertEqual(self.origin_head_subject(), "base")

    def test_blocage_confirme_ancien_format_ignore(self):
        """Ancien state.json (blocked_confirmed) lu ; même code source : cycle ignoré sans push."""
        with open(os.path.join(self.state_dir, "state.json"), "w") as fh:
            json.dump({"last_processed_build": 10, "status": "idle", "pending": None, "consecutive_rollbacks": 0,
                       "consecutive_prepush_failures": 0, "consecutive_no_action_pushes": 0,
                       "blocked_confirmed": {"since": "2099-01-01T00:00:00Z", "source_sha": self.base_sha},
                       "no_action_confirmed": None}, fh)
        err = self.run_poll(self.build(11, "FAILURE", stage="Scan Sécurité Images Docker (Trivy)"))
        self.assertIn("blocage déjà constaté", err)
        s = self.read_state()
        self.assertEqual((s["last_processed_build"], s["same_cause"]["kind"]), (11, "blocked"))
        self.assertNotIn("blocked_confirmed", s)
        self.assertEqual(self.origin_head_subject(), "base")

    def test_validation_reussie_pousse_le_journal(self):
        self.write_state(status="pending_validation", last_processed_build=10, consecutive_rollbacks=1,
                         pending={"original_build": 10, "fix_commit_sha": self.base_sha, "trigger_build_seen": 10,
                                  "stage_type": "owasp", "original_findings": ["CVE-2026-1|p"]})
        routes = self.build(11, "SUCCESS")
        routes["/11/api/json?tree=actions"] = {"actions": [{"lastBuiltRevision": {"SHA1": self.base_sha}}]}
        self.run_poll(routes)
        s = self.read_state()
        self.assertEqual((s["status"], s["pending"], s["consecutive_rollbacks"], s["last_processed_build"]),
                         ("idle", None, 0, 11))
        self.assertIn("confirmation automatique du correctif", self.origin_head_subject())

    def test_halte_apres_pushes_no_action(self):
        """Stage OWASP en échec, détection sans finding, 2e push consécutif : halte et notification."""
        self.write_state(last_processed_build=10, consecutive_no_action_pushes=1)
        routes = self.build(11, "FAILURE", stage="OWASP Dependency-Check")
        routes["dependency-check-report.html"] = "<html></html>"
        self.run_poll(routes)
        s = self.read_state()
        self.assertEqual((s["status"], s["consecutive_no_action_pushes"], s["same_cause"]["kind"]),
                         ("halted", 2, "no_action"))
        self.assertIn("halte automatique", self.origin_head_subject())
        with open(self.notify) as fh:
            self.assertIn("Halte", fh.read())


if __name__ == "__main__":
    unittest.main()
