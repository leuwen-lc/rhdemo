---
statut: actif
verifie_le: 2026-11-06
sources:
  - rhDemo/infra/stagingkub/helm/observability/
  - rhDemo/infra/stagingkub/scripts/install-observability.sh
  - rhDemo/infra/stagingkub/scripts/components/
  - rhDemo/infra/stagingkub/scripts/deploy-grafana-dashboard.sh
  - rhDemo/infra/stagingkub/networkpolicies/
  - rhDemo/infra/stagingkub/helm/rhdemo/templates/servicemonitor-rhdemo.yaml
  - rhDemo/infra/stagingkub/helm/rhdemo/templates/servicemonitor-postgresql.yaml
---

# Stack d'observabilité de stagingkub

Logs et métriques de l'environnement stagingkub (KinD), consultables dans Grafana. Ce document décrit l'architecture et le mode opératoire. Les versions des charts sont dans les scripts `infra/stagingkub/scripts/components/install-or-upgrade-*.sh` (variables `*_VERSION`, mises à jour par Renovate) et ne sont jamais recopiées ici.

## Composants

| Composant | Rôle | Namespace | Configuration |
| --- | --- | --- | --- |
| kube-prometheus-stack | Prometheus, Prometheus Operator, Alertmanager, node-exporter, kube-state-metrics | `monitoring` | [`prometheus-values.yaml`](../infra/stagingkub/helm/observability/prometheus-values.yaml) |
| Loki | Stockage et requête des logs, mode SingleBinary | `loki-stack` | [`loki-modern-values.yaml`](../infra/stagingkub/helm/observability/loki-modern-values.yaml) |
| Grafana Alloy | Collecte des logs des pods (remplace Promtail, en fin de vie depuis mars 2026) | `loki-stack` | [`alloy-values.yaml`](../infra/stagingkub/helm/observability/alloy-values.yaml) |
| Grafana | Visualisation, datasources Loki et Prometheus, dashboards | `loki-stack` | `grafana-values.yaml`, créé localement à partir de [`grafana-values.yaml.template`](../infra/stagingkub/helm/observability/grafana-values.yaml.template) |

Le chart Loki vient du fork communautaire (`grafana-community/helm-charts`) : depuis sa version 7, le dépôt Grafana Labs ne publie plus que la variante Grafana Enterprise Logs. Alloy et Grafana restent sur le dépôt Grafana Labs ; les deux dépôts partagent l'alias Helm `grafana`, d'où le `--force-update` des scripts.

## Ce qui est collecté

### Logs

Alloy tourne en DaemonSet et lit les fichiers de logs du nœud (`/var/log/pods/…`, monté en lecture seule), sans flux réseau vers les pods observés. Il ne retient que les pods du namespace `rhdemo-stagingkub` portant un label `app`, décode le format CRI, puis envoie à Loki par `loki-gateway`.

Labels disponibles dans Loki : `namespace`, `pod`, `container`, `app`, `component` et `job` (`<namespace>/<app>`). Les logs des composants système (Cilium, NGF, observabilité) ne sont pas collectés.

### Métriques

| Source | Collecte | Contenu |
| --- | --- | --- |
| Kubelet, cAdvisor, kube-state-metrics, node-exporter | ServiceMonitors de kube-prometheus-stack | CPU, mémoire, réseau, état et redémarrages des pods ; nœud |
| `rhdemo-app` | ServiceMonitor `rhdemo-app`, port `management` (9001), `/actuator/prometheus` | Micrometer : JVM, GC, threads, requêtes HTTP, HikariCP, événements de log |
| `postgresql-rhdemo` | ServiceMonitor `postgresql-rhdemo`, sidecar `postgres-exporter` (port 9187) | Connexions, verrous, tuples, cache, transactions longues, `pg_stat_statements` |

- L'actuator écoute sur un **port de management dédié**, distinct du port applicatif (9000) exposé par NGF : il n'est pas joignable depuis l'extérieur du cluster.
- L'exporter PostgreSQL n'utilise que ses collecteurs intégrés, dont trois activés explicitement : `stat_statements`, `long_running_transactions`, `process_idle`. PostgreSQL charge `pg_stat_statements` au démarrage (`shared_preload_libraries`) et l'extension est créée par le script d'initialisation de la base.
- Keycloak expose ses métriques (`keycloak.metricsEnabled: true`, port de management 9000), mais aucun ServiceMonitor ne les collecte. `postgresql-keycloak` n'a pas d'exporter. Pour ces deux composants, seules les métriques de pod sont disponibles.
- **Les deux ServiceMonitors du chart `rhdemo` sont désactivés par défaut** (`metrics.serviceMonitor.enabled: false` dans `values.yaml`). `Jenkinsfile-CD` les active quand la CRD `ServiceMonitor` est présente sur le cluster : l'application peut donc être déployée sans la stack d'observabilité. Après une première installation de la stack, il faut un nouveau déploiement de l'application pour que ses métriques soient collectées.
- Prometheus prend en compte tous les ServiceMonitors et PodMonitors du cluster, quel que soit leur namespace ou leurs labels (sélecteurs vides dans `prometheus-values.yaml`). Intervalle de collecte : 30 s.

## Installation et mise à jour

**Reconstruction complète.** [`install-observability.sh`](../infra/stagingkub/scripts/install-observability.sh) installe dans l'ordre kube-prometheus-stack, Loki, Alloy et Grafana, puis applique les NetworkPolicies de `monitoring` et `loki-stack` et ajoute l'entrée Grafana dans `/etc/hosts`. Prérequis : cluster stagingkub démarré, contexte `kind-rhdemo`, Helm 4, et le fichier `grafana-values.yaml` (voir [Sécurité](#sécurité)).

**Un script par composant.** Chaque étape appelle `scripts/components/install-or-upgrade-<composant>.sh`, idempotent (`helm upgrade --install --rollback-on-failure --wait`). Ces scripts sont aussi utilisés par le pipeline de mise à jour en place `RHDemo-Stagingkub-Upgrade-Deploy` : les deux chemins ne peuvent pas diverger. Particularités :

- **kube-prometheus-stack** : les CRDs du chart sont appliquées à part, en server-side apply, avant la release : `helm upgrade` ne met jamais à jour le dossier `crds/` d'un chart, et ces CRDs dépassent la taille maximale d'un apply côté client. Les webhooks d'admission de l'Operator sont désactivés.
- **Grafana** : le script crée en plus la `HTTPRoute` `grafana-route`, la ConfigMap de datasource Prometheus, redémarre Grafana puis redéploie les dashboards.
- **Mode validation** : avec `HELM_DRY_RUN=true`, les scripts ne font qu'un `--dry-run=server`, sans modifier le cluster. `Jenkinsfile-Renovate` s'en sert pour valider une montée de chart avant merge, et scanne avec Trivy les images rendues par le chart.

**Montées de version.** Renovate propose les montées de chart (variables `*_VERSION`) ; après merge, `RHDemo-Stagingkub-Upgrade-Deploy` applique le script du composant concerné avec le compte `jenkins-infra-upgrader`. Détails : [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md) et le README de stagingkub, section « Mise à jour en place ».

## Accès

| Interface | Accès |
| --- | --- |
| Grafana | `https://grafana-stagingkub.intra.leuwen-lc.fr`, compte `admin`, mot de passe de `grafana-values.yaml`. Exposé par la Gateway partagée de NGF (listener HTTPS `*.intra.leuwen-lc.fr`, certificat `shared-tls-cert`) |
| Prometheus | `kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090` |
| Alertmanager | `kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093` |
| Grafana sans DNS | `kubectl port-forward -n loki-stack svc/grafana 3000:80` |

Datasources Grafana : Loki (`uid: loki`, par défaut) et Prometheus (`uid: prometheus`).

## Dashboards

Quatre dashboards, versionnés dans `infra/stagingkub/` et chargés par le sidecar de Grafana depuis des ConfigMaps portant le label `grafana_dashboard: "1"` dans `loki-stack`.

| Fichier | Titre | Source | Contenu |
| --- | --- | --- | --- |
| `grafana-dashboard-rhdemo-logs.json` | rhDemo - Logs Application | Loki | Erreurs et avertissements, volume par application, logs de l'application, de Keycloak et de PostgreSQL, résultats des sauvegardes |
| `grafana-dashboard-rhdemo-metrics.json` | rhDemo - Metriques Pods | Prometheus | Statut, CPU, mémoire, réseau et redémarrages des quatre pods |
| `grafana-dashboard-rhdemo-springboot.json` | rhDemo - Metriques Spring Boot Actuator | Prometheus | Mémoire JVM, GC, threads, débit, latence et erreurs HTTP, pool HikariCP, uptime |
| `grafana-dashboard-rhdemo-postgresql.json` | rhDemo - Métriques PostgreSQL | Prometheus | Taille, connexions, verrous, requêtes les plus coûteuses (`pg_stat_statements`), cache, scans |

Après modification d'un fichier JSON : `./scripts/deploy-grafana-dashboard.sh [logs|metrics|springboot|postgresql|all]`. Le fichier contient le dashboard sous une clé `dashboard` (format de l'API Grafana) ; le script en extrait le contenu avec `jq`. Grafana n'a **pas de stockage persistant** : un dashboard créé ou modifié dans l'interface est perdu au redémarrage du pod s'il n'est pas exporté dans le fichier JSON.

## Requêtes utiles

LogQL, dans Grafana Explore avec la datasource Loki :

```logql
{namespace="rhdemo-stagingkub", app="rhdemo-app"} |= "ERROR"
sum by (app) (count_over_time({namespace="rhdemo-stagingkub"} [5m]))
{namespace="rhdemo-stagingkub", app="keycloak"} |= "WARN"
```

PromQL, avec la datasource Prometheus (le label `environment` est ajouté par les ServiceMonitors du chart) :

```promql
sum by (status) (rate(http_server_requests_seconds_count{environment="stagingkub"}[5m]))
histogram_quantile(0.95, sum by (le) (rate(http_server_requests_seconds_bucket{environment="stagingkub"}[5m])))
sum(jvm_memory_used_bytes{environment="stagingkub", area="heap"}) / sum(jvm_memory_max_bytes{environment="stagingkub", area="heap"})
topk(10, rate(pg_stat_statements_seconds_total[5m]))
```

Les dashboards fournis contiennent d'autres exemples : ouvrir un panneau en édition pour voir sa requête.

## Rétention et ressources

| Composant | Rétention | Stockage |
| --- | --- | --- |
| Prometheus | 7 jours, plafonnée à 5 Go | PVC 10 Gi |
| Loki | 168 h (`limits_config.retention_period`) | PVC 5 Gi |
| Alertmanager | — | PVC 2 Gi |
| Grafana | — | aucun (voir Dashboards) |

Requêtes et limites CPU/mémoire de chaque composant : fichiers de values. Loki tourne en un seul pod, avec deux caches memcached (chunks et résultats) ; les déploiements `read`, `write` et `backend` sont à zéro réplique. Son auto-monitoring, Loki Canary et les tests du chart sont désactivés.

Les règles d'alerte par défaut de kube-prometheus-stack sont créées, sauf celles des composants inaccessibles sur KinD (etcd, scheduler, controller-manager, SLO de l'API server). Aucun destinataire n'est configuré dans Alertmanager : les alertes sont visibles dans son interface mais ne sont envoyées nulle part.

## Sécurité

- **NetworkPolicies** : `default-deny-all` dans `monitoring` et `loki-stack`, puis flux autorisés un par un ([`monitoring-networkpolicies.yaml`](../infra/stagingkub/networkpolicies/monitoring-networkpolicies.yaml), [`loki-stack-networkpolicies.yaml`](../infra/stagingkub/networkpolicies/loki-stack-networkpolicies.yaml)), dont l'accès à l'API server par des `CiliumNetworkPolicy`. Côté application, les NetworkPolicies du chart `rhdemo` n'autorisent depuis `monitoring` que le port de management de l'application et le port 9187 de l'exporter. Les charts ne créent aucune NetworkPolicy : `install-observability.sh` les applique en dernier, une fois les pods prêts. Détail : [SECURITE_NETWORK_POLICY.md](SECURITE_NETWORK_POLICY.md).
- **RBAC** : Alloy n'a que des droits de lecture (découverte des pods), sa CRD `podlogs` n'est pas installée. Le sidecar de dashboards de Grafana est limité au namespace `loki-stack` (`rbac.namespaced: true`, `searchNamespace: loki-stack`) : pas de lecture des secrets du cluster entier. Les droits de `jenkins-infra-upgrader` : [SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md](SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md).
- **Grafana** : accès anonyme et inscription désactivés, télémétrie et vérification de mises à jour coupées. Le mot de passe administrateur est dans `grafana-values.yaml`, **fichier local ignoré par Git** et non chiffré par SOPS : copier le modèle, renseigner `adminPassword` (par exemple `openssl rand -base64 32`), puis le conserver dans un gestionnaire de mots de passe. Le script de Grafana refuse de s'exécuter si le mot de passe est vide.
- **Loki** est sans authentification (`auth_enabled: false`) : seules les NetworkPolicies limitent qui peut lui écrire ou le lire.

## Dépannage

| Symptôme | Vérification |
| --- | --- |
| Aucun log dans Grafana | `kubectl logs -n loki-stack -l app.kubernetes.io/name=alloy` ; le pod observé porte-t-il un label `app` et est-il dans `rhdemo-stagingkub` ? |
| Métriques de l'application absentes | `kubectl get servicemonitor -n monitoring` : sans `rhdemo-app`, redéployer l'application (activation par `Jenkinsfile-CD`) ; puis cible « DOWN » dans Prometheus, page `/targets` |
| Cible en erreur de connexion | NetworkPolicy du chart `rhdemo` (port 9001 ou 9187 depuis `monitoring`) |
| Grafana inaccessible | `kubectl get httproute -n loki-stack grafana-route` et entrée `/etc/hosts` ; à défaut, port-forward |
| Datasource en erreur | Depuis le pod Grafana, joindre `loki-gateway` et `prometheus-kube-prometheus-prometheus.monitoring.svc:9090` ; vérifier les NetworkPolicies de `loki-stack` |
| Volume Loki plein | `kubectl exec -n loki-stack loki-0 -- df -h /var/loki` ; voir aussi le point ouvert sur la rétention |

## Points ouverts

- **Rétention de Loki à vérifier** : Loki n'applique `retention_period` que si le compactor a `retention_enabled: true`, absent des values du projet. Contrôler la configuration rendue (`kubectl get configmap -n loki-stack loki -o yaml | grep retention`) ; sinon les logs ne sont jamais supprimés et le volume de 5 Gi finira par se remplir.
- **Datasource Prometheus déclarée deux fois**, dans `grafana-values.yaml` et dans la ConfigMap créée par `install-or-upgrade-grafana.sh`.
- **`helm/observability/grafana-gateway.yaml` n'est plus utilisé** : Grafana passe par la Gateway partagée (`grafana-route`), et aucun script n'applique ce fichier.
- **Aucune alerte n'est acheminée** (Alertmanager sans destinataire).

## Références

- [Prometheus Operator](https://prometheus-operator.dev/), [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
- [Loki](https://grafana.com/docs/loki/latest/), chart du fork communautaire : [grafana-community/helm-charts](https://github.com/grafana-community/helm-charts)
- [Grafana Alloy](https://grafana.com/docs/alloy/latest/)
- [LogQL](https://grafana.com/docs/loki/latest/query/), [PromQL](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [postgres_exporter](https://github.com/prometheus-community/postgres_exporter)
- Projet : README de `infra/stagingkub`, [SECURITE_NETWORK_POLICY.md](SECURITE_NETWORK_POLICY.md), [POSTGRESQL_BACKUP_CRONJOBS.md](POSTGRESQL_BACKUP_CRONJOBS.md)
