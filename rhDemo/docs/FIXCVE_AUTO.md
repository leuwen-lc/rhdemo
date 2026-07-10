# Remédiation CVE automatisée (fixcve-auto)

Automatisation complète de la remédiation des CVE bloquantes détectées par Trivy ou OWASP Dependency-Check dans le pipeline `RHDemo-CI`, **sans validation humaine**. Complète le skill interactif `/fixcve` (`.claude/skills/fixcve/SKILL.md`) qui reste disponible pour un usage manuel.

⚠️ Ce document décrit une automatisation qui **committe et pousse du code sur la branche courante sans revue humaine**, y compris des décisions d'acceptation de risque (suppression de CVE). C'est un choix assumé en échange des garde-fous ci-dessous — à désactiver si ces garde-fous ne sont plus jugés suffisants pour le contexte du moment (ex: montée en criticité du projet).

---

## Architecture

```
crontab (toutes les 15 min)
   └─> rhDemo/scripts/fixcve-auto-poll.sh   (bash + jq + curl, PAS de LLM)
         │
         ├─ Phase A (idle) : détecte un nouveau build Jenkins en échec Trivy/OWASP
         │     └─ invoque : claude -p "/fixcve-auto <build> <trivy|owasp>"
         │           (.claude/skills/fixcve-auto/SKILL.md — remédiation + commit + push)
         │
         └─ Phase B (pending_validation) : vérifie le build CI suivant
               ├─ SUCCESS  → marque résolu
               └─ FAILURE  → git revert automatique + halte après 2 rollbacks consécutifs
```

Le polling lui-même ne fait **aucun appel LLM** — Claude Code n'est invoqué que pour la remédiation proprement dite (parsing des rapports, recherche de correctif, rédaction de suppression, édition de fichiers).

---

## Garde-fous

| Garde-fou | Détail |
|---|---|
| **Working tree propre requis** | Si des modifications locales non committées existent, le script ne touche à rien (évite d'interférer avec un travail en cours). |
| **Branche à jour requise** | Si la branche locale est en retard/divergente par rapport à `origin`, le script s'arrête (pas de merge/rebase automatique). |
| **Rollback automatique** | Si le build Jenkins déclenché par un correctif automatique échoue à nouveau, `git revert` immédiat + push. |
| **Halte après rollbacks répétés** | Après `MAX_CONSECUTIVE_ROLLBACKS` (2) rollbacks consécutifs, le statut passe à `halted` : plus aucune action tant qu'un humain ne réinitialise pas `~/.config/rhdemo-fixcve/state.json`. |
| **Critères objectifs pour toute suppression/acceptation de risque** | Une CVE sans correctif disponible n'est supprimée que si : scope `test`/`provided`, OU RetireJS sur une lib JS non utilisée dans `frontend/src`, OU vecteur d'attaque `AV:L`/`AV:P` (accès physique/local). Sinon : blocage documenté, `FIXCVE_AUTO_RESULT: NO_ACTION`, intervention manuelle requise. |
| **Journal d'audit append-only** | `rhDemo/docs/fixcve-audit.jsonl`, versionné, une ligne JSON par événement (détection, application, validation, rollback, halte). |
| **Verrou anti-chevauchement** | `flock` sur `~/.config/rhdemo-fixcve/poll.lock` — un cycle CI (~2h max) ne peut pas se chevaucher avec le suivant. |

---

## Prérequis d'installation

### 1. Outils

`jq`, `sops`, `yq`, `flock`, `curl`, `git`, `claude` (Claude Code CLI) disponibles dans le `PATH` de l'utilisateur cron.

### 2. Clé AGE personnelle

Doit déjà exister (utilisée par ailleurs pour les secrets du projet) :
```bash
ls -la ~/.config/sops/age/keys.txt
```

### 3. Credentials chiffrés : `~/.config/rhdemo-fixcve/credentials.sops.yaml`

Ce fichier vit **hors du dépôt git**, chiffré avec votre clé AGE personnelle (donc lisible uniquement sur cette machine, avec cette clé). Il contient :
- le compte Jenkins dédié à l'automatisation (`claude`, **pas** `admin` — voir `.claude/skills/fixcve/SKILL.md`),
- un token Codeberg **dédié et restreint à ce seul dépôt** (fine-grained access token, scope écriture sur `rhdemo` uniquement — ne pas réutiliser un token à portée large).

Création :
```bash
mkdir -p ~/.config/rhdemo-fixcve && chmod 700 ~/.config/rhdemo-fixcve

cat > /tmp/fixcve-creds-plain.yaml <<'EOF'
jenkins:
  user: claude
  token: METTRE_LE_VRAI_TOKEN_JENKINS_ICI
codeberg:
  user: leuwen-lc
  token: METTRE_LE_VRAI_TOKEN_CODEBERG_ICI
EOF

RECIPIENT=$(grep "public key:" ~/.config/sops/age/keys.txt | awk '{print $NF}')
SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops --encrypt --age "${RECIPIENT}" \
  /tmp/fixcve-creds-plain.yaml > ~/.config/rhdemo-fixcve/credentials.sops.yaml

shred -u /tmp/fixcve-creds-plain.yaml   # ne jamais laisser le clair sur disque

chmod 600 ~/.config/rhdemo-fixcve/credentials.sops.yaml
```

Vérification (affiche le déchiffré sans rien écrire sur disque) :
```bash
SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops -d ~/.config/rhdemo-fixcve/credentials.sops.yaml
```

Le token Jenkins doit être un token **régénéré** si une ancienne valeur a pu fuiter (ex: fichier de config local en clair) — révoquer l'ancien dans Jenkins avant de créer le nouveau.

### 4. `GIT_ASKPASS`

Déjà en place : `~/.config/rhdemo-fixcve/git-askpass.sh` (aucun secret dedans, lit `CODEBERG_USER`/`CODEBERG_TOKEN` depuis l'environnement au moment du push).

### 5. Installation du cron

**Ne pas installer sans avoir relu `rhDemo/scripts/fixcve-auto-poll.sh` et compris les garde-fous ci-dessus.**

```bash
crontab -e
```
Ajouter :
```cron
*/15 * * * * /home/leno-vo/git/repository/rhDemo/scripts/fixcve-auto-poll.sh >> /home/leno-vo/.config/rhdemo-fixcve/poll.log 2>&1
```

### 6. Rotation de `poll.log`

`poll.log` est alimenté à chaque cycle (toutes les 15 min) et grossirait indéfiniment sans rotation. Config `logrotate` en espace utilisateur (pas de `sudo` requis), déjà en place : `~/.config/rhdemo-fixcve/logrotate.conf` (hebdomadaire, 4 générations conservées compressées, taille max 10 Mo).

Ligne cron associée (exécution quotidienne à 3h) :
```cron
0 3 * * * /usr/sbin/logrotate --state /home/leno-vo/.config/rhdemo-fixcve/logrotate.state /home/leno-vo/.config/rhdemo-fixcve/logrotate.conf
```

---

## Désactivation / pause

```bash
crontab -e   # supprimer ou commenter la ligne fixcve-auto-poll.sh
```
Ou, sans toucher au cron, forcer une halte immédiate :
```bash
jq '.status="halted"' ~/.config/rhdemo-fixcve/state.json > /tmp/s.json && mv /tmp/s.json ~/.config/rhdemo-fixcve/state.json
```

## Reprise après une halte manuelle

Après avoir traité manuellement la cause des rollbacks répétés (visible dans `rhDemo/docs/fixcve-audit.jsonl`, événements `automation_halted`) :
```bash
jq '.status="idle" | .consecutive_rollbacks=0' ~/.config/rhdemo-fixcve/state.json > /tmp/s.json && mv /tmp/s.json ~/.config/rhdemo-fixcve/state.json
```

## Lecture des logs

Deux fichiers distincts, deux usages différents :

- **`~/.config/rhdemo-fixcve/poll.log`** — sortie brute (stdout/stderr) de **chaque** exécution du cron, toutes les 15 min, y compris les cycles où rien ne se passe. Utile pour vérifier que le cron tourne bien :

  ```bash
  tail -f ~/.config/rhdemo-fixcve/poll.log
  ```

- **`rhDemo/docs/fixcve-audit.jsonl`** — uniquement les événements notables (remédiation appliquée, build hors périmètre, validation, rollback, halte). Versionné dans git, à consulter avec la commande ci-dessous.

## Lecture du journal d'audit

```bash
cat rhDemo/docs/fixcve-audit.jsonl | jq .
# Uniquement les rollbacks :
jq 'select(.event == "validation_failed_rollback")' rhDemo/docs/fixcve-audit.jsonl
```

## Voir aussi

- [`.claude/skills/fixcve/SKILL.md`](../../.claude/skills/fixcve/SKILL.md) — version interactive avec validation humaine
- [`.claude/skills/fixcve-auto/SKILL.md`](../../.claude/skills/fixcve-auto/SKILL.md) — instructions détaillées de la remédiation automatique
- [SECURITY_ADVISORIES.md](SECURITY_ADVISORIES.md) — historique des CVE traitées (manuel et automatique)
- [SOPS_SETUP.md](SOPS_SETUP.md) — installation SOPS/AGE
