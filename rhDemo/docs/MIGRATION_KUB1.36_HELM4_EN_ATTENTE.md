# Montées de version Kubernetes 1.36 et Helm 4 — en attente

**Statut** : ✅ **Les deux verrous sont levés (30/08/2026).** Analyse initiale du
23/07/2026 conservée ci-dessous pour l'historique.
- **Helm 4** : migré, cf. [`MIGRATION_HELM_4.md`](MIGRATION_HELM_4.md).
- **Kubernetes 1.36** : débloqué (Cilium 1.20 stable supporte 1.36) — changements
  de config appliqués sur la branche `migration-helm-4`, à valider lors de la
  reconstruction de cluster de la phase 5 Helm 4.

**Concerne** : `kindest/node` (stagingkub) et le CLI `helm` utilisé par les scripts
`rhDemo/infra/stagingkub/scripts/`

Ce document trace l'analyse de risque qui a mené à repousser ces deux montées
de version, pour ne pas avoir à la refaire à chaque fois qu'elles reviennent
sur le tapis.

---

## 1. Kubernetes 1.36 (`kindest/node`)

> **✅ LEVÉ (30/08/2026).** Cilium **1.20** est sorti en stable et sa matrice de
> compatibilité officielle liste **K8s 1.33 → 1.36** en e2e-testé. Le projet
> était déjà passé à `CILIUM_VERSION="1.20.1"`. NGF 2.6.0 (K8s 1.31+) et
> kube-prometheus-stack 87.21.0 / Prom Operator v0.88.1 (K8s 1.25+) n'ont pas de
> plafond. Aucun `kubeadmConfigPatches` dans `kind-config.yaml` → le passage
> kubeadm v1beta3→v1beta4 de K8s 1.36 est transparent.
>
> Appliqué sur la branche `migration-helm-4` :
> - `kind-config.yaml` : `kindest/node:v1.36.1@sha256:3489c7674813…` (+ marqueur `# renovate:`)
> - `kind` CLI hôte : **v0.32.0 requis** (non versionné dans le dépôt)
> - docs/bannières : refs KinD 0.30/0.31 → 0.32, Cilium 1.18 → 1.20
>
> **Reste à valider** (phase 5 Helm 4, reconstruction de cluster) : que le nœud
> passe `Ready` avec Cilium 1.20.1 sur l'API 1.36 — c'est le risque ci-dessous.

**Pin (avant bascule)** : `kindest/node:v1.35.0`. CLI `kind` local en v0.31.0 ;
v0.32.0 défaut sur Kubernetes 1.36.1.

**Risque principal (analyse du 23/07) : Cilium n'était pas encore validé sur
1.36.** À l'époque, Cilium stable = 1.19.x (e2e-testé **1.32 à 1.35**), et
Cilium 1.20 encore en pré-release. Ce n'est plus le cas (cf. encadré).

**Pourquoi c'est bloquant et pas juste "à surveiller"** : `kind-config.yaml`
a `disableDefaultCNI: true` + `kubeProxyMode: none` (Cilium remplace
kube-proxy). Il n'y a **aucun filet de sécurité** — si Cilium ne s'initialise
pas correctement sur l'API 1.36, le nœud reste bloqué en `NotReady`
indéfiniment (pas de dégradation partielle, blocage total du cluster).

**Ce qui n'est PAS un risque pour ce projet** (vérifié dans les release notes
1.36) :
- Suppression d'IPVS dans kube-proxy → sans objet, kube-proxy n'est pas
  utilisé du tout ici.
- Suppression des volumes `gitRepo`, dépréciation `externalIPs` → non
  utilisés dans le repo.
- Retrait d'Ingress-NGINX (fin des patchs de sécurité, mars 2026) → sans
  objet, le projet est déjà sur NGINX Gateway Fabric/Gateway API (cf.
  [`NGINX_GATEWAY_FABRIC_MIGRATION.md`](NGINX_GATEWAY_FABRIC_MIGRATION.md)).

**Composants à risque plus faible** (API Kubernetes stables, pas d'internals
réseau) : NGINX Gateway Fabric (min K8s 1.31, pas de plafond documenté),
kube-prometheus-stack/Prometheus Operator (min K8s 1.16, pas de plafond
documenté).

**Condition pour revisiter** : une release Cilium stable (1.20.x ou +) listant
Kubernetes 1.36 dans sa matrice de compatibilité officielle.

---

## 2. Helm 4

> **✅ RÉALISÉE (branche `migration-helm-4`, cible v1.1.10).** Le plan
> d'exécution complet et le suivi sont dans
> [`MIGRATION_HELM_4.md`](MIGRATION_HELM_4.md). L'agent Jenkins est passé à
> `HELM_VERSION=4.2.4`, les 6 scripts composants utilisent
> `--rollback-on-failure`. La section ci-dessous est conservée pour l'historique
> de l'analyse de risque.

**CLI au moment de l'analyse (23/07/2026)** : `helm v3.19.2` en local ; image
Jenkins agent `HELM_VERSION=3.20.0`.

**Helm 3 n'est pas EOL** : dernière feature release prévue le 09/09/2026,
patchs de sécurité jusqu'à février 2027. Rester/monter dans la branche 3.x
est un simple bump, sans risque identifié pour ce projet.

**Changements Helm 4 pertinents pour ce projet** (vérifié dans le guide de
migration officiel) :
- `--atomic` renommé `--rollback-on-failure` — utilisé dans **les 6 scripts
  composants** (`install-or-upgrade-{cilium,ngf,kube-prometheus-stack,loki,
  alloy,grafana}.sh`). L'ancien flag reste accepté (warning de dépréciation
  uniquement), donc pas de casse immédiate.
- **Point d'attention principal** : le **server-side apply devient le
  comportement par défaut pour les nouvelles installations** (`helm install`,
  pas `upgrade` d'une release existante). Une recréation complète du cluster
  stagingkub fait de chaque composant une installation neuve — chemin de
  code jamais éprouvé avec les charts du projet. kube-prometheus-stack
  applique déjà ses CRD en `kubectl apply --server-side` explicitement (donc
  déjà couvert sur ce point précis), mais les autres `helm upgrade --install`
  changeraient de stratégie d'apply.
- `--force` → `--force-replace` : non utilisé dans le projet, sans impact.
- `helm registry login` domaine seul (pas d'URL complète) : non utilisé (le
  pull OCI de NGF, `oci://ghcr.io/nginx/charts/nginx-gateway-fabric`, est
  anonyme), sans impact.
- Post-renderers en plugins : non utilisés, sans impact.

**Condition pour revisiter** : un cycle de validation dédié (pas bundlé avec
un autre changement d'infra), pour tester le server-side apply par défaut sur
les 6 composants stagingkub avant de l'adopter en production du POC.

---

## 3. Décision actée

Pour la recréation du cluster stagingkub (migration Alloy) : **rester sur
`kindest/node:v1.35.0` et Helm 3.x**. Aucun changement de version de ces deux
outils dans cette opération.

**Mise à jour (30/08/2026)** : décision révisée. Le volet Helm 4 a été exécuté
(cf. [`MIGRATION_HELM_4.md`](MIGRATION_HELM_4.md)). Le volet Kubernetes 1.36 est
lui aussi débloqué (Cilium 1.20 stable) et **bundlé avec la reconstruction de
cluster de la phase 5 Helm 4** — puisqu'il faut de toute façon détruire/recréer
le cluster pour Helm 4, et que `kindest/node` ne se change pas autrement. La
phase 5 est séquencée (cluster 1.36 + Cilium d'abord, `Ready` confirmé, puis
reste des composants) pour garder les signaux de validation distincts.

## 4. Fichiers concernés (état sur la branche `migration-helm-4`)

| Fichier | Impact |
|---------|--------|
| `kind-config.yaml` | ✅ `kindest/node` → `v1.36.1@sha256:3489c76…` + marqueur `# renovate: datasource=docker depName=kindest/node` ajouté (le digest n'était **pas** réellement suivi avant, faute de ce marqueur) |
| `scripts/components/install-or-upgrade-cilium.sh` | déjà en `CILIUM_VERSION="1.20.1"` (compatible K8s 1.36) — rien à faire |
| `kind` CLI (poste hôte / doc) | v0.31.0 → **v0.32.0** (hors dépôt) |
| ~~`scripts/components/install-or-upgrade-*.sh` (les 6) — `--atomic` → `--rollback-on-failure`~~ | ✅ fait (Helm 4, cf. `MIGRATION_HELM_4.md`) |
| ~~`infra/jenkins-docker/Dockerfile.agent` — `HELM_VERSION`~~ | ✅ fait : `4.2.4` |
| `docs/STAGINGKUB_REBUILD_PIPELINE.md` | Rappel : `kindest/node` reste hors périmètre de la mise à jour en place (`jenkins-infra-upgrader`), toute montée de version Kubernetes passe par une reconstruction complète du cluster |
