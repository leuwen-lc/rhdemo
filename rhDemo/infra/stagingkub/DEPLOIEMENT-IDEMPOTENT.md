# Rendre le déploiement Kubernetes idempotent

## Problèmes identifiés

Suite au déploiement manuel, plusieurs problèmes d'idempotence ont été identifiés :

### 1. PostgreSQL : Mot de passe figé à l'initialisation
**Symptôme** : Erreur "password authentication failed" même avec les bons secrets
**Cause** : PostgreSQL initialise le mot de passe utilisateur uniquement au premier démarrage (quand PGDATA est vide). Les changements ultérieurs dans les secrets Kubernetes ne sont pas pris en compte.
**Impact** : Impossibilité de rotation des mots de passe sans suppression manuelle des PVC

### 2. Scripts d'init SQL non rejouables
**Symptôme** : Message "Database directory appears to contain a database; Skipping initialization"
**Cause** : Les scripts dans `/docker-entrypoint-initdb.d` ne sont exécutés qu'une seule fois, au premier démarrage
**Impact** : Modifications du schéma non appliquées lors des redéploiements

### 3. Pas de gestion de migrations de schéma
**Symptôme** : Erreur "Schema-validation: missing table [employes]"
**Cause** : Hibernate en mode `validate` mais pas de mécanisme de migration automatique
**Impact** : Nécessité d'intervenir manuellement pour créer/modifier les tables

---

## Solutions proposées

### Solution 1 : Job Kubernetes pour synchronisation des mots de passe PostgreSQL

Créer un Job qui s'exécute avant le déploiement et synchronise les mots de passe.

**Avantages** :
- Gère la rotation des mots de passe
- Idempotent (peut être réexécuté sans risque)
- Automatisé via Helm hooks

**Fichier** : `infra/stagingkub/helm/rhdemo/templates/postgresql-password-sync-job.yaml`

```yaml
{{- if (index .Values "postgresql-rhdemo").enabled }}
apiVersion: batch/v1
kind: Job
metadata:
  name: postgresql-rhdemo-password-sync-{{ .Release.Revision }}
  namespace: {{ .Values.global.namespace }}
  labels:
    app: postgresql-rhdemo
    component: password-sync
  annotations:
    # Exécuter AVANT le déploiement/mise à jour de l'application
    "helm.sh/hook": pre-upgrade,pre-install
    "helm.sh/hook-weight": "-5"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  ttlSecondsAfterFinished: 300
  template:
    metadata:
      name: postgresql-password-sync
    spec:
      restartPolicy: Never
      initContainers:
      # Attendre que PostgreSQL soit prêt
      - name: wait-for-db
        image: postgres:16-alpine
        command:
        - /bin/sh
        - -c
        - |
          until pg_isready -h {{ (index .Values "postgresql-rhdemo").database.host }} -U {{ (index .Values "postgresql-rhdemo").database.user }}; do
            echo "Waiting for PostgreSQL..."
            sleep 2
          done
          echo "PostgreSQL is ready"
      containers:
      - name: sync-password
        image: postgres:16-alpine
        env:
        - name: PGHOST
          value: {{ (index .Values "postgresql-rhdemo").database.host }}
        - name: PGPORT
          value: "{{ (index .Values "postgresql-rhdemo").service.port }}"
        - name: PGDATABASE
          value: {{ (index .Values "postgresql-rhdemo").database.name }}
        - name: PGUSER
          value: {{ (index .Values "postgresql-rhdemo").database.user }}
        - name: PGPASSWORD
          valueFrom:
            secretKeyRef:
              name: {{ (index .Values "postgresql-rhdemo").database.passwordSecret.name }}
              key: {{ (index .Values "postgresql-rhdemo").database.passwordSecret.key }}
        - name: NEW_PASSWORD
          valueFrom:
            secretKeyRef:
              name: {{ (index .Values "postgresql-rhdemo").database.passwordSecret.name }}
              key: {{ (index .Values "postgresql-rhdemo").database.passwordSecret.key }}
        command:
        - /bin/sh
        - -c
        - |
          set -e
          echo "🔑 Synchronisation du mot de passe PostgreSQL..."

          # Tenter de se connecter avec le mot de passe actuel
          if psql -c "SELECT 1" > /dev/null 2>&1; then
            echo "✅ Connexion réussie avec le mot de passe actuel"

            # Mettre à jour le mot de passe (idempotent)
            psql -c "ALTER USER ${PGUSER} WITH PASSWORD '${NEW_PASSWORD}';"
            echo "✅ Mot de passe synchronisé"
          else
            echo "⚠️  Impossible de se connecter - Le mot de passe nécessite une réinitialisation manuelle"
            echo "   Exécutez: kubectl delete statefulset postgresql-rhdemo -n {{ .Values.global.namespace }}"
            echo "   Puis: kubectl delete pvc postgresql-data-postgresql-rhdemo-0 -n {{ .Values.global.namespace }}"
            exit 1
          fi
{{- end }}
```

**Créer le même Job pour PostgreSQL Keycloak** : `postgresql-keycloak-password-sync-job.yaml`

---

### Solution 2 : Job Kubernetes pour migrations de schéma

Utiliser un Job Kubernetes qui applique les migrations de schéma avant chaque déploiement.

**Avantages** :
- Migrations versionnées et traçables
- Rejouable (idempotent si les migrations sont bien conçues)
- Exécuté automatiquement via Helm hooks

#### Option 2A : Job avec scripts SQL versionnés (Simple)

**Fichier** : `infra/stagingkub/helm/rhdemo/templates/schema-migration-job.yaml`

```yaml
{{- if (index .Values "postgresql-rhdemo").enabled }}
apiVersion: batch/v1
kind: Job
metadata:
  name: schema-migration-{{ .Release.Revision }}
  namespace: {{ .Values.global.namespace }}
  labels:
    app: rhdemo
    component: schema-migration
  annotations:
    "helm.sh/hook": pre-upgrade,pre-install
    "helm.sh/hook-weight": "0"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  ttlSecondsAfterFinished: 300
  template:
    metadata:
      name: schema-migration
    spec:
      restartPolicy: Never
      initContainers:
      - name: wait-for-db
        image: postgres:16-alpine
        command:
        - /bin/sh
        - -c
        - |
          until pg_isready -h {{ (index .Values "postgresql-rhdemo").database.host }} -U {{ (index .Values "postgresql-rhdemo").database.user }}; do
            echo "Waiting for PostgreSQL..."
            sleep 2
          done
      containers:
      - name: migrate
        image: postgres:16-alpine
        env:
        - name: PGHOST
          value: {{ (index .Values "postgresql-rhdemo").database.host }}
        - name: PGDATABASE
          value: {{ (index .Values "postgresql-rhdemo").database.name }}
        - name: PGUSER
          value: {{ (index .Values "postgresql-rhdemo").database.user }}
        - name: PGPASSWORD
          valueFrom:
            secretKeyRef:
              name: {{ (index .Values "postgresql-rhdemo").database.passwordSecret.name }}
              key: {{ (index .Values "postgresql-rhdemo").database.passwordSecret.key }}
        volumeMounts:
        - name: migrations
          mountPath: /migrations
        command:
        - /bin/sh
        - -c
        - |
          set -e
          echo "📊 Application des migrations de schéma..."

          # Créer la table de suivi des migrations si elle n'existe pas
          psql <<-EOSQL
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version VARCHAR(50) PRIMARY KEY,
              applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
          EOSQL

          # Appliquer chaque migration dans l'ordre
          for migration in /migrations/*.sql; do
            if [ -f "\$migration" ]; then
              version=\$(basename "\$migration" .sql)

              # Vérifier si déjà appliquée
              if psql -tA -c "SELECT 1 FROM schema_migrations WHERE version='\$version'" | grep -q 1; then
                echo "⏭️  Migration \$version déjà appliquée"
              else
                echo "▶️  Application de la migration \$version"
                psql -f "\$migration"
                psql -c "INSERT INTO schema_migrations (version) VALUES ('\$version')"
                echo "✅ Migration \$version appliquée"
              fi
            fi
          done

          echo "✅ Toutes les migrations sont appliquées"
      volumes:
      - name: migrations
        configMap:
          name: schema-migrations
{{- end }}
```

**Fichier** : `infra/stagingkub/helm/rhdemo/templates/schema-migrations-configmap.yaml`

```yaml
{{- if (index .Values "postgresql-rhdemo").enabled }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: schema-migrations
  namespace: {{ .Values.global.namespace }}
  labels:
    app: rhdemo
    component: schema-migration
data:
  # Numérotation : YYYYMMDD-HHmm-description.sql
  20251218-0001-initial-schema.sql: |
    -- Migration initiale : création de la table employes
    CREATE TABLE IF NOT EXISTS employes (
      id BIGSERIAL PRIMARY KEY,
      prenom VARCHAR(250) NOT NULL,
      nom VARCHAR(250) NOT NULL,
      mail VARCHAR(250) NOT NULL,
      adresse VARCHAR(500)
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_employes_mail ON employes(mail);
    CREATE INDEX IF NOT EXISTS idx_employes_nom ON employes(nom);
    CREATE INDEX IF NOT EXISTS idx_employes_prenom ON employes(prenom);
    CREATE INDEX IF NOT EXISTS idx_employes_nom_prenom ON employes(nom, prenom);
    CREATE INDEX IF NOT EXISTS idx_employes_adresse ON employes(adresse) WHERE adresse IS NOT NULL;

  # Exemple de migration future
  # 20251220-1000-add-phone-column.sql: |
  #   -- Ajout d'une colonne téléphone
  #   ALTER TABLE employes ADD COLUMN IF NOT EXISTS telephone VARCHAR(20);
  #   CREATE INDEX IF NOT EXISTS idx_employes_telephone ON employes(telephone);
{{- end }}
```

#### Option 2B : Utiliser Flyway ou Liquibase (Recommandé pour production)

**Avantages supplémentaires** :
- Gestion avancée des migrations (rollback, validation, reporting)
- Support de migrations Java pour logique complexe
- Intégration native avec Spring Boot

**Fichier** : `infra/stagingkub/helm/rhdemo/templates/flyway-migration-job.yaml`

```yaml
{{- if (index .Values "postgresql-rhdemo").enabled }}
apiVersion: batch/v1
kind: Job
metadata:
  name: flyway-migration-{{ .Release.Revision }}
  namespace: {{ .Values.global.namespace }}
  labels:
    app: rhdemo
    component: flyway-migration
  annotations:
    "helm.sh/hook": pre-upgrade,pre-install
    "helm.sh/hook-weight": "0"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  ttlSecondsAfterFinished: 300
  template:
    metadata:
      name: flyway-migration
    spec:
      restartPolicy: Never
      initContainers:
      - name: wait-for-db
        image: postgres:16-alpine
        command:
        - /bin/sh
        - -c
        - |
          until pg_isready -h {{ (index .Values "postgresql-rhdemo").database.host }} -U {{ (index .Values "postgresql-rhdemo").database.user }}; do
            echo "Waiting for PostgreSQL..."
            sleep 2
          done
      containers:
      - name: flyway
        image: flyway/flyway:10-alpine
        env:
        - name: FLYWAY_URL
          value: "jdbc:postgresql://{{ (index .Values "postgresql-rhdemo").database.host }}:{{ (index .Values "postgresql-rhdemo").service.port }}/{{ (index .Values "postgresql-rhdemo").database.name }}"
        - name: FLYWAY_USER
          value: {{ (index .Values "postgresql-rhdemo").database.user }}
        - name: FLYWAY_PASSWORD
          valueFrom:
            secretKeyRef:
              name: {{ (index .Values "postgresql-rhdemo").database.passwordSecret.name }}
              key: {{ (index .Values "postgresql-rhdemo").database.passwordSecret.key }}
        - name: FLYWAY_LOCATIONS
          value: "filesystem:/flyway/sql"
        - name: FLYWAY_BASELINE_ON_MIGRATE
          value: "true"
        volumeMounts:
        - name: migrations
          mountPath: /flyway/sql
        command:
        - flyway
        - migrate
      volumes:
      - name: migrations
        configMap:
          name: flyway-migrations
{{- end }}
```

**Fichier** : `infra/stagingkub/helm/rhdemo/templates/flyway-migrations-configmap.yaml`

```yaml
{{- if (index .Values "postgresql-rhdemo").enabled }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: flyway-migrations
  namespace: {{ .Values.global.namespace }}
  labels:
    app: rhdemo
    component: flyway-migration
data:
  # Flyway utilise la convention : V{version}__{description}.sql
  V1__initial_schema.sql: |
    CREATE TABLE IF NOT EXISTS employes (
      id BIGSERIAL PRIMARY KEY,
      prenom VARCHAR(250) NOT NULL,
      nom VARCHAR(250) NOT NULL,
      mail VARCHAR(250) NOT NULL,
      adresse VARCHAR(500)
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_employes_mail ON employes(mail);
    CREATE INDEX IF NOT EXISTS idx_employes_nom ON employes(nom);
    CREATE INDEX IF NOT EXISTS idx_employes_prenom ON employes(prenom);
    CREATE INDEX IF NOT EXISTS idx_employes_nom_prenom ON employes(nom, prenom);
    CREATE INDEX IF NOT EXISTS idx_employes_adresse ON employes(adresse) WHERE adresse IS NOT NULL;

  # Exemple de migration future
  # V2__add_phone_column.sql: |
  #   ALTER TABLE employes ADD COLUMN IF NOT EXISTS telephone VARCHAR(20);
  #   CREATE INDEX IF NOT EXISTS idx_employes_telephone ON employes(telephone);
{{- end }}
```

---

### Solution 3 : InitContainer pour l'application rhDemo

Au lieu de faire confiance au mode Hibernate `validate`, utiliser un initContainer qui vérifie/crée le schéma.

**Modification** : `infra/stagingkub/helm/rhdemo/templates/rhdemo-app-deployment.yaml`

Ajouter après le `wait-for-keycloak` initContainer :

```yaml
      - name: init-schema
        image: postgres:16-alpine
        env:
        - name: PGHOST
          value: {{ .Values.rhdemo.database.host }}
        - name: PGPORT
          value: "{{ .Values.rhdemo.database.port }}"
        - name: PGDATABASE
          value: {{ .Values.rhdemo.database.name }}
        - name: PGUSER
          value: {{ .Values.rhdemo.database.user }}
        - name: PGPASSWORD
          valueFrom:
            secretKeyRef:
              name: {{ .Values.rhdemo.database.passwordSecret.name }}
              key: {{ .Values.rhdemo.database.passwordSecret.key }}
        command:
        - /bin/sh
        - -c
        - |
          set -e
          echo "🔍 Vérification du schéma de base de données..."

          # Vérifier si la table employes existe
          if psql -tA -c "SELECT 1 FROM pg_tables WHERE tablename='employes'" | grep -q 1; then
            echo "✅ Le schéma existe déjà"
          else
            echo "⚠️  Le schéma n'existe pas - création en cours..."
            psql <<-EOSQL
              CREATE TABLE employes (
                id BIGSERIAL PRIMARY KEY,
                prenom VARCHAR(250) NOT NULL,
                nom VARCHAR(250) NOT NULL,
                mail VARCHAR(250) NOT NULL,
                adresse VARCHAR(500)
              );
              CREATE UNIQUE INDEX idx_employes_mail ON employes(mail);
              CREATE INDEX idx_employes_nom ON employes(nom);
              CREATE INDEX idx_employes_prenom ON employes(prenom);
              CREATE INDEX idx_employes_nom_prenom ON employes(nom, prenom);
              CREATE INDEX idx_employes_adresse ON employes(adresse) WHERE adresse IS NOT NULL;
          EOSQL
            echo "✅ Schéma créé avec succès"
          fi
```

---

### Solution 4 : Améliorer la configuration Hibernate

Modifier `application-stagingkub.yml` pour utiliser Hibernate en mode `update` ou intégrer Flyway.

#### Option 4A : Mode Hibernate update (simple mais limité)

```yaml
spring:
  jpa:
    hibernate:
      ddl-auto: update  # Au lieu de validate
```

**Avantages** : Simple, automatique
**Inconvénients** :
- Pas de rollback
- Peut créer des colonnes orphelines
- Dangereux en production

#### Option 4B : Intégration Flyway dans l'application (Recommandé)

**Fichier** : `pom.xml` - Ajouter la dépendance

```xml
<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-core</artifactId>
</dependency>
<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-database-postgresql</artifactId>
</dependency>
```

**Fichier** : `src/main/resources/application-stagingkub.yml`

```yaml
spring:
  flyway:
    enabled: true
    baseline-on-migrate: true
    locations: classpath:db/migration
  jpa:
    hibernate:
      ddl-auto: validate  # Garde validate, Flyway gère les migrations
```

**Créer** : `src/main/resources/db/migration/V1__initial_schema.sql`

```sql
CREATE TABLE IF NOT EXISTS employes (
  id BIGSERIAL PRIMARY KEY,
  prenom VARCHAR(250) NOT NULL,
  nom VARCHAR(250) NOT NULL,
  mail VARCHAR(250) NOT NULL,
  adresse VARCHAR(500)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_employes_mail ON employes(mail);
CREATE INDEX IF NOT EXISTS idx_employes_nom ON employes(nom);
CREATE INDEX IF NOT EXISTS idx_employes_prenom ON employes(prenom);
CREATE INDEX IF NOT EXISTS idx_employes_nom_prenom ON employes(nom, prenom);
CREATE INDEX IF NOT EXISTS idx_employes_adresse ON employes(adresse) WHERE adresse IS NOT NULL;
```

**Avantages** :
- Migrations gérées dans le code source
- Versionnement avec Git
- Exécution automatique au démarrage de l'application
- Support de migrations Java pour logique complexe

---

### Solution 5 : Améliorer le pipeline CD

Ajouter des étapes de vérification et de rollback automatique.

**Fichier** : `Jenkinsfile-CD`

Ajouter après le déploiement Helm :

```groovy
stage('🔍 Vérification Santé Déploiement') {
    steps {
        script {
            sh """
                # Attendre que tous les pods soient Ready
                kubectl wait --for=condition=ready pod \
                    -l app.kubernetes.io/instance=rhdemo \
                    -n rhdemo-stagingkub \
                    --timeout=300s || {
                    echo "❌ Échec de la vérification de santé"
                    echo "🔄 Rollback automatique..."
                    helm rollback rhdemo -n rhdemo-stagingkub
                    exit 1
                }

                # Vérifier les endpoints actuator
                kubectl exec -n rhdemo-stagingkub \
                    deployment/rhdemo-app -- \
                    curl -f http://localhost:9000/actuator/health || {
                    echo "❌ Health check échoué"
                    helm rollback rhdemo -n rhdemo-stagingkub
                    exit 1
                }

                echo "✅ Déploiement vérifié et fonctionnel"
            """
        }
    }
}

stage('🧪 Tests de Fumée') {
    steps {
        script {
            sh """
                # Tests basiques pour vérifier que l'application fonctionne
                echo "Test 1: Vérification de la connexion à la base de données"
                kubectl exec -n rhdemo-stagingkub deployment/rhdemo-app -- \
                    curl -f http://localhost:9000/actuator/health/db

                echo "Test 2: Vérification de Keycloak"
                kubectl exec -n rhdemo-stagingkub deployment/rhdemo-app -- \
                    curl -f http://localhost:9000/actuator/health/ping

                echo "✅ Tests de fumée réussis"
            """
        }
    }
}
```

---

## Recommandations par ordre de priorité

### Priorité 1 - Quick wins (impact immédiat, effort faible)

1. **Ajouter InitContainer de vérification de schéma** (Solution 3)
   - Temps d'implémentation : 15 minutes
   - Résout immédiatement le problème de schéma manquant
   - Aucun changement dans l'application

2. **Améliorer le pipeline CD avec health checks** (Solution 5)
   - Temps d'implémentation : 30 minutes
   - Détecte les problèmes avant qu'ils n'impactent
   - Rollback automatique

### Priorité 2 - Court terme (1-2 jours)

3. **Job de synchronisation des mots de passe** (Solution 1)
   - Temps d'implémentation : 1-2 heures
   - Permet la rotation des secrets
   - Évite les interventions manuelles

4. **Job de migration SQL simple** (Solution 2A)
   - Temps d'implémentation : 2-3 heures
   - Gestion basique des migrations
   - Traçabilité des changements de schéma

### Priorité 3 - Moyen terme (1 semaine)

5. **Intégration Flyway dans l'application** (Solution 4B)
   - Temps d'implémentation : 1 journée
   - Solution robuste et standard de l'industrie
   - Migrations versionnées avec le code

6. **Job Flyway Kubernetes** (Solution 2B)
   - Temps d'implémentation : 3-4 heures
   - Alternative si Flyway ne peut pas être intégré dans l'app
   - Plus flexible que les scripts SQL simples

---

## Plan d'action proposé

### Phase 1 : Stabilisation immédiate (aujourd'hui)
- [ ] Ajouter l'initContainer `init-schema` à `rhdemo-app-deployment.yaml`
- [ ] Tester le redéploiement
- [ ] Commit et push

### Phase 2 : Sécurisation (cette semaine)
- [ ] Implémenter le Job de synchronisation des mots de passe PostgreSQL
- [ ] Ajouter les health checks au pipeline CD
- [ ] Ajouter le rollback automatique
- [ ] Tester un déploiement complet

### Phase 3 : Industrialisation (semaine prochaine)
- [ ] Intégrer Flyway dans l'application rhDemo
- [ ] Migrer les scripts SQL dans `src/main/resources/db/migration/`
- [ ] Supprimer le ConfigMap `postgresql-rhdemo-init`
- [ ] Documenter le processus de création de nouvelles migrations

---

## Tests de validation

Pour valider que le déploiement est idempotent :

```bash
# Test 1 : Déploiement initial
helm install rhdemo ./helm/rhdemo -n rhdemo-stagingkub
kubectl wait --for=condition=ready pod -l app=rhdemo-app -n rhdemo-stagingkub --timeout=300s

# Test 2 : Redéploiement sans changement (doit être idempotent)
helm upgrade rhdemo ./helm/rhdemo -n rhdemo-stagingkub
kubectl wait --for=condition=ready pod -l app=rhdemo-app -n rhdemo-stagingkub --timeout=300s

# Test 3 : Changement de mot de passe
kubectl create secret generic rhdemo-db-secret \
  --from-literal=password=new-password-123 \
  -n rhdemo-stagingkub --dry-run=client -o yaml | kubectl apply -f -
helm upgrade rhdemo ./helm/rhdemo -n rhdemo-stagingkub
# Vérifier que l'application se connecte avec le nouveau mot de passe

# Test 4 : Ajout d'une migration
# Ajouter V2__add_column.sql
helm upgrade rhdemo ./helm/rhdemo -n rhdemo-stagingkub
# Vérifier que la migration est appliquée

# Test 5 : Rollback
helm rollback rhdemo -n rhdemo-stagingkub
kubectl wait --for=condition=ready pod -l app=rhdemo-app -n rhdemo-stagingkub --timeout=300s
```

---

## Références

- [PostgreSQL Docker Hub - Environment Variables](https://hub.docker.com/_/postgres)
- [Flyway Documentation](https://flywaydb.org/documentation/)
- [Helm Hooks](https://helm.sh/docs/topics/charts_hooks/)
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Spring Boot Flyway Integration](https://docs.spring.io/spring-boot/docs/current/reference/html/howto.html#howto.data-initialization.migration-tool.flyway)
