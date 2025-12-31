# 📦 Helm Chart RHDemo - Documentation complète

Ce document explique en détail le contenu du Helm Chart RHDemo et toutes les ressources Kubernetes créées.

---

## 📋 Table des matières

- [Qu'est-ce que Helm ?](#quest-ce-que-helm-)
- [Structure du Chart](#structure-du-chart)
- [Fichiers de configuration](#fichiers-de-configuration)
- [Templates Kubernetes](#templates-kubernetes)
- [Variables et personnalisation](#variables-et-personnalisation)
- [Déploiement et mise à jour](#déploiement-et-mise-à-jour)

---

## 🎯 Qu'est-ce que Helm ?

### Définition

**Helm** est le gestionnaire de packages pour Kubernetes. C'est l'équivalent de :
- `apt/yum` pour Linux
- `npm` pour Node.js
- `pip` pour Python
- `maven` pour Java

### Pourquoi Helm ?

**Sans Helm** (Kubernetes natif) :
```bash
kubectl apply -f namespace.yaml
kubectl apply -f secret1.yaml
kubectl apply -f secret2.yaml
kubectl apply -f configmap.yaml
kubectl apply -f statefulset1.yaml
kubectl apply -f statefulset2.yaml
kubectl apply -f deployment1.yaml
kubectl apply -f deployment2.yaml
kubectl apply -f service1.yaml
kubectl apply -f service2.yaml
kubectl apply -f service3.yaml
kubectl apply -f service4.yaml
kubectl apply -f ingress.yaml
# ... 15+ fichiers à gérer manuellement
```

**Avec Helm** :
```bash
helm install rhdemo ./helm/rhdemo
# Déploie tout d'un coup, dans le bon ordre
```

### Concepts clés

| Concept | Description |
|---------|-------------|
| **Chart** | Package Helm (= ensemble de templates Kubernetes) |
| **Release** | Instance déployée d'un chart (ex: `rhdemo`) |
| **Values** | Fichier de configuration (values.yaml) |
| **Template** | Fichier Kubernetes avec variables Helm |
| **Repository** | Dépôt de charts (comme DockerHub pour les images) |

---

## 📁 Structure du Chart

```
helm/rhdemo/
├── Chart.yaml              # Métadonnées du chart
├── values.yaml             # Configuration par défaut
├── templates/              # Templates Kubernetes
│   ├── _helpers.tpl        # Fonctions réutilisables
│   ├── namespace.yaml      # Namespace rhdemo-stagingkub
│   ├── postgresql-rhdemo-* # PostgreSQL pour RHDemo (3 fichiers)
│   ├── postgresql-keycloak-* # PostgreSQL pour Keycloak (2 fichiers)
│   ├── keycloak-*          # Keycloak (2 fichiers)
│   ├── rhdemo-app-*        # Application RHDemo (2 fichiers)
│   ├── ingress.yaml        # Exposition HTTPS
│   └── NOTES.txt           # Message post-déploiement
└── README.md               # Ce fichier
```

**Total** : 16 fichiers

---

## 📄 Fichiers de configuration

### 1. Chart.yaml

**Rôle** : Métadonnées du chart (nom, version, description)

```yaml
apiVersion: v2                    # Version de l'API Helm
name: rhdemo                      # Nom du chart
description: RHDemo Application   # Description
type: application                 # Type: application (vs library)
version: 1.0.0                    # Version du chart (incrémente à chaque modif)
appVersion: "1.1.0-SNAPSHOT"      # Version de l'app déployée
```

**Commandes utiles** :
```bash
# Voir les infos du chart
helm show chart ./helm/rhdemo

# Lister les charts installés
helm list -n rhdemo-stagingkub
```

---

### 2. values.yaml

**Rôle** : Configuration par défaut du déploiement

Ce fichier contient **TOUTES** les valeurs configurables :

#### Structure du values.yaml

```yaml
global:                           # Variables globales
  namespace: rhdemo-stagingkub       # Namespace Kubernetes
  environment: stagingkub            # Environnement (staging/prod)
  domain: stagingkub.local           # Domaine DNS

postgresql-rhdemo:                # Config PostgreSQL RHDemo
  enabled: true                   # Activer ce composant ?
  image:
    repository: postgres          # Image Docker
    tag: "16-alpine"              # Version
  database:
    name: rhdemo                  # Nom de la base
    user: rhdemo                  # Utilisateur
  persistence:
    size: 2Gi                     # Taille du volume
  resources:                      # Limites CPU/RAM
    requests:
      memory: "256Mi"
      cpu: "250m"

postgresql-keycloak:              # Config PostgreSQL Keycloak
  # ... (structure identique)

keycloak:                         # Config Keycloak
  enabled: true
  image:
    repository: quay.io/keycloak/keycloak
    tag: "26.4.2"
  replicaCount: 1                 # Nombre de pods
  admin:
    user: admin
  hostname:
    url: https://keycloak.stagingkub.local
  resources:                      # Plus de ressources que les DB
    requests:
      memory: "512Mi"
      cpu: "500m"

rhdemo:                           # Config Application RHDemo
  enabled: true
  image:
    repository: rhdemo-api        # Sera remplacé par localhost:5000/rhdemo-api
    tag: "1.1.0-SNAPSHOT"
  replicaCount: 1
  springProfile: ephemere
  serverPort: 9000
  jvm:                            # Config JVM
    threadCount: 50
    maxRamPercentage: 75.0
    gcType: G1GC

ingress:                          # Config Ingress (exposition HTTPS)
  enabled: true
  className: nginx
  hosts:
    - host: rhdemo.stagingkub.local
    - host: keycloak.stagingkub.local
  tls:
    enabled: true
```

**Comment personnaliser** :

```bash
# Méthode 1 : Modifier values.yaml directement
vim helm/rhdemo/values.yaml

# Méthode 2 : Créer un fichier custom
cat > values-custom.yaml <<EOF
rhdemo:
  replicaCount: 2              # 2 pods au lieu de 1
  resources:
    requests:
      memory: "1Gi"            # Plus de RAM
EOF

helm upgrade rhdemo ./helm/rhdemo \
  --values values-custom.yaml

# Méthode 3 : Override via CLI (recommandé pour CI/CD)
helm upgrade rhdemo ./helm/rhdemo \
  --set rhdemo.replicaCount=2 \
  --set rhdemo.image.tag=1.2.0-SNAPSHOT
```

---

## 🏗️ Templates Kubernetes

Chaque template génère une ressource Kubernetes. Helm remplace les variables `{{ .Values.xxx }}` par les valeurs du `values.yaml`.

### Template 1 : namespace.yaml

**Rôle** : Crée le namespace `rhdemo-stagingkub`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: {{ .Values.global.namespace }}    # → rhdemo-stagingkub
  labels:
    {{- include "rhdemo.labels" . | nindent 4 }}
    name: {{ .Values.global.namespace }}
```

**Résultat après templating** :
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: rhdemo-stagingkub
  labels:
    app.kubernetes.io/name: rhdemo
    app.kubernetes.io/instance: rhdemo
    environment: ephemere
```

**Qu'est-ce qu'un Namespace ?**
- C'est comme un "dossier" dans Kubernetes
- Isole les ressources (un namespace = un environnement)
- Permet de gérer les droits (RBAC)

**Commandes** :
```bash
# Lister les namespaces
kubectl get namespaces

# Lister toutes les ressources dans un namespace
kubectl get all -n rhdemo-stagingkub
```

---

### Template 2-4 : PostgreSQL RHDemo

#### A) postgresql-rhdemo-statefulset.yaml

**Rôle** : Déploie PostgreSQL pour la base de données RHDemo

```yaml
apiVersion: apps/v1
kind: StatefulSet                # StatefulSet (pas Deployment)
metadata:
  name: postgresql-rhdemo
  namespace: {{ .Values.global.namespace }}
spec:
  serviceName: postgresql-rhdemo  # Lien avec le Service
  replicas: 1                     # 1 seul pod (DB = pas de réplication)
  selector:
    matchLabels:
      app: postgresql-rhdemo      # Selector = comment trouver les pods
  template:
    metadata:
      labels:
        app: postgresql-rhdemo    # Labels du pod
    spec:
      containers:
      - name: postgresql
        image: "{{ .Values.postgresql-rhdemo.image.repository }}:{{ .Values.postgresql-rhdemo.image.tag }}"
        # → postgres:16-alpine
        ports:
        - name: postgresql
          containerPort: 5432     # Port PostgreSQL
        env:
        - name: POSTGRES_DB
          value: {{ .Values.postgresql-rhdemo.database.name }}  # → rhdemo
        - name: POSTGRES_USER
          value: {{ .Values.postgresql-rhdemo.database.user }}  # → rhdemo
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:         # Récupère depuis un Secret
              name: rhdemo-db-secret
              key: password
        volumeMounts:
        - name: postgresql-data
          mountPath: /var/lib/postgresql/data  # Données persistantes
        livenessProbe:            # Probe de santé
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U rhdemo
          initialDelaySeconds: 30
          periodSeconds: 10
  volumeClaimTemplates:           # Template pour créer un PVC
  - metadata:
      name: postgresql-data
    spec:
      accessModes:
      - ReadWriteOnce             # 1 seul pod peut écrire
      resources:
        requests:
          storage: 2Gi            # Taille du volume
```

**Concepts clés** :

| Concept | Explication |
|---------|-------------|
| **StatefulSet** | Comme un Deployment, mais pour des apps avec état (DB, cache). Garantit un nom de pod stable, un stockage persistant. |
| **volumeMounts** | Monte un volume dans le container (comme `docker -v`) |
| **volumeClaimTemplates** | Demande automatique de stockage (PVC) pour chaque pod |
| **livenessProbe** | Kubernetes vérifie si le container est vivant. Si échec → redémarre le pod |
| **secretKeyRef** | Récupère une valeur depuis un Secret (jamais de mot de passe en clair !) |

**Commandes** :
```bash
# Voir le StatefulSet
kubectl get statefulset -n rhdemo-stagingkub

# Voir les pods créés
kubectl get pods -n rhdemo-stagingkub -l app=postgresql-rhdemo

# Se connecter au pod PostgreSQL
kubectl exec -it postgresql-rhdemo-0 -n rhdemo-stagingkub -- psql -U rhdemo -d rhdemo
```

---

#### B) postgresql-rhdemo-service.yaml

**Rôle** : Expose PostgreSQL en interne (ClusterIP)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgresql-rhdemo
  namespace: {{ .Values.global.namespace }}
spec:
  type: ClusterIP              # Accessible uniquement dans le cluster
  ports:
  - name: postgresql
    port: 5432                 # Port du service
    targetPort: postgresql     # Port du container (aussi 5432)
  selector:
    app: postgresql-rhdemo     # Route vers les pods avec ce label
  clusterIP: None              # Headless service (pour StatefulSet)
```

**Qu'est-ce qu'un Service ?**
- Expose un ensemble de pods sous un nom DNS stable
- Types :
  - **ClusterIP** : Interne uniquement (DB, cache)
  - **NodePort** : Expose sur un port du node (30000-32767)
  - **LoadBalancer** : Expose via un load balancer externe (AWS ELB, GCP LB)
  - **Headless** (clusterIP: None) : Pas de load balancing, accès direct aux pods

**Pourquoi Headless pour les DB ?**
- StatefulSet crée des pods avec des noms stables : `postgresql-rhdemo-0`
- Un service headless permet d'y accéder directement via DNS : `postgresql-rhdemo-0.postgresql-rhdemo.rhdemo-stagingkub.svc.cluster.local`

**Commandes** :
```bash
# Lister les services
kubectl get svc -n rhdemo-stagingkub

# Tester la connexion depuis un autre pod
kubectl run -it --rm debug --image=postgres:16-alpine -n rhdemo-stagingkub -- \
  psql -h postgresql-rhdemo -U rhdemo -d rhdemo
```

---

#### C) postgresql-rhdemo-configmap.yaml

**Rôle** : Contient les scripts d'initialisation de la base de données

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgresql-rhdemo-init
  namespace: {{ .Values.global.namespace }}
data:
  init-db.sql: |                 # Fichier SQL d'initialisation
    -- Script d'initialisation pour la base de données RHDemo
    -- Ce fichier sera exécuté automatiquement au premier démarrage

    \echo 'Database rhdemo initialized'
```

**Qu'est-ce qu'un ConfigMap ?**
- Stocke des données de configuration (non sensibles)
- Peut être monté comme volume ou injecté comme variables d'env
- Différence avec Secret : ConfigMap = données en clair, Secret = données encodées base64

**PostgreSQL et InitDB** :
- Les fichiers dans `/docker-entrypoint-initdb.d/` sont exécutés au **premier démarrage uniquement**
- Le ConfigMap est monté dans le pod PostgreSQL à cet emplacement

**Commandes** :
```bash
# Voir le ConfigMap
kubectl get configmap -n rhdemo-stagingkub

# Voir le contenu
kubectl describe configmap postgresql-rhdemo-init -n rhdemo-stagingkub
```

---

### Template 5-6 : PostgreSQL Keycloak

Structure identique à PostgreSQL RHDemo, mais pour Keycloak :
- `postgresql-keycloak-statefulset.yaml`
- `postgresql-keycloak-service.yaml`

**Différences** :
- Base de données : `keycloak`
- Utilisateur : `keycloak`
- Secret : `keycloak-db-secret`

---

### Template 7-8 : Keycloak

#### A) keycloak-deployment.yaml

**Rôle** : Déploie Keycloak (serveur d'authentification)

```yaml
apiVersion: apps/v1
kind: Deployment               # Deployment (pas StatefulSet)
metadata:
  name: keycloak
  namespace: {{ .Values.global.namespace }}
spec:
  replicas: {{ .Values.keycloak.replicaCount }}  # → 1
  selector:
    matchLabels:
      app: keycloak
  template:
    metadata:
      labels:
        app: keycloak
    spec:
      initContainers:          # Container qui s'exécute AVANT le main
      - name: wait-for-db
        image: busybox:1.36
        command: ['sh', '-c', 'until nc -z postgresql-keycloak 5432; do echo waiting; sleep 2; done;']
        # Attend que PostgreSQL soit prêt

      containers:
      - name: keycloak
        image: "{{ .Values.keycloak.image.repository }}:{{ .Values.keycloak.image.tag }}"
        # → quay.io/keycloak/keycloak:26.4.2
        args:                  # Arguments de démarrage Keycloak
        - start-dev            # Mode dev (pas de TLS obligatoire)
        - --db=postgres
        - --db-url=jdbc:postgresql://postgresql-keycloak:5432/keycloak
        - --db-username=keycloak
        - --proxy-headers=xforwarded    # Keycloak derrière proxy (Nginx)
        - --http-enabled=true
        - --health-enabled=true
        - --metrics-enabled=true
        ports:
        - name: http
          containerPort: 8080  # Port Keycloak
        env:
        - name: KEYCLOAK_ADMIN
          value: {{ .Values.keycloak.admin.user }}  # → admin
        - name: KEYCLOAK_ADMIN_PASSWORD
          valueFrom:
            secretKeyRef:
              name: keycloak-admin-secret
              key: password
        - name: KC_DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: keycloak-db-secret
              key: password
        - name: KC_HOSTNAME_URL
          value: {{ .Values.keycloak.hostname.url }}
          # → https://keycloak.stagingkub.local
        livenessProbe:
          httpGet:
            path: /health/live
            port: http
          initialDelaySeconds: 60
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: http
          initialDelaySeconds: 60
```

**Concepts clés** :

| Concept | Explication |
|---------|-------------|
| **Deployment** | Crée et gère des pods identiques. Pour apps stateless. Supporte rolling updates. |
| **initContainers** | Containers qui s'exécutent AVANT le main container. Utile pour attendre des dépendances (DB, config, etc.) |
| **livenessProbe** | Kubernetes vérifie si l'app est vivante. Si échec → redémarre |
| **readinessProbe** | Kubernetes vérifie si l'app est prête à recevoir du trafic. Si échec → retire du Service (pas de redémarrage) |
| **args** | Arguments passés au container (équivalent CMD dans Docker) |

**Deployment vs StatefulSet** :

| Aspect | Deployment | StatefulSet |
|--------|-----------|-------------|
| **Nom des pods** | Random (keycloak-6d8f4-xxx) | Stable (postgresql-0, postgresql-1) |
| **Ordre démarrage** | Parallèle | Séquentiel (0 → 1 → 2) |
| **Stockage** | Partagé ou éphémère | PVC individuel par pod |
| **Use case** | Apps stateless (API, front) | Apps stateful (DB, cache) |

**Commandes** :
```bash
# Voir le Deployment
kubectl get deployment -n rhdemo-stagingkub

# Voir les ReplicaSets (créés par le Deployment)
kubectl get replicaset -n rhdemo-stagingkub

# Scaler horizontalement
kubectl scale deployment keycloak --replicas=2 -n rhdemo-stagingkub

# Rolling update (changer l'image)
kubectl set image deployment/keycloak keycloak=quay.io/keycloak/keycloak:27.0.0 -n rhdemo-stagingkub
```

---

#### B) keycloak-service.yaml

**Rôle** : Expose Keycloak en interne

```yaml
apiVersion: v1
kind: Service
metadata:
  name: keycloak
  namespace: {{ .Values.global.namespace }}
spec:
  type: ClusterIP
  ports:
  - name: http
    port: 8080
    targetPort: http
  selector:
    app: keycloak
```

---

### Template 9-10 : Application RHDemo

#### A) rhdemo-app-deployment.yaml

**Rôle** : Déploie l'application Spring Boot

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rhdemo-app
  namespace: {{ .Values.global.namespace }}
spec:
  replicas: {{ .Values.rhdemo.replicaCount }}
  selector:
    matchLabels:
      app: rhdemo-app
  template:
    metadata:
      labels:
        app: rhdemo-app
    spec:
      initContainers:
      - name: wait-for-db
        image: busybox:1.36
        command: ['sh', '-c', 'until nc -z postgresql-rhdemo 5432; do sleep 2; done;']
      - name: wait-for-keycloak
        image: busybox:1.36
        command: ['sh', '-c', 'until nc -z keycloak 8080; do sleep 2; done;']

      containers:
      - name: rhdemo-app
        image: "{{ .Values.rhdemo.image.repository }}:{{ .Values.rhdemo.image.tag }}"
        # → localhost:5000/rhdemo-api:1.1.0-SNAPSHOT (override via --set)
        ports:
        - name: http
          containerPort: 9000
        env:
        # Configuration Spring Boot
        - name: SPRING_PROFILES_ACTIVE
          value: {{ .Values.rhdemo.springProfile }}  # → staging
        - name: SERVER_PORT
          value: "9000"
        - name: SPRING_DATASOURCE_URL
          value: "jdbc:postgresql://postgresql-rhdemo:5432/rhdemo"
        - name: SPRING_DATASOURCE_USERNAME
          value: rhdemo
        - name: SPRING_DATASOURCE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: rhdemo-db-secret
              key: password

        # JVM Options (Paketo Buildpacks)
        - name: BPL_JVM_THREAD_COUNT
          value: "50"
        - name: JAVA_TOOL_OPTIONS
          value: "-XX:MaxRAMPercentage=75.0 -XX:+UseG1GC"

        volumeMounts:
        - name: secrets
          mountPath: /workspace/secrets  # secrets-rhdemo.yml
          readOnly: true

        livenessProbe:
          httpGet:
            path: /actuator/health/liveness
            port: http
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: http
          initialDelaySeconds: 60

      volumes:
      - name: secrets
        secret:
          secretName: rhdemo-app-secrets
          items:
          - key: secrets-rhdemo.yml
            path: secrets-rhdemo.yml
```

**Configuration Spring Boot via environnement** :
- Les variables `SPRING_*` sont automatiquement lues par Spring Boot
- Équivalent de `application-ephemere.properties`
- Permet de surcharger la config sans rebuild

**Volumes et Secrets** :
- Le Secret `rhdemo-app-secrets` contient `secrets-rhdemo.yml`
- Monté comme fichier dans `/workspace/secrets/`
- Spring Boot le charge via `spring.config.import`

---

#### B) rhdemo-app-service.yaml

```yaml
apiVersion: v1
kind: Service
metadata:
  name: rhdemo-app
  namespace: {{ .Values.global.namespace }}
spec:
  type: ClusterIP
  ports:
  - name: http
    port: 9000
    targetPort: http
  selector:
    app: rhdemo-app
```

---

### Template 11 : ingress.yaml

**Rôle** : Expose l'application et Keycloak via HTTPS

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: rhdemo-ingress
  namespace: {{ .Values.global.namespace }}
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  ingressClassName: nginx       # Utilise Nginx Ingress Controller
  tls:
  - hosts:
    - rhdemo.stagingkub.local
    - keycloak.stagingkub.local
    secretName: rhdemo-tls-cert # Secret contenant les certificats SSL
  rules:
  # Règle 1 : rhdemo.stagingkub.local → rhdemo-app:9000
  - host: rhdemo.stagingkub.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: rhdemo-app
            port:
              number: 9000

  # Règle 2 : keycloak.stagingkub.local → keycloak:8080
  - host: keycloak.stagingkub.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: keycloak
            port:
              number: 8080
```

**Qu'est-ce qu'un Ingress ?**
- Point d'entrée unique pour exposer plusieurs services HTTP/HTTPS
- Routing basé sur :
  - **Hostname** : rhdemo.stagingkub.local → app, keycloak.stagingkub.local → keycloak
  - **Path** : /api → service1, /admin → service2
- Nécessite un **Ingress Controller** (Nginx, Traefik, HAProxy)

**Flux de requête** :
```
Client (navigateur)
  ↓ https://rhdemo.stagingkub.local
Ingress (port 443)
  ↓ détermine le backend via rules.host
Service rhdemo-app (port 9000)
  ↓ load balance vers les pods
Pod rhdemo-app (port 9000)
```

**Commandes** :
```bash
# Voir l'Ingress
kubectl get ingress -n rhdemo-stagingkub

# Voir les détails (events, rules)
kubectl describe ingress rhdemo-ingress -n rhdemo-stagingkub

# Tester depuis un pod
kubectl run -it --rm debug --image=curlimages/curl -n rhdemo-stagingkub -- \
  curl -H "Host: rhdemo.stagingkub.local" http://rhdemo-app:9000/actuator/health
```

---

### Template 12 : _helpers.tpl

**Rôle** : Fonctions Helm réutilisables

```go
{{/*
Expand the name of the chart.
*/}}
{{- define "rhdemo.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rhdemo.labels" -}}
helm.sh/chart: {{ include "rhdemo.chart" . }}
{{ include "rhdemo.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
environment: {{ .Values.global.environment }}
{{- end }}
```

**Utilisation** :
```yaml
# Dans un template
metadata:
  labels:
    {{- include "rhdemo.labels" . | nindent 4 }}
```

**Résultat** :
```yaml
metadata:
  labels:
    helm.sh/chart: rhdemo-1.0.0
    app.kubernetes.io/name: rhdemo
    app.kubernetes.io/instance: rhdemo
    app.kubernetes.io/version: "1.1.0-SNAPSHOT"
    app.kubernetes.io/managed-by: Helm
    environment: staging
```

---

### Template 13 : NOTES.txt

**Rôle** : Message affiché après le déploiement

```
╔═══════════════════════════════════════════════════════════════╗
║   🎉 RHDemo déployé avec succès sur Kubernetes !             ║
╚═══════════════════════════════════════════════════════════════╝

📦 Release: rhdemo
🏷️  Version: 1.1.0-SNAPSHOT
📂 Namespace: rhdemo-stagingkub

🌐 URLS D'ACCÈS
  Application RHDemo: https://rhdemo.stagingkub.local
  Keycloak Admin Console: https://keycloak.stagingkub.local

📊 VÉRIFIER LE STATUT
  kubectl get pods -n rhdemo-stagingkub
```

---

## 🔧 Variables et personnalisation

### Syntaxe des templates Helm

```yaml
# Accès à une valeur
{{ .Values.rhdemo.image.tag }}

# Condition
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
{{- end }}

# Boucle
{{- range .Values.ingress.hosts }}
- host: {{ .host }}
{{- end }}

# Appel de fonction
{{- include "rhdemo.labels" . | nindent 4 }}

# Valeur par défaut
{{ .Values.rhdemo.replicaCount | default 1 }}
```

### Variables disponibles

| Variable | Description |
|----------|-------------|
| `.Values` | Valeurs du values.yaml |
| `.Chart` | Métadonnées du Chart.yaml |
| `.Release` | Info sur la release (nom, namespace) |
| `.Template` | Info sur le template en cours |
| `.Files` | Accès aux fichiers du chart |

---

## 🚀 Déploiement et mise à jour

### Installation initiale

```bash
helm install rhdemo ./helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --create-namespace
```

### Mise à jour (upgrade)

```bash
# Avec nouvelle version d'image
helm upgrade rhdemo ./helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --set rhdemo.image.tag=1.2.0-SNAPSHOT

# Avec fichier custom
helm upgrade rhdemo ./helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --values values-custom.yaml
```

### Rollback

```bash
# Voir l'historique
helm history rhdemo -n rhdemo-stagingkub

# Revenir à la version précédente
helm rollback rhdemo -n rhdemo-stagingkub

# Revenir à une version spécifique
helm rollback rhdemo 3 -n rhdemo-stagingkub
```

### Désinstallation

```bash
# Supprimer la release (garde les PVC)
helm uninstall rhdemo -n rhdemo-stagingkub

# Supprimer aussi le namespace (supprime tout)
kubectl delete namespace rhdemo-stagingkub
```

---

## 📊 Récapitulatif des ressources créées

| Type | Nom | Rôle |
|------|-----|------|
| **Namespace** | rhdemo-stagingkub | Isolation des ressources |
| **StatefulSet** | postgresql-rhdemo | Base de données RHDemo |
| **StatefulSet** | postgresql-keycloak | Base de données Keycloak |
| **Deployment** | keycloak | Serveur d'authentification |
| **Deployment** | rhdemo-app | Application Spring Boot |
| **Service** | postgresql-rhdemo | Exposition interne DB (5432) |
| **Service** | postgresql-keycloak | Exposition interne DB (5432) |
| **Service** | keycloak | Exposition interne Keycloak (8080) |
| **Service** | rhdemo-app | Exposition interne App (9000) |
| **Ingress** | rhdemo-ingress | Exposition HTTPS (443) |
| **ConfigMap** | postgresql-rhdemo-init | Scripts init DB |
| **PVC** | postgresql-data (x2) | Stockage persistant (2Gi chacun) |

**Total** : 18 ressources Kubernetes

---

## 📚 Ressources pour aller plus loin

- [Documentation Helm](https://helm.sh/docs/)
- [Kubernetes Concepts](https://kubernetes.io/docs/concepts/)
- [Helm Best Practices](https://helm.sh/docs/chart_best_practices/)
- [Helm Templates](https://helm.sh/docs/chart_template_guide/)

---

## ✅ Checklist de compréhension

- [ ] Je comprends ce qu'est un Chart Helm
- [ ] Je sais lire un fichier values.yaml
- [ ] Je comprends la différence entre Deployment et StatefulSet
- [ ] Je sais ce qu'est un Service (ClusterIP vs NodePort vs LoadBalancer)
- [ ] Je comprends le rôle d'un Ingress
- [ ] Je sais personnaliser un déploiement avec --set
- [ ] Je sais faire un rollback avec Helm
