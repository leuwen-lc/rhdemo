# Sécurité des Logs Jenkins

## Problème identifié

Les logs Jenkins contiennent des secrets en clair et sont accessibles via le système de fichiers, représentant un **risque de sécurité majeur**.

## Localisation des logs

### Volume Docker
- **Volume** : `rhdemo-jenkins-home` (défini dans [docker-compose.yml](infra/jenkins-docker/docker-compose.yml))
- **Chemin conteneur** : `/var/jenkins_home/`
- **Chemin hôte** : `/var/lib/docker/volumes/rhdemo-jenkins-home/_data/`

### Logs des builds
```bash
# Logs d'un build spécifique
/var/lib/docker/volumes/rhdemo-jenkins-home/_data/jobs/<job-name>/builds/<build-number>/log

# Workspace contenant fichiers temporaires
/var/lib/docker/volumes/rhdemo-jenkins-home/_data/workspace/<job-name>/
```

## Corrections appliquées (commit d774841)

### 1. Suppression des affichages de secrets
- ❌ Supprimé : `echo "Début (cut): $(echo $SECRET | cut -c1-10)..."`
- ❌ Supprimé : `grep -A 2 "admin:" "${CONFIG_FILE}"` (affichait username/password)
- ❌ Supprimé : `grep "secret:" "${CONFIG_FILE}" | cut -c1-30`
- ✅ Remplacé par des messages génériques : "Configuration sensible créée (secrets non affichés pour sécurité)"

### 2. Protection des logs avec `set +x`
```bash
# Désactiver l'écho des commandes pendant manipulation des secrets
set +x
. rhDemo/secrets/env-vars.sh
export RHDEMO_DB_PASSWORD="${RHDEMO_DATASOURCE_PASSWORD_PG}"
set -x  # Réactiver pour traçabilité des commandes non sensibles
```

Sections protégées :
- Déchiffrement SOPS et création env-vars.sh
- Configuration rhDemoInitKeycloak (generation application-staging.yml)
- Déploiement Docker Compose (export variables d'environnement)
- Initialisation Keycloak (source des secrets)

### 3. Nettoyage sécurisé des fichiers temporaires

Ajout dans `post.always` :
```bash
# Écraser avec shred avant suppression (3 passes)
shred -vfz -n 3 rhDemo/secrets/env-vars.sh 2>/dev/null || rm -f rhDemo/secrets/env-vars.sh
shred -vfz -n 3 ${SECRETS_DECRYPTED} 2>/dev/null || rm -f ${SECRETS_DECRYPTED}
shred -vfz -n 3 rhDemoInitKeycloak/src/main/resources/application-staging.yml 2>/dev/null || \
    rm -f rhDemoInitKeycloak/src/main/resources/application-staging.yml
```

Fichiers nettoyés :
- `rhDemo/secrets/env-vars.sh` (mots de passe base de données, client-secret, Keycloak admin)
- `rhDemo/secrets/secrets-decrypted.yml` (secrets SOPS déchiffrés)
- `rhDemoInitKeycloak/src/main/resources/application-staging.yml` (configuration Keycloak avec secrets)

## Risques résiduels

### 1. Accès au volume Docker
**Risque** : Utilisateur avec accès root peut lire `/var/lib/docker/volumes/rhdemo-jenkins-home/_data/`

**Mitigation actuelle** :
- Nettoyage sécurisé des fichiers temporaires avec `shred`
- Suppression garantie même en cas d'échec du build (post.always)
- Pas d'affichage des secrets dans les logs

**Risque résiduel** :
- Les logs Jenkins historiques (builds précédents) peuvent contenir des secrets
- Accès root requis mais pas de chiffrement du volume

### 2. Logs dans le conteneur Jenkins
**Risque** : Logs accessibles depuis le conteneur Jenkins lui-même

**Mitigation recommandée** :
```bash
# Limiter les permissions du volume
sudo chmod 700 /var/lib/docker/volumes/rhdemo-jenkins-home/_data/
sudo chown -R 1000:1000 /var/lib/docker/volumes/rhdemo-jenkins-home/_data/
```

### 3. Rotation et archivage des logs
**Risque** : Accumulation des logs historiques contenant potentiellement des secrets

**Mitigation recommandée** :
- Implémenter rotation automatique des logs Jenkins
- Chiffrer les archives de logs avec GPG ou similaire
- Définir une politique de rétention (ex: 30 jours)

## Recommandations supplémentaires

### 1. Utiliser Jenkins Credentials Binding
Au lieu de fichiers temporaires `env-vars.sh`, utiliser directement les credentials Jenkins :

```groovy
withCredentials([
    string(credentialsId: 'rhdemo-db-password', variable: 'DB_PASSWORD'),
    string(credentialsId: 'keycloak-admin-password', variable: 'KEYCLOAK_ADMIN_PASSWORD')
]) {
    sh """
        docker-compose up -d
    """
}
```

**Avantages** :
- Secrets jamais écrits sur disque
- Masquage automatique dans les logs Jenkins
- Gestion centralisée des credentials

### 2. Chiffrement du volume Jenkins
```yaml
# docker-compose.yml
volumes:
  jenkins_home:
    driver: local
    driver_opts:
      type: none
      o: bind,encryption=aes256
      device: /opt/jenkins-encrypted
```

### 3. Plugin Jenkins Audit Trail
Activer le plugin pour tracer tous les accès aux logs :
```yaml
# jenkins-casc.yaml
unclassified:
  audit-trail:
    logFile: /var/jenkins_home/audit.log
    logBuildCause: true
    pattern: ".*"
```

### 4. Limiter l'accès aux logs
Dans [jenkins-casc.yaml](infra/jenkins-docker/jenkins-casc.yaml), configurer :
```yaml
jenkins:
  authorizationStrategy:
    projectMatrix:
      permissions:
        - "Job/Read:authenticated"
        - "Job/Build:authenticated"
        # NE PAS donner Job/Console aux utilisateurs non admin
        - "Job/Console:admin"
```

### 5. Scanner régulièrement les logs
Utiliser un outil comme `truffleHog` ou `gitleaks` pour détecter les secrets dans les logs :

```bash
# Script à exécuter périodiquement (cron)
docker run --rm -v rhdemo-jenkins-home:/data \
    trufflesecurity/trufflehog:latest \
    filesystem /data/jobs --json --no-verification
```

## Checklist de sécurité

- [x] Secrets non affichés dans les logs (echo, grep supprimés)
- [x] Protection avec `set +x` pendant manipulation des secrets
- [x] Nettoyage sécurisé avec `shred` dans post.always
- [ ] Permissions restrictives sur le volume Docker (chmod 700)
- [ ] Rotation automatique des logs Jenkins
- [ ] Chiffrement du volume jenkins_home
- [ ] Migration vers Jenkins Credentials Binding
- [ ] Audit trail des accès aux logs
- [ ] Scan régulier des secrets dans les logs historiques

## Références

- [Jenkins Security Best Practices](https://www.jenkins.io/doc/book/security/)
- [OWASP Top 10 - A02:2021 Cryptographic Failures](https://owasp.org/Top10/A02_2021-Cryptographic_Failures/)
- [Docker Secrets Management](https://docs.docker.com/engine/swarm/secrets/)
