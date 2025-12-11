# 🌍 Guide des environnements RHDemo

Ce document décrit les différents environnements disponibles pour le déploiement et les tests de l'application RHDemo.

---

## 📋 Environnements disponibles

| Environnement | Type | Description | Cas d'usage |
|---------------|------|-------------|-------------|
| **none** | - | Build + tests uniquement | CI rapide sans déploiement |
| **staging** | Docker Compose | Environnement de staging avec Docker Compose | Tests fonctionnels rapides, debugging |
| **stagingkub** | Kubernetes (KinD) | Environnement de staging Kubernetes local | Tests Kubernetes, validation pre-prod |
| **production** | Docker Compose | Production (à migrer vers Kubernetes) | Déploiement production |

---

## 🔧 Configuration Jenkins

### Paramètre DEPLOY_ENV

Dans le pipeline Jenkins, le paramètre `DEPLOY_ENV` contrôle l'environnement de déploiement :

```groovy
choice(name: 'DEPLOY_ENV',
       choices: ['staging', 'stagingkub', 'production', 'none'],
       description: 'Environnement de déploiement')
```

### Comportement selon l'environnement

| Stage | none | staging | stagingkub | production |
|-------|------|---------|------------|------------|
| Checkout | ✅ | ✅ | ✅ | ✅ |
| Lecture Version Maven | ❌ | ✅ | ✅ | ✅ |
| Compilation Backend | ✅ | ✅ | ✅ | ✅ |
| Build Frontend | ✅ | ✅ | ✅ | ✅ |
| Build Docker Image | ❌ | ✅ | ✅ | ✅ |
| Tag Image Docker | ❌ | ✅ | ❌ | ✅ |
| Load Image to KinD | ❌ | ❌ | ✅ | ❌ |
| Update K8s Secrets | ❌ | ❌ | ✅ | ❌ |
| Deploy to Kubernetes | ❌ | ❌ | ✅ | ❌ |
| Démarrage Docker Compose | ❌ | ✅ | ❌ | ✅ |
| Tests Unitaires | ✅ | ✅ | ✅ | ✅ |
| Tests Selenium | ❌ | ✅ | ⚠️ À impl. | ✅ |
| SonarQube | ✅ | ✅ | ✅ | ✅ |

---

## 🐳 Environnement: `staging` (Docker Compose)

### Caractéristiques

- **Technologie** : Docker Compose
- **Localisation** : `rhDemo/infra/staging/`
- **Fichier principal** : `docker-compose.yml`
- **Port HTTPS** : 443

### Architecture

```
┌─────────────────────────────────────────────┐
│ Host (port 443)                             │
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
DEPLOY_ENV=staging

# Ou manuellement
cd rhDemo/infra/staging
./init-staging.sh
docker-compose up -d
```

### URLs d'accès

- Application : https://rhdemo.staging.local
- Keycloak : https://keycloak.staging.local

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
│ Namespace: rhdemo-staging                        │
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

- Application : https://rhdemo.staging.local
- Keycloak : https://keycloak.staging.local

### Avantages

✅ Teste les déploiements Kubernetes
✅ Validation des Helm Charts
✅ Readiness/Liveness probes
✅ Rolling updates
✅ Scaling horizontal facile
✅ Production-ready (si prod = K8s)
✅ GitOps compatible

### Inconvénients

❌ Démarrage plus long (3-5 minutes)
❌ Courbe d'apprentissage Kubernetes
❌ Plus de ressources requises (8GB RAM min)
❌ Debugging plus complexe

---

## 🔄 Migration staging → stagingkub

### Quand migrer ?

Migrez vers stagingkub si :
- La production utilise Kubernetes
- Vous voulez tester les Helm charts
- Vous avez besoin de rolling updates
- Vous voulez valider les probes K8s

### Guide de migration

1. **Initialiser stagingkub**
   ```bash
   cd rhDemo/infra/stagingkub
   ./scripts/init-stagingkub.sh
   ```

2. **Tester le déploiement**
   ```bash
   ./scripts/deploy.sh 1.1.0-SNAPSHOT
   ```

3. **Valider les tests**
   - Accès application : ✅
   - Accès Keycloak : ✅
   - Login utilisateur : ✅
   - API fonctionnelle : ✅

4. **Basculer Jenkins vers stagingkub**
   - Modifier `DEPLOY_ENV` par défaut si souhaité
   - Ou laisser le choix à l'utilisateur

---

## 🆚 Comparaison détaillée

### Performance

| Aspect | staging | stagingkub |
|--------|---------|------------|
| Temps démarrage | ~2 min | ~4 min |
| Temps déploiement | ~30s | ~2 min |
| RAM utilisée | ~4GB | ~6GB |
| CPU utilisé | Faible | Moyen |

### Gestion des secrets

| Aspect | staging | stagingkub |
|--------|---------|------------|
| Méthode | Variables env + docker cp | Kubernetes Secrets |
| Chiffrement | SOPS | SOPS → K8s Secrets |
| Rotation | Redémarrage conteneurs | Rolling update |

### Réseau

| Aspect | staging | stagingkub |
|--------|---------|------------|
| Type | Docker network bridge | K8s Services + Ingress |
| DNS interne | Noms de services | K8s DNS |
| Exposition | Port mapping direct | Ingress Controller |

### Volumes

| Aspect | staging | stagingkub |
|--------|---------|------------|
| Type | Docker volumes | PersistentVolumeClaims |
| Persistance | Locale | Locale (hostPath) |
| Backup | docker cp | kubectl cp ou Velero |

---

## 📚 Documentation

- [Documentation staging](./staging/README.md)
- [Documentation stagingkub](./stagingkub/README.md)

---

## ❓ FAQ

### Puis-je utiliser les deux environnements en même temps ?

Oui, mais ils écoutent tous les deux sur le port 443. Vous devrez :
- Utiliser des domaines différents dans `/etc/hosts`
- OU arrêter un environnement avant de démarrer l'autre

### Lequel utiliser pour le développement local ?

**staging** (Docker Compose) est recommandé pour :
- Développement quotidien
- Tests rapides
- Debugging

**stagingkub** est recommandé pour :
- Valider les manifests K8s avant merge
- Tester les rolling updates
- Reproduire un comportement production

### Comment choisir entre staging et stagingkub dans Jenkins ?

Lors du lancement du build, sélectionnez le paramètre `DEPLOY_ENV` :
- `staging` : Déploiement Docker Compose classique
- `stagingkub` : Déploiement Kubernetes (KinD)
- `none` : Build + tests uniquement (pas de déploiement)

### Les secrets sont-ils les mêmes ?

Oui, les deux environnements utilisent les mêmes secrets sources (SOPS), mais :
- **staging** : Injectés via variables d'environnement et `docker cp`
- **stagingkub** : Stockés dans Kubernetes Secrets

---

## 🔗 Liens utiles

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [KinD Documentation](https://kind.sigs.k8s.io/)
- [Helm Documentation](https://helm.sh/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
