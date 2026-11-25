---
statut: actif
verifie_le: 2026-11-22
sources:
  - rhDemo/infra/jenkins-docker/init-registry-certs.sh
  - rhDemo/infra/jenkins-docker/start-jenkins.sh
  - rhDemo/infra/jenkins-docker/docker-compose.yml
  - rhDemo/infra/jenkins-docker/openbao/
  - rhDemo/infra/stagingkub/scripts/init-stagingkub.sh
  - rhDemo/infra/stagingkub/scripts/init-keycloak-stagingkub.sh
  - rhDemo/infra/stagingkub/scripts/install-observability.sh
  - rhDemo/scripts/openbao-setup.py
  - rhDemo/Jenkinsfile-FixCVE
---

# Installation complète depuis une machine vide

Ce guide donne l'**ordre** d'installation de toute la chaîne : poste de développement, Jenkins, OpenBao, chaîne CI (environnement ephemere), cluster stagingkub et chaîne CD, observabilité, Renovate et fixcve-auto. Pour chaque composant, il renvoie à sa documentation de référence au lieu de la recopier.

L'ordre suit les dépendances :

```
Docker ─┬─ dev (facultatif)
        └─ jenkins-docker : registry, Jenkins, SonarQube, OpenBao
              ├─ CI  → environnement ephemere, image signée dans le registry
              └─ stagingkub (registry + OpenBao) → CD → Keycloak initialisé
                    ├─ observabilité
                    └─ Renovate, mise à jour en place de l'infrastructure
        fixcve-auto (facultatif, après la CI)
```

Les chemins sont relatifs à la racine du dépôt. Prévoir un gestionnaire de mots de passe local (KeePassXC) : plusieurs étapes affichent une seule fois un secret à y ranger.

## 1. Machine et outils

- Linux, 16 Go de RAM (stagingkub et Jenkins tournent ensemble), 4 cœurs ou plus, 20 Go de disque libres.
- Docker et Docker Compose v2 récents, Git, `openssl`, `curl`, `jq`, Python 3 avec PyYAML (scripts de `rhDemo/scripts/`).
- Pour stagingkub : KinD 0.33+, `kubectl`, Helm 4 ; limites inotify relevées pour Cilium. Versions et commandes : [stagingkub/README.md](../infra/stagingkub/README.md), section « Prérequis ».
- Pour le développement seulement : Java 25 (le wrapper Maven est fourni).

```bash
git clone https://github.com/leuwen-lc/rhdemo.git
```

## 2. Poste de développement (facultatif)

PostgreSQL et Keycloak locaux en Docker Compose, puis `./mvnw spring-boot:run` depuis `rhDemo/` : [infra/dev/README.md](../infra/dev/README.md). Indépendant du reste de la chaîne.

## 3. Jenkins, registry et OpenBao (`rhDemo/infra/jenkins-docker/`)

OpenBao vit dans le même Docker Compose que Jenkins, et les agents Jenkins montent l'autorité de certification locale créée pour lui : **l'autorité doit exister avant le premier démarrage de Jenkins**.

1. Registry et mots de passe Jenkins : étapes 1 et 2 de [QUICKSTART.md](../infra/jenkins-docker/QUICKSTART.md) (`init-registry-certs.sh`, certificat déclaré à Docker, fichier `.env`).
2. OpenBao : étapes 1 à 5 de [OPENBAO.md](OPENBAO.md), « Installation à blanc » (autorité locale, certificat, démarrage, initialisation, déverrouillage, configuration de base). La clé de déverrouillage, le jeton root et le mot de passe `admin` vont dans KeePassXC. Le cluster KinD n'existant pas encore, le certificat d'OpenBao est émis sans l'IP du réseau `kind` : c'est attendu, il sera réémis à l'étape 5.
3. Démarrage de Jenkins : `./start-jenkins.sh` (étape 3 du QUICKSTART, étape 6 d'OPENBAO.md), puis http://localhost:8080. Architecture et exploitation : [jenkins-docker/README.md](../infra/jenkins-docker/README.md).
4. Credentials de la CI, à créer avant le premier build :
   - accès de Jenkins à OpenBao : `rhDemo/scripts/openbao-setup.py jenkins-approle` ;
   - signature Cosign : étape 8 d'OPENBAO.md (`configure-openbao.sh cosign`, credential `cosign-public-key-transit`, `openbao-setup.py cosign-approle`) ;
   - SonarQube et NVD : section « Obligatoires » du QUICKSTART.

## 4. Chaîne CI et environnement ephemere

Lancer le job `RHDemo-CI`. Il construit et teste l'application, monte l'environnement ephemere (Docker Compose jetable, secrets tirés au hasard), y passe Selenium et ZAP, puis pousse et signe l'image dans le registry local. Aucun secret à préparer pour ephemere.

- Étapes du pipeline et dépannage : [PIPELINES_CI_CD.md](PIPELINES_CI_CD.md).
- Accès manuel à ephemere après un build (option `KEEP_EPHEMERE_ENV`, entrées `/etc/hosts`) : [ephemere/README.md](../infra/ephemere/README.md).
- Tests Selenium : [rhDemoAPITestIHM/README.md](../../rhDemoAPITestIHM/README.md).

## 5. Cluster stagingkub

1. Secrets de stagingkub, **avant tout déploiement** : `rhDemo/scripts/openbao-setup.py stagingkub` (valeurs générées : PostgreSQL ne prend son mot de passe qu'à l'initialisation de sa base).
2. Cluster : `rhDemo/infra/stagingkub/scripts/init-stagingkub.sh` (KinD, Cilium, NGINX Gateway Fabric, certificats, `/etc/hosts`, External Secrets Operator, RBAC et kubeconfigs de Jenkins). Détail : [stagingkub/README.md](../infra/stagingkub/README.md), « Installation initiale ».
3. Première installation seulement : le script s'arrête à l'installation d'ESO, car le certificat d'OpenBao ne contient pas encore l'IP du réseau `kind`, créé avec le cluster. Le réémettre, redémarrer et déverrouiller OpenBao, puis relancer `init-stagingkub.sh`, qui réutilise le cluster déjà créé :

   ```bash
   cd rhDemo/infra/jenkins-docker
   ./openbao/init-local-ca.sh openbao     # réémet le certificat avec l'IP kind
   docker compose restart openbao && ./openbao/unseal.sh
   ../stagingkub/scripts/init-stagingkub.sh
   ```

4. Contrôle : `rhDemo/infra/stagingkub/scripts/validate-stagingkub.sh`.
5. Credentials Jenkins des kubeconfigs `kubeconfig-stagingkub` (CD) et `kubeconfig-stagingkub-infra-upgrader` (mise à jour en place) : créés par `init-stagingkub.sh` (mot de passe admin de Jenkins demandé). Jenkins indisponible à ce moment : `rhDemo/scripts/rotate-secrets.py --if-missing kubeconfig-stagingkub kubeconfig-stagingkub-infra-upgrader`. Liste commentée : `casc/jenkins-casc.yaml` ; droits : [SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md](SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md).

Certificats de la Gateway (auto-signés par défaut, Let's Encrypt possible) : [CERTIFICATS_WEB.md](CERTIFICATS_WEB.md). Flux réseau autorisés : [SECURITE_NETWORK_POLICY.md](SECURITE_NETWORK_POLICY.md).

## 6. Chaîne CD et initialisation de Keycloak

1. Lancer le job `RHDemo-CD` (sans paramètre : dernier build CI validé). Il vérifie la signature de l'image et la synchronisation des secrets, puis déploie le chart Helm.
2. Une seule fois, Keycloak démarré : `rhDemo/infra/stagingkub/scripts/init-keycloak-stagingkub.sh` (realm, client OIDC, utilisateurs de test) : [README-INIT-KEYCLOAK.md](../infra/stagingkub/scripts/README-INIT-KEYCLOAK.md).
3. Application : https://rhdemo-stagingkub.intra.leuwen-lc.fr, avec un utilisateur de test (identifiants dans OpenBao : [ROTATION_SECRETS.md](ROTATION_SECRETS.md), « Retrouver un secret »).

Paramétrage de l'application dans le cluster : [PARAMETRAGE-APPLICATIF-AVEC-KUB.md](PARAMETRAGE-APPLICATIF-AVEC-KUB.md).

## 7. Observabilité (facultatif)

`rhDemo/scripts/openbao-setup.py observability` (mot de passe administrateur de Grafana, généré dans OpenBao), puis `rhDemo/infra/stagingkub/scripts/components/install-external-secrets.sh` (il crée le Secret `grafana-admin`), puis `rhDemo/infra/stagingkub/scripts/install-observability.sh` (Prometheus, Loki, Alloy, Grafana) : [OBSERVABILITY_STACK_INTEGRATION.md](OBSERVABILITY_STACK_INTEGRATION.md). Le CD suivant active les ServiceMonitors de l'application.

## 8. Renovate et mise à jour en place (facultatif)

1. Comptes bots Codeberg et accès externes (GitHub, Docker Hub) : [RENOVATE_AUTOMERGE_CI.md](RENOVATE_AUTOMERGE_CI.md), « Comptes et credentials ».
2. Valeurs dans OpenBao et credentials Jenkins de même identifiant : `rhDemo/scripts/openbao-setup.py jenkins` (étape 7 d'OPENBAO.md ; les tokens Codeberg et la clé GPG sont émis directement).
3. Le job `RHDemo-Renovate` tourne chaque jour ; `RHDemo-Stagingkub-Upgrade-Deploy` applique les montées de version de l'infrastructure de stagingkub ([STAGINGKUB_REBUILD_PIPELINE.md](etudes/STAGINGKUB_REBUILD_PIPELINE.md)).

## 9. fixcve-auto (facultatif)

Remédiation automatique des CVE détectées par la CI, par le job Jenkins `RHDemo-FixCVE` : comptes dédiés (Jenkins `claude`, bot Codeberg), puis `rhDemo/scripts/openbao-setup.py jenkins fixcve-forgejo-token fixcve-jenkins-api` ; le job et son agent sont déjà dans JCasC. Skill interactif `/fixcve` : `rhDemo/scripts/fixcve-install.sh`. Détail : [FIXCVE_AUTO.md](FIXCVE_AUTO.md), « Installation ».

## 10. Fin d'installation

- Révoquer le jeton root d'OpenBao : `rhDemo/infra/jenkins-docker/openbao/configure-openbao.sh revoke-root`. L'administration courante passe par l'utilisateur `admin` ; un jeton root se recrée au besoin (`generate-root`, voir [OPENBAO.md](OPENBAO.md)).
- Tâches récurrentes sur les secrets (`rotate-secrets.py --check`, `secret_id` AppRole à renouveler avant 100 jours, certificat d'OpenBao annuel) et identifiants de connexion : [ROTATION_SECRETS.md](ROTATION_SECRETS.md).

## Après chaque redémarrage de la machine

1. `rhDemo/infra/jenkins-docker/openbao/unseal.sh` : OpenBao redémarre scellé ; tant qu'il l'est, les pipelines, ESO et fixcve-auto attendent ou échouent.
2. `rhDemo/infra/stagingkub/scripts/repair-cluster-after-restart.sh` : conteneurs du cluster et du registry, réseau `kind`, Cilium et DNS du cluster.

Ports, URLs et ressources de chaque environnement : [ENVIRONMENTS.md](../infra/ENVIRONMENTS.md).
