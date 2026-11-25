"""Opérations git du bot fixcve-auto : commit, push, rejeu sur origin, rollback.

Commandes lancées par liste d'arguments (aucun shell). Le jeton Codeberg n'est jamais un argument :
git le demande à GIT_ASKPASS, script sans secret qui le relit dans l'environnement.
"""
import os
import stat
import subprocess
import tempfile

BOT_NAME = "RHDemo FixCVE Bot"
BOT_EMAIL = "fixcve-bot@leuwen-lc.fr"
AUDIT_LOG_REL = "rhDemo/docs/fixcve-audit.jsonl"
AUDIT_MD_REL = "rhDemo/docs/fixcve-audit.md"
# Fichiers qu'un correctif « suppressions seules » peut toucher : il ne peut introduire aucune CVE.
SUPPRESSION_FILES = {"rhDemo/owasp-suppressions.xml", "rhDemo/.trivyignore.yaml",
                     "rhDemo/docs/SECURITY_ADVISORIES.md", AUDIT_LOG_REL, AUDIT_MD_REL}

_ASKPASS = """#!/bin/sh
case "$1" in
  Username*) printf '%s' "${CODEBERG_USER:?}" ;;
  Password*) printf '%s' "${CODEBERG_TOKEN:?}" ;;
  *) exit 1 ;;
esac
"""


def bot_environment(env, askpass_dir):
    """Environnement git du bot : identité des commits et GIT_ASKPASS (variables plutôt que
    `git config user.*`, sûr même si le dépôt redevenait un jour la copie principale)."""
    path = os.path.join(askpass_dir, "git-askpass.sh")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_ASKPASS)
    os.chmod(path, stat.S_IRWXU)
    out = dict(env)
    out.update(GIT_ASKPASS=path, GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME=BOT_NAME, GIT_AUTHOR_EMAIL=BOT_EMAIL,
               GIT_COMMITTER_NAME=BOT_NAME, GIT_COMMITTER_EMAIL=BOT_EMAIL)
    return out


class GitError(Exception):
    pass


class Git:
    def __init__(self, repo, branch, log, env=None, dry_run=False):
        self.repo = repo
        self.branch = branch
        self.log = log
        self.env = env if env is not None else dict(os.environ)
        self.dry_run = dry_run

    # --- exécution -------------------------------------------------------------------------
    def run(self, *args, check=True, quiet=True):
        """`quiet` : sortie capturée ; sinon elle va dans la console du job (commit, revert)."""
        proc = subprocess.run(["git", *args], cwd=self.repo, env=self.env, text=True,
                              capture_output=quiet, stdout=None if quiet else 2)
        if check and proc.returncode != 0:
            raise GitError(f"git {' '.join(args[:2])} : code {proc.returncode} {(proc.stderr or '').strip()[:500]}")
        return proc

    def ok(self, *args):
        return self.run(*args, check=False).returncode == 0

    def out(self, *args):
        proc = self.run(*args, check=False)
        return proc.stdout.strip() if proc.returncode == 0 else ""

    # --- usage courant ---------------------------------------------------------------------
    def checkout_branch(self):
        """Le checkout Jenkins est détaché : on se place sur origin/<branche> à jour."""
        self.run("fetch", "--quiet", "origin", f"+refs/heads/{self.branch}:refs/remotes/origin/{self.branch}")
        self.run("checkout", "--quiet", "-B", self.branch, f"origin/{self.branch}")

    def head(self, ref="HEAD"):
        return self.out("rev-parse", ref)

    def add(self, *paths, cwd_rel=None):
        if cwd_rel:
            subprocess.run(["git", "add", "--", *paths], cwd=os.path.join(self.repo, cwd_rel), env=self.env,
                           check=True, capture_output=True)
        else:
            self.run("add", "--", *paths)

    def add_audit(self):
        self.add(AUDIT_LOG_REL, AUDIT_MD_REL)

    def commit(self, message):
        self.run("commit", "-m", message, quiet=False)

    def source_sha(self):
        """Dernier commit du code source, hors journal d'audit (commité par le bot lui-même) :
        clé de la mémoire « même cause »."""
        return self.out("log", "-1", "--format=%H", "--", ".", f":!{AUDIT_LOG_REL}", f":!{AUDIT_MD_REL}")

    def discard_unapplied_changes(self):
        """Modifications de remédiation laissées en vain dans l'arbre (ex. package-lock.json d'un
        `npm audit fix` abandonné), sinon l'arbre resterait sale. Journal exclu, commits intacts."""
        self.run("restore", "--staged", "--worktree", "--", ".", f":!{AUDIT_LOG_REL}", f":!{AUDIT_MD_REL}",
                 check=False)

    def is_ancestor(self, ancestor, descendant):
        return bool(ancestor and descendant) and self.ok("merge-base", "--is-ancestor", ancestor, descendant)

    # --- push ------------------------------------------------------------------------------
    def push_raw(self):
        if self.dry_run:
            self.log(f"DRY_RUN : push omis ({self.out('log', '-1', '--format=%h %s')}).")
            return True
        return self.ok("push", "--quiet", "origin", f"HEAD:refs/heads/{self.branch}")

    def push(self):
        """Push des commits du bot. Refusé parce qu'origin a avancé pendant le cycle (merge Renovate,
        push manuel) : commits du bot rejoués sur origin puis repoussés. Échec définitif : GitError,
        le passage s'arrête sans écrire l'état et le suivant recommence (checkout neuf)."""
        if self.push_raw():
            return
        self.log(f"Push refusé : origin/{self.branch} a avancé pendant le cycle — rejeu des commits du bot.")
        self.run("fetch", "--quiet", "origin", f"+refs/heads/{self.branch}:refs/remotes/origin/{self.branch}")
        if not self.rebase_bot_commits_onto_origin():
            raise GitError("push impossible")

    def rebase_bot_commits_onto_origin(self):
        """Rejoue les commits locaux sur origin s'ils sont tous du bot ; sinon (travail humain) ou en
        cas de conflit, ne touche à rien. Le SHA du correctif est relu après le push par l'appelant
        (HEAD~1) : l'ancien poller réécrivait pending.fix_commit_sha, inutile ici (un correctif en
        attente de validation est déjà sur origin et n'est jamais rejoué)."""
        branch = self.branch
        authors = sorted(set(self.out("log", "--format=%an", f"origin/{branch}..HEAD").splitlines()))
        if authors != [BOT_NAME]:
            self.log(f"Branche locale '{branch}' divergente par rapport à origin avec des commits qui ne sont pas "
                     f"ceux du bot ({', '.join(authors)}) — résolution manuelle requise, on ne touche à rien.")
            return False
        if not self.ok("rebase", "--quiet", f"origin/{branch}"):
            self.ok("rebase", "--abort")
            self.log(f"ALERTE : branche '{branch}' divergente et rebase des commits du bot en conflit — commits du "
                     "cycle abandonnés, le passage suivant recommence.")
            return False
        if not self.push_raw():
            self.log("Rebase des commits du bot sur origin réussi mais push refusé — nouvel essai au prochain passage.")
            return False
        self.log(f"Branche locale '{branch}' divergente : commits du bot rejoués sur origin et poussés.")
        return True

    # --- rollback --------------------------------------------------------------------------
    def fix_commit_only_suppressions(self, sha):
        """Le commit ne touche que des suppressions et de la documentation : il ne peut introduire
        aucune CVE. Une CVE NOUVELLE après lui a une cause indépendante (incident #975)."""
        proc = self.run("show", "--no-renames", "--format=", "--name-only", sha, check=False)
        files = [f for f in proc.stdout.splitlines() if f] if proc.returncode == 0 else []
        return bool(files) and all(f in SUPPRESSION_FILES for f in files)

    def revert_fix_commit(self, sha):
        """`git revert` du correctif. Garde-fou : seul un commit du bot présent sur la branche est
        annulé (le SHA vient de l'état persistant). Revert en conflit : abandonné, clone propre
        (incident #974/#975, clone resté en revert inachevé)."""
        author = self.out("log", "-1", "--format=%an", sha)
        if author != BOT_NAME or not self.is_ancestor(sha, "HEAD"):
            self.log(f"ALERTE : revert refusé, {sha} n'est pas un commit du bot présent sur la branche "
                     f"(auteur : {author or 'inconnu'}) — décision humaine requise.")
            return False
        if self.run("revert", "--no-edit", sha, check=False, quiet=False).returncode == 0:
            return True
        self.ok("revert", "--abort")
        self.log(f"ALERTE : revert du correctif {sha} impossible (conflit avec un commit plus récent) — revert "
                 "abandonné, le correctif reste en place, décision humaine requise.")
        return False


def temporary_askpass_dir():
    return tempfile.TemporaryDirectory(prefix="fixcve-askpass-")
