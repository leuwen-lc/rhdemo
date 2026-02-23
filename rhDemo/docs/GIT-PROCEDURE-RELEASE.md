# Procédure standard : PR `evolutions-post-1.1.5` -> `master`, release `1.1.6-RELEASE`, tag, puis retour en `-SNAPSHOT`

Contexte :
- Branche source (exemple) : `evolutions-post-1.1.5` 
- Branche cible : `master`
- Tag Git (exemple) : `1.1.6-RELEASE`
- Après la release, `master` repasse en `-SNAPSHOT`


## Prérequis 
- chaine CI/CD complète au vert avec options sonarqube et selenium
- README.md racine mis à jour en particulier la section changelog pour la nouvelle version


## 1) Synchroniser le repo local avec le distant

```bash
git fetch origin
# Récupère toutes les dernières références (branches/tags) depuis le remote, sans modifier la branche courante.
```

```bash
git checkout evolutions-post-1.1.5
# Bascule sur la branche de travail à livrer.
```

```bash
git pull --rebase origin evolutions-post-1.1.5
# Met à jour la branche avec le distant en rejouant les commits au-dessus (historique plus propre qu’un merge).
```

---

## 2) Ré-aligner la branche avec `master`

```bash
git fetch origin
# Rafraîchit les références distantes (dont origin/master) avant de rebaser.
```

```bash
git rebase origin/master
# Rejoue les commits de la branche au-dessus de master pour minimiser les surprises au moment du merge de la PR.
```

> Si conflits : les résoudre, puis faire `git add ...` et `git rebase --continue` (répéter jusqu’à fin du rebase).

---

## 3) Passer la version Maven en `1.1.6-RELEASE` (dans les POM)

1. Modifie les `pom.xml` (3 modules) :
   - Remplacer par exemple `1.1.6-SNAPSHOT` par `1.1.6-RELEASE`.

Puis :

```bash
git status
# Afficher les fichiers modifiés pour vérifier que seuls les POM attendus ont changé.
```

```bash
git add **/pom.xml
# Ajoute à l’index les POM (racine + modules) pour préparer le commit de version.
```

```bash
git commit -m "chore(release): passage à la version 1.1.6-RELEASE"
# Crée un commit traçable qui fige la version release dans les POM.
```

```bash
git push origin evolutions-post-1.1.5
# Pousse la branche mise à jour (avec le commit de version) vers le remote pour l’utiliser dans la Pull Request.
```

> Si rebase et que Git refuse le push :  
> `git push --force-with-lease origin evolutions-post-1.1.5`  
> (réécrit la branche distante de façon “sécurisée” en vérifiant qu’elle n’a pas bougé côté remote).

---

## 4) Ouvrir et merger la Pull Request sur GitHub

Sur GitHub :
- (Demandeur) Créer une PR :
  - **base** : `master`
  - **compare** : `evolutions-post-1.1.5`
- Validateur : Vérifier que la CI est verte avec les options SonarQube et Selenium et que la PR est conforme (checks, conventions, etc.).
- Validateur : merger la PR dès que les règles du dépôt le permettent (branch protection, approvals, etc.).

> Stratégie de merge : Squash/Merge 
---

## 5) Tagger la release sur le commit de `master` (après merge)

```bash
git fetch origin
# Récupère les dernières mises à jour du remote (dont le merge de la PR sur master).
```

```bash
git checkout master
# Basculer sur la branche master en local.
```

```bash
git pull origin master
# Met à jour master local avec le dernier état de master distant (incluant le merge de la PR).
```

```bash
git tag -a 1.1.6-RELEASE -m "Release 1.1.6-RELEASE"
# Crée un tag annoté sur le commit courant (celui de master) pour marquer officiellement la release.
```

```bash
git push origin 1.1.6-RELEASE
# Publie le tag vers le remote pour le rendre visible à tous (et déclencher d’éventuels pipelines de release).
```

---

## 6) Repasser `master` en `-SNAPSHOT` après la release

Décide de la version de développement suivante :
- `1.1.6-SNAPSHOT` (exemple)


1. Modifier les `pom.xml` pour mettre la prochaine version `-SNAPSHOT`.

Puis :

```bash
git status
# Vérifie les fichiers modifiés avant de committer le retour en SNAPSHOT.
```

```bash
git add **/pom.xml
# Ajoute les POM modifiés à l’index (préparation du commit “back to snapshot”).
```

```bash
git commit -m "chore: retour à 1.1.6-SNAPSHOT après 1.1.6-RELEASE"
# Committe le retour en version de développement pour éviter que master reste bloqué en version release.
```

```bash
git push origin master
# Publie le commit sur master.
```




