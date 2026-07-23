# Migration Promtail → Grafana Alloy (stagingkub)

**Statut** : ✅ Code migré, cluster pas encore recréé (à faire par l'utilisateur)
**Environnement** : stagingkub (Kubernetes/KinD)
**Version Alloy** : chart `grafana/alloy` 1.11.0 (Alloy v1.18.0)

---

## 1. Contexte

Promtail est en LTS depuis le 13/02/2025 et **EOL depuis le 02/03/2026** : plus
aucun correctif de sécurité fourni par Grafana Labs. Le remplaçant officiel
est Grafana Alloy.

**Licence vérifiée** : Alloy est Apache-2.0 (`LICENSE` du repo
`grafana/alloy`) — contrairement à Loki/Grafana (AGPLv3), qui avaient forcé
le projet à basculer Loki vers un fork communautaire (commit `be796db`).
Aucun contournement de licence nécessaire ici.

Le cluster KinD `rhdemo` n'a **pas** été touché : cette migration porte
uniquement sur le code/config, l'utilisateur recrée le cluster de zéro
(`kind delete` + `init-stagingkub.sh` + `install-observability.sh`), donc pas
de bascule "en place" (`helm uninstall promtail` + `helm install alloy`) à
gérer.

---

## 2. Procédure exécutée

1. **Nouveau chart Helm** : `install-or-upgrade-promtail.sh` +
   `promtail-values.yaml` renommés/réécrits en
   `install-or-upgrade-alloy.sh` + `alloy-values.yaml`
   (`rhDemo/infra/stagingkub/{scripts/components,helm/observability}/`).
   La config Promtail (YAML `scrapeConfigs`/`relabel_configs`) a été
   traduite terme à terme dans le langage Alloy
   (`discovery.kubernetes`/`discovery.relabel`/`local.file_match`/
   `loki.source.file`/`loki.process`/`loki.write`), en préservant le même
   comportement : découverte limitée au namespace `rhdemo-stagingkub`, mêmes
   labels produits (`namespace`/`pod`/`container`/`app`/`component`/`job`),
   lecture des logs via hostPath (`/var/log/pods`, pas de flux réseau vers
   les pods sources — choix délibéré de `local.file_match`/`loki.source.file`
   plutôt que `loki.source.kubernetes`, qui streamerait via l'API server),
   parsing CRI identique.
2. **Orchestrateur** `install-observability.sh` : étape renommée, appelle
   le nouveau script.
3. **Renovate** (`renovate.json`) : `managerFilePatterns` du custom manager
   des composants stagingkub mis à jour (`install-or-upgrade-alloy.sh`).
   Tag de version dans le script :
   `# renovate: datasource=helm depName=alloy registryUrl=https://grafana.github.io/helm-charts`.
4. **RBAC** (`rbac/jenkins-infra-upgrader-clusterrole.yaml` et fichiers
   associés) : `promtail` → `alloy` dans les listes `resourceNames`
   (`clusterroles`/`clusterrolebindings`).
5. **NetworkPolicies** (`networkpolicies/loki-stack-networkpolicies.yaml`) :
   `promtail-netpol` → `alloy-netpol`, `allow-apiserver-promtail` →
   `allow-apiserver-alloy` (CiliumNetworkPolicy), port de health check
   `3101` → `12345` (port `http-metrics` par défaut d'Alloy).
6. **Jenkins** (`Jenkinsfile-Stagingkub-Upgrade-Deploy`, `jenkins-casc.yaml`) :
   texte du paramètre `COMPONENT` mis à jour. Aucune logique changée — le
   pipeline déduit déjà dynamiquement le composant et le script depuis
   `install-or-upgrade-*.sh`.
7. **Documentation** : toutes les mentions de Promtail renommées en Alloy
   dans `OBSERVABILITY_STACK_INTEGRATION.md`, `STAGINGKUB_REBUILD_PIPELINE.md`,
   `SECURITE_NETWORK_POLICY.md`, `RENOVATE_AUTOMERGE_CI.md`, les README de
   `networkpolicies/`, `rbac/`, `stagingkub/`, `jenkins-docker/`, et les
   commentaires de plusieurs scripts/templates (`install-or-upgrade-grafana.sh`,
   `apply-networkpolicies.sh`, `jenkins-infra-upgrader-serviceaccount.yaml`,
   `postgresql-rhdemo-config.yaml`). Les mentions historiques (changelog
   `README.md` v1.1.1, phrases "remplace Promtail") ont été laissées
   intactes — ce sont des faits passés, pas de l'état courant.

---

## 3. Vérifications effectuées (pièges déjà rencontrés sur d'autres composants)

Le projet a déjà été touché par des plantages de scheduling sur ce cluster
mono-nœud (`podAntiAffinity` dur sur Loki et `cilium-operator`, cf. commits
`dc1ec86`/`02dcbbe`) et par des pièges RBAC (élévation de privilèges refusée
par l'admission Kubernetes sur `loki-clusterrole`, cf.
`STAGINGKUB_REBUILD_PIPELINE.md`). Les mêmes classes de problèmes ont donc été
vérifiées explicitement pour Alloy, **avant** toute application sur un
cluster réel :

- **Rendu Helm réel** : `helm template` exécuté contre le chart réel
  `grafana/alloy` 1.11.0 (dépôt `https://grafana.github.io/helm-charts`)
  avec `alloy-values.yaml` — succès, noms de ressources confirmés
  (`ClusterRole`/`ClusterRoleBinding`/`Service`/`DaemonSet` tous nommés
  `alloy`, label `app.kubernetes.io/name: alloy`).
- **Syntaxe de la config Alloy** : le bloc `alloy.configMap.content` extrait
  du rendu a été validé avec le binaire réel (`docker run grafana/alloy:v1.18.0
  validate <config>`) — exit code 0, aucune erreur.
- **RBAC** : `ClusterRole` rendu inspecté ligne à ligne — strictement en
  lecture (`get/list/watch` sur `pods`/`pods/log`/`namespaces`/`endpoints`/
  `endpointslices`/`ingresses`/`services`), aucun verbe d'écriture, aucun
  `create`. Légèrement plus large que celui de Promtail (ajoute
  `endpoints`/`endpointslices`/`ingresses`/`services`/`pods/log`) mais même
  niveau de risque (lecture de métadonnées uniquement).
- **CRD `podlogs.monitoring.grafana.com`** : présente dans le chart
  (activée par défaut via `crds.create: true`) mais **non utilisée** par la
  config statique retenue → désactivée (`crds.create: false`) pour ne pas
  élargir le RBAC CRD de `jenkins-infra-upgrader`, même logique que la
  désactivation de `sidecar.rules.enabled` sur Loki. Cette CRD sert au
  composant `loki.source.podlogs`, une alternative à
  `discovery.kubernetes`/`discovery.relabel` où les règles de scraping sont
  déclarées comme des ressources `PodLogs` (modèle proche des
  `PodMonitor`/`ServiceMonitor` de Prometheus Operator, déjà utilisés dans ce
  projet), utile pour laisser plusieurs équipes/namespaces gérer leurs
  propres règles sans toucher à `alloy-values.yaml`. Non pertinent ici
  (un seul namespace scrappé, config déjà centralisée dans Helm), et ce
  composant lit les logs via l'API Kubernetes plutôt que le hostPath — ce
  qui aurait élargi la surface réseau retenue. Marqué expérimental par la
  doc Alloy elle-même.
- **Anti-affinity / scheduling mono-nœud** : `templates/controllers/_pod.yaml`
  du chart inspecté + rendu final vérifié — `controller.affinity: {}` et
  `controller.topologySpreadConstraints: []` par défaut (tous deux vides), le
  bloc `affinity:` n'étant émis que `{{- with .Values.controller.affinity }}`
  (donc absent du manifeste tant que la valeur reste vide). Confirmé sur le
  rendu final : aucune clé `affinity`/`topologySpreadConstraints`/
  `nodeSelector`/`tolerations` dans le `DaemonSet`. De plus, Alloy est un
  `DaemonSet` par construction (`controller.type: daemonset`) — un seul pod
  par nœud, donc aucune contrainte d'anti-affinité inter-replicas possible
  même en théorie, à la différence de Loki (`StatefulSet`) et
  `cilium-operator` (`Deployment`).

Détail complet de ces deux derniers points dans
[`STAGINGKUB_REBUILD_PIPELINE.md`](STAGINGKUB_REBUILD_PIPELINE.md), section
« Cas particulier Alloy ».

---

## 4. Ce qui n'a PAS été fait

- **Aucune mutation du cluster réel** : pas de `helm uninstall promtail`, pas
  de `helm install alloy` exécuté contre `kind-rhdemo`. Le cluster va être
  entièrement recréé par l'utilisateur.
- **Dashboard Grafana inchangé** : les labels LogQL produits par Alloy sont
  volontairement identiques à ceux de Promtail (`namespace`/`app`/...), donc
  le dashboard "rhDemo - Logs Application" fonctionne sans modification.

---

## 5. Vérification après recréation du cluster

À faire par l'utilisateur une fois `init-stagingkub.sh` +
`install-observability.sh` exécutés :

```bash
# Pod Alloy en Running (DaemonSet, 1 pod car cluster mono-nœud)
kubectl get pods -n loki-stack -l app.kubernetes.io/name=alloy

# NetworkPolicies présentes, plus aucune trace de promtail-netpol
kubectl get networkpolicy -n loki-stack
kubectl get ciliumnetworkpolicies -n loki-stack

# Logs visibles dans Grafana Explore (datasource Loki)
# Requête LogQL identique à avant : {namespace="rhdemo-stagingkub", app="rhdemo-app"}
```

---

## 6. Fichiers de l'implémentation

| Fichier | Description |
|---------|-------------|
| `helm/observability/alloy-values.yaml` | Config Helm (remplace `promtail-values.yaml`) |
| `scripts/components/install-or-upgrade-alloy.sh` | Script idempotent (remplace `install-or-upgrade-promtail.sh`) |
| `scripts/install-observability.sh` | Orchestrateur, étape 3/4 renommée |
| `renovate.json` | `customManager` versions composants stagingkub |
| `rbac/jenkins-infra-upgrader-clusterrole.yaml` | `resourceNames` `promtail` → `alloy` |
| `networkpolicies/loki-stack-networkpolicies.yaml` | `alloy-netpol` + `allow-apiserver-alloy` |
| `Jenkinsfile-Stagingkub-Upgrade-Deploy`, `jenkins-casc.yaml` | Texte du paramètre `COMPONENT` |
| `docs/STAGINGKUB_REBUILD_PIPELINE.md` | Section "Cas particulier Alloy" (RBAC + scheduling détaillés) |
