# RBAC Jenkins — stagingkub

Ce répertoire contient les manifestes RBAC appliqués sur le cluster KinD `rhdemo`
pour donner à Jenkins des accès **nommés et strictement scopés**, jamais
cluster-admin. Deux ServiceAccounts distincts, pour deux responsabilités
distinctes :

| ServiceAccount | Utilisé par | Portée |
|---|---|---|
| `jenkins-deployer` | `Jenkinsfile-CD` (déploiement applicatif) | Namespace `rhdemo-stagingkub` + lecture/écriture ServiceMonitors dans `monitoring` + PersistentVolumes (cluster-scoped) |
| `jenkins-infra-upgrader` | `Jenkinsfile-Renovate` (validation dry-run) + `Jenkinsfile-Stagingkub-Upgrade-Deploy` (application réelle) | `nginx-gateway`, `loki-stack`, `monitoring` (étendu), `kube-system` (restreint à Cilium), + CRDs/ClusterRoles cluster-scoped nommés |

Les deux credentials Jenkins correspondants (`kubeconfig-stagingkub` et
`kubeconfig-stagingkub-infra-upgrader`) sont générés par
`scripts/init-stagingkub.sh` et **ne se substituent jamais l'un à l'autre** :
`Jenkinsfile-CD` n'a et n'aura jamais les droits élargis de
`jenkins-infra-upgrader`, et réciproquement `jenkins-infra-upgrader` n'a aucun
droit dans `rhdemo-stagingkub` (aucun des composants qu'il gère n'y vit).

Aucun des deux ServiceAccounts n'a le CLI `kind` ni un accès à `docker.sock` —
la reconstruction complète du cluster (`kind delete`/`kind create`) reste
exclusivement une opération de la machine hôte, jamais de Jenkins. Voir
`Dockerfile.agent` (image des agents Jenkins) et
`docs/STAGINGKUB_REBUILD_PIPELINE.md` pour le détail de cette séparation.

## jenkins-deployer

Fichiers : `jenkins-serviceaccount.yaml`, `jenkins-role.yaml`,
`jenkins-rolebinding.yaml`, `jenkins-clusterrole.yaml`,
`jenkins-clusterrolebinding.yaml`, `jenkins-monitoring-role.yaml`.

Permissions accordées :
- Namespace `rhdemo-stagingkub` : pods, deployments, statefulsets, services,
  secrets, configmaps, ingresses/Gateway API, etc. (déploiement Helm de
  l'application rhDemo + Keycloak + PostgreSQL).
- Namespace `monitoring` : ServiceMonitors/PodMonitors uniquement (CRUD).
- Cluster-wide : PersistentVolumes, namespaces (get/list/watch/create/patch),
  StorageClasses (lecture), GatewayClasses (lecture).
- Pas d'accès à `kube-system`, `nginx-gateway` ni `loki-stack`.

## jenkins-infra-upgrader (Option 3 — mise à jour en place)

Fichiers : `jenkins-infra-upgrader-serviceaccount.yaml`,
`jenkins-infra-upgrader-nginx-gateway-role.yaml`,
`jenkins-infra-upgrader-loki-stack-role.yaml`,
`jenkins-infra-upgrader-monitoring-role.yaml`,
`jenkins-infra-upgrader-kube-system-role.yaml`,
`jenkins-infra-upgrader-clusterrole.yaml`.

Ce ServiceAccount existe pour une raison précise : absorber les mises à jour
Renovate des composants d'infrastructure (Cilium, NGINX Gateway Fabric,
kube-prometheus-stack, Loki, Promtail, Grafana) **sans jamais reconstruire le
cluster**, en respectant malgré tout le principe de moindre privilège. C'est
une extension RBAC réelle et documentée, pas une exception silencieuse — voir
l'étude complète dans
[`docs/STAGINGKUB_REBUILD_PIPELINE.md`](../../../docs/STAGINGKUB_REBUILD_PIPELINE.md)
(étape 3).

### Principes appliqués

- **`resourceNames` partout où c'est possible** : jamais un accès générique à
  un namespace ou à un type de ressource cluster-scoped, toujours restreint à
  la liste exacte des objets déjà connus (vérifiés par `helm template`/`helm
  show crds` sur les charts réels du projet, pas devinés).
- **Jamais de `create` sur les CustomResourceDefinition ni sur les
  ClusterRole/ClusterRoleBinding** — empêche l'installation de CRDs
  arbitraires ou la création de bindings vers des rôles non prévus.
- **`jenkins-infra-upgrader-cluster-role`/`-cluster-rolebinding` n'apparaissent
  dans aucune liste `resourceNames`** — ce ServiceAccount ne peut jamais
  modifier ses propres droits.
- **Toute nouvelle ressource nommée** (nouveau type de CRD, nouveau
  ClusterRole) introduite par une future version d'un composant doit être
  ajoutée ici explicitement et revue — jamais un accès élargi par défaut.
  L'échec est le comportement attendu tant que cet ajout n'a pas été fait.

### Cas particulier Cilium (`kube-system`)

Cilium bootstrappe lui-même ses CRDs (`cilium.io`) au démarrage de
l'agent/operator, via son propre ServiceAccount — vérifié en inspectant le
chart 1.18.6 (`helm template --include-crds` : aucune CRD rendue ; aucun
dossier `crds/` dans le chart). `jenkins-infra-upgrader` n'a donc **aucun
droit CRD** sur `cilium.io`, uniquement des droits nommés sur les objets que
la release Helm gère directement : `daemonset/cilium`,
`deployment/cilium-operator`, `configmap/cilium-config`, et les
ClusterRole/ClusterRoleBinding `cilium`/`cilium-operator` (portés par
`jenkins-infra-upgrader-clusterrole.yaml`).

Le garde-fou réel sur ces deux derniers objets : Kubernetes empêche
nativement l'auto-élévation de privilèges via RBAC (verbe spécial
`escalate`) — `jenkins-infra-upgrader` ne pourra jamais réécrire les règles
du ClusterRole `cilium` pour lui accorder des droits qu'il ne détient pas
déjà lui-même. Si une future version de Cilium a besoin d'étendre son propre
ClusterRole, l'upgrade échoue proprement (rollback `--atomic`) plutôt que de
réussir silencieusement avec des droits élargis.

**Compromis assumé et documenté — lecture des pods/logs `kube-system`** : la
règle `pods`/`pods/log` de `jenkins-infra-upgrader-kube-system-role.yaml` est
la seule de tout ce Role sans `resourceNames` (contrairement au principe
énoncé plus haut). Les pods du DaemonSet Cilium portent un nom généré
(suffixe aléatoire, change à chaque rollout) — un `resourceNames` figé
casserait la lecture de logs dès le premier redémarrage. Conséquence acceptée
et vérifiée (`kubectl auth can-i get pods -n kube-system --as=...` → `yes`) :
`jenkins-infra-upgrader` peut lire (jamais écrire) les pods et logs de
**tout** `kube-system` (kube-apiserver, etcd, coredns, kube-proxy...), pas
seulement ceux de Cilium. Risque limité à une fuite de confidentialité en
lecture seule, sans élévation de privilège ni action d'écriture possible.

### CRDs cluster-scoped couvertes (`customresourcedefinitions`)

Liste vérifiée par `helm show crds` / `kubectl kustomize` sur les charts
réels (voir `jenkins-infra-upgrader-clusterrole.yaml` pour le détail complet) :

- **Gateway API (channel standard, 8 CRDs)** : `backendtlspolicies`,
  `gatewayclasses`, `gateways`, `grpcroutes`, `httproutes`, `listenersets`,
  `referencegrants`, `tlsroutes` (`.gateway.networking.k8s.io`).
- **NGINX Gateway Fabric (11 CRDs embarquées dans le chart)** :
  `authenticationfilters`, `clientsettingspolicies`, `nginxgateways`,
  `nginxproxies`, `observabilitypolicies`, `proxysettingspolicies`,
  `ratelimitpolicies`, `snippetsfilters`, `snippetspolicies`,
  `upstreamsettingspolicies`, `wafpolicies` (`.gateway.nginx.org`).
- **kube-prometheus-stack (10 CRDs)** : `alertmanagerconfigs`,
  `alertmanagers`, `podmonitors`, `probes`, `prometheusagents`,
  `prometheuses`, `prometheusrules`, `scrapeconfigs`, `servicemonitors`,
  `thanosrulers` (`.monitoring.coreos.com`).

### Admission webhooks Prometheus Operator : désactivés

`prometheusOperator.admissionWebhooks.enabled: false` dans
`helm/observability/prometheus-values.yaml` — décision actée pour supprimer
à la racine le risque d'un `ValidatingWebhookConfiguration`/
`MutatingWebhookConfiguration` cluster-scoped mal configuré (capable
d'intercepter/rejeter des requêtes API pour tout le cluster). Vérifié par
`helm template` : aucun objet `*WebhookConfiguration` n'est rendu une fois
cette option désactivée. Aucun droit `admissionregistration.k8s.io` n'est
donc nécessaire pour `jenkins-infra-upgrader`.

### Ce qui reste hors du périmètre de jenkins-infra-upgrader

- **`kindest/node`** (version de Kubernetes) : `kind` ne supporte pas le
  remplacement de version de nœud en place. Reste exclusivement traité par
  `init-stagingkub.sh` (reconstruction complète), exécuté depuis l'hôte.
- **Toute dérive d'état** (résidus, secrets corrompus, cluster incohérent) :
  reste couverte par `clean-cluster.sh` + `init-stagingkub.sh` +
  `install-observability.sh`, exécutés depuis l'hôte.

## Régénération

`scripts/init-stagingkub.sh` applique automatiquement l'ensemble des
manifestes de ce répertoire (via `kubectl apply -f`, pas `kubectl apply -k` —
le fichier `kustomization.yaml` local existe pour un usage manuel ponctuel :
`kubectl apply -k rhDemo/infra/stagingkub/rbac/`) et génère les deux
kubeconfigs dans `jenkins-kubeconfig/` :

- `kubeconfig-jenkins-rbac.yaml` → credential Jenkins `kubeconfig-stagingkub`
- `kubeconfig-jenkins-infra-upgrader-rbac.yaml` → credential Jenkins
  `kubeconfig-stagingkub-infra-upgrader`

Ces deux fichiers contiennent des tokens et ne sont jamais commités (voir
`jenkins-kubeconfig/.gitignore`).
