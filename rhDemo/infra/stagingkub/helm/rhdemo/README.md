# Chart Helm `rhdemo`

Chart qui déploie l'application RHDemo et ses dépendances (Keycloak, deux PostgreSQL) dans le namespace `rhdemo-stagingkub` du cluster KinD stagingkub.

Ce document décrit **ce que fait le chart** et **où regarder** : les valeurs exactes (images, ressources, ports, hôtes) se lisent dans [`values.yaml`](values.yaml) et dans les templates, jamais ici.

---

## Ce que le chart ne fait pas

Le chart suppose un cluster préparé par [`init-stagingkub.sh`](../../scripts/init-stagingkub.sh), qui crée hors du chart :

| Élément | Créé par |
| --- | --- |
| Namespace `rhdemo-stagingkub` | `init-stagingkub.sh` (le template `namespace.yaml.disabled` n'est plus rendu ; `Jenkinsfile-CD` passe en plus `--create-namespace`) |
| NGINX Gateway Fabric et le Gateway partagé `shared-gateway` (namespace `nginx-gateway`) | `init-stagingkub.sh`, [`shared-gateway.yaml`](../../shared-gateway.yaml) |
| Certificat TLS `shared-tls-cert` | `init-stagingkub.sh` ([CERTIFICATS_WEB.md](../../../../docs/CERTIFICATS_WEB.md)) |
| Secrets applicatifs (`rhdemo-db-secret`, `keycloak-db-secret`, `keycloak-admin-secret`, `rhdemo-app-secrets`) | External Secrets Operator, depuis OpenBao ([`external-secrets/`](../../external-secrets/), [OPENBAO.md](../../../../docs/OPENBAO.md)) |
| Comptes RBAC de Jenkins | [`rbac/`](../../rbac/) |
| Prometheus Operator (CRD `ServiceMonitor`) | `install-observability.sh` |

Les templates ne font que **référencer** ces Secrets par leur nom (`passwordSecret.name`, `secretsFile.secretName` dans `values.yaml`) : aucun mot de passe ne transite par Helm ni par Jenkins.

---

## Contenu du chart

```
helm/rhdemo/
├── Chart.yaml
├── values.yaml        # source unique des valeurs, dont global.images (images tierces)
└── templates/
    ├── _helpers.tpl, NOTES.txt
    ├── postgresql-rhdemo-*, postgresql-keycloak-*, postgresql-persistentvolumes.yaml
    ├── postgresql-backup-cronjob.yaml
    ├── keycloak-*, rhdemo-app-*
    ├── httproute.yaml, ratelimitpolicy.yaml, proxysettingspolicy.yaml
    ├── networkpolicy-*.yaml
    └── servicemonitor-*.yaml
```

| Templates | Ressources | Rôle |
| --- | --- | --- |
| `postgresql-rhdemo-statefulset.yaml`, `-service.yaml` | StatefulSet, Service | Base de l'application, avec un sidecar postgres-exporter |
| `postgresql-rhdemo-configmap.yaml` | ConfigMap `postgresql-rhdemo-init` | Scripts d'initialisation de la base |
| `postgresql-rhdemo-config.yaml` | ConfigMap | Configuration PostgreSQL (journalisation), si `logging.enabled` |
| `postgresql-keycloak-statefulset.yaml`, `-service.yaml` | StatefulSet, Service | Base de Keycloak |
| `postgresql-persistentvolumes.yaml` | 2 PersistentVolumes | `hostPath` sur `/mnt/data/postgresql-*`, monté par les `extraMounts` de [`kind-config.yaml`](../../kind-config.yaml) : les données survivent à la recréation du cluster |
| `postgresql-backup-cronjob.yaml` | 2 CronJobs | `pg_dump` quotidien des deux bases, rétention `postgresqlBackup.retentionDays` ([POSTGRESQL_BACKUP_CRONJOBS.md](../../../../docs/POSTGRESQL_BACKUP_CRONJOBS.md)) |
| `keycloak-deployment.yaml`, `-service.yaml` | Deployment, Service | Keycloak en mode `start` (production), stratégie `Recreate` et cache local (voir les commentaires de `values.yaml`) |
| `rhdemo-app-deployment.yaml`, `-service.yaml` | Deployment, Service | Application Spring Boot : port applicatif et port management (actuator) séparés, secrets montés depuis `rhdemo-app-secrets` |
| `httproute.yaml` | 2 HTTPRoutes | Exposition HTTPS de l'application et de Keycloak, attachées au `shared-gateway` ; en-têtes de sécurité ajoutés par `ResponseHeaderModifier` |
| `ratelimitpolicy.yaml` | RateLimitPolicy (NGF) | Limite de débit par adresse IP, une par route |
| `proxysettingspolicy.yaml` | ProxySettingsPolicy (NGF) | Buffers proxy agrandis pour les cookies OAuth2 de Keycloak |
| `networkpolicy-*.yaml` | NetworkPolicies | Default deny, puis chaque flux autorisé explicitement ([SECURITE_NETWORK_POLICY.md](../../../../docs/SECURITE_NETWORK_POLICY.md)) |
| `servicemonitor-*.yaml` | ServiceMonitors | Scraping Prometheus de l'application et de postgres-exporter, si activés |

Les images tierces sont toutes déclarées dans `global.images`, épinglées par digest et mises à jour par Renovate ([IMAGE_VERSIONS_MANAGEMENT.md](../../../../docs/IMAGE_VERSIONS_MANAGEMENT.md)). L'image de l'application (`rhdemo.image`) est fournie au déploiement.

Chaque composant a un interrupteur `enabled` dans `values.yaml` ; les NetworkPolicies se coupent ensemble par `networkPolicies.enabled` (à ne faire que pour un diagnostic).

---

## Exposition

```
navigateur ──HTTPS──▶ NodePort ─▶ shared-gateway (nginx-gateway, TLS shared-tls-cert)
                                      ├─ HTTPRoute rhdemo-route   ─▶ rhdemo-app (port applicatif ; /actuator/health ─▶ port management)
                                      └─ HTTPRoute keycloak-route ─▶ keycloak
```

La terminaison TLS est faite par le Gateway partagé ; à l'intérieur du cluster, les flux sont en HTTP. Le chart ne crée ni Gateway ni Ingress. Hôtes, règles et en-têtes : section `gateway` de `values.yaml`.

---

## Déploiement

**Voie normale : `RHDemo-CD`** ([PIPELINES_CI_CD.md](../../../../docs/PIPELINES_CI_CD.md)). Le pipeline vérifie la signature de l'image et la synchronisation des ExternalSecret, puis lance `helm upgrade --install` avec l'image du build CI (`rhdemo.image.repository`, `rhdemo.image.tag`, `rhdemo.image.pullPolicy`) et active les ServiceMonitors si Prometheus Operator est présent. La commande exacte est dans le stage `Deploy to Kubernetes` de [`Jenkinsfile-CD`](../../../../Jenkinsfile-CD).

À la main (diagnostic), depuis la racine du dépôt, avec le kubeconfig du cluster :

```bash
# Rendu sans rien appliquer
helm template rhdemo rhDemo/infra/stagingkub/helm/rhdemo --set rhdemo.image.tag=<tag>

# État, historique, retour arrière
helm status rhdemo -n rhdemo-stagingkub
helm history rhdemo -n rhdemo-stagingkub
helm rollback rhdemo <révision> -n rhdemo-stagingkub
```

Une release bloquée (`another operation is in progress`) se débloque avec [`helm-unlock.sh`](../../scripts/helm-unlock.sh).

`helm uninstall rhdemo -n rhdemo-stagingkub` supprime les ressources du chart ; les données PostgreSQL restent sur l'hôte (`hostPath` des PersistentVolumes), et les Secrets gérés par ESO ne sont pas concernés.

---

## Vérifications

```bash
kubectl get pods,svc,httproute -n rhdemo-stagingkub
kubectl get externalsecrets -n rhdemo-stagingkub          # Ready = secrets synchronisés depuis OpenBao
kubectl get networkpolicies -n rhdemo-stagingkub
rhDemo/infra/stagingkub/scripts/validate-stagingkub.sh   # contrôle global de l'environnement
```

URLs, ports et ressources de l'environnement : [ENVIRONMENTS.md](../../../ENVIRONMENTS.md).

---

## Pour aller plus loin

- [Documentation Helm](https://helm.sh/docs/), [guide des templates](https://helm.sh/docs/chart_template_guide/)
- [Gateway API](https://gateway-api.sigs.k8s.io/), [NGINX Gateway Fabric](https://docs.nginx.com/nginx-gateway-fabric/)
- RBAC de Jenkins sur ce namespace : [SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md](../../../../docs/SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md)
