"""fixcve_lib/gitops.py : rejeu des commits du bot sur origin, rollback, dépôts git locaux.
(Anciens tests de fixcve-git-sync.sh, portés sur le module Python.)"""
import os
import subprocess
import tempfile
import unittest

import helpers  # noqa: F401  (chemin de fixcve_lib)
from fixcve_lib.gitops import BOT_NAME as BOT, Git

BRANCH = "evo"


def git(cwd, *args, author="Humain"):
    env = dict(os.environ, GIT_AUTHOR_NAME=author, GIT_AUTHOR_EMAIL="a@x", GIT_COMMITTER_NAME=author,
               GIT_COMMITTER_EMAIL="a@x", GIT_CONFIG_GLOBAL="/dev/null")
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def commit_file(cwd, name, content, msg, author="Humain"):
    path = os.path.join(cwd, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    git(cwd, "add", name)
    git(cwd, "commit", "-q", "-m", msg, author=author)
    return git(cwd, "rev-parse", "HEAD")


def bot_git(repo, logs, dry_run=False):
    env = dict(os.environ, GIT_COMMITTER_NAME=BOT, GIT_COMMITTER_EMAIL="b@x", GIT_AUTHOR_NAME=BOT,
               GIT_AUTHOR_EMAIL="b@x", GIT_CONFIG_GLOBAL="/dev/null")
    return Git(repo, BRANCH, logs.append, env=env, dry_run=dry_run)


class GitSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = self.tmp.name
        self.origin, self.clone, self.other = (os.path.join(t, n) for n in ("origin.git", "clone", "other"))
        git(t, "init", "-q", "--bare", "-b", BRANCH, self.origin)
        git(t, "clone", "-q", self.origin, self.clone)
        git(self.clone, "checkout", "-q", "-B", BRANCH)
        commit_file(self.clone, "base.txt", "base", "base")
        git(self.clone, "push", "-q", "origin", BRANCH)
        git(t, "clone", "-q", "-b", BRANCH, self.origin, self.other)
        self.logs = []
        self.git = bot_git(self.clone, self.logs)

    def _remote_commit(self, name="renovate.txt"):
        commit_file(self.other, name, "x", "chore(deps): renovate", author="Renovate Bot")
        git(self.other, "push", "-q", "origin", BRANCH)

    def test_commits_du_bot_rejoues_et_pousses(self):
        commit_file(self.clone, "fix.txt", "fix", "fix(security): corriger x", author=BOT)
        commit_file(self.clone, "audit.txt", "a", "chore(security): journal", author=BOT)
        self._remote_commit()
        self.git.push()
        self.assertEqual(git(self.clone, "rev-parse", "HEAD"), git(self.origin, "rev-parse", BRANCH))
        self.assertEqual(git(self.clone, "rev-list", "--count", "HEAD"), "4")
        self.assertEqual(git(self.clone, "log", "-1", "--format=%s", "HEAD~1"), "fix(security): corriger x")
        self.assertTrue(any("rejeu des commits du bot" in m for m in self.logs))

    def test_commit_humain_local_intouche(self):
        commit_file(self.clone, "mien.txt", "m", "feat: travail en cours")
        head = git(self.clone, "rev-parse", "HEAD")
        self._remote_commit()
        git(self.clone, "fetch", "-q", "origin")
        self.assertFalse(self.git.rebase_bot_commits_onto_origin())
        self.assertIn("pas ceux du bot", self.logs[-1])
        self.assertEqual(git(self.clone, "rev-parse", "HEAD"), head)

    def test_conflit_abandonne_avec_alerte(self):
        commit_file(self.clone, "base.txt", "bot", "fix: bot", author=BOT)
        head = git(self.clone, "rev-parse", "HEAD")
        commit_file(self.other, "base.txt", "autre", "chore: autre", author="Renovate Bot")
        git(self.other, "push", "-q", "origin", BRANCH)
        git(self.clone, "fetch", "-q", "origin")
        self.assertFalse(self.git.rebase_bot_commits_onto_origin())
        self.assertIn("ALERTE", self.logs[-1])
        self.assertEqual(git(self.clone, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.clone, "status", "--porcelain"), "")

    def test_dry_run_rien_pousse(self):
        commit_file(self.clone, "fix.txt", "fix", "fix(security): corriger x", author=BOT)
        bot_git(self.clone, self.logs, dry_run=True).push()
        self.assertEqual(git(self.origin, "log", "-1", "--format=%s", BRANCH), "base")
        self.assertIn("DRY_RUN : push omis", self.logs[-1])


class FixCommitHelpersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = os.path.join(self.tmp.name, "repo")
        git(self.tmp.name, "init", "-q", "-b", BRANCH, self.repo)
        self.supp = os.path.join("rhDemo", "owasp-suppressions.xml")
        commit_file(self.repo, self.supp, "<s>\n</s>\n", "base", author=BOT)
        self.logs = []
        self.git = bot_git(self.repo, self.logs)

    def _commit(self, files, msg="fix"):
        for name, content in files.items():
            commit_file(self.repo, name, content, msg, author=BOT)
        return git(self.repo, "rev-parse", "HEAD")

    def _commit_together(self, files):
        for name, content in files.items():
            path = os.path.join(self.repo, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "-m", "fix", author=BOT)
        return git(self.repo, "rev-parse", "HEAD")

    def test_suppression_seule_reconnue(self):
        sha = self._commit_together({self.supp: "<s>\n<a/>\n</s>\n", "rhDemo/docs/SECURITY_ADVISORIES.md": "x"})
        self.assertTrue(self.git.fix_commit_only_suppressions(sha))

    def test_montee_de_version_non_reconnue(self):
        sha = self._commit_together({self.supp: "<s>\n<a/>\n</s>\n", "rhDemo/pom.xml": "<p/>"})
        self.assertFalse(self.git.fix_commit_only_suppressions(sha))

    def test_commit_inconnu_non_reconnu(self):
        self.assertFalse(self.git.fix_commit_only_suppressions("deadbeef"))

    def test_revert_simple_commite(self):
        sha = self._commit({self.supp: "<s>\n<a/>\n</s>\n"})
        self.assertTrue(self.git.revert_fix_commit(sha))
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.repo, "rev-list", "--count", "HEAD"), "3")

    def test_revert_refuse_commit_humain(self):
        """Garde-fou : un état altéré ne peut pas faire annuler un commit qui n'est pas du bot."""
        sha = commit_file(self.repo, "humain.txt", "h", "fix: correctif humain")
        self.assertFalse(self.git.revert_fix_commit(sha))
        self.assertIn("revert refusé", self.logs[-1])
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), sha)

    def test_revert_refuse_commit_hors_branche(self):
        sha = self._commit({self.supp: "<s>\n<a/>\n</s>\n"})
        git(self.repo, "reset", "-q", "--hard", "HEAD~1")
        self.assertFalse(self.git.revert_fix_commit(sha))
        self.assertIn("revert refusé", self.logs[-1])

    def test_revert_en_conflit_abandonne_clone_propre(self):
        """Incident #974/#975 : un commit voisin plus récent rend le revert conflictuel."""
        sha = self._commit({self.supp: "<s>\n<a/>\n</s>\n"})
        head = self._commit({self.supp: "<s>\n<a/>\n<b/>\n</s>\n"}, "voisin")
        self.assertFalse(self.git.revert_fix_commit(sha))
        self.assertIn("ALERTE", self.logs[-1])
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "REVERT_HEAD")))

    def test_source_sha_ignore_le_journal(self):
        code = git(self.repo, "rev-parse", "HEAD")
        self._commit({"rhDemo/docs/fixcve-audit.jsonl": "{}\n"}, "journal")
        self.assertEqual(self.git.source_sha(), code)


if __name__ == "__main__":
    unittest.main()
