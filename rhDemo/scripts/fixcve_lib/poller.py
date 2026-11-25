"""Poller fixcve-auto : un passage du job Jenkins RHDemo-FixCVE (voir docs/FIXCVE_AUTO.md).

Phase B : validation (ou rollback) d'un correctif poussé au passage précédent. Phase A : détection
d'une nouvelle panne de RHDemo-CI sur Trivy/OWASP, recherche de correctif, classification,
application, vérification locale, puis commit et push.

Ce module n'exécute que les effets (Jenkins, git, journal, étapes). Les décisions de cycle (haltes,
mémoire « même cause », verdict de validation) sont des fonctions pures de cycle.py ; le nouvel état
n'est écrit qu'APRÈS les effets : un push en échec laisse l'état inchangé et le passage suivant
recommence. Les étapes de remédiation sont les scripts fixcve-*.py (ceux du skill /fixcve), lancés
en sous-processus et lus par leur ligne de résultat.

Environnement (posé par Jenkinsfile-FixCVE) :
  FIXCVE_BRANCH          branche suivie (celle que RHDemo-CI construit)
  FIXCVE_STATE_DIR       état persistant (volume rhdemo-fixcve-state de l'agent « fixcve »)
  FIXCVE_JENKINS_URL     API Jenkins (http://jenkins:8080 depuis le réseau des agents)
  JENKINS_USER/TOKEN     compte Jenkins lecture seule (credential fixcve-jenkins-api)
  CODEBERG_USER/TOKEN    bot Codeberg (credential fixcve-forgejo-token), lu par GIT_ASKPASS
  NVD_API_KEY            facultatif : rescan Dependency-Check local, passé à la seule vérification
  FIXCVE_DRY_RUN         true : aucun push (l'appelant travaille alors sur une copie de l'état)
  FIXCVE_EXPECTED_BUILD  build CI qui a déclenché ce passage : attendu comme dernier build terminé
  FIXCVE_REPLAY_BUILD    DRY_RUN seulement : build CI à traiter à la place du dernier build terminé
  FIXCVE_NOTIFY_FILE     lignes à notifier par mail (halte, rollback, blocage, ALERTE)
"""
import datetime
import fcntl
import glob
import json
import os
import shutil
import subprocess
import sys
import time

from . import cycle
from .common import load_json
from .gitops import AUDIT_LOG_REL, AUDIT_MD_REL, BOT_NAME, Git, GitError, bot_environment, temporary_askpass_dir
from .jenkins import Jenkins, JenkinsError, failure_context
from .rules import stage_type

CYCLE_ARCHIVE_RETENTION = 50
EXPECTED_BUILD_POLLS = 24
EXPECTED_BUILD_DELAY_SECONDS = 5
PLACEHOLDER = "{}"


class Abort(Exception):
    """Fin du passage avec ce code retour (1 : nouvel essai au passage suivant, état inchangé)."""

    def __init__(self, code=0):
        super().__init__(code)
        self.code = code


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


def result_line(text, prefix):
    """Dernière occurrence de `prefix` dans la sortie d'une étape, jusqu'à la fin de sa ligne."""
    found = ""
    for line in (text or "").splitlines():
        i = line.find(prefix)
        if i >= 0:
            found = line[i:]
    return found


class Logger:
    """Console du job sur stderr. Toute ligne ALERTE est aussi notifiée par mail."""

    def __init__(self, notify_file):
        self.notify_file = notify_file

    def _append(self, msg):
        if self.notify_file:
            with open(self.notify_file, "a", encoding="utf-8") as fh:
                fh.write(msg + "\n")

    def log(self, msg):
        print(f"[{now_iso()}] {msg}", file=sys.stderr, flush=True)
        if "ALERTE" in msg:
            self._append(msg)

    def notify(self, msg):
        """Événement notifié par mail (build UNSTABLE) : halte, rollback, blocage confirmé."""
        self.log(msg)
        if "ALERTE" not in msg:
            self._append(msg)


class StateStore:
    """state.json sous verrou ; nouvel état calculé par une règle, installé par commit()."""

    def __init__(self, state_dir):
        self.dir = state_dir
        self.path = os.path.join(state_dir, "state.json")
        self.lock_path = os.path.join(state_dir, "poll.lock")
        self._lock_fh = None
        self.next = None

    def ensure(self):
        os.makedirs(self.dir, exist_ok=True)
        if not os.path.exists(self.path):
            self._write(cycle.INITIAL_STATE)

    def lock(self, wait_seconds=0):
        """Verrou exclusif (en plus de disableConcurrentBuilds() du job). False si déjà pris."""
        self._lock_fh = open(self.lock_path, "w")
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                fcntl.flock(self._lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.5)

    def unlock(self):
        if self._lock_fh:
            self._lock_fh.close()
            self._lock_fh = None

    def load(self):
        return load_json(self.path) or {}

    def _write(self, doc):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        os.replace(tmp, self.path)

    def rule(self, fn, *args):
        """Décision d'une règle de cycle.py sur l'état écrit ; l'état n'est pas encore installé."""
        decision = fn(self.load(), *args)
        self.next = decision.pop("state")
        return decision

    def commit(self):
        if self.next is not None:
            self._write(self.next)
            self.next = None


class Poller:
    def __init__(self, env=None):
        self.env = dict(os.environ if env is None else env)
        e = self.env
        scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.repo = e.get("FIXCVE_REPO_DIR") or subprocess.run(
            ["git", "-C", scripts, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
            check=True).stdout.strip()
        self.rhdemo = os.path.join(self.repo, "rhDemo")
        self.scripts = os.path.join(self.rhdemo, "scripts")
        self.branch = e.get("FIXCVE_BRANCH")
        self.state_dir = e.get("FIXCVE_STATE_DIR")
        self.dry_run = e.get("FIXCVE_DRY_RUN", "false") == "true"
        self.expected_build = e.get("FIXCVE_EXPECTED_BUILD", "")
        replay = e.get("FIXCVE_REPLAY_BUILD", "")
        # Rejeu d'un build précis : jamais hors DRY_RUN (pousser un correctif tiré d'un rapport ancien
        # serait dangereux). Vide : dernier build terminé, comportement normal.
        self.replay_build = int(replay) if self.dry_run and replay.isdigit() else None
        self.out = Logger(e.get("FIXCVE_NOTIFY_FILE") or os.devnull)
        self.log = self.out.log
        self.audit_log = os.path.join(self.repo, AUDIT_LOG_REL)
        self.audit_md = os.path.join(self.repo, AUDIT_MD_REL)
        self.cycle_dir = os.path.join(self.rhdemo, ".fixcve-cycle")
        self.files = {k: os.path.join(self.cycle_dir, f"{k}.json")
                      for k in ("detected", "lookup", "plan", "apply-result", "verify")}

    # ============================================================================================
    # Point d'entrée
    # ============================================================================================
    def run(self):
        if not self.branch:
            print("FIXCVE_BRANCH non défini (branche suivie)", file=sys.stderr)
            return 1
        if not self.state_dir:
            print("FIXCVE_STATE_DIR non défini (répertoire persistant du bot)", file=sys.stderr)
            return 1
        self.state = StateStore(self.state_dir)
        self.state.ensure()
        self.archive_dir = os.path.join(self.state_dir, "cycle", "archive")
        os.makedirs(self.archive_dir, exist_ok=True)
        if not self.state.lock():
            self.log("Cycle précédent encore actif, on saute ce passage.")
            return 0
        try:
            return self._run_locked()
        except Abort as a:
            return a.code
        except (GitError, subprocess.CalledProcessError) as e:
            self.log(f"Opération git en échec ({e}) — état inchangé, nouvel essai au prochain passage.")
            return 1
        finally:
            self.state.unlock()

    def _run_locked(self):
        # Halte de sécurité après trop d'échecs consécutifs (rollbacks, échecs pré-push, no action).
        if self.state.load().get("status") == "halted":
            self.log("Automatisation halted (rollbacks ou échecs pré-push répétés) — intervention manuelle requise. "
                     f"Voir {self.state.path} et {self.audit_log}.")
            return 0
        os.makedirs(self.cycle_dir, exist_ok=True)
        for var, credential in (("JENKINS_USER", "fixcve-jenkins-api"), ("JENKINS_TOKEN", "fixcve-jenkins-api"),
                                ("CODEBERG_USER", None), ("CODEBERG_TOKEN", "fixcve-forgejo-token")):
            if not self.env.get(var):
                self.log(f"{var} non défini" + (f" (credential {credential})" if credential else ""))
                return 1
        # Clé NVD (optionnelle) : réservée au sous-processus de vérification.
        self.nvd_key = self.env.pop("NVD_API_KEY", "")
        self.env["FIXCVE_JENKINS_URL"] = self.env.get("FIXCVE_JENKINS_URL") or "http://jenkins:8080"
        self.jenkins = Jenkins(self.env["FIXCVE_JENKINS_URL"], self.env["JENKINS_USER"], self.env["JENKINS_TOKEN"])
        with temporary_askpass_dir() as askpass_dir:
            self.env = bot_environment(self.env, askpass_dir)
            self.git = Git(self.repo, self.branch, self.log, env=self.env, dry_run=self.dry_run)
            self.git.checkout_branch()
            self._wait_expected_build()
            if self.state.load().get("status") == "pending_validation" and self.replay_build is None:
                self.phase_b()
            else:
                self.phase_a()
        return 0

    # ============================================================================================
    # Outils
    # ============================================================================================
    def fetch_json(self, path):
        """Appel Jenkins en échec : visible dans la console (jamais un arrêt silencieux, constaté le
        2026-07-29) ; un 401/403 (jeton invalide ou révoqué) est notifié."""
        url = self.jenkins.job_url(path)
        try:
            return self.jenkins.json(url)
        except JenkinsError as e:
            self.log(f"Échec de l'appel Jenkins ({url}) — HTTP {e.code or '000'} — abandon de ce cycle, nouvelle "
                     "tentative au prochain passage.")
            if e.code in (401, 403):
                self.log(f"ALERTE : jeton Jenkins rejeté (HTTP {e.code}) : le régénérer et mettre à jour "
                         "kv/jenkins/fixcve-jenkins-api (voir rhDemo/docs/FIXCVE_AUTO.md).")
            raise Abort(1) from None

    def _wait_expected_build(self):
        """Jenkins lance ce job depuis le post { always } du build CI, donc juste avant qu'il soit
        marqué terminé : on attend (2 min au plus) qu'il soit le dernier build terminé."""
        if not self.expected_build.isdigit():
            return
        for _ in range(EXPECTED_BUILD_POLLS):
            if self.fetch_json("lastCompletedBuild/api/json?tree=number")["number"] >= int(self.expected_build):
                return
            time.sleep(EXPECTED_BUILD_DELAY_SECONDS)

    def audit(self, event):
        """Événement du journal (append-only, source de vérité) et régénération de la vue lisible."""
        self.append_audit([event])

    def append_audit(self, events):
        with open(self.audit_log, "a", encoding="utf-8") as fh:
            for event in events:
                fh.write(compact(event) + "\n")
        subprocess.run([os.path.join(self.scripts, "fixcve-audit-render.sh"), self.audit_log, self.audit_md],
                       check=True, env=self.env)

    def commit_audit_and_push(self, message):
        self.git.add_audit()
        self.git.commit(message)
        self.git.push()

    def step(self, script, *args, cwd=None, env=None, isolated=True):
        """Étape fixcve-*.py -> (code retour, sortie standard et erreur mêlées)."""
        cmd = ["python3"] + (["-I"] if isolated else []) + [os.path.join(self.scripts, script), *map(str, args)]
        proc = subprocess.run(cmd, cwd=cwd or self.rhdemo, env=env or self.env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
        return proc.returncode, proc.stdout

    def detect(self, build, stage, out):
        # Lancé depuis la racine du dépôt, sans -I (comme l'ancien poller).
        return self.step("fixcve-detect.py", build, stage, out, cwd=self.repo, isolated=False)

    def validate(self, *args):
        code, text = self.step("fixcve-validate-json.py", *args, cwd=self.repo)
        try:
            return json.loads(text.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"ok": False, "reason": "validateur illisible"}

    def log_info_lines(self, label, text):
        for line in text.splitlines():
            if line.startswith("info: "):
                self.log(f"{label} {line}")

    def archive(self, src, build, label):
        """Fichiers de cycle conservés pour le post-mortem, purge par ancienneté."""
        if not os.path.isfile(src):
            return
        shutil.copy(src, os.path.join(self.archive_dir, f"{build}-{label}.json"))
        files = sorted(glob.glob(os.path.join(self.archive_dir, "*.json")), key=os.path.getmtime, reverse=True)
        for old in files[CYCLE_ARCHIVE_RETENTION:]:
            os.remove(old)

    def halt_journal(self, decision, event, message):
        self.out.notify(decision["notify"])
        self.audit(event)
        self.commit_audit_and_push(message)

    # ============================================================================================
    # Phase B — validation d'un correctif précédemment poussé
    # ============================================================================================
    def phase_b(self):
        pending = self.state.load().get("pending") or {}
        fix = pending.get("fix_commit_sha") or ""
        original_build = pending.get("original_build")
        last = self.fetch_json("lastCompletedBuild/api/json?tree=number,result")
        build, result = last["number"], last["result"]
        if build <= (pending.get("trigger_build_seen") or 0):
            self.log(f"En attente du build déclenché par le correctif {fix} (dernier build vu : #{build}).")
            return
        # Le build suivant par NUMÉRO n'est pas forcément celui bâti sur le correctif : un push sans
        # rapport intercalé (doc, Renovate) déclenche aussi un build. On ne valide (ni n'annule) que si
        # le correctif est un ancêtre du commit réellement bâti (incident #749/#750).
        actions = self.fetch_json(f"{build}/api/json?tree=actions[lastBuiltRevision[SHA1]]").get("actions") or []
        built = next((a["lastBuiltRevision"]["SHA1"] for a in actions
                      if isinstance(a, dict) and (a.get("lastBuiltRevision") or {}).get("SHA1")), "")
        if not built or not self.git.is_ancestor(fix, built):
            self.log(f"Build #{build} (sha {built or 'inconnu'}) sans rapport avec le correctif {fix} (push intercalé) "
                     "— pas de validation ni rollback, on continue d'attendre le vrai build.")
            return

        def end(verdict):
            self.state.rule(cycle.on_validation, build, verdict, self.git.source_sha(), time.time())
            self.state.commit()

        if result == "SUCCESS":
            self.log(f"Build #{build} OK — correctif {fix} validé.")
            self.audit({"timestamp": now_iso(), "event": "validation_success", "commit": fix,
                        "jenkins_build": build, "result": "resolved"})
            self.commit_audit_and_push(f"chore(security): confirmation automatique du correctif CVE (build #{build})")
            end("success")
            return

        # Build encore rouge : avant de conclure à une régression, vérifier que le rouge ne vient pas
        # de findings que ce correctif ne traitait pas.
        stage = pending.get("stage_type") or ""
        original = pending.get("original_findings")
        partial = {"verdict": "rollback", "reason": "etat_pending_sans_findings_d_origine", "removed": [],
                   "remaining": [], "next_stage": ""}
        if stage and original not in (None, False):
            partial = self.partial_validation(build, stage, original, fix)
        reason = partial["reason"]

        if partial["verdict"] == "next_stage":
            nxt = partial["next_stage"]
            self.log(f"Build #{build} : le stage {stage} est propre, correctif {fix} validé ({reason}). L'échec est sur "
                     f"le stage {nxt}, à traiter comme une nouvelle panne au prochain cycle. Pas de rollback.")
            self.audit({"timestamp": now_iso(), "event": "validation_stage_cleared", "commit": fix,
                        "jenkins_build": build, "original_build": original_build, "stage_cleared": stage,
                        "next_failing_stage": nxt, "removed": partial["removed"],
                        "result": "kept_next_stage_pending"})
            self.commit_audit_and_push(f"chore(security): journal fixcve-auto - correctif {fix[:12]} validé sur {stage}, "
                                       f"échec suivant sur {nxt} ({reason}, build #{build})")
            end("next_stage")
            return

        if partial["verdict"] == "keep":
            self.log(f"Build #{build} encore en échec ({result}) mais correctif {fix} validé partiellement ({reason}) — "
                     f"disparus : {compact(partial['removed'])} ; restants (bloqués) : {compact(partial['remaining'])}. "
                     "Pas de rollback.")
            self.audit({"timestamp": now_iso(), "event": "validation_partial", "commit": fix, "jenkins_build": build,
                        "original_build": original_build, "removed": partial["removed"],
                        "remaining": partial["remaining"], "result": "kept_partial"})
            self.commit_audit_and_push(f"chore(security): journal fixcve-auto - validation partielle du correctif "
                                       f"{fix[:12]} (build #{build})")
            end("keep")
            return

        self.log(f"Build #{build} en échec ({result}) après le correctif {fix} ({reason}) — rollback automatique.")
        # Cause réelle capturée avant le rollback (#760/#762, #819). Best-effort.
        failing_stage, detail = self.failure_context(build)
        if not self.git.revert_fix_commit(fix):
            # Correctif gardé, attente humaine (anti-boucle d'un blocage confirmé).
            self.audit({"timestamp": now_iso(), "event": "rollback_conflict", "commit": fix, "jenkins_build": build,
                        "original_build": original_build, "failure_stage": failing_stage, "failure_detail": detail,
                        "partial_check": reason, "outcome_code": "bad_fix", "result": "manual_review_required"})
            self.git.add_audit()
            self.out.notify(f"Rollback impossible du correctif {fix[:12]} (build #{build}) : correctif conservé, "
                            "décision humaine requise.")
            self.git.commit(f"chore(security): journal fixcve-auto - rollback impossible, correctif {fix[:12]} "
                            f"conservé (build #{build})")
            self.git.push()
            end("rollback_conflict")
            return
        self.audit({"timestamp": now_iso(), "event": "validation_failed_rollback", "commit": fix,
                    "revert_commit": self.git.head(), "jenkins_build": build, "original_build": original_build,
                    "failure_stage": failing_stage, "failure_detail": detail, "partial_check": reason,
                    "result": "rolled_back"})
        self.git.add_audit()
        self.out.notify(f"Rollback du correctif {fix[:12]} : build #{build} en échec sur {failing_stage} ({reason}).")
        self.git.commit(f"chore(security): journal fixcve-auto - rollback build #{build} (correctif {fix})")
        self.git.push()
        decision = self.state.rule(cycle.on_validation, build, "rollback", self.git.source_sha(), time.time())
        if decision["halt"]:
            self.halt_journal(decision, {"timestamp": now_iso(), "event": "automation_halted",
                                         "original_build": original_build, "reason": "max_consecutive_rollbacks",
                                         "result": "manual_review_required"},
                              f"chore(security): halte automatique fixcve-auto après rollbacks répétés "
                              f"(build #{original_build})")
        self.state.commit()

    def failure_context(self, build):
        try:
            wf = json.loads(self.jenkins.text_or_empty(self.jenkins.job_url(f"{build}/wfapi/describe")) or "null")
        except ValueError:
            wf = None
        return failure_context(wf, self.jenkins.text_or_empty(self.jenkins.job_url(f"{build}/consoleText")))

    def partial_validation(self, build, stage, original, fix):
        """Validation par NON-RÉGRESSION : rapport du build relu et comparé aux findings d'origine.
        Verdict (keep | next_stage | rollback) : cycle.partial_verdict. Tout doute => rollback."""
        out = os.path.join(self.cycle_dir, "validation-detected.json")
        with open(out, "w") as fh:
            fh.write(PLACEHOLDER)
        detect, current, only_supp = "error", [], False
        failing_stage, detail = "inconnu", "non disponible"
        code, text = self.detect(build, stage, out)
        if code == 0:
            line = result_line(text, "FIXCVE_DETECT_RESULT:")
            if line.startswith("FIXCVE_DETECT_RESULT: OK"):
                if self.validate("--schema", "detect", out).get("ok"):
                    detect = "ok"
                    current = [f["finding_id"] + "|" + f["package_name"] for f in (load_json(out) or {})["findings"]]
                    only_supp = bool(fix) and self.git.fix_commit_only_suppressions(fix)
                else:
                    detect = "invalid"
            else:
                prefix = "FIXCVE_DETECT_RESULT: NO_ACTION "
                detect = "no_action:" + (line[len(prefix):] if line.startswith(prefix) else line)
                # Stage d'origine propre : le stage réellement en échec et son extrait décident.
                failing_stage, detail = self.failure_context(build)
        try:
            verdict, reason, removed, remaining, nxt = cycle.partial_verdict(
                stage, original, detect, current, failing_stage, detail, only_supp)
        except Exception:  # noqa: BLE001 — tout doute => rollback
            return {"verdict": "rollback", "reason": "comparaison_impossible", "removed": [], "remaining": [],
                    "next_stage": ""}
        return {"verdict": verdict, "reason": reason, "removed": removed, "remaining": remaining,
                "next_stage": nxt or ""}

    # ============================================================================================
    # Phase A — détection d'une nouvelle panne CI
    # ============================================================================================
    def phase_a(self):
        if self.replay_build is not None:
            self.log(f"DRY_RUN : rejeu du build #{self.replay_build} (rapport ancien, code actuel) à la place du "
                     "dernier build terminé.")
            try:
                last = self.jenkins.json(self.jenkins.job_url(f"{self.replay_build}/api/json?tree=number,result"))
            except JenkinsError as e:
                if e.code != 404:
                    raise
                # Un rejeu sur un build supprimé ne réussira jamais : pas de « nouvelle tentative ».
                self.log(f"Build #{self.replay_build} absent de l'historique Jenkins (rétention des 30 derniers "
                         "builds, buildDiscarder de Jenkinsfile-CI) : rejeu impossible, choisir un build conservé.")
                raise Abort(1) from None
        else:
            last = self.fetch_json("lastCompletedBuild/api/json?tree=number,result")
        build, result = last["number"], last["result"]
        self.build_num = build
        if build <= (self.state.load().get("last_processed_build") or 0):
            self.log(f"Rien de nouveau (dernier build #{build}, déjà traité).")
            return
        if result != "FAILURE":
            self.log(f"Build #{build} : {result}, rien à faire.")
            # Build repassé au vert : la cause « no action » mémorisée n'est plus d'actualité.
            self.state.rule(cycle.on_build_not_failed, build)
            self.state.commit()
            return

        # Stage en échec : seul le PREMIER stage non SUCCESS (ordre d'exécution) est la cause racine,
        # les suivants sont en cascade (un Trivy jamais atteint contient « Trivy » dans son nom).
        stages = (self.fetch_json(f"{build}/wfapi/describe").get("stages") or [])
        failed = [f"{s.get('name', '')} :: {(s.get('error') or {}).get('message', '')}"
                  for s in stages if s.get("status") != "SUCCESS"]
        root = failed[0] if failed else ""
        self.stage = stage = stage_type(root)
        if not stage:
            # Hors périmètre (Selenium, infra) : jamais journalisé en git, sinon chaque push relance un
            # build qui échoue pareil (boucles #772/#774, #796/#797).
            self.log(f"Build #{build} en échec, cause hors périmètre fixcve-auto (stage racine : {root}) — non tracé "
                     f"en git. Tous les stages en échec : {chr(10).join(failed)}")
            self.state.rule(cycle.on_out_of_scope, build)
            self.state.commit()
            return

        # Anti-boucle : blocage déjà confirmé sur ce même code source (#735-#744).
        decision = self.state.rule(cycle.check_same_cause, build, self.git.source_sha(), time.time())
        if decision["skip"]:
            self.log(f"Build #{build} en échec sur {stage} — blocage déjà constaté depuis {decision['since']} sur le "
                     f"même code, prochaine revérification dans {decision['minutes_left']} min. Cycle ignoré : aucun "
                     "commit, aucun push.")
            self.state.commit()
            return
        if decision.get("log"):
            self.log(decision["log"])

        # Fichier resté à `{}` (étape qui n'a rien écrit) : rejeté par le validateur de schéma.
        for path in self.files.values():
            with open(path, "w") as fh:
                fh.write(PLACEHOLDER)
        self.log(f"Build #{build} en échec sur {stage} — détection.")
        self.detection()
        self.resolve_and_classify()
        self.apply_and_verify()

    # --- Étape 1 : détection ----------------------------------------------------------------
    def detection(self):
        build, stage, detected = self.build_num, self.stage, self.files["detected"]
        code, text = self.detect(build, stage, detected)
        if code != 0:
            self.log(f"fixcve-detect.py a échoué (crash/erreur, ex. Jenkins injoignable) pour le build #{build} — "
                     f"abandon de ce cycle, nouvelle tentative au prochain passage. Détail : {text.strip()}")
            raise Abort(1)
        line = result_line(text, "FIXCVE_DETECT_RESULT:")
        if not line:
            self.log("La phase détection n'a pas produit de ligne FIXCVE_DETECT_RESULT — traité comme échec pré-push.")
            self.audit({"timestamp": now_iso(), "event": "detect_phase_failed", "jenkins_build": build, "stage": stage,
                        "reason": "no_result_line", "result": "manual_review_required"})
            self.commit_audit_and_push(f"chore(security): journal fixcve-auto - build #{build} détection sans résultat "
                                       "exploitable")
            self.prepush_failure_and_maybe_halt("detect")
        if line.startswith("FIXCVE_DETECT_RESULT: NO_ACTION"):
            self.detect_no_action(line[len("FIXCVE_DETECT_RESULT: NO_ACTION "):])
        validation = self.validate("--schema", "detect", detected)
        if not validation.get("ok"):
            detail = validation.get("detail") or validation.get("reason") or "validateur illisible"
            self.log(f"detected.json rejeté par le validateur de schéma : {detail}")
            self.archive(detected, build, "detected-invalid")
            self.audit({"timestamp": now_iso(), "event": "detect_phase_failed", "jenkins_build": build, "stage": stage,
                        "reason": "schema_invalid", "detail": detail, "result": "manual_review_required"})
            self.commit_audit_and_push(f"chore(security): journal fixcve-auto - build #{build} detected.json invalide")
            self.prepush_failure_and_maybe_halt("detect")
        self.log(f"Détection OK ({validation.get('count')} finding(s)) — recherche de correctif.")

    def detect_no_action(self, reason):
        """Stage en périmètre mais rien d'exploitable : notifié une fois par code source (#799-#802)."""
        build = self.build_num
        self.log(f"Phase détection : aucune action pour le build #{build} ({reason}).")
        decision = self.state.rule(cycle.on_detect_no_action, build, self.git.source_sha(), time.time())
        if not decision["push_journal"]:
            self.log("Même cause \"no action\" déjà notifiée sur ce code source — pas de nouveau commit/push, on avance "
                     "juste last_processed_build.")
            self.state.commit()
            raise Abort(0)
        self.audit({"timestamp": now_iso(), "event": "skipped_infra_failure", "jenkins_build": build,
                    "stage": self.stage, "reason": reason, "result": "no_action"})
        self.commit_audit_and_push(f"chore(security): journal fixcve-auto - build #{build} détection sans CVE "
                                   f"exploitable ({reason})")
        if decision["halt"]:
            self.halt_journal(decision, {"timestamp": now_iso(), "event": "automation_halted", "jenkins_build": build,
                                         "reason": "max_consecutive_no_action_pushes",
                                         "result": "manual_review_required"},
                              f"chore(security): halte automatique fixcve-auto après boucle no_action (build #{build})")
        self.state.commit()
        raise Abort(0)

    def prepush_failure_and_maybe_halt(self, step):
        """Échec avant tout push de correctif : halte au-delà de MAX_CONSECUTIVE_PREPUSH_FAILURES."""
        build = self.build_num
        decision = self.state.rule(cycle.on_prepush_failure, build, step)
        if decision["halt"]:
            self.halt_journal(decision, {"timestamp": now_iso(), "event": "automation_halted", "jenkins_build": build,
                                         "reason": "max_consecutive_prepush_failures", "failing_stage": step,
                                         "result": "manual_review_required"},
                              f"chore(security): halte automatique fixcve-auto après échecs pré-push répétés "
                              f"(build #{build})")
        self.state.commit()
        raise Abort(0)

    def prepush_failure(self, step, reason, detail, code):
        """Échec d'une étape avant tout push de correctif : journal commité, compteur pré-push."""
        build = self.build_num
        self.log(f"Étape {step} en échec pour le build #{build} ({reason}) : {detail}")
        self.git.discard_unapplied_changes()
        self.audit({"timestamp": now_iso(), "event": "cycle_failed", "jenkins_build": build, "stage": self.stage,
                    "step": step, "reason": reason, "detail": detail[:1000], "outcome_code": code,
                    "result": "manual_review_required"})
        self.commit_audit_and_push(f"chore(security): journal fixcve-auto - build #{build} étape {step} en échec "
                                   f"({reason})")
        self.prepush_failure_and_maybe_halt(step)

    # --- Étapes 2 et 3 : recherche de correctif et classification -------------------------------
    def resolve_and_classify(self):
        build, f = self.build_num, self.files
        if not os.access(os.path.join(self.rhdemo, "frontend", "node", "npm"), os.X_OK):
            # npm du frontend (npm audit) : absent d'un checkout neuf, installé par Maven (cache ~/.m2).
            self.log("Installation de node/npm du frontend (mvnw generate-resources).")
            subprocess.run(["./mvnw", "-q", "-B", "generate-resources"], cwd=self.rhdemo, env=self.env,
                           stdout=sys.stderr, check=True)
        code, text = self.step("fixcve-resolve.py", f["detected"], f["lookup"])
        if code != 0:
            # Crash (réseau coupé, exception) : l'état n'avance pas, nouvel essai au prochain passage.
            tail = " ".join(text.strip().splitlines()[-5:])
            self.log(f"fixcve-resolve.py a échoué pour le build #{build} — nouvel essai au prochain passage. "
                     f"Détail : {tail}")
            raise Abort(1)
        self.log_info_lines("resolve", text)
        line = result_line(text, "FIXCVE_RESOLVE_RESULT:")
        if not line.startswith("FIXCVE_RESOLVE_RESULT: OK"):
            self.prepush_failure("resolve", "no_result_line", line or "aucune ligne de résultat", "tooling")
        validation = self.validate("--schema", "lookup", "--cross-ref", f["detected"], f["lookup"])
        if not validation.get("ok"):
            self.archive(f["detected"], build, "detected")
            self.archive(f["lookup"], build, "lookup-invalid")
            self.prepush_failure("resolve", "schema_invalid", validation.get("detail") or validation.get("reason") or "",
                                 "tooling")
        self.log(f"Recherche de correctif : {line[len('FIXCVE_RESOLVE_RESULT: '):]}")

        _, text = self.step("fixcve-classify.py", f["detected"], f["lookup"], f["plan"])
        line = result_line(text, "FIXCVE_CLASSIFY_RESULT:")
        validation = self.validate("--schema", "plan", "--cross-ref", f["detected"], f["plan"])
        if not line.startswith("FIXCVE_CLASSIFY_RESULT: OK") or not validation.get("ok"):
            self.prepush_failure("classify", "plan_invalide", f"{line or 'aucune ligne'} {validation.get('detail') or ''}",
                                 "tooling")
        self.log(f"Plan : {line[len('FIXCVE_CLASSIFY_RESULT: '):]}")
        for key, label in (("detected", "detected"), ("lookup", "lookup"), ("plan", "plan")):
            self.archive(f[key], build, label)

    # --- Étapes 5 et 6 : application puis vérification locale ------------------------------------
    def apply_and_verify(self):
        """Une montée qui échoue à la vérification bascule (une seule fois) dans la branche « sans
        correctif » de la politique et le plan est réappliqué ; des CVE nouvelles au rescan local sont
        ajoutées au cycle une fois (#1102) ; toute autre erreur annule le cycle."""
        build, f = self.build_num, self.files
        downgrade, line, new_round = "", "", False
        verify_env = dict(self.env, NVD_API_KEY=self.nvd_key)
        for attempt in (1, 2, 3):
            _, text = self.step("fixcve-apply.py", f["plan"], f["apply-result"], "--downgrade", downgrade)
            self.log_info_lines("apply", text)
            line = result_line(text, "FIXCVE_APPLY_RESULT:")
            if not (line.startswith("FIXCVE_APPLY_RESULT: APPLIED") or line.startswith("FIXCVE_APPLY_RESULT: NO_ACTION")):
                self.prepush_failure("apply", "no_result_line", line or " ".join(text.strip().splitlines()[-3:]),
                                     "tooling")
            if not line.startswith("FIXCVE_APPLY_RESULT: APPLIED"):
                break
            _, vtext = self.step("fixcve-verify.py", f["apply-result"], f["detected"], self.stage, f["verify"],
                                 env=verify_env)
            vline = result_line(vtext, "FIXCVE_VERIFY_RESULT:")
            self.log(f"Vérification locale (essai {attempt}) : {vline or 'aucune ligne'}")
            if vline.startswith("FIXCVE_VERIFY_RESULT: OK"):
                break
            report = load_json(f["verify"])
            # Rapport illisible : compté comme une erreur (jamais de nouvel essai sur un doute).
            errors = len(report.get("errors") or []) if isinstance(report, dict) else 1
            report = report if isinstance(report, dict) else {}
            failed = ",".join(report.get("failed_upgrades") or [])
            new = report.get("new_findings") or []
            self.git.discard_unapplied_changes()
            if new and errors == 0 and not failed and not new_round and attempt < 3:
                new_round = True
                names = ", ".join(f"{n['finding_id']} {n['package_name']}@{n['installed_version']}" for n in new)
                self.log(f"CVE nouvelles au rescan local ({names}) — ajoutées au cycle et retraitées.")
                detected = load_json(f["detected"])
                detected["findings"] += new
                with open(f["detected"], "w", encoding="utf-8") as fh:
                    json.dump(detected, fh, ensure_ascii=False)
                if not self.validate("--schema", "detect", f["detected"]).get("ok"):
                    self.prepush_failure("verify", "nouvelles_cve_schema_invalide", compact(new)[:500], "tooling")
                self.resolve_and_classify()
                continue
            if attempt < 3 and failed and errors == 0 and not downgrade:
                self.log(f"Montées non confirmées par la vérification ({failed}) — bascule en « sans correctif » et "
                         "nouvel essai.")
                downgrade = failed
                continue
            detail = " ".join(l for l in vtext.splitlines() if l.startswith("erreur: ") or "FIXCVE_VERIFY_RESULT" in l)
            self.prepush_failure("verify", "verification_locale_en_echec", detail + " ", "bad_fix")
        self.archive(f["apply-result"], build, "apply")
        result = load_json(f["apply-result"]) or {}
        if line.startswith("FIXCVE_APPLY_RESULT: APPLIED"):
            self.push_fix(result)
        else:
            self.no_change(line[len("FIXCVE_APPLY_RESULT: NO_ACTION "):], result)

    def push_fix(self, result):
        """Deux commits : le correctif seul (c'est lui qu'un rollback annule), puis le journal
        (append-only, jamais annulé)."""
        build = self.build_num
        self.git.add(*result["changed_files"], cwd_rel="rhDemo")
        self.git.commit(result["commit_message"])
        fix = self.git.head()
        events = result.get("events") or []
        incomplete = (load_json(self.files["verify"]) or {}).get("incomplete") or []
        if incomplete:
            events = events + [{"timestamp": now_iso(), "event": "local_validation_incomplete", "jenkins_build": build,
                                "stage": self.stage, "missing": incomplete, "result": "validation_par_le_build_ci"}]
        self.append_audit(events)
        self.commit_audit_and_push(f"chore(security): journal fixcve-auto - build #{build} (correctif {fix[:12]})")
        # Le correctif est le parent du commit de journal ; un rejeu sur origin au push a pu changer son SHA.
        fix = self.git.head("HEAD~1")
        if self.dry_run:
            self.log(f"DRY_RUN : correctif appliqué et vérifié localement (commit {fix}), push omis.")
        else:
            self.log(f"Correctif appliqué, vérifié et poussé (commit {fix}) — attente de validation CI.")
        original = [x["finding_id"] + "|" + x["package_name"] for x in load_json(self.files["detected"])["findings"]]
        self.state.rule(cycle.on_fix_pushed, build, fix, self.stage, original)
        self.state.commit()

    def no_change(self, reason, result):
        """Aucun fichier modifié : findings bloqués, recherche en panne, ou déjà corrigé."""
        build = self.build_num
        decision = self.state.rule(cycle.on_apply_no_change, build, reason, self.git.source_sha(), time.time())
        if decision.get("log"):
            self.log(decision["log"])
        if reason == "cve_bloquante_sans_upgrade_disponible":
            # Échec conforme : journalisé une fois, puis silence 48 h sur ce même code source.
            self.out.notify(decision["notify"])
            self.append_audit(result.get("events") or [])
            self.commit_audit_and_push(f"chore(security): journal fixcve-auto - build #{build} findings bloqués sans "
                                       "correctif")
        elif reason == "transient":
            # Recherche en panne : nouvel essai dans 1 h sans journal ; au dernier essai, journalisé une fois.
            if decision["push_journal"]:
                self.append_audit(result.get("events") or [])
                self.commit_audit_and_push(f"chore(security): journal fixcve-auto - build #{build} recherche de "
                                           "correctif en panne")
        else:
            # deja_corrige_sur_head / rien_a_appliquer : un push relancerait un build inutile.
            self.log(f"Build #{build} : aucune action ({reason}).")
        self.state.commit()


__all__ = ["Abort", "BOT_NAME", "Logger", "Poller", "StateStore", "result_line"]
