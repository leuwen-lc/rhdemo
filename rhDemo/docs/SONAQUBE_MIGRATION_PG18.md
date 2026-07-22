# Migration PostgreSQL 16 → 18 (base SonarQube)

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
