# Procédure standard : PR `evolutions-post-1.1.7` -> `master`, release `1.1.8-RELEASE`, tag, puis retour en `-SNAPSHOT`

Contexte (modifier les versions par remplacement global):

- Branche source (exemple) : `evolutions-post-1.1.7`
- Branche cible : `master`
- Tag Git (exemple) : `1.1.8-RELEASE`
- Après la release, `master` repasse en `-SNAPSHOT`

## Prérequis

- chaine CI/CD complète au vert avec options sonarqube et selenium
- README.md racine mis à jour en particulier la section changelog pour la nouvelle version

---

## Étapes automatisées vs manuelles

| Étape | Outil | Description |
| ----- | ----- | ----------- |
| Sync + align master + bump RELEASE + push | `release.sh pre-merge` | Automatisé |
| Squash merge signé | `git` local | **Manuel** (nécessite clé GPG/SSH locale) |
| Tag + push tag + bump SNAPSHOT + push | `release.sh post-merge` | Automatisé |

Script : [`rhDemo/scripts/release.sh`](../scripts/release.sh)

---

## 1) Préparer la branche (automatisé)

```bash
cd <racine du dépôt>
rhDemo/scripts/release.sh pre-merge 1.1.8-RELEASE evolutions-post-1.1.7
```

Le script effectue dans l'ordre :

1. Vérifie que le répertoire de travail est propre
2. Bascule sur la branche si nécessaire
3. `git pull --rebase origin evolutions-post-1.1.7`
4. `git fetch origin && git merge origin/master` (alignement avec master)
5. Bumpe les 3 `pom.xml` : `1.1.8-SNAPSHOT` → `1.1.8-RELEASE`
6. Commit `chore(release): passage à la version 1.1.8-RELEASE`
7. Push

> Si des conflits surviennent à l'étape 4, le script s'arrête avec les instructions pour les résoudre manuellement.

---

## 2) Vérifier la CI et ouvrir la PR sur Codeberg

- Attendre que le **statut de commit Jenkins CI** soit vert sur Codeberg
- Créer la PR : `evolutions-post-1.1.7` → `master`
- Faire relire la PR (checks, conventions, etc.)

---

## 3) Merger en squash signé en local (manuel)

> Seule étape qui reste manuelle : le squash merge signé requiert la clé GPG/SSH locale.
> Ne pas utiliser le bouton Merge de l'interface Codeberg.

```bash
git fetch origin
git checkout master
git merge --squash origin/evolutions-post-1.1.7
git commit -S -m "release: merge evolutions-post-1.1.7"
git push origin master
```

---

## 4) Tagger et repasser en SNAPSHOT (automatisé)

```bash
cd <racine du dépôt>
rhDemo/scripts/release.sh post-merge 1.1.8-RELEASE 1.1.9-SNAPSHOT
```

Le script effectue dans l'ordre :

1. Vérifie que le répertoire de travail est propre et que la branche est `master`
2. `git pull origin master`
3. Contrôle que `pom.xml` est bien en `1.1.8-RELEASE` (cohérence avec le squash merge)
4. `git tag -a 1.1.8-RELEASE -m "Release 1.1.8-RELEASE"`
5. `git push origin 1.1.8-RELEASE`
6. Bumpe les 3 `pom.xml` : `1.1.8-RELEASE` → `1.1.9-SNAPSHOT`
7. Met à jour `jenkins-casc.yaml` : branche CI/CD → `evolutions-post-1.1.8`
8. Commit `chore: retour à 1.1.9-SNAPSHOT après 1.1.8-RELEASE`
9. Push

---

## 5) Créer la branche d'évolution suivante

Le script affiche la commande à la fin, exemple :

```bash
git checkout -b evolutions-post-1.1.8
git push origin evolutions-post-1.1.8
```
