# Scripts d'initialisation - Environnement Staging

Ce répertoire contient les scripts d'initialisation pour l'environnement staging de RHDemo.

## 📋 Scripts disponibles

### 1. `init-keycloak.sh` - Initialisation Keycloak

Configure automatiquement Keycloak avec le realm, client, rôles et utilisateurs pour RHDemo.

**Utilisation:**
```bash
./init-keycloak.sh
```

**Ce script crée:**
- ✅ Realm `RHDemo`
- ✅ Client OAuth2 `RHDemo` avec secret
- ✅ Rôles: `admin`, `consult`, `MAJ`
- ✅ 3 utilisateurs de test:
  - `admin` / `admin123` (tous les droits)
  - `consultant` / `consult123` (lecture seule)
  - `manager` / `manager123` (lecture + modification)

**Prérequis:**
- Services Docker démarrés (`docker compose up -d`)
- Keycloak accessible
- Projet `rhDemoInitKeycloak` buildé

---

### 2. `init-database.sh` - Initialisation base de données

Initialise (ou réinitialise) la base de données PostgreSQL de l'application RHDemo avec le schéma et les données de test.

**Utilisation:**
```bash
./init-database.sh
```

**Ce script:**
- ⚠️  **SUPPRIME** toutes les données existantes (demande confirmation)
- ✅ Crée la table `employes` avec index optimisés
- ✅ Insère 300+ employés de test
- ✅ Vérifie l'intégrité des données

**Index créés:**
- `idx_employes_mail` (UNIQUE) - Recherches rapides par email
- `idx_employes_nom` - Tri alphabétique par nom
- `idx_employes_prenom` - Recherches par prénom
- `idx_employes_nom_prenom` - Recherches combinées
- `idx_employes_adresse` (partiel) - Recherches géographiques

**Prérequis:**
- Container PostgreSQL en cours d'exécution
- Fichier `../../pgddl.sql` présent

---

## 🚀 Initialisation complète d'un environnement

Pour initialiser un environnement staging depuis zéro:

```bash
# 1. Démarrer les services
sudo docker compose up -d

# 2. Attendre que les services soient prêts (30-60 secondes)
sudo docker compose ps

# 3. Initialiser Keycloak
./init-keycloak.sh

# 4. Initialiser la base de données
./init-database.sh

# 5. Redémarrer l'application (optionnel)
sudo docker compose restart rhdemo-app

# 6. Vérifier les logs
sudo docker compose logs -f rhdemo-app
```

---

## 🔧 Commandes utiles

### Vérifier l'état des services
```bash
sudo docker compose ps
sudo docker compose logs --tail=50 rhdemo-app
```

### Accéder aux bases de données

**PostgreSQL RHDemo:**
```bash
sudo docker exec -it rhdemo-staging-db psql -U rhdemo -d rhdemo
```

**PostgreSQL Keycloak:**
```bash
sudo docker exec -it keycloak-staging-db psql -U keycloak -d keycloak
```

### Réinitialiser complètement l'environnement
```bash
# ATTENTION: Supprime toutes les données !
sudo docker compose down -v
sudo docker compose up -d
./init-keycloak.sh
./init-database.sh
```

---

## 📊 Données de test

### Utilisateurs Keycloak

| Utilisateur  | Mot de passe | Rôles              | Accès                          |
|--------------|--------------|--------------------|---------------------------------|
| admin        | admin123     | admin, consult, MAJ| Lecture + écriture + suppression|
| consultant   | consult123   | consult            | Lecture seule                   |
| manager      | manager123   | consult, MAJ       | Lecture + écriture              |

### Employés dans la base

300+ employés de test avec données réalistes:
- Prénom, nom, email (unique)
- Adresse complète (ville française)
- Données insérées depuis `pgddl.sql`

---

## ⚠️  Notes importantes

1. **init-keycloak.sh** peut être exécuté plusieurs fois:
   - Supprime et recrée le client si existant
   - Conserve les utilisateurs existants
   - Met à jour les rôles

2. **init-database.sh** demande confirmation avant suppression:
   - Utilise `pgddl.sql` comme source
   - Toutes les données existantes sont perdues
   - Les index sont recréés automatiquement

3. **Certificats SSL**: Auto-signés pour staging
   - Acceptés par `rhDemoInitKeycloak` (trust all certificates)
   - Nécessitent `-k` avec `curl`

---

## 🐛 Dépannage

### Keycloak non accessible
```bash
curl -k https://keycloak.staging.local
# Vérifier: sudo docker compose logs keycloak
```

### Base de données non accessible
```bash
sudo docker exec rhdemo-staging-db pg_isready -U rhdemo
# Vérifier: sudo docker compose logs rhdemo-db
```

### Application ne démarre pas
```bash
sudo docker compose logs --tail=100 rhdemo-app | grep Error
# Redémarrer: sudo docker compose restart rhdemo-app
```

### Erreur SSL lors de l'init Keycloak
Le script utilise désormais HTTPS via nginx avec certificats auto-signés.
La validation SSL est désactivée dans `rhDemoInitKeycloak`.

---

## 📚 Documentation complémentaire

- OAuth2/Keycloak: Voir `/home/leno-vo/git/repository/rhDemo/CSRF_GUIDE.md`
- Architecture: Voir `/home/leno-vo/git/repository/rhDemo/.github/copilot-instructions.md`
- Tests Selenium: Voir `/home/leno-vo/git/repository/rhDemoAPITestIHM/`
