"""Bibliothèque déterministe de fixcve-auto (aucun LLM).

Modules :
  rules        règles métier : seuils, images, nature du composant, constantes de cycle
  cycle        règles de cycle du poller (haltes, mémoire « même cause », verdict de validation)
  poller       passage du bot : phases A et B, état sous verrou, journal (exécute les effets)
  jenkins      API Jenkins (jeton en en-tête) et cause réelle d'un build en échec
  gitops       commit, push, rejeu sur origin et rollback des commits du bot
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
