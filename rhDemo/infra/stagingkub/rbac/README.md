# RBAC Jenkins — stagingkub

Ce répertoire contient les manifestes RBAC appliqués sur le cluster KinD `rhdemo`
pour donner à Jenkins des accès **nommés et strictement scopés**, jamais
cluster-admin. Deux ServiceAccounts distincts, pour deux responsabilités
distinctes :

| ServiceAccount | Utilisé par | Portée |
|---|---|---|
| `jenkins-deployer` | `Jenkinsfile-CD` (déploiement applicatif) | Namespace `rhdemo-stagingkub` + lecture/écriture ServiceMonitors dans `monitoring` + PersistentVolumes (cluster-scoped) |
| `jenkins-infra-upgrader` | `Jenkinsfile-Renovate` (validation dry-run) + `Jenkinsfile-Stagingkub-Upgrade-Deploy` (application réelle) | `nginx-gateway`, `loki-stack`, `monitoring` (étendu), `cilium-system` (namespace dédié Cilium, RBAC large), `kube-system` (un seul objet nommé, Prometheus/CoreDNS), + CRDs/ClusterRoles cluster-scoped nommés |

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
`jenkins-infra-upgrader-cilium-system-role.yaml`,
`jenkins-infra-upgrader-cilium-secrets-role.yaml`,
`jenkins-infra-upgrader-clusterrole.yaml`.

Ce ServiceAccount existe pour une raison précise : absorber les mises à jour
Renovate des composants d'infrastructure (Cilium, NGINX Gateway Fabric,
kube-prometheus-stack, Loki, Alloy, Grafana) **sans jamais reconstruire le
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

### Cas particulier Cilium (`cilium-system`)

**Historique** : Cilium vivait initialement dans `kube-system` (choix par
défaut de la doc Cilium), avec un RBAC restreint par `resourceNames` comme
NGF/kube-prometheus-stack. En pratique, chaque nouvelle version de Cilium
introduisait régulièrement un objet nommé inédit (`cilium-envoy`,
`cilium-config-agent`, `cilium-operator-ztunnel`, `cilium-pre-flight`...),
provoquant un échec de pipeline à chaque fois tant que le nom n'avait pas été
ajouté manuellement au RBAC — bien plus fréquent que pour les autres
composants. Vérifié avant bascule (`helm template` sur le chart 1.19.6,
comparaison namespace custom vs `kube-system`, inspection des variables
d'environnement `CILIUM_K8S_NAMESPACE`) : le chart Cilium ne câble aucun
namespace en dur, l'agent/operator lisent leur propre namespace via la
downward API, et le chart supporte officiellement une installation hors
`kube-system` (garde-fou GKE qui recommande explicitement cette option dans
certains cas). Cilium a donc été basculé vers un namespace dédié et
mono-usage, `cilium-system`, au même titre que `nginx-gateway`/`loki-stack` —
voir `install-or-upgrade-cilium.sh` pour le détail de la bascule.

Cilium bootstrappe lui-même ses CRDs (`cilium.io`) au démarrage de
l'agent/operator, via son propre ServiceAccount — vérifié en inspectant le
chart 1.18.6 (`helm template --include-crds` : aucune CRD rendue ; aucun
dossier `crds/` dans le chart). `jenkins-infra-upgrader` n'a donc **aucun
droit CRD** sur `cilium.io`.

**`jenkins-infra-upgrader-cilium-system-role.yaml`** : RBAC large sans
`resourceNames` sur `daemonsets`/`deployments`/`configmaps`/`secrets`/
`serviceaccounts`/`services` (create/update/patch/delete), même logique que
`nginx-gateway`/`loki-stack` — namespace mono-usage, aucun risque d'exposer
un objet système sans rapport. Ceci couvre à la fois les ressources réelles
de la release `cilium` et le stockage Helm de ses secrets de suivi
(`sh.helm.release.v1.*`, nom non fixe), qui vivent désormais dans le même
namespace : plus besoin du namespace séparé `cilium-release` de l'ancien
modèle. Cela couvre aussi, sans ajout RBAC, la release `cilium-preflight`
(job de compatibilité CRD exécuté à chaque montée de version mineure) —
c'est elle qui avait déclenché l'échec initial motivant cette bascule.

**Ce qui reste nommé et restreint malgré la bascule — ClusterRole/
ClusterRoleBinding cluster-scoped (`cilium`, `cilium-operator`,
`cilium-pre-flight`)** : portés par `jenkins-infra-upgrader-clusterrole.yaml`,
`get`/`update`/`patch` uniquement, jamais `create`. Ces objets ne sont pas
namespacés — le namespace dédié de Cilium ne change rien à leur niveau de
risque, la restriction reste nécessaire. Le garde-fou réel : Kubernetes
empêche nativement l'auto-élévation de privilèges via RBAC (verbe spécial
`escalate`) — `jenkins-infra-upgrader` ne pourra jamais réécrire les règles
du ClusterRole `cilium` pour lui accorder des droits qu'il ne détient pas
déjà lui-même. Si une future version de Cilium a besoin d'étendre son propre
ClusterRole, l'upgrade échoue proprement (rollback `--atomic`) plutôt que de
réussir silencieusement avec des droits élargis. Conséquence pour
`cilium-pre-flight` : sa première création (par version majeure/mineure
introduisant ce garde-fou) reste une opération admin ponctuelle, comme pour
`cilium`/`cilium-operator` — voir `install-or-upgrade-cilium.sh` (la release
`cilium-preflight` n'est volontairement jamais supprimée par
`jenkins-infra-upgrader`, uniquement mise à jour en place, pour ne jamais
avoir besoin de la recréer).

**`jenkins-infra-upgrader-kube-system-role.yaml` — désormais quasi vide.**
Depuis la bascule, le seul objet encore géré par `jenkins-infra-upgrader`
dans `kube-system` est sans rapport avec Cilium : le Service headless
`prometheus-kube-prometheus-coredns`, créé par la release Helm
`kube-prometheus-stack` (namespace `monitoring`) pour scraper les métriques
CoreDNS. Plus aucun accès générique (`pods`/`pods/log`, `secrets`) n'y est
nécessaire — l'ancien compromis (lecture de tous les pods/logs de
`kube-system`, uniquement justifié par les noms de pods aléatoires du
DaemonSet Cilium) a disparu avec la bascule.

**Namespace `cilium-secrets` — créé par le chart lui-même, inchangé par la
bascule.** Le chart Cilium crée ce namespace pour la synchro de secrets TLS
(Ingress/Gateway API/Envoy SDS), fonctionnalité présente dans le chart mais
non utilisée ici. Il ne contient que deux `Role`/`RoleBinding` gérés par la
release (`cilium-tlsinterception-secrets`,
`cilium-operator-tlsinterception-secrets`) — inventaire vérifié
exhaustivement sur le cluster réel, pas deviné. Nom fixe indépendant du
namespace d'installation de Cilium, donc non affecté par la bascule vers
`cilium-system`. Même traitement qu'ailleurs : accès nommé, jamais de
`create` (`jenkins-infra-upgrader-cilium-secrets-role.yaml`).

**Méthode d'audit à privilégier pour Cilium** : ne pas se fier uniquement à
`helm template`/aux commentaires du chart pour lister les objets à couvrir —
plusieurs objets (`cilium-envoy`, `cilium-envoy-config`, `cilium-config-agent`,
les Role/RoleBinding de `cilium-secrets`) sont passés inaperçus lors de
l'audit initial et n'ont été détectés qu'au premier upgrade réel en échec.
Commande fiable pour lister exhaustivement ce qu'une release Helm possède
réellement sur le cluster (à répéter à chaque montée de version majeure/mineure
de Cilium, avant de faire confiance au chart) :

```bash
kubectl get <kind> --all-namespaces -o json | jq -r '.items[]
  | select(.metadata.annotations."meta.helm.sh/release-name"=="cilium")
  | "\(.metadata.namespace // "-") \(.metadata.name)"'
```

à exécuter pour chaque `<kind>` namespacé pertinent (daemonsets, deployments,
configmaps, secrets, serviceaccounts, services, roles, rolebindings...).

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

### Miroir des règles Operator/Prometheus (`jenkins-infra-upgrader-clusterrole.yaml`)

En plus du `get`/`update`/`patch` nommé sur les `ClusterRole`
`prometheus-kube-prometheus-operator`/`-prometheus`, `jenkins-infra-upgrader`
détient un bloc de règles qui reprend exactement le contenu de ces deux
`ClusterRole` (union des deux, vérifiée sur le message d'erreur RBAC réel de
l'upgrade 87.17.0) : le garde-fou anti-élévation de Kubernetes exige de
détenir déjà toute règle qu'on écrit dans un `ClusterRole`, même déjà
présente et inchangée. Ni `resourceNames` ni réduction de portée possibles
(ces `ClusterRole` s'appliquent cluster-wide) — conséquence assumée :
`secrets`/`configmaps` cluster-wide pour `jenkins-infra-upgrader`.

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
