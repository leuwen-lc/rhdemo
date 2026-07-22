# Journal d'opérations — 2026-07-22

Récapitulatif des interventions réalisées sur l'infrastructure Jenkins/Renovate/SonarQube lors de
cette session : durcissement sécurité du pipeline Renovate, déblocage du CI, notifications email,
vérification des permissions du compte de service Claude, migration PostgreSQL de SonarQube.

---

## 1. Durcissement sécurité du pipeline Renovate

**Problème** : le pipeline `Jenkinsfile-Renovate` sélectionnait les PRs à auto-merger sur le seul
nom de branche (`head.ref` matchant `renovate`), sans vérifier l'origine réelle de la PR ; et le
token Forgejo à accès Write était exposé en variable d'environnement pendant l'exécution du build
Maven d'une PR (code non revu), ouvrant un vecteur d'exfiltration en cas de dépendance compromise.

**Correctifs** (voir [`Jenkinsfile-Renovate`](../Jenkinsfile-Renovate)) :
- Filtre `jq` du listing des PRs : ajout de `select(.head.repo.full_name == $repo)`, rejette
  explicitement les PRs dont la branche source n'est pas dans le dépôt principal.
- `FORGEJO_TOKEN` scopé aux seules étapes qui en ont besoin (push de synchronisation, merge,
  commentaires) — jamais présent pendant `mvnw verify`/OWASP.

Documentation associée mise à jour : [`RENOVATE_AUTOMERGE_CI.md`](RENOVATE_AUTOMERGE_CI.md)
(section Sécurité).

## 2. Historique linéaire pour les merges Renovate

**Problème** : chaque PR Renovate mergée laissait un triplet de commits sur
`evolutions-post-1.1.9` (commit original + commit de synchronisation + commit de merge),
compliquant l'historique git.

**Correctif** : passage du merge final Forgejo de `"Do":"merge"` à `"Do":"squash"` dans
`Jenkinsfile-Renovate` — un seul commit par PR. Sans impact sur l'étape de synchronisation
(reste un merge classique, nécessaire pour ne pas casser le merge-base). Nécessite
**« Allow squash merging »** activé côté réglages du dépôt Codeberg.

## 3. Réécriture de `RENOVATE_AUTOMERGE_CI.md`

Le document détaillait longuement cinq options d'architecture jamais implémentées (comparatifs,
pseudo-code). Remplacé par un paragraphe unique résumant problème/alternatives écartées/solution
retenue, le reste du document ne documentant plus que l'implémentation réelle (voir
[`RENOVATE_AUTOMERGE_CI.md`](RENOVATE_AUTOMERGE_CI.md)). Convention appliquée à l'ensemble du
document : pas de copie de code de plus de 10 lignes, référence au fichier source à la place.

## 4. Blocage du polling RHDemo-CI après bump de branche

**Symptôme** : `RHDemo-CI` ne se déclenchait plus malgré des merges Renovate quotidiens sur
`evolutions-post-1.1.9` (dernier build : 9 jours).

**Cause** : le plugin Git de Jenkins détermine la « dernière révision construite » à partir du
`BuildData` du dernier build, pas du `BranchSpec` courant du job. Le dernier build (#659) avait
tourné sur `evolutions-post-1.1.8` juste avant le bump de branche — le polling restait ancré
dessus, ignorant `evolutions-post-1.1.9`.

**Correctif** : un build manuel (« Build Now ») sur la nouvelle branche suffit à réancrer le
polling. Documenté dans [`GIT-PROCEDURE-RELEASE.md`](GIT-PROCEDURE-RELEASE.md) (note après
l'étape `release.sh post-merge`) pour anticiper ce blocage à chaque future release.

## 5. Notifications email de succès/échec — RHDemo-CI

**Objectif** : recevoir un email à chaque succès/échec du pipeline CI, sur le même principe que
les notifications déjà reçues pour les PRs/merges Renovate (mécanisme Forgejo, indépendant de
Jenkins).

**Itérations** :
1. Première tentative avec le plugin Mailer basique + credential Jenkins référencé par
   `credentialsId` en JCasC → échec au boot (`UnknownAttributesException`, cette classe
   n'accepte que `username`/`password` en clair via JCasC, pas de credential).
2. Deuxième tentative avec `username`/`password` en clair via une variable d'environnement
   (`.env`) → fonctionnel mais expose le mot de passe hors du coffre chiffré Jenkins.
3. **Solution retenue** : plugin **email-ext**, qui gère en interne un vrai credential Jenkins.
   Le configurateur JCasC ne sait pas piloter ce champ non plus (bug connu upstream) — la config
   SMTP (host/port/SSL + credential `smtp-infomaniak-credentials`) est donc faite **manuellement**
   une fois via *Manage Jenkins > System > Extended E-mail Notification*, JCasC ne la touchant
   pas et ne l'écrasant donc pas au redémarrage.

Fichiers modifiés : [`Jenkinsfile-CI`](../Jenkinsfile-CI) (step `emailext` dans
`post { success/failure }`), [`jenkins-casc.yaml`](../infra/jenkins-docker/jenkins-casc.yaml)
(doc du credential #9), [`plugins.txt`](../infra/jenkins-docker/plugins.txt) (ajout
`email-ext`, régénéré avec `generate-pluginslist.sh`).

## 6. Vérification des permissions du compte Jenkins `claude`

**Objectif** : confirmer que le compte en lecture seule utilisé par `/fixcve`
(`Overall/Read`, `Job/Read`, `View/Read` — voir [`jenkins-casc.yaml`](../infra/jenkins-docker/jenkins-casc.yaml))
ne peut pas lire la valeur des credentials Jenkins.

**Résultat** : testé sur plusieurs vecteurs (listing des credentials, accès direct à
`nvd-api-key`, Script Console, config XML brut d'un job) — tous refusés (404/403). Contrôle
positif (API JSON d'un job) fonctionnel, confirmant que le compte fonctionne normalement pour ce
qui est autorisé. Aucune fuite possible via l'API REST standard.

## 7. Migration PostgreSQL 16 → 18 (base SonarQube)

**Symptôme** : après un rebuild (`start-jenkins.sh`), `rhdemo-sonarqube-db` en échec — Renovate
avait bumpé `postgres:16-alpine` → `postgres:18-alpine` dans
[`docker-compose.yml`](../infra/jenkins-docker/docker-compose.yml), un changement de version
majeure incompatible avec les fichiers de données existants (format sur disque différent).

**Côté SonarQube** : aucun problème — PostgreSQL 18 est officiellement supporté depuis
SonarQube Community Build 26.2 (le projet est en 26.7.0).

**Procédure exécutée** :
1. Dump de la base `sonar` via un conteneur `postgres:16-alpine` temporaire pointé sur le volume
   existant (les données restaient lisibles avec les anciens binaires).
2. Sauvegarde brute du volume (tar) en plus du dump SQL, avant toute suppression.
3. Suppression du volume PG16, recréation via `postgres:18-alpine`.
4. **Piège additionnel** : PG18+ change son layout par défaut (répertoire versionné plutôt que le
   point de montage classique `/var/lib/postgresql/data`) — même un volume neuf vide était
   rejeté. Corrigé en fixant `PGDATA=/var/lib/postgresql/data` explicitement dans
   `docker-compose.yml`.
5. Restauration du dump dans la base fraîchement initialisée.
6. Redémarrage de SonarQube, migration de schéma déclenchée (`POST /api/system/migrate_db`),
   terminée sans erreur — 125 tables, projets (`rhdemo-api`) intacts.

Sauvegardes (dump SQL + tar du volume) déplacées hors du dépôt git, dans
`~/rhdemo-backups/sonarqube-pg16-to-pg18-2026-07-22/` — à conserver quelques jours puis
supprimer une fois la stabilité confirmée.
