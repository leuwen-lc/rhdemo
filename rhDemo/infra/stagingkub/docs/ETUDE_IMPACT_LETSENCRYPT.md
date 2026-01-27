# Étude d'Impact : Migration vers Let's Encrypt avec Certbot

**Date**: 2026-01-09
**Auteur**: Claude Code
**Environnement**: stagingkub (KinD)
**Domaine**: leuwen.fr
**Sous-domaines cibles**:
- `rhdemo.stagingkub.leuwen.fr`
- `keycloak.stagingkub.leuwen.fr`

---

## 📋 Table des matières

1. [Résumé exécutif](#résumé-exécutif)
2. [Contexte et situation actuelle](#contexte-et-situation-actuelle)
3. [Objectifs de la migration](#objectifs-de-la-migration)
4. [Analyse des contraintes techniques](#analyse-des-contraintes-techniques)
5. [Solutions techniques envisagées](#solutions-techniques-envisagées)
6. [Impacts sur l'infrastructure](#impacts-sur-linfrastructure)
7. [Plan de migration recommandé](#plan-de-migration-recommandé)
8. [Risques et mitigations](#risques-et-mitigations)
9. [Estimation des efforts](#estimation-des-efforts)
10. [Recommandations](#recommandations)

---

## 📊 Résumé exécutif

### Situation actuelle
- **Certificats auto-signés** générés par OpenSSL (CN=*.stagingkub.intra.leuwen-lc.fr)
- **Validité**: 365 jours (expire Dec 18 2026)
- **Domaines locaux**: rhdemo.stagingkub.intra.leuwen-lc.fr, keycloak.stagingkub.intra.leuwen-lc.fr
- **Stockage**: Fichiers locaux dans `infra/stagingkub/certs/`
- **Gestion**: Manuelle via `init-stagingkub.sh`

### Objectif
Migrer vers **Let's Encrypt** pour obtenir des certificats signés par une AC reconnue, permettant l'accès sans avertissement SSL.

### Recommandation finale
**❌ NON RECOMMANDÉ pour l'environnement stagingkub actuel**

**Raisons**:
1. ⚠️ Let's Encrypt ne peut pas émettre de certificats pour un cluster Kubernetes local (KinD) non accessible publiquement
2. 🔒 Les domaines doivent être validables via HTTP-01 (port 80) ou DNS-01 (enregistrements DNS)
3. 💰 Complexité technique élevée pour un gain limité en staging
4. ⏱️ Renouvellement automatique nécessite une infrastructure permanente

**Alternative recommandée**:
- **Garder les certificats auto-signés en staging** (environnement de test)
- **Utiliser Let's Encrypt uniquement pour la production** (déployée sur infrastructure publique)

---

## 🔍 Contexte et situation actuelle

### Architecture actuelle des certificats

#### Génération (init-stagingkub.sh, lignes 342-357)
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$CERTS_DIR/tls.key" \
  -out "$CERTS_DIR/tls.crt" \
  -subj "/CN=*.stagingkub.intra.leuwen-lc.fr/O=RHDemo" \
  -addext "subjectAltName=DNS:rhdemo.stagingkub.intra.leuwen-lc.fr,DNS:keycloak.stagingkub.intra.leuwen-lc.fr"
```

#### Stockage
```
rhDemo/infra/stagingkub/certs/
├── tls.crt (1.3K) - Certificat auto-signé
└── tls.key (1.7K) - Clé privée (permissions 600)
```

#### Déploiement Kubernetes
```bash
kubectl create secret tls rhdemo-tls-cert \
  --cert="$CERTS_DIR/tls.crt" \
  --key="$CERTS_DIR/tls.key" \
  --namespace rhdemo-stagingkub
```

#### Référence dans Ingress (helm/rhdemo/values.yaml)
```yaml
ingress:
  tls:
    enabled: true
    secretName: rhdemo-tls-cert
```

### Points de référence actuels

| Fichier | Ligne | Référence |
|---------|-------|-----------|
| `scripts/init-stagingkub.sh` | 342-365 | Génération OpenSSL + création secret |
| `helm/rhdemo/values.yaml` | 243 | `secretName: rhdemo-tls-cert` |
| `helm/rhdemo/templates/ingress.yaml` | 19 | `secretName: {{ .Values.ingress.tls.secretName }}` |
| `scripts/validate.sh` | 174, 229-245 | Validation fichiers tls.crt/tls.key |
| `helm/observability/grafana-values.yaml` | 39-42 | Secret TLS Grafana |
| `scripts/install-loki.sh` | 58-71 | Génération certificat Grafana |

---

## 🎯 Objectifs de la migration

### Objectifs initiaux (avant analyse)
1. ✅ Obtenir des certificats signés par une AC reconnue (Let's Encrypt)
2. ✅ Éliminer les avertissements SSL dans les navigateurs
3. ✅ Automatiser le renouvellement des certificats (validité 90 jours)
4. ✅ Utiliser des domaines publics: `rhdemo.stagingkub.leuwen.fr` et `keycloak.stagingkub.leuwen.fr`

### Objectifs révisés (après analyse)
1. ❌ **Impossible**: Let's Encrypt nécessite une validation publique (HTTP-01 ou DNS-01)
2. ❌ **Non applicable**: stagingkub est un cluster KinD local (127.0.0.1), non accessible depuis Internet
3. ⚠️ **Complexe**: Nécessiterait un tunnel reverse (ngrok, cloudflare tunnel) ou validation DNS-01

---

## 🚧 Analyse des contraintes techniques

### 1. Contrainte principale: Validation Let's Encrypt

Let's Encrypt nécessite de **prouver que vous contrôlez le domaine** via l'un des challenges suivants:

#### a) HTTP-01 Challenge (port 80)
**Principe**: Let's Encrypt envoie une requête HTTP à `http://rhdemo.stagingkub.leuwen.fr/.well-known/acme-challenge/<TOKEN>`

**Exigences**:
- ✅ Nom de domaine public résolvable via DNS
- ❌ **Serveur accessible depuis Internet sur le port 80**
- ❌ **Bloqué par**: stagingkub tourne en local (127.0.0.1), non exposé publiquement

**Résultat**: ❌ **IMPOSSIBLE** pour un cluster KinD local

---

#### b) DNS-01 Challenge
**Principe**: Let's Encrypt demande de créer un enregistrement TXT DNS `_acme-challenge.rhdemo.stagingkub.leuwen.fr`

**Exigences**:
- ✅ Accès API à votre registrar DNS (OVH, Cloudflare, Route53, etc.)
- ✅ Automatisation via certbot plugin (ex: `certbot-dns-ovh`, `certbot-dns-cloudflare`)
- ❌ **Complexité**: Configuration API + credentials

**Résultat**: ✅ **POSSIBLE** mais complexe

---

#### c) TLS-ALPN-01 Challenge (port 443)
**Principe**: Let's Encrypt envoie une requête TLS-ALPN sur le port 443

**Exigences**:
- ✅ Nom de domaine public résolvable
- ❌ **Serveur accessible depuis Internet sur le port 443**

**Résultat**: ❌ **IMPOSSIBLE** pour un cluster KinD local

---

### 2. Contrainte infrastructure: Cluster KinD local

#### Architecture actuelle
```
┌─────────────────────────────────────────┐
│   Machine locale (127.0.0.1)            │
│                                          │
│   ┌────────────────────────────────┐    │
│   │  Cluster KinD "rhdemo"         │    │
│   │                                │    │
│   │  Nginx Ingress Controller      │    │
│   │  ├─ NodePort 31792 → 80        │    │
│   │  └─ NodePort 32616 → 443       │    │
│   │                                │    │
│   │  Services:                     │    │
│   │  ├─ rhdemo-app                 │    │
│   │  └─ keycloak                   │    │
│   └────────────────────────────────┘    │
│                                          │
│   /etc/hosts:                            │
│   127.0.0.1 rhdemo.stagingkub.intra.leuwen-lc.fr     │
│   127.0.0.1 keycloak.stagingkub.intra.leuwen-lc.fr   │
└─────────────────────────────────────────┘
```

**Problème**: Let's Encrypt ne peut pas accéder à `127.0.0.1` depuis Internet.

---

### 3. Contrainte DNS: Résolution publique vs locale

#### Configuration actuelle
- **DNS local**: Enregistrements `/etc/hosts` pointant vers `127.0.0.1`
- **Domaine public**: `leuwen.fr` existe mais ne pointe pas vers le cluster local

#### Configuration requise pour Let's Encrypt
```
Enregistrement DNS public:
rhdemo.stagingkub.leuwen.fr.   A   <IP_PUBLIQUE>
keycloak.stagingkub.leuwen.fr. A   <IP_PUBLIQUE>
```

**Problème**: Votre cluster KinD n'a pas d'IP publique.

---

### 4. Contrainte renouvellement: Automatisation

Let's Encrypt émet des certificats valides **90 jours**. Le renouvellement doit être automatisé.

**Options**:
1. **Cron job** sur la machine hôte (exécute certbot tous les jours)
2. **cert-manager** dans Kubernetes (renouvellement automatique)

**Problème**: Nécessite que le cluster soit accessible 24/7 pour la validation.

---

## 💡 Solutions techniques envisagées

### Solution 1: Tunnel reverse (ngrok, cloudflare tunnel)

#### Principe
Exposer le cluster KinD local via un tunnel reverse sécurisé.

```
Internet → Tunnel (ngrok/cloudflare) → Machine locale → KinD cluster
```

#### Mise en œuvre
1. Installer ngrok ou cloudflare tunnel
2. Créer un tunnel vers `localhost:80` et `localhost:443`
3. Configurer DNS pour pointer vers l'URL du tunnel
4. Utiliser certbot avec HTTP-01 challenge

#### Avantages
- ✅ Permet la validation Let's Encrypt HTTP-01
- ✅ Pas besoin d'API DNS

#### Inconvénients
- ❌ **Coût**: Ngrok Pro ($8-20/mois) pour domaines personnalisés
- ❌ **Complexité**: Configuration tunnel + DNS
- ❌ **Dépendance**: Service tiers nécessaire 24/7
- ❌ **Sécurité**: Expose le cluster local sur Internet
- ❌ **Maintenance**: Tunnel doit rester actif

#### Recommandation
❌ **Non recommandé** pour un environnement de staging/test.

---

### Solution 2: Validation DNS-01 avec plugin certbot

#### Principe
Utiliser l'API DNS de votre registrar pour valider le domaine.

```
Certbot → API DNS (OVH/Cloudflare) → Créer TXT _acme-challenge
Let's Encrypt → Vérifie TXT → Émet certificat
```

#### Mise en œuvre
1. Installer certbot + plugin DNS (ex: `certbot-dns-ovh`)
2. Configurer credentials API DNS
3. Exécuter `certbot certonly --dns-ovh -d rhdemo.stagingkub.leuwen.fr`
4. Copier les certificats dans `infra/stagingkub/certs/`
5. Recréer le secret Kubernetes

#### Avantages
- ✅ Pas besoin d'exposer le cluster publiquement
- ✅ Validation indépendante de l'infrastructure
- ✅ Certificats signés par Let's Encrypt

#### Inconvénients
- ❌ **Configuration API**: Nécessite credentials API DNS
- ❌ **Plugin dépendant**: Doit correspondre à votre registrar (OVH, Cloudflare, Gandi, etc.)
- ❌ **Renouvellement manuel**: Tous les 90 jours (sauf cron job)
- ❌ **Complexité CI/CD**: Jenkins doit avoir accès aux credentials API DNS

#### Recommandation
⚠️ **Envisageable** mais complexité élevée pour un environnement de test.

---

### Solution 3: cert-manager dans Kubernetes

#### Principe
Installer cert-manager dans le cluster KinD pour automatiser la gestion des certificats.

```
cert-manager → Let's Encrypt (DNS-01) → Renouvellement automatique
```

#### Mise en œuvre
1. Installer cert-manager dans le cluster (`kubectl apply -f cert-manager.yaml`)
2. Créer un `ClusterIssuer` Let's Encrypt avec DNS-01
3. Créer un `Certificate` pour rhdemo et keycloak
4. cert-manager gère automatiquement le renouvellement

#### Avantages
- ✅ **Automatisation complète**: Renouvellement tous les 90 jours
- ✅ **Intégration native Kubernetes**
- ✅ **Best practice** pour production

#### Inconvénients
- ❌ **Nécessite DNS-01**: API DNS obligatoire
- ❌ **Complexité**: Configuration cert-manager + ClusterIssuer + Certificate
- ❌ **Overhead**: Pods supplémentaires dans le cluster
- ❌ **Overkill**: Pour un cluster de staging local

#### Recommandation
⚠️ **Réservé pour la production** (infrastructure permanente publique).

---

### Solution 4: Certificats Let's Encrypt générés manuellement (hors cluster)

#### Principe
Générer les certificats Let's Encrypt sur une machine publique, puis les copier dans stagingkub.

```
Machine publique (VPS) → Certbot DNS-01 → Télécharger certs → Copier dans KinD
```

#### Mise en œuvre
1. Utiliser un VPS temporaire ou votre machine locale avec certbot
2. Exécuter certbot avec DNS-01: `certbot certonly --manual --preferred-challenges dns`
3. Créer manuellement l'enregistrement TXT DNS demandé
4. Récupérer les certificats dans `/etc/letsencrypt/live/rhdemo.stagingkub.leuwen.fr/`
5. Copier `fullchain.pem` et `privkey.pem` dans `infra/stagingkub/certs/`

#### Avantages
- ✅ Certificats signés Let's Encrypt
- ✅ Pas besoin d'API DNS automatisée
- ✅ Pas de modifications majeures du code

#### Inconvénients
- ❌ **Renouvellement manuel**: Tous les 90 jours
- ❌ **Process manuel**: Créer TXT DNS à chaque fois
- ❌ **Non automatisable**: Ne peut pas être intégré dans CI/CD
- ❌ **Pas scalable**

#### Recommandation
⚠️ **Solution de contournement** acceptable pour tests ponctuels.

---

### Solution 5: Garder les certificats auto-signés (Recommandée)

#### Principe
Continuer à utiliser les certificats auto-signés pour l'environnement stagingkub.

#### Avantages
- ✅ **Simplicité**: Aucune modification nécessaire
- ✅ **Rapidité**: Déjà fonctionnel
- ✅ **Adapté au staging**: Les certificats auto-signés sont acceptables pour les tests
- ✅ **Pas de dépendances externes**

#### Inconvénients
- ❌ Avertissement SSL dans les navigateurs (mais acceptable en staging)

#### Recommandation
✅ **RECOMMANDÉ** pour stagingkub. Réserver Let's Encrypt pour la production.

---

## 📦 Impacts sur l'infrastructure

### 1. Fichiers à modifier (si migration Let's Encrypt)

#### Option DNS-01 (Certbot manuel)

| Fichier | Modifications requises | Impact |
|---------|------------------------|--------|
| `scripts/init-stagingkub.sh` | Remplacer génération OpenSSL par copie certificats Let's Encrypt | Moyen |
| `helm/rhdemo/values.yaml` | Changer `domain: stagingkub.intra.leuwen-lc.fr` → `stagingkub.leuwen.fr` | Faible |
| `Jenkinsfile-CD` | Ajout étape renouvellement certificats (optionnel) | Faible |
| `scripts/validate.sh` | Ajout validation expiration certificats Let's Encrypt | Faible |
| `.gitignore` | S'assurer que `certs/*.pem` est ignoré | Faible |
| `/etc/hosts` | Remplacer par DNS publics (ou garder pour résolution locale) | Faible |

#### Option cert-manager

| Fichier | Modifications requises | Impact |
|---------|------------------------|--------|
| `scripts/init-stagingkub.sh` | Installation cert-manager + ClusterIssuer | Élevé |
| `helm/rhdemo/templates/ingress.yaml` | Ajouter annotations cert-manager | Moyen |
| `helm/rhdemo/values.yaml` | Configuration issuer DNS-01 | Moyen |
| Nouveau: `cert-manager-values.yaml` | Configuration complète cert-manager | Élevé |
| Nouveau: `cluster-issuer.yaml` | Définition issuer Let's Encrypt | Moyen |

---

### 2. DNS et résolution de noms

#### Configuration DNS publique requise

**Avant (local)**:
```
/etc/hosts:
127.0.0.1 rhdemo.stagingkub.intra.leuwen-lc.fr
127.0.0.1 keycloak.stagingkub.intra.leuwen-lc.fr
```

**Après (public DNS)**:
```
Enregistrements DNS chez votre registrar:
rhdemo.stagingkub.leuwen.fr.   A   <IP_PUBLIQUE_ou_TUNNEL>
keycloak.stagingkub.leuwen.fr. A   <IP_PUBLIQUE_ou_TUNNEL>
```

**Problème**: Votre cluster KinD n'a pas d'IP publique.

**Solutions**:
- **Tunnel reverse** (ngrok/cloudflare): Utiliser l'IP/URL du tunnel
- **Split-horizon DNS**: Résolution locale via `/etc/hosts`, validation DNS-01 séparée

---

### 3. Secrets Kubernetes

#### Secret actuel
```bash
kubectl create secret tls rhdemo-tls-cert \
  --cert=certs/tls.crt \
  --key=certs/tls.key \
  -n rhdemo-stagingkub
```

#### Secret Let's Encrypt (certbot)
```bash
kubectl create secret tls rhdemo-tls-cert \
  --cert=/etc/letsencrypt/live/rhdemo.stagingkub.leuwen.fr/fullchain.pem \
  --key=/etc/letsencrypt/live/rhdemo.stagingkub.leuwen.fr/privkey.pem \
  -n rhdemo-stagingkub
```

#### Secret Let's Encrypt (cert-manager)
Géré automatiquement par cert-manager via une ressource `Certificate`.

---

### 4. CI/CD Pipeline (Jenkinsfile-CD)

#### Impacts

| Étape pipeline | Modification requise | Complexité |
|----------------|----------------------|------------|
| **Secrets SOPS** | Ajouter credentials API DNS | Faible |
| **Kubernetes Access** | Aucune | - |
| **Nouveau: Renouvellement certificats** | Étape optionnelle pour vérifier expiration | Moyen |
| **Helm Deploy** | Aucune (si secret identique `rhdemo-tls-cert`) | - |
| **Health Checks** | Aucune | - |

#### Script Jenkinsfile-CD additionnel (optionnel)
```groovy
stage('🔒 Vérifier Certificats Let\'s Encrypt') {
    steps {
        script {
            sh '''
                # Vérifier expiration certificats
                CERT_EXPIRY=$(openssl x509 -in certs/tls.crt -noout -enddate | cut -d= -f2)
                echo "Certificat expire le: $CERT_EXPIRY"

                # Alerter si expiration < 30 jours
                EXPIRY_EPOCH=$(date -d "$CERT_EXPIRY" +%s)
                NOW_EPOCH=$(date +%s)
                DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

                if [ $DAYS_LEFT -lt 30 ]; then
                    echo "⚠️ ATTENTION: Certificat expire dans $DAYS_LEFT jours"
                fi
            '''
        }
    }
}
```

---

### 5. Observabilité (Grafana)

Le script `install-loki.sh` génère également des certificats auto-signés pour Grafana.

#### Impact
- **Si migration Let's Encrypt**: Générer également un certificat pour `grafana.stagingkub.leuwen.fr`
- **Solution**: Utiliser un certificat wildcard `*.stagingkub.leuwen.fr` (certbot avec DNS-01)

---

## 📋 Plan de migration recommandé

### ❌ Recommandation: NE PAS MIGRER vers Let's Encrypt pour stagingkub

**Raisons**:
1. **Complexité technique élevée** pour un gain limité en environnement de test
2. **Infrastructure locale** (KinD) non adaptée à Let's Encrypt
3. **Certificats auto-signés suffisants** pour le staging
4. **Coût en temps** non justifié

---

### ✅ Recommandation: Préparer la production avec Let's Encrypt

Si vous prévoyez de déployer en production sur une infrastructure publique (VPS, cloud), préparez la migration en suivant ces étapes:

#### Phase 1: Configuration DNS publique (Effort: 1h)

1. **Créer les sous-domaines** dans votre registrar DNS:
   ```
   rhdemo.prod.leuwen.fr   A   <IP_PUBLIQUE>
   keycloak.prod.leuwen.fr A   <IP_PUBLIQUE>
   ```

2. **Vérifier la résolution DNS**:
   ```bash
   dig rhdemo.prod.leuwen.fr
   dig keycloak.prod.leuwen.fr
   ```

#### Phase 2: Installation cert-manager (Effort: 2-3h)

1. **Installer cert-manager** dans le cluster de production:
   ```bash
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.3/cert-manager.yaml
   ```

2. **Créer ClusterIssuer Let's Encrypt**:
   ```yaml
   apiVersion: cert-manager.io/v1
   kind: ClusterIssuer
   metadata:
     name: letsencrypt-prod
   spec:
     acme:
       server: https://acme-v02.api.letsencrypt.org/directory
       email: admin@leuwen.fr
       privateKeySecretRef:
         name: letsencrypt-prod
       solvers:
       - http01:
           ingress:
             class: nginx
   ```

3. **Créer Certificate**:
   ```yaml
   apiVersion: cert-manager.io/v1
   kind: Certificate
   metadata:
     name: rhdemo-tls-cert
     namespace: rhdemo-prod
   spec:
     secretName: rhdemo-tls-cert
     issuerRef:
       name: letsencrypt-prod
       kind: ClusterIssuer
     dnsNames:
     - rhdemo.prod.leuwen.fr
     - keycloak.prod.leuwen.fr
   ```

#### Phase 3: Mise à jour Helm Chart (Effort: 1h)

1. **Modifier `values.yaml`**:
   ```yaml
   global:
     domain: prod.leuwen.fr

   ingress:
     annotations:
       cert-manager.io/cluster-issuer: letsencrypt-prod
     tls:
       enabled: true
       secretName: rhdemo-tls-cert
   ```

2. **Déployer**:
   ```bash
   helm upgrade --install rhdemo helm/rhdemo \
     --namespace rhdemo-prod \
     --values values-prod.yaml
   ```

#### Phase 4: Validation (Effort: 30min)

1. **Vérifier émission certificat**:
   ```bash
   kubectl describe certificate rhdemo-tls-cert -n rhdemo-prod
   kubectl get secret rhdemo-tls-cert -n rhdemo-prod
   ```

2. **Tester HTTPS**:
   ```bash
   curl -I https://rhdemo.prod.leuwen.fr
   ```

---

## ⚠️ Risques et mitigations

### Risques identifiés

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **Validation Let's Encrypt échoue** (cluster local) | Élevée | Bloquant | ❌ Ne pas migrer stagingkub |
| **Limite rate-limit Let's Encrypt** (5 certificats/semaine) | Moyenne | Moyen | Utiliser staging Let's Encrypt pour tests |
| **Expiration certificat non détectée** (90 jours) | Faible | Élevé | Monitoring expiration + alertes |
| **API DNS credentials exposées** | Faible | Critique | Stocker dans SOPS + Jenkins credentials |
| **Downtime pendant migration** | Faible | Moyen | Migration en dehors des heures de test |
| **Incompatibilité cert-manager/KinD** | Faible | Moyen | Tester dans cluster de dev d'abord |

---

## 📊 Estimation des efforts

### Option 1: DNS-01 manuel (Certbot)

| Tâche | Effort | Complexité |
|-------|--------|------------|
| Configuration API DNS | 1h | Moyenne |
| Installation certbot + plugin | 30min | Faible |
| Génération certificats manuels | 30min | Faible |
| Modification scripts (init-stagingkub.sh) | 1h | Faible |
| Tests et validation | 1h | Faible |
| Documentation | 1h | Faible |
| **TOTAL** | **5h** | **Moyenne** |

**Renouvellement**: 30min tous les 90 jours (manuel).

---

### Option 2: cert-manager (Automatisé)

| Tâche | Effort | Complexité |
|-------|--------|------------|
| Installation cert-manager | 1h | Moyenne |
| Configuration ClusterIssuer DNS-01 | 2h | Élevée |
| Création ressources Certificate | 1h | Moyenne |
| Modification Helm charts | 2h | Moyenne |
| Configuration API DNS | 1h | Moyenne |
| Tests et validation | 2h | Moyenne |
| Documentation | 2h | Faible |
| **TOTAL** | **11h** | **Élevée** |

**Renouvellement**: Automatique.

---

### Option 3: Tunnel reverse (ngrok/cloudflare)

| Tâche | Effort | Complexité |
|-------|--------|------------|
| Configuration tunnel (ngrok Pro) | 2h | Élevée |
| Configuration DNS | 1h | Moyenne |
| Installation certbot HTTP-01 | 1h | Faible |
| Modification scripts | 1h | Faible |
| Tests et validation | 2h | Moyenne |
| **TOTAL** | **7h** | **Élevée** |

**Coût récurrent**: $8-20/mois (ngrok Pro) + maintenance tunnel.

---

## 🎯 Recommandations

### Recommandation finale

#### Pour l'environnement stagingkub (KinD local)
✅ **GARDER LES CERTIFICATS AUTO-SIGNÉS**

**Justifications**:
1. ✅ **Adapté au staging**: Les certificats auto-signés sont standard pour les environnements de test
2. ✅ **Simplicité**: Aucune modification nécessaire
3. ✅ **Pas de dépendances**: Pas d'API DNS, pas de tunnel, pas d'infrastructure publique
4. ✅ **Économie de temps**: Évite 5-11h de développement pour un gain limité
5. ✅ **Sécurité**: Environnement local non exposé sur Internet

**Action**:
- Documenter que stagingkub utilise des certificats auto-signés (déjà fait dans README.md)
- Ajouter instructions pour accepter le certificat dans le navigateur (voir ci-dessous)

---

#### Pour l'environnement de production (futur)
✅ **UTILISER LET'S ENCRYPT avec cert-manager**

**Justifications**:
1. ✅ **Infrastructure publique**: VPS/cloud accessible depuis Internet
2. ✅ **Automatisation**: Renouvellement automatique tous les 90 jours
3. ✅ **Best practice**: cert-manager est le standard Kubernetes
4. ✅ **Fiabilité**: Certificats signés par une AC reconnue
5. ✅ **UX**: Pas d'avertissement SSL pour les utilisateurs finaux

**Actions**:
1. Prévoir l'intégration cert-manager dans le Helm chart (nouveau fichier `values-prod.yaml`)
2. Créer un `ClusterIssuer` Let's Encrypt avec HTTP-01 (si VPS public) ou DNS-01
3. Documenter le process de déploiement production dans un nouveau document `DEPLOY_PROD.md`

---

### Accepter les certificats auto-signés dans les navigateurs (Staging)

#### Chrome/Edge
1. Accéder à `https://rhdemo.stagingkub.intra.leuwen-lc.fr`
2. Cliquer sur "Avancé" → "Continuer vers le site (non sécurisé)"
3. Ajouter une exception permanente

#### Firefox
1. Accéder à `https://rhdemo.stagingkub.intra.leuwen-lc.fr`
2. Cliquer sur "Avancé" → "Accepter le risque et continuer"
3. Ajouter une exception permanente

#### Automatiser l'acceptation (pour tests Selenium)
Dans le code Selenium, configurer les options pour ignorer les erreurs SSL:

```java
FirefoxOptions options = new FirefoxOptions();
options.setAcceptInsecureCerts(true); // Accepte les certificats auto-signés
WebDriver driver = new FirefoxDriver(options);
```

---

### Cas d'usage acceptables pour Let's Encrypt sur stagingkub (non recommandés)

Si vous souhaitez **absolument** utiliser Let's Encrypt sur stagingkub, voici les cas où cela pourrait être justifié:

1. **Démonstration client**: Besoin de montrer l'application à un client externe sans avertissement SSL
   - **Solution**: Utiliser un certificat Let's Encrypt généré manuellement (DNS-01) pour une démo ponctuelle

2. **Tests de production**: Valider le comportement exact de la production (redirections HTTPS, headers SSL, etc.)
   - **Solution**: Créer un environnement "staging-public" sur un VPS dédié avec cert-manager

3. **Formation équipe**: Former l'équipe à cert-manager avant le déploiement prod
   - **Solution**: Utiliser cert-manager en staging avec Let's Encrypt Staging (rate-limits plus élevés)

---

## 📚 Annexes

### A. Commandes utiles

#### Vérifier expiration certificat actuel
```bash
openssl x509 -in infra/stagingkub/certs/tls.crt -noout -enddate
# Output: notAfter=Dec 18 17:23:45 2026 GMT
```

#### Tester résolution DNS
```bash
dig rhdemo.stagingkub.leuwen.fr
nslookup keycloak.stagingkub.leuwen.fr
```

#### Tester HTTP-01 challenge (si exposition publique)
```bash
curl -I http://rhdemo.stagingkub.leuwen.fr/.well-known/acme-challenge/test
```

---

### B. Ressources externes

- [Documentation Let's Encrypt](https://letsencrypt.org/docs/)
- [Certbot Documentation](https://eff-certbot.readthedocs.io/)
- [cert-manager Documentation](https://cert-manager.io/docs/)
- [Let's Encrypt Rate Limits](https://letsencrypt.org/docs/rate-limits/)
- [Nginx Ingress + cert-manager Tutorial](https://cert-manager.io/docs/tutorials/acme/nginx-ingress/)

---

### C. Glossaire

| Terme | Définition |
|-------|------------|
| **ACME** | Automatic Certificate Management Environment - Protocole utilisé par Let's Encrypt |
| **HTTP-01** | Challenge Let's Encrypt nécessitant une requête HTTP sur port 80 |
| **DNS-01** | Challenge Let's Encrypt nécessitant un enregistrement TXT DNS |
| **cert-manager** | Contrôleur Kubernetes pour automatiser la gestion des certificats |
| **ClusterIssuer** | Ressource cert-manager définissant une source de certificats (Let's Encrypt, etc.) |
| **Certificate** | Ressource cert-manager demandant l'émission d'un certificat |
| **KinD** | Kubernetes in Docker - Cluster Kubernetes local pour développement |
| **Ingress** | Ressource Kubernetes exposant des services HTTP/HTTPS |

---

## ✅ Conclusion

### Décision recommandée

**Pour stagingkub (environnement local KinD)**:
- ✅ **GARDER** les certificats auto-signés
- ✅ Documenter comment accepter les certificats dans les navigateurs
- ✅ Réserver Let's Encrypt pour la production

**Pour production (futur déploiement public)**:
- ✅ **UTILISER** Let's Encrypt avec cert-manager
- ✅ Planifier l'intégration cert-manager dans le Helm chart
- ✅ Créer un environnement "staging-public" si besoin de tests

---

**Prochaines étapes recommandées**:

1. ✅ Valider cette décision avec l'équipe
2. ✅ Documenter l'architecture certificats dans `infra/stagingkub/README.md`
3. ✅ Créer un document `DEPLOY_PROD.md` anticipant l'utilisation de cert-manager
4. ✅ Ajouter un chapitre "Accepter les certificats auto-signés" dans la documentation utilisateur

---

**Questions à se poser avant de migrer**:

1. ❓ Est-ce que stagingkub sera accessible publiquement sur Internet ?
   - **Non** → Garder les certificats auto-signés
   - **Oui** → Envisager Let's Encrypt avec cert-manager

2. ❓ Avez-vous une infrastructure permanente (VPS/cloud) ?
   - **Non** → Garder les certificats auto-signés
   - **Oui** → Let's Encrypt est adapté

3. ❓ Avez-vous besoin de montrer l'application à des clients externes ?
   - **Non** → Garder les certificats auto-signés
   - **Oui** → Envisager un certificat Let's Encrypt ponctuel

4. ❓ Le gain en UX justifie-t-il 5-11h de développement ?
   - **Non** → Garder les certificats auto-signés
   - **Oui** → Procéder avec Let's Encrypt DNS-01

---

**Date de révision**: 2026-01-09
**Auteur**: Claude Code
**Statut**: ✅ Validé pour revue
