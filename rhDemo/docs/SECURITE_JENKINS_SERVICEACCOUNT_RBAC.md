---
statut: actif
verifie_le: 2026-11-23
sources:
  - rhDemo/infra/stagingkub/rbac/
  - rhDemo/infra/stagingkub/scripts/init-stagingkub.sh
  - rhDemo/scripts/rotation_lib/k8s.py
  - rhDemo/secrets/inventory.yaml
---

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

Ce document porte sur `jenkins-deployer`, utilisé par `RHDemo-CD`. Les montées des composants système (Cilium, NGF, observabilité) passent par un second compte, `jenkins-infra-upgrader` (credential `kubeconfig-stagingkub-infra-upgrader`), aux droits plus larges (Roles par namespace système et ClusterRole qui reprend les règles des charts installés, exigé par la protection RBAC contre l'escalade) : leur liste et leur justification sont dans [rbac/README.md](../infra/stagingkub/rbac/README.md).

## Fichiers

| Fichier | Description |
|---------|-------------|
| `jenkins-serviceaccount.yaml` | ServiceAccount `jenkins-deployer` (sans Secret de token : voir « Token et kubeconfig ») |
| `jenkins-role.yaml` | Role avec permissions namespace-scoped |
| `jenkins-rolebinding.yaml` | RoleBinding liant le ServiceAccount au Role |
| `jenkins-clusterrole.yaml` | ClusterRole pour ressources cluster-wide (PV, namespaces) |
| `jenkins-clusterrolebinding.yaml` | ClusterRoleBinding pour le ClusterRole |
| `jenkins-monitoring-role.yaml` | Role et RoleBinding pour le namespace `monitoring` |

## Installation

`init-stagingkub.sh` applique les manifestes de `rbac/` (les deux ServiceAccounts, leurs Roles et ClusterRoles), contrôle quelques droits par impersonation, puis délègue le token et le kubeconfig à `rotate-secrets.py --if-missing` (section suivante). Application manuelle des seuls manifestes de `jenkins-deployer` :

```bash
kubectl create namespace rhdemo-stagingkub
kubectl create namespace monitoring
kubectl apply -f jenkins-serviceaccount.yaml -f jenkins-role.yaml -f jenkins-rolebinding.yaml \
  -f jenkins-clusterrole.yaml -f jenkins-clusterrolebinding.yaml -f jenkins-monitoring-role.yaml
```

## Token et kubeconfig

Le token de chaque ServiceAccount est porté par un Secret `kubernetes.io/service-account-token` **daté** (`jenkins-deployer-token-<AAAAMMJJ-HHMMSS>`), créé par `rhDemo/scripts/rotate-secrets.py` (méthode `k8s-sa-token`, entrées `kubeconfig-stagingkub` et `kubeconfig-stagingkub-infra-upgrader` de `secrets/inventory.yaml`). Le script :

1. crée le nouveau Secret ; le contrôleur de tokens y dépose un token, l'ancien reste valide ;
2. vérifie le nouveau token depuis le poste : identité (`kubectl auth whoami`) et droits attendus (`allowed` et `denied` de l'inventaire, par `kubectl auth can-i`) ;
3. construit le kubeconfig en mémoire (serveur `https://rhdemo-control-plane:6443`, vu des agents Jenkins) et le pousse dans le credential Jenkins « Secret file », qu'il crée s'il n'existe pas ;
4. supprime les anciens Secrets de token du même compte, ce qui invalide leurs tokens.

Un échec en 2 ou 3 supprime le nouveau Secret : rien n'a changé. Aucun kubeconfig n'est écrit sur le disque (le fichier de vérification vit en mémoire, dans `/dev/shm`, le temps des contrôles).

Le manifeste du ServiceAccount ne déclare plus de Secret au nom fixe : chaque `kubectl apply` en recréerait un, donc un token valide que personne ne suit. `init-stagingkub.sh` appelle `rotate-secrets.py --if-missing`, qui ne fait rien si un token existe déjà (cluster réutilisé) et sinon crée le premier (mot de passe admin de Jenkins demandé). Jenkins arrêté : l'étape échoue avant toute création, le script le signale et la commande est à relancer plus tard.

Renouvellement (période de 180 jours, ou en urgence) : `rotate-secrets.py kubeconfig-stagingkub kubeconfig-stagingkub-infra-upgrader` ([ROTATION_SECRETS.md](ROTATION_SECRETS.md)).

## Permissions accordées

### Namespace `rhdemo-stagingkub`

| Ressource | Verbes | Justification |
|-----------|--------|---------------|
| pods | get, list, watch, delete | Vérification et nettoyage |
| pods/exec | create | Health checks via `kubectl exec` |
| pods/log | get, list | Debug et logs |
| services | CRUD | Helm déploie les Services |
| configmaps | CRUD | Helm déploie les ConfigMaps |
| secrets | CRUD | Secrets gérés par la release Helm ; les Secrets applicatifs (DB, Keycloak, `rhdemo-app-secrets`) sont écrits par ESO depuis OpenBao, plus par Jenkins |
| externalsecrets, secretstores (`external-secrets.io`) | get, list, watch | Contrôle de la synchronisation ESO par `Jenkinsfile-CD` (aucune valeur de secret lue) |
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
| gateways, httproutes, referencegrants (`gateway.networking.k8s.io`, avec `/status`) | CRUD | Helm déploie le routage Gateway API |
| clientsettingspolicies, proxysettingspolicies, observabilitypolicies, ratelimitpolicies (`gateway.nginx.org`, avec `/status`) | CRUD | Politiques NGINX Gateway Fabric du chart |
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

Jenkins démarré, avant le premier passage d'`init-stagingkub.sh` : le credential `kubeconfig-stagingkub` est alors créé directement (section « Token et kubeconfig »). Sinon, relancer `rhDemo/scripts/rotate-secrets.py --if-missing kubeconfig-stagingkub kubeconfig-stagingkub-infra-upgrader` une fois Jenkins disponible.

### Utilisation dans le pipeline

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

`rhDemo/scripts/rotate-secrets.py kubeconfig-stagingkub` (section « Token et kubeconfig »). Les tokens n'expirent pas : la rotation est périodique (180 jours) ou d'urgence.

## Dépannage

### Le token n'est pas généré

```bash
# Secrets de token du compte (aucun : relancer rotate-secrets.py --if-missing)
kubectl get secrets -n rhdemo-stagingkub --field-selector type=kubernetes.io/service-account-token
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
- Gérer les Secrets de la release Helm, lire l'état des ExternalSecret
- Créer les PersistentVolumes pour PostgreSQL
- Configurer le monitoring Prometheus

### Ce qui est interdit
- Accéder aux autres namespaces (kube-system, nginx-gateway, external-secrets, etc.)
- Modifier les RBAC (pas de création de Role/RoleBinding)
- Accéder aux secrets des autres applications
- Modifier la configuration du cluster
- Supprimer des nodes

### Limite connue : création de tokens par Secret (constat du 2026-11-23)

Le droit `create secrets` permet de créer un Secret `service-account-token` pour **n'importe quel ServiceAccount du même namespace**, et donc d'obtenir son token. Constaté par `kubectl auth can-i`, sans exploitation :

- `jenkins-deployer` peut créer des Secrets dans `rhdemo-stagingkub`, où vit aussi `jenkins-infra-upgrader` : il peut obtenir les droits de ce dernier ;
- `jenkins-infra-upgrader` détient `secrets` sur tout le cluster (règles miroir des charts, voir [rbac/README.md](../infra/stagingkub/rbac/README.md)) : il peut créer un token pour un compte de `kube-system` aux droits étendus (par exemple `clusterrole-aggregation-controller`, qui a `escalate` sur les ClusterRoles).

Un pipeline compromis pourrait donc remonter jusqu'à l'administration du cluster, contrairement au principe « pas d'accès admin au cluster ». Pistes de correction, non appliquées : une ValidatingAdmissionPolicy qui refuse la création de Secrets `service-account-token` à tout autre que l'administrateur du cluster, et `jenkins-infra-upgrader` dans un namespace où `jenkins-deployer` n'a aucun droit.

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

3. **Credential Jenkins** : créé par `init-stagingkub.sh` si Jenkins tourne, sinon `rhDemo/scripts/rotate-secrets.py --if-missing kubeconfig-stagingkub`.

4. **Valider un déploiement** :
   - Lancez le pipeline CD
   - Vérifiez que le message "pas d'accès aux namespaces système" apparaît
