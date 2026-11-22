# Secrets par environnement

## 📋 Vue d'ensemble

Chaque environnement a ses propres secrets, sans valeur partagée : la compromission de l'un n'affecte pas les autres. Aucun secret n'est versionné dans Git. Les fichiers de ce répertoire sont des modèles ou des fichiers locaux ignorés par Git, plus l'inventaire.

| Environnement | Où vivent les secrets | Création | Renouvellement |
|---------------|------------------------|----------|----------------|
| **ephemere** (Docker Compose, CI) | Nulle part : tirés au hasard à chaque build | Stage « Génération Secrets ephemere » de `Jenkinsfile-CI` | Rien à faire, l'environnement est détruit en fin de build |
| **stagingkub** (Kubernetes, CD) | OpenBao (`kv/stagingkub/*`), recopiés dans le cluster par External Secrets Operator | `scripts/openbao-setup.py stagingkub` (valeurs générées) | `scripts/rotate-secrets.py` |
| **dev** (poste) | `secrets-rhdemo.yml`, local, ignoré par Git | Copie de `secrets-rhdemo.yml.template` | À la main |

Pipelines et outils (Jenkins, Renovate, fixcve-auto) : secrets dans OpenBao également (`kv/jenkins/*`, `kv/fixcve/*`).

## 📁 Fichiers de ce répertoire

| Fichier | Rôle |
|---------|------|
| `inventory.yaml` | Inventaire de tous les secrets du projet (aucune valeur) : où ils vivent, comment les renouveler. Lu par `rotate-secrets.py` |
| `secrets-rhdemo.yml.template` | Modèle du fichier de secrets de l'environnement dev |
| `secrets-rhdemo.yml` | Secrets dev, local, jamais commité |

## 📝 Bonnes pratiques

1. **Ne jamais** commiter un secret en clair, ni le passer en argument de commande (visible dans `ps`) : entrée standard ou variable d'environnement.
2. Renouveler par `rotate-secrets.py` (`--check` signale les secrets à renouveler) : [ROTATION_SECRETS.md](../docs/ROTATION_SECRETS.md).
3. Garder `inventory.yaml` à jour à chaque ajout de secret.

## 🔗 Références

- [OpenBao : installation, déverrouillage, rotation](../docs/OPENBAO.md)
- [Secrets au quotidien : tâches récurrentes, rotation d'urgence, accès](../docs/ROTATION_SECRETS.md)
- [Pipeline CI (Jenkinsfile-CI)](../Jenkinsfile-CI)
- [Pipeline CD (Jenkinsfile-CD)](../Jenkinsfile-CD)
- [Environnements](../infra/ENVIRONMENTS.md)
