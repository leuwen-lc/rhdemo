---
statut: actif
verifie_le: 2026-10-22
sources:
  - rhDemo/pgschema.sql
  - rhDemo/pgdata.sql
  - rhDemo/src/main/resources/data.sql
---

# 🗄️ Base de données RHDemo

Ce document explique l'organisation des fichiers SQL pour la base de données PostgreSQL de RHDemo.

## 📁 Fichiers SQL

Le projet utilise deux fichiers SQL distincts pour séparer la **structure** de la base de données et les **données de test** :

### 1. `pgschema.sql` - Schéma de la base (DDL)

**Contenu** : Data Definition Language (DDL)
- Définition de la table `employes`
- Création des 5 index pour optimiser les performances

**Usage** :
- ✅ **Environnement de ephemere (Docker Compose)** : Oui
- ✅ **Environnement de développement** : Oui
- ✅ **Environnement de stagingkub (Kubernetes)** : Oui (automatique si pas de table existante)


**Exécution** :
```bash
# Développement
docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < pgschema.sql

# Staging (Docker Compose)
docker exec -i rhdemo-ephemere-db psql -U rhdemo -d rhdemo < pgschema.sql

# Stagingkub (Kubernetes) - Automatique via ConfigMap, ou manuel si besoin :
kubectl exec -it postgresql-rhdemo-0 -n rhdemo-stagingkub -- psql -U rhdemo -d rhdemo < pgschema.sql

# Production (à adapter selon votre infrastructure)
psql -h your-db-host -U your-user -d your-database < pgschema.sql
```

**Note Kubernetes stagingkub** : Le schéma est automatiquement créé au premier démarrage du pod PostgreSQL via un ConfigMap init script. Il utilise une vérification conditionnelle pour **préserver les données existantes** lors des redéploiements.

### 2. `pgdata.sql` - Données de test (DML)

**Contenu** : Data Manipulation Language (DML)
- 304 employés fictifs pour les tests

**Usage** :
- ✅ **Environnement de ephemere (Docker Compose)** : Oui
- ✅ **Environnement de développement** : Oui
- ⚠️ **Environnement de stagingkub (Kubernetes)** : Non a priori car on simule un fonctionnement prod ou la base persiste d'installation en installation

**Exécution** :
```bash
# Développement
docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < pgdata.sql

# Staging (Docker Compose)
docker exec -i rhdemo-ephemere-db psql -U rhdemo -d rhdemo < pgdata.sql

# Stagingkub (Kubernetes) - Manuel uniquement si nécessaire
kubectl exec -it postgresql-rhdemo-0 -n rhdemo-stagingkub -- psql -U rhdemo -d rhdemo < pgdata.sql
```


## 📊 Structure de la table `employes`

```sql
CREATE TABLE employes (
  id BIGSERIAL PRIMARY KEY,
  prenom VARCHAR(250) NOT NULL,
  nom VARCHAR(250) NOT NULL,
  mail VARCHAR(250) NOT NULL,
  adresse VARCHAR(500)
);
```

### Index créés

| Index | Colonne(s) | Type | Utilité |
|-------|-----------|------|---------|
| `idx_employes_mail` | `mail` | UNIQUE | Recherche par email + contrainte d'unicité |
| `idx_employes_nom` | `nom` | BTREE | Recherche/tri alphabétique par nom |
| `idx_employes_prenom` | `prenom` | BTREE | Recherche par prénom |
| `idx_employes_nom_prenom` | `nom, prenom` | BTREE | Recherche combinée nom + prénom |
| `idx_employes_adresse` | `adresse` (WHERE NOT NULL) | PARTIAL | Recherche géographique |

## 🚀 Initialisation par environnement

### Développement local

```bash
cd rhDemo/infra/dev
./start.sh

# Initialiser la base
docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < ../../pgschema.sql
docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < ../../pgdata.sql
```

### Staging (Docker Compose)

```bash
# Option 1 : Script automatique
Via Jenkins (Jenkinsfile-CI)

# Option 2 : Manuel
docker exec -i rhdemo-ephemere-db psql -U rhdemo -d rhdemo < ../../pgschema.sql
docker exec -i rhdemo-ephemere-db psql -U rhdemo -d rhdemo < ../../pgdata.sql
```

### Stagingkub (Kubernetes)

**Automatique** : Le schéma est créé automatiquement au premier démarrage du pod PostgreSQL.

**Détails** :
- Le ConfigMap `postgresql-rhdemo-init` contient le script `init-db.sql`
- Ce script est monté dans `/docker-entrypoint-initdb.d/`
- PostgreSQL l'exécute automatiquement au premier démarrage
- Vérification conditionnelle : si la table existe déjà, le script ne fait rien

**Ajout de données de test** (si nécessaire) :
```bash
# Copier pgdata.sql dans le pod
kubectl cp pgdata.sql postgresql-rhdemo-0:/tmp/data.sql -n rhdemo-stagingkub

# Exécuter
kubectl exec postgresql-rhdemo-0 -n rhdemo-stagingkub -- psql -U rhdemo -d rhdemo -f /tmp/data.sql
```


## 🔧 Modifications du schéma

Si vous modifiez la structure de la base :

1. **Modifier `pgschema.sql`** avec les changements DDL
2. **Mettre à jour le ConfigMap Kubernetes** : `infra/stagingkub/helm/rhdemo/templates/postgresql-rhdemo-configmap.yaml`
3. **Tester localement** :
   ```bash
   docker exec -i rhdemo-dev-db psql -U dbrhdemo -d dbrhdemo < pgschema.sql
   ```
4. **Redéployer en stagingkub (Kubernetes)** : Le nouveau schéma sera appliqué au prochain pod créé avec un volume vierge

## TODO
Ajouter une gestion incrémentale et versionnée du schéma avec Liquibase

## ❓ FAQ

**Q: Pourquoi deux fichiers au lieu d'un seul ?**
R: Séparation des responsabilités. Le schéma peut être appliqué en production, pas les données de test.

**Q: Que se passe-t-il si je redéploie le pod PostgreSQL en Kubernetes ?**
R: Si le PersistentVolume existe, les données sont préservées. Le script d'init détecte que la table existe et ne fait rien.

**Q: Comment vider complètement la base en Kubernetes ?**
R: Supprimer le PersistentVolumeClaim :
```bash
kubectl delete pvc postgresql-data-postgresql-rhdemo-0 -n rhdemo-stagingkub
```
Au prochain démarrage, le schéma sera recréé automatiquement.

**Q: Puis-je modifier `pgdata.sql` pour ajouter mes propres données de test ?**
R: Oui ! C'est justement fait pour ça. Modifiez le fichier et réexécutez-le.

**Q: Les index sont-ils automatiquement créés ?**
R: Oui, ils font partie de `pgschema.sql` et sont créés en même temps que la table.

---

**Dernière mise à jour** : 2025-12-12
