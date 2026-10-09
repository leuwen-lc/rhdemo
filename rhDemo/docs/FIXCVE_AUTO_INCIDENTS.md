# fixcve-auto — registre des incidents

Chaque garde-fou de [FIXCVE_AUTO.md](FIXCVE_AUTO.md) vient d'un incident réel. Ce registre relie l'incident, sa cause, la protection actuelle et le test qui le rejoue (`rhDemo/scripts/tests/`, lancer `run-all.sh`). Les récits détaillés antérieurs à la refonte du 2026-10-09 sont dans l'historique git de `FIXCVE_AUTO.md` et des scripts.

| Builds | Cause | Protection actuelle | Test |
| --- | --- | --- | --- |
| #710 | Ligne de résultat absente, script tué par `set -e` | Scripts déterministes, absence de ligne de résultat traitée comme échec d'étape | `poll-sandbox.sh` |
| #715 | `npm` absent du `PATH` sous cron | Binaire `frontend/node/npm` (chemin littéral) | — |
| #718, #734 | Bon correctif annulé à cause d'autres CVE restées rouges | Validation par non-régression (`validation_partial`) | `poll-sandbox.sh` (`PHASE_B`) |
| #735 à #745 | Tomcat 7,5 sans correctif : le LLM renonçait à tout le lot, 11 cycles | Table de décision : critère B pour CVSS < 9 | `test_policy.test_tomcat_735_cvss_7_5_sans_correctif_critere_b` |
| #749, #750 | Build intercalé pris pour la validation | Validation par SHA | — |
| #752, #753 | `log()` sur stdout mélangé au JSON, crochets interprétés par curl | `log()` sur stderr, `curl --globoff` | — |
| #760, #762 | Suppression rendue illisible (`--` dans un commentaire XML) | Générateur : justification dans `<notes>` ; vérification syntaxique | `test_suppressions.test_double_inscription_et_xml_valide`, `test_apply_verify.VerifyTest.test_syntaxe_invalide` |
| #772 à #802 | Boucles de journal (hors périmètre, « sans finding ») | Hors périmètre jamais committé ; anti-boucle par SHA source | — |
| #806 | Workspace Claude Code non approuvé | Sans objet (plus de LLM) | — |
| #812 à #823 | Keycloak : version rétrograde, version non publiée en tag, branche suivante ignorée | Candidates Trivy triées, tag publié et plus récent que le courant, digest du registre | `test_resolve_maven_image.ImageTest` |
| #819 | Cause du rollback mal journalisée | `capture_failure_context()` | — |
| #844 à #847 | Montée npm sans effet (parent verrouillant la plage) | Montée retenue seulement si toutes les copies du lockfile atteignent la cible | `test_apply_verify.ApplyTest.test_npm_montee_sans_effet_restauree` |
| #878, #882 | `proxy-addr` 9,3 en devDependency bloquait 19 findings ; statut npm non reproductible | Critère A prioritaire, `npm_dev_only` calculé | `test_policy.test_882_critere_a_prime_sur_cvss_9` |
| #882 | Journal non committé, clone sale 9 h | Journal committé par le poller | — |
| #884, #886 | API de recherche Maven (5 versions par pertinence) : 13 `lookup_failed` | `maven-metadata.xml` complet, garde-fou de cohérence | `test_resolve_maven_image.MavenTest.test_garde_fou_version_installee_absente_de_la_liste` |
| #884 (rejeu) | Fiches CVE d'OSV sans entrée par paquet : jackson classé « sans correctif » | Suivi des alias GHSA | `test_resolve_maven_image.MavenTest.test_884_fiche_cve_sans_paquet_suit_l_alias_ghsa` |
| #890 | Rollback à tort : OWASP propre, échec Trivy suivant | Verdict `next_stage` | — |
| #894 | Doublon Trivy (même jar à deux emplacements) | Dédoublonnage `(finding_id, package_name)` | `test_outcomes_schema_detect.DetectTest.test_894_doublon_trivy_dedoublonne` |
| #895 | bcprov / freemarker 9,1 dans Keycloak, aucun tag corrigé | Échec conforme, décision humaine | `test_policy.test_895_jars_embarques_cvss_9_sans_correctif_bloques`, `ImageTest.test_895_version_de_bibliotheque_jamais_un_tag` |
| #913 | Phase 3 LLM : commandes hors règles d'autorisation, cycle abandonné ; phase 2 LLM : texte non ASCII, schéma invalide | Sans objet (plus de LLM) | `poll-sandbox.sh` |
| #914 | npm `fixAvailable` vrai, dry-run muet : `lookup_failed` | Repli sur l'avis OSV | `test_resolve_npm.test_build_914_fix_available_but_dry_run_silent` |
| #914 | GHSA voisin relevé dans les références, supprimé par ricochet | Alias = fiches contenant l'identifiant du finding | `test_resolve_npm.test_secondary_id_finds_advisory_but_is_not_an_alias` |
| Renovate #123 / CI #912 | Même faille nommée CVE (OSS Index) ou GHSA (Node Audit) ; cache Node Audit | Double inscription générée ; cache Node Audit coupé | `test_suppressions.test_forme_manquante_ajoutee_au_bloc_existant` |
| Bac à sable 2026-10-09 | npm audit hors ligne : rapport vide pris pour « sans correctif » | « Sans correctif » exige un avis OSV lu | `test_resolve_npm.test_audit_vide_et_avis_injoignable_jamais_sans_correctif` |
| Bac à sable 2026-10-09 | Journal dans le commit du correctif : un rollback l'aurait annulé | Deux commits | `poll-sandbox.sh` (`PHASE_B=FAILURE`) |
