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
- ✅ Crée un registry Docker local (localhost:5000)
- ✅ Crée le cluster KinD "rhdemo"
- ✅ Connecte le registry au cluster KinD
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
- ✅ Tag l'image pour le registry local
- ✅ Push l'image vers le registry
- ✅ Déploie avec Helm
- ✅ Attend que tous les services soient prêts

**Durée** : ~2-4 minutes

---

## ✅ Vérification

### Accès à l'application

Ouvrez votre navigateur :
- **Application** : https://rhdemo.stagingkub.local
- **Keycloak** : https://keycloak.stagingkub.local

⚠️ Vous verrez un avertissement de certificat (self-signed) → Acceptez et continuez

### Vérifier le statut

```bash
# Statut des pods
kubectl get pods -n rhdemo-stagingkub

# Logs de l'application
kubectl logs -f -n rhdemo-stagingkub -l app=rhdemo-app

# Tous les services
kubectl get all -n rhdemo-stagingkub
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
# Tag et push vers le registry local
docker tag rhdemo-api:1.2.0-SNAPSHOT localhost:5000/rhdemo-api:1.2.0-SNAPSHOT
docker push localhost:5000/rhdemo-api:1.2.0-SNAPSHOT

# Mettre à jour via Helm
helm upgrade rhdemo ./helm/rhdemo \
  --namespace rhdemo-stagingkub \
  --set rhdemo.image.repository=localhost:5000/rhdemo-api \
  --set rhdemo.image.tag=1.2.0-SNAPSHOT \
  --wait
```

### 📦 Vérifier les images dans le registry

```bash
# Lister toutes les images
curl http://localhost:5000/v2/_catalog

# Voir les tags d'une image
curl http://localhost:5000/v2/rhdemo-api/tags/list
```

---

## 🐛 Troubleshooting rapide

### Problème : Pod en CrashLoopBackOff

```bash
# Voir les logs du pod qui crash
kubectl logs -n rhdemo-stagingkub <pod-name> --previous

# Voir les events
kubectl get events -n rhdemo-stagingkub --sort-by='.lastTimestamp'
```

### Problème : Ingress ne répond pas

```bash
# Vérifier Nginx Ingress
kubectl get pods -n ingress-nginx

# Vérifier l'ingress
kubectl describe ingress rhdemo-ingress -n rhdemo-stagingkub

# Test direct avec curl
curl -k https://rhdemo.stagingkub.local
```

### Problème : /etc/hosts non configuré

```bash
echo "127.0.0.1 rhdemo.stagingkub.local" | sudo tee -a /etc/hosts
echo "127.0.0.1 keycloak.stagingkub.local" | sudo tee -a /etc/hosts
```

---

## 🗑️ Nettoyage

### Supprimer le déploiement (conserver le cluster)

```bash
helm uninstall rhdemo -n rhdemo-stagingkub
```

### Supprimer tout le namespace

```bash
kubectl delete namespace rhdemo-stagingkub
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
kubectl get pods -n rhdemo-stagingkub

# Voir les services
kubectl get svc -n rhdemo-stagingkub

# Voir l'ingress
kubectl get ingress -n rhdemo-stagingkub

# Port-forward direct (alternative à Ingress)
kubectl port-forward -n rhdemo-stagingkub svc/rhdemo-app 9000:9000
```

---

**Bon déploiement ! 🚀**
