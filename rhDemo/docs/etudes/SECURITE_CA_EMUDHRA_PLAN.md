---
statut: historique
verifie_le: 2026-11-19
sources:
  - rhDemo/Dockerfile
  - rhDemo/infra/jenkins-docker/Dockerfile.agent
  - rhDemo/infra/jenkins-docker/Dockerfile.jenkins
  - rhDemo/infra/jenkins-docker/docker-compose.yml
  - rhDemo/infra/jenkins-docker/docker-compose.zap.yml
  - rhDemo/infra/stagingkub/helm/rhdemo/values.yaml
  - rhDemo/infra/stagingkub/kind-config.yaml
  - rhDemo/Jenkinsfile-CI
  - rhDemo/.trivyignore.yaml
---

# Compromission des CA intermédiaires eMudhra (CVE-2026-111943) : bilan de la remédiation

**Incident clos le 2026-11-19.** Tous les composants exposés sont corrigés ; plus aucune version corrective n'est attendue. Ce document est figé : il trace l'incident, les mesures et l'état final constaté. Les versions citées sont celles du 2026-11-19 ; l'état courant des images se lit dans les fichiers sources.

## 1. Contexte

- **Incident** : les clés privées de 8 CA intermédiaires eMudhra (6 TLS, 2 signature de code) sont récupérables depuis les certificats publics (signalement du 2026-10-17). Quiconque en tire les clés peut émettre des certificats acceptés par les clients qui font confiance à la chaîne.
- **Chaîne concernée** : intermédiaires signés par *emSign ECC Root CA – G3* et cross-signés par *Comodo/Sectigo AAA Certificate Services*.
- **Identifiants** : CVE-2026-111943 est le correctif Go (denylist `crypto/x509`), pas une CVE de l'incident lui-même ; CVE-2026-91403 est la CVE Java ; Red Hat : bulletin RHSB-2026-012.
- **Exploitation** : attaquant en position réseau (MITM) face à un client qui valide contre un magasin public et ne contrôle pas la révocation.
- **Échéance** : Chrome retire la racine le 2026-10-27.
- **Correctifs** : Debian `ca-certificates` 20250419+deb13u1 (deb12u2 pour Debian 12), Ubuntu `20260816ubuntu0.*`, Alpine `20261020-r0`, Temurin `25.0.5+8` (section 3). Ces versions viennent de sources secondaires (blogs, bulletin Red Hat) ; les empreintes des 8 intermédiaires et le rapport primaire Mozilla (bug 2083449) n'ont pas été consultés.

## 2. Principe d'évaluation de l'exposition

Un composant est exposé s'il ouvre des connexions TLS sortantes validées par un magasin public. Une connexion vers une CA privée ou auto-signée (Keycloak interne, registry local) n'est pas concernée. L'application est donc peu exposée ; le risque se concentrait dans la chaîne CI/CD, qui télécharge des artefacts sur Internet.

| Composant | Exposition estimée | Raison |
| --- | --- | --- |
| Agent Jenkins | Élevée | Nombreux téléchargements (curl, NVD, bases Trivy, Maven, npm) |
| Contrôleur Jenkins | Moyenne | Update center et plugins |
| Scanners (dependency-check, Trivy, SonarQube) | Moyenne | Bases de vulnérabilités téléchargées : une base falsifiée masquerait des CVE |
| Stage builder du `Dockerfile` | Moyenne | Maven Central et npm |
| Hôte Linux | Moyenne | Pull d'images, Renovate |
| Application `rhdemo-api` | Faible | Seuls appels : Keycloak interne ; egress bloqué en stagingkub |
| Keycloak | Faible | Pas de SMTP ni LDAP |
| PostgreSQL, nginx, observabilité | Négligeable | Pas de connexion sortante vers Internet |
| ZAP, Selenium | Négligeable | Cible = environnement éphémère |
| Certificats serveur stagingkub | Aucune | Nous ne sommes pas client d'eMudhra |

## 3. Mécanisme du correctif JDK : Temurin 25.0.5+8

- Temurin `25.0.5+8` (publié le 2026-10-22) **retire les racines emSign G3, C3 et C1 de `cacerts`** (seule G1 reste ; 118 entrées contre 144 en 25.0.3). Le fichier `blocked.certs` n'est pas modifié. Le JDK Oracle utilise un autre mécanisme (hachages dans `blocked.certs`, version `25.0.5.0.2`).
- Le correctif est dans le JDK, indépendant du système d'exploitation de l'image : il est durable tant que les images restent en Temurin 25.0.5 ou plus. Une image rebasée sur un Temurin plus ancien perd la protection.
- Calendrier : présent dès le 2026-10-29 dans les images Jenkins Debian ; `eclipse-temurin:25.0.5_8-jre-noble` publiée début novembre ; image Maven (`3.10.0-eclipse-temurin-25-noble`) et SonarQube 26.11 publiées le 2026-11-12.

## 4. Test de contrôle

Programme Java `HttpClient` (compilé ou lancé en mode source) ; hôtes `dv-g3b-emudhra.we-have-a-problem.com` (chaîne eMudhra G3) et `dv-g3b-aaa-emudhra.we-have-a-problem.com` (chaîne AAA). **Connexion acceptée = vulnérable.** Pour les magasins système : `curl`, `node` ou `wget`. Contrôle hors ligne équivalent : `keytool -list -cacerts` ne doit plus lister `emsign_ecc_root_ca__g3`, et le magasin système ne doit plus contenir `emSign_ECC_Root_CA_-_G3.pem`.

La chaîne AAA est rejetée par tous les JDK Temurin, la racine AAA étant absente de leur `cacerts` : un échec sur cet hôte ne prouve pas un correctif, seul le test G3 est significatif pour un JDK.

## 5. État final par composant (2026-11-19)

| Composant | `ca-certificates` | JDK | Racine G3 | État |
| --- | --- | --- | --- | --- |
| Hôte (Ubuntu 24.04) | 20260816ubuntu0.24.04.1 | n/a | absente | **corrigé** (2026-10-23) |
| Nœud KinD (Debian 13) | 20250419+deb13u1 | n/a | retirée | **corrigé** (réappliqué par `init-stagingkub.sh`) |
| Agent Jenkins (`inbound-agent:latest-jdk25`) | 20250419+deb13u1 | Temurin 25.0.5+8 | retirée | **corrigé** (test de contrôle G3 rejeté) |
| Contrôleur Jenkins (`jenkins:2.580.2-lts-jdk25`) | 20250419+deb13u1 | Temurin 25.0.5+8 | retirée | **corrigé** (test de contrôle G3 rejeté) |
| Application (`eclipse-temurin:25.0.5_8-jre-noble`) | 20260816ubuntu0.24.04.1 | Temurin 25.0.5+8 | retirée | **corrigé** (test de contrôle G3 rejeté) |
| Builder (`maven:3.10.0-eclipse-temurin-25-noble`) | 20260816ubuntu0.24.04.2 | Temurin 25.0.5 | retirée | **corrigé** le 2026-11-19 (Maven 3.9.16 → 3.10.0, épinglé par digest) |
| SonarQube (`26.11.0.134175-community`) | 20260816ubuntu0.24.04.2 | Temurin 25.0.5 | retirée | **corrigé** le 2026-11-19 (26.10 → 26.11, épinglé par digest) |
| ZAP (`zap-stable:2.17.0`) | 20250419~deb12u2 | OpenJDK 17.0.21 (Debian, magasin système) | absente | **corrigé** en amont |
| nginx (`1.31.8-alpine-slim`) | bundle 20261020-r0 | n/a | absente | **corrigé** en amont |
| Keycloak 26.8.1 (RHEL 9) | corrigé depuis 26.8.1 | JDK Red Hat 21.0.13 | magasin système corrigé | **risque accepté** (section 6) |
| `postgres:18.4-alpine3.22` | bundle 20260413-r0 (145 certificats) | n/a | présumée présente | **non corrigé, sans objet** : aucune connexion TLS sortante ; corrigé par la prochaine montée de l'image (Renovate) |

## 6. Keycloak : CVE-2026-91403 acceptée de façon permanente

`fixcve-auto` (build #948) avait accepté temporairement deux paquets de l'image Keycloak, motif `[PENDING_UPSTREAM_FIX]` (CVSS 6.8 < 9.0) : `ca-certificates` (CVE-2026-114406), retirée le 2026-11-05 avec Keycloak 26.8.1, et `java-21-openjdk-headless` (CVE-2026-91403).

Le 2026-11-19, Red Hat classe CVE-2026-91403 en `will_not_fix` : aucun RPM correctif ne viendra et le motif d'attente n'a plus de sens. L'acceptation devient permanente dans `.trivyignore.yaml` : Keycloak n'ouvre aucune connexion TLS vers une CA publique (ni SMTP, ni LDAP, ni fournisseur d'identité externe), et le JDK Red Hat s'appuie sur le magasin système, corrigé depuis 26.8.1. À revoir si Keycloak reçoit un flux sortant vers Internet.

## 7. Actions réalisées

| Date | Action | Cible |
| --- | --- | --- |
| 2026-10-23 | `ca-certificates` mis à jour, ajouté à `init-stagingkub.sh` | Nœud KinD |
| 2026-10-23 | Épinglage par digest de `docker-socket-proxy` et `zaproxy` | Jenkins, ZAP |
| 2026-10-29 | Base `jenkins/inbound-agent:latest-jdk25` (tag et digest), JDK unique | Agent |
| 2026-10-29 | Base `jenkins/jenkins:2.580.2-lts-jdk25`, rebuild et redémarrage | Contrôleur |
| 2026-11-05 | Base `eclipse-temurin:25.0.5_8-jre-noble` (digest) | Application |
| 2026-11-05 | Keycloak 26.8.1 : acceptation `ca-certificates` retirée | Keycloak |
| 2026-11-19 | Builder `maven:3.10.0-eclipse-temurin-25-noble` (digest) | Builder |
| 2026-11-19 | SonarQube 26.11 (digest) | SonarQube |
| 2026-11-19 | CVE-2026-91403 passée en acceptation permanente (`will_not_fix`) | Keycloak |

## 8. Suites non réalisées

Pistes identifiées pendant l'incident, non nécessaires à sa clôture et non engagées. Elles relèvent d'une décision séparée :

- étape de contrôle G3 dans `Jenkinsfile-CI` (échec si une image construite accepte la chaîne G3) et runbook « compromission de CA » : Trivy et OWASP DC ne détectent pas ce type de faille pour un JDK Temurin, qui n'est pas géré par le gestionnaire de paquets de l'image ;
- durcissement de l'agent : truststore minimal (domaines réellement joints), filtrage egress par liste de domaines, vérification d'intégrité des binaires téléchargés dans `Dockerfile.agent` (`releases/latest`, `stable.txt`) ;
- denylist des 8 intermédiaires par configuration (`jdk.security.provider.disallowedCerts`) : devenue inutile avec Temurin 25.0.5.

## 9. Lien avec CVE-2026-114938 (Java4Shell, 2026-11-17)

Temurin 25.0.5 et le JDK Red Hat 21.0.13, qui closent cet incident, sont vulnérables à CVE-2026-114938 (écriture hors limites dans l'intrinsèque Base64 AVX-512 de C2). Contournement `-XX:-UseBASE64Intrinsics` appliqué le 2026-11-19 à Keycloak, à l'application et à Jenkins ; suivi dans [TRIVY_SECURITY_SCAN.md](../TRIVY_SECURITY_SCAN.md) et `SECURITY_ADVISORIES.md`.

## Historique du document

- 2026-10-23 : création, mesure initiale, phase 1 (nœud KinD, agent, contrôleur, épinglages), acceptations `fixcve-auto`.
- 2026-10-29 : agent et contrôleur sur Temurin 25.0.5+8 ; retrait du contournement par vérification de révocation CRL (non viable, il rejetait `github.com` et `ghcr.io`).
- 2026-11-05 : application en `eclipse-temurin:25.0.5_8-jre-noble` ; acceptation `ca-certificates` de Keycloak retirée (Keycloak 26.8.1).
- 2026-11-19 : builder et SonarQube corrigés, ZAP et nginx constatés corrigés en amont, CVE-2026-91403 en acceptation permanente ; incident clos, document passé en `historique`.
