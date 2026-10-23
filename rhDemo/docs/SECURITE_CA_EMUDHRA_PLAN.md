---
statut: actif
verifie_le: 2026-10-23
sources:
  - rhDemo/Dockerfile
  - rhDemo/infra/jenkins-docker/Dockerfile.agent
  - rhDemo/infra/jenkins-docker/Dockerfile.jenkins
  - rhDemo/infra/jenkins-docker/docker-compose.zap.yml
  - rhDemo/infra/stagingkub/helm/rhdemo/values.yaml
  - rhDemo/infra/stagingkub/kind-config.yaml
  - rhDemo/Jenkinsfile-CI
  - rhDemo/.trivyignore.yaml
---

# Compromission des CA intermédiaires eMudhra (CVE-2026-111943) : analyse d'impact et plan d'action

Document de suivi, enrichi au fil de l'avancement. L'état de chaque phase est indiqué dans son titre. Les constats sont datés ; l'historique des changements du document est en bas de page.

## 1. Contexte

- **Incident** : les clés privées de 8 CA intermédiaires eMudhra (6 TLS, 2 signature de code) sont récupérables depuis les certificats publics (signalement du 2026-10-17). Quiconque en tire les clés peut émettre des certificats acceptés par les clients qui font confiance à la chaîne.
- **Chaîne concernée** : intermédiaires signés par *emSign ECC Root CA – G3* et cross-signés par *Comodo/Sectigo AAA Certificate Services*.
- **CVE-2026-111943** : correctif Go (denylist `crypto/x509`, Go 1.27.3 et 1.26.10), pas une CVE de l'incident lui-même. Les correctifs OS et runtimes ont d'autres identifiants (Red Hat : bulletin RHSB-2026-012).
- **Exploitation** : attaquant en position réseau (MITM) face à un client qui valide contre un magasin public et ne contrôle pas la révocation.
- **Échéance** : Chrome retire la racine le 2026-10-27.
- **Correctifs annoncés** (SOCRadar, non revérifiés sur les sources primaires) : Debian `ca-certificates` 20250419+deb13u1 (deb12u2 pour Debian 12), Ubuntu `20260816ubuntu0.*`, Alpine `20261020-r0`, Node 22.23.4 / 24.22.1 / 26.12.1, certifi 2026.10.19. Rien trouvé pour OpenJDK ni Keycloak.

Les sources sont secondaires (blogs, bulletin Red Hat). Le rapport primaire Mozilla (bug 2083449) n'a pas été lu, et les empreintes des 8 intermédiaires ne sont pas connues. À compléter en phase 2.

## 2. Principe d'évaluation de l'exposition

Un composant est exposé s'il ouvre des connexions TLS sortantes validées par un magasin public. Une connexion vers une CA privée ou auto-signée (Keycloak interne, registry local) n'est pas concernée. L'application est donc peu exposée ; le risque se concentre dans la chaîne CI/CD, qui télécharge des artefacts sur Internet.

| Composant | Exposition estimée | Raison |
| --- | --- | --- |
| Agent Jenkins | Élevée | Nombreux téléchargements (curl, NVD, bases Trivy, Maven, npm), tag de base non épinglé |
| Contrôleur Jenkins | Moyenne | Update center et plugins |
| Scanners (dependency-check, Trivy, sonar-scanner) | Moyenne | Bases de vulnérabilités téléchargées : une base falsifiée masquerait des CVE |
| Stage builder du `Dockerfile` | Moyenne | Maven Central et npm |
| Hôte Linux | Moyenne | Pull d'images, Renovate |
| Application `rhdemo-api` | Faible | Seuls appels : Keycloak interne ; egress bloqué en stagingkub |
| Keycloak | Faible | Pas de SMTP ni LDAP |
| PostgreSQL, nginx, observabilité | Négligeable | Pas de connexion sortante vers Internet |
| ZAP, Selenium | Négligeable | Cible = environnement éphémère |
| Certificats serveur stagingkub | Aucune | Nous ne sommes pas client d'eMudhra |

## 3. Phase 0 : mesure de l'exposition réelle (faite le 2026-10-23)

Méthode : lancement en lecture seule de chaque image locale avec un script qui relève la version de `ca-certificates`, la version du JDK et la présence d'*emSign* et *AAA* dans `cacerts` Java et dans le bundle PEM. Le script est dans le répertoire temporaire de la session, non versionné.

| Image / cible | OS | `ca-certificates` | JDK | emSign dont **G3** dans `cacerts` / bundle | AAA |
| --- | --- | --- | --- | --- | --- |
| Hôte (Ubuntu 24.04.5) | Ubuntu 24.04 | 20260816ubuntu0.24.04.1 | n/a | **G3 absent** (C3, C1, G1 présents) | absent |
| App `rhdemo-api` (build 946), `eclipse-temurin:25.0.3_9-jre-noble` | Ubuntu 24.04 | 20260601~24.04.1 | 25.0.3 | **oui** | absent |
| Builder `maven:3.9-eclipse-temurin-25-noble` | Ubuntu 24.04 | 20260601~24.04.1 | 25.0.3 | **oui** | absent |
| Keycloak 26.7.2 et 26.7.3 | RHEL 9.8 | n/a | 21.0.12.1 | **oui** | absent |
| `postgres:18-alpine` (Alpine 3.24) | Alpine | bundle de 119 certs | n/a | **oui** (bundle) | absent |
| Contrôleur Jenkins `rhdemo-jenkins` | Debian 13 | 20250419 (**non corrigé**) | 25.0.3 | **oui** | **oui** (bundle) |
| Agent Jenkins `rhdemo-jenkins-agent` | Debian 13 | 20250419 (**non corrigé**) | 25.0.4 | **oui** | **oui** (bundle) |
| ZAP `stable` | Debian 12 | 20230311+deb12u1 (**non corrigé**) | 17.0.19 | **oui** | **oui** |
| SonarQube 26.8.0 | Ubuntu 24.04 | 20260601~24.04.1 | 25.0.4 | **oui** | absent |
| Nœud KinD `rhdemo-control-plane` | Debian | 20250419 (**non corrigé**) | n/a | **oui** | **oui** |

Les images Ubuntu et Alpine locales datent d'avant les correctifs (`ca-certificates` Ubuntu 20260601, correctif attendu 20260816 ; Alpine, correctif attendu 20261020-r0). Aucun JDK ne contient d'AAA dans son `cacerts`, mais tous contiennent encore *emSign ECC Root CA – G3*, la racine qui signe les intermédiaires compromis.

### Constats

1. **Aucune image locale n'est corrigée.** Toutes contiennent encore la racine G3, donc toutes feraient confiance à un certificat forgé avec une clé compromise.
2. **L'hôte est déjà à jour** (G3 absent). C'est le seul composant corrigé.
3. **Debian (contrôleur, agent, ZAP, nœud KinD)** : `ca-certificates` est à la version précédant le correctif, et le bundle contient en plus la racine AAA.
4. **JDK** : voir la section 3 bis. Le correctif Java n'est pas un retrait de G3 de `cacerts` ; il n'est pas encore disponible dans Temurin. **Keycloak** (JDK Red Hat) : à vérifier auprès de Red Hat (phase 2).
5. **Le `Dockerfile.agent` n'épingle pas sa base** (`jenkins/inbound-agent:latest-jdk21`) : aucun correctif ne sera repris sans reconstruction explicite. Idem pour `tecnativa/docker-socket-proxy:latest` et `zaproxy:stable`.
6. **Écarts à noter** : le JDK de l'agent est en 25 alors que le fichier source indique `jdk21` (image locale issue d'une autre base ou d'un tag déplacé) ; Keycloak est en JDK 21 dans l'image 26.7.x. Ne change pas l'analyse, mais à corriger dans la doc `JENKINS_AGENTS_EPHEMERES.md` si l'écart est confirmé.

## 3 bis. Correctif OpenJDK / Temurin (vérifié le 2026-10-23)

- **CVE Java** : CVE-2026-91403 (la CVE-2026-111943 est celle de Go).
- **Version corrigée** : `25.0.5.0.2` (commit « 8395142: CA Enhancements »). Le tag `jdk-25.0.5+8` **ne contient pas** le correctif ; Oracle le liste comme affecté (source : article de test lilting.ch, notes Oracle non lisibles : HTTP 403).
- **Mécanisme** : ajout de 48 hachages dans `lib/security/blocked.certs` (39 à 87 lignes). Les racines emSign G3 et AAA **restent dans `cacerts`** : l'absence de G3 n'est donc pas un critère de réussite pour un JDK.
- **Disponibilité Temurin** : au 2026-10-23, aucun tag `eclipse-temurin:25.0.5_8-*` sur Docker Hub ; `25-jre-noble` date du 2026-10-17. Pas d'image corrigée disponible. Les JDK Oracle ont été publiés le 2026-10-21.
- **Contournement vérifié par un tiers** (Temurin 25.0.4.1, macOS) : `-Dcom.sun.net.ssl.checkRevocation=true -Dcom.sun.security.enableCRLDP=true` fait rejeter la chaîne eMudhra (`CA_COMPROMISE`).
- **Test de contrôle** : hôtes `dv-g3b-emudhra.we-have-a-problem.com` (racine eMudhra) et `dv-g3b-aaa-emudhra.we-have-a-problem.com` (racine AAA). Une réponse 200 = JDK vulnérable ; une erreur = protégé. Un JDK sans AAA dans `cacerts` (cas de Temurin) échoue de toute façon sur la seconde chaîne, sans que cela prouve un correctif.

## 3 ter. Test de contrôle sur les images locales (fait le 2026-10-23)

Méthode : programme Java `HttpClient` (compilé `--release 17`, monté dans chaque conteneur) pour les JDK ; `curl`, `node` ou `wget` pour les magasins système. Hôtes : chaîne eMudhra (G3) et chaîne Sectigo/AAA de `we-have-a-problem.com`. **Accepté = vulnérable.** Pour les JDK, deuxième passe avec `-Dcom.sun.net.ssl.checkRevocation=true -Dcom.sun.security.enableCRLDP=true`.

| Cible | Chaîne eMudhra (G3) | Chaîne AAA | Avec vérif. de révocation |
| --- | --- | --- | --- |
| JDK 25.0.3 : app, builder, contrôleur Jenkins | **acceptée** | rejetée (AAA absente de `cacerts`) | G3 **rejetée** (`CA_COMPROMISE`) |
| JDK 25.0.4 : agent Jenkins, SonarQube | **acceptée** | rejetée | G3 **rejetée** |
| JDK 21.0.12.1 : Keycloak 26.7.3 | **acceptée** | rejetée | G3 **rejetée** |
| JDK 17.0.19 : ZAP | **acceptée** | **acceptée** | les deux **rejetées** |
| Agent Jenkins : `curl` et Node 20.19.2 | **acceptée** | **acceptée** | non applicable |
| Nœud KinD : `curl` | **acceptée** | **acceptée** | non applicable |
| Alpine (postgres) : `wget` | **acceptée** | rejetée | non applicable |
| Hôte : `curl` | rejetée (exit 60) | rejetée (exit 60) | non applicable |

Conclusions :
- **Aucun JDK local n'est protégé par défaut** (cohérent avec l'absence de `blocked.certs` à jour). Le contrôle des certificats `Oracle 25.0.5.0.2` reste à refaire quand l'image sera disponible.
- **La vérification de révocation CRL fonctionne** sur tous les JDK testés, y compris Keycloak (JDK 21), et rejette la chaîne avec `CA_COMPROMISE`. Le contournement 1.7 est validé techniquement ; l'impact (latence, CRL injoignable) reste à mesurer.
- **Les plus exposés** sont ceux qui acceptent les deux chaînes : ZAP, l'agent (`curl`, Node), le nœud KinD. Ils s'appuient sur le bundle Debian non corrigé.
- **Les JDK hors Debian ne font pas confiance à la chaîne AAA** (racine absente de leur `cacerts`) : un échec sur cet hôte ne prouve pas un correctif.
- **L'hôte est protégé** pour `curl`. Java n'est pas installé sur l'hôte.
- Keycloak n'a pas été testé avec `curl` ou autre : il n'en a pas besoin pour ses connexions Java.

## 3 quater. Impact de la vérification de révocation (mesuré le 2026-10-23)

JDK 25.0.4 de l'agent, 17 endpoints utilisés par la CI (Maven Central, npm, NVD, Adoptium, GitHub, ghcr.io, dl.k8s.io, Docker Hub, quay.io, Jenkins update center, OSS Index, Trivy, Helm). Défaut : 17 acceptés en 5 s. Avec `-Dcom.sun.net.ssl.checkRevocation=true -Dcom.sun.security.enableCRLDP=true` : 14 acceptés en 6 s, **3 rejetés** (`github.com`, `ghcr.io`, `api.github.com` : « Could not determine revocation status »). Le temps ajouté est faible, mais le mode est strict (pas de repli si le statut est indéterminable) et casserait les téléchargements GitHub de la CI. À ne pas généraliser ; privilégier l'ajout des hachages à `blocked.certs` dès que le JDK corrigé est disponible.

## 3 quinquies. Détection et acceptations automatiques (fixcve-auto, build #948)

Trivy a détecté l'incident sur l'image Keycloak (RHEL 9) et `fixcve-auto` a ajouté deux acceptations temporaires dans `.trivyignore.yaml` (journal : `SECURITY_ADVISORIES.md`, `fixcve-audit.md`), motif `[PENDING_UPSTREAM_FIX]` (critère B : aucun correctif publié dans la branche installée, CVSS 6.8 < 9.0) :

| CVE | Paquet (image Keycloak) | Version installée |
| --- | --- | --- |
| CVE-2026-114406 | `ca-certificates` (RHEL, magasin système) | 2025.2.80_v9.0.305-91.el9 |
| CVE-2026-91403 | `java-21-openjdk-headless` (JDK Red Hat) | 1:21.0.12.1.1-1.2.el9 |

Ces acceptations sont revérifiées à chaque cycle ; elles ne sont **pas** une correction. À retirer dès que Red Hat publie les paquets corrigés (action 1.9). Elles montrent aussi que Trivy détecte l'incident via les avis des distributions : l'étape de contrôle de la phase 3 reste utile pour les JDK Temurin, dont le paquet n'est pas géré par le gestionnaire de paquets de l'image.

## 4. Plan d'action

### Phase 0 : mesure (faite, voir section 3)

### Phase 1 : corrections prioritaires (exécutée le 2026-10-23, reste 1.3 redémarrage, 1.4 attente Temurin)

| # | Action | Cible | État |
| --- | --- | --- | --- |
| 1.1 | Mettre à jour `ca-certificates` du nœud KinD (`apt` dans le conteneur, ou recréation du cluster avec une image `kindest/node` plus récente) | Nœud KinD | fait le 2026-10-23 : nœud corrigé (20250419+deb13u1), deux chaînes rejetées, CA du registry intacte ; correction ajoutée à `init-stagingkub.sh` pour survivre à une recréation du cluster |
| 1.2 | Épingler la base du `Dockerfile.agent` par tag et digest, ajouter la mise à jour de `ca-certificates`, rebuild `--no-cache --pull` | Agent | fait : base épinglée par digest, couche `ca-certificates` ajoutée, image reconstruite et testée (`curl` et Node rejettent les deux chaînes) ; JDK toujours vulnérable |
| 1.3 | Rebuild du contrôleur Jenkins (`--no-cache --pull`) | Contrôleur | image reconstruite et testée (`ca-certificates` corrigé) ; **redémarrage du contrôleur à faire** via `start-jenkins.sh` |
| 1.4 | Rebuild de l'image app et du builder avec `--pull` quand Temurin publie une image `25.0.5.0.2` (ou équivalent) **et** embarquant `ca-certificates` Ubuntu 20260816 ; pas de contournement viable en attendant (voir 1.7) | App, builder | en attente d'image Temurin |
| 1.5 | Laisser Renovate proposer les montées de digest (Alpine, Keycloak, nginx, postgres) | Autres images | rien à faire ici : suivi continu des PR Renovate |
| 1.6 | Épingler `docker-socket-proxy` et `zaproxy` par digest | Jenkins, ZAP | fait : `docker-socket-proxy` et `zaproxy` épinglés par digest ; ZAP `stable` n'est pas corrigé en amont (`~deb12u1`, les deux chaînes acceptées), point ouvert |
| 1.7 | Contournement JVM : ajouter `-Dcom.sun.net.ssl.checkRevocation=true -Dcom.sun.security.enableCRLDP=true` aux JVM qui sortent vers Internet (agent, builder, contrôleur Jenkins) ; mesurer l'impact (latence, échecs si CRL injoignable) avant généralisation | Agent, builder, contrôleur | **non viable globalement** : mesuré, la révocation stricte rejette `github.com`, `ghcr.io` et `api.github.com` (statut indéterminable) ; à réserver à des JVM ciblées |
| 1.8 | Test de contrôle (hôtes `we-have-a-problem.com`) dans chaque JDK avant/après, puis intégré en phase 3 | Tous JDK | fait une première fois (section 3 ter), à refaire après chaque rebuild |
| 1.9 | Surveiller la publication des paquets Red Hat (`ca-certificates`, `java-21-openjdk`) et retirer les deux acceptations de `.trivyignore.yaml` (CVE-2026-114406, CVE-2026-91403) | Keycloak | en attente de correctif amont |

### Phase 2 : durcissement (à faire, non commencée)

- Suivre la publication de Temurin `25.0.5.0.2` (et du JDK Red Hat pour Keycloak, du JDK embarqué par SonarQube) ; alternative si le délai se prolonge : copier les 48 hachages de `blocked.certs` du JDK corrigé dans un `blocked.certs` surchargé dans nos images.
- Récupérer les empreintes des 8 intermédiaires (rapport Mozilla) et décider d'une denylist de configuration (`jdk.security.provider.disallowedCerts` à valider, ou retrait de G3 des trust stores des images qui n'en ont pas besoin).
- Truststore minimal sur l'agent (domaines réellement joints) plutôt que le bundle complet.
- Vérification de révocation : stricte et globale non viable (section 3 quater) ; étudier un mode ciblé (JVM qui ne joignent pas GitHub) ou un repli souple.
- Vérification d'intégrité (checksum, signature) des binaires téléchargés dans `Dockerfile.agent` : `releases/latest`, `stable.txt`.
- Filtrage egress de l'agent vers une liste de domaines.

### Phase 3 : process et documentation (à faire, non commencée)

- Étape de contrôle dans `Jenkinsfile-CI` : échec si le test de contrôle (section 3 bis) réussit à se connecter depuis une image construite.
- Entrée dans `SECURITY_ADVISORIES.md` et runbook « compromission de CA ». Les outils actuels (Trivy, OWASP DC) ne détectent pas ce type de vulnérabilité.
- Vérifier avant le 2026-10-27 que les PR Renovate de digest sont mergées.

### Ordre de priorité

Constat phase 0 → nœud KinD, agent et contrôleur Jenkins → app et builder → autres images via Renovate → phases 2 et 3.

## 5. Points ouverts

- **Redémarrage du contrôleur Jenkins** à faire par `./start-jenkins.sh` pour prendre l'image reconstruite (l'agent est pris en compte dès le prochain agent éphémère).
- **JDK vulnérables** : app, builder, contrôleur, agent, SonarQube, Keycloak (aucune image corrigée disponible). Pour Keycloak, la CVE est suivie par deux acceptations temporaires de `fixcve-auto` (section 3 quinquies).
- **ZAP `stable`** : `ca-certificates` `~deb12u1`, deux chaînes acceptées ; envisager une image dérivée avec `ca-certificates` `~deb12u2` si l'amont tarde.
- **Alpine (postgres)**, **app et builder (Ubuntu)** : magasin système à rafraîchir par Renovate/rebuild (`ca-certificates` Alpine `20261020-r0`, Ubuntu `20260816`).
- **Modifications non vérifiées en pipeline** : les changements de `Dockerfile.agent`, `Dockerfile.jenkins` et `init-stagingkub.sh` ne sont testés qu'en local (build et test de contrôle), pas encore par une exécution CI complète.
- Disponibilité d'une image Temurin 25.0.5.0.2, et version du JDK Red Hat embarqué par Keycloak : à surveiller.
- Empreintes exactes des 8 intermédiaires : non obtenues.
- Image `postgres`, `nginx` et `busybox` épinglées dans `values.yaml` (non présentes localement) : contenu du bundle non mesuré, supposé identique à Alpine 3.24 (G3 présent).

## Historique du document

- 2026-10-23 : création, analyse d'impact et résultats de la phase 0.
- 2026-10-23 : ajout de la section 3 bis : Temurin 25.0.5+8 ne contient pas le correctif (disponible en 25.0.5.0.2, via `blocked.certs`).
- 2026-10-23 : ajout de la section 3 ter (test de contrôle sur les images locales).
- 2026-10-23 : phase 1 exécutée ; section 3 quater (impact de la révocation : non viable globalement) ; points ouverts réécrits.
- 2026-10-23 : section 3 quinquies (acceptations `fixcve-auto` build #948) et action 1.9.
