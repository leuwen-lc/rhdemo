# Analyse des problèmes d'accès Jenkins → stagingkub

## 🔍 Problèmes identifiés et résolus

### 1. ❌ PROBLÈME : Accès au Registry Docker

**Symptôme** :
```
❌ Erreur: Registry sur le port 5000 mais pas accessible via HTTP
```

**Cause** :
- Jenkins tourne dans un container Docker
- `localhost:5000` dans le contexte de Jenkins fait référence au container Jenkins lui-même, pas à l'hôte
- Le registry `rhdemo-docker-registry` est sur un réseau Docker différent

**Solution appliquée** : [Jenkinsfile:902-918](../../../Jenkinsfile#L902-L918)
- Détection dynamique du nom du registry : `docker ps --filter "publish=5000"`
- Utilisation du nom DNS du container : `http://$REGISTRY_NAME:5000`
- Fallback sur `localhost:5000` si l'accès par nom échoue
- Variable `$REGISTRY_URL` utilisée pour toutes les vérifications HTTP

**Résultat** :
```bash
✅ Registry détecté: rhdemo-docker-registry
✅ Registry accessible via le réseau Docker
```

---

### 2. ❌ PROBLÈME : Accès au cluster Kubernetes (KinD)

**Symptôme** :
```
Unable to connect to the server: dial tcp 127.0.0.1:33309: connect: connection refused
```

**Cause** :
- Jenkins n'était PAS connecté au réseau Docker `kind`
- La kubeconfig par défaut utilise `https://127.0.0.1:33309` qui n'est pas accessible depuis le container Jenkins
- L'API Kubernetes est accessible via `https://rhdemo-control-plane:6443` sur le réseau `kind`

**Solutions appliquées** :

#### a) Connexion réseau
```bash
docker network connect kind rhdemo-jenkins
```

#### b) Configuration kubectl dynamique : [Jenkinsfile-CD:233-287](../Jenkinsfile-CD#L233-L287)

Étape dans le pipeline : `☸️ Configure Kubernetes Access`

Cette étape :
1. ✅ Vérifie que le cluster KinD existe
2. ✅ Connecte Jenkins au réseau `kind` automatiquement
3. ✅ **Connecte le registry au réseau `kind` automatiquement** (ajouté 2026-01-09)
4. ✅ Génère une kubeconfig adaptée avec `https://rhdemo-control-plane:6443`
5. ✅ Installe la kubeconfig dans `$HOME/.kube/config`
6. ✅ Vérifie l'accès avec `kubectl cluster-info`
7. ✅ Active le contexte `kind-rhdemo`

**Code clé** :
```bash
# Connexion automatique de Jenkins au réseau kind
JENKINS_CONTAINER=$(hostname)
if ! docker network inspect kind 2>/dev/null | grep -q "$JENKINS_CONTAINER"; then
    docker network connect kind $JENKINS_CONTAINER
fi

# Connexion automatique du registry au réseau kind (ajouté 2026-01-09)
REGISTRY_CONTAINER=$(docker ps --filter "publish=5000" --format '{{.Names}}' | head -n 1)
if [ -n "$REGISTRY_CONTAINER" ]; then
    if ! docker network inspect kind 2>/dev/null | grep -q "$REGISTRY_CONTAINER"; then
        docker network connect kind $REGISTRY_CONTAINER
    fi
fi

# Génération kubeconfig avec nom DNS interne
kind get kubeconfig --name rhdemo | \
    sed 's|https://127.0.0.1:[0-9]*|https://rhdemo-control-plane:6443|g' \
    > $HOME/.kube/config
```

**Résultat** :
```bash
✅ Jenkins déjà connecté au réseau kind
✅ Registry 'rhdemo-docker-registry' déjà connecté au réseau kind (IP: 172.21.0.4)
✅ Configuration kubectl installée
✅ Accès au cluster KinD confirmé
✅ Contexte 'kind-rhdemo' activé
```

---

### 3. ❌ PROBLÈME : ImagePullBackOff sur les pods Kubernetes (ajouté 2026-01-09)

**Symptôme** :
```bash
rhdemo-app-56bd96bc49-7tbvd   0/1     ImagePullBackOff   0   46h
```

```
Events:
  Type     Reason   Age                 From     Message
  ----     ------   ----                ----     -------
  Normal   Pulling  31m (x58 over 5h)   kubelet  Pulling image "localhost:5000/rhdemo-api:latest"
  Warning  Failed   4m (x1317 over 5h)  kubelet  Error: ImagePullBackOff
```

**Cause** :
- Le registry Docker `rhdemo-docker-registry` n'était **pas connecté au réseau `kind`**
- Les pods Kubernetes dans le cluster KinD essaient de pull l'image via `localhost:5000`
- `localhost` depuis un pod Kubernetes fait référence au pod lui-même, pas à l'hôte
- Le cluster KinD ne peut accéder au registry que s'il est sur le même réseau Docker

**Diagnostic** :
```bash
# Vérifier que le registry existe
docker ps | grep registry
# ✅ rhdemo-docker-registry existe et écoute sur 0.0.0.0:5000

# Vérifier que l'image existe dans le registry
curl http://localhost:5000/v2/rhdemo-api/tags/list
# ✅ {"name":"rhdemo-api","tags":["latest",...]}

# Vérifier la connexion réseau du registry
docker network inspect kind | grep rhdemo-docker-registry
# ❌ Pas de résultat - registry NON connecté au réseau kind
```

**Solution appliquée** : [Jenkinsfile-CD:260-279](../Jenkinsfile-CD#L260-L279)

Ajout dans le stage `☸️ Configure Kubernetes Access` :
```bash
# Connecter le registry au réseau kind si nécessaire
REGISTRY_CONTAINER=$(docker ps --filter "publish=5000" --format '{{.Names}}' | head -n 1)
if [ -n "$REGISTRY_CONTAINER" ]; then
    if ! docker network inspect kind 2>/dev/null | grep -q "$REGISTRY_CONTAINER"; then
        echo "⚠️  Registry '$REGISTRY_CONTAINER' NON connecté au réseau kind"
        echo "▶ Connexion du registry au réseau kind..."
        docker network connect kind $REGISTRY_CONTAINER
        echo "✅ Registry connecté au réseau kind"
    else
        echo "✅ Registry déjà connecté au réseau kind"
    fi
fi
```

**Résolution manuelle (si nécessaire)** :
```bash
# Connecter manuellement le registry au réseau kind
docker network connect kind rhdemo-docker-registry

# Supprimer le pod en erreur pour forcer une nouvelle tentative de pull
kubectl delete pod rhdemo-app-56bd96bc49-7tbvd -n rhdemo-stagingkub

# Vérifier que le nouveau pod démarre correctement
kubectl get pods -n rhdemo-stagingkub -w
```

**Résultat** :
```bash
✅ Registry connecté au réseau kind (IP: 172.21.0.4)
✅ Pod rhdemo-app passe de ImagePullBackOff à Running
✅ Application accessible via https://rhdemo.stagingkub.local
```

**Prévention** :
- Le pipeline Jenkinsfile-CD vérifie et connecte automatiquement le registry à chaque déploiement
- Le script `init-stagingkub.sh` connecte le registry lors de l'initialisation du cluster

---

### 4. ✅ VÉRIFICATION : Commandes kubectl et helm

Toutes les commandes suivantes fonctionnent maintenant correctement depuis Jenkins :

| Commande | Stage | Ligne | Statut |
|----------|-------|-------|--------|
| `kubectl config use-context kind-rhdemo` | Update Secrets | 1015 | ✅ OK |
| `kubectl create secret ...` | Update Secrets | 1018-1037 | ✅ OK |
| `helm upgrade --install ...` | Deploy to Kubernetes | 1061 | ✅ OK |
| `kubectl get pods` | Deploy to Kubernetes | 1075 | ✅ OK |
| `kubectl get svc` | Deploy to Kubernetes | 1078 | ✅ OK |
| `kubectl get ingress` | Deploy to Kubernetes | 1081 | ✅ OK |
| `kubectl wait --for=condition=ready` | Wait for Readiness | 1103-1110 | ✅ OK |

---

## 🌐 Architecture réseau finale

### Réseaux Docker

```
┌─────────────────────────────────────────────────────────────┐
│                     Réseau: kind                             │
│                                                              │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────────┐ │
│  │ rhdemo-jenkins   │  │ rhdemo-registry │  │ rhdemo-    │ │
│  │                  │  │                 │  │ control-   │ │
│  │ IP: 172.21.0.x   │  │ IP: 172.21.0.3  │  │ plane      │ │
│  │                  │  │                 │  │            │ │
│  │                  │  │ Alias: registry │  │ :6443 API  │ │
│  └──────────────────┘  └─────────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Réseau: rhdemo-jenkins-network                  │
│                                                              │
│  ┌──────────────────┐  ┌─────────────────┐                 │
│  │ rhdemo-jenkins   │  │ rhdemo-registry │                 │
│  │                  │  │                 │                 │
│  │ IP: 172.18.0.6   │  │ IP: 172.18.0.3  │                 │
│  │                  │  │                 │                 │
│  │ Port: 8080       │  │ Port: 5000      │                 │
│  └──────────────────┘  └─────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

### Accès depuis Jenkins

| Cible | Depuis Jenkins (container) | Protocole | Port |
|-------|----------------------------|-----------|------|
| Registry Docker | `http://rhdemo-docker-registry:5000` | HTTP | 5000 |
| KinD API Server | `https://rhdemo-control-plane:6443` | HTTPS | 6443 |
| KinD Ingress (HTTP) | Via hôte `http://localhost:80` | HTTP | 80 |
| KinD Ingress (HTTPS) | Via hôte `https://localhost:443` | HTTPS | 443 |

---

## 🔧 Scripts modifiés

### 1. Jenkinsfile
- **Ajout** : Stage `☸️ Configure Kubernetes Access` (lignes 862-919)
- **Modification** : Stage `☸️ Push Image to Local Registry` (lignes 921-995)
  - Détection dynamique du registry
  - Accès via nom DNS container

### 2. init-stagingkub.sh
- **Modification** : Détection et réutilisation de registries existants (lignes 47-79)
- **Modification** : Affichage du nom réel du registry (lignes 276-279)

### 3. deploy.sh
- **Modification** : Détection du registry avec messages adaptés (lignes 51-69)

### 4. validate.sh
- **Modification** : Détection et validation du registry (lignes 58-103)

---

## ✅ Checklist de déploiement stagingkub

Avant de lancer un build Jenkins avec `DEPLOY_ENV=stagingkub` :

- [ ] Cluster KinD créé : `kind get clusters | grep rhdemo`
- [ ] Registry actif : `docker ps | grep registry`
- [ ] Jenkins démarré : `docker ps | grep rhdemo-jenkins`
- [ ] Jenkins connecté au réseau kind : `docker network inspect kind | grep rhdemo-jenkins`
- [ ] **Registry connecté au réseau kind** : `docker network inspect kind | grep registry` ⚠️ **Critique pour éviter ImagePullBackOff**
- [ ] Secrets SOPS disponibles : `ls rhDemo/secrets/env-vars.sh`

**Note** : Les connexions Jenkins et Registry au réseau kind sont vérifiées et établies automatiquement par le pipeline Jenkinsfile-CD (stage `☸️ Configure Kubernetes Access`).

**Commande d'initialisation** :
```bash
cd rhDemo/infra/stagingkub
./scripts/init-stagingkub.sh
```

**Commande de validation** :
```bash
cd rhDemo/infra/stagingkub
./scripts/validate.sh
```

---

## 🐛 Dépannage

### Erreur : "Registry non accessible"
```bash
# Vérifier que le registry tourne
docker ps | grep registry

# Vérifier la connectivité réseau
docker network inspect kind | grep registry
docker network inspect rhdemo-jenkins-network | grep registry

# Redémarrer le registry si nécessaire
docker restart rhdemo-docker-registry
```

### Erreur : "Unable to connect to Kubernetes cluster"
```bash
# Vérifier que Jenkins est sur le réseau kind
docker network inspect kind | grep rhdemo-jenkins

# Reconnecter manuellement si nécessaire
docker network connect kind rhdemo-jenkins

# Vérifier depuis Jenkins
docker exec rhdemo-jenkins kubectl cluster-info
```

### Erreur : "kind: command not found" dans Jenkins
```bash
# Vérifier que kind est installé dans l'image Jenkins
docker exec rhdemo-jenkins which kind

# Si absent, vérifier le Dockerfile.jenkins
cat rhDemo/infra/jenkins-docker/Dockerfile.jenkins | grep kind
```

### Commandes kubectl échouent dans le pipeline
```bash
# Tester l'accès manuellement
docker exec rhdemo-jenkins kubectl get nodes

# Vérifier la kubeconfig
docker exec rhdemo-jenkins cat /var/jenkins_home/.kube/config

# Recréer la kubeconfig
kind get kubeconfig --name rhdemo | \
    sed 's|https://127.0.0.1:[0-9]*|https://rhdemo-control-plane:6443|g' | \
    docker exec -i rhdemo-jenkins tee /var/jenkins_home/.kube/config
```

---

## 📚 Références

- [Docker networking](https://docs.docker.com/network/)
- [KinD documentation](https://kind.sigs.k8s.io/)
- [Kubectl configuration](https://kubernetes.io/docs/tasks/access-application-cluster/configure-access-multiple-clusters/)
- [Docker Registry API](https://docs.docker.com/registry/spec/api/)

---

## 📝 Historique des modifications

| Date | Modification | Auteur |
|------|-------------|--------|
| 2025-12-11 | Création initiale - Connexion Jenkins au réseau kind | Claude Code |
| 2026-01-09 | Ajout connexion automatique du registry au réseau kind | Claude Code |

---

**Date de création** : 2025-12-11
**Dernière mise à jour** : 2026-01-09
**Auteur** : Configuration automatisée via Claude Code
