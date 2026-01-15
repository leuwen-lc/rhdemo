# Configuration du Registry Docker Local

## 📋 Vue d'ensemble

Le projet utilise un **registry Docker local** unique pour tous les environnements (Jenkins CI/CD et Kind stagingkub).

### Principes

- **Nom unique**: `kind-registry` partout
- **Port**: `5000` (localhost:5000)
- **Réseau**: Connecté au réseau Docker `kind` avec alias `kind-registry`
- **Volume**: `kind-registry-data` pour persistance
- **Image**: `registry:2` (officielle)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Host (localhost)                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Registry Container: kind-registry                    │  │
│  │  - Port: 5000:5000                                    │  │
│  │  - Volume: kind-registry-data                         │  │
│  │  - Networks:                                          │  │
│  │    • rhdemo-jenkins-network (pour Jenkins)           │  │
│  │    • kind (pour Kind K8s) + alias "kind-registry"    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────┐    ┌─────────────┐    ┌──────────────┐  │
│  │   Jenkins    │───▶│ kind-       │◀───│ Kind K8s     │  │
│  │   Container  │    │ registry    │    │ (rhdemo)     │  │
│  │              │    │ :5000       │    │              │  │
│  └──────────────┘    └─────────────┘    └──────────────┘  │
│                                                             │
│  Accès depuis host: localhost:5000                         │
│  Accès depuis Jenkins: kind-registry:5000                  │
│  Accès depuis Kind: localhost:5000 → kind-registry:5000    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Configuration

### 1. Création du Registry (jenkins-docker/docker-compose.yml)

```yaml
services:
  registry:
    image: registry:2
    container_name: kind-registry  # ✅ Nom standardisé
    networks:
      - rhdemo-jenkins-network
    ports:
      - "5000:5000"
    restart: always
    volumes:
      - registry_data:/var/lib/registry

volumes:
  registry_data:
    name: kind-registry-data  # ✅ Volume standardisé
```

**Important**: Le registry est créé par `docker-compose up` dans jenkins-docker et persiste grâce au volume nommé.

### 2. Connexion au Réseau Kind (init-stagingkub.sh)

```bash
# Connecter le registry au réseau kind avec l'alias
REGISTRY_NAME=$(docker ps --filter "publish=5000" --format '{{.Names}}' | head -n 1)

if [ -n "$REGISTRY_NAME" ]; then
    # Déconnecter puis reconnecter avec alias
    docker network disconnect kind "$REGISTRY_NAME" 2>/dev/null || true
    docker network connect kind "$REGISTRY_NAME" --alias kind-registry
fi
```

**Rôle de l'alias**: Permet à Kind de résoudre `kind-registry` vers l'IP du registry sur le réseau Docker.

### 3. Configuration Containerd dans Kind

Kind est configuré (via `kind-config.yaml`) pour rediriger `localhost:5000` vers `kind-registry:5000`:

```yaml
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]
    endpoint = ["http://kind-registry:5000"]
```

**Résultat**: Les pods Kubernetes peuvent pull `localhost:5000/image:tag` et containerd redirige vers `kind-registry:5000`.

---

## 🚀 Utilisation

### Démarrage du Registry

**Première fois (avec Jenkins):**
```bash
cd rhDemo/infra/jenkins-docker
docker-compose up -d registry
```

**Vérification:**
```bash
# Vérifier que le registry tourne
docker ps --filter name=kind-registry

# Tester l'accès
curl http://localhost:5000/v2/_catalog
```

### Publication d'une Image (CI)

**Dans Jenkinsfile-CI:**
```groovy
// Tag et push vers le registry
sh """
    docker tag rhdemo-api:${VERSION} localhost:5000/rhdemo-api:${VERSION}
    docker push localhost:5000/rhdemo-api:${VERSION}
"""
```

### Déploiement avec Kind (CD)

**Dans Jenkinsfile-CD:**
```groovy
// Déploiement Helm avec image du registry
helm upgrade --install rhdemo ... \
  --set rhdemo.image.repository=localhost:5000/rhdemo-api \
  --set rhdemo.image.tag=${VERSION}
```

**Kubernetes pull l'image:**
- Pod demande: `localhost:5000/rhdemo-api:1.0.0`
- Containerd redirige vers: `http://kind-registry:5000`
- Résolution DNS dans réseau kind: `kind-registry` → IP du container
- Image téléchargée depuis le registry

---

## 🔍 Vérifications

### Vérifier la Connexion au Réseau Kind

```bash
# Lister les conteneurs sur le réseau kind
docker network inspect kind | jq -r '.[0].Containers | to_entries[] | "\(.value.Name) - \(.value.IPv4Address)"'

# Devrait afficher:
# kind-registry - 172.21.0.X/16
# rhdemo-control-plane - 172.21.0.Y/16
```

### Vérifier l'Alias DNS

```bash
# Depuis le node Kind
docker exec rhdemo-control-plane getent hosts kind-registry

# Devrait afficher:
# <IPv6> kind-registry
# <IPv4> kind-registry
```

### Vérifier l'Accès au Registry depuis Kind

```bash
# Test HTTP depuis le node Kind
docker exec rhdemo-control-plane curl -s http://kind-registry:5000/v2/_catalog

# Devrait afficher:
# {"repositories":["rhdemo-api",...]}
```

### Vérifier la Configuration Containerd

```bash
# Voir la config containerd
docker exec rhdemo-control-plane cat /etc/containerd/config.toml | grep -A5 "localhost:5000"

# Devrait afficher:
# [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]
#   endpoint = ["http://kind-registry:5000"]
```

---

## 🐛 Dépannage

### Problème: Image Pull Error

**Symptôme**: `ImagePullBackOff` sur les pods

**Diagnostic:**
```bash
# 1. Vérifier que le registry tourne
docker ps --filter name=kind-registry

# 2. Vérifier que l'image existe
curl http://localhost:5000/v2/rhdemo-api/tags/list

# 3. Vérifier la connexion réseau
docker network inspect kind | grep kind-registry

# 4. Vérifier l'alias DNS
docker exec rhdemo-control-plane getent hosts kind-registry
```

**Solution si l'alias manque:**
```bash
REGISTRY=$(docker ps --filter "publish=5000" --format '{{.Names}}' | head -n 1)
docker network disconnect kind "$REGISTRY" 2>/dev/null || true
docker network connect kind "$REGISTRY" --alias kind-registry
```

### Problème: Registry Inaccessible depuis Jenkins

**Symptôme**: `Cannot connect to registry` dans pipeline CI

**Diagnostic:**
```bash
# Vérifier le réseau Jenkins
docker exec rhdemo-jenkins curl -s http://kind-registry:5000/v2/_catalog
```

**Solution:**
```bash
# Reconnecter Jenkins au réseau kind si nécessaire
JENKINS=$(docker ps --filter name=jenkins --format '{{.Names}}' | head -n 1)
docker network connect kind "$JENKINS" 2>/dev/null || true
```

### Problème: Deux Registries Existent

**Symptôme**: `rhdemo-docker-registry` et `kind-registry` coexistent

**Solution: Nettoyer et recréer**
```bash
# Arrêter et supprimer l'ancien registry
docker stop rhdemo-docker-registry kind-registry 2>/dev/null || true
docker rm rhdemo-docker-registry kind-registry 2>/dev/null || true

# Supprimer les volumes orphelins
docker volume rm rhdemo-docker-registry 2>/dev/null || true

# Recréer via docker-compose
cd rhDemo/infra/jenkins-docker
docker-compose up -d registry

# Connecter au réseau kind
REGISTRY=$(docker ps --filter "publish=5000" --format '{{.Names}}' | head -n 1)
docker network connect kind "$REGISTRY" --alias kind-registry
```

---

## 📝 Checklist d'Installation

- [ ] **1. Créer le registry**
  ```bash
  cd rhDemo/infra/jenkins-docker
  docker-compose up -d registry
  ```

- [ ] **2. Vérifier l'accès**
  ```bash
  curl http://localhost:5000/v2/_catalog
  ```

- [ ] **3. Créer le cluster Kind**
  ```bash
  cd rhDemo/infra/stagingkub
  ./scripts/init-stagingkub.sh
  ```
  *(Le script connecte automatiquement le registry au réseau kind)*

- [ ] **4. Vérifier l'alias**
  ```bash
  docker exec rhdemo-control-plane getent hosts kind-registry
  ```

- [ ] **5. Tester le pull depuis Kind**
  ```bash
  kubectl run test --image=localhost:5000/rhdemo-api:latest --rm -it -n rhdemo-stagingkub
  ```

---

## 🔗 Références

- [Kind - Local Registry](https://kind.sigs.k8s.io/docs/user/local-registry/)
- [Docker Registry Documentation](https://docs.docker.com/registry/)
- [Containerd Registry Configuration](https://github.com/containerd/containerd/blob/main/docs/hosts.md)

---

## 📚 Fichiers Concernés

| Fichier | Rôle |
|---------|------|
| `infra/jenkins-docker/docker-compose.yml` | Création du registry |
| `infra/stagingkub/kind-config.yaml` | Config containerd pour redirection localhost:5000 |
| `infra/stagingkub/scripts/init-stagingkub.sh` | Connexion registry au réseau kind |
| `Jenkinsfile-CI` | Publication images dans le registry |
| `Jenkinsfile-CD` | Déploiement images depuis le registry |
