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

#### b) Configuration kubectl dynamique : [Jenkinsfile:862-919](../../../Jenkinsfile#L862-L919)

Nouvelle étape ajoutée au pipeline : `☸️ Configure Kubernetes Access`

Cette étape :
1. ✅ Vérifie que le cluster KinD existe
2. ✅ Connecte Jenkins au réseau `kind` automatiquement
3. ✅ Génère une kubeconfig adaptée avec `https://rhdemo-control-plane:6443`
4. ✅ Installe la kubeconfig dans `$HOME/.kube/config`
5. ✅ Vérifie l'accès avec `kubectl cluster-info`
6. ✅ Active le contexte `kind-rhdemo`

**Code clé** :
```bash
# Connexion automatique au réseau kind
JENKINS_CONTAINER=$(hostname)
if ! docker network inspect kind 2>/dev/null | grep -q "$JENKINS_CONTAINER"; then
    docker network connect kind $JENKINS_CONTAINER
fi

# Génération kubeconfig avec nom DNS interne
kind get kubeconfig --name rhdemo | \
    sed 's|https://127.0.0.1:[0-9]*|https://rhdemo-control-plane:6443|g' \
    > $HOME/.kube/config
```

**Résultat** :
```bash
✅ Jenkins déjà connecté au réseau kind
✅ Configuration kubectl installée
✅ Accès au cluster KinD confirmé
✅ Contexte 'kind-rhdemo' activé
```

---

### 3. ✅ VÉRIFICATION : Commandes kubectl et helm

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
- [ ] Secrets SOPS disponibles : `ls rhDemo/secrets/env-vars.sh`

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

**Date de création** : 2025-12-11
**Dernière mise à jour** : 2025-12-11
**Auteur** : Configuration automatisée via Claude Code
