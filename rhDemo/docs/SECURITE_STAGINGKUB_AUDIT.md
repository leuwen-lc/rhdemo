# Audit de sécurité - Cluster KinD `stagingkub`

> Date : 2026-02-11 | Kubernetes v1.35.0 | Cluster KinD mono-node

## Architecture actuelle

| Composant | Image | Rôle |
|---|---|---|
| **KinD** | `kindest/node:v1.35.0` | Cluster mono-node control-plane |
| **Cilium 1.18.6** | eBPF kube-proxy replacement | CNI avancé |
| **NGINX Gateway Fabric** | Gateway API | Ingress HTTPS (TLS termination) |
| **rhdemo-app** | `rhdemo-api:1.1.0-SNAPSHOT` | Application Spring Boot |
| **Keycloak 26.5.0** | `quay.io/keycloak/keycloak:26.5.0` | IAM / OAuth2 |
| **PostgreSQL 18** | `postgres:18-alpine` | 2 instances (rhdemo + keycloak) |
| **postgres-exporter** | `v0.19.0` | Métriques Prometheus |
| **Backups CronJob** | `postgres:16-alpine` | Sauvegardes quotidiennes (2h/3h) |

## Points forts

- **Modèle Zero Trust réseau** : default deny all + rules explicites par pod (NetworkPolicies complètes)
- **RBAC Jenkins** : permissions granulaires par namespace, pas de cluster-admin
- **TLS termination** : HTTPS via Gateway API avec certificat wildcard `*.intra.leuwen-lc.fr`
- **Secrets** : gérés via SOPS + Kubernetes Secrets (pas en clair dans les manifests)
- **Resource limits** : CPU/mémoire définis sur tous les workloads
- **Health checks** : liveness + readiness probes sur tous les deployments
- **Backups** : pg_dump quotidien avec rétention 7 jours et validation de taille
- **Observabilité** : ServiceMonitors Prometheus, postgres-exporter

---

## ALERTE : Aucun `securityContext` n' était configuré 

Après vérification de **tous les manifests**, **aucun** deployment, statefulset ou cronjob ne définit de `securityContext`. Cela signifie :

| Fichier | `runAsNonRoot` | `allowPrivilegeEscalation` | `drop: ALL` | `readOnlyRootFilesystem` |
|---|---|---|---|---|
| `rhdemo-app-deployment.yaml` | absent | absent | absent | absent |
| `keycloak-deployment.yaml` | absent | absent | absent | absent |
| `postgresql-rhdemo-statefulset.yaml` | absent | absent | absent | absent |
| `postgresql-keycloak-statefulset.yaml` | absent | absent | absent | absent |
| `postgresql-backup-cronjob.yaml` | absent | absent | absent | absent |
| init containers `busybox:1.36` | absent | absent | absent | absent |

**Conséquence** : Tous les containers s'exécutent potentiellement en **root** et peuvent **escalader leurs privilèges**. C'est le point de sécurité le plus critique du cluster.

### Analyse par image

- **`postgres:18-alpine`** : l'entrypoint Docker officiel démarre en root puis fait un `gosu postgres`, mais le container lui-même tourne initialement en root (UID 0)
- **`quay.io/keycloak/keycloak:26.5.0`** : l'image Keycloak officielle tourne en UID 1000 (non-root) par défaut, mais sans `runAsNonRoot: true` dans le manifest, rien ne l'empêche de revenir à root
- **`rhdemo-api` (Eclipse Temurin 25)** : le Dockerfile définit `USER spring:spring` (non-root, créé avec `useradd -r`), mais le UID système n'est pas fixé explicitement — il faut le vérifier avec `docker run --rm rhdemo-api id` pour configurer `runAsUser` correctement
- **`busybox:1.36`** : tourne en root par défaut
- **`postgres:16-alpine` (backup)** : tourne en root par défaut

---

## Améliorations de sécurité pour se rapprocher de la production

### 1. Ajouter les `securityContext` sur tous les workloads (CRITIQUE) (FAIT)

Le minimum requis pour chaque container :

```yaml
securityContext:
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
  seccompProfile:
    type: RuntimeDefault
```

Et au niveau pod :

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    fsGroup: 1000
```

### 2. Activer Pod Security Admission (CRITIQUE) (FAIT en warn/audit pas en enforce)

Appliquer le label sur le namespace pour enforcer le profil `restricted` :

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

### 3. Keycloak en mode production (IMPORTANT) 

Actuellement en `start-dev` (`keycloak-deployment.yaml:30`), qui désactive des protections de sécurité. Pour un staging représentatif, utiliser `start` avec un build optimisé.

### 4. Ajouter `readOnlyRootFilesystem: true` (RECOMMANDE) 

Empêche les containers d'écrire sur le filesystem racine, limitant l'impact d'une compromission. Nécessite des `emptyDir` pour les répertoires temp.

### 5. Ajouter des ResourceQuotas et LimitRanges (RECOMMANDE)

Prévenir l'épuisement des ressources du namespace :

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: rhdemo-quota
spec:
  hard:
    pods: "20"
    requests.cpu: "4"
    requests.memory: 4Gi
```

### 6. Ajouter des PodDisruptionBudgets (RECOMMANDE)

Pour les déploiements multi-réplicas en production.

### 7. Image tagging par digest (RECOMMANDE)

Remplacer les tags mutables (`18-alpine`, `1.36`) par des digests SHA256 pour garantir l'immutabilité.

### 8. ServiceAccount dédiés (BONNE PRATIQUE)

Aucun workload ne définit de `serviceAccountName` ni `automountServiceAccountToken: false`. Chaque pod monte automatiquement le token du service account par défaut.

---

## Kubernetes 1.35 - Avancées sécurité pertinentes pour stagingkub

Le cluster tourne déjà en **v1.35.0**. Voici les fonctionnalités de sécurité activables :

| Feature K8s 1.35 | Statut | Pertinence pour stagingkub |
|---|---|---|
| **User Namespaces** (beta) | Utilisable | Les pods tournent en root *dans* le container mais sont mappés sur un UID non-privilégié sur l'hôte. Réduit massivement le risque d'évasion |
| **Constrained Impersonation** (alpha) | Feature gate | Empêche les machines compromises d'usurper l'identité de noeuds légitimes |
| **WebSocket Upgrade Authorization** | Par défaut | `kubectl exec` requiert maintenant le verbe `create` en plus de `get` - vérifier que le RBAC Jenkins est à jour |
| **Kubelet Certificate CN Validation** | Feature gate | Renforce la validation des certificats kubelet (pertinent si multi-node) |
| **`supplementalGroupsPolicy: Strict`** | Stable | Empêche les images malveillantes d'escalader via `/etc/group` |
| **Image Pull Credential Verification** | Par défaut | Empêche le vol d'images entre tenants (utile si registry partagé) |
| **Pod Certificates** (beta) | Utilisable | Provisionnement X.509 simplifié pour les workloads |
| **Cgroup v2** obligatoire | Breaking change | Vérifier que la machine hôte est bien en cgroup v2 |

### Recommandation pour K8s 1.35

Activer les **User Namespaces** pour que même sans `securityContext` parfait, un container root soit isolé de l'hôte :

```yaml
apiVersion: v1
kind: Pod
spec:
  hostUsers: false  # Active les user namespaces
```

---

## Résumé des priorités

| Priorité | Action | Effort |
|---|---|---|
| **P0** | Ajouter `securityContext` sur tous les containers | Moyen |
| **P0** | Activer Pod Security Admission `restricted` | Faible |
| **P1** | Passer Keycloak en mode `start` (production) | Faible |
| **P1** | `automountServiceAccountToken: false` + SA dédiés | Faible |
| **P1** | Activer `hostUsers: false` (user namespaces K8s 1.35) | Faible |
| **P2** | `readOnlyRootFilesystem: true` | Moyen |
| **P2** | ResourceQuotas + LimitRanges | Faible |
| **P2** | Image pinning par digest SHA256 | Faible |
| **P3** | `supplementalGroupsPolicy: Strict` | Faible |
| **P3** | PodDisruptionBudgets | Faible |

---

## Analyse des risques de régression

Chaque mesure de sécurité listée ci-dessus a un potentiel de régression sur les workloads existants.
Cette section détaille les risques concrets par mesure et par composant.

### P0 : `securityContext` — runAsNonRoot + allowPrivilegeEscalation: false + drop ALL

#### PostgreSQL 18-alpine (2 instances + backup CronJobs) — RISQUE ELEVE

L'entrypoint `docker-entrypoint.sh` de l'image officielle `postgres:18-alpine` :

1. Démarre en **root (UID 0)**
2. Crée les répertoires de données avec les bonnes permissions
3. Appelle **`gosu postgres`** pour basculer vers UID 70 (alpine) via les syscalls `setuid`/`setgid`

| Mesure | Effet | Casse ? |
|---|---|---|
| `runAsNonRoot: true` | Le container refuse de démarrer car l'entrypoint est UID 0 | **OUI — crash au start** |
| `allowPrivilegeEscalation: false` | Active le flag kernel `no_new_privs` → `gosu` échoue avec `"failed switching to 'postgres': operation not permitted"` car setuid/setgid sont bloqués | **OUI — crash au start** |
| `capabilities.drop: ["ALL"]` | Supprime `CAP_SETUID`/`CAP_SETGID` nécessaires à gosu | **OUI — crash au start** |

**Contournement** : utiliser `runAsUser: 70` + `runAsGroup: 70` dans le pod spec. L'entrypoint
détecte `id -u != 0`, skip gosu entièrement, et démarre PostgreSQL directement. Dans ce cas
`allowPrivilegeEscalation: false` et `drop: ALL` fonctionnent.

**Attention — migration des données existantes** : les données sur les hostPath
(`/home/leno-vo/kind-data/rhdemo-stagingkub/postgresql-*`) ont probablement été créées par root.
Avec `runAsUser: 70`, PostgreSQL ne pourra pas lire ses propres fichiers de données. Solutions :

- un `initContainer` root qui fait `chown -R 70:70 /var/lib/postgresql`
- un `fsGroup: 70` dans le pod securityContext (ne fonctionne pas avec hostPath, uniquement avec PVC)
- un `chown` manuel sur l'hôte avant redéploiement

Le CronJob de backup (`postgres:16-alpine`) a exactement le même problème — `pg_dump` doit
tourner en tant que l'utilisateur postgres (UID 70).

#### busybox:1.36 (init containers) — RISQUE MOYEN

Tourne en root par défaut. La commande `nc -z <host> <port>` fonctionne en non-root pour les
ports > 1024 (5432 et 8080 sont OK).

**Contournement** : `runAsUser: 65534` (nobody) fonctionne.

#### Keycloak 26.5.0 — RISQUE FAIBLE

L'image officielle définit `USER 1000` dans le Dockerfile. `runAsNonRoot: true`,
`allowPrivilegeEscalation: false` et `drop: ALL` devraient fonctionner sans régression.

Point de vigilance : Keycloak est membre du groupe `root` (GID 0) pour compatibilité OpenShift.
Si des fichiers internes dépendent de cette appartenance au GID 0, un `drop: ALL` combiné avec
un `supplementalGroupsPolicy: Strict` pourrait poser problème (voir section dédiée).

#### rhdemo-app (Eclipse Temurin 25) — RISQUE FAIBLE (corrigé)

Le Dockerfile définit `USER spring:spring` (non-root). L'utilisateur est créé via `useradd -r`
(system user) sans UID explicite. Avec `runAsNonRoot: true` au niveau pod, Kubernetes ne peut pas
vérifier que l'utilisateur `spring` (déclaré par nom, non numérique) n'est pas root, et rejette le
container avec l'erreur `CreateContainerConfigError` :

> *container has runAsNonRoot and image has non-numeric user (spring), cannot verify user is non-root*

**Solution appliquée** : ajout de `runAsUser: 1000` dans le `securityContext` du container
`rhdemo-app`. Cela fournit à Kubernetes un UID numérique vérifiable, résolvant l'erreur.
`allowPrivilegeEscalation: false` et `drop: ALL` fonctionnent sans régression.

> **Recommandation** : fixer le UID dans le Dockerfile (`useradd -r -u 1000 -g spring spring`) pour
> garantir la cohérence entre l'UID de l'image et le `runAsUser` du manifest Kubernetes.

#### postgres-exporter v0.19.0 — RISQUE FAIBLE

L'image communautaire Prometheus tourne en non-root. À vérifier au déploiement.

---

### P0 : Pod Security Admission `restricted`

**Risque critique d'ordre d'application** : si on active le label
`pod-security.kubernetes.io/enforce: restricted` sur le namespace **avant** d'avoir corrigé tous
les securityContext, **tous les futurs pods seront rejetés** par l'admission controller. Les pods
existants continuent de tourner, mais au prochain redéploiement, Helm/Jenkins ne pourra plus créer
de pods.

**Ordre obligatoire** :

1. Corriger tous les securityContext sur tous les workloads
2. Déployer et valider que tout fonctionne
3. Activer PSA en mode `warn` + `audit` uniquement (les pods non conformes génèrent des warnings mais ne sont pas bloqués)
4. Vérifier les logs et corriger les derniers problèmes
5. Passer en `enforce` une fois que tous les pods sont conformes

---

### P1 : Keycloak `start` au lieu de `start-dev`

| Comportement | `start-dev` (actuel) | `start` (cible) |
|---|---|---|
| Cache des thèmes | Désactivé (hot-reload) | Activé |
| HTTP | Autorisé | Requiert `--http-enabled=true` ou HTTPS |
| Build Quarkus | Auto à chaque démarrage | Requiert un pré-build ou fait un build au start |
| CSP headers | Relaxés | Plus stricts |
| Temps de démarrage | Rapide | Plus long si pas de `--optimized` |

**Risques concrets** :

- **Temps de démarrage** : sans `--optimized`, Keycloak fait un build Quarkus au démarrage → le
  `readinessProbe` (60s initialDelay + failureThreshold 15) pourrait timeout si le build est lent
- **Thèmes custom** : si des thèmes sont modifiés en live, le cache activé en mode `start` ne
  les rechargera pas
- **Configuration** : certains paramètres acceptés en `start-dev` sont rejetés en `start`
  (ex: hostnames non-HTTPS sans flag explicite)

**Contournement recommandé** : builder une image custom avec `kc.sh build` dans le Dockerfile,
puis utiliser `start --optimized` au runtime.

---

### P1 : `automountServiceAccountToken: false`

**Risque faible**. Aucun des workloads applicatifs (rhdemo-app, Keycloak, PostgreSQL) n'utilise
l'API Kubernetes. Les health checks du kubelet n'utilisent pas le token SA — ils font des requêtes
HTTP directes vers les ports des containers.

Seul cas de casse possible : si un init container ou un sidecar utilisait `kubectl` ou l'API K8s
en interne (ce n'est pas le cas ici).

---

### P1 : User Namespaces K8s 1.35 (`hostUsers: false`) — RISQUE ELEVE

C'est la mesure K8s 1.35 avec le plus fort potentiel de régression.

**Mécanisme** : les UIDs sont remappés — UID 0 dans le container correspond à UID 65536+ sur
l'hôte. Kubernetes utilise des **idmap mounts** pour traduire les UIDs au niveau des volumes.

#### Volumes hostPath et permissions — RISQUE CRITIQUE

Les données PostgreSQL existantes sur l'hôte (`/home/leno-vo/kind-data/rhdemo-stagingkub/postgresql-*`)
ont été créées avec les UIDs réels (UID 70 pour postgres sur alpine). Après activation des user
namespaces :

- Le UID 70 du container est remappé vers UID 65536+70 = 65606 sur l'hôte
- Les fichiers existants (owned par UID 70 sur l'hôte) apparaissent comme owned par un UID inconnu
  dans le container
- **PostgreSQL ne peut plus lire ses données** → crash au démarrage

Le filesystem du hostPath doit supporter les **idmap mounts** (ext4, XFS, btrfs = OK ; NFS = NON).
Vérifier avec :

```bash
df -T /home/leno-vo/kind-data/
```

#### Volumes tmpfs (secrets, configmaps, projected) — OK

Le kernel de la machine est **6.17.0** → le support idmap pour tmpfs est présent (requis >= 6.3).
Les secrets Kubernetes (montés via projected volumes tmpfs) fonctionneront.

#### Backups hostPath

Les CronJobs de backup écrivent dans `/mnt/backups/` (hostPath). Les fichiers créés auront les
UIDs remappés sur l'hôte, ce qui peut casser la restauration si elle est faite depuis un autre
contexte (hôte direct, autre container sans user namespaces).

#### Incompatibilités

`hostUsers: false` ne peut pas être combiné avec `hostNetwork: true`, `hostIPC: true`, ou
`hostPID: true` (pas utilisés ici, mais à savoir pour l'avenir).

---

### P2 : `readOnlyRootFilesystem: true`

Chaque workload a besoin de répertoires temporaires montés en écriture (`emptyDir`) :

| Workload | Répertoires à monter en `emptyDir` | Risque sans ces volumes |
|---|---|---|
| **PostgreSQL** | `/var/run/postgresql` (socket Unix + PID), `/tmp` | Crash : impossible de créer le socket |
| **Keycloak** | `/opt/keycloak/data` (transaction logs), `/tmp` (JVM) | Crash : échec Quarkus au démarrage |
| **rhdemo-app** | `/tmp` (Tomcat work directory) | Crash : Spring Boot ne peut pas créer les fichiers temp |
| **postgres-exporter** | `/tmp` | Probablement OK sans, à tester |
| **busybox (init)** | Aucun (`nc` ne write pas) | OK |
| **Backup CronJob** | `/tmp` (fichiers temp pour le dump) | Crash : pg_dump échoue |

Le risque principal est **d'oublier un répertoire**, ce qui provoque un crash difficile à
diagnostiquer (erreur `Permission denied` sur un fichier temp interne).

Exemple minimal pour PostgreSQL :

```yaml
securityContext:
  readOnlyRootFilesystem: true
volumeMounts:
  - name: data
    mountPath: /var/lib/postgresql 
  - name: run
    mountPath: /run/postgresql
  - name: tmp
    mountPath: /tmp
volumes:
  - name: run
    emptyDir:
      medium: Memory
  - name: tmp
    emptyDir:
      medium: Memory
```

---

### P3 : `supplementalGroupsPolicy: Strict`

**Mécanisme** : par défaut, Kubernetes fusionne les groupes supplémentaires définis dans le pod
spec (`supplementalGroups`, `fsGroup`) avec ceux du `/etc/group` de l'image container. Avec
`Strict`, **seuls** les groupes du pod spec sont appliqués. Les groupes définis dans `/etc/group`
de l'image sont ignorés.

| Workload | Groupes dans l'image | Risque avec `Strict` |
|---|---|---|
| **PostgreSQL alpine** | `postgres` (GID 70) via `/etc/group` | **MOYEN** : si les fichiers de données sont owned par GID 70, il faut ajouter `fsGroup: 70` ou `supplementalGroups: [70]` dans le pod spec, sinon perte d'accès |
| **Keycloak** | `root` (GID 0) pour compatibilité OpenShift | **MOYEN** : certains fichiers sous `/opt/keycloak/` sont writable via le GID 0. Sans GID 0 dans `supplementalGroups`, Keycloak pourrait perdre l'accès en écriture à ses répertoires de données |
| **rhdemo-app** | `spring` (GID système, non fixé) | **FAIBLE** : les fichiers sont owned par `spring:spring`, le primary group suffit. Vérifier le GID réel si `supplementalGroups` est nécessaire |
| **busybox** | `root` (GID 0) | **FAIBLE** : pas d'écriture de fichiers |

Le piège avec `Strict` est que **la casse peut être silencieuse** : tout fonctionne au premier
déploiement, mais un cas limite (un fichier avec des permissions groupe spécifiques, une
bibliothèque qui vérifie l'appartenance à un groupe) provoque des `Permission denied`
intermittents difficiles à corréler avec cette policy.

---

### Matrice de synthèse des risques

| Mesure | PostgreSQL | Keycloak | rhdemo-app | busybox | Backup CronJob |
| --- | --- | --- | --- | --- | --- |
| `runAsNonRoot: true` | **CASSE** (gosu) | OK | OK | **CASSE** | **CASSE** (gosu) |
| `allowPrivilegeEscalation: false` | **CASSE** (gosu) | OK | OK | OK | **CASSE** (gosu) |
| `drop: ["ALL"]` | **CASSE** (gosu) | OK | OK | OK | **CASSE** (gosu) |
| PSA `restricted` | **CASSE** (tout) | OK | OK | **CASSE** | **CASSE** (tout) |
| Keycloak `start` | n/a | Attention startup | n/a | n/a | n/a |
| `automountServiceAccountToken: false` | OK | OK | OK | OK | OK |
| `hostUsers: false` (User NS) | **CASSE** (hostPath) | OK | OK | OK | **CASSE** (hostPath) |
| `readOnlyRootFilesystem` | **CASSE** sans emptyDir | **CASSE** sans emptyDir | **CASSE** sans emptyDir | OK | **CASSE** sans emptyDir |
| `supplementalGroupsPolicy: Strict` | Risque moyen | Risque moyen | OK | OK | Risque moyen |

### Stratégie d'application recommandée

L'ordre d'application le plus sûr pour éviter les régressions :

1. ✅ **Phase 1 — securityContext** : appliquer `runAsUser`/`runAsGroup` spécifiques par workload
   (PostgreSQL: 70, Keycloak: 1000, rhdemo-app: UID `spring` à vérifier, busybox: 65534) + migrer les permissions
   des données existantes sur l'hôte — **appliqué le 2026-02-11**
2. ✅ **Phase 2 — Tester** : valider que tous les pods démarrent, que les données sont accessibles,
   que les backups fonctionnent — **validé**
3. ✅ **Phase 3 — PSA warn/audit** : activer Pod Security Admission en mode warning uniquement — **appliqué le 2026-02-23**
4. **Phase 4 — readOnlyRootFilesystem** : ajouter les `emptyDir` nécessaires et activer
5. **Phase 5 — PSA enforce** : passer en enforcement une fois tout validé
6. **Phase 6 — User Namespaces** : activer `hostUsers: false` après avoir résolu les permissions
   hostPath (ou après migration vers des PVC avec idmap mounts)
7. **Phase 7 — supplementalGroupsPolicy: Strict** : activer en dernier, après avoir explicité
   tous les `fsGroup`/`supplementalGroups` dans les pod specs

---

## Mise en place concrète des mesures

### Phase 1 — securityContext (appliquée)

> Date d'application : 2026-02-11

#### Résumé des modifications par fichier

| Fichier | Pod securityContext | Container securityContext | initContainer ajouté | automountServiceAccountToken |
| --- | --- | --- | --- | --- |
| `rhdemo-app-deployment.yaml` | `runAsNonRoot`, `seccompProfile: RuntimeDefault` | `runAsUser: 1000`, `allowPrivilegeEscalation: false`, `drop: ALL` | Non (déjà présent : wait-for-db, wait-for-keycloak en UID 65534) | `false` |
| `keycloak-deployment.yaml` | `runAsNonRoot`, `seccompProfile: RuntimeDefault` | `runAsUser: 1000`, `allowPrivilegeEscalation: false`, `drop: ALL` | Non (déjà présent : wait-for-db en UID 65534) | `false` |
| `postgresql-rhdemo-statefulset.yaml` | `runAsUser: 70`, `runAsGroup: 70`, `fsGroup: 70`, `seccompProfile: RuntimeDefault` | `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `drop: ALL` (postgresql + postgres-exporter) | `fix-permissions` (chown 70:70) | `false` |
| `postgresql-keycloak-statefulset.yaml` | `runAsUser: 70`, `runAsGroup: 70`, `fsGroup: 70`, `seccompProfile: RuntimeDefault` | `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `drop: ALL` | `fix-permissions` (chown 70:70) | `false` |
| `postgresql-backup-cronjob.yaml` (x2) | `seccompProfile: RuntimeDefault` | `runAsNonRoot`, `runAsUser: 70`, `runAsGroup: 70`, `allowPrivilegeEscalation: false`, `drop: ALL` | `fix-permissions` (chown 70:70 /backups) | `false` |

#### Contournement PostgreSQL — gosu et UID 70

L'image `postgres:18-alpine` démarre en root et utilise `gosu postgres` (UID 70) pour changer
d'utilisateur, ce qui nécessite `CAP_SETUID`/`CAP_SETGID` et `allowPrivilegeEscalation: true`.

**Solution appliquée** : forcer `runAsUser: 70` / `runAsGroup: 70` au niveau pod. L'entrypoint
`docker-entrypoint.sh` détecte que `id -u` != 0, skip entièrement l'appel à `gosu`, et démarre
PostgreSQL directement en tant que l'utilisateur `postgres`. Cela permet d'appliquer
`allowPrivilegeEscalation: false` et `capabilities.drop: ["ALL"]` sans régression.

Le même contournement est appliqué aux CronJobs de backup (`postgres:16-alpine`), qui utilisent
le même mécanisme `gosu`.

#### Migration des permissions — initContainer fix-permissions

Les données PostgreSQL existantes sur les hostPath (via PV `manual-postgresql`) ont été créées par
root (UID 0). Avec `runAsUser: 70`, PostgreSQL ne peut plus lire ses propres fichiers.

**Solution appliquée** : un `initContainer` nommé `fix-permissions` exécute `chown -R 70:70` sur
le volume de données avant le démarrage du container principal. Ce container :

- Tourne en root (`runAsUser: 0`, `runAsNonRoot: false`)
- Dispose des capabilities `CAP_CHOWN`, `CAP_DAC_READ_SEARCH` et `CAP_FOWNER` (toutes les autres sont supprimées)
- `allowPrivilegeEscalation: false` reste actif

> **Note importante** : `runAsNonRoot: true` est défini au niveau **container** (et non au niveau
> pod) pour les containers principaux. Cela évite un conflit avec l'initContainer `fix-permissions`
> qui doit tourner en root (UID 0). Certaines versions de kubelet ou politiques d'admission
> peuvent rejeter un pod qui déclare `runAsNonRoot: true` au niveau pod alors qu'un initContainer
> a `runAsUser: 0`, provoquant une erreur "stream closed: EOF". Les CronJobs de backup utilisent
> déjà cette approche (pas de `runAsNonRoot` au niveau pod).

```yaml
initContainers:
- name: fix-permissions
  image: busybox:1.36
  command: ['sh', '-c', 'chown -R 70:70 /var/lib/postgresql']
  volumeMounts:
  - name: postgresql-data
    mountPath: /var/lib/postgresql
  securityContext:
    runAsUser: 0
    runAsNonRoot: false
    allowPrivilegeEscalation: false
    capabilities:
      drop: ["ALL"]
      add: ["CHOWN", "DAC_READ_SEARCH", "FOWNER"]
```

Les capabilities supplémentaires sont nécessaires pour que `chown -R` puisse traverser et modifier
l'arborescence complète du volume :

- `CHOWN` : changer le propriétaire des fichiers
- `DAC_READ_SEARCH` : traverser les répertoires sans vérification des permissions read/execute
- `FOWNER` : bypasser les vérifications de propriétaire sur les opérations fichier

Pour les CronJobs de backup, le même pattern est appliqué sur le hostPath `/backups`.

#### UIDs par workload

| Workload | UID | GID | Utilisateur |
| --- | --- | --- | --- |
| rhdemo-app | 1000 | 1000 | `spring` (Eclipse Temurin) — `runAsUser: 1000` explicite requis car l'image déclare l'utilisateur par nom |
| Keycloak | 1000 | — | UID fixé dans l'image officielle |
| PostgreSQL (x2) | 70 | 70 | `postgres` sur Alpine |
| postgres-exporter | 70 (hérité du pod) | 70 (hérité du pod) | non-root |
| busybox (init wait-for-*) | 65534 | — | `nobody` |
| busybox (init fix-permissions) | 0 | — | `root` (CAP_CHOWN, CAP_DAC_READ_SEARCH, CAP_FOWNER) |
| Backup CronJobs (x2) | 70 | 70 | `postgres` sur Alpine |

#### Validation post-déploiement

Commandes à exécuter après `helm upgrade` pour valider la Phase 1 :

```bash
# Vérifier que tous les pods démarrent correctement
kubectl get pods -n rhdemo -w

# Vérifier les securityContext effectifs sur un pod PostgreSQL
kubectl get pod postgresql-rhdemo-0 -n rhdemo -o jsonpath='{.spec.securityContext}' | jq .
kubectl get pod postgresql-rhdemo-0 -n rhdemo -o jsonpath='{.spec.containers[0].securityContext}' | jq .

# Vérifier que PostgreSQL tourne bien en UID 70
kubectl exec postgresql-rhdemo-0 -n rhdemo -- id
# Attendu : uid=70(postgres) gid=70(postgres)

# Vérifier que les données sont accessibles
kubectl exec postgresql-rhdemo-0 -n rhdemo -- psql -U rhdemo -c "SELECT count(*) FROM information_schema.tables;"

# Tester un backup manuel
kubectl create job --from=cronjob/postgresql-rhdemo-backup test-backup-rhdemo -n rhdemo
kubectl logs job/test-backup-rhdemo -n rhdemo -f

# Nettoyer le job de test
kubectl delete job test-backup-rhdemo -n rhdemo
```

### Phase 3 — PSA warn/audit (appliquée)

> Date d'application : 2026-02-23

#### Modification apportée

Ajout de 4 labels PSA sur le namespace `rhdemo-stagingkub` dans `scripts/init-stagingkub.sh` :

```yaml
pod-security.kubernetes.io/audit: restricted
pod-security.kubernetes.io/audit-version: latest
pod-security.kubernetes.io/warn: restricted
pod-security.kubernetes.io/warn-version: latest
```

**Mode choisi** : `warn` + `audit`, niveau `restricted`. Pas d'`enforce` à ce stade.

- `warn` : Kubernetes retourne un header HTTP `Warning` dans la réponse kubectl lors du `apply` ou du démarrage de pod non conforme. Visible directement dans le terminal.
- `audit` : les violations sont enregistrées dans l'audit log de l'API server. Permet une analyse a posteriori.
- `version: latest` : utilise les règles de la version courante du cluster (1.35).

Pour appliquer sans recréer le cluster :

```bash
kubectl label namespace rhdemo-stagingkub \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/audit-version=latest \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/warn-version=latest
```

#### Violations identifiées (niveau `restricted`)

Les 4 initContainers `fix-permissions` génèrent des warnings. Le contenu du warning permet d'identifier le workload :

| Warning | Violations spécifiques | Workload identifié |
|---|---|---|
| #1 | capabilities + runAsUser=0 | `postgresql-rhdemo` StatefulSet |
| #2 | capabilities + runAsUser=0 | `postgresql-keycloak` StatefulSet |
| #3 | capabilities + runAsUser=0 + **hostPath** | `postgresql-rhdemo-backup` CronJob |
| #4 | capabilities + runAsUser=0 + **hostPath** | `postgresql-keycloak-backup` CronJob |

Les StatefulSets utilisent des PVC (pas de `hostPath` direct) — les CronJobs utilisent un `hostPath` pour `/mnt/backups`, ce qui ajoute une violation supplémentaire de type `restricted volume types`.

| Règle PSA `restricted` | Violation | Workloads concernés | Justification métier |
|---|---|---|---|
| `runAsNonRoot: true` requis | `runAsUser: 0` / `runAsNonRoot: false` | StatefulSets + CronJobs (×4) | Doit tourner en root pour `chown -R` |
| Aucune capability ajoutée | `add: [CHOWN, DAC_READ_SEARCH, FOWNER]` | StatefulSets + CronJobs (×4) | Nécessaire pour traverser et modifier l'arborescence |
| Volume type restreint | `hostPath` interdit | CronJobs backup (×2) | Accès au répertoire de backup sur le nœud KinD |

Note : `DAC_READ_SEARCH` n'est pas non plus dans la liste des capabilities autorisées par `baseline`. Ces violations constituent l'unique exception justifiée et documentée (voir Phase 1).

#### Workloads conformes `restricted`

| Workload | Conformité `restricted` |
|---|---|
| `rhdemo-app` | ✅ Conforme |
| `keycloak` | ✅ Conforme |
| `postgresql-rhdemo` (container principal) | ✅ Conforme |
| `postgresql-keycloak` (container principal) | ✅ Conforme |
| `postgres-exporter` sidecar | ✅ Conforme |
| `busybox` initContainers wait-for-* | ✅ Conforme |
| `fix-permissions` initContainers StatefulSets (×2) | ❌ 2 violations (capabilities, runAsUser=0) |
| `fix-permissions` initContainers CronJobs (×2) | ❌ 3 violations (capabilities, runAsUser=0, hostPath) |

#### Exemple de warning kubectl attendu

Lors d'un `helm upgrade` ou `kubectl apply`, le terminal affichera :

```
Warning: would violate PodSecurity "restricted:latest":
  allowPrivilegeEscalation != false (container "fix-permissions" must set
  securityContext.allowPrivilegeEscalation=false),
  unrestricted capabilities (container "fix-permissions" must set
  securityContext.capabilities.drop=["ALL"]; container "fix-permissions" must
  not include "CHOWN", "DAC_READ_SEARCH", "FOWNER" in
  securityContext.capabilities.add),
  runAsNonRoot != true (pod or container "fix-permissions" must set
  securityContext.runAsNonRoot=true)
```

Ces warnings sont **attendus et documentés**. Ils n'ont pas d'impact sur le déploiement.

---

## Sources

- [Kubernetes 1.35 - New security features | Sysdig](https://www.sysdig.com/blog/kubernetes-1-35-whats-new)
- [Kubernetes v1.35: Timbernetes Release | kubernetes.io](https://kubernetes.io/blog/2025/12/17/kubernetes-v1-35-release/)
- [Kubernetes Security: 2025 Stable Features and 2026 preview | CNCF](https://www.cncf.io/blog/2025/12/15/kubernetes-security-2025-stable-features-and-2026-preview/)
