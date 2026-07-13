# Forgejo Actions — Renovate

> **Statut : rapatrié vers Jenkins.** Le scan Renovate tourne désormais dans le job
> `RHDemo-Renovate` (cron 3h, `rhDemo/Jenkinsfile-Renovate`), suite à l'indisponibilité
> récurrente du pool de runners `codeberg-medium` (pas seulement un timeout — plus de
> container disponible du tout). `renovate.yml` reste dans ce dépôt en secours manuel
> (`workflow_dispatch` uniquement, cron désactivé) si Jenkins devient indisponible.
> Voir [`rhDemo/docs/RENOVATE_AUTOMERGE_CI.md`](../../rhDemo/docs/RENOVATE_AUTOMERGE_CI.md).
>
> Le contenu ci-dessous reste pertinent si on doit un jour retourner à une exécution
> côté Codeberg Actions (secours du secours).

## Problématique runner Codeberg (context deadline exceeded)

Les runners 'codeberg-small' annulent tout job dépassant ~5 minutes avec l'erreur
"context deadline exceeded" lors de l'archivage Podman post-step
(`SUMMARY.md`, `pathcmd.txt`). C'est une limitation de leur infrastructure,
pas un bug du workflow (confirmé par reproduction minimale : `echo "hello"`
passe, tout ce qui dépasse ~5 min échoue).

**Solution actuelle :** les runners `codeberg-medium` permettent d'exécuter
Renovate en un seul passage (moins de 10 minutes ~51 deps après désactivation de `jenkins` et
`maven-wrapper` dans `renovate.json`).

## Si codeberg-medium commence à échouer : scinder en deux workflows

Remplacer `renovate.yml` par les deux fichiers ci-dessous, décalés de 20 min.

**`renovate-infra.yml`** — 3h00, `codeberg-small`, 18 deps :
```yaml
RENOVATE_ENABLED_MANAGERS: '["docker-compose","dockerfile","github-actions","helm-values"]'
```

**`renovate-app.yml`** — 3h20, `codeberg-small`, 33 deps :
```yaml
RENOVATE_ENABLED_MANAGERS: '["maven","npm"]'
```

Les deux fichiers partagent la même configuration GPG et les mêmes variables
d'environnement que `renovate.yml`. Supprimer `renovate.yml` lors de l'activation
du split. Le contenu complet des deux fichiers est disponible dans le commit
`e646f6f` (branche master).
