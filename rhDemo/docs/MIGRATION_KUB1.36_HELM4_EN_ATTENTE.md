# Montées de version Kubernetes 1.36 et Helm 4 — en attente

**Statut** : ⏸️ Reportées, non appliquées à ce jour (23/07/2026)
**Concerne** : `kindest/node` (stagingkub) et le CLI `helm` utilisé par les scripts
`rhDemo/infra/stagingkub/scripts/`

Ce document trace l'analyse de risque qui a mené à repousser ces deux montées
de version, pour ne pas avoir à la refaire à chaque fois qu'elles reviennent
sur le tapis. Décision prise en marge de la migration Alloy (cf.
[`ALLOY_MIGRATION.md`](ALLOY_MIGRATION.md)) : le cluster stagingkub va être
recréé pour cette migration, occasion naturelle de se poser la question des
deux bumps — réponse : pas maintenant.

---

## 1. Kubernetes 1.36 (`kindest/node`)

**Pin actuel** : `kindest/node:v1.35.0` (`kind-config.yaml`). CLI `kind` local en
v0.31.0 ; la dernière release (v0.32.0) supporte/défaut sur Kubernetes 1.36.1.

**Risque principal : Cilium n'est pas encore validé sur 1.36.** Vérifié sur la
documentation officielle de compatibilité Cilium 1.19.6 (version stable
correspondant au pin projet `CILIUM_VERSION=1.19.5`) : Kubernetes versions
listées comme e2e-testées et garanties compatibles = **1.32 à 1.35**, pas
1.36. La version qui ajouterait le support 1.36 serait Cilium 1.20, **encore
en pré-release** (`v1.20.0-pre.0`) à ce jour — aucune version stable
disponible.

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

**CLI actuel** : `helm v3.19.2` en local ; l'image Jenkins agent
(`Dockerfile.agent`) pin `HELM_VERSION=3.20.0` (léger écart déjà existant,
sans rapport avec ce document).

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

## 4. Fichiers concernés si ces montées sont faites plus tard

| Fichier | Impact |
|---------|--------|
| `kind-config.yaml` | Digest `kindest/node` (déjà suivi par le `customManager` Renovate générique, cf. `renovate.json`) |
| `scripts/components/install-or-upgrade-cilium.sh` | `CILIUM_VERSION`, à monter en même temps que le bump Kubernetes |
| `scripts/components/install-or-upgrade-*.sh` (les 6) | `--atomic` → `--rollback-on-failure` si passage à Helm 4 |
| `infra/jenkins-docker/Dockerfile.agent` | `HELM_VERSION` du CLI embarqué dans les agents Jenkins |
| `docs/STAGINGKUB_REBUILD_PIPELINE.md` | Rappel : `kindest/node` reste hors périmètre de la mise à jour en place (`jenkins-infra-upgrader`), toute montée de version Kubernetes passe par une reconstruction complète du cluster |
