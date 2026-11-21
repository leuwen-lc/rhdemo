# Initialisation Keycloak pour stagingkub

## Description

Le script `init-keycloak-stagingkub.sh` permet d'initialiser automatiquement Keycloak dans l'environnement Kubernetes **stagingkub**.

Ce script :
- Lit les secrets de stagingkub dans OpenBao (`kv/stagingkub/*`, `kv/stagingkub-tests/users`)
- Configure le realm `RHDemo`
- Crée le client OAuth2 `RHDemo`
- Crée les utilisateurs de test avec leurs rôles

## Utilisation

### Prérequis

1. **Cluster Kubernetes stagingkub démarré**
   ```bash
   kubectl config use-context kind-rhdemo
   kubectl get pods -n rhdemo-stagingkub
   ```

2. **Keycloak déployé et accessible**
   ```bash
   kubectl get pod -l app=keycloak -n rhdemo-stagingkub
   # Le pod doit être Ready
   ```

3. **OpenBao déverrouillé** et alimenté (`rhDemo/scripts/openbao-setup.py stagingkub`) ; le mot de passe de l'utilisateur `admin` d'OpenBao est demandé ([OPENBAO.md](../../../docs/OPENBAO.md))

4. **Maven ou Maven Wrapper** disponible dans rhDemoInitKeycloak

### Exécution

```bash
cd /path/to/rhDemo/infra/stagingkub/scripts
./init-keycloak-stagingkub.sh
```

Le script va :
1. ✓ Vérifier tous les prérequis
2. ✓ Lire dans OpenBao les credentials et utilisateurs de test (session admin révoquée en fin de script)
4. ✓ Créer un port-forward vers le pod Keycloak
5. ✓ Builder rhDemoInitKeycloak
6. ✓ Exécuter l'initialisation avec la configuration générée
7. ✓ Nettoyer automatiquement (arrêt du port-forward, effacement de la configuration temporaire)

## Configuration

Le script lit dans OpenBao :

### Secrets Keycloak Admin
- `kv/stagingkub/keycloak` : `admin_user`, `admin_password`

### Secrets Client OAuth2
- `kv/stagingkub/rhdemo` : `oidc_client_secret` (le client `RHDemo` est supprimé puis recréé avec ce secret)

### Utilisateurs de test
Les utilisateurs sont créés à partir de `kv/stagingkub-tests/users` (un utilisateur existant n'est pas modifié ; ses mots de passe se renouvellent par `rotate-secrets.py stagingkub-test-users`) :

| Clé | Rôle(s) | Description |
|------------|---------|-------------|
| `iduseradmin` / `pwduseradmin` | ROLE_admin | Administrateur complet |
| `iduserconsult` / `pwduserconsult` | ROLE_consult | Consultation seule |
| `idusermaj` / `pwdusermaj` | ROLE_consult + ROLE_MAJ | Consultation + Mise à jour |

### URLs configurées

Le client OAuth2 est configuré pour l'environnement stagingkub :
- Root URL: `https://rhdemo-stagingkub.intra.leuwen-lc.fr/`
- Redirect URIs: `https://rhdemo-stagingkub.intra.leuwen-lc.fr/*`
- Web Origins: `https://rhdemo-stagingkub.intra.leuwen-lc.fr`

## Résultat

Après exécution réussie, vous pouvez :

1. **Accéder à Keycloak** : https://keycloak-stagingkub.intra.leuwen-lc.fr
   - Admin console avec les credentials de `kv/stagingkub/keycloak` (`bao kv get -mount=kv stagingkub/keycloak`)

2. **Se connecter à l'application** : https://rhdemo-stagingkub.intra.leuwen-lc.fr
   - Avec l'un des utilisateurs de test créés

3. **Vérifier la configuration** :
   - Realm `RHDemo` créé
   - Client `RHDemo` configuré avec le bon secret
   - Utilisateurs avec leurs rôles assignés

## Quand utiliser ce script ?

- ✅ **Premier déploiement** de l'environnement stagingkub
- ✅ **Après un reset complet** de Keycloak
- ✅ **Pour recréer** la configuration Keycloak depuis zéro

⚠️ **Note** : Ce script n'est PAS intégré au pipeline CD car il n'est nécessaire qu'au premier déploiement ou après un reset.

## Dépannage

### Port-forward échoue

Si le port 6090 est déjà utilisé :
```bash
# Vérifier les processus utilisant le port
lsof -i :6090

# Tuer le processus si nécessaire
pkill -f "kubectl.*port-forward.*6090"
```

### Secrets illisibles

OpenBao scellé (`rhDemo/infra/jenkins-docker/openbao/unseal.sh`), mot de passe `admin` refusé, ou valeurs absentes (`rhDemo/scripts/openbao-setup.py stagingkub`).

### Keycloak non ready

Attendez que Keycloak soit prêt :
```bash
kubectl wait --for=condition=ready pod -l app=keycloak -n rhdemo-stagingkub --timeout=5m
```

### Erreur "Realm already exists"

Si le realm existe déjà, vous pouvez :
1. Supprimer le realm manuellement via l'admin console
2. Ou modifier `rhDemoInitKeycloak` pour ignorer l'erreur si le realm existe

## Voir aussi

- [init-stagingkub.sh](./init-stagingkub.sh) : Script d'initialisation complète de l'environnement
- [../../../secrets/README-SECRETS-SEPARATION.md](../../../secrets/README-SECRETS-SEPARATION.md) : Documentation sur la séparation des secrets
- [../../Jenkinsfile-CD](../../Jenkinsfile-CD) : Pipeline de déploiement continu
