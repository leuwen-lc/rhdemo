"""Rebase automatique des commits du bot sur origin (fixcve-git-sync.sh), dépôts git locaux."""
import json
import os
import subprocess
import tempfile
import unittest

import helpers

LIB = os.path.join(helpers.SCRIPTS, "fixcve-git-sync.sh")
BOT = "RHDemo FixCVE Bot"
BRANCH = "evo"


def git(cwd, *args, author="Humain"):
    env = dict(os.environ, GIT_AUTHOR_NAME=author, GIT_AUTHOR_EMAIL="a@x", GIT_COMMITTER_NAME=author,
               GIT_COMMITTER_EMAIL="a@x")
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def commit_file(cwd, name, content, msg, author="Humain"):
    with open(os.path.join(cwd, name), "w") as f:
        f.write(content)
    git(cwd, "add", name)
    git(cwd, "commit", "-q", "-m", msg, author=author)
    return git(cwd, "rev-parse", "HEAD")


class GitSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.origin, self.clone, self.other = (os.path.join(t, n) for n in ("origin.git", "clone", "other"))
        git(t, "init", "-q", "--bare", "-b", BRANCH, self.origin)
        git(t, "clone", "-q", self.origin, self.clone)
        git(self.clone, "checkout", "-q", "-B", BRANCH)
        commit_file(self.clone, "base.txt", "base", "base")
        git(self.clone, "push", "-q", "origin", BRANCH)
        git(t, "clone", "-q", "-b", BRANCH, self.origin, self.other)
        self.state = os.path.join(t, "state.json")
        self._write_state({"status": "idle", "pending": None})

    def tearDown(self):
        self.tmp.cleanup()

    def _write_state(self, d):
        with open(self.state, "w") as f:
            json.dump(d, f)

    def _run(self):
        script = (f'log() {{ echo "$*" >&2; }}; STATE_FILE={self.state}; '
                  'state_set() { local t; t=$(mktemp); jq "$@" "$STATE_FILE" > "$t" && mv "$t" "$STATE_FILE"; }; '
                  f'. {LIB}; cd {self.clone}; rebase_bot_commits_onto_origin {BRANCH}')
        env = dict(os.environ, GIT_COMMITTER_NAME=BOT, GIT_COMMITTER_EMAIL="b@x")
        return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)

    def _remote_commit(self, name="renovate.txt"):
        commit_file(self.other, name, "x", "chore(deps): renovate", author="Renovate Bot")
        git(self.other, "push", "-q", "origin", BRANCH)
        git(self.clone, "fetch", "-q", "origin")

    def test_commits_du_bot_rejoues_et_poussés(self):
        old = commit_file(self.clone, "fix.txt", "fix", "fix(security): corriger x", author=BOT)
        commit_file(self.clone, "audit.txt", "a", "chore(security): journal", author=BOT)
        self._write_state({"status": "pending_validation", "pending": {"fix_commit_sha": old}})
        self._remote_commit()
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(git(self.clone, "rev-parse", "HEAD"), git(self.origin, "rev-parse", BRANCH))
        self.assertEqual(git(self.clone, "rev-list", "--count", "HEAD"), "4")
        with open(self.state) as f:
            new = json.load(f)["pending"]["fix_commit_sha"]
        self.assertNotEqual(new, old)
        self.assertEqual(git(self.clone, "log", "-1", "--format=%s", new), "fix(security): corriger x")

    def test_commit_humain_local_intouché(self):
        commit_file(self.clone, "mien.txt", "m", "feat: travail en cours")
        head = git(self.clone, "rev-parse", "HEAD")
        self._remote_commit()
        r = self._run()
        self.assertEqual(r.returncode, 1)
        self.assertIn("pas ceux du bot", r.stderr)
        self.assertEqual(git(self.clone, "rev-parse", "HEAD"), head)

    def test_conflit_abandonné_avec_alerte(self):
        commit_file(self.clone, "base.txt", "bot", "fix: bot", author=BOT)
        head = git(self.clone, "rev-parse", "HEAD")
        commit_file(self.other, "base.txt", "autre", "chore: autre", author="Renovate Bot")
        git(self.other, "push", "-q", "origin", BRANCH)
        git(self.clone, "fetch", "-q", "origin")
        r = self._run()
        self.assertEqual(r.returncode, 1)
        self.assertIn("ALERTE", r.stderr)
        self.assertEqual(git(self.clone, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.clone, "status", "--porcelain"), "")


class FixCommitHelpersTest(unittest.TestCase):
    """fix_commit_only_suppressions et revert_fix_commit (fixcve-git-sync.sh), dépôt git local."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "repo")
        git(self.tmp.name, "init", "-q", "-b", BRANCH, self.repo)
        os.makedirs(os.path.join(self.repo, "rhDemo"))
        self.supp = os.path.join("rhDemo", "owasp-suppressions.xml")
        commit_file(self.repo, self.supp, "<s>\n</s>\n", "base", author=BOT)

    def tearDown(self):
        self.tmp.cleanup()

    def _bash(self, call):
        script = f'log() {{ echo "$*" >&2; }}; . {LIB}; cd {self.repo}; {call}'
        env = dict(os.environ, GIT_COMMITTER_NAME=BOT, GIT_COMMITTER_EMAIL="b@x",
                   GIT_AUTHOR_NAME=BOT, GIT_AUTHOR_EMAIL="b@x")
        return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)

    def _commit(self, files, msg="fix"):
        for name, content in files.items():
            path = os.path.join(self.repo, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "-m", msg, author=BOT)
        return git(self.repo, "rev-parse", "HEAD")

    def test_suppression_seule_reconnue(self):
        sha = self._commit({self.supp: "<s>\n<a/>\n</s>\n", "rhDemo/docs/SECURITY_ADVISORIES.md": "x"})
        self.assertEqual(self._bash(f"fix_commit_only_suppressions {sha}").returncode, 0)

    def test_montee_de_version_non_reconnue(self):
        sha = self._commit({self.supp: "<s>\n<a/>\n</s>\n", "rhDemo/pom.xml": "<p/>"})
        self.assertEqual(self._bash(f"fix_commit_only_suppressions {sha}").returncode, 1)

    def test_commit_inconnu_non_reconnu(self):
        self.assertEqual(self._bash("fix_commit_only_suppressions deadbeef").returncode, 1)

    def test_revert_simple_commite(self):
        sha = self._commit({self.supp: "<s>\n<a/>\n</s>\n"})
        self.assertEqual(self._bash(f"revert_fix_commit {sha}").returncode, 0)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.repo, "rev-list", "--count", "HEAD"), "3")

    def test_revert_en_conflit_abandonne_clone_propre(self):
        """Incident #974/#975 : un commit voisin plus récent rend le revert conflictuel."""
        sha = self._commit({self.supp: "<s>\n<a/>\n</s>\n"})
        head = self._commit({self.supp: "<s>\n<a/>\n<b/>\n</s>\n"}, "voisin")
        r = self._bash(f"revert_fix_commit {sha}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ALERTE", r.stderr)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "REVERT_HEAD")))


class EvaluatePartialValidationTest(unittest.TestCase):
    """Verdict de evaluate_partial_validation (fixcve-auto-poll.sh) avec un détecteur factice."""
    POLL = os.path.join(helpers.SCRIPTS, "fixcve-auto-poll.sh")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.repo = os.path.join(t, "repo")
        git(t, "init", "-q", "-b", BRANCH, self.repo)
        os.makedirs(os.path.join(self.repo, "rhDemo"))
        commit_file(self.repo, "rhDemo/owasp-suppressions.xml", "<s/>", "base", author=BOT)
        self.detect = os.path.join(t, "detect.py")
        self.validate = os.path.join(t, "validate.py")
        with open(self.validate, "w") as f:
            f.write("print('{\"ok\": true}')\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _fix(self, files):
        for name in files:
            path = os.path.join(self.repo, name)
            with open(path, "w") as f:
                f.write(name + "x")
            git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "-m", "fix", author=BOT)
        return git(self.repo, "rev-parse", "HEAD")

    def _verdict(self, fix, now_ids, original):
        findings = [{"finding_id": i, "package_name": "p"} for i in now_ids]
        with open(self.detect, "w") as f:
            f.write("import json,sys\n"
                    f"json.dump({{'findings': {findings!r}}}, open(sys.argv[3], 'w'))\n"
                    "print('FIXCVE_DETECT_RESULT: OK', len(sys.argv))\n")
        script = (f'log() {{ :; }}; CYCLE_DIR={self.tmp.name}; CYCLE_PLACEHOLDER=x; DETECT_SCRIPT={self.detect}; '
                  f'VALIDATE_SCRIPT={self.validate}; capture_failure_context() {{ :; }}; '
                  f'. {LIB}; eval "$(sed -n \'/^evaluate_partial_validation() {{/,/^}}/p\' {self.POLL})"; '
                  f'cd {self.repo}; evaluate_partial_validation 975 owasp \'{json.dumps(original)}\' {fix}; '
                  'echo "$PARTIAL_VERDICT|$PARTIAL_REASON|$PARTIAL_NEXT_STAGE"')
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip().splitlines()[-1]

    def test_975_suppression_et_nouvelle_cve_independante_gardee(self):
        fix = self._fix(["rhDemo/owasp-suppressions.xml"])
        self.assertEqual(self._verdict(fix, ["CVE-NEW"], ["CVE-OLD|p"]),
                         "next_stage|correctif_suppression_nouvelle_cve_independante|owasp")

    def test_montee_de_version_et_nouvelle_cve_rollback(self):
        fix = self._fix(["rhDemo/owasp-suppressions.xml", "rhDemo/pom.xml"])
        self.assertEqual(self._verdict(fix, ["CVE-NEW"], ["CVE-OLD|p"]), "rollback|nouvelle_cve_apres_correctif|")

    def test_suppression_inefficace_rollback(self):
        """Un finding du correctif est encore là : la suppression n'a pas fonctionné, pas de passe-droit."""
        fix = self._fix(["rhDemo/owasp-suppressions.xml"])
        self.assertEqual(self._verdict(fix, ["CVE-OLD", "CVE-NEW"], ["CVE-OLD|p"]),
                         "rollback|nouvelle_cve_apres_correctif|")


if __name__ == "__main__":
    unittest.main()
