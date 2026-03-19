# Certificats TLS pour l'environnement stagingkub

Ce document décrit les deux options de gestion des certificats TLS pour l'environnement Kubernetes stagingkub :
1. **Certificats auto-signés** : pour les environnements isolés sans accès Internet
2. **Certificats Let's Encrypt** : pour les environnements avec accès Internet et un domaine DNS valide

## Vue d'ensemble

| Aspect | Auto-signé | Let's Encrypt |
|--------|------------|---------------|
| **Domaine** | `*.intra.leuwen-lc.fr` | `*.intra.leuwen-lc.fr` |
| **Validité** | 365 jours (renouvelable manuellement) | 90 jours (renouvellement automatique) |
| **Prérequis** | Aucun | cert-manager + webhook DNS (Infomaniak) |
| **Avertissement navigateur** | Oui (certificat non reconnu) | Non |
| **Logout OIDC** | ❌ Non fonctionnel | ✅ Fonctionnel |
| **Cas d'usage** | Développement local, environnement isolé | Staging proche production |

---

## Architecture TLS avec NGINX Gateway Fabric

Depuis la migration vers **NGINX Gateway Fabric 2.4.2**, la terminaison TLS est centralisée au niveau du `shared-gateway` dans le namespace `nginx-gateway`. Les Ingress Kubernetes ne sont plus utilisés.

```
Internet → KinD (hostPort 443) → NodePort 32616 → shared-gateway (TLS terminé ici) → HTTPRoutes → Services
```

Le **shared-gateway** gère les certificats TLS pour tous les services :
- `rhdemo-stagingkub.intra.leuwen-lc.fr` → HTTPRoute dans `rhdemo-stagingkub`
- `keycloak-stagingkub.intra.leuwen-lc.fr` → HTTPRoute dans `rhdemo-stagingkub`
- `grafana-stagingkub.intra.leuwen-lc.fr` → HTTPRoute dans `loki-stack`

Le certificat TLS est référencé dans `shared-gateway.yaml` (namespace `nginx-gateway`) :

```yaml
# infra/stagingkub/shared-gateway.yaml
spec:
  listeners:
    - name: https
      port: 443
      protocol: HTTPS
      tls:
        mode: Terminate
        certificateRefs:
          - name: shared-tls-cert      # auto-signé (init-stagingkub.sh)
          # - name: intra-wildcard-tls # Let's Encrypt (cert-manager)
```

---

## Option 1 : Certificats auto-signés

### Quand utiliser cette option ?

- Environnement de développement local sur un PC personnel
- Réseau isolé sans accès Internet
- Pas de domaine DNS public disponible
- Tests rapides sans configuration complexe

### Procédure d'installation

#### 1. Initialiser l'environnement

Le script `init-stagingkub.sh` génère automatiquement un certificat auto-signé et le charge dans les namespaces appropriés :

```bash
cd rhDemo/infra/stagingkub
./scripts/init-stagingkub.sh
```

Le script génère :
- `certs/tls.crt` : Certificat X.509 auto-signé
- `certs/tls.key` : Clé privée RSA 2048 bits
- Secret Kubernetes `shared-tls-cert` dans le namespace `nginx-gateway` (utilisé par le shared-gateway)
- Secret Kubernetes `rhdemo-tls-cert` dans le namespace `rhdemo-stagingkub` (**legacy, inutilisé** — à supprimer d'`init-stagingkub.sh` : le port-forward utilise HTTP direct, et sans DNS cluster Keycloak est de toute façon inaccessible hors cluster)

Le certificat couvre le domaine wildcard `*.intra.leuwen-lc.fr`.

#### 2. Configuration Helm pour rhdemo (auto-signé)

Avec les certificats auto-signés, **aucune modification de `values.yaml` n'est nécessaire** pour le TLS. La terminaison TLS est gérée par le `shared-gateway` créé par `init-stagingkub.sh`.

La section `gateway:` dans `infra/stagingkub/helm/rhdemo/values.yaml` configure uniquement le routage :

```yaml
gateway:
  enabled: true

  sharedGateway:
    name: shared-gateway
    namespace: nginx-gateway
    sectionName: https  # Listener du shared-gateway.yaml

  routes:
    - name: rhdemo-route
      hostname: rhdemo-stagingkub.intra.leuwen-lc.fr
      rules:
        - path: /
          pathType: PathPrefix
          serviceName: rhdemo-app
          servicePort: 9000

    - name: keycloak-route
      hostname: keycloak-stagingkub.intra.leuwen-lc.fr
      rules:
        - path: /
          pathType: PathPrefix
          serviceName: keycloak
          servicePort: 8080
```

> **Note** : La section `ingress:` n'existe plus dans `values.yaml`. Le TLS est entièrement géré par le `shared-gateway` dans le namespace `nginx-gateway`.

#### 3. Configuration Helm pour Grafana (auto-signé)

L'Ingress est désactivé dans `infra/stagingkub/helm/observability/grafana-values.yaml` :

```yaml
ingress:
  enabled: false  # Remplacé par Gateway API
```

Le script `install-observability.sh` crée automatiquement une HTTPRoute inline attachée au `shared-gateway` :

```bash
cd rhDemo/infra/stagingkub
./scripts/install-observability.sh
```

Ce script :
- Installe Loki et Grafana via Helm (sans Ingress)
- Crée une `HTTPRoute` dans `loki-stack` attachée au `shared-gateway` (namespace `nginx-gateway`) via `kubectl apply` inline
- Grafana est ainsi exposé via le même certificat `shared-tls-cert` que les autres services

> **Note** : Le fichier `infra/stagingkub/helm/observability/grafana-gateway.yaml` présent dans le dépôt est une **ancienne architecture** (gateway dédié dans `loki-stack` avec `intra-wildcard-tls`). Il n'est plus appliqué par les scripts. L'architecture active utilise le `shared-gateway` décrit ci-dessus.

#### 4. Déployer l'application

Le déploiement de l'application RHDemo se fait via le pipeline Jenkins CD :

```bash
# Lancer le pipeline CD depuis Jenkins
# Job: RHDemo-CD
# Paramètre: IMAGE_TAG=<VERSION>
```

Voir [Jenkinsfile-CD](../Jenkinsfile-CD) pour les détails du pipeline.

Alternativement, pour un déploiement manuel :

```bash
cd rhDemo/infra/stagingkub
helm upgrade --install rhdemo ./helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --set rhdemo.image.tag=<VERSION>
```

### Limitations avec certificats auto-signés

#### ⚠️ Logout OIDC non fonctionnel

Avec un certificat auto-signé, le **logout SSO Keycloak ne fonctionne pas**.

**Symptôme** : Après avoir cliqué sur "Logout", l'utilisateur reste connecté.

**Cause technique** :

Le logout OIDC nécessite que Spring Security découvre l'endpoint `end_session_endpoint` de Keycloak. Cette découverte se fait via :

```
https://keycloak-stagingkub.intra.leuwen-lc.fr/realms/RHDemo/.well-known/openid-configuration
```

Avec un certificat auto-signé :
1. Spring Boot tente de télécharger ce fichier en HTTPS
2. Le client HTTP Java rejette le certificat (non reconnu par la CA)
3. La découverte échoue → pas d'endpoint de logout → logout local uniquement

**Contournement** : L'utilisateur peut se déconnecter manuellement de Keycloak via :
```
https://keycloak-stagingkub.intra.leuwen-lc.fr/realms/RHDemo/protocol/openid-connect/logout
```

#### Avertissement navigateur

Le navigateur affichera un avertissement de sécurité. Pour le contourner :
- Firefox : "Accepter le risque et continuer"
- Chrome : Taper `thisisunsafe` sur la page d'erreur
- Ou importer le certificat CA dans le navigateur

---

## Option 2 : Certificats Let's Encrypt (cert-manager)

### Quand utiliser cette option ?

- Environnement staging proche de la production
- Domaine DNS valide avec accès à l'API du registrar
- Besoin du logout OIDC fonctionnel
- Éviter les avertissements navigateur

### Prérequis

1. **cert-manager** installé dans le cluster
2. **Webhook DNS** pour le challenge DNS-01 (ex: Infomaniak)
3. **Domaine DNS** avec accès API pour créer des enregistrements TXT

### Procédure d'installation

#### 1. Installer cert-manager

```bash
# Ajouter le repo Helm
helm repo add jetstack https://charts.jetstack.io
helm repo update

# Installer cert-manager avec les CRDs
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set crds.enabled=true
```

#### 2. Installer le webhook DNS (exemple Infomaniak)

```bash
# Installer le webhook Infomaniak pour les challenges DNS-01
helm repo add infomaniak-webhook https://infomaniak.github.io/cert-manager-webhook-infomaniak
helm install infomaniak-webhook infomaniak-webhook/cert-manager-webhook-infomaniak \
  --namespace cert-manager-infomaniak \
  --create-namespace
```

#### 3. Configurer le ClusterIssuer

Créer le fichier `cluster-issuer.yaml` :

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-infomaniak-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: votre-email@domaine.fr
    privateKeySecretRef:
      name: letsencrypt-infomaniak-prod-key
    solvers:
      - dns01:
          webhook:
            groupName: acme.infomaniak.com
            solverName: infomaniak
            config:
              apiTokenSecretRef:
                name: infomaniak-api-credentials
                key: api-token
```

Appliquer :
```bash
kubectl apply -f cluster-issuer.yaml
```

#### 4. Créer le certificat wildcard dans nginx-gateway

Le certificat doit être créé dans le namespace `nginx-gateway` car c'est le `shared-gateway` qui s'en sert pour la terminaison TLS :

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: intra-wildcard
  namespace: nginx-gateway
spec:
  secretName: intra-wildcard-tls
  dnsNames:
    - "*.intra.leuwen-lc.fr"
  issuerRef:
    name: letsencrypt-infomaniak-prod
    kind: ClusterIssuer
```

> **Note** : Contrairement à l'ancienne configuration Ingress, le certificat est dans le namespace `nginx-gateway` (pas `rhdemo-stagingkub` ni `loki-stack`), car le `shared-gateway` centralise toute la terminaison TLS.

#### 5. Mettre à jour le shared-gateway pour Let's Encrypt

Modifier `infra/stagingkub/shared-gateway.yaml` pour référencer le certificat Let's Encrypt :

```yaml
spec:
  listeners:
    - name: https
      port: 443
      protocol: HTTPS
      tls:
        mode: Terminate
        certificateRefs:
          - name: intra-wildcard-tls  # Let's Encrypt
```

Appliquer :
```bash
kubectl apply -f infra/stagingkub/shared-gateway.yaml
```

#### 6. Vérifier les certificats

```bash
# Vérifier le statut du certificat
kubectl get certificates -n nginx-gateway

# Vérifier les détails
kubectl describe certificate intra-wildcard -n nginx-gateway

# Vérifier le contenu du certificat
kubectl get secret intra-wildcard-tls -n nginx-gateway \
  -o jsonpath='{.data.tls\.crt}' | base64 -d | \
  openssl x509 -noout -text | grep -E "(Subject:|DNS:|Not After)"
```

#### 7. Configuration Helm pour rhdemo (Let's Encrypt)

**Aucune modification de `values.yaml` n'est nécessaire** : la configuration `gateway:` dans `values.yaml` est identique pour les deux options. Le certificat est résolu au niveau du `shared-gateway`, pas du chart Helm.

```yaml
# infra/stagingkub/helm/rhdemo/values.yaml - identique auto-signé et Let's Encrypt
gateway:
  enabled: true
  sharedGateway:
    name: shared-gateway
    namespace: nginx-gateway
    sectionName: https
```

#### 8. Configuration pour Grafana (Let's Encrypt)

Identique à l'option auto-signée : `ingress.enabled: false` dans `grafana-values.yaml`, HTTPRoute attachée au `shared-gateway` via `install-observability.sh`. Aucune modification supplémentaire.

Le certificat `intra-wildcard-tls` étant dans le namespace `nginx-gateway` (là où réside le `shared-gateway`), Grafana bénéficie automatiquement du certificat Let's Encrypt sans configuration supplémentaire dans `loki-stack`.

#### 9. Déployer

Le déploiement se fait via le pipeline Jenkins CD :

```bash
# Lancer le pipeline CD depuis Jenkins
# Job: RHDemo-CD
# Paramètre: IMAGE_TAG=<VERSION>
```

Voir [Jenkinsfile-CD](../Jenkinsfile-CD) pour les détails du pipeline.

### Avantages de Let's Encrypt

- ✅ **Logout OIDC fonctionnel** : Spring peut découvrir `end_session_endpoint`
- ✅ **Pas d'avertissement navigateur** : Certificat reconnu par les CA
- ✅ **Renouvellement automatique** : cert-manager gère le renouvellement
- ✅ **Configuration proche production** : Même workflow qu'en production

---

## Comparaison des configurations

### Où est configuré le certificat ?

| Élément | Auto-signé | Let's Encrypt |
|---------|------------|---------------|
| **Secret TLS** | `shared-tls-cert` dans `nginx-gateway` | `intra-wildcard-tls` dans `nginx-gateway` |
| **Créé par** | `init-stagingkub.sh` (openssl) | cert-manager |
| **Référencé dans** | `shared-gateway.yaml` | `shared-gateway.yaml` |
| **Renouvellement** | Manuel (annuel) | Automatique (90j) |
| **values.yaml rhdemo** | Inchangé | Inchangé |
| **grafana-values.yaml** | `ingress.enabled: false` | `ingress.enabled: false` |

### Résolution DNS (/etc/hosts)

Identique pour les deux options :
```
127.0.0.1 rhdemo-stagingkub.intra.leuwen-lc.fr
127.0.0.1 keycloak-stagingkub.intra.leuwen-lc.fr
127.0.0.1 grafana-stagingkub.intra.leuwen-lc.fr
```

---

## Dépannage

### Certificat auto-signé expiré

```bash
# Supprimer les anciens certificats
rm -f infra/stagingkub/certs/tls.*
kubectl delete secret shared-tls-cert -n nginx-gateway

# Régénérer (relancer init-stagingkub.sh qui recrée le secret)
./scripts/init-stagingkub.sh
```

### Certificat Let's Encrypt non généré

```bash
# Vérifier les événements
kubectl describe certificate intra-wildcard -n nginx-gateway

# Vérifier les challenges
kubectl get challenges -A

# Vérifier les logs cert-manager
kubectl logs -n cert-manager deploy/cert-manager -f
```

### HTTPRoute non attachée au Gateway

```bash
# Vérifier le statut des HTTPRoutes
kubectl get httproute -n rhdemo-stagingkub
kubectl get httproute -n loki-stack

# Vérifier les détails (section "Parents" pour voir si attaché)
kubectl describe httproute rhdemo-route -n rhdemo-stagingkub
```

### Erreur "certificate signed by unknown authority"

Avec un certificat auto-signé, cette erreur est normale pour les appels HTTPS serveur-à-serveur. C'est pourquoi :
- `token-uri` et `jwk-set-uri` utilisent HTTP interne (`http://keycloak:8080/...`)
- Seul `authorization-uri` utilise HTTPS (car c'est le navigateur qui y accède)

---

## Recommandations

| Environnement | Recommandation |
|---------------|----------------|
| PC développeur isolé | Certificat auto-signé |
| PC développeur avec Internet | Let's Encrypt si domaine disponible |
| Serveur staging partagé | Let's Encrypt obligatoire |
| CI/CD (ephemere) | Certificat auto-signé (environnement jetable) |

---

## Références

- [cert-manager Documentation](https://cert-manager.io/docs/)
- [Let's Encrypt](https://letsencrypt.org/)
- [NGINX Gateway Fabric 2.4.2](https://docs.nginx.com/nginx-gateway-fabric/) (correctif CVE-2026-33186)
- [Gateway API - Kubernetes](https://gateway-api.sigs.k8s.io/)
- [Spring Security OAuth2 Client](https://docs.spring.io/spring-security/reference/servlet/oauth2/client/index.html)
- [Keycloak OIDC Logout](https://www.keycloak.org/docs/latest/securing_apps/#logout)
