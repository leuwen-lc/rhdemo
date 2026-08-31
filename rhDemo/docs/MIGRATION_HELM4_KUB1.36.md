# Migration Helm 3 → Helm 4 + Kubernetes 1.35 → 1.36 (stagingkub)

**Statut** : ✅ Réalisé — livré en 1.1.10 (30/08/2026).
**Périmètre** : environnement `stagingkub` (KinD) uniquement. `Jenkinsfile-CD`
et `Jenkinsfile-CI` ne sont pas concernés (aucun flag Helm déprécié).

Les deux montées ont été livrées **ensemble** : changer `kindest/node` impose
de toute façon de détruire/recréer le cluster KinD, et c'est aussi le seul
scénario où le nouveau comportement par défaut de Helm 4 (server-side apply à
l'installation, cf. §3.2) s'exerce réellement.

---

## 1. État final

| Élément | Avant | Après |
|---------|-------|-------|
| CLI Helm — agent Jenkins | `3.21.4` | **`4.2.4`** (`infra/jenkins-docker/Dockerfile.agent`) |
| CLI Helm — poste dev | `3.21.x` | à passer en `4.2.x` manuellement (binaire système, hors dépôt) |
| `kindest/node` | `v1.35.0` | **`v1.36.4`** (pinné par digest + marqueur `# renovate:` dans `kind-config.yaml`) |
| CLI `kind` — poste hôte | `v0.31.0` | **`v0.33.0`** requis (hors dépôt) |
| Cilium | `1.19.x` | `1.20.1` (déjà en place avant la bascule) |
| Flag rollback des 6 scripts composants | `--atomic` | `--rollback-on-failure` |

Le backend de stockage des releases reste `sh.helm.release.v1` (Secret) :
aucune migration de données Helm, `helm-unlock.sh` et les annotations
`meta.helm.sh/*` restent valides. Vérifié à la bascule : un binaire Helm 4 lit
sans conversion les releases écrites par Helm 3.

---

## 2. Pourquoi maintenant

### Kubernetes 1.36 — débloqué par Cilium 1.20

`kind-config.yaml` a `disableDefaultCNI: true` + `kubeProxyMode: none` :
Cilium remplace le CNI **et** kube-proxy, sans filet. Si Cilium ne supporte
pas l'API server, le nœud reste `NotReady` — blocage total, pas de
dégradation partielle. Le verrou a sauté quand **Cilium 1.20 stable** est
sorti avec une matrice de compatibilité officielle **K8s 1.33 → 1.36**
(Cilium 1.19 s'arrêtait à 1.35). NGF 2.6 (K8s 1.31+) et kube-prometheus-stack
n'ont pas de plafond.

**K8s 1.37 écarté** : publié lui aussi avec kind 0.33, mais hors matrice
Cilium 1.20 (et Cilium 1.21 encore en `-dev`). On reste sur le dernier patch
1.36.

Aucun `kubeadmConfigPatches` dans `kind-config.yaml` → le passage kubeadm
`v1beta3` → `v1beta4` de K8s 1.36 est transparent.

### Helm 4 — cycle de validation dédié

Helm 3 n'était pas EOL (patchs de sécurité jusqu'à ~février 2027) : la bascule
a été planifiée hors urgence, non bundlée avec un changement applicatif, pour
isoler le risque server-side apply (§3.2).

---

## 3. Changements Helm 4 qui touchent ce projet

### 3.1 `--atomic` → `--rollback-on-failure`

Renommage mécanique dans les 6 scripts
`install-or-upgrade-{cilium,ngf,kube-prometheus-stack,loki,alloy,grafana}.sh`
(+ commentaires et doc). L'ancien `--atomic` reste accepté avec un
avertissement de dépréciation ; `--rollback-on-failure` **n'existe pas en
Helm 3** → le flag et le bump du binaire sont indissociables (même changeset).

### 3.2 Server-side apply par défaut à l'installation — le vrai point de vigilance

En Helm 4, une **installation neuve** (`helm install`, ou `helm upgrade
--install` sur une release absente) utilise le server-side apply (SSA). Un
`helm upgrade` d'une release existante conserve sa stratégie.

Conséquence : le déploiement CD courant (`rhdemo` déjà installé) est un
`upgrade`, non concerné. Mais une **recréation complète du cluster** fait de
chaque composant une install neuve → SSA actif, avec des risques de field
managers / conflits d'ownership. Échappatoire si un composant régresse :
forcer le client-side apply à l'install (`--client-side-apply` sur la 4.x
cible).

### 3.3 Sans impact (vérifié)

`--force` → `--force-replace` : `--force` non utilisé. `helm registry login`
domaine seul : le pull OCI de NGF est anonyme. Post-renderers déplacés en
plugins : non utilisés. `apiVersion: v2` du `Chart.yaml` : toujours valide.
Templates : pas de `lookup` / `.Capabilities` → aucun rendu dépendant du
cluster à re-valider. Compat client Helm 4.2.4 ↔ K8s : `KubeClientVersion
v1.36`, politique n-3 ⇒ 1.33 → 1.36.

### 3.4 Ce qui n'est PAS un risque côté K8s 1.36 (release notes vérifiées)

- Retrait d'IPVS dans kube-proxy → sans objet (kube-proxy non utilisé).
- Retrait des volumes `gitRepo`, dépréciation `externalIPs` → non utilisés.
- Retrait d'Ingress-NGINX → sans objet, projet déjà sur NGINX Gateway Fabric.

---

## 4. Bugs rencontrés et corrigés pendant la reconstruction de cluster (30/08/2026)

1. **Préflight RBAC sur cluster vierge** — `rbac-preflight-check.sh` faisait
   un `kubectl apply --dry-run=server` des Role/RoleBinding namespacés du
   chart Cilium avant que `helm install --create-namespace` n'ait créé le
   namespace (`namespaces "cilium-system"/"cilium-secrets" not found`).
   Corrigé : le préflight tolère « namespace not found » (skip doux —
   l'anti-élévation RBAC native s'applique toujours au apply réel), échec dur
   conservé pour le reste ; `install-or-upgrade-cilium.sh` / `-ngf.sh` créent
   leur namespace avant le préflight.

2. **`helm show crds` sur chart OCI en Helm 4** — pour
   `oci://…/nginx-gateway-fabric`, Helm 4 écrit les lignes `Pulled:` /
   `Digest:` sur **stdout** (stderr en Helm 3) → `kubectl apply -f` du fichier
   échouait (`apiVersion not set, kind not set`). Corrigé dans
   `install-or-upgrade-ngf.sh` : filtrage `sed -n '/^---$/,$p'` pour ne garder
   que le flux de manifestes.

3. **SSA par défaut (§3.2) matérialisé sur NGF** — l'install NGF passait
   `--set nginx.service.ports[].nodePort=…`, clé **inexistante** dans le chart
   2.6.0 (renommée `nginx.service.nodePorts[]` = `{port, listenerPort}`). Sous
   Helm 3 (client-side) le champ inconnu était silencieusement élagué — le
   NodePort n'était **jamais appliqué**. Sous Helm 4 (SSA) : `field not
   declared in schema` → release annulée par `--rollback-on-failure`. Corrigé :
   `--set nginx.service.nodePorts[0]=…`. *Effet de bord positif : le SSA a
   révélé un paramétrage mort depuis plusieurs versions.*

---

## 5. Fichiers modifiés

| Fichier | Modification |
|---------|--------------|
| `infra/jenkins-docker/Dockerfile.agent` | `HELM_VERSION` → `4.2.4` |
| `infra/stagingkub/kind-config.yaml` | `kindest/node` → `v1.36.4` (digest) + marqueur `# renovate: datasource=docker depName=kindest/node` (le digest n'était pas suivi avant) |
| `infra/stagingkub/scripts/components/install-or-upgrade-*.sh` (les 6) | `--atomic` → `--rollback-on-failure` |
| `…/components/install-or-upgrade-ngf.sh` | + filtrage stdout `helm show crds` OCI ; `--set nginx.service.nodePorts[]` |
| `…/components/install-or-upgrade-cilium.sh` | crée son namespace avant le préflight |
| `…/scripts/rbac-preflight-check.sh` | tolère « namespace not found » |
| `infra/stagingkub/scripts/test-deploy-helm.sh` | `--dry-run` → `--dry-run=client` (explicitation) |
| `infra/stagingkub/scripts/install-observability.sh` | prérequis « Helm 3 » → « Helm 4 » |
| Docs / commentaires réalignés | `README-helm-unlock.md`, `jenkins-casc.yaml`, `Jenkinsfile-Stagingkub-Upgrade-Deploy`, `Jenkinsfile-Renovate`, `STAGINGKUB_REBUILD_PIPELINE.md`, `infra/stagingkub/README.md`, `infra/stagingkub/rbac/README.md`, `helm/observability/{loki-modern,prometheus}-values.yaml`, `docs/JENKINS_AGENTS_EPHEMERES.md`, `README.md` (racine) |

**Non modifiés** : `renovate.json` (bump `helm/helm` major déjà bloqué
derrière `dependencyDashboardApproval`) · `Jenkinsfile-CD` / `Jenkinsfile-CI`
· `helm/rhdemo/Chart.yaml` (`apiVersion: v2` reste valide) ·
`migrate-postgresql-*.sh` (`helm upgrade --install` sans flag déprécié).

---

## 6. Point ouvert

`kindest/node` reste **hors périmètre** de la mise à jour en place via
`jenkins-infra-upgrader` (`Jenkinsfile-Stagingkub-Upgrade-Deploy`) : toute
future montée de version Kubernetes impose une reconstruction complète du
cluster.
