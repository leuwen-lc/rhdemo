# 🌍 Guide des environnements RHDemo

Ce document compare les environnements du projet et donne, pour chacun, comment le démarrer et comment y accéder. Le détail de chaque environnement est dans son README ; les images et versions se lisent dans les fichiers cités ([IMAGE_VERSIONS_MANAGEMENT.md](../docs/IMAGE_VERSIONS_MANAGEMENT.md)).

---

## 📋 Environnements disponibles

| Environnement | Technologie | Rôle | Démarrage | README |
|---------------|-------------|------|-----------|--------|
| **dev** | Docker Compose (PostgreSQL + Keycloak), application lancée par Maven ou l'IDE | Développement local | `./mvnw spring-boot:run -Dspring-boot.run.profiles=dev` depuis `rhDemo/` | [dev/README.md](./dev/README.md) |
| **ephemere** | Docker Compose | Environnement jetable de la CI : tests Selenium et scan OWASP ZAP | Créé et détruit par chaque build `RHDemo-CI` | [ephemere/README.md](./ephemere/README.md) |
| **stagingkub** | Kubernetes KinD, chart Helm | Environnement proche de la production | `init-stagingkub.sh` une fois, puis job `RHDemo-CD` | [stagingkub/README.md](./stagingkub/README.md) |
| **jenkins-docker** | Docker Compose | Usine logicielle : Jenkins, SonarQube, registre local, OpenBao | [QUICKSTART.md](./jenkins-docker/QUICKSTART.md) | [jenkins-docker/README.md](./jenkins-docker/README.md) |

Installation de l'ensemble depuis une machine vide : [INSTALLATION_COMPLETE.md](../docs/INSTALLATION_COMPLETE.md).

---

## 🔌 Ports et URLs

| Environnement | Service | Accès | Source |
|---------------|---------|-------|--------|
| dev | Application | http://localhost:9000 | `server.port` de `application.yml` |
| dev | Keycloak | http://localhost:6090 | [`dev/docker-compose.yml`](./dev/docker-compose.yml) |
| dev | PostgreSQL | `127.0.0.1:5432` | idem |
| ephemere | Application | https://rhdemo.ephemere.local:58443 | [`ephemere/docker-compose.yml`](./ephemere/docker-compose.yml), seul port publié (nginx) |
| ephemere | Keycloak | https://keycloak.ephemere.local:58443 | idem |
| stagingkub | Application | https://rhdemo-stagingkub.intra.leuwen-lc.fr | port 443 de l'hôte → NodePort 32616 de NGF ([`kind-config.yaml`](./stagingkub/kind-config.yaml)) |
| stagingkub | Keycloak | https://keycloak-stagingkub.intra.leuwen-lc.fr | idem |
| stagingkub | Grafana | https://grafana-stagingkub.intra.leuwen-lc.fr | idem ([OBSERVABILITY_STACK_INTEGRATION.md](../docs/OBSERVABILITY_STACK_INTEGRATION.md)) |
| jenkins-docker | Jenkins | http://localhost:8080 | [`jenkins-docker/docker-compose.yml`](./jenkins-docker/docker-compose.yml) |
| jenkins-docker | SonarQube | http://localhost:9020 (démarré seulement pendant l'analyse de la CI) | idem |
| jenkins-docker | Registre `kind-registry` | `localhost:5000` (HTTPS, autorité locale) | idem ([REGISTRY.md](../docs/REGISTRY.md)) |
| jenkins-docker | OpenBao | `https://127.0.0.1:8200` | idem ([OPENBAO.md](../docs/OPENBAO.md)) |

Les ports de jenkins-docker et de PostgreSQL en dev ne sont publiés que sur `127.0.0.1`. Les noms `*.ephemere.local` et `*-stagingkub.intra.leuwen-lc.fr` se résolvent par `/etc/hosts` (voir les README d'environnement).

---

## 🐳 Environnement `ephemere` (Docker Compose)

```
Hôte (port 58443)
 └─ nginx (TLS, en-têtes de sécurité, limitation de débit)
     ├─ rhdemo-app ── rhdemo-db (PostgreSQL)
     └─ keycloak ──── keycloak-db (PostgreSQL)
```

- **Services** : `rhdemo-db`, `keycloak-db`, `keycloak`, `rhdemo-app` (image construite par le `Dockerfile` du projet), `nginx`.
- **Cycle de vie** : `Jenkinsfile-CI` génère les secrets, démarre l'environnement, initialise la base et Keycloak, lance Selenium à travers le proxy ZAP, puis détruit tout. Le paramètre `KEEP_EPHEMERE_ENV` le garde après le build pour le débogage.
- **Pas de démarrage manuel** : l'environnement dépend des secrets, des certificats et de l'image produits par le build en cours ; pour l'inspecter, lancer `RHDemo-CI` avec `KEEP_EPHEMERE_ENV` (accès : voir son README).
- **Limites** : ne teste ni Kubernetes, ni Helm, ni les NetworkPolicies.

---

## ☸️ Environnement `stagingkub` (Kubernetes KinD)

```
Hôte (port 443)
 └─ NodePort 32616 ─ NGINX Gateway Fabric, shared-gateway (namespace nginx-gateway, TLS shared-tls-cert)
     ├─ HTTPRoute rhdemo-route   ─ rhdemo-app ── postgresql-rhdemo (StatefulSet)
     └─ HTTPRoute keycloak-route ─ keycloak ──── postgresql-keycloak (StatefulSet)
Cluster KinD « rhdemo » : CNI Cilium, NetworkPolicies default deny, pas d'egress Internet
Autres namespaces : external-secrets (ESO), monitoring et loki-stack (observabilité)
```

- **Initialisation** (une fois, ou après recréation du cluster) : `rhDemo/infra/stagingkub/scripts/init-stagingkub.sh`. Il crée le cluster, Cilium, NGF et le Gateway partagé, le certificat TLS, le namespace, ESO et son raccordement à OpenBao (qui doit être démarré et déverrouillé), et connecte le registre local. L'observabilité s'installe ensuite par `install-observability.sh`.
- **Déploiement** : job `RHDemo-CD`, déclenché par chaque build `RHDemo-CI` réussi qui publie l'image, ou lancé à la main avec `IMAGE_TAG=<tag>` ([PIPELINES_CI_CD.md](../docs/PIPELINES_CI_CD.md)). Contenu du chart : [helm/rhdemo/README.md](./stagingkub/helm/rhdemo/README.md).
- **Composants système** (Cilium, NGF, observabilité) : mis à jour en place par `RHDemo-Stagingkub-Upgrade-Deploy` après merge d'une PR Renovate ([STAGINGKUB_REBUILD_PIPELINE.md](../docs/STAGINGKUB_REBUILD_PIPELINE.md)).
- **Contrôle** : `rhDemo/infra/stagingkub/scripts/validate-stagingkub.sh`.

---

## 🆚 Comparaison ephemere / stagingkub

| Aspect | ephemere | stagingkub |
|--------|----------|------------|
| Secrets | Tirés au hasard à chaque build par `Jenkinsfile-CI`, jamais stockés ; injectés par variables d'environnement et `docker cp` | Stockés dans OpenBao, recopiés en Secrets Kubernetes par External Secrets Operator ([OPENBAO.md](../docs/OPENBAO.md)) |
| Rotation | À chaque build | `rotate-secrets.py` ([ROTATION_SECRETS.md](../docs/ROTATION_SECRETS.md)) |
| Exposition | nginx, port 58443 publié | Gateway API (NGF), port 443 de l'hôte |
| Isolation réseau | Réseau Docker du Compose | NetworkPolicies default deny, flux whitelistés ([SECURITE_NETWORK_POLICY.md](../docs/SECURITE_NETWORK_POLICY.md)) |
| Données | Volumes Docker, perdus à la destruction | PersistentVolumes `hostPath` (`extraMounts` KinD), conservés à la recréation du cluster |
| Sauvegardes | Aucune (jetable) | CronJobs `pg_dump` quotidiens ([POSTGRESQL_BACKUP_CRONJOBS.md](../docs/POSTGRESQL_BACKUP_CRONJOBS.md)) |
| Observabilité | `docker logs` | Prometheus, Loki, Grafana |
| Image de l'application | Image locale du build en cours | Image signée du registre local, signature vérifiée avant déploiement |

---

## ❓ FAQ

### Les environnements peuvent-ils tourner en même temps ?

Oui : ephemere publie le port 58443, stagingkub le port 443, jenkins-docker des ports sur `127.0.0.1`. Sur un poste de 16 Go, la mémoire est la contrainte : SonarQube n'est démarré que pendant l'analyse, et Jenkins n'exécute qu'un agent à la fois.

### Lequel utiliser ?

- **dev** pour coder et déboguer dans l'IDE.
- **ephemere** pour rejouer à la main ce que fait la CI (option `KEEP_EPHEMERE_ENV`).
- **stagingkub** pour valider le chart, les NetworkPolicies, les montées de composants et le comportement proche de la production.

### Les secrets sont-ils les mêmes ?

Non, aucune valeur n'est partagée entre ephemere (aléatoire à chaque build) et stagingkub (OpenBao).

---

## 🔗 Liens utiles

- [Docker Compose](https://docs.docker.com/compose/), [KinD](https://kind.sigs.k8s.io/), [Helm](https://helm.sh/docs/), [Kubernetes](https://kubernetes.io/docs/)
