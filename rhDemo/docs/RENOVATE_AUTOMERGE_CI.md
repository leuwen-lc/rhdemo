# Intégration automatique des mises à jour Renovate après validation CI Jenkins

## Contexte et contraintes

### Architecture actuelle

| Composant | État |
|---|---|
| Renovate | Tourne en nuit (3h) sur Codeberg Actions, crée des PRs vers `evolutions-post-1.1.8` |
| Jenkins CI | Local (Docker Compose), surveille uniquement la branche `master` (poll toutes les 5 min) |
| Forgejo/Codeberg | Héberge le dépôt, mais **ne peut pas appeler Jenkins** (Jenkins non exposé sur Internet) |
| Statuts CI | **Non remontés** vers Forgejo (raison du `prCreation: immediate`) |

### Le problème

Renovate sait créer des PRs mais ne peut pas les merger automatiquement car :
1. Il attend des statuts CI qui ne lui parviennent jamais
2. Jenkins ne surveille pas les branches Renovate (`renovate/*`)
3. Aucun webhook entrant n'est possible (Jenkins derrière NAT)

---

## Approches possibles

### Option A — Jenkins pipeline dédié « Renovate Validator » ⭐ Recommandée

Jenkins prend la responsabilité complète : il détecte les PRs Renovate ouvertes via l'API Forgejo, exécute la CI dessus, puis merge si ça passe.

```
03h00 — Renovate crée les PRs (Codeberg Actions)
04h00 — Jenkins "RHDemo-Renovate" se déclenche (cron)
         ↓
         Liste les PRs Renovate ouvertes via API Forgejo
         ↓ Pour chaque PR (patch/minor uniquement)
         Checkout de la branche PR
         → Build Maven + tests unitaires + tests intégration
         → OWASP Dependency-Check
         → Build image Docker
         (Selenium/ZAP exclus pour la vitesse)
         ↓
         CI passe ?
         ├─ OUI → merge de la PR via API Forgejo + commentaire de confirmation
         └─ NON → commentaire d'échec sur la PR + notification Jenkins
```

**Avantages :**
- Aucune modification de l'infrastructure (Jenkins reste local, pas d'exposition Internet)
- Contrôle total sur ce qui est automerged (patch/minor uniquement)
- Les PR major restent bloquées par `dependencyDashboardApproval: true` déjà en place

**Inconvénients :**
- Un pipeline Jenkins supplémentaire à maintenir
- La CI tourne N fois (une par PR ouverte) — peut être long si beaucoup de PRs

---

### Option B — Reporting des statuts CI + automerge Renovate natif

Jenkins reporte le statut de chaque build à Forgejo via l'API Commit Status, et Renovate se charge du merge quand le statut est vert.

```
Jenkins build → POST /api/v1/repos/leuwen-lc/rhdemo/statuses/{sha}
                     { "state": "success", "context": "jenkins/ci" }

Renovate (nuit suivante) → lit le statut → merge automatique
```

**Avantages :**
- Architecturalement plus propre (séparation des responsabilités)
- Renovate garde la maîtrise du merge

**Inconvénients :**
- Jenkins surveille actuellement `master` seulement — il faudrait ajouter un pipeline multibranch sur `renovate/*`
- Le merge n'est effectif qu'au **passage suivant de Renovate** (lendemain matin), soit ~24h de délai
- Plus complexe à mettre en place

---

### Option C — Migration CI vers Codeberg Actions (hors scope)

Déplacer la CI vers Codeberg Actions permettrait les webhooks natifs et le reporting de statuts automatique. Étude disponible dans `docs/` (rapport d'audit Copilot). Non retenu ici car cela représente une refonte complète du pipeline.

---

### Option D — Paramétrage du Jenkinsfile-CI existant + orchestrateur minimal

Plutôt que de créer un `Jenkinsfile-Renovate` avec ses propres stages build/test/OWASP (dupliquant la logique du CI principal), on paramètre le `Jenkinsfile-CI` existant et on n'ajoute qu'un **orchestrateur de ~30 lignes** dont le seul rôle est de lister les PRs et de déclencher le CI avec les bons paramètres.

#### Analyse du Jenkinsfile-CI existant

Le `Jenkinsfile-CI` dispose déjà de leviers pour modifier son comportement à l'exécution :

| Paramètre existant | Valeur pour mode Renovate | Stages concernés |
|---|---|---|
| `RUN_SELENIUM_TESTS=false` | skip | ZAP Proxy, Tests Selenium |
| `RUN_SONAR=false` | skip | Analyse SonarQube, Quality Gate |
| `PUBLISH_IMAGE=false` | skip | Tag/Publication, Signature Cosign, Nettoyage registry |
| `SIGN_IMAGE=false` | skip | Signature Cosign (déjà couvert) |

Ces quatre paramètres écartent environ 30 % du pipeline (les phases les plus longues : Selenium ~20 min, SonarQube ~5 min, publication ~3 min). Il manque uniquement deux paramètres pour compléter le mode Renovate :

1. **`BRANCH_TO_TEST`** — pour que le checkout cible la branche PR plutôt que la branche configurée dans le job Jenkins.
2. **`PR_NUMBER`** — pour qu'un stage final conditionnel appelle l'API Forgejo et merge la PR si la CI passe.

#### Architecture proposée

```
Jenkinsfile-Renovate-Orchi (orchestrateur ~30 lignes)
  ↓ Liste les PRs Renovate ouvertes via API Forgejo
  ↓ Pour chaque PR (patch/minor) :
      build job: 'RHDemo-CI', wait: true, parameters: [
          BRANCH_TO_TEST=renovate/xxx, PR_NUMBER=42,
          RUN_SELENIUM_TESTS=false, RUN_SONAR=false,
          PUBLISH_IMAGE=false, SIGN_IMAGE=false
      ]
  ↓
  RHDemo-CI s'exécute avec ces paramètres :
      → checkout branche PR
      → Compile + Tests unitaires/intégration
      → OWASP Dependency-Check  ← clé pour des mises à jour de dépendances
      → Build image Docker
      → Scan Trivy (optionnel, déjà rapide ~3 min)
      → (skip : éphémère, Selenium, ZAP, SonarQube, publication)
      → Stage conditionnel « Merge PR Renovate » si PR_NUMBER défini et CI OK
```

#### Modifications requises dans Jenkinsfile-CI

**Bloc `parameters` — 2 ajouts :**
```groovy
string(name: 'BRANCH_TO_TEST', defaultValue: '',
       description: 'Branche PR à tester (vide = branche SCM du job)')
string(name: 'PR_NUMBER', defaultValue: '',
       description: 'Numéro PR à merger après CI OK via API Forgejo (vide = pas de merge auto)')
```

**Stage Checkout — adaptation du git checkout (~5 lignes) :**
```groovy
if (params.BRANCH_TO_TEST?.trim()) {
    sh "git fetch origin '${params.BRANCH_TO_TEST}' && git checkout FETCH_HEAD"
    echo "✅ Branche PR checkoutée : ${params.BRANCH_TO_TEST}"
}
```

**Nouveau stage final conditionnel « Merge PR Renovate » :**
```groovy
stage('🔀 Merge PR Renovate') {
    when {
        allOf {
            expression { params.PR_NUMBER?.trim() }
            expression { currentBuild.currentResult == 'SUCCESS' }
        }
    }
    steps {
        withCredentials([string(credentialsId: 'forgejo-api-token', variable: 'FORGEJO_TOKEN')]) {
            sh """
                curl -sf -X POST \
                  -H "Authorization: token \${FORGEJO_TOKEN}" \
                  -H "Content-Type: application/json" \
                  -d '{"Do":"merge","merge_message_field":"Automerge Renovate PR #${params.PR_NUMBER} — CI Jenkins OK","delete_branch_after_merge":true}' \
                  "${FORGEJO_API}/repos/${REPO}/pulls/${params.PR_NUMBER}/merge" \
                || echo "⚠️ Merge échoué (conflit possible)"
            """
        }
    }
}
```

Les constantes `FORGEJO_API` et `REPO` doivent être ajoutées dans le bloc `environment` du CI (ou externalisées dans `rhDemoLib.groovy`).

#### Orchestrateur minimal (Jenkinsfile-Renovate-Orchi)

```groovy
pipeline {
    agent { label 'builder' }
    triggers { cron('H 4 * * *') }
    options { disableConcurrentBuilds() }
    environment {
        FORGEJO_API = 'https://codeberg.org/api/v1'
        REPO        = 'leuwen-lc/rhdemo'
        BASE_BRANCH = 'evolutions-post-1.1.8'
    }
    stages {
        stage('Lister les PRs Renovate') {
            // Identique à Option A — ~20 lignes curl + python3
        }
        stage('Déclencher CI pour chaque PR') {
            when { expression { env.RENOVATE_PRS?.trim() } }
            steps {
                script {
                    def failures = []
                    env.RENOVATE_PRS.split(' ').each { prEntry ->
                        def parts = prEntry.split(':')
                        def result = build(job: 'RHDemo-CI', wait: true, propagate: false,
                            parameters: [
                                string(name: 'BRANCH_TO_TEST', value: parts[1]),
                                string(name: 'PR_NUMBER',      value: parts[0]),
                                booleanParam(name: 'RUN_SELENIUM_TESTS', value: false),
                                booleanParam(name: 'RUN_SONAR',          value: false),
                                booleanParam(name: 'PUBLISH_IMAGE',      value: false),
                                booleanParam(name: 'SIGN_IMAGE',         value: false)
                            ])
                        if (result.result != 'SUCCESS') failures << parts[0]
                    }
                    if (failures) unstable("PRs en échec : ${failures.join(', ')}")
                }
            }
        }
    }
}
```

#### Comparaison Option A vs Option D

| Critère | Option A (pipeline dédié) | Option D (CI paramétré) |
|---|---|---|
| Duplication de logique CI | Élevée (~200 lignes) | **Nulle** — réutilise le CI |
| Taille du Jenkinsfile Renovate | ~250 lignes | **~30 lignes** (orchestration pure) |
| Modifications Jenkinsfile-CI | Aucune | +2 params, +5 lignes checkout, +1 stage conditionnel |
| Traçabilité Jenkins | 1 build « Renovate » | 1 build orchi + N builds CI enfant |
| Risque de dérive CI vs Renovate | Élevé (deux codes) | **Faible** (un seul CI) |
| Correctifs CI bénéficient à Renovate | ❌ | ✅ automatiquement |
| Parallélisation | `parallel {}` Groovy | Builds parallèles Jenkins natifs |
| Timeout estimé par PR | ~30 min | ~30 min (idem) |

**Avantages clés :**
- Tout correctif ou nouveau scan ajouté au CI bénéficie automatiquement à la validation Renovate, sans synchronisation manuelle.
- L'orchestrateur est trivial et quasi sans logique build : seule responsabilité = lister les PRs et déléguer.
- Le périmètre « mode Renovate » est déjà couvert à 80 % par les paramètres existants.

**Inconvénients / points de vigilance :**
- Le Jenkinsfile-CI gagne deux paramètres et un stage supplémentaire ; cela ajoute une légère complexité à un fichier déjà long.
- Le stage « Merge PR Renovate » s'exécute dans un pipeline CI, ce qui peut sembler hors contexte — il est strictement gardé par `PR_NUMBER` non vide.
- Les variables `FORGEJO_API` et `REPO` doivent être disponibles dans le CI (à centraliser dans `rhDemoLib.groovy` ou dans le bloc `environment`).
- Si l'orchestrateur exécute les builds CI en séquentiel (`wait: true`), le temps total reste N × 30 min. Passer en parallèle (`wait: false` + monitoring) est possible mais complique la gestion des échecs.
- Le timeout global du CI existant (2h) est largement suffisant pour le mode Renovate (~30 min), mais il faudrait veiller à ne pas le réduire à tort.

---

### Option E — Factorisation des parties communes dans une bibliothèque partagée

L'idée est d'aller plus loin que l'Option D en extrayant les ~10 stages identiques dans un **callable Jenkins Shared Library** (`vars/rhDemoCIPipeline.groovy`), de sorte que `Jenkinsfile-CI` et `Jenkinsfile-Renovate` deviennent tous les deux de fins wrappers de configuration.

#### Ce qui est commun aux deux pipelines

| Stage | CI principal | Renovate |
|---|---|---|
| Checkout (avec branche cible) | ✅ | ✅ |
| Lecture version Maven | ✅ | ✅ |
| Déchiffrement SOPS | ✅ | ✅ |
| Extraction secrets rhDemo | ✅ | ✅ |
| Configuration rhDemoInitKeycloak | ✅ | ✅ |
| Compilation Maven | ✅ | ✅ |
| Tests unitaires + intégration | ✅ | ✅ |
| OWASP Dependency-Check | ✅ | ✅ |
| Build image Docker | ✅ | ✅ |
| Couverture JaCoCo | ✅ | optionnel |

| Stage | CI principal | Renovate |
|---|---|---|
| SonarQube + Quality Gate | ✅ | ❌ |
| Environnement éphémère complet | ✅ | ❌ |
| Selenium / OWASP ZAP | ✅ | ❌ |
| Scan Trivy + SBOM | ✅ | ❌ |
| Publication image + Cosign | ✅ | ❌ |
| Merge PR Forgejo | ❌ | ✅ |

#### Pattern Jenkins : callable de shared library

```groovy
// vars/rhDemoCIPipeline.groovy
def call(Map cfg = [:]) {
    // cfg.runSelenium, cfg.runSonar, cfg.publishImage,
    // cfg.branchToTest, cfg.prNumber ...

    pipeline {
        agent { label 'builder' }
        stages {
            stage('Checkout')            { steps { script { /* checkout + branchToTest */ } } }
            stage('Lecture Version')     { steps { /* mvnw help:evaluate */ } }
            stage('Déchiffrement SOPS') { steps { /* sops -d */ } }
            stage('Compilation Maven')  { steps { /* mvnw clean compile */ } }
            stage('Tests')              { steps { /* mvnw verify */ } }
            stage('OWASP')              { steps { /* mvnw dependency-check:check */ } }
            stage('Build Docker')       { steps { /* docker build */ } }

            // Stages CI-only
            stage('SonarQube') {
                when { expression { cfg.runSonar } }
                steps { /* sonar:sonar */ }
            }
            stage('Environnement Staging + Selenium') {
                when { expression { cfg.runSelenium } }
                steps { /* docker-compose up + Selenium + ZAP */ }
            }
            stage('Publication Image') {
                when { expression { cfg.publishImage } }
                steps { /* docker push + cosign */ }
            }

            // Stage Renovate-only
            stage('Merge PR Forgejo') {
                when { expression { cfg.prNumber?.trim() } }
                steps { /* curl API merge */ }
            }
        }
    }
}
```

Les deux Jenkinsfiles deviennent alors :

```groovy
// Jenkinsfile-CI  (~5 lignes)
rhDemoCIPipeline(
    runSonar: params.RUN_SONAR,
    runSelenium: params.RUN_SELENIUM_TESTS,
    publishImage: params.PUBLISH_IMAGE
)

// Jenkinsfile-Renovate  (~5 lignes + boucle liste-PRs)
renovatePRs.each { pr ->
    rhDemoCIPipeline(
        branchToTest: pr.branch,
        prNumber: pr.number,
        runSonar: false, runSelenium: false, publishImage: false
    )
}
```

#### Contrainte technique majeure

Jenkins **Declarative Pipeline** (`pipeline { stages { ... } }`) n'est pas conçu pour être instancié dynamiquement depuis une shared library. Deux contournements existent, tous avec un coût :

| Contournement | Mécanisme | Inconvénient |
|---|---|---|
| **Scripted pipeline** dans la lib | `node('builder') { stage('X') { ... } }` | Perd la syntaxe déclarative, la validation statique, et `when {}` intégré |
| **Hybrid** : stages en closures passées en paramètre | Le caller définit les steps comme lambdas Groovy | Syntaxe non standard, difficile à lire, Jenkins plugins mal supportés |

En pratique le callable fonctionne, mais le `Jenkinsfile-CI` actuel (1900 lignes, entièrement déclaratif) devrait être **réécrit en scripted pipeline** pour être extrait dans la lib — refactoring significatif sur un pipeline fonctionnel.

#### Factorisation partielle (variante allégée)

Une option intermédiaire : ne pas extraire les **stages** mais uniquement les **fonctions utilitaires** (déjà le rôle de `rhDemoLib.groovy`). Les étapes Maven/Docker communes deviendraient des méthodes appelables depuis les deux fichiers :

```groovy
// rhDemoLib.groovy — ajouts potentiels
def runMavenBuild()       { sh './mvnw clean compile -DskipTests' }
def runTests()            { sh './mvnw verify' }
def runOwaspCheck()       { sh './mvnw org.owasp:dependency-check-maven:check ...' }
def buildDockerImage(tag) { sh "docker build -t ${tag} ." }
```

Les deux Jenkinsfiles gardent leur structure déclarative propre mais appellent ces méthodes — pas de duplication du **contenu** des steps, mais les déclarations de stages restent dans chaque fichier.

#### Comparaison des options

| Critère | Option A (dédié) | Option D (CI paramétré) | Option E complète (lib callable) | Option E partielle (méthodes lib) |
|---|---|---|---|---|
| Duplication logique | Élevée | Nulle | Nulle | Faible (steps dupliqués, pas les corps) |
| Refactoring du CI existant | Aucun | Minimal (+2 params) | **Majeur** (réécriture scripted) | Minime |
| Lisibilité des Jenkinsfiles | ❌ (long) | ❌ (légèrement +complexe) | ✅ (5 lignes chacun) | ✅ (stages explicites) |
| Risque de régression CI | Nul | Faible | **Élevé** | Faible |
| Complexité de maintenance | 2 fichiers | 1 fichier + orchestrateur | 1 lib + 2 wrappers | 1 lib + 2 fichiers normaux |

**Verdict :** L'Option E complète est la plus propre architecturalement mais implique de réécrire un pipeline fonctionnel en scripted Groovy — coût/bénéfice défavorable pour un projet école. L'Option E partielle (enrichir `rhDemoLib.groovy` avec des méthodes communes) est complémentaire à l'Option D et peut être menée progressivement sans risque.

---

## Implémentation recommandée (Option A)

> **Statut** : implémenté — [`Jenkinsfile-Renovate`](../Jenkinsfile-Renovate), job `RHDemo-Renovate` dans
> [`jenkins-casc.yaml`](../infra/jenkins-docker/jenkins-casc.yaml) et fonction `postForgejoComment`
> dans [`rhDemoLib.groovy`](../vars/rhDemoLib.groovy). Le script ci-dessous est celui **réellement
> implémenté**, corrigé par rapport au brouillon initial sur trois points :
> 1. **`python3` n'existe pas** dans l'image agent Jenkins ([`Dockerfile.agent`](../infra/jenkins-docker/Dockerfile.agent))
>    — le filtrage JSON utilise `jq` (déjà installé) à la place.
> 2. **Parsing cassé** : `head.label` (API Forgejo/GitHub) est au format `owner:branche`. Un split
>    naïf par `:` sur `numero:label:sha` explose dès que le label contient lui-même un `:`. Le script
>    utilise `head.ref` (nom de branche brut) et `base.ref` (au lieu de `.label`), avec `|` comme
>    séparateur (un sha ou un nom de branche ne peut pas en contenir).
> 3. **`-Dskip.selenium=true` et `-Pskip-sonar` n'existent pas** dans `pom.xml` (aucune propriété ni
>    profil de ce nom — Selenium est un module Maven séparé, jamais invoqué par `rhDemo/mvnw`, et
>    Sonar est piloté par un paramètre Jenkins, pas un profil Maven). Le script exécuté est la même
>    séquence que `RHDemo-CI` : `mvnw clean compile -DskipTests` puis `mvnw verify` puis le goal OWASP
>    explicite `org.owasp:dependency-check-maven:check` (credentials `nvd-api-key` /
>    `ossindex-credentials`, déjà existants — sinon OWASP n'est jamais exécuté en mode Renovate).
>
> Ajout ultérieur : synchronisation automatique de la branche PR avec la base par un merge classique
> avant les tests, quand elle est en retard (voir point 3 de « Limites connues » ci-dessous — un
> squash merge a été essayé puis abandonné, il casse la filiation git et provoque des faux conflits
> à chaque cycle).

### 1. Credential Jenkins : token API Forgejo

Créer manuellement dans Jenkins UI un credential de type **Secret text** :
- **ID** : `forgejo-api-token`
- **Description** : Token API Forgejo pour merge automatique des PRs Renovate
- **Valeur** : token **dédié** généré sur `https://codeberg.org/user/settings/applications` avec
  scope `repository` uniquement — distinct du token Codeberg déjà utilisé par `/fixcve-auto`
  (`~/.config/rhdemo-fixcve/credentials.sops.yaml`), pour isoler les deux automatisations.

### 2. Fichier `Jenkinsfile-Renovate`

Créé dans `rhDemo/Jenkinsfile-Renovate` (extrait des stages clés — voir le fichier pour la version complète) :

```groovy
pipeline {
    agent { label 'builder' }

    options {
        timeout(time: 2, unit: 'HOURS')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '15'))
        disableConcurrentBuilds()
    }

    tools {
        jdk 'JDK25'
        maven 'Maven3'
    }

    environment {
        FORGEJO_API = 'https://codeberg.org/api/v1'
        REPO        = 'leuwen-lc/rhdemo'
        BASE_BRANCH = 'evolutions-post-1.1.8'
    }

    // Pas de bloc triggers ici : le cron est déclaré côté job CASC (RHDemo-Renovate),
    // comme pour RHDemo-CI/RHDemo-CD — cohérent avec la convention existante.

    stages {
        stage('🛠️ Checkout') {
            steps {
                script {
                    def lib = load 'rhDemo/vars/rhDemoLib.groovy'
                    lib.printSectionHeader("Pipeline Renovate Automerge - RHDemo")
                }
                checkout scm
            }
        }

        stage('📋 Lister les PRs Renovate') {
            steps {
                withCredentials([string(credentialsId: 'forgejo-api-token', variable: 'FORGEJO_TOKEN')]) {
                    script {
                        def httpCode = sh(
                            script: """
                                set +x
                                curl -sf -H "Authorization: token \${FORGEJO_TOKEN}" \
                                  "${FORGEJO_API}/repos/${REPO}/pulls?state=open&limit=50" \
                                  -o /tmp/renovate-prs-\${BUILD_NUMBER}.json
                            """,
                            returnStatus: true
                        )
                        if (httpCode != 0) error("Impossible de lister les PRs Forgejo (curl exit ${httpCode})")

                        // jq (pas de python3 dans l'image agent) — filtre sur head.ref (nom de
                        // branche brut, pas head.label qui est préfixé "owner:branche" et casserait
                        // le split ci-dessous). Séparateur "|" : le sha ne peut pas en contenir.
                        env.RENOVATE_PRS = sh(
                            script: """
                                jq -r --arg base "${BASE_BRANCH}" '
                                    [ .[]
                                      | select((.head.ref // "") | test("renovate"; "i"))
                                      | select(.base.ref == \$base)
                                      | "\\(.number)|\\(.head.ref)|\\(.head.sha)"
                                    ] | join(" ")
                                ' /tmp/renovate-prs-${BUILD_NUMBER}.json
                            """,
                            returnStdout: true
                        ).trim()

                        if (!env.RENOVATE_PRS) {
                            echo "Aucune PR Renovate ouverte sur ${BASE_BRANCH} — rien à faire."
                        } else {
                            echo "PRs Renovate trouvées : ${env.RENOVATE_PRS}"
                        }

                        sh "rm -f /tmp/renovate-prs-${BUILD_NUMBER}.json"
                    }
                }
            }
        }

        stage('🔀 Valider et merger chaque PR') {
            when { expression { env.RENOVATE_PRS?.trim() } }
            steps {
                withCredentials([
                    string(credentialsId: 'forgejo-api-token', variable: 'FORGEJO_TOKEN'),
                    string(credentialsId: 'nvd-api-key', variable: 'NVD_API_KEY'),
                    usernamePassword(credentialsId: 'ossindex-credentials', usernameVariable: 'OSSINDEX_USER', passwordVariable: 'OSSINDEX_PASSWORD')
                ]) {
                    script {
                        def lib = load 'rhDemo/vars/rhDemoLib.groovy'
                        def failures = []

                        env.RENOVATE_PRS.split(' ').each { prEntry ->
                            def parts    = prEntry.split('\\|')
                            def prNumber = parts[0]
                            def branchRef = parts[1]

                            echo "=== Traitement PR #${prNumber} (${branchRef}) ==="

                            sh "git fetch origin '${branchRef}'"
                            sh 'git checkout FETCH_HEAD'
                            // FETCH_HEAD est écrasé par le prochain "git fetch" (celui de la base) —
                            // on capture le SHA de la PR avant, pour pouvoir y revenir en cas de conflit.
                            def prTipSha = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
                            sh "git fetch origin ${BASE_BRANCH}"

                            // Branche en retard sur la base ? Un correctif de sécurité mergé entre-temps
                            // (ex: CVE fixée) ferait sinon échouer la CI pour une raison sans rapport
                            // avec le changement de la PR. Merge classique de la base + push avant de
                            // tester (pas un squash : voir la note ci-dessous).
                            def upToDate = sh(
                                script: "git merge-base --is-ancestor origin/${BASE_BRANCH} HEAD",
                                returnStatus: true
                            ) == 0

                            def syncFailed = false
                            if (!upToDate) {
                                def syncStatus = sh(
                                    script: """
                                        set -e
                                        git config user.email "jenkins-renovate@leuwen-lc.fr"
                                        git config user.name "Jenkins Renovate Bot"
                                        git merge origin/${BASE_BRANCH} -m "chore: synchronisation avec ${BASE_BRANCH} (merge automatique CI Renovate)"
                                    """,
                                    returnStatus: true
                                )
                                if (syncStatus != 0) {
                                    sh 'git merge --abort 2>/dev/null || true'
                                    sh "git reset --hard ${prTipSha}"
                                    sh 'git clean -fd'
                                    syncFailed = true
                                } else {
                                    def pushStatus = sh(
                                        script: """
                                            set +x
                                            git push "https://\${FORGEJO_TOKEN}@codeberg.org/${REPO}.git" "HEAD:refs/heads/${branchRef}"
                                        """,
                                        returnStatus: true
                                    )
                                    if (pushStatus != 0) { syncFailed = true }
                                }
                            }

                            if (syncFailed) {
                                failures << prNumber
                                lib.postForgejoComment(FORGEJO_API, REPO, prNumber,
                                    "Conflit lors de la synchronisation automatique avec ${BASE_BRANCH} — rebase manuel nécessaire.")
                                return
                            }

                            // Même séquence que RHDemo-CI (hors Selenium/ZAP/Sonar/publication) :
                            // pas de flags Maven inexistants, OWASP exécuté explicitement.
                            def ciStatus = sh(
                                script: '''
                                    cd rhDemo
                                    set -e
                                    ./mvnw clean compile -DskipTests
                                    ./mvnw verify
                                    ./mvnw org.owasp:dependency-check-maven:check -DnvdApiKey=${NVD_API_KEY} -DossindexAnalyzerUsername=${OSSINDEX_USER} -DossindexAnalyzerPassword=${OSSINDEX_PASSWORD}
                                ''',
                                returnStatus: true
                            )

                            if (ciStatus == 0) {
                                echo "CI OK pour PR #${prNumber} — merge en cours"
                                def mergeStatus = sh(
                                    script: """
                                        set +x
                                        curl -sf -X POST \
                                          -H "Authorization: token \${FORGEJO_TOKEN}" \
                                          -H "Content-Type: application/json" \
                                          -d '{"Do":"merge","merge_message_field":"Automerge Renovate PR #${prNumber} - CI Jenkins OK","delete_branch_after_merge":true}' \
                                          "${FORGEJO_API}/repos/${REPO}/pulls/${prNumber}/merge"
                                    """,
                                    returnStatus: true
                                )
                                if (mergeStatus != 0) {
                                    echo "WARN: merge API échoué pour PR #${prNumber} (conflit possible ?)"
                                    failures << prNumber
                                    lib.postForgejoComment(FORGEJO_API, REPO, prNumber,
                                        "CI Jenkins OK mais merge échoué (conflit possible). Intervention manuelle requise. Build : ${env.BUILD_URL}")
                                } else {
                                    lib.postForgejoComment(FORGEJO_API, REPO, prNumber,
                                        "CI Jenkins validée — PR mergée automatiquement. Build : ${env.BUILD_URL}")
                                }
                            } else {
                                echo "CI KO pour PR #${prNumber} — PR conservée ouverte"
                                failures << prNumber
                                lib.postForgejoComment(FORGEJO_API, REPO, prNumber,
                                    "CI Jenkins échouée — voir build ${env.BUILD_URL}. Mise à jour à revoir manuellement.")
                            }

                            junit allowEmptyResults: true, testResults: 'rhDemo/target/surefire-reports/*.xml'
                            junit allowEmptyResults: true, testResults: 'rhDemo/target/failsafe-reports/*.xml'
                        }

                        if (failures) {
                            // FAILURE (pas unstable) : les builds UNSTABLE ne comptent pas dans le
                            // rapport météo/"aucun build récent n'a échoué" de Jenkins.
                            currentBuild.result = 'FAILURE'
                            echo "❌ ${failures.size()} PR(s) en échec : ${failures.join(', ')}"
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            sh "git checkout ${env.BASE_BRANCH} || true"
            cleanWs()
        }
    }
}
```

La fonction `postForgejoComment` (dans `rhDemoLib.groovy`, chargée via `load` comme le reste de la
lib) construit le JSON avec `jq -n --arg` plutôt que par interpolation directe dans une chaîne
`-d '{"body":"..."}'`, pour ne pas casser la requête si un message venait à contenir un guillemet.

### 3. Déclaration dans `jenkins-casc.yaml`

Job `RHDemo-Renovate` ajouté dans le bloc `jobs` du CASC (voir
[`jenkins-casc.yaml`](../infra/jenkins-docker/jenkins-casc.yaml) pour la version exacte), sur le
même modèle que `RHDemo-CI`/`RHDemo-CD` (checkout du repo public sans credentials, `scriptPath`
vers le nouveau Jenkinsfile, `disableConcurrentBuilds`, `buildDiscarder`). Le cron `H 4 * * *` est
déclaré dans le `triggers {}` du job CASC, pas dans le Jenkinsfile lui-même.

Prise en compte : `docker-compose restart jenkins` (mécanisme déjà documenté dans `QUICKSTART.md`)
suffit à recharger la configuration et faire apparaître le nouveau job — aucune étape
supplémentaire nécessaire.

### 4. Ajustements `renovate.json`

Ajouter `automerge: false` explicitement pour les mises à jour **major** (déjà bloquées par `dependencyDashboardApproval`) et confirmer que minor/patch ne bloquent pas sur les statuts :

```json
{
  "packageRules": [
    {
      "matchUpdateTypes": ["patch", "minor"],
      "automerge": false
    }
  ]
}
```

(`prCreation: "immediate"` est déjà défini globalement dans `renovate.json`, pas besoin de le répéter par règle.)

> Note : `automerge: false` ici signifie que Renovate lui-même ne tente pas de merger (c'est Jenkins qui le fait). Cela évite les conflits entre les deux mécanismes.

---

## Périmètre d'automerge

| Type de mise à jour | Traitement |
|---|---|
| `patch` (ex: 1.2.3 → 1.2.4) | Automerge Jenkins si CI verte |
| `minor` (ex: 1.2.3 → 1.3.0) | Automerge Jenkins si CI verte |
| `major` (ex: 1.x → 2.x) | Bloqué — `dependencyDashboardApproval: true` — revue manuelle |
| Plugins Jenkins | Exclus — `matchManagers: ["jenkins"]` désactivé |
| Image `rhdemo-api` | Exclue — `matchPackageNames: ["rhdemo-api"]` désactivé |

---

## Sécurité

- Le token Forgejo doit avoir uniquement le scope `repository` (pas d'accès admin)
- Le token est stocké comme credential Jenkins chiffré (jamais en clair dans les fichiers)
- Le pipeline vérifie que la PR cible bien `evolutions-post-1.1.8` avant de merger
- Les PRs major ne passent jamais par ce pipeline (bloquées côté Renovate)

---

## Limites connues

1. **Durée** : Si Renovate crée 15 PRs en une nuit, le pipeline peut tourner 2-3h (CI séquentielle). Mitigation : paralléliser avec `parallel {}` Jenkins si les ressources le permettent.

2. **Conflits entre PRs** : Si deux PRs modifient le même fichier (rare pour des dépendances), la seconde peut conflictiquer après merge de la première. Le pipeline détecte l'échec du merge API et laisse la PR ouverte.

3. ~~Pas de rebase automatique~~ **Résolu** : le pipeline vérifie désormais (`git merge-base --is-ancestor`) si la branche PR est en retard sur `evolutions-post-1.1.8` avant de lancer les tests. Si oui, il fait un `git merge` (classique, pas squash) de la base dans la branche PR, commit, et pousse sur Codeberg avant de lancer la CI — ça évite qu'un correctif déjà mergé sur la base (ex: CVE fixée entre-temps) fasse échouer la CI d'une PR sans rapport avec ce correctif.
   - **Pourquoi pas un squash merge** : essayé initialement, mais un `git merge --squash` ne crée pas de commit de fusion à deux parents — git perd la trace de ce qui a déjà été synchronisé. Chaque sync suivante recalcule alors un merge-base bien plus ancien que le dernier sync réussi, ce qui provoque un faux conflit `add/add` dès qu'un fichier est retouché côté base entre deux cycles (observé en pratique sur `Jenkinsfile-Renovate` lui-même). Un merge classique préserve la filiation avec la base : chaque sync devient incrémentale.
   - En cas de conflit lors du merge, la PR est marquée en échec avec un commentaire dédié ("rebase manuel nécessaire") plutôt que de faire planter le build.
   - Ce commit de synchronisation est indépendant du `rebaseWhen: "behind-base-branch"` de Renovate (qui continue de fonctionner en parallèle, côté nocturne) — les deux mécanismes se recouvrent partiellement mais ne rentrent pas en conflit : si Renovate rebase la branche entre-temps (force-push), le prochain run Jenkins repart d'un état propre.
   - **Incident connu** : la première version (squash) a poussé un commit corrompu (ancêtre commun perdu) sur `renovate/renovate-renovate-43.x` avant d'être corrigée. Cette branche spécifique continuera de conflictuer sur tout fichier déjà présent des deux côtés tant qu'elle n'aura pas été rebasée proprement par Renovate (`@renovate rebase` en commentaire de PR, ou passage nocturne).

4. **Pas de déclenchement CD** : Ce pipeline ne déclenche pas le CD après merge. Le CI principal (`RHDemo-CI`) doit être étendu pour surveiller aussi `evolutions-post-1.1.8` (ou un cron nocturne séparé).
