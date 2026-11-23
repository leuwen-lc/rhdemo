---
statut: proposition
verifie_le: 2026-11-23
sources:
  - rhDemo/infra/jenkins-docker/casc/jenkins-casc.yaml
  - rhDemo/infra/jenkins-docker/QUICKSTART.md
  - rhDemo/Jenkinsfile-CI
  - rhDemo/Jenkinsfile-CD
  - rhDemo/Jenkinsfile-Renovate
  - rhDemo/secrets/
  - rhDemo/Jenkinsfile-FixCVE
  - rhDemo/infra/stagingkub/rbac/
  - rhDemo/infra/stagingkub/scripts/init-stagingkub.sh
  - rhDemo/secrets/inventory.yaml
  - rhDemo/scripts/rotate-secrets.py
  - rhDemo/scripts/rotation_lib/
  - rhDemo/scripts/openbao-setup.py
  - rhDemo/infra/jenkins-docker/openbao/
---

# Étude : renouvellement rapide des secrets de RHDemo

**Objectif** : pouvoir renouveler vite, et par API plutôt que par IHM, tous les secrets dont la fuite permet une écriture, une facturation ou une malveillance significative. Deux usages : la **rotation périodique** (hygiène) et la **rotation d'urgence** après une fuite supposée (poste compromis, log exposé, dépendance malveillante en CI).

**Hors périmètre** (demande explicite) : les jetons qui n'ouvrent qu'un quota de lecture. Ils sont listés en fin d'inventaire pour mémoire.

**Statut** : proposition. Phases 0 et 1 réalisées le 2026-11-17 (§3.4), phase 2 en grande partie par OpenBao (2026-11-21). État au 2026-11-23 et reste à faire : §5. L'adoption d'OpenBao ([ETUDE_OPENBAO.md](ETUDE_OPENBAO.md), [OPENBAO.md](OPENBAO.md)) a changé plusieurs options : les secrets sont stockés et propagés par OpenBao au lieu de SOPS et des credentials Jenkins, la clé Cosign est une clé Transit, les secrets de stagingkub sont renouvelés par le script, SOPS et sa clé AGE sont abandonnés (2026-11-21). Usage courant du script et tâches récurrentes : [ROTATION_SECRETS.md](ROTATION_SECRETS.md).

---

## 1. Inventaire

Recensement initial (2026-11-16) fait à partir des `credentialsId` des `Jenkinsfile-*`, de la section CREDENTIALS de `jenkins-casc.yaml`, des fichiers SOPS de l'époque, de `fixcve-install.sh` et des scripts stagingkub. La colonne « Où il est stocké » est à jour après la migration vers OpenBao ; l'inventaire de référence est `rhDemo/secrets/inventory.yaml`.

Criticité : **C** critique (prise de contrôle de la chaîne de livraison ou de tous les secrets), **H** élevée (écriture sur le dépôt, le cluster ou une identité), **M** moyenne (impact limité à un environnement de test ou à un outil).

Exposition : d'où un secret volé est **exploitable**, indépendamment de l'endroit où il est stocké.

- **Internet** : utilisable depuis n'importe où (service en ligne, ou historique public du dépôt). Priorité de rotation la plus haute : le vol le plus probable passe par la CI, qui exécute du code tiers (dépendances, PR Renovate) avec un accès Internet.
- **LAN** : utilisable depuis le réseau local, via stagingkub publié sur les ports 80 et 443 de l'hôte.
- **Local** : utilisable seulement depuis le poste (ports Jenkins, SonarQube et registry publiés sur `127.0.0.1`, fichiers en 600).

### 1.1 Secrets dans le périmètre

| # | Secret | Où il est stocké | Ce qu'il permet en cas de fuite | Crit. | Expo. |
| --- | --- | --- | --- | --- | --- |
| 1 | Clé privée AGE (SOPS) | *Abandonnée avec SOPS le 2026-11-21, retirée de l'inventaire ; fichier encore présent sur le poste (§4.6)* | Déchiffrait tous les fichiers SOPS, historique Git public compris ; les valeurs concernées ont été renouvelées | — | — |
| 2 | Clé Cosign | Clé Transit d'OpenBao, non exportable (publique : credential `cosign-public-key-transit`) | Faire signer une image malveillante par OpenBao, avec l'AppRole `jenkins-cosign` (encore faut-il la pousser dans le registry local) | C | Local |
| 3 | Token Codeberg `ci-bot-forgejo-token` (compte `cibot-leuwen-lc`) | OpenBao `kv/jenkins/ci-bot-forgejo-token`, lu par un credential Jenkins de même identifiant | Push et merge sur `rhdemo` (Write), commentaires | C | Internet |
| 4 | Token Codeberg `renovate-forgejo-token` (bot Renovate) | OpenBao `kv/jenkins/renovate-forgejo-token` | Push de branches, ouverture de PR, scope `user` (gestion des clés du compte bot) | H | Internet |
| 5 | Token Codeberg du bot fixcve (`fixcvebot-leuwen-lc`) | OpenBao `kv/jenkins/fixcve-forgejo-token` (credential Jenkins depuis le 2026-11-22) | Push sur `rhdemo` (Write) | H | Internet |
| 6 | Token(s) Codeberg et clés SSH du compte personnel `leuwen-lc` | Poste de travail (credential helper Git, `~/.ssh`) | Admin du dépôt : réglages, protections de branche, suppression | C | Internet |
| 6b | Mots de passe des comptes bots Codeberg (`cibot-leuwen-lc`, bot Renovate, `fixcvebot-leuwen-lc`) | Gestionnaire de mots de passe de l'utilisateur | Avec la 2FA, insuffisant seul pour créer des tokens ; reste la porte d'entrée du compte | C | Internet |
| 7 | Clé GPG `renovate-gpg-key` | OpenBao `kv/jenkins/renovate-gpg-key`, clé publique sur le compte bot Codeberg | Commits « vérifiés » au nom de Renovate | H | Internet |
| 8 | Kubeconfig `kubeconfig-stagingkub-infra-upgrader` | Credential Jenkins, fichier local non versionné | Upgrades Helm de l'infra du cluster (Cilium, NGF, observabilité) | H | Local |
| 9 | Kubeconfig `kubeconfig-stagingkub` (`jenkins-deployer`) | Credential Jenkins, fichier local non versionné | Déploiement et lecture des Secrets du namespace `rhdemo-stagingkub` | H | Local |
| 10 | Mot de passe `admin` Jenkins | `infra/jenkins-docker/.env` (en clair), appliqué par JCasC | Tout : lecture de tous les credentials, **dont les secrets Internet #3, #4, #7, #12**, exécution de code | C | Local |
| 11 | Mot de passe et token API du compte Jenkins `claude` | `.env` (mot de passe), OpenBao `kv/jenkins/fixcve-jenkins-api` (token) | Lecture des builds et des logs (lecture seule) | M | Local |
| 12 | Mot de passe de l'appareil « Jenkins » de la boîte des notifications | Credential Jenkins `smtp-infomaniak-credentials` | Envoyer des mails au nom de l'adresse de notification (hameçonnage), lire la boîte (IMAP) | H | Internet |
| 13 | Credential Claude (abonnement) | `~/.claude/.credentials.json` (jeton OAuth de Claude Code) | Consommation du quota d'abonnement, facturation si l'usage supplémentaire payant est activé, accès à l'historique des sessions | H | Internet |
| 14 | Token SonarQube `jenkins-sonar-token`, mot de passe admin SonarQube, `SONAR_DB_PASSWORD` | Credential Jenkins, `.env` | Falsifier la Quality Gate ; base SonarQube | M | Local |
| 15 | Secrets applicatifs stagingkub (PostgreSQL, Keycloak DB, Keycloak admin, secret client OIDC, mots de passe des utilisateurs de test) | OpenBao `kv/stagingkub/*`, recopiés en Secrets Kubernetes par ESO (inventaire : #15 à #15d) | Données de l'environnement « proche production », usurpation du client OIDC | H | LAN |
| 16 | Mêmes secrets pour ephemere | Nulle part : tirés au hasard à chaque build par `Jenkinsfile-CI` | Environnement jetable, détruit en fin de build | M | Local |
| 17 | Mot de passe admin Grafana | OpenBao `kv/observability/grafana`, recopié dans `loki-stack` par ESO (rotation automatisée depuis le 2026-11-21) | Lecture des logs et métriques, modification des dashboards | M | LAN |
| 18 | Clés privées TLS (`shared-tls-cert`, certificat du registry) | Secret Kubernetes, `infra/*/certs/` | Interception si un attaquant est déjà sur le réseau local | M | LAN |
| 20 à 22 | `secret_id` AppRole d'OpenBao (Jenkins, Cosign ; fixcve supprimé le 2026-11-22, le bot tourne dans Jenkins) | Credentials Jenkins `openbao-approle`, `openbao-cosign-approle` | Lire les secrets de l'identité concernée, ou faire signer une image (Cosign) ; valables 100 jours | C | Local |
| 23 | Mot de passe de l'utilisateur `admin` d'OpenBao | KeePassXC | Lire et écrire tous les secrets d'OpenBao | C | Local |
| 24 | Clé de déverrouillage d'OpenBao | KeePassXC et papier | Déverrouiller OpenBao, recréer un jeton root | C | Local |

### 1.2 Hors périmètre (quota de lecture seulement)

`nvd-api-key`, `ossindex-credentials`, `renovate-github-token` (lecture des dépôts publics), `dockerhub-renovate-readonly` (« Public Repo Read-only »). `notification-email` n'est pas un secret mais une donnée personnelle masquée.

### 1.3 Constats faits pendant l'inventaire

Les constats corrigés les 2026-11-16 et 2026-11-17 (Grafana, défauts `sonar123` et `changeme`, droits des fichiers locaux, exposition de ZAP, anciens secrets Codeberg Actions) sont tracés dans [log.md](log.md).

- **Les tokens Kubernetes sont de longue durée** (`type: kubernetes.io/service-account-token` dans `rbac/`). Ils n'expirent jamais.
- **La clé AGE déchiffrait l'historique** : SOPS ne protégeait que le présent, les anciens fichiers chiffrés restant dans l'historique public. Résolu par l'abandon de SOPS : les valeurs qu'ils contenaient ont été renouvelées le 2026-11-21.

---

## 2. Capacité d'automatisation par fournisseur

| Fournisseur | Créer un nouveau secret | Révoquer l'ancien | Ce qui reste manuel |
| --- | --- | --- | --- |
| **Codeberg (Forgejo)** | `POST /api/v1/users/{user}/tokens` (nom, scopes) | `DELETE /api/v1/users/{user}/tokens/{id}` | La création exige une **authentification par mot de passe** (pas par token) et, avec la 2FA, l'en-tête `X-Forgejo-OTP`. Saisie interactive du mot de passe et du code TOTP du bot (2FA active sur les trois bots depuis le 2026-11-17). |
| **Codeberg, clés GPG/SSH** | `POST /api/v1/user/gpg_keys`, `POST /api/v1/user/keys` | `DELETE /api/v1/user/gpg_keys/{id}`, `.../keys/{id}` | Rien si le token a le scope `write:user` (cas du token Renovate) |
| **Jenkins, credentials** | CLI `update-credentials-by-xml system::system::jenkins _ <id>` (ou `POST .../credential/<id>/config.xml`) | Remplacement en place | Authentification admin (mot de passe saisi, ou token admin éphémère) |
| **Jenkins, token API d'un utilisateur** | `POST /user/<id>/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken` | `.../revoke?tokenUuid=…` | Depuis Jenkins 2.129, un admin ne peut pas générer de token pour un autre utilisateur par défaut : il faut s'authentifier **en tant que** `claude` (mot de passe + crumb) *à vérifier sur la version installée* |
| **Jenkins, mots de passe locaux** | Modifier la variable, puis `POST /manage/configuration-as-code/reload` | Écrasé par JCasC | Rien |
| **Kubernetes** | Supprimer puis réappliquer le Secret `service-account-token` (nouveau token émis), ou `kubectl create token --duration` | Suppression du Secret | Rien (admin du cluster local) |
| **Cosign (Transit OpenBao)** | `bao write -f cosign-transit/keys/cosign/rotate` | Nouvelle clé publique dans le credential du CD | Publier la clé publique ; les images signées avant la rotation ne sont plus déployables (§4.3) |
| **OpenBao** | KV v2 (écriture avec contrôle de version), nouveau `secret_id` AppRole | Destruction des anciens `secret_id` | Rien (utilisateur `admin`) ; mot de passe `admin` et clé de déverrouillage à la main |
| **SOPS / AGE** | *Sans objet : SOPS abandonné* | | |
| **GPG** | `gpg --batch --quick-gen-key` | `DELETE` de la clé sur Codeberg | Rien |
| **Keycloak** | `POST /admin/realms/{realm}/clients/{uuid}/client-secret` (régénère le secret OIDC), `PUT /admin/realms/{realm}/users/{id}/reset-password` | Immédiat | Rien (admin REST ou `kcadm.sh`) |
| **PostgreSQL** | `ALTER ROLE … PASSWORD …` via `kubectl exec` | Immédiat | Rien |
| **Grafana** | Nouvelle valeur dans OpenBao (`kv/observability/grafana`), recopiée par ESO, appliquée au redémarrage (Grafana sans persistance reprend le mot de passe du Secret à chaque démarrage) | Immédiat | Rien |
| **SonarQube** | `POST /api/user_tokens/generate` (avec `expirationDate`), `POST /api/users/change_password` | `POST /api/user_tokens/revoke` | Rien |
| **Infomaniak (boîte des notifications)** | Appareil dédié : `POST /1/mail_hostings/{service_mail}/mailboxes/{mailbox}/accesses/devices` | `DELETE …/accesses/devices/{id}` | Ces routes exigent l'identifiant d'un hébergement mail (produit « Service Mail ») et un token de scope `mail` ; non utilisées pour une adresse gérée depuis my kSuite. Rotation dans le Manager (§4.8). |
| **Anthropic (abonnement Claude)** | `/logout` puis `/login` dans Claude Code | Déconnexion des sessions depuis les réglages du compte claude.ai *à vérifier* | Tout : l'authentification OAuth passe par un navigateur, et l'API d'administration Anthropic ne concerne que les clés API des organisations, pas les abonnements |

**Conclusion** : tout est automatisable sauf trois points, qui demandent une action humaine courte et incompressible :

1. le **mot de passe et le code 2FA des comptes bots Codeberg** au moment de créer leur token (c'est voulu : un token ne peut pas en créer un autre) ;
2. la **reconnexion Claude** (OAuth dans un navigateur) ;
3. le **mot de passe SMTP Infomaniak** : appareil créé et supprimé dans le Manager, le script ne fait que tester le mot de passe et le propager (§4.8).

Stocker le mot de passe et la graine TOTP des bots pour supprimer l'étape 1 est déconseillé : ce secret permettrait de recréer des tokens à volonté, et la 2FA ne servirait plus à rien.

Le compte Codeberg personnel `leuwen-lc` reste **hors du script** (décision du 2026-11-16) : aucun script ne manipule le compte administrateur du dépôt. Son contrôle reste manuel (§4.1).

---

## 3. Architecture proposée

### 3.1 Un inventaire déclaratif sans valeur

Fichier versionné `rhDemo/secrets/inventory.yaml` : une entrée par secret du §1.1, avec identifiant, criticité, exposition, méthode de rotation et cibles (chemin OpenBao, credential Jenkins, fichier AppRole ; à l'origine aussi fichier SOPS), plus les périodes cibles par criticité. La date de dernière rotation n'y figure pas : elle vit dans le journal local, pour ne pas imposer un commit à chaque rotation. Il ne contient aucune valeur et peut être publié. Il remplace la liste en commentaire de `jenkins-casc.yaml` comme référence unique.

### 3.2 Un script d'orchestration

`rhDemo/scripts/rotate-secrets.py` (Python, bibliothèque standard plus PyYAML, comme fixcve), exécuté sur le poste (pas dans Jenkins : il doit pouvoir réparer un Jenkins compromis).

```text
rotate-secrets.py <id>            # un secret
rotate-secrets.py --level C       # tous les secrets critiques
rotate-secrets.py --emergency     # tout le périmètre, dans l'ordre d'urgence (phase 3, non réalisé)
rotate-secrets.py --check         # âge des secrets, secrets en retard sur leur période
```

Un module par fournisseur dans `scripts/rotation_lib/` (`forgejo.py`, `jenkins.py`, `smtp.py`, puis `openbao.py` et `keycloak.py` avec OpenBao ; Grafana et PostgreSQL dans `rotations.py`). Chaque rotation suit le même cycle :

1. **Contrôler les cibles** avant toute création (credential Jenkins existant et du bon type, chemin OpenBao présent) ;
2. **Créer** le nouveau secret (API du fournisseur) ;
3. **Vérifier** par un appel réel avec le nouveau secret, avant de le propager (par exemple `GET /api/v1/user` et droit d'écriture sur le dépôt pour Codeberg, connexion SMTP pour le mot de passe des notifications, `kubectl auth can-i`, `cosign verify`). En cas d'échec, le nouveau secret est supprimé et rien n'a changé ;
4. **Propager** aux consommateurs : écriture dans OpenBao (lue par Jenkins, fixcve-auto et ESO), credential Jenkins pour les secrets restés dans Jenkins, synchronisation ESO forcée puis `rollout restart` pour stagingkub. Si la propagation échoue sans avoir modifié de cible, le nouveau secret est supprimé ;
5. **Révoquer** l'ancien, seulement si les étapes 3 et 4 ont réussi. En mode `--emergency`, la révocation passe **avant** la vérification : mieux vaut une CI cassée qu'un attaquant actif.
6. **Tracer** : date et identifiant dans un journal local (`~/.config/rhdemo-rotation/journal.jsonl`), jamais de valeur.

Règles de sécurité du script :

- les valeurs ne transitent que par des variables et des tubes, jamais en argument de commande (visible dans `ps`) ni dans un fichier en clair ;
- les identifiants maîtres (mot de passe admin Jenkins, mots de passe des bots) sont **demandés au lancement**, gardés en mémoire pour la session puis effacés ;
- les nouvelles valeurs aléatoires sont générées par `secrets.token_urlsafe(32)` (256 bits) ;
- aucun secret n'est affiché, sauf à la demande pour un secret à saisir à la main ailleurs.

### 3.3 Ordre en mode urgence

Principe : révoquer d'abord ce qui est **exploitable depuis Internet** (colonne Expo. du §1.1), puis les secrets LAN, puis les secrets locaux.

1. Tokens Codeberg (#3, #4, #5), mots de passe des bots (#6b), contrôle manuel du compte personnel (#6)
2. SMTP Infomaniak (#12), clé GPG (#7), Claude (#13)
3. Secrets LAN : applicatifs stagingkub (#15), Grafana (#17), clés TLS (#18)
4. Secrets locaux : OpenBao (`secret_id` #20 à #22, mot de passe `admin` #23, clé de déverrouillage #24 en cas de doute), Cosign (#2), kubeconfigs (#8, #9), admin et `claude` Jenkins (#10, #11), SonarQube (#14)

**Exception, compromission de Jenkins ou du poste** (code malveillant exécuté par la CI, accès à la session) : commencer par le mot de passe `admin` Jenkins (#10) et l'invalidation de ses sessions (redémarrage), puis le `secret_id` AppRole de Jenkins (#20) : ils donnent accès aux secrets Internet que Jenkins lit dans OpenBao. Sinon, l'attaquant relirait les nouveaux tokens au fur et à mesure de leur mise à jour. Enchaîner ensuite sur l'ordre ci-dessus.

### 3.4 Utilisation (phase 1)

Rotation automatique : tokens des trois bots Codeberg (#3, #4, #5), clé GPG de Renovate (#7). Semi-manuelle (méthode `manual-value` : valeur créée à la main, saisie, vérifiée si possible, puis propagée) : mot de passe SMTP (#12, testé en SMTP avant la mise à jour de Jenkins), token SonarQube (#14). Les autres secrets affichent leur procédure manuelle ou leur phase prévue. Une rotation faite à la main se trace avec `--record <id>`.

Avant la première rotation réelle :

1. `scripts/rotate-secrets.py --preflight` : connexion à Jenkins (mot de passe admin demandé), existence et type de chaque credential cible, présence des outils ;
2. `scripts/rotate-secrets.py --dry-run <id>` : lit les tokens, clés ou accès existants (mot de passe et code TOTP du bot demandés) et affiche ce qui serait créé et révoqué, sans rien modifier ;
3. commencer par un secret peu risqué, par exemple `fixcve-forgejo-token`, puis vérifier le prochain cycle de fixcve-auto.

Comportements à connaître :

- **Noms datés** : les tokens et accès créés s'appellent `<préfixe>-AAAAMMJJ-HHMMSS` (préfixes dans l'inventaire). Aux rotations suivantes, les anciens de même préfixe sont révoqués d'office. Les tokens créés à la main (première rotation) sont listés un par un avec confirmation, et l'option `--no` les conserve tous.
- **Portées** : si un token à révoquer n'a pas les mêmes portées que l'inventaire, le script demande confirmation. Sans accord, il s'arrête : corriger l'inventaire. Pour `fixcve-forgejo-token`, `write:repository` seul suffit (constaté sur le token d'origine).
- **Codes TOTP** : un code saisi est réutilisé pendant 25 secondes (Forgejo ne refuse pas sa réutilisation sur l'API). Si Codeberg répond 401, le script en redemande un.
- **Clé GPG** : RSA 4096, valable 2 ans, avec la même identité que l'actuelle (« Renovate Bot » et l'adresse du compte bot). Le script la génère dans un trousseau jetable en mémoire (`/dev/shm`), prouve sa possession à Codeberg (jeton signé), puis retire les anciennes clés du compte bot. Les anciens commits de Renovate apparaissent ensuite « non vérifiés » : c'est le prix de la révocation.
- **SMTP (#12)** : le script lit l'adresse dans le credential Jenkins, teste la connexion SMTP avec le mot de passe collé, et ne met à jour Jenkins que si elle réussit. Il rappelle ensuite de supprimer l'ancien appareil dans le Manager.
- **Code retour de `--check`** : 1 si un secret est en retard ou n'a jamais été tracé, ce qui permet un rappel par cron (phase 4). Les secrets à expiration imposée (`secret_id` AppRole, clé GPG, token SonarQube) sont marqués « (bloquant) » et signalés 14 jours avant leur expiration (2026-11-23, [ROTATION_SECRETS.md](ROTATION_SECRETS.md)).

Tests : `scripts/tests/test_rotation.py` (lancé par `run-all.sh`), avec de faux Codeberg et Jenkins et le vrai `gpg` sur des clés jetables (les méthodes OpenBao et Keycloak : `test_openbao.py`, `test_keycloak_rotation.py`). Les routes Codeberg ont été vérifiées dans la spécification Swagger de Codeberg (Forgejo 17), puis validées sur le vrai compte fixcve.

Corrections issues du premier essai réel : Jenkins renvoie parfois le XML des credentials en Latin-1 malgré sa déclaration UTF-8 ; Forgejo recopie la valeur saisie dans ses réponses 401, d'où le masquage systématique des chaînes longues dans les messages et le journal ; `GET /api/v1/user` exige une portée `user`, la vérification d'un token repose donc sur son droit d'écriture sur le dépôt.

**Piste** : depuis Forgejo 17, un token peut être restreint à des dépôts précis (champ `repositories` à la création). Cela réduirait encore l'impact d'une fuite. Non activé : il faut d'abord vérifier que `GET /api/v1/user` et l'initialisation de Renovate acceptent un tel token.

---

## 4. Procédures par secret

### 4.1 Tokens Codeberg (#3, #4, #5)

Le script demande le mot de passe et le code TOTP du bot, crée un token aux **mêmes scopes** que l'ancien (lus dans l'inventaire), le vérifie, l'écrit dans OpenBao (`kv/jenkins/…`), puis supprime l'ancien par son identifiant (`GET /api/v1/users/{user}/tokens` pour le retrouver par son nom). Nommer les tokens avec la date (`jenkins-ci-2026-11-16`) facilite la révocation ciblée.

**2FA (TOTP) sur les trois comptes bots** : activée le 2026-11-17 (phase 0). Sans elle, le mot de passe d'un bot (#6b) suffisait pour créer des tokens par API ; il faut désormais aussi le code TOTP, qui reste sur le téléphone de l'utilisateur. Les tokens ne sont pas concernés par la 2FA : le Git de Jenkins et de fixcve continue de s'authentifier par token. Rotations faites : 2026-11-17 (première rotation, révocation des tokens créés à la main), puis 2026-11-22 (écriture dans OpenBao).

Le compte personnel (#6) est hors script. Contrôle manuel conseillé en rotation d'urgence : réglages Codeberg > Applications (tokens et applications OAuth autorisées) et clés SSH/GPG.

### 4.2 Credentials Jenkins

Un seul module générique : remplacement du `config.xml` du credential, avec un modèle XML par type (Secret text, Secret file en base64, Username with password, AppRole). Depuis OpenBao, il ne sert plus qu'aux secrets restés dans Jenkins (#12, #14) et aux `secret_id` AppRole (#20, #21) ; #3, #4 et #7 sont écrits dans OpenBao.

Pour le mot de passe `admin` (#10) : générer une valeur, l'écrire dans `.env`, recharger JCasC. Le `.env` reste en clair en 600 (décision au §6).

### 4.3 Clé Cosign (#2)

Depuis OpenBao, la clé privée est une clé Transit non exportable : la CI fait signer par OpenBao, sans jamais détenir la clé. Rotation : nouvelle version de la clé Transit, puis publication de la nouvelle clé publique dans le credential du CD (procédure `cosign-key` de l'inventaire). Décision du 2026-11-21 : pas de re-signature, aucune ancienne image n'étant à redéployer ; les images signées avant la rotation sont refusées par le CD, il suffit de relancer la CI.

### 4.4 Kubeconfigs (#8, #9)

Supprimer le Secret `service-account-token` du compte de service, relancer `init-stagingkub.sh` (il réapplique `rbac/`, le contrôleur émet un nouveau token, et il régénère le kubeconfig), mettre à jour le credential. L'ancien token est invalide dès la suppression du Secret. Procédure manuelle dans l'inventaire depuis le 2026-11-21 ; l'automatisation reste ouverte (§5).

Évolution recommandée : passer à des tokens à durée limitée (`kubectl create token --duration=720h`) renouvelés par `rotate-secrets.py --check`, ce qui borne la fenêtre d'exploitation d'une fuite non détectée. La section RBAC de `SECURITE_JENKINS_SERVICEACCOUNT_RBAC.md` serait à mettre à jour.

### 4.5 Secrets applicatifs stagingkub (#15)

Réalisé avec OpenBao (2026-11-21) : `rotate-secrets.py` écrit la nouvelle valeur dans OpenBao, force la synchronisation ESO, l'applique côté serveur (`ALTER ROLE` pour PostgreSQL, API d'administration de Keycloak pour le secret client, l'administrateur et les utilisateurs de test) et redémarre les pods, avec retour arrière en cas d'échec. Détail par secret : [OPENBAO.md](OPENBAO.md), section « Rotation ».

Ephemere (#16) n'a plus de secrets stockés : valeurs tirées au hasard à chaque build.

### 4.6 Clé AGE (#1)

Sans objet : SOPS est abandonné (2026-11-21), les valeurs qu'il protégeait ont été renouvelées. Reste à détruire la clé : le fichier `~/.config/sops/age/keys.txt` est toujours sur le poste (constaté le 2026-11-23). Le credential `sops-age-key` n'est plus déclaré dans `jenkins-casc.yaml` ; vérifier dans la console Jenkins qu'il n'y subsiste pas. La détruire ne présente aucun risque : rien ne la lit plus, et l'historique Git qu'elle déchiffre ne contient que des valeurs renouvelées.

### 4.7 Claude (#13)

Le compte utilise un abonnement, pas de clé API Console. Ce secret ne sert pas à la chaîne CI (fixcve-auto n'appelle plus Claude Code), et sa rotation ne peut pas être automatisée.

Procédure : `/logout` puis `/login` dans Claude Code, puis déconnexion des autres sessions dans les réglages du compte claude.ai *à vérifier*. Le script se contente de rappeler la procédure dans la liste d'urgence.

Mesure qui réduit le risque de facturation : ne pas activer l'usage supplémentaire payant au-delà du forfait, ou le plafonner *à vérifier dans les réglages de l'abonnement*. Une fuite ne coûte alors que du quota.

### 4.8 SMTP Infomaniak (#12)

Jenkins s'authentifie en SMTP avec le mot de passe d'un **appareil** dédié (Manager > Gérer mon adresse mail > Appareils), et non avec le mot de passe principal de la boîte : une fuite du credential ne donne que ce mot de passe, révocable seul en supprimant l'appareil. Mis en place le 2026-11-17 ; jusque-là, Jenkins utilisait le mot de passe principal.

Constats du 2026-11-17 (spécification OpenAPI officielle `https://developer.infomaniak.com/openapi.json`, puis essais réels) :

- les **mots de passe d'application** du compte Infomaniak (`/2/profile/applications/passwords`) ne servent pas au SMTP de la boîte : refusés (535) ; celui créé en juillet 2026 n'avait jamais été utilisé. L'API ne permet d'ailleurs pas de les supprimer ;
- les **appareils** correspondent aux « accès appareil » de l'API (`/1/mail_hostings/{service_mail}/mailboxes/{mailbox}/accesses/devices`, création, changement de mot de passe, suppression). Ces routes exigent l'identifiant d'un hébergement mail et un token de scope `mail`, valable pour toutes les boîtes de l'hébergement. L'adresse étant gérée depuis my kSuite, sans page « Service Mail » visible, cette voie n'est pas retenue.

**Procédure retenue (semi-manuelle, sans token API)** : `rotate-secrets.py smtp-infomaniak`

1. dans le Manager (Gérer mon adresse mail > Appareils), ajouter un appareil nommé `rhdemo-jenkins-ci-<date>` et copier le mot de passe affiché ;
2. le coller quand le script le demande : il teste la connexion SMTP (`mail.infomaniak.com:465`) avec l'adresse lue dans le credential Jenkins, et ne met à jour `smtp-infomaniak-credentials` que si elle réussit ;
3. supprimer l'ancien appareil dans le Manager (rappelé par le script).

En urgence : supprimer d'abord l'ancien appareil (les notifications échouent jusqu'à l'étape 2), puis en créer un nouveau.

Limite : le mot de passe d'un appareil permet aussi de **lire** la boîte (IMAP). D'où l'intérêt d'une adresse qui ne sert qu'aux notifications.

---

## 5. Plan de mise en œuvre

| Phase | Contenu | Effort estimé |
| --- | --- | --- |
| 0 | Corrections immédiates : mot de passe Grafana, défauts `sonar123` et `changeme` (ZAP), droits 600 sur les fichiers locaux, vérification des anciens secrets Codeberg Actions, **2FA sur les trois comptes bots Codeberg et sur le compte personnel**, revue manuelle des tokens et clés SSH du compte personnel. *Terminée le 2026-11-17 (aucun secret Actions restant aux niveaux dépôt, organisation et utilisateur).* | 1 h 30 |
| 1 | `inventory.yaml`, module Jenkins générique, module Codeberg (tokens et GPG), saisie manuelle vérifiée (SMTP), `--check`. *Implémentée le 2026-11-17 (§3.4). #3, #4, #5, #7 et #12 renouvelés le 2026-11-17, puis #3, #4, #5 et #7 de nouveau le 2026-11-22 lors de leur passage dans OpenBao.* | 1,5 jour |
| 2 | Modules Kubernetes (kubeconfigs), Cosign avec re-signature, secrets applicatifs stagingkub. *Cosign et stagingkub réalisés par OpenBao (2026-11-21), sans re-signature (§4.3). Kubeconfigs : procédure manuelle, automatisation ouverte.* | 1 à 2 jours |
| 3 | Module AGE, mode `--emergency`. *Module AGE sans objet (SOPS abandonné). `--emergency` ouvert ; en attendant, ordre d'urgence dans [ROTATION_SECRETS.md](ROTATION_SECRETS.md).* | 1 jour |
| 4 | Tokens Kubernetes à durée limitée, rotation périodique planifiée (rappel par `--check` en cron, pas de rotation silencieuse). *Ouvert.* | 0,5 jour |

Tests : comme pour fixcve-auto, un bac à sable avec un faux Forgejo et un faux Jenkins valide les modules sans toucher aux vrais comptes. Le module Kubernetes se teste sur le cluster KinD. Le code est sous `scripts/`, donc hors couverture Sonar Java ; les modules Python suivent la règle `python3 -I`.

### État au 2026-11-23

Relevé par `rotate-secrets.py --check` et le journal local des rotations.

**Renouvelés et tracés** : tokens Codeberg des trois bots (#3, #4, #5) et clé GPG de Renovate (#7) le 2026-11-22 ; SMTP (#12) le 2026-11-17 ; secrets applicatifs stagingkub (#15 à #15d) et Grafana (#17) le 2026-11-21 ; `secret_id` AppRole de Jenkins (#20) le 2026-11-22. Ephemere (#16) est régénéré à chaque build.

**Sans rotation journalisée** (13 secrets, `--check` sort en code 1) :

- créés neufs à l'installation d'OpenBao (2026-11-21 et 22) mais non tracés : clé Cosign Transit (#2), mot de passe `admin` (#23) et clé de déverrouillage (#24) d'OpenBao, `secret_id` AppRole de Cosign (#21, journalisé sous un ancien identifiant, `openbao-approle-jenkins-cosign`, que `--check` ne reconnaît pas) ;
- jamais renouvelés depuis l'inventaire du 2026-11-16, ou sans trace : mot de passe `admin` Jenkins (#10), compte Jenkins `claude` (#11), token SonarQube (#14), kubeconfigs (#8, #9), clés TLS (#18), mots de passe des bots Codeberg (#6b), session Claude (#13), contrôle du compte personnel (#6).

### Reste à faire

1. **Rattraper le journal** des secrets neufs non tracés (#2, #21, #23, #24) par `--record`. Urgent pour #21 : son `secret_id` expire au bout de 100 jours (`SECRET_ID_TTL` de `configure-openbao.sh`), vers le 2027-03-01, et sans trace `--check` ne préviendra pas ; à l'échéance, la signature Cosign de la CI échouerait.
2. **Renouveler les secrets jamais renouvelés**, par criticité : #10 et #6b (C) d'abord, puis #8, #9 et #13 (H), puis #11, #14 et #18 (M) ; tracer chaque rotation manuelle par `--record`.
3. **Détruire la clé AGE** (§4.6) et vérifier l'absence du credential `sops-age-key` dans Jenkins.
4. **Kubeconfigs (#8, #9)** : automatiser la procédure manuelle, puis passer à des tokens à durée limitée (phase 4). Les tokens actuels sont des Secrets `service-account-token` sans expiration (`infra/stagingkub/rbac/`).
5. **Mode `--emergency`** (phase 3) ; en attendant, ordre d'urgence manuel dans [ROTATION_SECRETS.md](ROTATION_SECRETS.md).
6. **Rappel périodique** : la ligne cron de `--check` documentée dans [ROTATION_SECRETS.md](ROTATION_SECRETS.md) n'est pas installée sur le poste (seule la rotation du journal d'audit d'OpenBao l'est). Tant que le point 1 n'est pas fait, le rappel signalerait 13 secrets en permanence.
7. **Piste** : tokens Codeberg restreints au dépôt `rhdemo` (§3.4), non implémentée.
8. Points marqués *à vérifier* (token Jenkins de `claude`, déconnexion des sessions Claude, plafond de facturation).

### Périodes de rotation proposées

| Criticité | Période | Exemples |
| --- | --- | --- |
| C | 90 jours, et immédiatement en cas de doute | Cosign, `secret_id` AppRole, `admin` Jenkins et OpenBao, tokens Codeberg Write |
| H | 180 jours | kubeconfigs (30 jours s'ils passent à durée limitée), GPG, SMTP, secrets stagingkub |
| M | 1 an | SonarQube, Grafana, compte Jenkins `claude` |

---

## 6. Décisions

| Question | Réponse | Conséquence |
| --- | --- | --- |
| Claude : abonnement ou clé API ? | Abonnement | Rotation manuelle (§4.7), pas d'API de révocation |
| 2FA sur les bots Codeberg ? | Non activée | Activée le jour même (TOTP), mots de passe des bots ajoutés à l'inventaire (#6b) |
| SMTP : API Infomaniak ou boîte dédiée ? (2026-11-16) | API Infomaniak, sous réserve de vérification | Vérification du 2026-11-17 : l'API des appareils exige un hébergement mail et un token `mail` valable pour toutes les boîtes, les mots de passe d'application ne servent pas au SMTP. Rotation semi-manuelle par appareil dédié retenue (§4.8), token API Infomaniak (ancien #19) retiré de l'inventaire. |
| Compte personnel dans le script ? | Non | Contrôle manuel uniquement (§4.1) |
| Chiffrer par SOPS les fichiers locaux non versionnés (`.env` Jenkins, `grafana-values.yaml`) ? | Non (sans objet depuis l'abandon de SOPS) | La clé AGE est lisible par le même compte unix que ces fichiers : contre un accès à la session, le chiffrement n'apporte rien. SOPS reste réservé aux secrets versionnés. Les droits 600 ferment l'accès aux autres comptes du poste. Gains résiduels jugés insuffisants face au coût (wrapper obligatoire pour toute commande Compose) : protection d'une copie accidentelle du dossier, source unique pour le script de rotation. À reconsidérer en phase 3 si le script en a besoin. |
| Stockage des secrets (2026-11-21) | OpenBao, SOPS abandonné | Propagation par OpenBao, Cosign par Transit, stagingkub par ESO ([ETUDE_OPENBAO.md](ETUDE_OPENBAO.md)) |
| Re-signer les images après rotation de Cosign ? (2026-11-21) | Non | Les images signées avant la rotation ne sont plus déployables ; relancer la CI |
| Admin Grafana dans OpenBao ? (2026-11-21) | Oui | `kv/observability/grafana`, recopié dans `loki-stack` par ESO (rôle `eso-observability` limité à `kv/observability/*`), rotation `rotate-secrets.py grafana-admin` avec vérification de connexion et retour arrière. Aucune dépendance de démarrage nouvelle : Grafana ne sert pas à accéder à OpenBao, et ESO était déjà en place pour stagingkub. Contrepartie : Grafana ne démarre pas tant que le Secret n'existe pas (OpenBao déverrouillé à l'installation) ; un changement de mot de passe fait dans l'interface est écrasé au redémarrage. |
| Mots de passe Jenkins (`admin`, `claude`) et base SonarQube dans OpenBao ? (2026-11-21) | Non, restent dans le fichier local de `jenkins-docker` (600, copie dans KeePassXC) | 1. **Démarrage** : ces valeurs sont lues par Docker Compose et JCasC au lancement des conteneurs. Les tirer d'OpenBao imposerait OpenBao déverrouillé et une connexion `admin` à chaque démarrage de Jenkins ou de SonarQube, alors qu'OpenBao est scellé après chaque redémarrage du poste. 2. **Racines de confiance séparées** : le mot de passe `admin` de Jenkins est un identifiant maître du script de rotation (§3.2), qui doit pouvoir réparer Jenkins quand OpenBao est perdu ou compromis, et inversement ; les mettre dans OpenBao ferait d'une compromission d'OpenBao une compromission de Jenkins. 3. **Gain faible** : la valeur finit de toute façon dans l'environnement du conteneur (lisible par `docker inspect` avec le même compte unix que le fichier) ; OpenBao n'en réduirait pas l'exposition locale, il unifierait seulement la gestion. 4. **Exposition** : locale (#10, #11, #14), contre LAN pour Grafana. Rotation manuelle conservée (`--list`, puis `--record`). |

Points restant à vérifier avant d'implémenter : les mentions *à vérifier* de ce document.
