# 📋 Gestion des paramètres rhDemo dans Kubernetes

## 🎯 Vue d'ensemble

L'application rhDemo utilise **3 niveaux de configuration** qui se combinent dans Kubernetes :

1. **Fichiers application*.yml** (embarqués dans l'image Docker)
2. **Fichiers secrets*.yml** (montés en volume Kubernetes)
3. **Variables d'environnement** (injectées par Helm)

---

## 📂 1. Fichiers de configuration embarqués

### 🔹 application.yml (configuration par défaut)

Fichier : `rhDemo/src/main/resources/application.yml`

```yaml
# Configuration de base (dev local)
spring:
  config:
    import:
      - optional:file:./secrets/secrets-rhdemo.yml        # En local
      - optional:file:/workspace/secrets/secrets-rhdemo.yml  # En container

  datasource:
    url: jdbc:postgresql://localhost:5432/dbrhdemo
    username: dbrhdemo
    password: ${rhdemo.datasource.password.pg}  # ← Depuis secrets-rhdemo.yml

  security:
    oauth2:
      client:
        registration:
          keycloak:
            client-secret: ${rhdemo.client.registration.keycloak.client.secret}  # ← Depuis secrets-rhdemo.yml
```

**Valeurs substituées** :
- `${rhdemo.datasource.password.pg}` → depuis secrets-rhdemo.yml
- `${rhdemo.client.registration.keycloak.client.secret}` → depuis secrets-rhdemo.yml

### 🔹 application-stagingkub.yml (profile Kubernetes)

Fichier : `rhDemo/src/main/resources/application-stagingkub.yml`

```yaml
spring:
  security:
    oauth2:
      client:
        provider:
          keycloak:
            # URLs Keycloak adaptées à Kubernetes
            authorization-uri: https://keycloak-stagingkub.intra.leuwen-lc.fr/realms/RHDemo/...
            token-uri: http://keycloak:8080/realms/RHDemo/...  # ← Service Kubernetes
            jwk-set-uri: http://keycloak:8080/realms/RHDemo/...

server:
  forward-headers-strategy: framework  # ← Support reverse proxy nginx

management:
  endpoints:
    web:
      exposure:
        include: '*'  # ← Tous les endpoints actuator
```

**Spécificités Kubernetes** :
- Utilise les noms de services Kubernetes (`keycloak`, `postgresql-rhdemo`)
- URLs internes HTTP pour backend
- URLs externes HTTPS pour navigateur

---

## 🔐 2. Secrets (gérés par SOPS et Kubernetes Secrets)

### 🔹 Flux des secrets dans le pipeline CD

```
secrets-stagingkub.yml (chiffré SOPS)
    ↓ [Pipeline CD - Stage: Déchiffrement Secrets SOPS]
secrets-decrypted.yml (temporaire)
    ↓ [Extraction via yq]
env-vars.sh (variables bash)
    ↓ [Stage: Extraction secrets rhDemo]
secrets-rhdemo.yml (fichier pour l'app)
    ↓ [Stage: Update Kubernetes Secrets]
Kubernetes Secret: rhdemo-app-secrets
    ↓ [Helm deploy]
Volume monté dans /workspace/secrets/
    ↓ [Spring Boot]
Chargé via spring.config.import
```

### 🔹 Contenu de secrets-rhdemo.yml

```yaml
rhdemo:
  datasource:
    password:
      pg: <mot_de_passe_postgresql>
      h2: <mot_de_passe_h2>
  client:
    registration:
      keycloak:
        client:
          secret: <secret_client_keycloak>
```

### 🔹 Secrets Kubernetes créés par le pipeline

Dans le Jenkinsfile-CD, stage **'☸️ Update Kubernetes Secrets'** :

```bash
# Secret 1: Mot de passe PostgreSQL
kubectl create secret generic rhdemo-db-secret \
  --from-literal=password="${RHDEMO_DATASOURCE_PASSWORD_PG}"

# Secret 2: Fichier de config complet pour l'app
kubectl create secret generic rhdemo-app-secrets \
  --from-file=secrets-rhdemo.yml=rhDemo/secrets/secrets-rhdemo.yml

# Secret 3: Admin Keycloak
kubectl create secret generic keycloak-admin-secret \
  --from-literal=password="${KEYCLOAK_ADMIN_PASSWORD}"

# Secret 4: DB Keycloak
kubectl create secret generic keycloak-db-secret \
  --from-literal=password="${KEYCLOAK_DB_PASSWORD}"
```

**Commandes utiles** :

```bash
# Lister les secrets
kubectl get secrets -n rhdemo-stagingkub

# Voir le contenu d'un secret (base64)
kubectl get secret rhdemo-app-secrets -n rhdemo-stagingkub -o yaml

# Décoder un secret
kubectl get secret rhdemo-app-secrets -n rhdemo-stagingkub -o jsonpath='{.data.secrets-rhdemo\.yml}' | base64 -d
```

---

## ⚙️ 3. Variables d'environnement (injectées par Helm)

Dans le deployment Helm : `infra/stagingkub/helm/rhdemo/templates/rhdemo-app-deployment.yaml`

### 🔹 Variables Spring Boot

```yaml
env:
  # Profile Spring
  - name: SPRING_PROFILES_ACTIVE
    value: stagingkub  # ← Active application-stagingkub.yml

  # Base de données (surcharge application.yml)
  - name: SPRING_DATASOURCE_URL
    value: "jdbc:postgresql://postgresql-rhdemo:5432/rhdemo"
  - name: SPRING_DATASOURCE_USERNAME
    value: rhdemo
  - name: SPRING_DATASOURCE_PASSWORD
    valueFrom:
      secretKeyRef:
        name: rhdemo-db-secret  # ← Kubernetes Secret
        key: password

  # OAuth2 (surcharge application-stagingkub.yml)
  - name: SPRING_SECURITY_OAUTH2_CLIENT_REGISTRATION_KEYCLOAK_REDIRECT_URI
    value: "https://rhdemo-stagingkub.intra.leuwen-lc.fr/login/oauth2/code/{registrationId}"

  # Actuator
  - name: MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE
    value: "health,info,metrics,prometheus"

  # Réglages JVM
  # NB : les variables BPL_* sont un héritage de l'image Paketo. L'image
  # actuelle est construite depuis rhDemo/Dockerfile (Temurin 25) et ne les
  # interprète pas — seul JAVA_TOOL_OPTIONS est honoré nativement par la JVM.
  - name: BPL_JVM_THREAD_COUNT
    value: "50"
  - name: JAVA_TOOL_OPTIONS
    value: "-XX:MaxRAMPercentage=75.0 -XX:+UseG1GC"
```

### 🔹 Volume monté (secrets-rhdemo.yml)

```yaml
volumeMounts:
  - name: secrets
    mountPath: /workspace/secrets  # ← Fichier monté ici
    readOnly: true

volumes:
  - name: secrets
    secret:
      secretName: rhdemo-app-secrets  # ← Kubernetes Secret
      items:
        - key: secrets-rhdemo.yml
          path: secrets-rhdemo.yml
```

**Vérification dans le pod** :

```bash
# Se connecter au pod
POD_NAME=$(kubectl get pods -n rhdemo-stagingkub -l app=rhdemo-app -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it $POD_NAME -n rhdemo-stagingkub -- bash

# Vérifier le fichier monté
cat /workspace/secrets/secrets-rhdemo.yml

# Vérifier les variables d'environnement
env | grep SPRING
```

---

## 🔄 4. Ordre de priorité de configuration Spring Boot

Spring Boot charge les propriétés dans cet ordre (du plus faible au plus fort) :

```
1. application.yml (embarqué)
   ↓
2. application-stagingkub.yml (profile actif via SPRING_PROFILES_ACTIVE)
   ↓
3. /workspace/secrets/secrets-rhdemo.yml (via spring.config.import)
   ↓
4. Variables d'environnement (SPRING_DATASOURCE_URL, etc.)
   ↓ (priorité la plus forte)
```

**Exemple concret** pour `spring.datasource.url` :

```
application.yml:               jdbc:postgresql://localhost:5432/dbrhdemo
                              ↓ surchargé par
Variable d'environnement:      jdbc:postgresql://postgresql-rhdemo:5432/rhdemo
                              ↓ (valeur finale)
                              jdbc:postgresql://postgresql-rhdemo:5432/rhdemo ✅
```

---

## 📊 5. Tableau récapitulatif des sources de configuration

| Paramètre | Source | Méthode |
|-----------|--------|---------|
| **spring.datasource.url** | Variable env (Helm) | `SPRING_DATASOURCE_URL` |
| **spring.datasource.username** | Variable env (Helm) | `SPRING_DATASOURCE_USERNAME` |
| **spring.datasource.password** | Secret K8s → Variable env | `rhdemo-db-secret` → `SPRING_DATASOURCE_PASSWORD` |
| **client-secret Keycloak** | Volume monté | `secrets-rhdemo.yml` → `${rhdemo.client.registration.keycloak.client.secret}` |
| **authorization-uri** | application-stagingkub.yml | Embarqué |
| **token-uri** | application-stagingkub.yml | Embarqué |
| **redirect-uri** | Variable env (Helm) | `SPRING_SECURITY_OAUTH2_CLIENT_REGISTRATION_KEYCLOAK_REDIRECT_URI` |
| **server.port** | Variable env (Helm) | `SERVER_PORT` |
| **actuator endpoints** | Variable env (Helm) | `MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE` |

---

## 🎯 6. Résumé : Comment ça marche 

### Lors du déploiement CD (Jenkinsfile-CD) :

1. **Pipeline lit secrets-stagingkub.yml** (chiffré SOPS) → déchiffre avec clé AGE
2. **Crée secrets-rhdemo.yml** (extrait uniquement les secrets pour rhDemo)
3. **Crée les Kubernetes Secrets** dans le namespace `rhdemo-stagingkub`
4. **Helm déploie** avec :
   - Image Docker contenant `application.yml` + `application-stagingkub.yml`
   - Variables d'environnement injectées
   - Volume secret monté

### Au démarrage du pod :

1. **Spring Boot démarre** avec `SPRING_PROFILES_ACTIVE=stagingkub`
2. **Charge** `application.yml` (base)
3. **Merge** avec `application-stagingkub.yml` (profile)
4. **Importe** `/workspace/secrets/secrets-rhdemo.yml` (secrets)
5. **Surcharge** avec variables d'environnement (priorité max)
6. **Application configurée** ✅

---

## 🔧 7. Modification des paramètres

### Modifier un paramètre non-secret

**Exemple** : Changer le nombre de threads JVM

1. **Modifier values.yaml** :
```yaml
rhdemo:
  jvm:
    threadCount: 100  # Au lieu de 50
```

2. **Redéployer** :
```bash
cd rhDemo
jenkins-cli build Jenkinsfile-CD -p IMAGE_TAG=1.1.0-SNAPSHOT-123
```

### Modifier un secret

**Exemple** : Changer le mot de passe PostgreSQL

1. **Modifier le fichier chiffré** :
```bash
cd rhDemo/secrets
sops secrets-stagingkub.yml
# Modifier la valeur de rhdemo.datasource.password.pg
```

2. **Commit et push** :
```bash
git add secrets-stagingkub.yml
git commit -m "feat: mise à jour mot de passe PostgreSQL"
git push
```

3. **Redéployer via pipeline CD** (qui va déchiffrer et recréer les secrets K8s)

### Modifier une configuration Helm via --set

Pour un changement ponctuel sans modifier values.yaml :

```bash
helm upgrade rhdemo rhDemo/infra/stagingkub/helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --set rhdemo.replicaCount=2 \
  --set rhdemo.resources.limits.memory=2Gi
```

---

## 🐛 8. Debugging de la configuration

### Vérifier la configuration active dans le pod

```bash
# Se connecter au pod
POD_NAME=$(kubectl get pods -n rhdemo-stagingkub -l app=rhdemo-app -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it $POD_NAME -n rhdemo-stagingkub -- bash

# Voir toutes les variables d'environnement
env | sort

# Voir les fichiers montés
ls -la /workspace/secrets/
cat /workspace/secrets/secrets-rhdemo.yml
```

### Vérifier via l'endpoint Actuator

```bash
# Depuis votre machine (si ingress configuré)
curl -k https://rhdemo-stagingkub.intra.leuwen-lc.fr/actuator/env | jq

# Ou en port-forward
kubectl port-forward -n rhdemo-stagingkub $POD_NAME 9000:9000
curl http://localhost:9000/actuator/env | jq
```

### Vérifier les logs Spring Boot

```bash
# Logs du pod
kubectl logs -n rhdemo-stagingkub $POD_NAME

# Suivre les logs en temps réel
kubectl logs -n rhdemo-stagingkub -f $POD_NAME

# Logs avec filtrage
kubectl logs -n rhdemo-stagingkub $POD_NAME | grep -i "datasource\|oauth2\|keycloak"
```

### Vérifier les secrets Kubernetes

```bash
# Lister les secrets
kubectl get secrets -n rhdemo-stagingkub

# Voir le contenu du secret rhdemo-db-secret
kubectl get secret rhdemo-db-secret -n rhdemo-stagingkub -o jsonpath='{.data.password}' | base64 -d

# Voir le contenu du fichier secrets-rhdemo.yml
kubectl get secret rhdemo-app-secrets -n rhdemo-stagingkub -o jsonpath='{.data.secrets-rhdemo\.yml}' | base64 -d
```

---

## ✅ Avantages de cette architecture

✅ **Séparation secrets/config** : secrets jamais en clair dans Git
✅ **Flexibilité** : surcharge facile via variables d'environnement
✅ **Sécurité** : secrets chiffrés SOPS + Kubernetes Secrets
✅ **Portabilité** : même image Docker pour tous les environnements
✅ **Traçabilité** : config versionnée, secrets externalisés
✅ **Debugging facile** : Actuator expose toute la configuration

---

## 📚 Références

- [Spring Boot External Configuration](https://docs.spring.io/spring-boot/docs/current/reference/html/features.html#features.external-config)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Helm Values](https://helm.sh/docs/chart_template_guide/values_files/)
- [SOPS - Secrets OPerationS](https://github.com/getsops/sops)

---

**Dernière mise à jour** : 2025-12-16
