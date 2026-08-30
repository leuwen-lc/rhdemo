# Plan de migration Helm 3 → Helm 4

**Statut** : 🚧 En cours — phases 1 à 4 et 6 faites sur la branche
`migration-helm-4` (code + audit statique + dry-run cluster validés avec un
binaire Helm 4.2.4). **Reste avant merge** : phase 5 (validation end-to-end :
rebuild agent Jenkins, exécution réelle des scripts composants, recréation
complète de cluster).
**Rédigé le** : 30/08/2026 · **Dernière mise à jour** : 30/08/2026
**Version cible** : Helm **4.2.4** (dernière release stable au 30/08/2026).
**Remplace la section « 2. Helm 4 » de** [`MIGRATION_KUB1.36_HELM4_EN_ATTENTE.md`](MIGRATION_KUB1.36_HELM4_EN_ATTENTE.md)
(l'analyse de risque qui a mené au report reste valable ; ce document décrit
comment exécuter la migration).

Ce plan est **indépendant** de la montée de version Kubernetes 1.36 (bloquée
par Cilium) : Helm 4 se migre sur le cluster stagingkub actuel (K8s 1.35),
sans recréation obligatoire.

---

## 1. État des lieux

| Élément | Valeur actuelle | Source |
|---------|-----------------|--------|
| CLI Helm poste dev | `v3.21.3` — **à passer en 4.2.4** (non fait par la branche : binaire système) | `helm version` |
| CLI Helm agent Jenkins | `HELM_VERSION=4.2.4` (était `3.21.4`) | `infra/jenkins-docker/Dockerfile.agent` (~l.102) |
| Suivi de version | Renovate `customManager` regex, `datasource=github-releases depName=helm/helm`, **sans contrainte de version** | `renovate.json` (bloc « SOPS, Helm et Cosign ») |
| Chart applicatif | `apiVersion: v2`, `type: application`, **pas de sous-charts**, pas de `dependencies:`, pas de dossier `crds/`, pas de hooks, pas de `lookup`/`Capabilities` dans les templates | `infra/stagingkub/helm/rhdemo/` |

**Fenêtre de sérénité** : Helm 3 n'est pas EOL (dernière feature release
prévue ~09/09/2026, patchs de sécurité jusqu'à ~février 2027). Aucune urgence,
la migration se planifie hors période de release applicative.

**Garde-fou Renovate** : un bump `helm/helm` 3.x → 4.x est un changement
**major**, donc bloqué derrière `dependencyDashboardApproval: true` (approbation
manuelle via le Dependency Dashboard) — pas d'automerge possible.

> **Décision d'exécution** : le garde-fou temporaire `allowedVersions: "<4"`
> (phase 0 du plan initial) n'a **pas** été posé. La migration entière est
> faite dans une seule branche/PR (`migration-helm-4`) qui bump elle-même le
> binaire ; ajouter puis retirer la contrainte dans le même changeset n'aurait
> aucun effet net, et `renovate.json` n'est lu que depuis `master` (cf.
> `CLAUDE.md`). Le blocage `major` + `dependencyDashboardApproval` suffit à
> éviter un bump concurrent pendant la fenêtre.

---

## 2. Où Helm est utilisé dans le dépôt

### 2.1 Déploiement applicatif (CD)
- `Jenkinsfile-CD` (~l.648) : `helm upgrade --install rhdemo … --wait --timeout 15m --debug`.
  **Aucun flag renommé en Helm 4** → compatible tel quel.

### 2.2 Scripts composants infra (mise à jour en place)
`infra/stagingkub/scripts/components/` — chacun fait `helm repo add/update`
puis `helm upgrade --install … ${HELM_MODE_ARGS}` où `HELM_MODE_ARGS` vaut
`--atomic --wait --timeout <N>` en mode réel :

| Script | Ligne `--atomic` |
|--------|------------------|
| `install-or-upgrade-cilium.sh` | ~137 |
| `install-or-upgrade-ngf.sh` | ~48 |
| `install-or-upgrade-kube-prometheus-stack.sh` | ~50 |
| `install-or-upgrade-loki.sh` | ~45 |
| `install-or-upgrade-alloy.sh` | ~42 (+ commentaire d'en-tête ~l.13) |
| `install-or-upgrade-grafana.sh` | ~45 |

Mode dry-run (`HELM_DRY_RUN=true`, utilisé par `Jenkinsfile-Renovate` et
`Jenkinsfile-Stagingkub-Upgrade-Deploy`) : `HELM_MODE_ARGS="--dry-run=server"`
→ compatible Helm 4.

### 2.3 Autres scripts
- `rbac-preflight-check.sh` : `helm template … --namespace` + `helm show crds` → compatibles.
- `test-deploy-helm.sh` (~l.60, ~l.78) : `helm upgrade --install … --dry-run --debug`.
  `--dry-run` nu = `--dry-run=client` (comportement inchangé depuis Helm 3.13) → OK, à expliciter.
- `migrate-postgresql-rhdemo.sh` / `migrate-postgresql-keycloak.sh` : `helm upgrade --install … --wait --timeout 5m`, **pas de `--atomic`** → compatibles.
- `helm-unlock.sh` : `helm status` + sélection des secrets par label `owner=helm,name=<release>`. Le backend de stockage par défaut reste `sh.helm.release.v1` en Helm 4 → **inchangé**.
- `validate-stagingkub.sh` : `helm list`, `check_command helm` → OK.
- `install-observability.sh`, `init-stagingkub.sh` : délèguent aux scripts composants ou n'appellent pas Helm directement (annotations `meta.helm.sh/release-*` posées à la main → format inchangé).

### 2.4 Documentation / commentaires à réaligner
- `infra/stagingkub/scripts/README-helm-unlock.md` (~l.93-95, exemples `--atomic`).
- `infra/jenkins-docker/jenkins-casc.yaml` (~l.507, commentaire `--atomic`).
- `Jenkinsfile-Stagingkub-Upgrade-Deploy` (~l.24, ~l.225, ~l.231, mentions `--atomic`).
- `docs/STAGINGKUB_REBUILD_PIPELINE.md` (~l.46, description du passage à `--atomic`).
- `infra/stagingkub/scripts/components/install-or-upgrade-cilium.sh` (~l.124, commentaire d'en-tête).

---

## 3. Changements Helm 4 pertinents pour ce projet

Référence : guide de migration officiel Helm 3 → 4. Points classés par impact.

### 3.1 `--atomic` → `--rollback-on-failure` (impact : renommage mécanique)
Utilisé dans les 6 scripts composants (§2.2) + la doc (§2.4). L'ancien flag
`--atomic` reste **accepté avec un avertissement de dépréciation** en Helm 4 :
pas de casse immédiate, mais on aligne le code dans la même passe.

⚠️ `--rollback-on-failure` **n'existe pas en Helm 3**. Le changement de flag et
le bump du binaire doivent donc être livrés **ensemble** (une seule PR, cf.
phase 3+4), jamais en avance.

### 3.2 Server-Side Apply par défaut pour `helm install` (impact : risque n°1)
En Helm 4, le **server-side apply (SSA) devient la stratégie par défaut pour
les nouvelles installations** (`helm install`, y compris un `helm upgrade
--install` sur une release **absente**). Un `helm upgrade` d'une release
**existante** conserve la stratégie de la release.

Conséquences pour ce projet :
- **Déploiement CD courant** (`Jenkinsfile-CD` sur stagingkub où `rhdemo` est
  déjà installé) = `upgrade`, pas d'SSA par défaut → risque faible.
- **Recréation complète du cluster** (`init-stagingkub.sh` +
  `install-observability.sh`) = chaque composant est une **install neuve** →
  SSA activé, chemin de code jamais éprouvé avec ces charts. Risques : field
  managers, conflits de champs, ownership des objets.
- `kube-prometheus-stack` applique déjà ses CRDs en `kubectl apply
  --server-side` explicite → **déjà couvert sur ce point précis**. Les 5 autres
  charts (cilium, ngf, loki, alloy, grafana, + `rhdemo`) changeraient de
  stratégie d'apply à l'install.
- Échappatoire si un composant régresse : forcer le client-side apply à
  l'install (option `--client-side-apply` ou équivalent, **à confirmer sur la
  version 4.x cible**).

### 3.3 Sans impact pour ce projet (vérifié)
- `--force` → `--force-replace` : `--force` non utilisé.
- `helm registry login` domaine seul (plus d'URL complète) : le pull OCI de NGF
  (`oci://ghcr.io/nginx/charts/nginx-gateway-fabric`) est **anonyme**.
- Post-renderers déplacés en plugins : non utilisés.
- `apiVersion: v2` du `Chart.yaml` : **toujours valide** en Helm 4 (il n'existe
  pas de `v3`).
- Fonctions de template de `_helpers.tpl` (`trunc`, `trimSuffix`, `replace`,
  `contains`, `default`, `printf`) : standard, conservées.
- `lookup` / `.Capabilities.APIVersions` : **aucune occurrence** dans les
  templates → pas de comportement dépendant du cluster à re-valider.
- Backend de stockage des releases : reste `sh.helm.release.v1` (Secret) → les
  scripts `helm-unlock.sh` et les annotations `meta.helm.sh/*` restent valides.

### 3.4 Points vérifiés sur Helm 4.2.4 (phases 1-2, 30/08/2026)
- **Compat client Helm 4 ↔ Kubernetes** : `helm4 version` →
  `KubeClientVersion: v1.36`. Politique n-3 ⇒ compat K8s 1.33→1.36. Cluster
  stagingkub en **K8s 1.35** → dans la fenêtre. ✅
- **Lecture du storage Helm 3** : `helm4 list -n rhdemo-stagingkub` lit
  directement les secrets `sh.helm.release.v1.rhdemo.*` écrits par Helm 3
  (release `rhdemo` rev. 66 vue à l'identique par les deux binaires). Aucune
  migration de storage. ✅
- `--wait`, `--timeout`, `--create-namespace`, `--debug`, `--set`,
  `--dry-run=server`, `helm repo add --force-update`, `helm show crds`,
  `helm template` : tous conservés, testés sans warning. ✅
- Reste à lever en phase 5 : nom exact du flag de contournement du SSA à
  l'installation neuve (§3.2) — non bloquant pour un `upgrade` de release
  existante.

---

## 4. Stratégie retenue

**Cycle de validation dédié, non bundlé** avec un autre changement d'infra
(recommandation reprise de `MIGRATION_KUB1.36_HELM4_EN_ATTENTE.md`). Livraison
en **une branche/PR unique** (`migration-helm-4`) qui bump le binaire *et*
renomme les flags.

Ordre : audit statique ✅ → dry-run cluster ✅ → code+binaire ✅ →
validation E2E ⬜ (mise à jour en place, puis CD, puis recréation complète) → doc ✅.

> **État réel** : phases 1 à 4 et 6 faites. La phase 1 (template diff) et la
> phase 2 (dry-run serveur `rhdemo` sur `kind-rhdemo`) ont été exécutées avec un
> binaire Helm 4.2.4 — résultats dans §5. La **phase 5 reste à faire avant
> merge** : elle nécessite l'agent Jenkins reconstruit (Helm 4) et une fenêtre
> de mutation sur stagingkub.

---

## 5. Phases d'exécution

Légende : ✅ fait · ⬜ à faire · ➖ non retenue.

### Phase 0 — Garde-fous ➖ non retenue
- ➖ `allowedVersions: "<4"` non posé (cf. « Décision d'exécution » §1 : migration
      en une seule branche, `renovate.json` lu depuis `master` uniquement).
- ✅ Rollback outil : `helm` 3.x reste installable via l'URL versionnée
      `https://get.helm.sh/helm-v3.21.4-linux-amd64.tar.gz` (aucune action
      requise, le binaire système du poste dev est encore en 3.21.3).

### Phase 1 — Audit statique du chart maison ✅ fait (30/08/2026, binaire helm 4.2.4)
- [x] Binaire Helm 4.2.4 installé en parallèle, `helm` système inchangé (3.21.3).
- [x] `helm4 lint` du chart `rhdemo` → seule l'erreur pré-existante
      `namespace.yaml.disabled` (identique sous Helm 3, hors périmètre).
- [x] `helm template rhdemo … --namespace rhdemo-stagingkub` Helm 3 vs Helm 4 →
      **seul diff : une ligne vide ajoutée par Helm 4 avant chaque `---`**
      (cosmétique). Mêmes ressources, mêmes champs, mêmes valeurs.
- [x] `helm4 template` des charts observability (alloy, grafana, loki) avec
      leurs `--values` réels → rendu sans erreur.

### Phase 2 — Dry-run côté cluster, sans mutation ✅ fait (30/08/2026, cluster `kind-rhdemo`)
- [x] `helm4 upgrade --install rhdemo … --dry-run=server` (mêmes `--set` que
      `Jenkinsfile-CD`) → exit 0, aucun warning. Diff vs Helm 3 : uniquement le
      timestamp `LAST DEPLOYED` et la nouvelle ligne d'info `DESCRIPTION: Dry run
      complete`. **Manifestes rendus identiques.**
- [ ] Pour chaque script composant : `HELM_DRY_RUN=true` (→ `--dry-run=server`)
      sous Helm 4 sur l'agent Jenkins reconstruit (à faire en phase 5, nécessite
      les credentials `jenkins-infra-upgrader`).
- [ ] Rejouer la **boucle de validation pré-merge** de `Jenkinsfile-Renovate`
      avec l'agent Helm 4 sur une branche de test (phase 5).

### Phase 3 — Bascule des flags dans le code ✅ fait (commit sur `migration-helm-4`)
- [x] `--atomic` → `--rollback-on-failure` dans `HELM_MODE_ARGS` des 6 scripts :
      `install-or-upgrade-{cilium,ngf,kube-prometheus-stack,loki,alloy,grafana}.sh`.
- [x] `test-deploy-helm.sh` : `--dry-run` → `--dry-run=client` (explicitation).
- [x] Réaligner la doc / les commentaires : `README-helm-unlock.md`,
      `jenkins-casc.yaml`, `Jenkinsfile-Stagingkub-Upgrade-Deploy`,
      `Jenkinsfile-Renovate`, `STAGINGKUB_REBUILD_PIPELINE.md`,
      `infra/stagingkub/README.md`, `infra/stagingkub/rbac/README.md`,
      `helm/observability/{loki-modern,prometheus}-values.yaml`,
      en-têtes `install-or-upgrade-alloy.sh` / `-cilium.sh`,
      `install-observability.sh`.
- [x] `Jenkinsfile-CD` et `migrate-postgresql-*.sh` laissés intacts (aucun flag concerné).

### Phase 4 — Bump du binaire
- [x] `infra/jenkins-docker/Dockerfile.agent` : `ENV HELM_VERSION=4.2.4`.
- [x] `docs/JENKINS_AGENTS_EPHEMERES.md`, `README.md` : versions Helm citées mises à jour.
- [ ] **Rebuild + push de l'image agent Jenkins**, mise à jour de la référence utilisée (opération infra, hors branche).
- [ ] **Poste dev local** : passer `helm` (3.21.3) en 4.2.4 avant de rejouer les scripts localement.

### Phase 5 — Validation end-to-end 🚧 en cours (sur stagingkub, avec l'agent Helm 4)

> **Bug trouvé et corrigé pendant la validation (30/08/2026)** : sur une
> reconstruction depuis un cluster vierge, `rbac_preflight_check` échouait
> (`namespaces "cilium-system"/"cilium-secrets" not found`) — le
> `kubectl apply --dry-run=server` des Role/RoleBinding namespacés du chart
> Cilium tourne avant que le `helm install --create-namespace` n'ait créé le
> namespace. Corrigé : `rbac-preflight-check.sh` tolère désormais les erreurs
> « namespace not found » (skip doux, l'anti-élévation RBAC native s'applique
> toujours au apply réel) et ne fait échouer que sur les autres erreurs ;
> `install-or-upgrade-cilium.sh` / `-ngf.sh` créent leur namespace avant le
> préflight, comme le font déjà loki/alloy/grafana/kube-prometheus-stack.

> **Bundlé avec la montée Kubernetes 1.35 → 1.36.4** (cf.
> [`MIGRATION_KUB1.36_HELM4_EN_ATTENTE.md`](MIGRATION_KUB1.36_HELM4_EN_ATTENTE.md)) :
> la reconstruction de cluster ci-dessous se fait directement sur
> `kindest/node:v1.36.4` avec le CLI `kind` 0.33+ (K8s 1.37, aussi publié avec
> kind 0.33, est écarté : hors matrice Cilium 1.20). **Séquencer** : créer le
> cluster 1.36 + installer Cilium 1.20.1 **d'abord**, confirmer le nœud `Ready`
> (pas de filet : `disableDefaultCNI` + `kubeProxyMode: none`), **puis** dérouler
> le reste — une panne reste ainsi attribuable à l'un ou l'autre changement.

- [ ] **Mise à jour en place, composant par composant** via
      `Jenkinsfile-Stagingkub-Upgrade-Deploy`, en commençant par **Cilium** (le
      plus risqué : `disableDefaultCNI: true` + `kubeProxyMode: none`, aucun
      filet réseau). Vérifier que le rollback `--rollback-on-failure` se
      déclenche sur un échec provoqué volontairement.
- [ ] Puis ngf, kube-prometheus-stack, loki, alloy, grafana — un par un,
      contrôle de l'état après chacun.
- [ ] **`Jenkinsfile-CD` complet** : `helm upgrade --install rhdemo` sur la
      release existante (= `upgrade`, pas d'SSA par défaut) → smoke tests,
      HTTPRoute, app accessible.
- [ ] **Recréation complète du cluster** sur une fenêtre dédiée, **sur
      `kindest/node:v1.36.4`** (kind CLI ≥ 0.33) — c'est aussi LE scénario où
      l'SSA-par-défaut de `helm install` s'active : `init-stagingkub.sh` +
      `install-observability.sh`. Valider :
  - [ ] `kind create cluster` OK avec le CLI 0.33+ (config `v1alpha4` inchangée).
  - [ ] Cilium 1.20.1 s'installe, le nœud passe `Ready` sur l'API 1.36.
  - [ ] NGF + CRDs Gateway API opérationnels.
  - [ ] kube-prometheus-stack (CRDs déjà en SSA explicite) OK.
  - [ ] loki, alloy, grafana OK.
  - [ ] Chart `rhdemo` : install initiale OK, pods `Ready`, HTTPRoute résout,
        app + Keycloak accessibles.
- [ ] Comparer le comportement observé au cluster de référence ; si un composant
      régresse à cause du SSA, tester le contournement client-side apply (§3.2)
      et le documenter ici.

### Phase 6 — Documentation & clôture ✅ fait (reste : décocher au merge effectif)
- [x] `MIGRATION_KUB1.36_HELM4_EN_ATTENTE.md` : section Helm 4 marquée réalisée, renvoi vers ce plan.
- [x] Versions Helm citées mises à jour : `README.md`, `docs/JENKINS_AGENTS_EPHEMERES.md`,
      `docs/STAGINGKUB_REBUILD_PIPELINE.md`, `infra/stagingkub/README.md`.
      `docs/PIPELINES_CI_CD.md` / `INVENTAIRE_COMPOSANTS_OPEN_SOURCE.md` /
      `CICD_JENKINS_VS_FORGEJO_ACTIONS.md` / `CLAUDE.md` : aucune version Helm
      chiffrée à corriger (vérifié par `grep`).
- [x] Entrée CHANGELOG `### Version 1.1.10` dans `/README.md`.
- [ ] Au merge : basculer le **Statut** de ce document en ✅ et retirer la mention « en cours ».

---

## 6. Récapitulatif des fichiers modifiés (branche `migration-helm-4`)

| Fichier | Modification | Phase |
|---------|--------------|-------|
| `infra/jenkins-docker/Dockerfile.agent` | `HELM_VERSION` 3.21.4 → **4.2.4** | 4 |
| `infra/stagingkub/scripts/components/install-or-upgrade-cilium.sh` | `--atomic` → `--rollback-on-failure` (arg + commentaire) | 3 |
| `…/install-or-upgrade-ngf.sh` | `--atomic` → `--rollback-on-failure` | 3 |
| `…/install-or-upgrade-kube-prometheus-stack.sh` | `--atomic` → `--rollback-on-failure` | 3 |
| `…/install-or-upgrade-loki.sh` | `--atomic` → `--rollback-on-failure` | 3 |
| `…/install-or-upgrade-alloy.sh` | `--atomic` → `--rollback-on-failure` (arg + commentaire) | 3 |
| `…/install-or-upgrade-grafana.sh` | `--atomic` → `--rollback-on-failure` | 3 |
| `infra/stagingkub/scripts/test-deploy-helm.sh` | `--dry-run` → `--dry-run=client` | 3 |
| `infra/stagingkub/scripts/install-observability.sh` | prérequis « Helm 3 » → « Helm 4 » | 3 |
| `infra/stagingkub/scripts/README-helm-unlock.md` | exemple `--atomic` → `--rollback-on-failure` | 3 |
| `infra/jenkins-docker/jenkins-casc.yaml` | commentaire `--atomic` | 3 |
| `Jenkinsfile-Stagingkub-Upgrade-Deploy` | commentaires + message d'échec | 3 |
| `Jenkinsfile-Renovate` | commentaire `--atomic` | 3 |
| `infra/stagingkub/helm/observability/loki-modern-values.yaml` | commentaire `--atomic` | 3 |
| `infra/stagingkub/helm/observability/prometheus-values.yaml` | commentaire `--atomic` | 3 |
| `infra/stagingkub/README.md` | description script composant | 3 |
| `infra/stagingkub/rbac/README.md` | prose `rollback --atomic` | 3 |
| `docs/STAGINGKUB_REBUILD_PIPELINE.md` | 6 occurrences `--atomic` + note rename l.46 | 3 / 6 |
| `docs/MIGRATION_KUB1.36_HELM4_EN_ATTENTE.md` | statut Helm 4 → réalisé | 6 |
| `docs/JENKINS_AGENTS_EPHEMERES.md` | `Helm 3.20.0` → `Helm 4.2.4` | 6 |
| `README.md` (racine) | prérequis CD `Helm 4.2+` + CHANGELOG `### Version 1.1.10` | 6 |

### Fichiers explicitement NON modifiés
`renovate.json` (garde-fou `allowedVersions` non retenu, cf. §1) ·
`Jenkinsfile-CD` · `Jenkinsfile-CI` (aucun Helm) ·
`infra/stagingkub/helm/rhdemo/Chart.yaml` (`apiVersion: v2` reste valide) ·
`infra/stagingkub/helm/rhdemo/templates/_helpers.tpl` et les autres templates
(fonctions standard, pas de `lookup`/`Capabilities`/hooks) ·
`helm-unlock.sh` (backend `sh.helm.release.v1` inchangé) ·
`migrate-postgresql-rhdemo.sh` / `migrate-postgresql-keycloak.sh`
(`helm upgrade --install` sans flag déprécié).

---

## 7. Risques & mitigations

| Risque | Gravité | Mitigation |
|--------|---------|------------|
| SSA par défaut sur recréation complète casse un composant | Élevée | Phase 5 : test de recréation dédié, hors CD courant ; contournement client-side apply prêt (§3.2) |
| Cilium ne s'initialise pas sous Helm 4 (aucun filet réseau, nœud `NotReady`) | Élevée | Tester Cilium **en premier** en phase 5 ; rollback = recréation KinD depuis `kind-data` |
| `--rollback-on-failure` livré avant le binaire 4.x (scripts cassés sous Helm 3) | Moyenne | Flags + `HELM_VERSION` dans **la même branche** `migration-helm-4` ; ne pas merger avant que l'agent Jenkins tourne en Helm 4. **Dev local** : `helm` reste en 3.21.3 → les scripts échoueront en local tant que le poste n'est pas passé en 4.2.4 (phase 4) |
| Bump Renovate `helm/helm` non maîtrisé pendant la fenêtre | Faible | Blocage `major` derrière `dependencyDashboardApproval` (garde-fou `allowedVersions` non retenu, cf. §1) |
| Incompatibilité client Helm 4.2.4 ↔ K8s 1.35 | Faible | **Levé** : `helm4 version` → client K8s v1.36, politique n-3 couvre 1.33→1.36 (§3.4) |

---

## 8. Reste à faire avant merge (phase 5)

La branche `migration-helm-4` porte tout le code + la validation statique et
dry-run. Avant de merger, il faut une **fenêtre de mutation sur stagingkub** :

1. Reconstruire + pousser l'image agent Jenkins (Helm 4.2.4), pointer la
   config dessus.
2. Rejouer `RHDemo-Stagingkub-Upgrade-Deploy` composant par composant (Cilium
   d'abord), avec test d'échec volontaire pour valider `--rollback-on-failure`.
3. Rejouer `RHDemo-CD` complet (upgrade `rhdemo` en place) + smoke tests.
4. Test de **recréation complète** (`init-stagingkub.sh` +
   `install-observability.sh`) sur machine dédiée — seul scénario où le
   server-side apply par défaut de `helm install` s'active (§3.2).
5. Basculer le **Statut** de ce document en ✅ et passer la version 1.1.10 en
   « publiée » dans le CHANGELOG.
