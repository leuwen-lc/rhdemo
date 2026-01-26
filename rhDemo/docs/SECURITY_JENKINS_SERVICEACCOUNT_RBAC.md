# Configuration RBAC pour Jenkins - Stagingkub

Ce dossier contient la configuration RBAC (Role-Based Access Control) pour permettre à Jenkins de déployer sur le namespace `rhdemo-stagingkub` avec des permissions limitées.

## Architecture de sécurité

```text
┌─────────────────────────────────────────────────────────────────┐
│                     Machine Hôte                                │
│                                                                 │
│  ┌─────────────┐    ┌────────────────────────────────────────┐ │
│  │   Jenkins   │    │         Cluster KinD (rhdemo)          │ │
│  │  Container  │    │                                        │ │
│  │             │    │  ┌──────────────────────────────────┐  │ │
│  │ ✗ kind CLI  │───►│  │   Namespace: rhdemo-stagingkub   │  │ │
│  │ ✓ kubectl   │    │  │                                  │  │ │
│  │ ✓ helm      │    │  │  ServiceAccount: jenkins-deployer│  │ │
│  │             │    │  │  (permissions limitées)          │  │ │
│  │ kubeconfig  │    │  └──────────────────────────────────┘  │ │
│  │  (RBAC)     │    │                                        │ │
│  └─────────────┘    │  ┌──────────────────────────────────┐  │ │
│                     │  │   Namespace: kube-system         │  │ │
│                     │  │   ✗ Pas d'accès Jenkins          │  │ │
│                     │  └──────────────────────────────────┘  │ │
│                     └────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Philosophie de sécurité

Le principe de **moindre privilège** est appliqué :
- **kind n'est PAS installé** dans Jenkins pour empêcher la génération de kubeconfig admin
- Jenkins utilise un kubeconfig RBAC pré-provisionné comme credential
- Jenkins ne peut agir que sur le namespace `rhdemo-stagingkub` et les ressources strictement nécessaires
- Pas d'accès admin au cluster
- Pas d'accès aux autres namespaces (sauf `monitoring` pour les ServiceMonitors)

## Fichiers

| Fichier | Description |
|---------|-------------|
| `jenkins-serviceaccount.yaml` | ServiceAccount `jenkins-deployer` et son Secret token |
| `jenkins-role.yaml` | Role avec permissions namespace-scoped |
| `jenkins-rolebinding.yaml` | RoleBinding liant le ServiceAccount au Role |
| `jenkins-clusterrole.yaml` | ClusterRole pour ressources cluster-wide (PV, namespaces) |
| `jenkins-clusterrolebinding.yaml` | ClusterRoleBinding pour le ClusterRole |
| `jenkins-monitoring-role.yaml` | Role et RoleBinding pour le namespace `monitoring` |
| `setup-jenkins-rbac.sh` | Script d'installation automatique |

## Installation

### Option 1 : Script automatique (recommandé)

```bash
cd rhDemo/infra/stagingkub/rbac

# Installation des ressources RBAC
./setup-jenkins-rbac.sh

# Installation + génération du kubeconfig pour Jenkins
./setup-jenkins-rbac.sh --generate-kubeconfig
```

### Option 2 : Installation manuelle

```bash
# Créer le namespace si nécessaire
kubectl create namespace rhdemo-stagingkub
kubectl create namespace monitoring

# Appliquer les ressources RBAC
kubectl apply -f jenkins-serviceaccount.yaml
kubectl apply -f jenkins-role.yaml
kubectl apply -f jenkins-rolebinding.yaml
kubectl apply -f jenkins-clusterrole.yaml
kubectl apply -f jenkins-clusterrolebinding.yaml
kubectl apply -f jenkins-monitoring-role.yaml
```

## Permissions accordées

### Namespace `rhdemo-stagingkub`

| Ressource | Verbes | Justification |
|-----------|--------|---------------|
| pods | get, list, watch, delete | Vérification et nettoyage |
| pods/exec | create | Health checks via `kubectl exec` |
| pods/log | get, list | Debug et logs |
| services | CRUD | Helm déploie les Services |
| configmaps | CRUD | Helm déploie les ConfigMaps |
| secrets | CRUD | Secrets applicatifs (DB, Keycloak) |
| persistentvolumeclaims | CRUD | StatefulSets PostgreSQL |
| events | get, list, watch | Debug déploiements |
| endpoints | get, list, watch | Vérification services |
| deployments | CRUD | Helm déploie rhdemo-app, keycloak |
| deployments/scale | get, update, patch | Scaling si nécessaire |
| statefulsets | CRUD | Helm déploie PostgreSQL |
| statefulsets/scale | get, update, patch | Scaling si nécessaire |
| replicasets | get, list, watch | `kubectl rollout status` |
| cronjobs | CRUD | Backups PostgreSQL |
| jobs | get, list, watch, delete | Jobs créés par CronJobs |
| ingresses | CRUD | Helm déploie l'Ingress |
| networkpolicies | CRUD | Helm déploie les NetworkPolicies |

### Namespace `monitoring`

| Ressource | Verbes | Justification |
|-----------|--------|---------------|
| servicemonitors | CRUD | Prometheus scraping |
| podmonitors | CRUD | Prometheus scraping (futur) |

### Cluster-wide

| Ressource | Verbes | Justification |
|-----------|--------|---------------|
| persistentvolumes | CRUD | Helm crée les PV PostgreSQL |
| storageclasses | get, list, watch | Vérification classe stockage |
| namespaces | get, list, watch, create | Helm `--create-namespace` |
| nodes | get, list | `kubectl cluster-info` |

## Configuration Jenkins

### Prérequis

**IMPORTANT** : Le binaire `kind` n'est **PAS installé** dans l'image Jenkins pour des raisons de sécurité.
Cela empêche Jenkins de générer un kubeconfig admin et force l'utilisation du kubeconfig RBAC.

### Étape 1 : Initialiser le cluster (génère le kubeconfig RBAC)

Le script `init-stagingkub.sh` crée automatiquement les ressources RBAC et génère le kubeconfig :

```bash
cd rhDemo/infra/stagingkub/scripts
./init-stagingkub.sh
```

Le kubeconfig RBAC est généré dans :
`rhDemo/infra/stagingkub/jenkins-kubeconfig/kubeconfig-jenkins-rbac.yaml`

### Étape 2 : Configurer le credential Jenkins

1. Accédez à **Jenkins > Manage Jenkins > Credentials**
2. Sélectionnez le domaine approprié (ou Global)
3. Cliquez sur **Add Credentials**
4. Configurez :
   - **Kind** : Secret file
   - **File** : Uploadez `kubeconfig-jenkins-rbac.yaml`
   - **ID** : `kubeconfig-stagingkub`
   - **Description** : Kubeconfig RBAC pour stagingkub

### Étape 3 : Utilisation dans le pipeline

Le `Jenkinsfile-CD` utilise automatiquement ce credential :

```groovy
withCredentials([file(credentialsId: 'kubeconfig-stagingkub', variable: 'KUBECONFIG_FILE')]) {
    sh '''
        cp "$KUBECONFIG_FILE" $HOME/.kube/config
        kubectl get pods -n rhdemo-stagingkub
    '''
}
```

## Vérification des permissions

Après initialisation du cluster, vérifier les permissions :

```bash
# Tester l'accès aux pods
kubectl auth can-i get pods -n rhdemo-stagingkub \
    --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer

# Tester l'accès aux secrets
kubectl auth can-i create secrets -n rhdemo-stagingkub \
    --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer

# Tester l'accès aux PV (cluster-wide)
kubectl auth can-i create persistentvolumes \
    --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer

# Vérifier le NON-accès à kube-system (doit retourner "no")
kubectl auth can-i get pods -n kube-system \
    --as=system:serviceaccount:rhdemo-stagingkub:jenkins-deployer
```

## Régénérer le kubeconfig

Si le token expire ou si vous devez régénérer le kubeconfig :

```bash
# Option 1 : Réexécuter init-stagingkub.sh (régénère tout)
./scripts/init-stagingkub.sh

# Option 2 : Utiliser le script setup-jenkins-rbac.sh
cd rbac
./setup-jenkins-rbac.sh --generate-kubeconfig
# Le kubeconfig est généré dans : rbac/jenkins-kubeconfig.yaml
```

Après régénération, mettez à jour le credential Jenkins.

## Dépannage

### Le token n'est pas généré

```bash
# Vérifier le secret
kubectl get secret jenkins-deployer-token -n rhdemo-stagingkub -o yaml

# Le token devrait être présent dans .data.token
# Si absent, vérifier que le ServiceAccount existe
kubectl get sa jenkins-deployer -n rhdemo-stagingkub
```

### Permission refusée

```bash
# Vérifier les bindings
kubectl get rolebindings -n rhdemo-stagingkub
kubectl get clusterrolebindings | grep jenkins

# Vérifier le contenu du Role
kubectl describe role jenkins-deployer-role -n rhdemo-stagingkub
```

### Helm échoue

Si Helm échoue avec des erreurs de permission, vérifier que toutes les ressources Helm sont couvertes par le Role :

```bash
# Lister les types de ressources dans le chart Helm
helm template rhdemo rhDemo/infra/stagingkub/helm/rhdemo | \
    grep "^kind:" | sort -u
```

Comparer avec les ressources autorisées dans le Role.

## Sécurité

### Ce qui est autorisé
- Déployer l'application RHDemo
- Gérer les secrets applicatifs
- Créer les PersistentVolumes pour PostgreSQL
- Configurer le monitoring Prometheus

### Ce qui est interdit
- Accéder aux autres namespaces (kube-system, ingress-nginx, etc.)
- Modifier les RBAC (pas de création de Role/RoleBinding)
- Accéder aux secrets des autres applications
- Modifier la configuration du cluster
- Supprimer des nodes

## Migration depuis accès admin

Si vous migrez depuis une version antérieure où Jenkins avait un accès admin :

1. **Reconstruire l'image Jenkins** (sans `kind`) :

   ```bash
   cd rhDemo/infra/jenkins-docker
   docker-compose build jenkins
   docker-compose up -d jenkins
   ```

2. **Réinitialiser le cluster** (installe automatiquement RBAC) :

   ```bash
   cd rhDemo/infra/stagingkub/scripts
   ./init-stagingkub.sh
   ```

3. **Configurer le credential Jenkins** :
   - Uploadez `jenkins-kubeconfig/kubeconfig-jenkins-rbac.yaml` comme credential
   - ID : `kubeconfig-stagingkub`

4. **Valider un déploiement** :
   - Lancez le pipeline CD
   - Vérifiez que le message "pas d'accès aux namespaces système" apparaît
