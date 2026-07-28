# Inventaire des composants open source

> \*\*Convention retenue :\*\* un composant est un projet open source choisi explicitement dans la configuration du dépôt. Les \*\*24 plugins Jenkins directs\*\* sont comptés séparément, car ce sont des extensions installées explicitement. Les dépendances transitives restent des estimations et ne doivent pas être additionnées ligne à ligne, car elles se recouvrent.

|Catégorie|Composants open source principaux directs|Nombre direct|Estimation avec dépendances transitives|
|-|-|-:|-:|
|**Back-end Java**|Spring Boot, Spring Security, Spring Data JPA, Spring OAuth2, Spring Actuator, Thymeleaf, Springdoc OpenAPI, Hibernate ORM, PostgreSQL JDBC, H2, Micrometer, JsonPath, jqwik|**13**|120–135|
|**Bases de données**|PostgreSQL|**1**|5–10|
|**Front-end JavaScript**|Vue.js, Vue Router, Axios, Element Plus, Element Plus Icons, Vue CLI|**6**|700–760|
|**Tests et couverture**|JUnit, AssertJ, Selenium, WebDriverManager, JaCoCo, Firefox ESR|**6**|20–35|
|**IAM et intégration Keycloak**|Keycloak, Keycloak Admin Client, RESTEasy, Apache HttpClient|**4**|20–40|
|**Build et runtimes**|Apache Maven, Frontend Maven Plugin, Node.js, npm, Eclipse Temurin / OpenJDK, Maven Wrapper|**6**|20–35|
|**Jenkins et extensions CI/CD**|Jenkins, Git plugin, Workflow Aggregator, Pipeline Stage View, Credentials, Credentials Binding, Matrix Auth, Maven Integration, JDK Tool, SonarQube Scanner, Coverage, JUnit plugin, HTML Publisher, OWASP Dependency-Check plugin, Docker Plugin, Docker Pipeline, Mailer, Email Extension, Timestamper, Build Timeout, Workspace Cleanup, JCasC, Job DSL, Pipeline Utility Steps, Copy Artifact|**25**|100–115|
|**Services CI/CD et qualité**|Docker Socket Proxy, SonarQube Community, Docker Distribution Registry, OWASP ZAP, Renovate, Sonar Maven Plugin|**6**|30–50|
|**Sécurité / supply chain**|OWASP Dependency-Check, Trivy, SOPS, Cosign, OpenSSL, yq / jq|**6**|35–60|
|**Conteneurs, Kubernetes et réseau**|Docker Engine, Docker Compose, KinD, Kubernetes, kubectl, Helm, Cilium, NGINX Gateway Fabric, Nginx|**9**|40–70|
|**Observabilité**|Prometheus, Grafana, Loki, Promtail, Postgres Exporter|**5**|70–120|

|Total|Calcul|Nombre|
|-|-|-:|
|**Composants principaux directs, plugins Jenkins inclus**|Toutes les lignes ci-dessus|**87**|
|**Composants principaux directs, hors 24 plugins Jenkins**|87 − 24|**63**|
|**Composants avec transitifs, dédoublonnés entre catégories**|Estimation globale|**environ 950 à 1 200**|

> \*\*Note méthodologique (mise à jour) :\*\* les fourchettes Back-end Java, Front-end JavaScript et Jenkins ci-dessus sont ancrées sur des mesures réelles et non plus des estimations à vue :
>
> - Back-end Java : SBOM Trivy de l'image `rhdemo-api:1.1.10-SNAPSHOT-705` → 127 artefacts Maven embarqués dans `app.jar` (dont l'application elle-même et 2 doublons probables liés à un artefact de scan Trivy).
> - Front-end JavaScript : `rhDemo/frontend/package-lock.json` → 746 paquets npm (arbre complet, y compris l'outillage de build Vue CLI/webpack/babel).
> - Jenkins : `rhDemo/infra/jenkins-docker/plugins.txt` → 24 plugins directs + 83 dépendances transitives verrouillées = 107 entrées au total.
>
> L'estimation globale dédoublonnée (950–1 200) applique le même facteur de recouvrement que l'estimation précédente (~15–20 %, essentiellement dû aux paquets système partagés entre les images Docker des catégories Sécurité, Conteneurs/K8s, Services CI/CD et Observabilité) à la nouvelle somme brute des fourchettes (~1 160–1 430), dominée désormais par l'écosystème npm du front-end.
