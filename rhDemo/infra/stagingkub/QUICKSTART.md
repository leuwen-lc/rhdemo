# ⚡ Quick Start - stagingkub

Guide de démarrage rapide pour déployer RHDemo sur Kubernetes (KinD).

---

## 🚀 Déploiement en 3 étapes

### 1️⃣ Initialisation (une seule fois)

```bash
cd rhDemo/infra/stagingkub
./scripts/init-stagingkub.sh
```

Cette commande :
- ✅ Crée le cluster KinD "rhdemo"
- ✅ Installe Nginx Ingress Controller
- ✅ Crée les secrets Kubernetes
- ✅ Génère les certificats SSL
- ✅ Configure /etc/hosts

**Durée** : ~2-3 minutes

---

### 2️⃣ Construction de l'image Docker

```bash
cd rhDemo
./mvnw clean spring-boot:build-image \
  -Dspring-boot.build-image.imageName=rhdemo-api:1.1.0-SNAPSHOT
```

**Durée** : ~3-5 minutes

---

### 3️⃣ Déploiement

```bash
cd infra/stagingkub
./scripts/deploy.sh 1.1.0-SNAPSHOT
```

Cette commande :
- ✅ Charge l'image dans KinD
- ✅ Déploie avec Helm
- ✅ Attend que tous les services soient prêts

**Durée** : ~2-4 minutes

---

## ✅ Vérification

### Accès à l'application

Ouvrez votre navigateur :
- **Application** : https://rhdemo.staging.local
- **Keycloak** : https://keycloak.staging.local

⚠️ Vous verrez un avertissement de certificat (self-signed) → Acceptez et continuez

### Vérifier le statut

```bash
# Statut des pods
kubectl get pods -n rhdemo-staging

# Logs de l'application
kubectl logs -f -n rhdemo-staging -l app=rhdemo-app

# Tous les services
kubectl get all -n rhdemo-staging
```

---

## 🔄 Mise à jour de l'application

### Après modification du code

```bash
# 1. Rebuild l'image
./mvnw clean spring-boot:build-image \
  -Dspring-boot.build-image.imageName=rhdemo-api:1.2.0-SNAPSHOT

# 2. Redéployer
cd infra/stagingkub
./scripts/deploy.sh 1.2.0-SNAPSHOT
```

### Mise à jour rapide (sans rebuild complet)

```bash
# Charger nouvelle image dans KinD
kind load docker-image rhdemo-api:1.2.0-SNAPSHOT --name rhdemo

# Mettre à jour via Helm
helm upgrade rhdemo ./helm/rhdemo \
  --namespace rhdemo-staging \
  --set rhdemo.image.tag=1.2.0-SNAPSHOT \
  --wait
```

---

## 🐛 Troubleshooting rapide

### Problème : Pod en CrashLoopBackOff

```bash
# Voir les logs du pod qui crash
kubectl logs -n rhdemo-staging <pod-name> --previous

# Voir les events
kubectl get events -n rhdemo-staging --sort-by='.lastTimestamp'
```

### Problème : Ingress ne répond pas

```bash
# Vérifier Nginx Ingress
kubectl get pods -n ingress-nginx

# Vérifier l'ingress
kubectl describe ingress rhdemo-ingress -n rhdemo-staging

# Test direct avec curl
curl -k https://rhdemo.staging.local
```

### Problème : /etc/hosts non configuré

```bash
echo "127.0.0.1 rhdemo.staging.local" | sudo tee -a /etc/hosts
echo "127.0.0.1 keycloak.staging.local" | sudo tee -a /etc/hosts
```

---

## 🗑️ Nettoyage

### Supprimer le déploiement (conserver le cluster)

```bash
helm uninstall rhdemo -n rhdemo-staging
```

### Supprimer tout le namespace

```bash
kubectl delete namespace rhdemo-staging
```

### Supprimer le cluster complet

```bash
kind delete cluster --name rhdemo
```

---

## 📚 Pour aller plus loin

- [README complet](./README.md) - Documentation détaillée
- [Guide des environnements](../ENVIRONMENTS.md) - Comparaison staging vs stagingkub
- [Documentation Helm](./helm/rhdemo/) - Customisation du Chart

---

## 🆘 Besoin d'aide ?

### Validation de l'environnement

```bash
./scripts/validate.sh
```

Ce script vérifie :
- ✅ Outils requis installés
- ✅ Cluster KinD créé
- ✅ Nginx Ingress déployé
- ✅ Secrets configurés
- ✅ /etc/hosts configuré

### Commandes utiles

```bash
# Voir tous les pods
kubectl get pods -n rhdemo-staging

# Voir les services
kubectl get svc -n rhdemo-staging

# Voir l'ingress
kubectl get ingress -n rhdemo-staging

# Port-forward direct (alternative à Ingress)
kubectl port-forward -n rhdemo-staging svc/rhdemo-app 9000:9000
```

---

**Bon déploiement ! 🚀**
