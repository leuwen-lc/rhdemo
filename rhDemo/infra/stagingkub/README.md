# 🚀 Environnement stagingkub - Déploiement Kubernetes avec KinD

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Prérequis](#prérequis)
- [Architecture](#architecture)
- [Installation initiale](#installation-initiale)
- [Déploiement](#déploiement)
- [Configuration](#configuration)
- [Persistance des données](#-persistance-des-données)
- [Opérations courantes](#opérations-courantes)
- [Troubleshooting](#troubleshooting)
- [Comparaison ephemere vs stagingkub](#comparaison-ephemere-vs-stagingkub)

---

## 🎯 Vue d'ensemble

L'environnement **stagingkub** est un environnement de staging Kubernetes basé sur **KinD** (Kubernetes in Docker). Il reproduit l'architecture de l'environnement ephemere Docker Compose dans un cluster Kubernetes local, permettant de tester les déploiements Kubernetes avant la production.

### Stack technique

| Composant | Version | Description |
|-----------|---------|-------------|
| **KinD** | 0.30+ | Cluster Kubernetes local |
| **Cilium** | 1.18.6 | CNI avec kube-proxy replacement (eBPF) |
| **NGINX Gateway Fabric** | 2.3.0 | Gateway API (remplace nginx-ingress) |
| **PostgreSQL** | 16-alpine | Base de données |
| **Keycloak** | 26.4.2 | IAM / OAuth2 |

### Différences avec ephemere (Docker Compose)

| Aspect | ephemere (Docker Compose) | stagingkub (Kubernetes/KinD) |
|--------|-------------------------|------------------------------|
| **Orchestration** | Docker Compose | Kubernetes (KinD) |
| **Package** | docker-compose.yml | Helm Chart |
| **Secrets** | Variables d'env + docker cp | Kubernetes Secrets |
| **Réseau** | Docker network bridge | Cilium CNI + Gateway API |
| **Volumes** | Docker volumes | PersistentVolumeClaims |
| **Exposition** | Port mapping direct | NGINX Gateway Fabric (NodePort) |
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

4. **KinD** (version 0.30+)
   ```bash
   kind version
   ```

   Installation KinD :
   ```bash
   # Linux
   curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.30.0/kind-linux-amd64
   chmod +x ./kind
   sudo mv ./kind /usr/local/bin/kind

   # macOS
   brew install kind
   ```

5. **SOPS** (pour le déchiffrement des secrets)
   ```bash
   sops --version
   ```

### Configuration système (Cilium)

Cilium nécessite des limites inotify élevées :

```bash
# Vérifier les valeurs actuelles
cat /proc/sys/fs/inotify/max_user_watches   # minimum: 524288
cat /proc/sys/fs/inotify/max_user_instances # minimum: 512

# Configurer (permanent)
echo 'fs.inotify.max_user_watches=524288' | sudo tee -a /etc/sysctl.d/99-cilium.conf
echo 'fs.inotify.max_user_instances=512' | sudo tee -a /etc/sysctl.d/99-cilium.conf
sudo sysctl --system
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
│                    Cluster KinD "rhdemo"                    │
│                    CNI: Cilium 1.18 (eBPF)                  │
├─────────────────────────────────────────────────────────────┤
│  Namespace: nginx-gateway                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ NGINX Gateway Fabric 2.3.0                           │  │
│  │ • NodePort 31792 (HTTP) → 80 (host)                  │  │
│  │ • NodePort 32616 (HTTPS) → 443 (host)                │  │
│  │ • GatewayClass: nginx                                │  │
│  └────────────┬─────────────────────────────────────────┘  │
├───────────────┼─────────────────────────────────────────────┤
│  Namespace: rhdemo-stagingkub                               │
│               │                                             │
│  ┌────────────▼──────────┐    ┌────────────────────────┐   │
│  │ Gateway: rhdemo-gw    │    │                        │   │
│  │ └─ HTTPRoute: rhdemo  │    │ └─ HTTPRoute: keycloak │   │
│  │    → rhdemo-app:9000  │    │    → keycloak:8080     │   │
│  └────────────┬──────────┘    └────────────┬───────────┘   │
│               │                             │               │
│  ┌────────────▼───────────┐    ┌───────────▼───────────┐   │
│  │ Deployment: rhdemo-app │    │ Deployment: keycloak  │   │
│  │ • Image: rhdemo-api    │    │ • Image: keycloak     │   │
│  │ • Replicas: 1          │    │ • Replicas: 1         │   │
│  │ • Port: 9000           │    │ • Port: 8080          │   │
│  └────────────┬───────────┘    └───────────┬───────────┘   │
│               │                             │               │
│  ┌────────────▼──────────────┐ ┌───────────▼────────────┐  │
│  │ StatefulSet:              │ │ StatefulSet:           │  │
│  │ postgresql-rhdemo         │ │ postgresql-keycloak    │  │
│  │ • Image: postgres:16      │ │ • Image: postgres:16   │  │
│  │ • PVC: 2Gi                │ │ • PVC: 2Gi             │  │
│  └───────────────────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Ressources Kubernetes créées

**Infrastructure (par init-stagingkub.sh) :**

- **Cilium** : CNI avec kube-proxy replacement
- **NGINX Gateway Fabric** : Gateway API implementation
- **GatewayClass** : `nginx`

**Application (par Helm chart) :**

- **1 Namespace** : `rhdemo-stagingkub`
- **4 Deployments/StatefulSets** :
  - `postgresql-rhdemo` (StatefulSet)
  - `postgresql-keycloak` (StatefulSet)
  - `keycloak` (Deployment)
  - `rhdemo-app` (Deployment)
- **4 Services** :
  - `postgresql-rhdemo` (Headless)
  - `postgresql-keycloak` (Headless)
  - `keycloak` (ClusterIP)
  - `rhdemo-app` (ClusterIP)
- **Gateway API resources** :
  - `rhdemo-gateway` (Gateway)
  - `rhdemo-route` (HTTPRoute)
  - `keycloak-route` (HTTPRoute)
  - `keycloak-proxy-buffers` (SnippetsFilter)
  - `rhdemo-client-settings` (ClientSettingsPolicy)
- **5 Secrets** :
  - `rhdemo-db-secret` (mot de passe PostgreSQL rhdemo)
  - `keycloak-db-secret` (mot de passe PostgreSQL keycloak)
  - `keycloak-admin-secret` (mot de passe admin Keycloak)
  - `rhdemo-app-secrets` (secrets-rhdemo.yml)
  - `intra-wildcard-tls` (certificats SSL)
- **2 PersistentVolumes statiques** (hostPath)
- **2 PersistentVolumeClaims**
- **2 CronJobs** (backups PostgreSQL)
- **Network Policies** (Zero Trust)

---

## 🚀 Installation initiale

### 1. Créer le cluster KinD

```bash
cd rhDemo/infra/stagingkub
./scripts/init-stagingkub.sh
```

Ce script :

- ✅ Vérifie les prérequis système (limites inotify)
- ✅ Configure le registry Docker local
- ✅ Crée le cluster KinD `rhdemo` avec `kind-config.yaml`
- ✅ Installe **Cilium 1.18** (CNI avec kube-proxy replacement)
- ✅ Installe **NGINX Gateway Fabric 2.3.0** (Gateway API)
- ✅ Crée le namespace `rhdemo-stagingkub`
- ✅ Crée les secrets Kubernetes (depuis SOPS)
- ✅ Configure le RBAC pour Jenkins
- ✅ Génère les certificats SSL
- ✅ Ajoute les entrées DNS à `/etc/hosts`

### 2. Vérifier l'installation

```bash
# Vérifier le cluster
kubectl cluster-info --context kind-rhdemo

# Vérifier les nodes
kubectl get nodes

# Vérifier Cilium
kubectl get pods -n kube-system -l k8s-app=cilium

# Vérifier NGINX Gateway Fabric
kubectl get pods -n nginx-gateway
kubectl get gatewayclass nginx

# Vérifier le namespace
kubectl get ns rhdemo-stagingkub

# Validation complète
./scripts/validate-stagingkub.sh
```

---

## 📦 Déploiement

### Méthode 1 : Déploiement via Jenkins (recommandé)

1. Ouvrir le pipeline Jenkins CD (`Jenkinsfile-CD`)
2. Cliquer sur "Build with Parameters"
3. Entrer la version à déployer
4. Lancer le build

Le pipeline exécutera automatiquement :
- Récupération de l'image depuis le registry
- Mise à jour des secrets Kubernetes
- Déploiement Helm
- Attente de la disponibilité des services

### Méthode 2 : Déploiement Helm direct

```bash
# 1. Construire l'image Docker (depuis rhDemo/)
./mvnw clean package -DskipTests
docker build -t rhdemo-api:1.1.4-SNAPSHOT .

# 2. Tagger et pousser vers le registry local
docker tag rhdemo-api:1.1.4-SNAPSHOT localhost:5000/rhdemo-api:1.1.4-SNAPSHOT
docker push localhost:5000/rhdemo-api:1.1.4-SNAPSHOT

# 3. Déployer avec Helm
cd infra/stagingkub
helm upgrade --install rhdemo ./helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --create-namespace \
  --set rhdemo.image.tag=1.1.4-SNAPSHOT \
  --wait \
  --timeout 10m
```

### Vérifier le déploiement

```bash
# Pods
kubectl get pods -n rhdemo-stagingkub

# Gateway et routes
kubectl get gateway,httproute -n rhdemo-stagingkub

# Tester l'accès (ignorer le certificat self-signed)
curl -k https://rhdemo-stagingkub.intra.leuwen-lc.fr/actuator/health
```

---

## ⚙️ Configuration

### Fichiers de configuration

| Fichier | Description |
|---------|-------------|
| `kind-config.yaml` | Configuration du cluster KinD |
| `helm/rhdemo/Chart.yaml` | Métadonnées du chart Helm |
| `helm/rhdemo/values.yaml` | Configuration par défaut |
| `helm/rhdemo/templates/` | Templates Kubernetes |
| `scripts/init-stagingkub.sh` | Script d'initialisation |
| `rbac/` | Configuration RBAC Jenkins |

### Configuration Gateway API (values.yaml)

```yaml
gateway:
  enabled: true
  name: rhdemo-gateway
  className: nginx

  listeners:
    - name: https-rhdemo
      hostname: rhdemo-stagingkub.intra.leuwen-lc.fr
      port: 443
      protocol: HTTPS
      tls:
        mode: Terminate
        secretName: intra-wildcard-tls

  routes:
    - name: rhdemo-route
      listenerName: https-rhdemo
      hostname: rhdemo-stagingkub.intra.leuwen-lc.fr
      rules:
        - path: /
          pathType: PathPrefix
          serviceName: rhdemo-app
          servicePort: 9000

  # Proxy buffers pour Keycloak (gros cookies OAuth2)
  snippetsFilter:
    enabled: true
    proxyBufferSize: "128k"
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

## 💾 Persistance des données

### Architecture de persistance

Les données PostgreSQL sont persistées sur l'hôte via des **extraMounts KinD** :

```text
Hôte Linux                              KinD Container                    Pod PostgreSQL
─────────────                           ──────────────                    ──────────────
/home/leno-vo/kind-data/               /mnt/data/                        /var/lib/postgresql/data/
  └─ rhdemo-stagingkub/                  ├─ postgresql-rhdemo/ ◄──────── PV hostPath
       ├─ postgresql-rhdemo/             └─ postgresql-keycloak/ ◄────── PV hostPath
       ├─ postgresql-keycloak/
       └─ backups/                     /mnt/backups/
            ├─ rhdemo/                   ├─ rhdemo/ ◄──────────────────── CronJob backup
            └─ keycloak/                 └─ keycloak/ ◄─────────────────── CronJob backup
```

### Avantages

- ✅ **Survie aux recréations de cluster** : Les données restent sur l'hôte
- ✅ **Realm Keycloak préservé** : Pas besoin de reconfigurer après redémarrage
- ✅ **Backups accessibles** : Fichiers `.sql.gz` directement sur l'hôte

### Backups automatiques (CronJobs)

| CronJob                      | Schedule     | Rétention | Chemin backup              |
|------------------------------|--------------|-----------|----------------------------|
| `postgresql-rhdemo-backup`   | 2h du matin  | 7 jours   | `/mnt/backups/rhdemo/`     |
| `postgresql-keycloak-backup` | 3h du matin  | 7 jours   | `/mnt/backups/keycloak/`   |

```bash
# Vérifier les CronJobs
kubectl get cronjob -n rhdemo-stagingkub

# Déclencher un backup manuel
kubectl create job --from=cronjob/postgresql-rhdemo-backup manual-backup-$(date +%s) -n rhdemo-stagingkub

# Voir les backups sur l'hôte
ls -lh /home/leno-vo/kind-data/rhdemo-stagingkub/backups/rhdemo/
```

> 📖 Documentation complète : [POSTGRESQL_BACKUP_CRONJOBS.md](../../docs/POSTGRESQL_BACKUP_CRONJOBS.md)

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
```

### Vérifier le statut

```bash
# Statut des pods
kubectl get pods -n rhdemo-stagingkub

# Statut Gateway API
kubectl get gateway,httproute -n rhdemo-stagingkub

# Statut des services
kubectl get svc -n rhdemo-stagingkub

# Network Policies
kubectl get networkpolicies -n rhdemo-stagingkub
```

### Accéder aux services

```bash
# Port-forward vers l'application (alternative à Gateway)
kubectl port-forward -n rhdemo-stagingkub svc/rhdemo-app 9000:9000

# Port-forward vers Keycloak
kubectl port-forward -n rhdemo-stagingkub svc/keycloak 8080:8080

# Port-forward vers PostgreSQL
kubectl port-forward -n rhdemo-stagingkub svc/postgresql-rhdemo 5432:5432
```

### Mettre à jour l'application

```bash
# Via Helm
helm upgrade rhdemo ./helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --set rhdemo.image.tag=1.2.0-SNAPSHOT \
  --wait
```

### Redémarrer un service

```bash
# Redémarrer l'application
kubectl rollout restart deployment/rhdemo-app -n rhdemo-stagingkub

# Redémarrer Keycloak
kubectl rollout restart deployment/keycloak -n rhdemo-stagingkub
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

### Gateway ne fonctionne pas

```bash
# Vérifier NGINX Gateway Fabric
kubectl get pods -n nginx-gateway
kubectl logs -n nginx-gateway -l app.kubernetes.io/name=nginx-gateway-fabric

# Vérifier le GatewayClass
kubectl get gatewayclass nginx

# Vérifier la Gateway et les routes
kubectl describe gateway rhdemo-gateway -n rhdemo-stagingkub
kubectl describe httproute rhdemo-route -n rhdemo-stagingkub

# Vérifier les certificats TLS
kubectl get secret intra-wildcard-tls -n rhdemo-stagingkub

# Tester avec curl (ignorer le certificat self-signed)
curl -k https://rhdemo-stagingkub.intra.leuwen-lc.fr
```

### /etc/hosts non configuré

```bash
# Vérifier /etc/hosts
cat /etc/hosts | grep stagingkub

# Ajouter manuellement si nécessaire
echo "127.0.0.1 rhdemo-stagingkub.intra.leuwen-lc.fr" | sudo tee -a /etc/hosts
echo "127.0.0.1 keycloak-stagingkub.intra.leuwen-lc.fr" | sudo tee -a /etc/hosts
```

### Image Docker non trouvée

```bash
# Vérifier les images dans le registry
curl -s http://localhost:5000/v2/rhdemo-api/tags/list

# Vérifier la connectivité registry → KinD
kubectl get configmap local-registry-hosting -n kube-public -o yaml
```

### Network Policies bloquent le trafic

```bash
# Tester les Network Policies
./scripts/test-network-policies.sh

# Vérifier les policies actives
kubectl get networkpolicies -n rhdemo-stagingkub -o wide
```

---

## 📊 Comparaison ephemere vs stagingkub

### Quand utiliser ephemere (Docker Compose)

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
✅ Tester Gateway API
✅ Valider les Network Policies
✅ Se familiariser avec kubectl et Helm

---

## 📚 Ressources

- [Documentation KinD](https://kind.sigs.k8s.io/)
- [Documentation Helm](https://helm.sh/docs/)
- [Documentation Kubernetes](https://kubernetes.io/docs/)
- [NGINX Gateway Fabric](https://docs.nginx.com/nginx-gateway-fabric/)
- [Cilium Documentation](https://docs.cilium.io/)
- [Gateway API](https://gateway-api.sigs.k8s.io/)

---

## ✅ Checklist de déploiement

- [ ] Limites inotify configurées pour Cilium
- [ ] KinD installé et cluster créé
- [ ] kubectl configuré avec contexte `kind-rhdemo`
- [ ] Helm installé (version 3.12+)
- [ ] Cilium CNI opérationnel
- [ ] NGINX Gateway Fabric déployé
- [ ] GatewayClass `nginx` disponible
- [ ] Secrets créés dans le namespace `rhdemo-stagingkub`
- [ ] Certificats SSL générés
- [ ] `/etc/hosts` mis à jour
- [ ] Image Docker construite et poussée vers le registry
- [ ] Helm chart déployé
- [ ] Tous les pods en status `Running`
- [ ] Gateway et HTTPRoutes configurés
- [ ] Application accessible via https://rhdemo-stagingkub.intra.leuwen-lc.fr
