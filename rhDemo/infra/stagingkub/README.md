# 🚀 Environnement stagingkub - Déploiement Kubernetes avec KinD

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Prérequis](#prérequis)
- [Architecture](#architecture)
- [Installation initiale](#installation-initiale)
- [Déploiement](#déploiement)
- [Configuration](#configuration)
- [Opérations courantes](#opérations-courantes)
- [Troubleshooting](#troubleshooting)
- [Comparaison staging vs stagingkub](#comparaison-staging-vs-stagingkub)

---

## 🎯 Vue d'ensemble

L'environnement **stagingkub** est un environnement de staging Kubernetes basé sur **KinD** (Kubernetes in Docker). Il reproduit l'architecture de l'environnement staging Docker Compose dans un cluster Kubernetes local, permettant de tester les déploiements Kubernetes avant la production.

### Différences avec staging (Docker Compose)

| Aspect | staging (Docker Compose) | stagingkub (Kubernetes/KinD) |
|--------|-------------------------|------------------------------|
| **Orchestration** | Docker Compose | Kubernetes (KinD) |
| **Package** | docker-compose.yml | Helm Chart |
| **Secrets** | Variables d'env + docker cp | Kubernetes Secrets |
| **Réseau** | Docker network bridge | Kubernetes Services + Ingress |
| **Volumes** | Docker volumes | PersistentVolumeClaims |
| **Exposition** | Port mapping direct | Ingress Controller (NodePort) |
| **Healthchecks** | Docker healthcheck | Liveness/Readiness probes |
| **Use case** | Tests rapides, dev local | Tests Kubernetes, pré-prod |

---

## 📦 Prérequis

### Outils requis

1. **Docker** (version 20.10+)
   ```bash
   docker --version
   ```

2. **kubectl** (version 1.28+)
   ```bash
   kubectl version --client
   ```

3. **Helm** (version 3.12+)
   ```bash
   helm version
   ```

4. **KinD** (version 0.20+)
   ```bash
   kind version
   ```

   Installation KinD :
   ```bash
   # Linux
   curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
   chmod +x ./kind
   sudo mv ./kind /usr/local/bin/kind

   # macOS
   brew install kind
   ```

5. **SOPS** (pour le déchiffrement des secrets)
   ```bash
   sops --version
   ```

### Configuration requise

- **CPU** : 4 cores minimum (6 cores recommandés)
- **RAM** : 8 GB minimum (16 GB recommandés)
- **Disk** : 20 GB d'espace libre

---

## 🏗️ Architecture

### Composants déployés

```
┌─────────────────────────────────────────────────────────────┐
│                    Cluster KinD "rhdemo"                     │
├─────────────────────────────────────────────────────────────┤
│  Namespace: rhdemo-stagingkub                                   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Nginx Ingress Controller                              │  │
│  │ • Port 30443 (HTTPS) → 443 (host)                    │  │
│  │ • Port 30080 (HTTP) → 80 (host)                      │  │
│  └────────────┬─────────────────────────────────────────┘  │
│               │                                              │
│  ┌────────────▼──────────┐    ┌────────────────────────┐   │
│  │ Ingress                │    │ Ingress                │   │
│  │ rhdemo.stagingkub.local   │    │ keycloak.stagingkub.local │   │
│  └────────────┬───────────┘    └────────────┬───────────┘   │
│               │                               │              │
│  ┌────────────▼───────────┐    ┌─────────────▼──────────┐  │
│  │ Service: rhdemo-app    │    │ Service: keycloak      │  │
│  │ ClusterIP:9000         │    │ ClusterIP:8080         │  │
│  └────────────┬───────────┘    └────────────┬───────────┘  │
│               │                               │              │
│  ┌────────────▼───────────┐    ┌─────────────▼──────────┐  │
│  │ Deployment: rhdemo-app │    │ Deployment: keycloak   │  │
│  │ • Image: rhdemo-api    │    │ • Image: keycloak      │  │
│  │ • Replicas: 1          │    │ • Replicas: 1          │  │
│  │ • Port: 9000           │    │ • Port: 8080           │  │
│  └────────────┬───────────┘    └────────────┬───────────┘  │
│               │                               │              │
│  ┌────────────▼──────────────┐ ┌─────────────▼───────────┐ │
│  │ Service: postgresql-rhdemo│ │ Service: postgresql-    │ │
│  │ Headless ClusterIP:5432   │ │ keycloak                │ │
│  └────────────┬──────────────┘ │ Headless ClusterIP:5432 │ │
│               │                 └─────────────┬───────────┘ │
│  ┌────────────▼──────────────┐ ┌─────────────▼───────────┐ │
│  │ StatefulSet:              │ │ StatefulSet:            │ │
│  │ postgresql-rhdemo         │ │ postgresql-keycloak     │ │
│  │ • Image: postgres:16      │ │ • Image: postgres:16    │ │
│  │ • PVC: 2Gi                │ │ • PVC: 2Gi              │ │
│  └───────────────────────────┘ └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Ressources Kubernetes créées

- **1 Namespace** : `rhdemo-stagingkub`
- **5 Deployments/StatefulSets** :
  - `postgresql-rhdemo` (StatefulSet)
  - `postgresql-keycloak` (StatefulSet)
  - `keycloak` (Deployment)
  - `rhdemo-app` (Deployment)
- **5 Services** :
  - `postgresql-rhdemo` (Headless)
  - `postgresql-keycloak` (Headless)
  - `keycloak` (ClusterIP)
  - `rhdemo-app` (ClusterIP)
- **1 Ingress** : `rhdemo-ingress` (routes pour rhdemo + keycloak)
- **4 Secrets** :
  - `rhdemo-db-secret` (mot de passe PostgreSQL rhdemo)
  - `keycloak-db-secret` (mot de passe PostgreSQL keycloak)
  - `keycloak-admin-secret` (mot de passe admin Keycloak)
  - `rhdemo-app-secrets` (secrets-rhdemo.yml)
  - `rhdemo-tls-cert` (certificats SSL)
- **2 PersistentVolumeClaims** :
  - `postgresql-data` (pour postgresql-rhdemo)
  - `postgresql-data` (pour postgresql-keycloak)
- **1 ConfigMap** :
  - `postgresql-rhdemo-init` (scripts d'initialisation DB)

---

## 🚀 Installation initiale

### 1. Créer le cluster KinD (si nécessaire)

```bash
cd rhDemo/infra/stagingkub
./scripts/init-stagingkub.sh
```

Ce script :
- ✅ Crée le cluster KinD `rhdemo` (si non existant)
- ✅ Configure les port mappings (80:30080, 443:30443)
- ✅ Installe Nginx Ingress Controller
- ✅ Crée le namespace `rhdemo-stagingkub`
- ✅ Crée les secrets Kubernetes (depuis SOPS)
- ✅ Génère les certificats SSL
- ✅ Ajoute les entrées DNS à `/etc/hosts`

### 2. Vérifier l'installation

```bash
# Vérifier le cluster
kubectl cluster-info --context kind-rhdemo

# Vérifier les nodes
kubectl get nodes

# Vérifier Nginx Ingress
kubectl get pods -n ingress-nginx

# Vérifier le namespace
kubectl get ns rhdemo-stagingkub
```

---

## 📦 Déploiement

### Méthode 1 : Déploiement via Jenkins

1. Ouvrir le pipeline Jenkins
2. Cliquer sur "Build with Parameters"
3. Sélectionner `DEPLOY_ENV = stagingkub`
4. Lancer le build

Le pipeline exécutera automatiquement :
- Lecture de la version Maven
- Build de l'image Docker
- Chargement de l'image dans KinD
- Mise à jour des secrets Kubernetes
- Déploiement Helm
- Attente de la disponibilité des services

### Méthode 2 : Déploiement manuel

```bash
cd rhDemo/infra/stagingkub

# 1. Construire l'image Docker (depuis la racine du projet)
cd ../..
./mvnw clean spring-boot:build-image -Dspring-boot.build-image.imageName=rhdemo-api:1.1.0-SNAPSHOT

# 2. Déployer avec le script
cd infra/stagingkub
./scripts/deploy.sh 1.1.0-SNAPSHOT
```

### Méthode 3 : Déploiement Helm direct

```bash
# 1. Charger l'image dans KinD
kind load docker-image rhdemo-api:1.1.0-SNAPSHOT --name rhdemo

# 2. Déployer avec Helm
helm upgrade --install rhdemo ./helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --create-namespace \
  --set rhdemo.image.tag=1.1.0-SNAPSHOT \
  --wait \
  --timeout 10m
```

---

## ⚙️ Configuration

### Fichiers de configuration

| Fichier | Description |
|---------|-------------|
| `helm/rhdemo/Chart.yaml` | Métadonnées du chart Helm |
| `helm/rhdemo/values.yaml` | Configuration par défaut |
| `helm/rhdemo/templates/` | Templates Kubernetes |
| `scripts/init-stagingkub.sh` | Script d'initialisation |
| `scripts/deploy.sh` | Script de déploiement |

### Personnalisation de la configuration

Vous pouvez personnaliser le déploiement en créant un fichier `values-custom.yaml` :

```yaml
# values-custom.yaml
rhdemo:
  replicaCount: 2  # Augmenter le nombre de réplicas
  resources:
    requests:
      memory: "1Gi"
      cpu: "1000m"

keycloak:
  replicaCount: 2
```

Puis déployer avec :

```bash
helm upgrade --install rhdemo ./helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --values ./helm/rhdemo/values.yaml \
  --values values-custom.yaml
```

### Secrets

Les secrets sont gérés de deux manières :

1. **Secrets d'infrastructure** (DB passwords, Keycloak admin) : Créés par `init-stagingkub.sh` depuis SOPS
2. **Secrets applicatifs** (Keycloak client secret, etc.) : Montés depuis `secrets-rhdemo.yml`

Pour mettre à jour les secrets :

```bash
# Mettre à jour secrets-rhdemo.yml
kubectl create secret generic rhdemo-app-secrets \
  --from-file=secrets-rhdemo.yml=../../secrets/secrets-rhdemo.yml \
  --namespace rhdemo-stagingkub \
  --dry-run=client -o yaml | kubectl apply -f -

# Redémarrer le pod pour charger les nouveaux secrets
kubectl rollout restart deployment/rhdemo-app -n rhdemo-stagingkub
```

---

## 🔧 Opérations courantes

### Consulter les logs

```bash
# Logs de l'application
kubectl logs -f -n rhdemo-stagingkub -l app=rhdemo-app

# Logs de Keycloak
kubectl logs -f -n rhdemo-stagingkub -l app=keycloak

# Logs de PostgreSQL (rhdemo)
kubectl logs -f -n rhdemo-stagingkub -l app=postgresql-rhdemo

# Logs de tous les pods
kubectl logs -f -n rhdemo-stagingkub --all-containers=true
```

### Vérifier le statut

```bash
# Statut des pods
kubectl get pods -n rhdemo-stagingkub

# Statut détaillé d'un pod
kubectl describe pod <pod-name> -n rhdemo-stagingkub

# Statut des services
kubectl get svc -n rhdemo-stagingkub

# Statut de l'ingress
kubectl get ingress -n rhdemo-stagingkub
```

### Accéder aux services

```bash
# Port-forward vers l'application (alternative à Ingress)
kubectl port-forward -n rhdemo-stagingkub svc/rhdemo-app 9000:9000

# Port-forward vers Keycloak
kubectl port-forward -n rhdemo-stagingkub svc/keycloak 8080:8080

# Port-forward vers PostgreSQL
kubectl port-forward -n rhdemo-stagingkub svc/postgresql-rhdemo 5432:5432
```

### Mettre à jour l'application

```bash
# Méthode 1 : Via Helm
helm upgrade rhdemo ./helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --set rhdemo.image.tag=1.2.0-SNAPSHOT \
  --wait

# Méthode 2 : Via kubectl (patch)
kubectl set image deployment/rhdemo-app \
  rhdemo-app=rhdemo-api:1.2.0-SNAPSHOT \
  -n rhdemo-stagingkub
```

### Redémarrer un service

```bash
# Redémarrer l'application
kubectl rollout restart deployment/rhdemo-app -n rhdemo-stagingkub

# Redémarrer Keycloak
kubectl rollout restart deployment/keycloak -n rhdemo-stagingkub

# Redémarrer PostgreSQL (attention : va recréer le pod)
kubectl rollout restart statefulset/postgresql-rhdemo -n rhdemo-stagingkub
```

### Nettoyer l'environnement

```bash
# Supprimer le déploiement Helm (conserve les PVC)
helm uninstall rhdemo -n rhdemo-stagingkub

# Supprimer le namespace entier (supprime tout, y compris les PVC)
kubectl delete namespace rhdemo-stagingkub

# Supprimer le cluster KinD complet
kind delete cluster --name rhdemo
```

---

## 🐛 Troubleshooting

### Pod en status CrashLoopBackOff

```bash
# Voir les logs du pod qui crash
kubectl logs -n rhdemo-stagingkub <pod-name> --previous

# Voir les events
kubectl get events -n rhdemo-stagingkub --sort-by='.lastTimestamp'

# Décrire le pod pour voir les erreurs
kubectl describe pod <pod-name> -n rhdemo-stagingkub
```

### Problème de connexion à la base de données

```bash
# Vérifier que PostgreSQL est prêt
kubectl get pods -n rhdemo-stagingkub -l app=postgresql-rhdemo

# Tester la connexion depuis un pod
kubectl run -it --rm debug --image=postgres:16-alpine --restart=Never -n rhdemo-stagingkub -- psql -h postgresql-rhdemo -U rhdemo -d rhdemo

# Vérifier les secrets
kubectl get secret rhdemo-db-secret -n rhdemo-stagingkub -o yaml
```

### Ingress ne fonctionne pas

```bash
# Vérifier que Nginx Ingress Controller est actif
kubectl get pods -n ingress-nginx

# Vérifier l'ingress
kubectl describe ingress rhdemo-ingress -n rhdemo-stagingkub

# Vérifier les certificats TLS
kubectl get secret rhdemo-tls-cert -n rhdemo-stagingkub

# Tester avec curl (ignorer le certificat self-signed)
curl -k https://rhdemo.stagingkub.local
```

### /etc/hosts non configuré

```bash
# Vérifier /etc/hosts
cat /etc/hosts | grep staging.local

# Ajouter manuellement si nécessaire
echo "127.0.0.1 rhdemo.stagingkub.local" | sudo tee -a /etc/hosts
echo "127.0.0.1 keycloak.stagingkub.local" | sudo tee -a /etc/hosts
```

### Image Docker non trouvée

```bash
# Vérifier les images dans KinD
docker exec -it rhdemo-control-plane crictl images | grep rhdemo-api

# Recharger l'image
kind load docker-image rhdemo-api:VERSION --name rhdemo
```

---

## 📊 Comparaison staging vs stagingkub

### Quand utiliser staging (Docker Compose)

✅ Tests rapides de nouvelles fonctionnalités
✅ Développement local
✅ Debugging facile avec `docker logs`
✅ Démarrage/arrêt rapide
✅ Familiarité avec Docker Compose

### Quand utiliser stagingkub (Kubernetes)

✅ Tester les déploiements Kubernetes avant production
✅ Valider les manifests Kubernetes (Helm charts)
✅ Tester les rolling updates
✅ Valider les readiness/liveness probes
✅ Tester l'Ingress Controller
✅ Se familiariser avec kubectl et Helm
✅ Tests de montée en charge (scaling horizontal)

---

## 📚 Ressources

- [Documentation KinD](https://kind.sigs.k8s.io/)
- [Documentation Helm](https://helm.sh/docs/)
- [Documentation Kubernetes](https://kubernetes.io/docs/)
- [Nginx Ingress Controller](https://kubernetes.github.io/ingress-nginx/)

---

## ✅ Checklist de déploiement

- [ ] KinD installé et cluster créé
- [ ] kubectl configuré avec contexte `kind-rhdemo`
- [ ] Helm installé (version 3.12+)
- [ ] Nginx Ingress Controller déployé
- [ ] Secrets créés dans le namespace `rhdemo-stagingkub`
- [ ] Certificats SSL générés
- [ ] `/etc/hosts` mis à jour
- [ ] Image Docker construite
- [ ] Image chargée dans KinD
- [ ] Helm chart déployé
- [ ] Tous les pods en status `Running`
- [ ] Ingress accessible via https://rhdemo.stagingkub.local
