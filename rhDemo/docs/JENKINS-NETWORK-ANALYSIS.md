# Analyse des problèmes d'accès Jenkins Agent → stagingkub

## 🔍 Problèmes identifiés et résolus

### 1. ❌ PROBLÈME : Accès au Registry Docker

**Symptôme** :
```
❌ Erreur: Registry sur le port 5000 mais pas accessible via HTTP
```

**Cause** :
- L'agent Jenkins (builder) tourne dans un container Docker
- `localhost:5000` dans le contexte de l'agent fait référence au container agent lui-même, pas à l'hôte
- Le registry `kind-registry` est sur un réseau Docker différent

**Note importante** : Le registry doit s'appeler **exactement** `kind-registry` pour garantir la résolution DNS dans le cluster KinD. Voir [REGISTRY_SETUP.md](REGISTRY_SETUP.md) pour plus de détails.

**Solution appliquée** :
- Détection dynamique du nom du registry : `docker ps --filter "publish=5000"`
- Vérification que le nom est exactement `kind-registry` (sinon échec du pipeline)
- Utilisation du nom DNS du container : `http://localhost:5000` ou `http://kind-registry:5000`
- Variable `$REGISTRY_URL` utilisée pour toutes les vérifications HTTP

**Résultat** :
```bash
✅ Registry détecté: kind-registry
✅ Nom validé: kind-registry
✅ Registry accessible via le réseau Docker
```

---

### 2. ❌ PROBLÈME : Accès au cluster Kubernetes (KinD)

**Symptôme** :
```
Unable to connect to the server: dial tcp 127.0.0.1:33309: connect: connection refused
```

**Cause** :
- L'agent Jenkins n'était PAS connecté au réseau Docker `kind`
- La kubeconfig par défaut utilise `https://127.0.0.1:33309` qui n'est pas accessible depuis le container agent
- L'API Kubernetes est accessible via `https://rhdemo-control-plane:6443` sur le réseau `kind`

**Solutions appliquées** :

#### a) Connexion réseau
```bash
docker network connect kind rhdemo-jenkins-agent
```

#### b) Configuration kubectl dynamique : [Jenkinsfile-CD:233-305](../Jenkinsfile-CD#L233-L305)

Étape dans le pipeline : `☸️ Configure Kubernetes Access`

Cette étape :
1. ✅ Vérifie que le cluster KinD existe
2. ✅ Connecte Jenkins au réseau `kind` automatiquement
3. ✅ **Vérifie que le registry s'appelle `kind-registry`** (échoue sinon)
4. ✅ **Connecte le registry au réseau `kind` automatiquement avec alias DNS `kind-registry`**
5. ✅ Génère une kubeconfig adaptée avec `https://rhdemo-control-plane:6443`
6. ✅ Installe la kubeconfig dans `$HOME/.kube/config`
7. ✅ Vérifie l'accès avec `kubectl cluster-info`
8. ✅ Active le contexte `kind-rhdemo`

**Code clé** :
```bash
# Connexion automatique de l'agent au réseau kind
AGENT_CONTAINER=$(hostname)
if ! docker network inspect kind 2>/dev/null | grep -q "$AGENT_CONTAINER"; then
    docker network connect kind $AGENT_CONTAINER
fi

# Vérification du nom du registry (DOIT être 'kind-registry')
REGISTRY_CONTAINER=$(docker ps --filter "publish=5000" --format '{{.Names}}' | head -n 1)
if [ "$REGISTRY_CONTAINER" != "kind-registry" ]; then
    echo "❌ ERREUR: Registry trouvé '$REGISTRY_CONTAINER' mais le nom attendu est 'kind-registry'"
    exit 1
fi

# Connexion automatique du registry au réseau kind avec alias DNS
if ! docker network inspect kind 2>/dev/null | grep -q "$REGISTRY_CONTAINER"; then
    docker network disconnect kind $REGISTRY_CONTAINER 2>/dev/null || true
    docker network connect kind $REGISTRY_CONTAINER --alias kind-registry
fi

# Génération kubeconfig avec nom DNS interne
kind get kubeconfig --name rhdemo | \
    sed 's|https://127.0.0.1:[0-9]*|https://rhdemo-control-plane:6443|g' \
    > $HOME/.kube/config
```

**Résultat** :
```bash
✅ Agent déjà connecté au réseau kind
✅ Registry 'kind-registry' validé
✅ Registry déjà connecté au réseau kind avec alias 'kind-registry' (IP: 172.21.0.4)
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
- Le registry Docker `kind-registry` n'était **pas connecté au réseau `kind`** avec l'alias DNS approprié
- Les pods Kubernetes dans le cluster KinD essaient de pull l'image via `localhost:5000`
- Containerd dans KinD redirige `localhost:5000` vers `kind-registry:5000` (via mirror config)
- Sans l'alias DNS `kind-registry`, la résolution échoue
- Le cluster KinD ne peut accéder au registry que s'il est sur le même réseau Docker avec le bon alias

**Diagnostic** :
```bash
# Vérifier que le registry existe
docker ps | grep registry
# ✅ kind-registry existe et écoute sur 0.0.0.0:5000

# Vérifier que l'image existe dans le registry
curl http://localhost:5000/v2/rhdemo-api/tags/list
# ✅ {"name":"rhdemo-api","tags":["latest",...]}

# Vérifier la connexion réseau du registry
docker network inspect kind | grep kind-registry
# ❌ Pas de résultat - registry NON connecté au réseau kind
```

**Solution appliquée** : [Jenkinsfile-CD:260-300](../Jenkinsfile-CD#L260-L300)

Ajout dans le stage `☸️ Configure Kubernetes Access` :
```bash
# Vérifier que le registry s'appelle 'kind-registry' (OBLIGATOIRE)
REGISTRY_CONTAINER=$(docker ps --filter "publish=5000" --format '{{.Names}}' | head -n 1)
if [ "$REGISTRY_CONTAINER" != "kind-registry" ]; then
    echo "❌ ERREUR: Registry trouvé '$REGISTRY_CONTAINER' mais le nom attendu est 'kind-registry'"
    exit 1
fi

# Connecter le registry au réseau kind avec alias DNS
if ! docker network inspect kind 2>/dev/null | grep -q "$REGISTRY_CONTAINER"; then
    docker network disconnect kind $REGISTRY_CONTAINER 2>/dev/null || true
    docker network connect kind $REGISTRY_CONTAINER --alias kind-registry
else
    # Vérifier l'alias
    if ! docker network inspect kind 2>/dev/null | grep -q '"kind-registry"'; then
        docker network disconnect kind $REGISTRY_CONTAINER 2>/dev/null || true
        docker network connect kind $REGISTRY_CONTAINER --alias kind-registry
    fi
fi
```

**Résolution manuelle (si nécessaire)** :
```bash
# Vérifier le nom du registry
docker ps --filter "publish=5000" --format '{{.Names}}'
# DOIT afficher: kind-registry

# Si le nom est incorrect, recréer le registry
docker stop <mauvais-nom> && docker rm <mauvais-nom>
cd rhDemo/infra/jenkins-docker && docker-compose up -d registry

# Connecter le registry au réseau kind avec alias
docker network disconnect kind kind-registry 2>/dev/null || true
docker network connect kind kind-registry --alias kind-registry

# Supprimer le pod en erreur pour forcer une nouvelle tentative de pull
kubectl delete pod rhdemo-app-56bd96bc49-7tbvd -n rhdemo-stagingkub

# Vérifier que le nouveau pod démarre correctement
kubectl get pods -n rhdemo-stagingkub -w
```

**Résultat** :
```bash
✅ Registry 'kind-registry' validé
✅ Registry connecté au réseau kind avec alias 'kind-registry' (IP: 172.21.0.4)
✅ Pod rhdemo-app passe de ImagePullBackOff à Running
✅ Application accessible via https://rhdemo-stagingkub.intra.leuwen-lc.fr
```

**Prévention** :
- Le pipeline Jenkinsfile-CD vérifie le nom du registry et échoue si incorrect
- Le pipeline connecte automatiquement le registry avec l'alias à chaque déploiement
- Le script `init-stagingkub.sh` connecte le registry avec l'alias lors de l'initialisation du cluster
- Voir [REGISTRY_SETUP.md](REGISTRY_SETUP.md) pour la documentation complète

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

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                          Réseau: kind                                    │
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌────────────┐          │
│  │ agent éphémère      │  │ kind-registry   │  │ rhdemo-    │          │
│  │ (créé par build,    │  │ (container)     │  │ control-   │          │
│  │  nom = hash court)  │  │ IP: 172.21.0.3  │  │ plane      │          │
│  │                     │  │                 │  │            │          │
│  │                     │  │ Alias DNS:      │  │ :6443 API  │          │
│  │                     │  │ kind-registry   │  │            │          │
│  └─────────────────────┘  └─────────────────┘  └────────────┘          │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│              Réseau: rhdemo-jenkins-network                               │
│                                                                          │
│  ┌──────────────────┐  ┌────────────────────────┐  ┌─────────────────┐  │
│  │ rhdemo-jenkins   │  │ rhdemo-docker-socket-  │  │ kind-registry   │  │
│  │ (controller)     │  │ proxy (API filtrée)    │  │                 │  │
│  │ Port: 8080       │  │ Port TCP: 2375         │  │ Port: 5000      │  │
│  └──────────────────┘  └────────────────────────┘  └─────────────────┘  │
│                                                                          │
│  Agents éphémères : créés dynamiquement par Docker Cloud lors des builds │
│  et détruits immédiatement après. Connexion au réseau kind dynamique.    │
└──────────────────────────────────────────────────────────────────────────┘
```

**Note importante** : Le registry doit avoir le nom exact `kind-registry` et l'alias DNS `kind-registry` sur le réseau `kind` pour que containerd dans KinD puisse résoudre `kind-registry:5000`.

### Accès depuis l'agent Jenkins

| Cible | Depuis l'agent (container) | Protocole | Port |
|-------|----------------------------|-----------|------|
| Registry Docker | `http://localhost:5000` ou `http://kind-registry:5000` | HTTP | 5000 |
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
- [ ] **Registry nommé `kind-registry`** : `docker ps --filter "publish=5000" --format '{{.Names}}'` ⚠️ **DOIT afficher exactement `kind-registry`**
- [ ] Registry actif : `docker ps | grep kind-registry`
- [ ] Jenkins démarré : `docker ps | grep rhdemo-jenkins`
- [ ] Proxy socket démarré : `docker ps | grep rhdemo-docker-socket-proxy`
- [ ] **Registry nommé `kind-registry`** : `docker ps --filter "publish=5000" --format '{{.Names}}'`
- [ ] **Registry connecté au réseau kind avec alias** : `docker network inspect kind | grep -A2 kind-registry | grep Aliases` ⚠️ **Critique pour éviter ImagePullBackOff**
- [ ] Secrets SOPS disponibles : `ls rhDemo/secrets/env-vars.sh`

**Note** :
- Il n'y a plus d'agent permanent à démarrer — les agents éphémères sont créés automatiquement par le Docker Cloud au déclenchement d'un build
- La connexion de l'agent (éphémère) et du Registry au réseau kind est vérifiée et établie automatiquement par le pipeline Jenkinsfile-CD (stage `☸️ Configure Kubernetes Access`)
- L'agent éphémère est identifié par son hash court (`$(hostname)`) — ce pattern fonctionne sans modification dans les pipelines
- Voir [REGISTRY_SETUP.md](REGISTRY_SETUP.md) pour la configuration complète du registry

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
docker ps | grep kind-registry

# Vérifier le nom exact
docker ps --filter "publish=5000" --format '{{.Names}}'
# DOIT afficher: kind-registry

# Si le nom est incorrect, recréer le registry
docker stop <mauvais-nom> && docker rm <mauvais-nom>
cd rhDemo/infra/jenkins-docker && docker-compose up -d registry

# Vérifier la connectivité réseau
docker network inspect kind | grep kind-registry
docker network inspect rhdemo-jenkins-network | grep kind-registry

# Vérifier l'alias DNS sur le réseau kind
docker network inspect kind | grep -A2 kind-registry | grep Aliases

# Reconnecter avec alias si nécessaire
docker network disconnect kind kind-registry 2>/dev/null || true
docker network connect kind kind-registry --alias kind-registry

# Redémarrer le registry si nécessaire
docker restart kind-registry
```

### Erreur : "Unable to connect to Kubernetes cluster"
```bash
# Identifier le conteneur de l'agent éphémère en cours
AGENT=$(docker ps --filter "ancestor=rhdemo-jenkins-agent" --format '{{.Names}}' | head -n1)

# Vérifier que l'agent est sur le réseau kind
docker network inspect kind | grep "$AGENT"

# Reconnecter manuellement si nécessaire
docker network connect kind "$AGENT"

# Vérifier depuis l'agent
docker exec "$AGENT" kubectl cluster-info
```

> **Note** : Avec les agents éphémères, il n'y a plus de conteneur `rhdemo-jenkins-agent` permanent. Le conteneur actif se trouve via `docker ps --filter ancestor=rhdemo-jenkins-agent`.

### Erreur : "kind: command not found" dans Jenkins

C'est **normal** et voulu. `kind` CLI n'est PAS installé sur l'agent pour des raisons de sécurité (RBAC - moindre privilège). L'agent utilise un kubeconfig RBAC pré-provisionné avec des permissions limitées. La gestion du cluster KinD se fait uniquement depuis la machine hôte.

### Commandes kubectl échouent dans le pipeline
```bash
# Identifier le conteneur de l'agent éphémère en cours
AGENT=$(docker ps --filter "ancestor=rhdemo-jenkins-agent" --format '{{.Names}}' | head -n1)

# Tester l'accès manuellement depuis l'agent
docker exec "$AGENT" kubectl get nodes

# Vérifier la kubeconfig sur l'agent
docker exec "$AGENT" cat /home/jenkins/.kube/config

# Recréer la kubeconfig (depuis l'hôte)
kind get kubeconfig --name rhdemo | \
    sed 's|https://127.0.0.1:[0-9]*|https://rhdemo-control-plane:6443|g' | \
    docker exec -i "$AGENT" tee /home/jenkins/.kube/config
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
| 2026-01-15 | Standardisation nom registry → `kind-registry` + vérification obligatoire + alias DNS | Claude Code |
| 2026-02-08 | Mise à jour architecture master/agent : l'agent (builder) remplace le master pour les connexions réseau | Claude Code |
| 2026-04-20 | Migration vers agents éphémères Docker Cloud + docker-socket-proxy : suppression agent permanent, mise à jour architecture, checklist et dépannage | Claude Code |

---

**Date de création** : 2025-12-11
**Dernière mise à jour** : 2026-02-08
**Auteur** : Configuration automatisée via Claude Code

**Voir aussi** :
- [REGISTRY_SETUP.md](REGISTRY_SETUP.md) - Configuration complète du registry Docker local
