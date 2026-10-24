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


if __name__ == "__main__":
    unittest.main()
