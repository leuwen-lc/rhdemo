# 🌍 Guide des environnements RHDemo

Ce document décrit les différents environnements disponibles pour le déploiement et les tests de l'application RHDemo.

---

## 📋 Environnements disponibles

| Environnement | Type | Description | Cas d'usage |
|---------------|------|-------------|-------------|
| **none** | - | Build + tests uniquement | CI rapide sans déploiement |
| **ephemere** | Docker Compose | Environnement ephemere avec Docker Compose | Tests fonctionnels rapides, debugging |
| **stagingkub** | Kubernetes (KinD) | Environnement de staging Kubernetes local | Tests Kubernetes, validation pre-prod |
---

## 🔧 Configuration Jenkins

Deux pipelines sont disponibles :
Jenkinsfile-CI qui réalise 
- toutes les étapes de build, 
- tests unitaires et d'intégration, 
- les controles qualité et sécurité 
- déploie sur l'environnement ephemere
- lance les tests Selenium avec ZAP
- pousse le container applicatif dans le registry local
Jenkinsfile-CD qui 
- récupère le container applicatif
- déploie sur l'environnement stagingkub (namespace d'un cluster Kind)

## 🐳 Environnement: `ephemere` (Docker Compose)

### Caractéristiques

- **Technologie** : Docker Compose
- **Localisation** : `rhDemo/infra/ephemere/`
- **Fichier principal** : `docker-compose.yml`
- **Port HTTPS** : 58443

### Architecture

```
┌─────────────────────────────────────────────┐
│ Host (port 58443)                           │
│  ↓                                          │
│ Nginx (reverse proxy HTTPS)                 │
│  ├─→ rhdemo-app:9000                        │
│  │    └─→ rhdemo-db:5432 (PostgreSQL)      │
│  └─→ keycloak:8080                          │
│       └─→ keycloak-db:5432 (PostgreSQL)    │
└─────────────────────────────────────────────┘
```

### Services déployés

1. **rhdemo-db** : PostgreSQL 16 pour l'application
2. **keycloak-db** : PostgreSQL 16 pour Keycloak
3. **keycloak** : Serveur d'authentification
4. **rhdemo-app** : Application Spring Boot (image Paketo)
5. **nginx** : Reverse proxy HTTPS

### Démarrage rapide

```bash
# Via Jenkins
DEPLOY_ENV=ephemere

# Ou manuellement
cd rhDemo/infra/ephemere
./init-ephemere.sh
docker-compose up -d
```

### URLs d'accès (choisir l'option "KEEP_EPHEMERE_ENV dans Jenkins)

- Application : https://rhdemo.ephemere.local:58443
- Keycloak : https://keycloak.ephemere.local:58443

### Avantages

✅ Démarrage rapide (< 2 minutes)
✅ Debugging facile avec `docker logs`
✅ Familiarité avec Docker Compose
✅ Moins de ressources requises
✅ Fichier de configuration simple

### Inconvénients

❌ Ne teste pas Kubernetes
❌ Scaling horizontal limité
❌ Pas de Helm/manifests Kubernetes
❌ Moins représentatif de la production (si prod = K8s)

---

## ☸️ Environnement: `stagingkub` (Kubernetes/KinD)

### Caractéristiques

- **Technologie** : Kubernetes in Docker (KinD)
- **Localisation** : `rhDemo/infra/stagingkub/`
- **Package** : Helm Chart
- **Port HTTPS** : 443 (via NodePort 30443)

### Architecture

```
┌──────────────────────────────────────────────────┐
│ Cluster KinD "rhdemo"                            │
│                                                  │
│ ┌──────────────────────────────────────────┐   │
│ │ Ingress Controller (Nginx)                │   │
│ │  ├─→ rhdemo-app (Service ClusterIP:9000) │   │
│ │  └─→ keycloak (Service ClusterIP:8080)   │   │
│ └──────────────────────────────────────────┘   │
│                                                  │
│ Namespace: rhdemo-stagingkub                     │
│  ├─ Deployment: rhdemo-app                       │
│  ├─ Deployment: keycloak                         │
│  ├─ StatefulSet: postgresql-rhdemo               │
│  └─ StatefulSet: postgresql-keycloak             │
└──────────────────────────────────────────────────┘
```

### Ressources Kubernetes

- 1 Namespace
- 2 StatefulSets (PostgreSQL)
- 2 Deployments (app + keycloak)
- 5 Services
- 1 Ingress
- 4 Secrets
- 2 PVC
- 1 ConfigMap

### Démarrage rapide

```bash
# 1. Initialisation (une seule fois)
cd rhDemo/infra/stagingkub
./scripts/init-stagingkub.sh

# 2. Déploiement via Jenkins
DEPLOY_ENV=stagingkub

# Ou manuellement
./scripts/deploy.sh 1.1.0-SNAPSHOT
```

### URLs d'accès

- Application : https://rhdemo-stagingkub.intra.leuwen-lc.fr
- Keycloak : https://keycloak-stagingkub.intra.leuwen-lc.fr

### Avantages

✅ Démontre le déploiement Kubernetes
✅ Validation des Helm Charts
✅ Readiness/Liveness probes
✅ Rolling updates
✅ Scaling horizontal plus facile 
✅ Production-ready (si prod = K8s)
✅ GitOps compatible

### Inconvénients

❌ Démarrage plus long (3-5 minutes)
❌ Courbe d'apprentissage Kubernetes
❌ Plus de ressources requises (8GB RAM min)
❌ Debugging plus complexe

---


## 🆚 Comparaison détaillée

### Performance

| Aspect | ephemere | stagingkub |
|--------|----------|------------|
| Temps démarrage | ~2 min | ~4 min |
| Temps déploiement | ~30s | ~2 min |
| RAM utilisée | ~4GB | ~6GB |
| CPU utilisé | Faible | Moyen |

### Gestion des secrets

| Aspect | ephemere | stagingkub |
|--------|----------|------------|
| Source | Valeurs aléatoires générées à chaque build (jamais stockées) | OpenBao, recopiés par External Secrets Operator |
| Injection | Variables env + docker cp | Kubernetes Secrets |
| Rotation | Nouveau build | `rotate-secrets.py` (KV, synchronisation ESO, redémarrage) |

### Réseau

| Aspect | ephemere | stagingkub |
|--------|----------|------------|
| Type | Docker network bridge | K8s Services + Ingress |
| DNS interne | Noms de services | K8s DNS |
| Exposition | Port mapping direct | Ingress Controller |

### Volumes

| Aspect | ephemere | stagingkub |
|--------|----------|------------|
| Type | Docker volumes | PersistentVolumeClaims |
| Persistance | Locale | Locale (hostPath) |
| Backup | docker cp | kubectl cp ou Velero |

---

## 📚 Documentation

- [Documentation ephemere](./ephemere/README.md)
- [Documentation stagingkub](./stagingkub/README.md)

---

## ❓ FAQ

### Puis-je utiliser les deux environnements en même temps ?

Oui, ephemere utilise le port 58443 et stagingkub utilise le port 443.

### Lequel utiliser pour le développement local ?

**ephemere** (Docker Compose) est recommandé pour :
- Développement quotidien
- Tests rapides
- Debugging

**stagingkub** est recommandé pour :
- Valider les manifests K8s avant merge
- Tester les rolling updates
- Reproduire un comportement production

### Les secrets sont-ils les mêmes ?

Non, aucune valeur n'est partagée :
- **ephemere** : tirés au hasard à chaque build par `Jenkinsfile-CI`, injectés via variables d'environnement et `docker cp`
- **stagingkub** : stockés dans OpenBao, recopiés en Kubernetes Secrets par ESO ([OPENBAO.md](../docs/OPENBAO.md))

---

## 🔗 Liens utiles

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [KinD Documentation](https://kind.sigs.k8s.io/)
- [Helm Documentation](https://helm.sh/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
