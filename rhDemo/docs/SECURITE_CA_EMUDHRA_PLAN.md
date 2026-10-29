---
statut: actif
verifie_le: 2026-10-29
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

# Compromission des CA intermédiaires eMudhra (CVE-2026-111943) : état et plan d'action

Document de suivi décrivant l'état courant de la remédiation. Les mesures sont datées ; l'historique du document est en bas de page.

## 1. Contexte

- **Incident** : les clés privées de 8 CA intermédiaires eMudhra (6 TLS, 2 signature de code) sont récupérables depuis les certificats publics (signalement du 2026-10-17). Quiconque en tire les clés peut émettre des certificats acceptés par les clients qui font confiance à la chaîne.
- **Chaîne concernée** : intermédiaires signés par *emSign ECC Root CA – G3* et cross-signés par *Comodo/Sectigo AAA Certificate Services*.
- **Identifiants** : CVE-2026-111943 est le correctif Go (denylist `crypto/x509`), pas une CVE de l'incident lui-même ; CVE-2026-91403 est la CVE Java ; Red Hat : bulletin RHSB-2026-012.
- **Exploitation** : attaquant en position réseau (MITM) face à un client qui valide contre un magasin public et ne contrôle pas la révocation.
- **Échéance** : Chrome retire la racine le 2026-10-27.
- **Correctifs** : Debian `ca-certificates` 20250419+deb13u1 (deb12u2 pour Debian 12), Ubuntu `20260816ubuntu0.*`, Alpine `20261020-r0`, Temurin `25.0.5+8` (voir section 3 bis). Ces versions viennent de sources secondaires (blogs, bulletin Red Hat) ; les empreintes des 8 intermédiaires et le rapport primaire Mozilla (bug 2083449) n'ont pas été consultés.

## 2. Principe d'évaluation de l'exposition

Un composant est exposé s'il ouvre des connexions TLS sortantes validées par un magasin public. Une connexion vers une CA privée ou auto-signée (Keycloak interne, registry local) n'est pas concernée. L'application est donc peu exposée ; le risque se concentre dans la chaîne CI/CD, qui télécharge des artefacts sur Internet.

| Composant | Exposition estimée | Raison |
| --- | --- | --- |
| Agent Jenkins | Élevée | Nombreux téléchargements (curl, NVD, bases Trivy, Maven, npm) |
| Contrôleur Jenkins | Moyenne | Update center et plugins |
| Scanners (dependency-check, Trivy, sonar-scanner) | Moyenne | Bases de vulnérabilités téléchargées : une base falsifiée masquerait des CVE |
| Stage builder du `Dockerfile` | Moyenne | Maven Central et npm |
| Hôte Linux | Moyenne | Pull d'images, Renovate |
| Application `rhdemo-api` | Faible | Seuls appels : Keycloak interne ; egress bloqué en stagingkub |
| Keycloak | Faible | Pas de SMTP ni LDAP |
| PostgreSQL, nginx, observabilité | Négligeable | Pas de connexion sortante vers Internet |
| ZAP, Selenium | Négligeable | Cible = environnement éphémère |
| Certificats serveur stagingkub | Aucune | Nous ne sommes pas client d'eMudhra |

## 3. État courant par composant

Mesures en lecture seule sur les images locales : version de `ca-certificates`, version du JDK, présence des racines emSign dans `cacerts` et dans le bundle PEM, puis test de contrôle (section 3 ter). Colonne « Mesure » : date de la dernière vérification.

| Composant | OS | `ca-certificates` | JDK | Racine G3 | Mesure | État |
| --- | --- | --- | --- | --- | --- | --- |
| Hôte | Ubuntu 24.04 | 20260816ubuntu0.24.04.1 | n/a | absente | 2026-10-23 | **corrigé** |
| Agent Jenkins | Debian 13 | 20250419+deb13u1 | Temurin 25.0.5+8 | retirée de `cacerts` et du bundle | 2026-10-29 | **corrigé** |
| Contrôleur Jenkins | Debian 13 | 20250419+deb13u1 | Temurin 25.0.5+8 | retirée de `cacerts` | 2026-10-29 | **corrigé** (image reconstruite, redémarrage à faire) |
| Nœud KinD | Debian 13 | 20250419+deb13u1 | n/a | retirée | 2026-10-23 | **corrigé** |
| Application `rhdemo-api` (`eclipse-temurin:25.0.3_9-jre-noble`) | Ubuntu 24.04 | 20260601~24.04.1 | Temurin 25.0.3 | présente | 2026-10-23 | non corrigé |
| Builder (`maven:3.9-eclipse-temurin-25-noble`) | Ubuntu 24.04 | 20260601~24.04.1 | Temurin 25.0.3 | présente | 2026-10-29 | non corrigé |
| Keycloak 26.7.x | RHEL 9.8 | RHEL (sans correctif) | JDK Red Hat 21.0.12.1 | présente | 2026-10-23 | non corrigé (acceptations Trivy, section 3 quater) |
| SonarQube 26.8.0 | Ubuntu 24.04 | 20260601~24.04.1 | 25.0.4 | présente | 2026-10-23 | non corrigé (image tierce) |
| ZAP `stable` | Debian 12 | 20230311+deb12u1 | 17.0.19 | présente, AAA aussi | 2026-10-23 | non corrigé (image tierce) |
| `postgres:18-alpine` | Alpine 3.24 | bundle de 119 certs | n/a | présente | 2026-10-23 | non corrigé (Alpine attendu `20261020-r0`) |

Les images `postgres`, `nginx` et `busybox` épinglées dans `values.yaml` ne sont pas présentes localement : leur bundle est supposé identique à celui d'Alpine 3.24.

## 3 bis. Correctif JDK : Temurin 25.0.5+8

- **Mécanisme** : Temurin `25.0.5+8` (publié le 2026-10-22) **retire les racines emSign G3, C3 et C1 de `cacerts`** (seule G1 reste ; 118 entrées contre 144 en 25.0.3). Le fichier `blocked.certs` n'est pas modifié (39 lignes). Le JDK Oracle utilise un autre mécanisme (ajout de hachages dans `blocked.certs`, version `25.0.5.0.2`) qui n'est pas nécessaire ici.
- **Portée** : le correctif est dans le JDK lui-même, indépendant du système d'exploitation de l'image et de la version de `ca-certificates`. Il est donc durable tant que les images utilisent Temurin 25.0.5 ou plus. Une image rebasée sur un Temurin plus ancien perd la protection : le test de contrôle sert à le détecter.
- **Disponibilité au 2026-10-29** : présent dans les images Debian (`jenkins/inbound-agent:latest-jdk25`, `jenkins/jenkins:2.580.2-lts-jdk25`). **Absent des images `eclipse-temurin` et `maven` Ubuntu (noble et resolute, 25.0.4.1) et Alpine (25.0.4.1)**, qui contiennent encore G3 : aucune image pour l'application et le builder n'est corrigée.

## 3 ter. Test de contrôle

Programme Java `HttpClient` (compilé ou lancé en mode source) ; hôtes `dv-g3b-emudhra.we-have-a-problem.com` (chaîne eMudhra G3) et `dv-g3b-aaa-emudhra.we-have-a-problem.com` (chaîne AAA). **Connexion acceptée = vulnérable.** Pour les magasins système : `curl`, `node` ou `wget`.

Résultats : agent et contrôleur (Temurin 25.0.5+8) **rejettent** la chaîne G3 (`PKIX path building failed`) ; builder (25.0.3) l'accepte. `curl` et Node de l'agent, `curl` du nœud KinD et de l'hôte rejettent les deux chaînes. La chaîne AAA est rejetée par tous les JDK Temurin, car la racine AAA est absente de leur `cacerts` : un échec sur cet hôte ne prouve pas un correctif, seul le test G3 est significatif pour un JDK.

## 3 quater. Acceptations temporaires de fixcve-auto (build #948)

Trivy a détecté l'incident sur l'image Keycloak (RHEL 9) et `fixcve-auto` a ajouté deux acceptations temporaires dans `.trivyignore.yaml` (journal : `SECURITY_ADVISORIES.md`, `fixcve-audit.md`), motif `[PENDING_UPSTREAM_FIX]` (aucun correctif publié dans la branche installée, CVSS 6.8 < 9.0) :

| CVE | Paquet (image Keycloak) | Version installée |
| --- | --- | --- |
| CVE-2026-114406 | `ca-certificates` (RHEL, magasin système) | 2025.2.80_v9.0.305-91.el9 |
| CVE-2026-91403 | `java-21-openjdk-headless` (JDK Red Hat) | 1:21.0.12.1.1-1.2.el9 |

Ces acceptations sont revérifiées à chaque cycle ; elles ne sont pas une correction et sont à retirer dès que Red Hat publie les paquets corrigés. Trivy détecte l'incident via les avis des distributions ; pour les JDK Temurin, dont le paquet n'est pas géré par le gestionnaire de paquets de l'image, l'étape de contrôle de la phase 3 reste nécessaire.

## 4. Actions

### Réalisées

| Action | Cible | Résultat |
| --- | --- | --- |
| Mise à jour de `ca-certificates` du nœud KinD, ajoutée à `init-stagingkub.sh` pour survivre à une recréation du cluster | Nœud KinD | 20250419+deb13u1, deux chaînes rejetées, CA du registry intacte |
| Base du `Dockerfile.agent` passée en `jenkins/inbound-agent:latest-jdk25`, épinglée par tag et digest ; couche `ca-certificates` en tête ; JDK unique (le Temurin 25 téléchargé à la main est supprimé) | Agent | Temurin 25.0.5+8, `curl` et Node rejettent les deux chaînes, JDK rejette G3 |
| Base du `Dockerfile.jenkins` passée en `jenkins/jenkins:2.580.2-lts-jdk25`, rebuild | Contrôleur | Temurin 25.0.5+8, G3 rejetée, `github.com` accepté, 107 plugins installés |
| Épinglage par digest de `docker-socket-proxy` et `zaproxy` | Jenkins, ZAP | Plus de tag flottant ; ZAP `stable` n'est pas corrigé en amont |

### Restantes

| # | Action | Cible | État |
| --- | --- | --- | --- |
| 1 | Redémarrer le contrôleur (`./start-jenkins.sh`) pour prendre l'image reconstruite, puis exécuter une CI complète : l'agent et le contrôleur n'ont été validés qu'en local | Jenkins | à faire |
| 2 | Rebuild de l'application et du builder avec `--pull` dès qu'une image Ubuntu Temurin 25.0.5+8 (ou plus) est publiée et embarque `ca-certificates` 20260816 ; Renovate proposera la montée de digest et de tag (`25.0.3_9` est épinglé dans `rhDemo/Dockerfile`) | App, builder | en attente d'image Temurin Ubuntu |
| 3 | Retirer les deux acceptations de `.trivyignore.yaml` quand Red Hat publie `ca-certificates` et `java-21-openjdk` corrigés | Keycloak | en attente d'un correctif amont |
| 4 | Image `zaproxy` dérivée avec `ca-certificates` `~deb12u2` si l'amont tarde ; suivre aussi SonarQube (JDK 25.0.4) | ZAP, SonarQube | ouvert |
| 5 | Laisser Renovate proposer les montées de digest Alpine (`20261020-r0`), Keycloak, nginx, postgres, puis refaire le test de contrôle | Autres images | suivi continu |
| 6 | Après chaque rebuild, refaire le test de contrôle (section 3 ter) | Tous JDK | permanent |

### Durcissement (à faire)

- Récupérer les empreintes des 8 intermédiaires (rapport Mozilla) et décider d'une denylist de configuration (`jdk.security.provider.disallowedCerts` à valider) ou du retrait de G3 des trust stores qui n'en ont pas besoin, si l'application et le builder restent sans image corrigée.
- Truststore minimal sur l'agent (domaines réellement joints) plutôt que le bundle complet.
- Vérification d'intégrité (checksum, signature) des binaires téléchargés dans `Dockerfile.agent` : `releases/latest`, `stable.txt`.
- Filtrage egress de l'agent vers une liste de domaines.

### Process et documentation (à faire)

- Étape de contrôle dans `Jenkinsfile-CI` : échec si le test de contrôle G3 réussit à se connecter depuis une image construite.
- Entrée dans `SECURITY_ADVISORIES.md` et runbook « compromission de CA » : les outils actuels (Trivy, OWASP DC) ne détectent pas ce type de vulnérabilité pour les JDK Temurin.
- Vérifier que les PR Renovate de digest sont mergées.

## Historique du document

- 2026-10-23 : création, mesure initiale, phase 1 (nœud KinD, agent, contrôleur, épinglages), acceptations `fixcve-auto`.
- 2026-10-29 : agent et contrôleur sur Temurin 25.0.5+8 (correctif par retrait des racines emSign de `cacerts`) ; réécriture du document autour de l'état courant ; retrait du contournement par vérification de révocation CRL (non viable, il rejetait `github.com` et `ghcr.io`).
