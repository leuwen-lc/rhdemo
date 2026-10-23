---
statut: actif
verifie_le: 2026-10-23
sources:
  - rhDemo/infra/stagingkub/scripts/init-stagingkub.sh
  - rhDemo/Jenkinsfile-CD
---

# 📦 Registry Docker Local - Guide complet

Ce document explique le fonctionnement du registry Docker local utilisé par stagingkub.

---

## 🎯 Pourquoi un registry local ?

### Problème initial

KinD (Kubernetes in Docker) tourne dans un container Docker. Les images Docker construites sur l'hôte ne sont pas directement accessibles dans le cluster KinD. Il existe plusieurs solutions :

1. ❌ **kind load** : Nécessite le CLI kind, ne fonctionne pas depuis Jenkins
2. ❌ **docker save/load** : Hack, lent, pas production-like
3. ✅ **Registry local** : Solution propre, production-like, fonctionne depuis Jenkins

### Avantages du registry local

- ✅ **Jenkins-friendly** : Utilise uniquement Docker (pas de CLI externe)
- ✅ **Production-like** : Même workflow qu'en production avec DockerHub/Harbor
- ✅ **Cache efficace** : Les layers Docker sont réutilisés
- ✅ **Multi-cluster** : Plusieurs clusters KinD peuvent utiliser le même registry
- ✅ **Débug facile** : API REST pour inspecter les images

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      Docker Host                          │
│                                                           │
│  ┌─────────────────┐                                     │
│  │ Jenkins         │                                     │
│  │  1. Build image │                                     │
│  │  2. docker tag  │                                     │
│  │  3. docker push │──────┐                              │
│  └─────────────────┘      │                              │
│                            ▼                              │
│  ┌──────────────────────────────────────────┐            │
│  │ Registry Container (kind-registry)       │            │
│  │  • Port: 5000                            │            │
│  │  • Image: registry:3 (TLS autosigné)     │            │
│  │  • Réseau: bridge + kind                 │            │
│  │  • Stockage: /var/lib/registry           │            │
│  └──────────────────────────────────────────┘            │
│                            │                              │
│  ┌─────────────────────────▼──────────────────────────┐  │
│  │ KinD Cluster (réseau "kind")                       │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │ Node: rhdemo-control-plane                   │  │  │
│  │  │  • containerd configuré pour utiliser:      │  │  │
│  │  │    https://kind-registry:5000 (CA dédiée)   │  │  │
│  │  │  • Kubernetes pull automatiquement          │  │  │
│  │  │    depuis localhost:5000/rhdemo-api:VERSION │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## 📋 Configuration détaillée

### 1. Origine du registry

Le registry `kind-registry` est normalement démarré par Jenkins (`infra/jenkins-docker/docker-compose.yml`, image `registry:3`) avec un certificat TLS autosigné (`./init-registry-certs.sh`, certificat attendu par l'hôte dans `/etc/docker/certs.d/localhost:5000/ca.crt`).

`init-stagingkub.sh` :
- réutilise un registry actif sur le port 5000, sinon redémarre un conteneur arrêté sur ce port ;
- à défaut, crée un conteneur `kind-registry` de repli (`registry:2`, **sans TLS**) : le contrôle HTTPS qui suit échoue alors. Démarrez donc Jenkins (`docker-compose up -d registry`) avant le script ;
- vérifie ensuite l'accès en HTTPS avec le certificat de la CA.

### 2. Connexion au réseau KinD

```bash
docker network connect kind kind-registry
```

Cela permet au cluster KinD d'accéder au registry via le nom `kind-registry`.

### 3. Configuration du nœud KinD (containerd et CA)

Le cluster KinD est créé sans mirror containerd (voir `kind-config.yaml`). `init-stagingkub.sh` configure ensuite le nœud `rhdemo-control-plane` :

1. copie le certificat de la CA du registry dans `/usr/local/share/ca-certificates/kind-registry.crt` ;
2. met à jour le paquet `ca-certificates` du nœud (correctif de l'incident des CA eMudhra, voir [SECURITE_CA_EMUDHRA_PLAN.md](SECURITE_CA_EMUDHRA_PLAN.md)), puis lance `update-ca-certificates` ;
3. écrit `/etc/containerd/certs.d/localhost:5000/hosts.toml` : serveur `https://kind-registry:5000` avec cette CA.

Quand Kubernetes demande une image `localhost:5000/*`, containerd la télécharge donc en HTTPS depuis `kind-registry:5000`.

---

## 🔄 Workflow de déploiement

### 1. Build de l'image (hôte)

```bash
# Voie standard (celle du pipeline CI) : Dockerfile multi-stage, base Temurin 25
docker build -t rhdemo-api:$(./mvnw -q help:evaluate -Dexpression=project.version -DforceStdout) rhDemo/

# Voie alternative encore configurée dans pom.xml : buildpacks Paketo
./mvnw clean spring-boot:build-image
```

→ Crée l'image `rhdemo-api:<version pom.xml>` sur l'hôte

### 2. Tag pour le registry (hôte)

```bash
docker tag rhdemo-api:1.1.0-SNAPSHOT localhost:5000/rhdemo-api:1.1.0-SNAPSHOT
```

→ Crée un alias pointant vers le registry local

### 3. Push vers le registry (hôte)

```bash
docker push localhost:5000/rhdemo-api:1.1.0-SNAPSHOT
```

→ Pousse l'image vers le registry (port 5000)

### 4. Déploiement Helm (hôte)

```bash
helm upgrade --install rhdemo ./helm/rhdemo \
  --set rhdemo.image.repository=localhost:5000/rhdemo-api \
  --set rhdemo.image.tag=1.1.0-SNAPSHOT
```

→ Kubernetes crée un pod avec l'image `localhost:5000/rhdemo-api:1.1.0-SNAPSHOT`

### 5. Pull de l'image (KinD node)

Quand le pod démarre, Kubernetes demande à containerd de télécharger :
```
localhost:5000/rhdemo-api:1.1.0-SNAPSHOT
```

containerd, grâce à la configuration, va chercher l'image à :
```
https://kind-registry:5000/rhdemo-api:1.1.0-SNAPSHOT
```

---

## 🔍 Commandes utiles

### Vérifier l'état du registry

```bash
# Statut du container
docker ps | grep kind-registry

# Logs du registry
docker logs -f kind-registry

# Santé du registry
curl -k https://localhost:5000/v2/
```

### Inspecter les images

```bash
# Lister toutes les repositories
curl -k https://localhost:5000/v2/_catalog

# Exemple de réponse :
# {"repositories":["rhdemo-api"]}

# Lister les tags d'une image
curl -k https://localhost:5000/v2/rhdemo-api/tags/list

# Exemple de réponse :
# {"name":"rhdemo-api","tags":["1.1.0-SNAPSHOT","1.0.0-RELEASE"]}

# Obtenir le manifest d'une image
curl -k https://localhost:5000/v2/rhdemo-api/manifests/1.1.0-SNAPSHOT
```

### Gérer le registry

```bash
# Démarrer le registry (s'il est arrêté)
docker start kind-registry

# Arrêter le registry
docker stop kind-registry

# Redémarrer le registry
docker restart kind-registry

# Voir les logs en temps réel
docker logs -f kind-registry

# Voir l'utilisation disque
docker exec kind-registry du -sh /var/lib/registry
```

### Supprimer des images

⚠️ **Attention** : La suppression dans un registry v2 est complexe

```bash
# Supprimer une image nécessite l'API delete (désactivée par défaut)
# Pour vraiment nettoyer, il faut :

# 1. Arrêter le registry
docker stop kind-registry

# 2. Supprimer les données
docker rm kind-registry
docker volume rm registry-data  # Si utilisé

# 3. Recréer le registry (avec son certificat TLS, via Jenkins)
cd rhDemo/infra/jenkins-docker && docker-compose up -d registry
docker network connect kind kind-registry
```

---

## 🐛 Troubleshooting

### Problème : Registry non accessible depuis l'hôte

```bash
# Vérifier que le registry tourne
docker ps | grep kind-registry

# Vérifier le port
netstat -tuln | grep 5000

# Tester la connexion
curl -k https://localhost:5000/v2/

# Redémarrer si nécessaire
docker restart kind-registry
```

### Problème : Registry non accessible depuis KinD

```bash
# Vérifier la connexion réseau
docker network inspect kind | grep kind-registry

# Si non connecté, connecter
docker network connect kind kind-registry

# Vérifier depuis le node KinD
docker exec rhdemo-control-plane curl --cacert /usr/local/share/ca-certificates/kind-registry.crt https://kind-registry:5000/v2/
```

### Problème : Image not found lors du pull Kubernetes

```bash
# Vérifier que l'image est bien dans le registry
curl -k https://localhost:5000/v2/rhdemo-api/tags/list

# Vérifier les événements Kubernetes
kubectl get events -n rhdemo-stagingkub --sort-by='.lastTimestamp'

# Vérifier les logs du pod
kubectl describe pod <pod-name> -n rhdemo-stagingkub

# Vérifier la configuration containerd dans KinD
docker exec rhdemo-control-plane cat /etc/containerd/config.toml | grep registry
```

## 📊 Performances

### Taille du registry

```bash
# Voir l'utilisation disque du registry
docker exec kind-registry du -sh /var/lib/registry

# Voir la taille du container
docker ps -s | grep kind-registry
```

### Cache des layers

Le registry stocke les layers Docker séparément. Si vous poussez plusieurs versions d'une même image, seuls les layers modifiés sont stockés.

**Exemple** :
- Image `1.0.0` : 500 MB
- Image `1.1.0` : 510 MB (si seulement 10 MB ont changé)
- Stockage total : ~510 MB (pas 1010 MB)

---

## 🔒 Sécurité

### État actuel (développement)

- ✅ Registry local uniquement (localhost:5000)
- ✅ Pas d'exposition externe
- ✅ HTTPS avec certificat autosigné
- ✅ Pas d'authentification

### Pour la production

Si vous déployez en production, utilisez :

1. **TLS** : Certificats SSL pour HTTPS
2. **Authentification** : htpasswd ou token-based auth
3. **Registry externe** : DockerHub, Harbor, AWS ECR, Google GCR, etc.
4. **Scan de sécurité** : Trivy, Clair, Anchore

---

## 📚 Ressources

- [Documentation officielle Docker Registry](https://docs.docker.com/registry/)
- [KinD - Local Registry](https://kind.sigs.k8s.io/docs/user/local-registry/)
- [Containerd - Registry Configuration](https://github.com/containerd/containerd/blob/main/docs/hosts.md)

---

## ✅ Checklist

- [ ] Registry kind-registry créé et démarré
- [ ] Registry accessible sur https://localhost:5000
- [ ] Registry connecté au réseau kind
- [ ] Cluster KinD configuré avec containerd patch
- [ ] Test : Push d'une image vers localhost:5000
- [ ] Test : Pull d'une image depuis Kubernetes
