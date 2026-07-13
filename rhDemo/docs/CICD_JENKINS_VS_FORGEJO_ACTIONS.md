# Analyse stratégique CI/CD — Jenkins vs Forgejo Actions (Codeberg)

**Date :** 2026-06-09
**Auteur :** Avis d'expert CI/CD pour le projet RHDemo
**Périmètre :** Évaluation d'une bascule partielle ou totale du pipeline Jenkins existant
(`Jenkinsfile-CI`, `Jenkinsfile-CD`) vers **Forgejo Actions** *et* **Woodpecker CI** —
les deux solutions CI/CD proposées par Codeberg — en considérant la philosophie « 100% libre,
indépendance des grandes plateformes » du projet.

---

## 1. Synthèse exécutive (TL;DR)

| Question | Réponse courte |
|---|---|
| **Forgejo Actions peut-il exécuter le pipeline actuel ?** | **Techniquement oui, fonctionnellement non sans concessions majeures.** Les *steps* sont traduisibles ; ce qui n'est pas trivialement portable, c'est l'**orchestration réseau Docker locale**, la **bibliothèque Groovy partagée** et le **couplage fort** avec les services internes (SonarQube, registry, ZAP, KinD). |
| **Peut-on se passer complètement de Jenkins ?** | **Oui, mais au prix d'un déménagement coûteux** (réécriture ≈ 2 500 lignes YAML, refonte du déploiement K8s avec un *runner* local, perte des plugins riches Jenkins). Le bénéfice principal n'est pas technique : c'est la simplification opérationnelle et la cohérence Git/CI. |
| **Peut-on conserver un déploiement local sur le PC ?** | **Oui — c'est même obligatoire** pour atteindre stagingkub/ephemere. Solution : déployer un ***Forgejo Runner* auto-hébergé sur le PC**, enregistré auprès de Codeberg, avec accès Docker/KinD. |
| **Recommandation principale** | **Scénario hybride (option C ci-dessous)** : déplacer sur Codeberg ce qui est sans état et public (build, tests unitaires, OWASP dep-check, SonarCloud, SBOM, signature des releases). Garder sur le runner local tout ce qui touche au réseau Docker, à ZAP, à KinD et au déploiement. **Jenkins peut alors être retiré** au profit d'un Forgejo Runner local. |
| **Woodpecker CI est-il une alternative viable ?** | **Oui, et même meilleur que Forgejo Actions sur certains critères** : modèle 100 % conteneur natif (donc plus aligné avec votre stack Docker), YAML plus concis, base de code Go plus simple à auditer, déjà historiquement présent chez Codeberg (`ci.codeberg.org`). **Inconvénient majeur :** écosystème de *plugins* nettement plus petit que GitHub/Forgejo Actions, et le moteur Codeberg shared a des limites de ressources strictes (5 min/job sans approbation). Voir scénarios **E, F, G** en section 5bis. |

---

## 2. État des lieux

### 2.1 Pipeline Jenkins actuel — inventaire factuel

**CI (`Jenkinsfile-CI`, 1 902 lignes Groovy, ≈ 35 stages)** organisé en 7 phases :

1. **Préparation** : checkout, lecture version Maven, génération clé API ZAP, déchiffrement SOPS (age),
   extraction de secrets ciblés (`secrets-rhdemo.yml`), génération `application-ephemere.yml` pour
   `rhDemoInitKeycloak`.
2. **Build & tests** : `mvnw compile`, `mvnw verify` (Surefire + Failsafe + H2), OWASP Dependency-Check
   (clés NVD + OSSIndex), SonarQube, **Quality Gate avec webhook bloquant**, JaCoCo.
3. **Docker build** : nettoyage des anciennes images, `docker build` (BuildKit désactivé).
4. **Environnement ephemere** : `docker-compose up`, génération certs auto-signés, **connexion dynamique
   de l'agent Jenkins aux réseaux Docker** (`rhdemo-ephemere-network`), copies de configs Nginx,
   `pg_isready`, init schema PostgreSQL, init Keycloak via `mvnw spring-boot:run`, injection des secrets
   dans le conteneur app via `tar | docker cp`, redémarrage de l'application.
5. **Scans sécurité images** : Trivy en **parallèle** sur 5 images (postgres, keycloak, nginx, NGF,
   rhdemo-app) avec cache partagé, génération **SBOM CycloneDX**.
6. **Tests E2E** : OWASP ZAP démarré sur le réseau Jenkins, connecté au réseau ephemere, tests Selenium
   (Firefox headless via proxy ZAP), export du rapport HTML/JSON/HAR.
7. **Publication** : `docker tag` + `docker push` sur `kind-registry` HTTPS, **signature Cosign** par
   clé privée, rétention SNAPSHOT (3 dernières) + *garbage collection* du registry, archivage du
   `digest.txt` comme artifact (consommé par le CD via Copy Artifact).

**CD (`Jenkinsfile-CD`, 919 lignes, 13 stages)** :

1. Récupération du tag/digest via **Copy Artifact** depuis le job CI (`projectName: 'RHDemo-CI'`).
2. Déchiffrement SOPS (différents secrets : `secrets-stagingkub.yml`).
3. Configuration accès KinD : connexion de Jenkins au réseau `kind`, installation du **kubeconfig RBAC**
   (`jenkins-deployer`), vérification des permissions (`kubectl auth can-i`).
4. Vérification de la signature Cosign (clé publique).
5. `kubectl create secret … --dry-run=client | kubectl apply` pour DB, admin Keycloak, secrets app.
6. Déploiement Helm/manifests, rollout, healthchecks.

### 2.2 Forgejo Actions actuel

Une seule action existe (`.forgejo/workflows/renovate.yml`, 20 lignes) : exécute Renovate sur un
runner Docker hébergé chez Codeberg, déclenchée la nuit via cron. C'est un cas idéal pour Forgejo
Actions : *stateless*, sans accès au réseau local, sans secret métier.

### 2.3 Pourquoi le pipeline actuel est conçu pour Jenkins

L'examen du code révèle 9 dépendances **fortement couplées** à Jenkins :

| Dépendance | Détails | Difficulté de migration |
|---|---|---|
| Bibliothèque Groovy partagée | `load 'rhDemo/vars/rhDemoLib.groovy'` : `printSectionHeader`, `waitForHealthcheck`, `generateTrivyReport`, `aggregateTrivyResults`, `publishHTMLReports`, `cleanupSecrets` | Moyenne — à réécrire en shell/composite actions |
| `copyArtifactPermission` CI→CD | Le CD lit `image-digest/digest.txt` du CI via Copy Artifact | Moyenne — remplacer par OCI artifact + cosign attest, ou stockage objet |
| `waitForQualityGate abortPipeline: true` | Webhook SonarQube bloquant | Difficile — nécessite SonarCloud ou polling manuel |
| `recordCoverage` / `publishHTML` | Plugins Jenkins riches | Moyenne — replacer par upload de pages statiques ou commentaires PR |
| Agents éphémères Docker Cloud | Pool dynamique d'agents `rhdemo-jenkins-agent:latest` (cap = 2) avec caches Maven/Trivy/Selenium dans des **volumes Docker** | Difficile — la persistance de cache entre runs n'est pas garantie par Forgejo Actions |
| Branchement dynamique aux réseaux Docker | `docker network connect rhdemo-ephemere-network $(hostname)` | Difficile — l'agent Jenkins est un conteneur sur le même daemon que ephemere ; un runner Codeberg distant n'a aucun accès |
| Credentials Jenkins typés | `file()`, `string()`, `usernamePassword()` pour age, NVD, OSSIndex, Cosign, kubeconfig | Facile — `secrets.X` Forgejo, mais un secret `file` doit être encodé base64 |
| Configuration as Code (JCasC) | `jenkins-casc.yaml` déclare clouds, security realm, tools | À supprimer (gain net) |
| Communication via `docker-socket-proxy` | Le controller délègue le contrôle Docker à un proxy filtré (Tecnativa) | Sans objet — un runner Forgejo local ré-introduira un montage du socket |

---

## 3. Capacités de Forgejo Actions

### 3.1 Compatibilité avec l'écosystème GitHub Actions

Forgejo Actions repose sur le moteur **act_runner** (fork de `nektos/act`) et **accepte ≈ 95 %** des
*actions* GitHub publiées. Pratiquement, le YAML est identique :

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-java@v4
  with: { distribution: temurin, java-version: '25' }
- run: ./mvnw verify
```

Limites factuelles à connaître :
- Les *actions* qui dépendent de services externes GitHub (GitHub Token API spécifique, GHCR via OIDC,
  *workflow_run*) demandent une adaptation.
- Le runtime est **Node.js 20** par défaut ; les *actions* qui exigent une version supérieure peuvent
  échouer si le runner n'est pas à jour.
- Pas de *reusable workflows* en V1 du moteur Forgejo ; remplaçables par des **composite actions**
  internes (`./.forgejo/actions/<nom>/action.yml`).

### 3.2 Runners : trois variantes pertinentes

| Type | Coût | Souveraineté | Accès au PC local | Limite Codeberg |
|---|---|---|---|---|
| **Runner Codeberg partagé (CI)** | Gratuit, mutualisé | Hébergé en Allemagne, FOSS friendly | **Aucun** | 6 h max/job, faible CPU, pas d'accès au LAN |
| **Forgejo Runner auto-hébergé sur le PC** | Gratuit (votre matériel) | Totale | **Total** (réseau Docker, KinD, registry) | Aucune |
| **Hybride** (label `local-pc`) | Gratuit | Mixte | Sur jobs ciblés | Codeberg signe / PC exécute |

Le **Forgejo Runner auto-hébergé** est l'élément central de toute migration : c'est lui qui ré-introduit
l'accès au daemon Docker local, à KinD et au registry HTTPS, exactement comme l'agent Jenkins éphémère
actuel — mais sans tout l'appareillage JCasC / Docker Cloud Plugin.

### 3.3 Ce qui change concrètement vs Jenkins

| Capacité | Jenkins | Forgejo Actions |
|---|---|---|
| Langage du pipeline | Groovy (Turing-complet) | YAML déclaratif + shell |
| Étapes en parallèle | `parallel { … }` (groovy DSL) | Stratégie `matrix` ou jobs parallèles natifs |
| Webhook SonarQube bloquant | `waitForQualityGate` (plugin) | Polling REST API ou job séparé en `needs:` |
| Couverture | `recordCoverage` | Upload artifact + comment PR (action tierce) |
| Rapports HTML | `publishHTML` (UI Jenkins) | Upload artifact (téléchargement manuel) ou Forgejo Pages |
| Triggers | Webhook + cron + manuel | `push`/`pull_request`/`schedule`/`workflow_dispatch` |
| Variables d'env entre stages | `env.X` (mutable) | `outputs:` typés entre jobs |
| Reprise après échec partiel | Replay individuel d'un stage | Re-run d'un job (granularité plus large) |
| Auth | Plugins (LDAP, OIDC, etc.) | Authentification Codeberg native |

---

## 4. Mapping de traduction Groovy → Forgejo (par capacité)

| Élément Jenkins | Équivalent Forgejo | Effort | Risque |
|---|---|---|---|
| `agent { label 'builder' }` | `runs-on: local-pc` (label custom du runner) | Faible | Faible |
| `checkout scm` | `actions/checkout@v4` | Faible | Faible |
| `tools { jdk 'JDK25' }` | `actions/setup-java@v4 with: java-version: '25'` | Faible | Faible |
| `withCredentials([file(...)])` | `secrets.SOPS_AGE_KEY` (base64) + `echo $X | base64 -d > /tmp/age.key` | Faible | Moyen (encodage) |
| `withCredentials([usernamePassword(...)])` | 2 secrets séparés `secrets.OSSINDEX_USER` / `_PWD` | Faible | Faible |
| `def lib = load '…'` + 6 fonctions | 6 **composite actions** sous `.forgejo/actions/` ou scripts dans `rhDemo/ci/` | **Moyen** | Moyen — réécrire les helpers |
| `parallel(scanStages + [failFast: false])` | Job parent + `strategy.matrix` (5 entrées : images) ; ou jobs siblings | Faible | Faible (gain de lisibilité) |
| `waitForQualityGate abortPipeline: true` | Bascule vers **SonarCloud** (gratuit pour OSS) ou job de polling REST `/api/qualitygates/project_status` | Moyen | **Élevé** — SonarQube local exposé sur le LAN seulement |
| `recordCoverage tools:[[parser:'JACOCO', …]]` | Action `madrapps/jacoco-report` (commentaire PR) + upload XML | Faible | Faible |
| `publishHTML(...)` (8 rapports) | `actions/upload-artifact` (ZIP) ou push vers Forgejo Pages | Moyen | Modéré (perte d'UX immédiate) |
| `archiveArtifacts ... fingerprint: true` | `actions/upload-artifact@v4 with: retention-days: 30` | Faible | Faible |
| `copyArtifacts(projectName: 'RHDemo-CI', selector: lastSuccessful())` | **Disparait** si CI et CD sont dans le même workflow ; sinon **OCI artifact** (cosign attest) ou Codeberg Packages | Moyen | Moyen — repenser la frontière CI/CD |
| `docker network connect rhdemo-ephemere-network $(hostname)` | **Conserver tel quel** (le runner local est un conteneur sur le même daemon) | Faible | Faible (mais lie au runner local) |
| `junit '…/surefire-reports/*.xml'` | Action `dorny/test-reporter@v1` | Faible | Faible |
| `buildDiscarder(logRotator(...))` | `concurrency:` + rétention Forgejo configurable | Faible | Faible |
| `post { always { … cleanup … } }` | `if: always()` sur un job/step final | Faible | Faible |
| `timestamps()` | Activé par défaut dans Forgejo Actions UI | Faible | Faible |
| `timeout(time: 2, unit: 'HOURS')` | `timeout-minutes: 120` | Faible | Faible |

**Verdict du mapping :** environ **80 % des steps** se transposent en YAML quasi-mécaniquement.
Les **20 % restants** (Quality Gate, Copy Artifact, plugins de rapport) demandent un re-design
volontaire et de mauvais choix peuvent ici dégrader la sécurité ou l'UX.

---

## 5. Scénarios de répartition Jenkins / Forgejo

Quatre scénarios représentatifs, du plus conservateur au plus radical.

### Scénario A — *Status quo* + Forgejo pour la maintenance

**Description :** Jenkins reste maître de tout. Forgejo Actions ne porte que des tâches périphériques :
Renovate (déjà en place), validation YAML (`yamllint`), vérification des secrets non commités
(`gitleaks`), lint markdown.

**Avantages :**
- **0 perturbation** du pipeline en production.
- Forgejo absorbe les tâches bruyantes (Renovate) sans charger Jenkins.

**Inconvénients :**
- Aucun bénéfice structurel — la complexité Jenkins reste entière.
- Deux systèmes à maintenir.

**Quand le choisir ?** Si la priorité immédiate est la stabilité et que l'équipe n'a pas la
bande passante pour une migration.

---

### Scénario B — Forgejo construit, Jenkins déploie

**Description :** Tout ce qui est **stateless et build-time** part sur Codeberg (runner partagé) :

- Build Maven + tests unitaires Surefire (sans Keycloak)
- Build frontend Vue.js
- Tests d'intégration H2 Failsafe
- OWASP Dependency-Check
- Analyse SonarCloud (remplace SonarQube local) + Quality Gate via API
- Génération SBOM CycloneDX (Trivy sur le JAR avant build d'image, ou Syft)
- Signature de la **release tag** via Cosign + clé stockée comme secret Forgejo

Jenkins conserve uniquement :
- Build de l'image Docker (lié au registry HTTPS local)
- Démarrage ephemere + Selenium + ZAP
- Trivy multi-images (5 cibles)
- Publication sur `kind-registry`
- Tout le pipeline CD (KinD, kubectl RBAC)

**Avantages :**
- **Tests unitaires en quelques minutes** au lieu d'attendre la queue Jenkins (cap = 2 agents).
- Quality Gate visible en commentaire PR Codeberg, dès le push (pas après une heure de pipeline).
- Empreinte Jenkins réduite de ≈ 30 %.
- SonarCloud apporte des analyses cross-PR (différence vs main) que SonarQube CE n'a pas.

**Inconvénients :**
- **Double maintenance** des outils (Maven/Java/Node sont définis deux fois).
- **Double déchiffrement SOPS** : Codeberg n'a accès à aucun secret ephemere (et c'est bien) ; il
  faut séparer `secrets-public.yml` (CI build) et `secrets-private.yml` (CD).
- Si SonarCloud refuse les sources fermées, vous devez exposer un SonarQube public ou rester local.
- **Cosign clé privée chez Codeberg** : il faut accepter le modèle de confiance Codeberg pour la
  signature, ou ne signer qu'à la promotion finale (Jenkins).

**Quand le choisir ?** Si l'objectif est de **soulager Jenkins** et d'obtenir un **feedback rapide
sur les PR** sans toucher au déploiement.

---

### Scénario C — Forgejo orchestre tout, runner local pour l'infra (**recommandé**)

**Description :** Forgejo Actions devient le seul orchestrateur. Deux pools de runners enregistrés
sur Codeberg :

1. **Codeberg shared** (label `docker`, public) : build Maven, tests unitaires/IT, SonarCloud,
   OWASP, frontend.
2. **Self-hosted local** (label `local-pc`, sur votre machine 16 Go) : build d'image Docker, ephemere
   Docker Compose, Selenium + ZAP, Trivy multi-images, publication sur `kind-registry`, déploiement
   CD KinD (kubectl + Helm).

L'architecture devient :

```
┌──────────────────────┐        ┌───────────────────────────┐
│  Codeberg / Forgejo  │  jobs  │  Runner partagé Codeberg  │
│  Workflows           │ ─────► │  (build, tests, scan)     │
└──────────────────────┘        └───────────────────────────┘
            │
            │ jobs label=local-pc
            ▼
┌──────────────────────────────────────────────────────────┐
│  PC Linux 16 Go                                          │
│  ┌────────────────────┐                                  │
│  │ Forgejo Runner     │ ── DinD ── docker / KinD / regis│
│  │ (act_runner)       │                                  │
│  └────────────────────┘                                  │
│                                                          │
│  Plus de Jenkins controller, plus de SonarQube local,    │
│  plus de docker-socket-proxy.                            │
└──────────────────────────────────────────────────────────┘
```

**Avantages :**
- **Suppression complète de Jenkins** (controller, SonarQube CE local, docker-socket-proxy, JCasC,
  Docker Cloud Plugin) → **gain RAM ≈ 3-4 Go** sur la machine 16 Go.
- **Unification du workflow** : le pipeline est dans Git (`.forgejo/workflows/`), versionné avec le
  code, **revu en PR**. Plus de drift JCasC/Jenkinsfile.
- **Empreinte cognitive divisée par 2** : YAML déclaratif + shell vs Groovy + JCasC.
- **Auth unifiée** : pas de second compte admin Jenkins à protéger.
- **Cohérence sécurité** : un seul système à durcir (le runner local), un seul `gitleaks` à brancher.

**Inconvénients :**
- **Migration importante** : ≈ 2-3 semaines de travail focalisé (35 stages + 13 stages CD à porter).
- **Perte des features Jenkins riches** : Blue Ocean, replays granulaires, dashboard cross-job,
  `recordCoverage`, `publishHTML`. À remplacer par des actions communautaires (dorny, madrapps…)
  ou par Forgejo Pages.
- **Couplage fort au runner local** : si le runner tombe, ephemere + CD sont à l'arrêt. Mitigation :
  systemd `Restart=always` et second runner *cold standby*.
- **Risques de fuite via runner partagé Codeberg** : tout ce qui s'exécute sur le shared runner est
  observable par Codeberg ; les secrets ne doivent **jamais** transiter par ces jobs (NVD key,
  OSSIndex creds ne sont pas critiques ; SOPS age key l'est).
- **Le runner local en DinD** redonne au pipeline les pleins pouvoirs sur le Docker hôte ; il faut
  conserver l'équivalent du `docker-socket-proxy` ou accepter le risque.

**Quand le choisir ?** Si l'objectif est la **cible cible long terme** et qu'on accepte un investissement
de réécriture pour gagner une infrastructure plus simple, plus *git-native* et plus alignée avec
la philosophie « 100 % libre, indépendance des grandes plateformes » du projet.

---

### Scénario D — Tout Forgejo, *zero local* (non recommandé en l'état)

**Description :** Pousser même ephemere et la CD sur des runners Codeberg.

**Pourquoi c'est infaisable aujourd'hui :**
- Le runner partagé Codeberg n'a **pas accès** à votre cluster KinD local (NAT, pare-feu).
- ephemere consomme ≈ 4-5 Go RAM et fait tourner Keycloak + 2 Postgres + nginx — les limites de
  ressources / temps des runners partagés ne suffisent pas.
- La signature Cosign et le push registry HTTPS nécessitent que le registry soit publiquement
  joignable (ou via tunnel), ce qui contredit le modèle de sécurité actuel.

**Quand le choisir ?** Seulement si l'application est déployée sur un cluster Kubernetes **public**
(par exemple chez un hébergeur souverain : Scaleway, Clever Cloud, Infomaniak) — auquel cas
ephemere devient un environnement managé par Forgejo Actions via `kubectl` distant.

---

## 5bis. Scénarios alternatifs avec Woodpecker CI

### 5bis.1 Pourquoi évaluer Woodpecker CI à part ?

Codeberg propose **deux** moteurs CI distincts :

| Critère | Forgejo Actions | Woodpecker CI |
|---|---|---|
| Statut Codeberg | Officiel depuis 2024, intégré au moteur Forgejo | Historique (`ci.codeberg.org`), service séparé encore activement maintenu |
| Modèle d'exécution | Steps shell sur le runner OU dans un `container:` (modèle GitHub Actions) | **Tous les steps sont des conteneurs Docker**, jamais shell direct |
| Langage du pipeline | YAML GitHub-Actions-compatible | YAML très concis, syntaxe propre (≈ 30 % plus court que GitHub Actions) |
| Réutilisation | Composite actions (1-to-1 GitHub) | Plugins Docker (image OCI dédiée) + `template:` |
| Écosystème | Énorme (~ 95 % des actions GitHub fonctionnent) | Plus restreint (Woodpecker plugins, mais peut consommer toute image Docker) |
| Base de code | Go (Forgejo) + Node.js (act_runner) | **Go pur, 1 binaire** — empreinte minimale |
| Auto-hébergement | Forgejo Runner (act_runner) | Woodpecker Server + Agent (2 binaires) |
| Auth Codeberg | Native (compte Codeberg = login Forgejo) | OAuth Codeberg séparé sur `ci.codeberg.org` |
| Granularité runner | Labels (`docker`, `local-pc`) | Backends multiples (docker, kubernetes, local, ssh) |
| Secrets | `secrets.X` (jobs) | `secrets:` au niveau pipeline ou *organization-wide* |
| Limites Codeberg shared | 6 h max/job | **5 min/job sans approbation** (10 min après *trust*) — beaucoup plus strict |

**Synthèse :** Woodpecker est **plus simple, plus rapide à apprendre et plus aligné avec un stack
container-first** (votre cas), mais son écosystème de *plugins* prêts à l'emploi est plus petit
et les limites Codeberg shared sont beaucoup plus restrictives. Pour un projet self-hosted sur PC,
ces limites n'ont aucune importance.

### 5bis.2 Exemple de pipeline Woodpecker équivalent

Le même build Maven, en Woodpecker :

```yaml
# .woodpecker/ci-build.yaml
when:
  - event: [push, pull_request]
  - branch: [master, evolutions-post-*]

steps:
  build-and-test:
    image: maven:3.9-eclipse-temurin-21
    commands:
      - cd rhDemo && ./mvnw verify
    volumes:
      - maven-cache:/root/.m2

  owasp-check:
    image: maven:3.9-eclipse-temurin-21
    commands:
      - cd rhDemo && ./mvnw org.owasp:dependency-check-maven:check -DnvdApiKey=$NVD_API_KEY
    secrets: [nvd_api_key]
    depends_on: [build-and-test]
```

À comparer avec l'équivalent Forgejo Actions du même rapport (annexe A) : **≈ 40 % moins de lignes**,
pas de notion de `runs-on`, pas de `uses:`, pas de cache *explicite* (volume Docker classique).

### 5bis.3 Scénario E — Woodpecker shared Codeberg + Jenkins local

**Description :** Symétrique du scénario B mais avec Woodpecker (`ci.codeberg.org`) à la place de
Forgejo Actions. Build Maven + tests unitaires + OWASP + SBOM + SonarCloud sur Codeberg. Jenkins
conserve toute la partie ephemere/Selenium/ZAP/CD/registry.

**Avantages spécifiques à Woodpecker :**
- Définition de pipeline **30-40 % plus concise** que la version Forgejo Actions.
- Modèle 100 % conteneur : pas de `setup-java@v4`, on choisit directement l'image Maven officielle.
- **Moins de couplage** au runtime (Node.js du runner, versions d'actions, OS du runner).

**Inconvénients spécifiques à Woodpecker :**
- **Limite stricte de 5 min/job sans approbation** sur `ci.codeberg.org` : le `mvnw verify` actuel
  (5-6 min) + OWASP (4-5 min) **dépassent** ; nécessite de demander un *trust* explicite à Codeberg
  (procédure manuelle, délais variables). Sans *trust*, le scénario est inutilisable en l'état.
- Écosystème de *plugins* Woodpecker plus restreint : pour SonarCloud, il faudra écrire un step
  shell explicite (vs `SonarSource/sonarcloud-github-action` côté Forgejo).
- Codeberg pousse depuis 2024 vers Forgejo Actions et **maintient Woodpecker en mode legacy** :
  pas de garantie de pérennité long-terme sur le shared `ci.codeberg.org`.

**Quand le choisir ?** Si vous appréciez la concision de Woodpecker et acceptez de demander le *trust*
sur Codeberg. **Risque :** miser sur un service que Codeberg pourrait déprécier à terme.

### 5bis.4 Scénario F — Woodpecker entièrement auto-hébergé local (PC)

**Description :** Installer un **Woodpecker Server + Agent** sur le PC, connecté à Codeberg via OAuth.
Codeberg ne fait que stocker le code et déclencher les webhooks ; toute l'exécution est locale, sans
limite de temps ni de ressources.

**Composants à installer (≈ 200 Mo RAM, 2 binaires Go) :**
- `woodpecker-server` : reçoit les webhooks de Codeberg, expose une UI sur `:8000`.
- `woodpecker-agent` : exécute les pipelines en lançant des conteneurs sur le daemon Docker local.
- Connexion OAuth `gitea` (Codeberg implémente le provider Gitea) avec un *client ID* enregistré
  côté Codeberg.

```yaml
# docker-compose.yml minimaliste — remplace tout le bloc jenkins-docker
services:
  woodpecker-server:
    image: woodpeckerci/woodpecker-server:next
    ports: ["8000:8000"]
    environment:
      WOODPECKER_OPEN: "false"
      WOODPECKER_HOST: "https://ci.intra.leuwen-lc.fr"
      WOODPECKER_GITEA: "true"
      WOODPECKER_GITEA_URL: "https://codeberg.org"
      WOODPECKER_GITEA_CLIENT: "${OAUTH_CLIENT_ID}"
      WOODPECKER_GITEA_SECRET: "${OAUTH_CLIENT_SECRET}"
      WOODPECKER_AGENT_SECRET: "${AGENT_SECRET}"
    volumes:
      - woodpecker-server-data:/var/lib/woodpecker

  woodpecker-agent:
    image: woodpeckerci/woodpecker-agent:next
    environment:
      WOODPECKER_SERVER: "woodpecker-server:9000"
      WOODPECKER_AGENT_SECRET: "${AGENT_SECRET}"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on: [woodpecker-server]
```

**Avantages :**
- **Empreinte mémoire ≈ 200 Mo** (vs 3-4 Go pour Jenkins + agents + SonarQube + proxy).
- **Aucune limite Codeberg** : on peut faire tourner `mvnw verify` + ephemere + Selenium + ZAP sans
  contrainte de temps.
- **Code de Woodpecker** : Go pur, ≈ 50 000 LOC totales, auditable. À comparer à Jenkins
  (Java, > 1 M LOC + 133 plugins de tierces parties).
- Pas de comptes admin à gérer : auth déléguée à Codeberg via OAuth.
- Cache Maven/Trivy/Selenium gérés par **volumes Docker nommés**, exactement comme aujourd'hui
  côté Jenkins. **Migration 1-1 des volumes possible** (`rhdemo-maven-repository`,
  `rhdemo-trivy-cache`, `rhdemo-wdm-cache`).
- **Pipeline 100 % conteneur** : chaque step a son image dédiée, plus simple à raisonner que le mix
  shell+container actuel de Jenkins.
- UI Woodpecker minimaliste mais fonctionnelle (visualisation DAG, replay, secrets, logs).

**Inconvénients :**
- **Pas de PR depuis forks externes** sans configuration spécifique : Woodpecker filtre par défaut les
  contributions extérieures (sécurité). Pour un projet self-hosted *intra*, c'est sans impact.
- **Plus petit écosystème** : la plupart des « actions » GitHub n'existent pas en plugin Woodpecker
  natif → il faut écrire les commandes shell soi-même ou utiliser l'image OCI source. Pour ce projet
  qui fait déjà tout en shell+Maven, c'est **plutôt un avantage** (moins de magie cachée).
- **Réseau Docker dynamique** : `docker network connect` reste possible mais nécessite que l'agent
  Woodpecker tourne avec accès au socket Docker (mêmes implications sécurité que l'agent Jenkins
  actuel — voir mitigations en section 6.2).
- **Pas de `waitForQualityGate` natif** : à remplacer par polling SonarQube REST (idem Forgejo).

**Quand le choisir ?** Si la **priorité est la simplicité radicale et l'empreinte minimale**, et si
l'on accepte un écosystème de *plugins* moins fourni en échange. C'est le scénario qui s'aligne le
mieux avec « 100 % libre, auditable » : Woodpecker = ≈ 50 000 LOC Go vs Jenkins = > 1 M LOC Java.

### 5bis.5 Scénario G — Hybride Woodpecker Codeberg + Woodpecker local

**Description :** Symétrique du scénario C, mais avec Woodpecker des deux côtés :

- **Codeberg `ci.codeberg.org`** : jobs courts (build Maven, tests unitaires, OWASP, SBOM,
  SonarCloud) — sous réserve d'obtenir le *trust* pour dépasser 5 minutes.
- **Woodpecker local** : jobs longs (build image, ephemere, Selenium, ZAP, Trivy, publication, CD).

Les deux Woodpecker s'orchestrent via :
- Un workflow Codeberg qui pousse un **artifact OCI** (image build, JAR) sur `kind-registry` (via
  un tunnel SSH temporaire ou via Codeberg Packages).
- Le webhook de fin du pipeline Codeberg déclenche le pipeline local (via API Woodpecker locale).

**Avantages :** Identiques au scénario C (Forgejo) en plus :
- Empreinte locale réduite (Woodpecker server+agent < Forgejo runner+act_runner).
- **Cohérence syntaxique** : un seul format YAML Woodpecker partout, pas de dialecte différent
  entre Codeberg et le PC.

**Inconvénients :**
- **Complexité d'orchestration cross-server** : 2 serveurs Woodpecker à synchroniser, gestion de
  l'artifact handoff entre Codeberg shared et local.
- Plus complexe que le scénario F (tout local) ; gain en feedback PR ≈ similaire au scénario C.
- Dépendance double : Codeberg shared *et* runner local — chacun peut tomber indépendamment.

**Quand le choisir ?** Cas marginal. Si l'argument du feedback rapide sur PR est important **et**
que la concision Woodpecker prime sur l'écosystème Forgejo Actions. Sinon, préférer F (radical et
simple) ou C (Forgejo Actions hybride, plus de capacité d'extension).

### 5bis.6 Comparatif des 7 scénarios

| # | Scénario | Moteur CI/CD | Effort migration | Empreinte locale RAM | Risque opérationnel | Alignement projet |
|---|---|---|---|---|---|---|
| A | Status quo + Forgejo périphérique | Jenkins + Forgejo | Très faible | Inchangée | Très faible | Faible (pas d'évolution) |
| B | Forgejo build, Jenkins déploie | Jenkins + Forgejo Actions | Moyen | -500 Mo | Moyen | Moyen |
| C | Forgejo Actions partout (recommandé) | Forgejo Actions | Élevé (6-8 sem) | **-3 à -4 Go** | Moyen | **Très bon** |
| D | Tout Codeberg, zero local | Forgejo Actions | Infaisable | n/a | Très élevé | n/a |
| E | Woodpecker Codeberg + Jenkins | Jenkins + Woodpecker | Moyen | -500 Mo | Élevé (trust 5 min, deprecation risque) | Moyen |
| F | Woodpecker self-hosted total | Woodpecker | Élevé (5-7 sem) | **-3 à -4 Go** | Faible (binaire Go simple) | **Excellent** (FOSS minimaliste) |
| G | Woodpecker Codeberg + local | Woodpecker × 2 | Très élevé (cross-server) | -3 à -4 Go | Élevé | Bon mais complexe |

### 5bis.7 Choix entre Forgejo Actions et Woodpecker (cas auto-hébergé)

Si l'auto-hébergement total est la cible (scénarios C ou F), le choix entre les deux moteurs se
résume ainsi :

| Argument | Pousse vers Forgejo Actions (C) | Pousse vers Woodpecker (F) |
|---|---|---|
| Compatibilité écosystème | ✓ (95 % des actions GitHub utilisables) | ✗ (re-écrire en shell) |
| Concision YAML | ✗ | ✓ (30-40 % moins de lignes) |
| Empreinte mémoire serveur | ≈ 600 Mo (Forgejo lui-même est déjà installé) | ≈ 200 Mo |
| Maturité Codeberg | ✓ Récent mais officiel | ⚠ Historique, semble *legacy* depuis 2024 |
| Auth | Native (compte Codeberg = Forgejo) | OAuth séparé |
| Possibilité d'usage *aussi* sur runner Codeberg shared | ✓ Limite 6 h | ⚠ Limite 5 min |
| Réutilisation de code pipeline | Composite actions | Templates + plugins Docker |
| Modèle conteneur | Mixte (shell ou container:) | **100 % conteneur** |
| Lecture du Jenkinsfile-CI existant | Moins direct (passage par actions/setup-X) | Plus direct (tout est `image: + commands:`) |

**Verdict :** pour ce projet précis :
- **Si vous prévoyez d'intégrer des outils tiers** (`SonarSource/...`, `madrapps/jacoco-report`,
  `dorny/test-reporter`, etc.) → **scénario C (Forgejo Actions)**.
- **Si la priorité est l'empreinte minimale, la philosophie FOSS et la pureté conteneur** →
  **scénario F (Woodpecker self-hosted total)**.

Les deux sont défendables. Le scénario **F est le plus radical et le plus aligné avec l'esprit
« 100 % libre, indépendance des plateformes »** car il dépend uniquement de Codeberg pour
l'hébergement Git et des images Docker upstream pour l'exécution — aucun service tiers.

---

## 6. Impact sécurité

### 6.1 Surface d'attaque réduite (scénarios B/C)

- **Suppression de Jenkins** = -1 service exposé sur le LAN (UI sur 8080), -1 base d'utilisateurs
  (admin/claude), -1 chaîne de plugins (133 plugins selon `plugins.txt`) avec leur cadence de CVE.
- **Suppression de SonarQube local** = -2 conteneurs (Sonar + DB), -1 surface d'écoute (9020).
- **Suppression du docker-socket-proxy** = -1 conteneur privilégié.

### 6.2 Nouveaux risques à traiter

| Risque | Mitigation |
|---|---|
| Secrets Forgejo accessibles via un workflow malveillant (PR d'un attaquant) | `secrets:` ne sont **pas** exposés aux workflows déclenchés par des PR de forks. Configurer `permissions: read-all` + revue obligatoire des workflows modifiés en PR |
| Le runner local en DinD = root sur l'hôte | Conserver `docker-socket-proxy` côté runner local OU exécuter le runner dans une VM isolée OU utiliser Podman rootless |
| Fuite via un script `run:` qui `echo`-affiche un secret | Activer `actions/security-best-practices` : `mask::add-mask::` + revue systématique des `set +x` |
| Codeberg compromis → exfiltration des secrets stockés sur la plateforme | N'y stocker **que** les secrets non sensibles (NVD key, OSSIndex). Garder SOPS age key et Cosign privée **uniquement** sur le runner local (montage volume hors Codeberg) |
| Runner partagé Codeberg = supply chain externe | Pinner les *actions* par SHA (`uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11`), pas par tag |

### 6.3 Modèle de confiance des signatures Cosign

Dans le scénario C, la **clé privée Cosign ne doit jamais quitter le runner local** :

- Signature des images Docker `rhdemo-api` → runner local (clé montée depuis l'hôte).
- Signature des tags Git (release) → peut être Codeberg si la clé GPG/Cosign tag-only est différente.

Le pipeline actuel respecte déjà ce principe (`withCredentials([file(credentialsId: 'cosign-private-key'…)])`).
La migration doit le préserver.

### 6.4 Audit & traçabilité

- Jenkins propose nativement un *Audit Trail* plugin. Forgejo Actions journalise les runs en base ;
  exportables par API. **Pas de régression** si l'audit est exporté périodiquement vers Loki (déjà
  utilisé dans le projet).

---

## 7. Impact sur la durée d'exécution

Estimations basées sur la nature des étapes (CPU/IO bound) et la latence des runners.

| Étape | Aujourd'hui (Jenkins agent local) | Scénario B (build sur Codeberg) | Scénario C (build local, runner Forgejo) |
|---|---:|---:|---:|
| Checkout + setup Java | 30 s | 45 s (clone Codeberg + setup) | 25 s |
| `mvnw verify` (unitaires+IT H2) | 5-6 min | 5-7 min (CPU partagé) | 4-5 min |
| OWASP Dependency-Check | 4-5 min (avec cache NVD) | 5-7 min (cache à reconstruire) | 4-5 min |
| Sonar + Quality Gate | 3-4 min | 2-3 min (SonarCloud rapide) | identique |
| Build image Docker | 1-2 min | n/a (impossible : pas de registry public) | 1-2 min |
| ephemere + init + healthchecks | 3-4 min | n/a | 3-4 min |
| Trivy 5 images (parallèle) | 3-5 min | 4-6 min (pas de cache mutualisé) | 3-5 min |
| Tests Selenium + ZAP | 8-12 min | n/a | 8-12 min |
| Push registry + Cosign | 30 s | n/a | 30 s |
| **Total CI** | **30-45 min** | **identique ou +5 min** | **identique ou -3 min** |
| CD complet | 8-15 min | identique | identique |

**Analyse :**

- Le **gain de temps n'est pas le bon argument** pour migrer. Les étapes lourdes (ephemere, Selenium,
  Trivy) restent identiques car elles tournent toujours sur le même matériel.
- **Le vrai gain de feedback** est sur le scénario B/C : le développeur reçoit le résultat des tests
  unitaires + OWASP + Sonar en **6-10 minutes** sans attendre la queue du pipeline ephemere (les jobs
  Codeberg peuvent tourner en parallèle des jobs locaux, alors qu'aujourd'hui un seul agent Jenkins
  séquentialise tout — cap = 2).
- **Caches Maven, Trivy, NVD, Selenium webdriver** doivent être restaurés explicitement dans Forgejo
  via `actions/cache@v4` (équivalent du volume `rhdemo-maven-repository`). Une mauvaise stratégie
  de clé de cache peut ajouter 5-8 minutes par run — c'est le principal risque opérationnel.

---

## 8. Peut-on se passer complètement de Jenkins ?

**Oui, dans le scénario C, à 3 conditions :**

1. **Un Forgejo Runner local opérationnel et redondé** (un primary + un cold standby, démarrés
   par systemd, branchés au daemon Docker du PC).
2. **SonarQube remplacé** par SonarCloud (le projet est-il OSS ? sinon SonarCloud Team payant) ou
   conservé en *self-hosted* mais piloté par un job Forgejo local (perd l'argument simplification).
3. **Les helpers Groovy réécrits** en composite actions ou scripts shell sous `rhDemo/ci/`, avec
   tests dédiés.

**Pertes nettes par rapport à Jenkins :**

- Pas de **Blue Ocean** ni de visualisation de pipeline en arborescence DAG.
- Pas de **replay granulaire d'un seul stage** (Forgejo permet le re-run d'un job entier).
- `publishHTML` n'a pas d'équivalent direct ; les rapports HTML (Trivy, OWASP, ZAP, JaCoCo) doivent
  être téléchargés depuis les artifacts ou publiés sur Forgejo Pages.
- **`waitForQualityGate` bloquant** demande à être réécrit en polling REST (≈ 30 lignes shell).

**Gains nets :**

- ≈ 3-4 Go RAM libérés (Jenkins + agents + SonarQube + sa DB).
- Maintenance des **133 plugins Jenkins** supprimée.
- **Workflow CI versionné dans Git** (au lieu de partiellement dans JCasC, partiellement dans
  Jenkinsfile, partiellement dans l'UI Jenkins pour les credentials).
- **Un seul système** d'auth/secrets/runners à durcir.

---

## 9. Peut-on conserver un déploiement local sur le PC ?

**Oui, c'est même le seul moyen viable** dans tous les scénarios sauf D :

- ephemere doit **rester local** (4-5 Go RAM, accès au daemon Docker hôte).
- KinD reste local (cluster K8s in Docker, lié au noyau Linux du PC).
- Le registry `kind-registry:5000` reste local (TLS auto-signé, certs montés sur le runner).
- L'agent qui exécute `docker-compose up`, `kubectl apply`, `helm install` est :
  - **aujourd'hui** : l'agent Jenkins éphémère (`rhdemo-jenkins-agent:latest`).
  - **après migration** : un *Forgejo Runner* installé sur le même PC, avec **les mêmes droits**
    (montage du socket Docker, certificat `registry.crt`, etc.).

Concrètement, le `Dockerfile.agent` actuel (Maven, JDK 25, Trivy, kubectl, Helm, Cosign, SOPS, yq,
Firefox-ESR, jq) devient le **runtime du Forgejo Runner local**. C'est une **transposition 1-1** :

```yaml
# Exemple .forgejo/workflows/ci.yml — job de déploiement CD
deploy-stagingkub:
  runs-on: local-pc          # label du runner enregistré sur le PC
  needs: build-and-publish
  steps:
    - uses: actions/checkout@v4
    - name: Décrypter secrets SOPS
      run: |
        echo "$SOPS_AGE_KEY" | base64 -d > /tmp/age.key
        SOPS_AGE_KEY_FILE=/tmp/age.key sops -d rhDemo/secrets/secrets-stagingkub.yml > /tmp/secrets.yml
      env:
        SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY_B64 }}
    - name: Déployer sur KinD
      run: ./rhDemo/infra/stagingkub/scripts/deploy.sh ${{ needs.build-and-publish.outputs.tag }}
```

Le runner local **est** le même genre de processus qu'un agent Jenkins éphémère, **mais déclenché
par un événement Git** au lieu d'un build Jenkins.

---

## 10. Roadmap recommandée (scénario C, par étapes)

Étapes ordonnées pour réduire le risque :

### Étape 1 — Cohabitation (1-2 semaines)
- [ ] Installer un **Forgejo Runner self-hosted** sur le PC avec le label `local-pc`.
- [ ] Migrer en YAML **uniquement** les jobs *stateless* : `mvnw verify` (sans ephemere), OWASP
      Dependency-Check, SBOM CycloneDX, vérification SOPS, gitleaks.
- [ ] Garder Jenkins comme orchestrateur principal.
- [ ] Mesurer la stabilité des runs Codeberg (caches, queue, échecs intermittents).

### Étape 2 — Bascule SonarQube (1 semaine)
- [ ] Choisir : SonarCloud public, ou SonarQube CE auto-hébergé piloté par Forgejo Runner local.
- [ ] Réécrire le Quality Gate en polling REST si SonarQube reste local.

### Étape 3 — Migration ephemere + Selenium + ZAP (2-3 semaines)
- [ ] Porter les helpers Groovy (`waitForHealthcheck`, `generateTrivyReport`, etc.) en composite
      actions sous `.forgejo/actions/`.
- [ ] Réécrire les 13 stages ephemere en jobs Forgejo `runs-on: local-pc`.
- [ ] Conserver la **branche de validation** sur Jenkins en parallèle pour comparer les résultats.

### Étape 4 — Migration CD (1 semaine)
- [ ] Porter `Jenkinsfile-CD` en workflow Forgejo déclenché par `workflow_dispatch` ou par push d'un
      tag `v*.*.*`.
- [ ] Vérifier le passage de Copy Artifact → artifact Forgejo + cosign attest.

### Étape 5 — Retrait Jenkins (1 semaine)
- [ ] Arrêter `rhdemo-jenkins`, `rhdemo-jenkins-agent`, `rhdemo-docker-socket-proxy`, `rhdemo-sonarqube`,
      `rhdemo-sonarqube-db`.
- [ ] Conserver `kind-registry` (utilisé par le runner local).
- [ ] Mettre à jour la documentation (`README.md`, `CLAUDE.md`).
- [ ] Archiver `infra/jenkins-docker/` dans un sous-dossier `legacy/` pendant 3 mois.

**Effort total estimé : 6-8 semaines à temps partagé** (équivalent ≈ 15-20 jours-homme focalisés).

---

## 11. Conclusion : avis d'expert

**Le pipeline Jenkins actuel est de très bonne qualité** — il est rigoureux, sécurisé (SOPS,
Cosign, RBAC K8s, NetworkPolicies, scans multiples), bien documenté, et fait honneur à
l'ambition DevSecOps du projet.

**Pour autant, sa complexité dépasse la complexité réelle de l'application**. RHDemo est un CRUD
de 7 composants Vue.js et 3 contrôleurs Java. Maintenir 1 902 lignes de Groovy, 167 lignes de
Dockerfile.agent, 250 lignes de docker-compose Jenkins, 14 000 lignes de plugins (133 entrées dans
`plugins.txt`) pour cela est un **investissement disproportionné** dans l'outillage.

**Recommandation finale (deux trajectoires défendables) :**

### Trajectoire principale — Scénario C (Forgejo Actions)

1. **Migrer vers le scénario C** (Forgejo Actions partout + runner local self-hosted) en **6-8 semaines**.
2. **Conserver impérativement** la rigueur sécurité actuelle : SOPS hors workspace, secrets jamais
   loggés, signature Cosign clé privée locale, RBAC K8s.
3. **Ne pas migrer pour gagner du temps d'exécution** — le gain est ailleurs : moindre dette
   technique, alignement avec la philosophie « 100 % libre, Git-native », simplification opérationnelle.
4. **Garder Jenkins en parallèle** pendant les étapes 1-4 de la roadmap : un projet de cette taille
   ne peut pas se permettre une *big bang migration*. Le coût d'un retour arrière doit rester
   inférieur à une journée.
5. **Profiter de la migration pour resserrer la surface** : passer à BuildKit + cache mounts pour
   les builds Docker (gain ≈ 30-40 % sur la phase build), évaluer Podman rootless pour le runner
   local (élimine le risque DinD root).

Le pipeline Forgejo cible sera **plus court (~ 1 200 lignes YAML+shell vs ~ 2 800 lignes Groovy+Dockerfile+JCasC),
plus lisible, et davantage en phase avec l'esprit du projet**.

### Trajectoire alternative — Scénario F (Woodpecker self-hosted)

Si la **pureté FOSS et l'empreinte minimale** priment sur l'écosystème d'actions :

1. **Migrer vers Woodpecker self-hosted total** en **5-7 semaines** (légèrement moins long que C
   car YAML plus concis et moins de re-packaging d'helpers).
2. Avantage clé : **2 binaires Go ≈ 200 Mo RAM** remplacent Jenkins + agents + SonarQube + proxy
   (≈ 3-4 Go RAM). Le pipeline en YAML est **30-40 % plus court** qu'en Forgejo Actions.
3. Risque clé : **écosystème de plugins plus restreint**. Tout step non trivial doit être écrit en
   shell + image OCI dédiée. Pour ce projet qui fait déjà tout en shell+Maven dans le Jenkinsfile,
   c'est plutôt un trait positif.
4. Risque secondaire : **Woodpecker chez Codeberg est en mode legacy** (Codeberg pousse Forgejo
   Actions depuis 2024). Pour un usage purement local (Codeberg ne servant que de git), c'est sans
   conséquence.

### Comment choisir entre C et F ?

| Question | Si « oui » → C (Forgejo) | Si « oui » → F (Woodpecker) |
|---|---|---|
| Voulez-vous réutiliser des `actions/*` GitHub existantes ? | ✓ | |
| Voulez-vous publier les rapports HTML sur Forgejo Pages avec une intégration native ? | ✓ | |
| Recherchez-vous l'empreinte mémoire la plus faible possible ? | | ✓ |
| Préférez-vous l'absence totale de dépendance à un écosystème de tierces parties ? | | ✓ |
| Le YAML doit-il être le plus concis possible ? | | ✓ |
| Voulez-vous bénéficier des évolutions amont régulières et de la communauté la plus large ? | ✓ | |

**Pour ce projet**, les deux trajectoires sont défendables. **C reste recommandé par défaut**
(meilleur écosystème, plus de capacité d'évolution), **F est recommandé si vous voulez aller au bout
de la logique minimaliste/FOSS**. Les scénarios B, E (hybrides avec Jenkins) ne sont défendables
que comme étapes transitoires, pas comme cible long-terme. Les scénarios A (status quo) et D, G
(complexité excessive) sont à éviter.

---

## Annexes

### A. Exemple concret de workflow Forgejo Actions pour le CI build léger

```yaml
# .forgejo/workflows/ci-build.yml
name: CI Build & Tests
on:
  push:
    branches: [master, evolutions-post-*]
  pull_request:

jobs:
  build-and-test:
    runs-on: docker
    container:
      image: maven:3.9-eclipse-temurin-21
    steps:
      - uses: actions/checkout@v4
      - uses: actions/cache@v4
        with:
          path: ~/.m2/repository
          key: maven-${{ hashFiles('rhDemo/pom.xml') }}
      - name: Tests unitaires et intégration
        run: cd rhDemo && ./mvnw verify
      - uses: actions/upload-artifact@v4
        with:
          name: surefire-reports
          path: rhDemo/target/surefire-reports/

  owasp-dependency-check:
    runs-on: docker
    needs: build-and-test
    steps:
      - uses: actions/checkout@v4
      - name: OWASP Dependency-Check
        env:
          NVD_API_KEY: ${{ secrets.NVD_API_KEY }}
        run: cd rhDemo && ./mvnw org.owasp:dependency-check-maven:check -DnvdApiKey=$NVD_API_KEY
      - uses: actions/upload-artifact@v4
        with:
          name: dependency-check-report
          path: rhDemo/target/dependency-check-report.html
```

### B. Liste exhaustive des stages Jenkins CI (référence pour le mapping)

| # | Stage | Phase | Runner cible (scénario C) |
|---|---|---|---|
| 1 | Checkout | Prépa | tous |
| 2 | Lecture Version Maven | Prépa | tous |
| 3 | Init Variables Dynamiques (ZAP key) | Prépa | local-pc |
| 4 | Déchiffrement Secrets SOPS | Prépa | local-pc |
| 5 | Extraction secrets rhDemo | Prépa | local-pc |
| 6 | Configuration rhDemoInitKeycloak | Prépa | local-pc |
| 7 | Vérification Environnement | Build | tous |
| 8 | Compilation Maven | Build | docker (Codeberg) |
| 9 | Tests Unitaires + IT | Build | docker (Codeberg) |
| 10 | OWASP Dependency-Check | Build | docker (Codeberg) |
| 11 | SonarQube | Build | docker (SonarCloud) |
| 12 | Quality Gate | Build | docker |
| 13 | Couverture JaCoCo | Build | docker |
| 14 | Build Image Docker | Docker | local-pc |
| 15 | Nettoyage env ephemere | Ephemere | local-pc |
| 16 | Génération Certs SSL | Ephemere | local-pc |
| 17 | Démarrage docker-compose | Ephemere | local-pc |
| 18 | Connexion réseau ephemere | Ephemere | local-pc |
| 19 | Config Nginx HTTPS | Ephemere | local-pc |
| 20 | Attente DB | Ephemere | local-pc |
| 21 | Init Schema PostgreSQL | Ephemere | local-pc |
| 22 | Healthcheck Keycloak | Ephemere | local-pc |
| 23 | Init Keycloak | Ephemere | local-pc |
| 24 | Injection secrets container | Ephemere | local-pc |
| 25 | Démarrage app | Ephemere | local-pc |
| 26 | Healthcheck app | Ephemere | local-pc |
| 27 | Healthcheck Nginx HTTPS | Ephemere | local-pc |
| 28 | Trivy 5 images (parallèle) | Sécu | local-pc |
| 29 | SBOM CycloneDX | Sécu | local-pc |
| 30 | Démarrage OWASP ZAP | Tests E2E | local-pc |
| 31 | Tests Selenium | Tests E2E | local-pc |
| 32 | Génération Rapports HTML | Reports | local-pc |
| 33 | Tag + Push Image | Publish | local-pc |
| 34 | Signature Cosign | Publish | local-pc |
| 35 | Nettoyage Registry SNAPSHOT | Publish | local-pc |
| 36 | Archivage Artifacts | Archive | tous |

**Répartition cible :** 7 stages sur runner Codeberg partagé (≈ 20 %), 28 stages sur runner local-pc
(≈ 80 %). Cette répartition reflète bien la nature du projet : le **build est portable**, mais
**l'environnement d'exécution est intrinsèquement local**.

### C. Exemple de pipeline Woodpecker équivalent (scénario F)

```yaml
# .woodpecker/ci.yaml — extrait représentatif (scénario F : tout local)
when:
  - event: [push, pull_request]
  - branch: [master, evolutions-post-*]

# Variables partagées
variables:
  - &maven_image "maven:3.9-eclipse-temurin-21"
  - &jdk25_image "eclipse-temurin:25-jdk"

steps:
  build-test:
    image: *maven_image
    commands:
      - cd rhDemo && ./mvnw verify
    volumes:
      - rhdemo-maven-repository:/root/.m2

  owasp-check:
    image: *maven_image
    commands:
      - cd rhDemo && ./mvnw org.owasp:dependency-check-maven:check -DnvdApiKey=$NVD_API_KEY
    secrets: [nvd_api_key, ossindex_user, ossindex_password]
    depends_on: [build-test]

  sonar:
    image: sonarsource/sonar-scanner-cli:latest
    commands:
      - cd rhDemo && sonar-scanner -Dsonar.host.url=$SONAR_URL
    secrets: [sonar_token]
    depends_on: [build-test]

  decrypt-secrets:
    image: mozilla/sops:latest
    commands:
      - sops -d rhDemo/secrets/secrets-ephemere.yml > /tmp/secrets.yml
    secrets: [sops_age_key]
    depends_on: [build-test]

  build-image:
    image: docker:24-cli
    commands:
      - cd rhDemo && docker build -t rhdemo-api:$CI_COMMIT_SHA .
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on: [owasp-check, sonar]

  trivy-scan:
    image: aquasec/trivy:latest
    commands:
      - trivy image --severity CRITICAL --exit-code 1 rhdemo-api:$CI_COMMIT_SHA
    volumes:
      - rhdemo-trivy-cache:/root/.cache/trivy
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on: [build-image]

  cosign-sign:
    image: gcr.io/projectsigstore/cosign:latest
    commands:
      - cosign sign --key env://COSIGN_PRIVATE_KEY localhost:5000/rhdemo-api:$CI_COMMIT_SHA
    secrets: [cosign_private_key, cosign_password]
    depends_on: [trivy-scan]

  deploy-stagingkub:
    image: bitnami/kubectl:latest
    commands:
      - ./rhDemo/infra/stagingkub/scripts/deploy.sh $CI_COMMIT_SHA
    secrets: [kubeconfig_stagingkub]
    when:
      - event: tag
        ref: refs/tags/v*
    depends_on: [cosign-sign]
```

À comparer aux **1 902 lignes** du `Jenkinsfile-CI` actuel. L'exemple ci-dessus tient en ≈ 70 lignes
pour le squelette principal (les détails de la stack ephemere + ZAP + Selenium ajouteraient ≈ 150
lignes supplémentaires, restant **bien en deçà** de l'équivalent Groovy).

### D. Références

- Forgejo Actions documentation : <https://forgejo.org/docs/latest/user/actions/>
- act_runner (moteur Forgejo) : <https://code.forgejo.org/forgejo/runner>
- Compatibilité GitHub Actions : <https://docs.gitea.com/usage/actions/comparison>
- Woodpecker CI documentation : <https://woodpecker-ci.org/docs/intro>
- Codeberg CI (Woodpecker) : <https://docs.codeberg.org/ci/>
- Woodpecker plugins index : <https://woodpecker-ci.org/plugins>
- Comparaison Woodpecker vs Drone : <https://woodpecker-ci.org/docs/migrations#drone>
- SonarCloud Quality Gate API : <https://sonarcloud.io/web_api/api/qualitygates>
- Pipeline actuel : [Jenkinsfile-CI](../Jenkinsfile-CI), [Jenkinsfile-CD](../Jenkinsfile-CD)
- Action Renovate existante : [.forgejo/workflows/renovate.yml](../../.forgejo/workflows/renovate.yml)
