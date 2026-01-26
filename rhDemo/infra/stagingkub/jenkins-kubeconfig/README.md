# Kubeconfig Jenkins RBAC

Ce dossier contient le kubeconfig RBAC généré pour Jenkins.

## Fichier généré

Après exécution de `init-stagingkub.sh`, le fichier suivant est créé :

- `kubeconfig-jenkins-rbac.yaml` - Kubeconfig avec token du ServiceAccount `jenkins-deployer`

## Sécurité

**IMPORTANT** : Ce fichier contient un token d'authentification et ne doit PAS être commité dans Git.

Le fichier `.gitignore` de ce dossier exclut automatiquement les fichiers `.yaml`.

## Utilisation

1. Uploadez ce fichier comme credential Jenkins de type "Secret file"
2. ID du credential : `kubeconfig-stagingkub`
3. Le `Jenkinsfile-CD` utilisera automatiquement ce credential

## Régénération

Pour régénérer le kubeconfig :

```bash
cd rhDemo/infra/stagingkub/scripts
./init-stagingkub.sh
```

Ou :

```bash
cd rhDemo/infra/stagingkub/rbac
./setup-jenkins-rbac.sh --generate-kubeconfig
```
