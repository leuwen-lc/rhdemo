# Procédure standard : PR `evolutions-post-1.1.4` -> `master`, release `1.1.5-RELEASE`, tag, puis retour en `-SNAPSHOT`

Contexte :
- Branche source : `evolutions-post-1.1.4` (testée)
- Branche cible : `master`
- Tag Git : `1.1.5-RELEASE`
- Après la release, `master` repasse en `-SNAPSHOT`

> Remplace `origin` par le nom de ton remote si différent.

---

## 1) Synchroniser ton repo local avec le distant

```bash
git fetch origin
# Récupère toutes les dernières références (branches/tags) depuis le remote, sans modifier ta branche courante.
```

```bash
git checkout evolutions-post-1.1.4
# Bascule sur la branche de travail à livrer.
```

```bash
git pull --rebase origin evolutions-post-1.1.4
# Met à jour ta branche avec le distant en rejouant tes commits au-dessus (historique plus propre qu’un merge).
```

---

## 2) Ré-aligner la branche avec `master` (recommandé)

```bash
git fetch origin
# Rafraîchit les références distantes (dont origin/master) avant de rebaser.
```

```bash
git rebase origin/master
# Rejoue les commits de ta branche au-dessus de master pour minimiser les surprises au moment du merge de la PR.
```

> Si conflits : les résoudre, puis faire `git add ...` et `git rebase --continue` (répéter jusqu’à fin du rebase).

---

## 3) Passer la version Maven en `1.1.5-RELEASE` (dans le(s) POM)

1. Modifie le(s) `pom.xml` (parent + modules si besoin) :
   - Remplace par exemple `1.1.5-SNAPSHOT` par `1.1.5-RELEASE`.

Puis :

```bash
git status
# Affiche les fichiers modifiés pour vérifier que seuls les POM attendus ont changé.
```

```bash
git add pom.xml **/pom.xml
# Ajoute à l’index les POM (racine + modules) pour préparer le commit de version.
```

```bash
git commit -m "chore(release): set version to 1.1.5-RELEASE"
# Crée un commit traçable qui fige la version release dans les POM.
```

```bash
git push origin evolutions-post-1.1.4
# Pousse la branche mise à jour (avec le commit de version) vers le remote pour l’utiliser dans la Pull Request.
```

> Si tu as dû rebase et que Git refuse le push :  
> `git push --force-with-lease origin evolutions-post-1.1.4`  
> (réécrit la branche distante de façon “sécurisée” en vérifiant qu’elle n’a pas bougé côté remote).

---

## 4) Ouvrir et merger la Pull Request sur GitHub

Sur GitHub :
- Créer une PR :
  - **base** : `master`
  - **compare** : `evolutions-post-1.1.4`
- Vérifier que la CI est verte et que la PR est conforme (checks, conventions, etc.).
- Comme tu es demandeur et validateur : tu merges la PR dès que les règles du dépôt le permettent (branch protection, approvals, etc.).

> Stratégie de merge : celle imposée par le repo (Squash/Merge commit/Rebase). L’important est que `master` contienne le commit “version release”.

---

## 5) Tagger la release sur le commit de `master` (après merge)

```bash
git fetch origin
# Récupère les dernières mises à jour du remote (dont le merge de la PR sur master).
```

```bash
git checkout master
# Bascule sur la branche master en local.
```

```bash
git pull origin master
# Met à jour master local avec le dernier état de master distant (incluant le merge de la PR).
```

```bash
git tag -a 1.1.5-RELEASE -m "Release 1.1.5-RELEASE"
# Crée un tag annoté sur le commit courant (celui de master) pour marquer officiellement la release.
```

```bash
git push origin 1.1.5-RELEASE
# Publie le tag vers le remote pour le rendre visible à tous (et déclencher d’éventuels pipelines de release).
```

---

## 6) Repasser `master` en `-SNAPSHOT` après la release

Décide de la version de développement suivante (exemples courants) :
- `1.1.6-SNAPSHOT` (souvent)
- ou une autre selon votre versioning.

1. Modifie le(s) `pom.xml` pour mettre la prochaine version `-SNAPSHOT`.

Puis :

```bash
git status
# Vérifie les fichiers modifiés avant de committer le retour en SNAPSHOT.
```

```bash
git add pom.xml **/pom.xml
# Ajoute les POM modifiés à l’index (préparation du commit “back to snapshot”).
```

```bash
git commit -m "chore: back to <NEXT_VERSION>-SNAPSHOT after 1.1.5-RELEASE"
# Committe le retour en version de développement pour éviter que master reste bloqué en version release.
```

```bash
git push origin master
# Publie le commit “back to snapshot” sur master.
```

> Remplace `<NEXT_VERSION>` par la valeur réelle (ex: `1.1.6`).

---

## Checklist rapide

- [ ] `evolutions-post-1.1.4` à jour et rebase sur `origin/master` fait (ou stratégie équivalente)
- [ ] POM en `1.1.5-RELEASE` committé sur la branche
- [ ] PR ouverte vers `master` + CI verte + merge effectué
- [ ] Tag `1.1.5-RELEASE` créé **sur master après merge** et poussé
- [ ] `master` repassé en `<NEXT_VERSION>-SNAPSHOT` et poussé
