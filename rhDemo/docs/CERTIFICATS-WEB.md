# Certificats TLS pour l'environnement stagingkub

Ce document décrit les deux options de gestion des certificats TLS pour l'environnement Kubernetes stagingkub :
1. **Certificats auto-signés** : pour les environnements isolés sans accès Internet
2. **Certificats Let's Encrypt** : pour les environnements avec accès Internet et un domaine DNS valide

## Vue d'ensemble

| Aspect | Auto-signé | Let's Encrypt |
|--------|------------|---------------|
| **Domaine** | `*.stagingkub.intra.leuwen-lc.fr` | `*.intra.leuwen-lc.fr` |
| **Validité** | 365 jours (renouvelable manuellement) | 90 jours (renouvellement automatique) |
| **Prérequis** | Aucun | cert-manager + webhook DNS (Infomaniak) |
| **Avertissement navigateur** | Oui (certificat non reconnu) | Non |
| **Logout OIDC** | ❌ Non fonctionnel | ✅ Fonctionnel |
| **Cas d'usage** | Développement local, environnement isolé | Staging proche production |

---

## Option 1 : Certificats auto-signés

### Quand utiliser cette option ?

- Environnement de développement local sur un PC personnel
- Réseau isolé sans accès Internet
- Pas de domaine DNS public disponible
- Tests rapides sans configuration complexe

### Procédure d'installation

#### 1. Initialiser l'environnement

Le script `init-stagingkub.sh` génère automatiquement un certificat auto-signé :

```bash
cd rhDemo/infra/stagingkub
./scripts/init-stagingkub.sh
```

Le script génère :
- `certs/tls.crt` : Certificat X.509 auto-signé
- `certs/tls.key` : Clé privée RSA 2048 bits
- Secret Kubernetes `rhdemo-tls-cert` dans le namespace `rhdemo-stagingkub`

Le certificat couvre :
- `*.stagingkub.intra.leuwen-lc.fr` (wildcard)
- `rhdemo.stagingkub.intra.leuwen-lc.fr` (SAN)
- `keycloak.stagingkub.intra.leuwen-lc.fr` (SAN)

#### 2. Configurer Helm pour utiliser le certificat auto-signé

Modifier `infra/stagingkub/helm/rhdemo/values.yaml` :

```yaml
ingress:
  tls:
    enabled: true
    secretName: rhdemo-tls-cert  # Certificat auto-signé
```

Pour Grafana, modifier `infra/stagingkub/helm/observability/grafana-values.yaml` :

```yaml
ingress:
  tls:
    - secretName: grafana-tls-cert  # Certificat auto-signé Grafana
      hosts:
        - grafana.stagingkub.intra.leuwen-lc.fr
```

#### 3. Installer la stack d'observabilité (Grafana)

Le script `install-observability.sh` génère automatiquement le certificat auto-signé pour Grafana :

```bash
cd rhDemo/infra/stagingkub
./scripts/install-observability.sh
```

Ce script :

- Crée le namespace `loki-stack`
- Génère un certificat auto-signé pour `grafana.stagingkub.intra.leuwen-lc.fr`
- Crée le secret `grafana-tls-cert` dans le namespace `loki-stack`
- Installe Loki et Grafana via Helm

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
https://keycloak.stagingkub.intra.leuwen-lc.fr/realms/RHDemo/.well-known/openid-configuration
```

Avec un certificat auto-signé :
1. Spring Boot tente de télécharger ce fichier en HTTPS
2. Le client HTTP Java rejette le certificat (non reconnu par la CA)
3. La découverte échoue → pas d'endpoint de logout → logout local uniquement

**Contournement** : L'utilisateur peut se déconnecter manuellement de Keycloak via :
```
https://keycloak.stagingkub.intra.leuwen-lc.fr/realms/RHDemo/protocol/openid-connect/logout
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

#### 4. Créer les certificats

Pour rhdemo-stagingkub :
```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: intra-wildcard
  namespace: rhdemo-stagingkub
spec:
  secretName: intra-wildcard-tls
  dnsNames:
    - "*.intra.leuwen-lc.fr"
  issuerRef:
    name: letsencrypt-infomaniak-prod
    kind: ClusterIssuer
```

Pour loki-stack (Grafana) :
```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: intra-wildcard
  namespace: loki-stack
spec:
  secretName: intra-wildcard-tls
  dnsNames:
    - "*.intra.leuwen-lc.fr"
  issuerRef:
    name: letsencrypt-infomaniak-prod
    kind: ClusterIssuer
```

#### 5. Vérifier les certificats

```bash
# Vérifier le statut
kubectl get certificates -A

# Vérifier les détails
kubectl describe certificate intra-wildcard -n rhdemo-stagingkub

# Vérifier le contenu du certificat
kubectl get secret intra-wildcard-tls -n rhdemo-stagingkub \
  -o jsonpath='{.data.tls\.crt}' | base64 -d | \
  openssl x509 -noout -text | grep -E "(Subject:|DNS:|Not After)"
```

#### 6. Configurer Helm pour Let's Encrypt

Les fichiers `values.yaml` sont déjà configurés par défaut pour Let's Encrypt :

`infra/stagingkub/helm/rhdemo/values.yaml` :
```yaml
ingress:
  tls:
    enabled: true
    secretName: intra-wildcard-tls  # Let's Encrypt
```

`infra/stagingkub/helm/observability/grafana-values.yaml` :
```yaml
ingress:
  tls:
    - secretName: intra-wildcard-tls  # Let's Encrypt
      hosts:
        - grafana.stagingkub.intra.leuwen-lc.fr
```

#### 7. Déployer

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

## Comparaison des fichiers de configuration

### Différences dans values.yaml

| Paramètre | Auto-signé | Let's Encrypt |
|-----------|------------|---------------|
| `ingress.tls.secretName` | `rhdemo-tls-cert` | `intra-wildcard-tls` |
| Secret créé par | `init-stagingkub.sh` | cert-manager |
| Renouvellement | Manuel (annuel) | Automatique (90j) |

### Résolution DNS (/etc/hosts)

Identique pour les deux options :
```
127.0.0.1 rhdemo.stagingkub.intra.leuwen-lc.fr
127.0.0.1 keycloak.stagingkub.intra.leuwen-lc.fr
127.0.0.1 grafana.stagingkub.intra.leuwen-lc.fr
```

---

## Dépannage

### Certificat auto-signé expiré

```bash
# Supprimer l'ancien certificat
rm -f infra/stagingkub/certs/tls.*
kubectl delete secret rhdemo-tls-cert -n rhdemo-stagingkub

# Régénérer
./scripts/init-stagingkub.sh
```

### Certificat Let's Encrypt non généré

```bash
# Vérifier les événements
kubectl describe certificate intra-wildcard -n rhdemo-stagingkub

# Vérifier les challenges
kubectl get challenges -A

# Vérifier les logs cert-manager
kubectl logs -n cert-manager deploy/cert-manager -f
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
- [Spring Security OAuth2 Client](https://docs.spring.io/spring-security/reference/servlet/oauth2/client/index.html)
- [Keycloak OIDC Logout](https://www.keycloak.org/docs/latest/securing_apps/#logout)
