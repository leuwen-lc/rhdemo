---
name: docs-lint
description: Contrôle de cohérence de la documentation du projet RHDemo (frontmatter, index, liens, références, sources modifiées depuis la dernière vérification) puis, sur demande, correction des écarts des docs actifs. Déclencher avec /docs-lint, ou quand l'utilisateur demande de vérifier, de mettre à jour ou de ranger la documentation.
---

# /docs-lint — contrôle du wiki de documentation

Source versionnée : `rhDemo/scripts/docs-skills/docs-lint/SKILL.md` (copie locale dans `.claude/skills/docs-lint/`).
Principe et statuts : `rhDemo/docs/index.md`. Journal : `rhDemo/docs/log.md`.

## Règles

- Le script `rhDemo/scripts/docs-lint.py` fait les contrôles déterministes. Ne pas les refaire à la main.
- **Premier passage : rapport seul.** Ne rien modifier avant d'avoir présenté le rapport et obtenu l'accord de l'utilisateur sur ce qui est corrigé.
- Ne jamais réécrire un doc `historique` ou `journal` pour l'aligner sur l'état courant : signaler l'écart. Seule exception : corriger un lien ou un nom de fichier mort, si l'utilisateur le demande.
- Pas de frontmatter sur `fixcve-audit.md` (généré) ni `SECURITY_ADVISORIES.md` (modifié par fixcve-auto).
- Ne pas copier plus de 10 lignes de code dans un doc : renvoyer au fichier.
- Aucun commit ni push sans accord explicite. Messages de commit en français, préfixe `docs:`, sans ligne `Co-Authored-By`.

## Étapes

1. **Lancer le contrôle** depuis la racine du dépôt : `python3 -I rhDemo/scripts/docs-lint.py` (`--json` pour une sortie exploitable). Code retour 1 s'il y a des erreurs.
2. **Présenter le rapport** groupé par document, en distinguant :
   - les ERREURS (frontmatter, index, liens morts dans un doc actif) ;
   - les AVERTISSEMENTS : référence `.md` introuvable, source modifiée après `verifie_le`, doc non revérifié depuis plus de 180 jours, lien mort dans un doc historique ou journal.
3. **Pour chaque doc dont une source a changé** (avertissement « source modifiée »), lire la source (`git log -p` depuis `verifie_le`) et le doc, et dire s'il est encore exact. Si oui, proposer de mettre `verifie_le` à la date du jour. Si non, proposer la correction minimale du doc.
4. **Après accord**, appliquer les corrections, puis :
   - mettre à jour `verifie_le` des docs revérifiés ;
   - si un doc est ajouté, retiré ou reclassé : `rhDemo/docs/index.md` (ligne et statut) ;
   - ajouter en bas de `rhDemo/docs/log.md` une entrée `## [AAAA-MM-JJ] lint | titre` qui liste ce qui a été constaté et corrigé, et ce qui reste ouvert.
5. **Relancer le script** pour confirmer, puis `bash rhDemo/scripts/tests/run-all.sh` si le script lui-même a été modifié.

## Ce que le script ne couvre pas (jugement à exercer)

- Versions et valeurs citées dans un doc actif (images, ports, noms de ressources) : les comparer à la source de vérité (`pom.xml`, `values.yaml`, Jenkinsfile, scripts) quand `sources` en désigne une qui a changé.
- Un doc `proposition` dont la décision a été prise : à reclasser en `historique` (avec bilan de ce qui est appliqué) ou à supprimer.
- Un doc `historique` ou `journal` encore cité comme référence courante par un doc actif.
