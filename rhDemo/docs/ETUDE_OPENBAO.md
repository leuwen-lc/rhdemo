---
statut: proposition
verifie_le: 2026-11-17
sources:
  - rhDemo/docs/ETUDE_ROTATION_SECRETS.md
  - rhDemo/secrets/inventory.yaml
  - rhDemo/infra/jenkins-docker/docker-compose.yml
  - rhDemo/infra/stagingkub/scripts/init-stagingkub.sh
  - rhDemo/infra/stagingkub/scripts/repair-cluster-after-restart.sh
  - rhDemo/infra/stagingkub/helm/rhdemo/templates/networkpolicy-default-deny.yaml
  - rhDemo/Jenkinsfile-CI
  - rhDemo/Jenkinsfile-CD
---

# Étude : OpenBao comme gestionnaire de secrets de RHDemo

**Objectif** : évaluer ce qu'apporterait [OpenBao](https://openbao.org) (fork libre de HashiCorp Vault, licence MPL 2.0, projet de la Linux Foundation) par rapport à la démarche actuelle : secrets chiffrés par SOPS dans Git, credentials Jenkins saisis à la main, script `rotate-secrets.py` ([ETUDE_ROTATION_SECRETS.md](ETUDE_ROTATION_SECRETS.md)).

**Statut** : proposition, rien n'est implémenté. Les points marqués *à vérifier* n'ont pas trouvé de source fiable au 2026-11-17 et sont à tester en premier (étape 0 du §7).

**Verdict** : OpenBao n'apporte presque rien pour les secrets exposés sur Internet (Codeberg, Infomaniak, Claude), qui restent gérés par `rotate-secrets.py`. Il apporte beaucoup pour les secrets internes : signature Cosign sans clé extractible, identifiants PostgreSQL renouvelés automatiquement, journal d'audit de chaque lecture, et plus aucun secret dans l'historique Git public. Il remplacerait avantageusement les phases 2 à 4 de l'étude de rotation. Coût principal : le **déverrouillage** après chaque redémarrage du poste (§5), et un service critique de plus.

---

## 1. Situation actuelle

| Flux | Fonctionnement | Faiblesse |
| --- | --- | --- |
| Secrets applicatifs stagingkub (#15) | `secrets/secrets-stagingkub.yml` chiffré par SOPS dans Git, déchiffré par `init-stagingkub.sh` qui crée les Secrets Kubernetes (`kubectl create secret`) une seule fois | Rotation = modifier le fichier, relancer à la main la création des Secrets et les pods. L'historique chiffré est public : une fuite de la clé AGE le déchiffre en entier. |
| Credentials Jenkins (#2, #3, #4, #7, #8, #9, #12, #14) | Saisis dans l'interface, stockés chiffrés dans `jenkins_home` | Aucune trace des lectures : une fuite via un build compromis passe inaperçue. |
| Clé Cosign (#2) | Clé privée et mot de passe en credentials Jenkins, signature dans `Jenkinsfile-CI`, vérification par la clé publique dans `Jenkinsfile-CD` | La clé est extractible par tout build qui obtient le credential ; sa rotation impose de re-signer les images. |
| Kubeconfigs Jenkins (#8, #9) | Tokens de compte de service sans expiration | Fenêtre d'exploitation illimitée en cas de fuite non détectée. |

Numéros : inventaire de [ETUDE_ROTATION_SECRETS.md](ETUDE_ROTATION_SECRETS.md) §1.1 et `secrets/inventory.yaml`.

---

## 2. Apport par secret

| # | Secret | Avec OpenBao | Gain |
| --- | --- | --- | --- |
| 3, 4, 5, 7 | Tokens et clé GPG des bots Codeberg | Stockage KV, lecture par Jenkins au moment du build | **Faible** : audit des lectures. Pas de moteur Codeberg : la rotation reste dans `rotate-secrets.py`, qui écrirait dans OpenBao au lieu de Jenkins. |
| 12 | Mot de passe SMTP | Idem | **Faible**, idem. |
| 13 | Session Claude | Aucun | Nul. |
| 2 | Clé Cosign | Moteur **Transit** : la clé privée est créée et utilisée dans OpenBao, jamais exportée ; cosign signe par `openbao://<clé>` | **Fort** : la clé ne peut plus être volée, seulement utilisée tant qu'un accès est valide. Rotation par nouvelle version de clé. |
| 15 | Secrets applicatifs stagingkub | KV synchronisé vers les Secrets Kubernetes par External Secrets Operator (ESO) ; mots de passe PostgreSQL gérés par le moteur **database** (rôles statiques renouvelés par OpenBao) | **Fort** : plus de secret dans Git, rotation automatique des mots de passe des bases. |
| 1 | Clé AGE | Devient inutile une fois SOPS retiré | **Fort** : règle le constat du §1.3 de l'étude de rotation (historique public déchiffrable). La racine de confiance passe à la clé de déverrouillage (§5). |
| 8, 9 | Kubeconfigs Jenkins | Moteur kubernetes *à vérifier dans OpenBao* ; sinon `kubectl create token --duration` sans OpenBao | Moyen, et atteignable sans OpenBao. |
| 18 | Clés TLS | Moteur **PKI** : certificats à courte durée | Moyen, optionnel. |
| Tous | — | **Audit device** : chaque lecture et écriture journalisée (identité, chemin, date, jamais la valeur) | **Fort** : en rotation d'urgence, savoir quels secrets ont été lus et par qui, donc quoi renouveler en premier. |

OpenBao ne remplace pas KeePassXC : la clé de déverrouillage, les mots de passe des bots et le mot de passe admin d'OpenBao restent des secrets humains.

---

## 3. Compatibilités (état au 2026-11-17)

| Point | Constat | Source | À faire |
| --- | --- | --- | --- |
| Version | Ligne 2.7 (septembre–octobre 2026). Les seals KMS (AWS, GCP…) sont devenus des plugins externes en 2.7 ; le seal **static** (clé fournie par la configuration) existe depuis 2.4 | Notes de version OpenBao 2.7.0, docs du seal static | Épingler l'image par digest (invariant du projet), suivi par Renovate |
| Cosign | Schémas `openbao://` et `hashivault://` reconnus, moteur Transit requis, variables `BAO_ADDR`/`BAO_TOKEN` ; signature sans Rekor (`--tlog-upload=false`) déjà utilisée par le projet | Docs KMS de Sigstore, billet Control Plane d'août 2026 | *À vérifier* : chemin de montage Transit non standard côté OpenBao, version de cosign des agents |
| External Secrets Operator | Pas de fournisseur OpenBao dédié : le fournisseur Vault fonctionne (API compatible) ; ESO 2.7 ajoute des options propres à OpenBao (namespaces, CA) | Notes de version ESO 2.7.0, guides NVIDIA et Kubermatic | Authentification Kubernetes, KV v2 |
| Plugin Jenkins HashiCorp Vault | Aucune source sur la compatibilité avec OpenBao | — | *À vérifier* (étape 0). Repli : CLI `bao` ou `curl` dans l'agent, authentification AppRole |
| PostgreSQL | Moteur database : rôles dynamiques, rôles **statiques** (utilisateur existant, mot de passe renouvelé selon une période), rotation des identifiants racine, hachage `scram-sha-256` | Docs OpenBao du moteur database et du plugin PostgreSQL | Ne pas gérer par rôle statique les identifiants racine confiés à OpenBao (avertissement de la doc) |
| Kubernetes (moteur de tokens) | Non trouvé dans la documentation OpenBao | — | *À vérifier* ; repli sans OpenBao (§2) |
| Helm | Chart officiel (`openbao.github.io/openbao-helm`, aussi en OCI sur ghcr.io), injecteur d'agent et fournisseur CSI | Docs OpenBao Kubernetes | Non utilisé dans l'architecture retenue (§4) |

---

## 4. Architecture proposée

### 4.1 Où faire tourner OpenBao

| Option | Pour | Contre |
| --- | --- | --- |
| **A. Conteneur dans `infra/jenkins-docker`** (recommandée) | Cycle de vie indépendant du cluster KinD, souvent recréé ; sert la CI dès l'étape 1 ; même schéma que `kind-registry`, raccordé au réseau `kind` par `repair-cluster-after-restart.sh` | Hors des NetworkPolicies Kubernetes : protection par le réseau Docker et la liaison à `127.0.0.1` |
| B. Dans le cluster (chart Helm) | Outils Kubernetes natifs (injecteur, CSI) | Perdu à chaque recréation du cluster, ce qui oblige à restaurer et redéverrouiller ; la CI dépendrait de stagingkub |

Configuration de l'option A :

- image officielle épinglée par digest ; port `8200` publié sur `127.0.0.1` seulement (même raison que Jenkins : les règles iptables de Docker passent avant ufw) ; TLS avec un certificat de la même autorité locale que le registry ;
- stockage intégré (**Raft**, un seul nœud) sur un volume nommé ;
- **audit device** fichier sur un volume dédié, rotation des journaux ;
- consommation mémoire de l'ordre de quelques centaines de Mo, *à mesurer* : le poste n'a qu'environ 2 Go libres quand la CI et stagingkub tournent ensemble.

### 4.2 Identités et politiques

| Client | Méthode d'authentification | Droits (politique) |
| --- | --- | --- |
| Jenkins (pipelines) | **AppRole** : `role_id` dans la configuration, `secret_id` à durée courte en credential Jenkins (le seul secret restant dans Jenkins) | Lecture des chemins KV des pipelines, `sign` sur la clé Transit Cosign |
| ESO (stagingkub) | **Kubernetes** : OpenBao valide le token du compte de service d'ESO auprès de l'API du cluster | Lecture de `kv/stagingkub/*` et des identifiants database |
| Administrateur | Utilisateur dédié, token de courte durée | Écriture KV, gestion des rôles ; le token root est révoqué après l'installation (`bao operator generate-root` pour le régénérer) |
| `rotate-secrets.py` | Token administrateur demandé au lancement | Écriture des chemins des secrets qu'il renouvelle |

Dans le namespace `rhdemo-stagingkub`, rien ne change : les pods lisent toujours des Secrets Kubernetes, créés par ESO au lieu d'un script. Le Default Deny reste intact. Seul le contrôleur ESO, dans son propre namespace, reçoit une règle de sortie vers OpenBao.

---

## 5. Déverrouillage : le vrai coût

Au démarrage, OpenBao est **scellé** : il ne peut rien déchiffrer tant qu'on ne lui fournit pas la clé de déverrouillage. Tant que c'est le cas, la CI et les synchronisations ESO échouent.

| Mode | Fonctionnement | Évaluation pour RHDemo |
| --- | --- | --- |
| **Shamir, clé saisie** (recommandé) | Une part, seuil 1, gardée dans KeePassXC avec une copie papier. Déverrouillage par un script lancé après le démarrage du poste, qui lit la clé via le Secret Service de KeePassXC, avec confirmation | Une action par démarrage, intégrable à `repair-cluster-after-restart.sh`. La clé n'est jamais sur le disque en clair. |
| Seal static | La clé est dans la configuration, donc sur le disque | Équivaut à la clé AGE actuelle sur le disque ; ne protège que contre le vol d'une sauvegarde. La documentation demande d'en évaluer soigneusement l'usage. |
| Seal KMS ou Transit | Clé confiée à un KMS externe ou à un autre OpenBao | Pas de KMS disponible sur un poste unique. |

**Racine de confiance** : la clé de déverrouillage remplace la clé AGE. Sa perte rend les données irrécupérables, y compris les instantanés Raft (`bao operator raft snapshot save`), qui restent chiffrés. Il faut donc deux copies hors du poste : KeePassXC synchronisé et papier.

---

## 6. Impact sur l'existant

- **Invariant de sécurité** (CLAUDE.md) : « Secrets : jamais en clair dans Git, uniquement chiffrés par SOPS » deviendrait « référencés dans OpenBao, ou chiffrés par SOPS pendant la transition ». Entrée à ajouter dans `DECISIONS.md`.
- **SOPS** : retiré par étapes, fichier par fichier. `SOPS_SETUP.md` passe en historique à la fin de la migration. Les anciens fichiers chiffrés restent dans l'historique Git : leurs valeurs doivent avoir changé avant que la clé AGE soit abandonnée (même règle que le §1.3 de l'étude de rotation).
- **`rotate-secrets.py`** : conservé pour les secrets exposés sur Internet ; nouvelle cible `{kind: openbao, path: …}` dans l'inventaire, à la place des credentials Jenkins migrés.
- **Étude de rotation** : les phases 2 (Kubernetes, Cosign, stagingkub) et 4 (tokens à durée limitée) seraient remplacées par les étapes 2 à 4 ci-dessous.
- **Pipelines** : les blocs `withCredentials` concernés sont remplacés par une lecture OpenBao (plugin ou CLI). `PIPELINES_CI_CD.md` est à mettre à jour.

---

## 7. Plan par étapes

Chaque étape est réversible et utilisable seule. Les credentials Jenkins et les fichiers SOPS ne sont retirés qu'après une CI verte avec la nouvelle source.

| Étape | Contenu | Critère de sortie | Effort |
| --- | --- | --- | --- |
| 0 | Prototype jetable : OpenBao en conteneur, tests des points *à vérifier* (plugin Jenkins, cosign `openbao://` avec la version des agents, moteur kubernetes), mesure mémoire | Décision de continuer ou d'abandonner, consignée dans cette étude | 0,5 jour |
| 1 | OpenBao dans `jenkins-docker` (Raft, TLS, audit), procédure de déverrouillage via KeePassXC, KV v2 ; migration des secrets des pipelines Renovate et des notifications ; cible `openbao` dans `rotate-secrets.py` | Un cycle CI et Renovate vert sans les credentials migrés, lectures visibles dans le journal d'audit | 1,5 jour |
| 2 | Cosign par Transit : signature `openbao://cosign` dans `Jenkinsfile-CI`, clé publique exportée pour `Jenkinsfile-CD` ; ancienne clé publique conservée tant que des images signées avec elle restent déployables | CD vert sur une image signée par Transit, credentials `cosign-private-key` et `cosign-password` supprimés | 1 jour |
| 3 | ESO dans stagingkub, `ExternalSecret` à la place des `kubectl create secret` de `init-stagingkub.sh` ; NetworkPolicy de sortie d'ESO vers OpenBao | Recréation complète de stagingkub sans `secrets-stagingkub.yml` | 1 jour |
| 4 | Rôles statiques PostgreSQL (bases rhdemo et Keycloak) ; redémarrage des pods à chaque renouvellement (Reloader ou `rollout restart`, car Spring Boot et Keycloak lisent le mot de passe au démarrage) | Mot de passe renouvelé par OpenBao, application et Keycloak reconnectés sans intervention | 1 jour |
| 5 (option) | PKI pour les certificats internes, tokens Kubernetes à courte durée | — | 1 jour |

Total : environ 5 jours, étape 0 comprise.

---

## 8. Risques et points ouverts

- **Point unique de défaillance** : OpenBao arrêté ou scellé bloque CI, CD et synchronisations. À mitiger avec un healthcheck, une alerte dans Grafana et une procédure de déverrouillage documentée.
- **Sauvegarde** : instantané Raft régulier, à restaurer pour test au moins une fois ; sans la clé de déverrouillage, il ne sert à rien.
- **Bootstrap** : le `secret_id` AppRole de Jenkins devient le secret le plus sensible de Jenkins. Il faut lui donner une durée courte et le renouveler par `rotate-secrets.py`.
- **Mémoire** : à mesurer à l'étape 0, la marge du poste étant faible.
- **Complexité pédagogique** : bénéfice réel pour une preuve de concept DevSecOps (secrets dynamiques, signature sans clé extractible, audit), mais la documentation d'exploitation (déverrouillage, sauvegarde, restauration) devient indispensable.

## 9. Recommandation

Faire l'étape 0, puis décider. Si elle est concluante, enchaîner les étapes 2 (Cosign) et 3 (ESO), qui apportent le plus, l'étape 1 étant leur prérequis. Ne pas poursuivre la phase 2 de l'étude de rotation pour Cosign et les secrets stagingkub tant que cette décision n'est pas prise, pour ne pas coder deux fois.

## Sources

- OpenBao : [notes de version 2.7.0](https://openbao.org/community/release-notes/2-7-0/), [seal static](https://openbao.org/docs/configuration/seal/static/), [moteur database](https://openbao.org/docs/secrets/databases/), [plugin PostgreSQL](https://openbao.org/docs/secrets/databases/postgresql/), [Helm](https://openbao.org/docs/platform/k8s/helm/)
- Sigstore : [support KMS de cosign](https://docs.sigstore.dev/cosign/kms_support), [signature souveraine avec OpenBao et cosign](https://control-plane.io/posts/sovereign-signing-openbao-cosign-flux/)
- External Secrets Operator : [version 2.7.0](https://newreleases.io/project/artifacthub/helm/external-secrets-operator/external-secrets/release/2.7.0), [guide ESO avec OpenBao](https://docs.nvidia.com/mission-control/docs/nmc-software-installation-guide/2.5.0/gitops-components/external-secrets.html)
- Jenkins : [plugin HashiCorp Vault](https://plugins.jenkins.io/hashicorp-vault-plugin)
