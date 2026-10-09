"""Bibliothèque déterministe de fixcve-auto (aucun LLM).

Modules :
  common       versions, JSON, sous-processus
  osv          avis OSV.dev (plage corrigée par branche, alias CVE <-> GHSA)
  registry     versions publiées : Maven Central, npm, registres d'images
  resolve      recherche de correctif par finding (étape 2)
  policy       classification upgrade / suppression A / B / blocage (étape 3)
  suppressions générateurs owasp-suppressions.xml et .trivyignore.yaml
  edits        application des montées de version (npm, Maven, images)
  advisories   entrée de docs/SECURITY_ADVISORIES.md
  verify       vérification locale avant push (étape 6)
  outcomes     codes de résultat et statistiques du journal (indicateur K)

Voir rhDemo/docs/FIXCVE_AUTO.md.
"""
