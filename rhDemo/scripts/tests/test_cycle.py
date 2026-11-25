"""Règles de cycle du poller (fixcve_lib/cycle.py), rejouées sur les incidents du registre
docs/FIXCVE_AUTO_INCIDENTS.md, sans Jenkins ni git."""
import json
import os
import subprocess
import tempfile
import unittest

from helpers import SCRIPTS
from fixcve_lib import cycle
from fixcve_lib.rules import (BLOCKED_RECHECK_SECONDS, MAX_CONSECUTIVE_NO_ACTION_PUSHES,
                              MAX_CONSECUTIVE_PREPUSH_FAILURES, MAX_CONSECUTIVE_ROLLBACKS,
                              TRANSIENT_MAX_ATTEMPTS, TRANSIENT_RECHECK_SECONDS)

NOW = 1_800_000_000
ORIG = ["CVE-2026-1|g:a", "CVE-2026-2|g:b"]


def state(**kw):
    return dict(cycle.INITIAL_STATE, **kw)


class SameCauseTest(unittest.TestCase):
    def test_735_blocage_confirme_meme_code_ignore_sans_push(self):
        """Builds #735-#744 : un blocage confirmé ne doit pas repousser une ligne de journal à chaque build."""
        d = cycle.on_apply_no_change(state(), 735, "cve_bloquante_sans_upgrade_disponible", "sha1", NOW)
        self.assertTrue(d["push_journal"])
        s = d["state"]
        d = cycle.check_same_cause(s, 736, "sha1", NOW + 3600)
        self.assertTrue(d["skip"])
        self.assertEqual(d["state"]["last_processed_build"], 736)

    def test_blocage_revérifie_apres_48h_ou_code_change(self):
        s = cycle.on_apply_no_change(state(), 735, "cve_bloquante_sans_upgrade_disponible", "sha1", NOW)["state"]
        self.assertFalse(cycle.check_same_cause(s, 736, "sha1", NOW + BLOCKED_RECHECK_SECONDS)["skip"])
        self.assertFalse(cycle.check_same_cause(s, 736, "sha2", NOW + 60)["skip"])

    def test_transitoire_borne_puis_48h(self):
        """Recherche en panne : 1 h entre essais, journal versionné seulement au dernier essai."""
        s = state()
        for attempt in range(1, TRANSIENT_MAX_ATTEMPTS + 1):
            d = cycle.on_apply_no_change(s, 900, "transient", "sha1", NOW)
            s = d["state"]
            self.assertEqual(s["last_processed_build"], 899, "le même build est repris")
            self.assertEqual(s["same_cause"]["attempts"], attempt)
            self.assertEqual(d["push_journal"], attempt == TRANSIENT_MAX_ATTEMPTS)
        self.assertEqual(s["same_cause"]["recheck_seconds"], BLOCKED_RECHECK_SECONDS)
        self.assertTrue(cycle.check_same_cause(s, 900, "sha1", NOW + TRANSIENT_RECHECK_SECONDS)["skip"])

    def test_transitoire_reessaye_apres_1h(self):
        s = cycle.on_apply_no_change(state(), 900, "transient", "sha1", NOW)["state"]
        self.assertTrue(cycle.check_same_cause(s, 900, "sha1", NOW + 60)["skip"])
        self.assertFalse(cycle.check_same_cause(s, 900, "sha1", NOW + TRANSIENT_RECHECK_SECONDS)["skip"])

    def test_deja_corrige_leve_le_blocage(self):
        s = cycle.on_apply_no_change(state(), 1, "cve_bloquante_sans_upgrade_disponible", "sha1", NOW)["state"]
        s = cycle.on_apply_no_change(s, 2, "deja_corrige_sur_head", "sha1", NOW)["state"]
        self.assertIsNone(s["same_cause"])


class NoActionTest(unittest.TestCase):
    def test_799_no_action_notifie_une_fois_par_code_source(self):
        """Builds #799-#802 : même cause « no action » sur un code inchangé, un seul push."""
        d = cycle.on_detect_no_action(state(), 799, "sha1", NOW)
        self.assertTrue(d["push_journal"])
        d = cycle.on_detect_no_action(d["state"], 800, "sha1", NOW + 60)
        self.assertFalse(d["push_journal"])
        self.assertEqual(d["state"]["last_processed_build"], 800)

    def test_halte_apres_pushes_no_action_consecutifs(self):
        s = state()
        for i in range(MAX_CONSECUTIVE_NO_ACTION_PUSHES):
            d = cycle.on_detect_no_action(s, 800 + i, f"sha{i}", NOW)
            s = d["state"]
        self.assertTrue(d["halt"])
        self.assertEqual(s["status"], "halted")

    def test_build_vert_oublie_la_cause_no_action(self):
        s = cycle.on_detect_no_action(state(), 799, "sha1", NOW)["state"]
        s = cycle.on_build_not_failed(s, 800)["state"]
        self.assertIsNone(s["same_cause"])
        self.assertEqual(s["consecutive_no_action_pushes"], 0)
        self.assertTrue(cycle.on_detect_no_action(s, 801, "sha1", NOW)["push_journal"])

    def test_build_vert_garde_un_blocage(self):
        s = cycle.on_apply_no_change(state(), 1, "cve_bloquante_sans_upgrade_disponible", "sha1", NOW)["state"]
        self.assertEqual(cycle.on_build_not_failed(s, 2)["state"]["same_cause"]["kind"], "blocked")


class HaltTest(unittest.TestCase):
    def test_halte_echecs_pre_push(self):
        s = state()
        for i in range(MAX_CONSECUTIVE_PREPUSH_FAILURES):
            d = cycle.on_prepush_failure(s, 10 + i, "resolve")
            s = d["state"]
        self.assertTrue(d["halt"])
        self.assertEqual((s["status"], s["last_processed_build"]), ("halted", 11))

    def test_succes_remet_le_compteur_pre_push_a_zero(self):
        s = cycle.on_prepush_failure(state(), 10, "resolve")["state"]
        s = cycle.on_fix_pushed(s, 11, "abc", "owasp", ORIG)["state"]
        self.assertEqual((s["status"], s["consecutive_prepush_failures"]), ("pending_validation", 0))
        self.assertEqual(s["pending"]["original_findings"], ORIG)

    def test_halte_rollbacks(self):
        s = state()
        for i in range(MAX_CONSECUTIVE_ROLLBACKS):
            s = dict(s, status="pending_validation")
            d = cycle.on_validation(s, 20 + i, "rollback", "sha", NOW)
            s = d["state"]
        self.assertTrue(d["halt"])
        self.assertEqual(s["status"], "halted")

    def test_validation_reussie_remet_les_rollbacks_a_zero(self):
        s = cycle.on_validation(state(status="pending_validation"), 20, "rollback", "sha", NOW)["state"]
        s = cycle.on_validation(dict(s, status="pending_validation"), 21, "success", "sha", NOW)["state"]
        self.assertEqual((s["status"], s["consecutive_rollbacks"], s["pending"]), ("idle", 0, None))

    def test_next_stage_remet_le_build_a_traiter(self):
        s = cycle.on_validation(state(status="pending_validation"), 890, "next_stage", "sha", NOW)["state"]
        self.assertEqual(s["last_processed_build"], 889)

    def test_validation_partielle_memorise_le_blocage(self):
        s = cycle.on_validation(state(status="pending_validation"), 882, "keep", "sha", NOW)["state"]
        self.assertTrue(cycle.check_same_cause(s, 883, "sha", NOW + 60)["skip"])


class PartialVerdictTest(unittest.TestCase):
    def test_890_owasp_propre_echec_trivy_suivant(self):
        v = cycle.partial_verdict("owasp", ORIG, "no_action:owasp_no_finding_above_threshold",
                                  failing_stage="Scan Sécurité Images Docker (Trivy)")
        self.assertEqual((v[0], v[1], v[4]), ("next_stage", "stage_owasp_propre_echec_sur_trivy", "trivy"))

    def test_972_echec_sur_finding_non_detecte_garde_le_correctif(self):
        v = cycle.partial_verdict("owasp", ORIG, "no_action:owasp_no_finding_above_threshold",
                                  failing_stage="OWASP Dependency-Check", failure_detail="CVE-2026-116804 DOMPurify")
        self.assertEqual(v[0], "keep", "CVE-2026-1 n'est pas une sous-chaîne qui compte")

    def test_972_finding_du_correctif_encore_en_echec_rollback(self):
        v = cycle.partial_verdict("owasp", ORIG, "no_action:owasp_no_finding_above_threshold",
                                  failing_stage="OWASP Dependency-Check", failure_detail="CVE-2026-1 encore là")
        self.assertEqual(v[0], "rollback")

    def test_975_cve_nouvelle_independante_d_un_correctif_de_suppressions(self):
        v = cycle.partial_verdict("owasp", ORIG, "ok", current=["CVE-2026-9|g:z"], fix_only_suppressions=True)
        self.assertEqual((v[0], v[1], v[4]), ("next_stage", "correctif_suppression_nouvelle_cve_independante", "owasp"))
        v = cycle.partial_verdict("owasp", ORIG, "ok", current=["CVE-2026-9|g:z"], fix_only_suppressions=False)
        self.assertEqual((v[0], v[1]), ("rollback", "nouvelle_cve_apres_correctif"))

    def test_progres_sans_regression_et_aucun_progres(self):
        self.assertEqual(cycle.partial_verdict("owasp", ORIG, "ok", current=["CVE-2026-2|g:b"])[:2],
                         ("keep", "progres_sans_regression"))
        self.assertEqual(cycle.partial_verdict("owasp", ORIG, "ok", current=ORIG)[:2], ("rollback", "aucun_progres"))

    def test_doute_rollback(self):
        for detect in ("error", "invalid", "no_action:scan_trivy_infra_failure"):
            self.assertEqual(cycle.partial_verdict("trivy", ORIG, detect)[0], "rollback", detect)


class LegacyStateTest(unittest.TestCase):
    def test_ancien_format_lu(self):
        old = {"last_processed_build": 5, "status": "idle", "pending": None, "consecutive_rollbacks": 1,
               "consecutive_prepush_failures": 0, "consecutive_no_action_pushes": 0,
               "blocked_confirmed": {"since": cycle.iso(NOW), "source_sha": "sha1", "recheck_seconds": 3600,
                                     "attempts": 2},
               "no_action_confirmed": None}
        s = cycle.normalize(old)
        self.assertNotIn("blocked_confirmed", s)
        self.assertEqual((s["same_cause"]["kind"], s["same_cause"]["attempts"]), ("transient", 2))
        self.assertTrue(cycle.check_same_cause(old, 6, "sha1", NOW + 60)["skip"])
        s = cycle.normalize({"blocked_confirmed": {"since": "2026-01-01T00:00:00Z", "source_sha": "x"}})
        self.assertEqual(s["same_cause"]["kind"], "blocked")
        s = cycle.normalize({"no_action_confirmed": {"since": "2026-01-01T00:00:00Z", "source_sha": "y"}})
        self.assertEqual(s["same_cause"]["kind"], "no_action")


class CliTest(unittest.TestCase):
    """fixcve-cycle.py : n'écrit jamais state.json, seulement le nouvel état à part."""

    def run_cli(self, *args, params=None):
        out = subprocess.run(["python3", "-I", os.path.join(SCRIPTS, "fixcve-cycle.py"), *args],
                             input=json.dumps(params or {}), capture_output=True, text=True, check=True)
        return out.stdout.strip()

    def test_regle_et_etat_a_part(self):
        with tempfile.TemporaryDirectory() as d:
            st, nxt = os.path.join(d, "state.json"), os.path.join(d, "next.json")
            with open(st, "w") as fh:
                json.dump(state(consecutive_prepush_failures=1), fh)
            decision = json.loads(self.run_cli("prepush-failure", st, nxt, params={"build": 7, "step": "apply"}))
            self.assertTrue(decision["halt"])
            with open(st) as fh:
                self.assertEqual(json.load(fh)["status"], "idle")
            with open(nxt) as fh:
                self.assertEqual(json.load(fh)["status"], "halted")

    def test_stage_type_et_verdict(self):
        self.assertEqual(self.run_cli("stage-type", "Analyse OWASP"), "owasp")
        self.assertEqual(self.run_cli("stage-type", "Tests Selenium"), "")
        v = json.loads(self.run_cli("verdict", params={"stage": "owasp", "original": ORIG, "detect": "ok",
                                                       "current": ["CVE-2026-2|g:b"]}))
        self.assertEqual(v["verdict"], "keep")


if __name__ == "__main__":
    unittest.main()
