---
statut: historique
verifie_le: 2026-11-21
sources:
  - rhDemo/docs/etudes/ETUDE_ROTATION_SECRETS.md
  - rhDemo/secrets/inventory.yaml
  - rhDemo/infra/jenkins-docker/docker-compose.yml
  - rhDemo/infra/stagingkub/scripts/init-stagingkub.sh
  - rhDemo/infra/stagingkub/scripts/repair-cluster-after-restart.sh
  - rhDemo/infra/stagingkub/helm/rhdemo/templates/networkpolicy-default-deny.yaml
  - rhDemo/Jenkinsfile-CI
  - rhDemo/Jenkinsfile-CD
  - rhDemo/infra/jenkins-docker/Dockerfile.agent
  - rhDemo/scripts/fixcve_lib/poller.py
  - rhDemo/scripts/fixcve-install.sh
  - rhDemo/infra/jenkins-docker/init-registry-certs.sh
  - rhDemo/docs/CERTIFICATS_WEB.md
---

> **Historique** : étude mise en œuvre (étapes 1 à 4) et migration depuis SOPS terminée en novembre 2026. État courant et exploitation : [OPENBAO.md](../OPENBAO.md).

# Étude : OpenBao comme gestionnaire de secrets de RHDemo

**Objectif** : évaluer ce qu'apporterait [OpenBao](https://openbao.org) (fork libre de HashiCorp Vault, licence MPL 2.0, projet de la Linux Foundation) par rapport à la démarche actuelle : secrets chiffrés par SOPS dans Git, credentials Jenkins saisis à la main, script `rotate-secrets.py` ([ETUDE_ROTATION_SECRETS.md](ETUDE_ROTATION_SECRETS.md)).

**Statut** : proposition. L'étape 0 (prototype jetable) a été réalisée le 2026-11-20 : tous les points *à vérifier* sont levés, résultats au §7.1. **Décision : continuer.** Les étapes 1 à 4 sont codées sur la branche `evolution_openbao` (2026-11-21), pas encore déployées : exploitation et points restant à valider dans [OPENBAO.md](../OPENBAO.md).

**Verdict** : OpenBao n'apporte presque rien pour les secrets exposés sur Internet (Codeberg, Infomaniak, Claude), qui restent gérés par `rotate-secrets.py`. Il apporte beaucoup pour les secrets internes : signature Cosign sans clé extractible, journal d'audit de chaque lecture, et plus aucun secret dans l'historique Git public. Il remplacerait avantageusement les phases 2 à 4 de l'étude de rotation. Coût principal : le **déverrouillage** manuel après chaque redémarrage du poste ou du conteneur (§5), et un service critique de plus. Le prototype a levé les doutes techniques : cosign signe par Transit avec la version des agents, le plugin Jenkins fonctionne tel quel, et la mémoire consommée est négligeable (moins de 30 Mo).

---

## 1. Situation actuelle

| Flux | Fonctionnement | Faiblesse |
| --- | --- | --- |
| Secrets applicatifs stagingkub (#15) | `secrets/secrets-stagingkub.yml` chiffré par SOPS dans Git, déchiffré par `init-stagingkub.sh` qui crée les Secrets Kubernetes (`kubectl create secret`) une seule fois | Rotation = modifier le fichier, relancer à la main la création des Secrets et les pods. L'historique chiffré est public : une fuite de la clé AGE le déchiffre en entier. |
| Credentials Jenkins (#2, #3, #4, #7, #8, #9, #12, #14) | Saisis dans l'interface, stockés chiffrés dans `jenkins_home` | Aucune trace des lectures : une fuite via un build compromis passe inaperçue. |
| Credentials de fixcve-auto (#5, #11, clé NVD) | `~/.config/rhdemo-fixcve/credentials.sops.yaml`, hors Git, déchiffré par `fixcve-auto-poll.sh` à chaque passage du cron avec la clé AGE personnelle | Le cron dispose d'une clé AGE qui déchiffre **tous** les fichiers SOPS, historique Git compris, pour lire trois secrets. Aucune trace des lectures. |
| Clé Cosign (#2) | Clé privée et mot de passe en credentials Jenkins, signature dans `Jenkinsfile-CI`, vérification par la clé publique dans `Jenkinsfile-CD` | La clé est extractible par tout build qui obtient le credential ; sa rotation impose de re-signer les images. |
| Certificats TLS (#18) | Tous auto-signés, sans autorité : `shared-tls-cert` du Gateway stagingkub (365 jours, généré une fois par `init-stagingkub.sh`), registry (**10 ans**, `init-registry-certs.sh`), nginx ephemere (365 jours). L'option Let's Encrypt de `CERTIFICATS_WEB.md` n'est pas celle utilisée | Chaque client approuve le certificat lui-même : renouveler celui du registry impose de le recopier dans `/etc/docker/certs.d`, dans le nœud KinD et dans les agents. Clé du registry exploitable 10 ans en cas de fuite ; clés privées sur le disque. |
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
| 15 | Secrets applicatifs stagingkub | KV synchronisé vers les Secrets Kubernetes par External Secrets Operator (ESO) ; mots de passe PostgreSQL renouvelés à la demande par `rotate-secrets.py` (étape 4), sans le moteur **database** (§8) | **Fort** : plus de secret dans Git, lectures auditées, rotation des mots de passe des bases en une commande. |
| 5, 11, NVD | Credentials de fixcve-auto | KV `kv/fixcve/*`, lu par le poller avec un AppRole dédié (étape 1 bis) | **Moyen** : le cron ne lit plus que ses trois secrets au lieu de détenir la clé AGE, lectures auditées, `secret_id` révocable. Le fichier n'étant pas dans Git, le défaut de l'historique public ne le concerne pas. |
| 1 | Clé AGE | Devient inutile une fois SOPS retiré, y compris pour `credentials.sops.yaml` de fixcve-auto (étape 1 bis) | **Fort** : règle le constat du §1.3 de l'étude de rotation (historique public déchiffrable). La racine de confiance passe à la clé de déverrouillage (§5). |
| 8, 9 | Kubeconfigs Jenkins | Moteur **kubernetes** (intégré, vérifié à l'étape 0) : token de compte de service à durée courte, émis à la demande. Ces tokens ne sont pas révocables avant expiration (§7.1) | Moyen : plus de token permanent dans Jenkins, mais une durée courte s'obtient aussi par `kubectl create token --duration`. |
| 18 | Clés TLS | Autorité locale (racine hors ligne, intermédiaire dans le moteur **PKI**) ; `shared-tls-cert` émis et renouvelé par cert-manager (30 à 90 jours) ; registry et OpenBao émis pour un an environ (§4.3) | **Moyen** : une seule ancre de confiance, plus de certificat de 10 ans, clé du Gateway hors du disque et renouvelée sans intervention, émissions auditées. Exposition limitée au réseau local. L'autorité seule apporterait déjà l'essentiel ; OpenBao ajoute l'émission automatique, la durée courte et l'audit. |
| Tous | — | **Audit device** : chaque lecture et écriture journalisée (identité, chemin, date, jamais la valeur) | **Fort** : en rotation d'urgence, savoir quels secrets ont été lus et par qui, donc quoi renouveler en premier. |

OpenBao ne remplace pas KeePassXC : la clé de déverrouillage, les mots de passe des bots et le mot de passe admin d'OpenBao restent des secrets humains.

---

## 3. Compatibilités (état au 2026-11-17)

| Point | Constat | Source | À faire |
| --- | --- | --- | --- |
| Version | Ligne 2.7 (dernière : 2.7.3 du 2026-11-19 ; prototype en 2.7.2). Les seals KMS (AWS, GCP…) sont devenus des plugins externes en 2.7 ; le seal **static** (clé fournie par la configuration) existe depuis 2.4 | Notes de version OpenBao 2.7.0, docs du seal static, Docker Hub `openbao/openbao` | Épingler l'image par digest (invariant du projet), suivi par Renovate |
| Cosign | **Vérifié** avec la version des agents (`Dockerfile.agent`) : `openbao://` (variables `BAO_ADDR`/`BAO_TOKEN`) et `hashivault://` (`VAULT_*`) fonctionnent ; montage Transit non standard par `TRANSIT_SECRET_ENGINE_PATH` ; mêmes options sans Rekor que `Jenkinsfile-CI` | Docs KMS de Sigstore, étape 0 (§7.1) | — |
| External Secrets Operator | Pas de fournisseur OpenBao dédié : le fournisseur Vault fonctionne (API compatible) ; ESO 2.7 ajoute des options propres à OpenBao (namespaces, CA) | Notes de version ESO 2.7.0, guides NVIDIA et Kubermatic | Authentification Kubernetes, KV v2 |
| Plugin Jenkins HashiCorp Vault | **Vérifié** (version 384.vda_86ec66c537, cœur Jenkins 2.479.3 minimum) : AppRole, KV v2, `withVault` et credential « Vault Secret Text » lu par `withCredentials`, valeurs masquées dans la console | Étape 0 (§7.1) | Suivre ses avis de sécurité : six depuis 2022, tous corrigés |
| PostgreSQL | Moteur database : rôles dynamiques, rôles **statiques** (utilisateur existant, mot de passe renouvelé selon une période), rotation des identifiants racine, hachage `scram-sha-256` | Docs OpenBao du moteur database et du plugin PostgreSQL | Non retenu (§8) : OpenBao, hors du cluster, ne joint pas PostgreSQL sans l'exposer |
| Kubernetes (moteur de tokens) | **Vérifié** : moteur intégré à l'image (`bao plugin list`), émission de tokens pour un compte de service existant | Étape 0 (§7.1) | Mode « compte de service existant » seulement (§7.1) |
| Helm | Chart officiel (`openbao.github.io/openbao-helm`, aussi en OCI sur ghcr.io), injecteur d'agent et fournisseur CSI | Docs OpenBao Kubernetes | Non utilisé dans l'architecture retenue (§4) |

---

## 4. Architecture proposée

### 4.1 Où faire tourner OpenBao

| Option | Pour | Contre |
| --- | --- | --- |
| **A. Conteneur dans `infra/jenkins-docker`** (recommandée) | Cycle de vie indépendant du cluster KinD, souvent recréé ; sert la CI dès l'étape 1 ; même schéma que `kind-registry`, raccordé au réseau `kind` par `repair-cluster-after-restart.sh` | Hors des NetworkPolicies Kubernetes : protection par le réseau Docker et la liaison à `127.0.0.1` |
| B. Dans le cluster (chart Helm) | Outils Kubernetes natifs (injecteur, CSI) | Perdu à chaque recréation du cluster, ce qui oblige à restaurer et redéverrouiller ; la CI dépendrait de stagingkub |

Configuration de l'option A :

- image officielle épinglée par digest ; port `8200` publié sur `127.0.0.1` seulement (même raison que Jenkins : les règles iptables de Docker passent avant ufw) ; TLS avec un certificat émis par l'autorité locale créée à l'étape 1 (§4.3) ;
- stockage intégré (**Raft**, un seul nœud) sur un volume nommé ;
- **audit device** fichier sur un volume dédié, rotation des journaux ;
- consommation mémoire mesurée à l'étape 0 : 26 à 27 Mo après les tests (Raft, audit, Transit, KV, AppRole, kubernetes actifs), négligeable même avec la marge d'environ 2 Go du poste quand la CI et stagingkub tournent ensemble.

### 4.2 Identités et politiques

| Client | Méthode d'authentification | Droits (politique) |
| --- | --- | --- |
| Jenkins (pipelines) | **AppRole** : `role_id` et `secret_id` dans un credential « Vault App Role » du plugin (le seul secret restant dans Jenkins), qui ouvre une session à chaque lecture | Lecture des chemins KV des pipelines, `sign` sur la clé Transit Cosign |
| ESO (stagingkub) | **Kubernetes** : OpenBao valide le token du compte de service d'ESO auprès de l'API du cluster | Lecture de `kv/stagingkub/*` |
| Administrateur | Utilisateur dédié, token de courte durée | Écriture KV, gestion des rôles ; le token root est révoqué après l'installation (`bao operator generate-root` pour le régénérer) |
| fixcve-auto (poller du cron) | **AppRole** `fixcve` : `role_id` et `secret_id` dans `~/.config/rhdemo-fixcve/` (mode 600), connexion par `curl` | Lecture de `kv/data/fixcve/*` uniquement |
| `rotate-secrets.py` | Token administrateur demandé au lancement | Écriture des chemins des secrets qu'il renouvelle, dont les mots de passe PostgreSQL de `kv/stagingkub/*` (étape 4) |

Dans le namespace `rhdemo-stagingkub`, rien ne change : les pods lisent toujours des Secrets Kubernetes, créés par ESO au lieu d'un script. Le Default Deny reste intact. Seul le contrôleur ESO, dans son propre namespace, reçoit une règle de sortie vers OpenBao.

### 4.3 Autorité locale et certificats TLS

Il n'existe aujourd'hui aucune autorité locale : chaque certificat est auto-signé et approuvé pour lui-même (§1). Or OpenBao a besoin d'un certificat dès l'étape 1. Proposition en deux temps :

- **Étape 1** : créer une autorité locale. Racine hors ligne (clé gardée dans KeePassXC, jamais sur le poste en dehors de la cérémonie de signature), qui signe une autorité intermédiaire. Au départ, l'intermédiaire peut être un simple `openssl` ; il passe dans le moteur PKI d'OpenBao à l'étape 5. Le certificat d'OpenBao lui-même (environ un an) est émis par cette autorité, jamais par OpenBao : il doit rester valide même si OpenBao reste scellé.
- **Étape 5 (option)** : moteur PKI avec l'intermédiaire, et émission par certificat :

| Certificat | Émission | Durée |
| --- | --- | --- |
| `shared-tls-cert` (Gateway) | cert-manager, émetteur Vault (compatible OpenBao, *à vérifier*), authentification Kubernetes comme ESO ; ressource `Certificate` à la place du `kubectl create secret tls` | 30 à 90 jours, renouvelé aux deux tiers |
| Registry | Script de renouvellement (`registry:3` ne relit son certificat qu'au redémarrage) | Environ un an |
| OpenBao | Autorité hors OpenBao (voir ci-dessus) | Environ un an |
| Nginx ephemere | Inchangé (auto-signé, jetable) ; émission au début de la CI possible, Jenkins accédant à OpenBao | 365 jours |

Distribution de l'autorité, à la place des copies actuelles du certificat du registry : `/etc/docker/certs.d` de l'hôte, nœud KinD et configuration containerd (`init-stagingkub.sh`), montages des agents (`jenkins-casc.yaml`), truststore Java du contrôleur Jenkins, navigateurs (importée une fois). Le logout OIDC, noté non fonctionnel en auto-signé dans `CERTIFICATS_WEB.md`, est peut-être réglé si sa cause est la confiance du certificat côté backend : *à vérifier*.

---

## 5. Déverrouillage : le vrai coût

Au démarrage, OpenBao est **scellé** : il ne peut rien déchiffrer tant qu'on ne lui fournit pas la clé de déverrouillage. Tant que c'est le cas, la CI et les synchronisations ESO échouent.

| Mode | Fonctionnement | Évaluation pour RHDemo |
| --- | --- | --- |
| **Shamir, clé collée à la main** (retenu) | Une part, seuil 1, gardée dans KeePassXC avec une copie papier. Après chaque démarrage, `bao operator unseal` lancé sans argument demande la clé en saisie masquée ; on la colle depuis KeePassXC | Une action par démarrage du poste, du démon Docker ou du conteneur. Aucun fichier ni outil supplémentaire ; la clé n'est jamais sur le disque du poste en dehors de la base KeePassXC, ni dans les arguments d'une commande. Passage bref par le presse-papiers, vidé par KeePassXC (§5.1). |
| Seal static | La clé est dans la configuration, donc sur le disque | Équivaut à la clé AGE actuelle sur le disque ; ne protège que contre le vol d'une sauvegarde. La documentation demande d'en évaluer soigneusement l'usage. |
| Seal KMS ou Transit | Clé confiée à un KMS externe ou à un autre OpenBao | Pas de KMS disponible sur un poste unique ; un KMS cloud contredit l'indépendance vis-à-vis des SaaS, et un second OpenBao devrait lui-même être déverrouillé. |

**Pas de déverrouillage entièrement automatique sans affaiblir la protection** : sur un poste unique, toute solution automatique (seal static, TPM, clé matérielle PKCS#11 branchée en permanence) met la clé, ou de quoi l'utiliser, à la portée de quiconque contrôle le poste. Seule la saisie humaine protège aussi le poste à l'arrêt et ses sauvegardes. Une mise à jour Renovate de l'image OpenBao ne scelle rien par elle-même : elle ne modifie que le digest dans `infra/jenkins-docker/docker-compose.yml`, et le conteneur n'est recréé qu'au `docker compose up` manuel, donc en présence de l'utilisateur.

**Racine de confiance** : la clé de déverrouillage remplace la clé AGE. Sa perte rend les données irrécupérables, y compris les instantanés Raft (`bao operator raft snapshot save`), qui restent chiffrés. Il faut donc deux copies hors du poste : KeePassXC synchronisé et papier.

### 5.1 Choix du mode de saisie

Le Secret Service de KeePassXC, envisagé au départ, n'est pas utilisable sur le poste : le service D-Bus est déjà fourni par le trousseau GNOME, et KeePassXC est installé en snap. Options examinées :

| Option | Évaluation |
| --- | --- |
| **Copier-coller depuis KeePassXC** (retenu) | Aucun outil ni fichier supplémentaire, aucun script n'accède à la base personnelle. Fréquence acceptable (redémarrages du poste, du démon Docker ou du conteneur). Non intégrable à `repair-cluster-after-restart.sh`, qui peut seulement signaler l'état scellé. |
| `age -p` | Alternative scriptable : fichier dédié à la seule clé, chiffré par phrase de passe (scrypt), puis `age -d … \| jq -Rc '{key: .}' \| curl --cacert … -X PUT --data @- …/v1/sys/unseal`. Écarté pour l'instant : ajoute un fichier chiffré sur le disque, exposé à des essais hors ligne, et une phrase de passe à retenir, pour un gain de confort faible. |
| `keepassxc.cli` sur la base personnelle | Fonctionne sans Secret Service, mais expose au script une base qui contient beaucoup d'autres secrets. Le snap n'accède pas aux dossiers cachés du home. |
| Base kdbx dédiée à la clé | Équivalente à `age -p`. Seul apport : un second facteur (fichier clé, YubiKey), au prix de `keepassxc.cli` et de l'interface `raw-usb` du snap. |
| Trousseau GNOME (`secret-tool`) | Écarté : déverrouillé à l'ouverture de session, la clé serait lisible sans confirmation par tout processus de l'utilisateur. |
| Clé scellée par le TPM (`systemd-creds --with-key=tpm2`) | Écarté : déverrouillage automatique, équivalent au seal static face à une compromission locale. |

Règles :

- **Ne jamais passer la clé en argument** (`bao operator unseal <clé>`) : elle serait visible dans `ps`. Lancer la commande sans argument, par exemple `docker exec -it <conteneur> bao operator unseal`.
- **Token root** : révoqué après l'installation, régénéré au besoin par `bao operator generate-root`, qui demande la clé de déverrouillage.

---

## 6. Impact sur l'existant

- **Invariant de sécurité** (CLAUDE.md) : « Secrets : jamais en clair dans Git, uniquement chiffrés par SOPS » deviendrait « référencés dans OpenBao, ou chiffrés par SOPS pendant la transition ». Entrée à ajouter dans `DECISIONS.md`.
- **SOPS** : retiré par étapes, fichier par fichier. `SOPS_SETUP.md` passe en historique à la fin de la migration. Les anciens fichiers chiffrés restent dans l'historique Git : leurs valeurs doivent avoir changé avant que la clé AGE soit abandonnée (même règle que le §1.3 de l'étude de rotation).
- **fixcve-auto** : `fixcve-auto-poll.sh` lit ses credentials dans OpenBao au lieu de `sops -d`, `fixcve-install.sh` les écrit dans le KV ; `FIXCVE_AUTO.md` est à mettre à jour. Tant que cette migration n'est pas faite, la clé AGE ne peut pas être abandonnée.
- **`rotate-secrets.py`** : conservé pour les secrets exposés sur Internet ; nouvelle cible `{kind: openbao, path: …}` dans l'inventaire, à la place des credentials Jenkins migrés.
- **Étude de rotation** : les phases 2 (Kubernetes, Cosign, stagingkub) et 4 (tokens à durée limitée) seraient remplacées par les étapes 2 à 4 ci-dessous.
- **Pipelines** : changement minimal. Un credential Jenkins de type « Vault Secret Text » portant le même identifiant remplace l'ancien, et les blocs `withCredentials` existants restent inchangés (vérifié à l'étape 0). `withVault` reste possible pour les lectures groupées. `PIPELINES_CI_CD.md` est à mettre à jour.

---

## 7. Plan par étapes

Chaque étape est réversible et utilisable seule. Les credentials Jenkins et les fichiers SOPS ne sont retirés qu'après une CI verte avec la nouvelle source.

| Étape | Contenu | Critère de sortie | Effort |
| --- | --- | --- | --- |
| 0 ✅ | Prototype jetable : OpenBao en conteneur, tests des points *à vérifier* (plugin Jenkins, cosign `openbao://` avec la version des agents, moteur kubernetes), mesure mémoire | Décision de continuer ou d'abandonner, consignée dans cette étude : **continuer** (§7.1) | 0,5 jour, fait le 2026-11-20 |
| 1 | Autorité locale (§4.3) ; OpenBao dans `jenkins-docker` (Raft, TLS, audit), procédure de déverrouillage manuel (§5.1), KV v2 ; migration des secrets des pipelines Renovate et des notifications ; cible `openbao` dans `rotate-secrets.py` | Un cycle CI et Renovate vert sans les credentials migrés, lectures visibles dans le journal d'audit | 1,5 jour |
| 1 bis | Credentials de fixcve-auto dans `kv/fixcve/*`, AppRole `fixcve` ; poller et script d'installation adaptés ; cible `openbao` à la place de `sops` pour `fixcve-forgejo-token` dans l'inventaire, procédure manuelle de `jenkins-claude-account` mise à jour | Un cycle fixcve-auto complet sans `credentials.sops.yaml` ; lectures visibles dans le journal d'audit. Dernière condition, avec l'étape 3, pour abandonner la clé AGE | 0,5 jour |
| 2 | Cosign par Transit : signature `openbao://cosign` dans `Jenkinsfile-CI`, clé publique exportée pour `Jenkinsfile-CD` ; ancienne clé publique conservée tant que des images signées avec elle restent déployables | CD vert sur une image signée par Transit, credentials `cosign-private-key` et `cosign-password` supprimés | 1 jour |
| 3 | ESO dans stagingkub, `ExternalSecret` à la place des `kubectl create secret` de `init-stagingkub.sh` ; NetworkPolicy de sortie d'ESO vers OpenBao | Recréation complète de stagingkub sans `secrets-stagingkub.yml` | 1 jour |
| 4 | Rotation des mots de passe PostgreSQL (bases rhdemo et Keycloak) par `rotate-secrets.py` : écriture dans `kv/stagingkub/*`, synchronisation ESO forcée, `ALTER ROLE` par `kubectl exec`, `rollout restart` (Spring Boot et Keycloak lisent le mot de passe au démarrage) | Mot de passe renouvelé en une commande, application et Keycloak reconnectés, aucun flux réseau nouveau | 1 jour |
| 5 (option) | PKI : intermédiaire dans OpenBao, cert-manager et `shared-tls-cert` à durée courte, certificat du registry émis par l'autorité (§4.3) ; tokens Kubernetes à courte durée | `shared-tls-cert` renouvelé par cert-manager, registry joint par l'hôte, le nœud KinD et les agents avec l'autorité seule | 2 jours |

Total : environ 6,5 jours, étape 0 comprise (6 jours restants).

L'étape 1 bis ne dépend que de l'étape 1 et peut être faite à tout moment après elle. Elle est peu urgente (le fichier n'est pas dans Git) mais nécessaire pour retirer SOPS et la clé AGE.

### 7.1 Résultats de l'étape 0 (2026-11-20)

Prototype entièrement jetable, supprimé après les tests : OpenBao 2.7.2 (image officielle par digest) en mode serveur, Raft sur un seul nœud, Shamir 1 part, audit fichier ; registry `registry:3` éphémère ; Jenkins `2.580.2-lts-jdk25` jetable avec le plugin ; cluster KinD jetable (`kindest/node` de stagingkub). Aucun environnement du projet (Jenkins, `kind-registry`, cluster `rhdemo`) n'a été modifié.

| Test | Résultat |
| --- | --- |
| Cosign 3.1.4 (image `rhdemo-jenkins-agent`), clé Transit `ecdsa-p256` non exportable, montage `cosign-transit` | Signature OK par `openbao://cosign` et par `hashivault://cosign`. Les options de `Jenkinsfile-CI` (`--use-signing-config=false --tlog-upload=false`) sont nécessaires : `--tlog-upload=false` seul est refusé par cosign 3.x. |
| Politique de signature minimale (`update` sur `sign/cosign`, `read` sur `keys/cosign`), token de 15 min | Suffit pour signer et exporter la clé publique (`cosign public-key --key openbao://cosign`). Lecture de `export/signing-key` refusée. |
| Vérification sans accès à OpenBao, comme `Jenkinsfile-CD` | OK avec la clé publique exportée ; échec attendu avec une autre clé. |
| Rotation de la clé Transit | `public-key` renvoie ensuite la nouvelle version ; les signatures antérieures restent vérifiables avec l'ancienne clé publique. Confirme le plan de l'étape 2 (conserver l'ancienne clé publique dans la CD). |
| Plugin Jenkins, AppRole (politique en lecture sur `kv/data/jenkins/*`), KV v2 | `withVault` et `withCredentials` sur un credential « Vault Secret Text » lisent la valeur, masquée (`****`) dans la console. |
| Journal d'audit | Chaque connexion AppRole et lecture KV ou signature Transit est tracée : chemin, opération, politiques, adresse IP. Les valeurs (secret lu, condensé signé) sont remplacées par un HMAC. |
| Moteur kubernetes, rôle sur un compte de service existant, compte d'OpenBao limité à `create` sur `serviceaccounts/token` de ce seul compte | Token de 10 min émis, droits du compte respectés (accès aux Secrets refusé). En revanche, la révocation du bail OpenBao **n'invalide pas** le token, qui reste valide jusqu'à son expiration. |
| Mémoire | 26 à 27 Mo pour OpenBao, données Raft de 152 Ko. |

Conséquences sur l'étude :

- **Moteur kubernetes** : la révocation effective impose le mode où OpenBao crée lui-même un compte de service et ses rôles à chaque demande. OpenBao aurait alors besoin du droit de créer des `Role` et `RoleBinding`, soit un risque d'escalade de privilèges contraire au moindre privilège du RBAC Jenkins. On garde le mode « compte existant » avec une durée courte (15 min). L'étape 5 reste optionnelle.
- **`secret_id` AppRole** : le plugin ne le renouvelle pas et ouvre une session à chaque lecture. Une durée de validité courte impose donc de remplacer régulièrement le credential Jenkins, tâche à confier à `rotate-secrets.py` (§8).
- **Mémoire** : le risque du §8 est levé.

### 7.2 Guide de reprise : acquis et points à traiter par étape

Ce guide permet de reprendre les étapes 1 à 5 sans refaire le prototype. **Acquis** : vérifié à l'étape 0, réutilisable tel quel. **À traiter** : non couvert par le prototype, à concevoir ou tester pendant l'étape.

**Socle commun (étape 1)**

- Acquis, serveur : `bao server -config=…` avec un bloc `storage "raft"` (`path`, `node_id`), `api_addr` et `cluster_addr`, `disable_mlock = true`. Le bloc `audit "file"` déclaré dans le fichier HCL est actif dès le démarrage (`bao audit list`). L'image tourne avec l'uid 100 et le gid 1000, qui doivent pouvoir écrire dans les répertoires de données et de journaux.
- Acquis, initialisation : `bao operator init -key-shares=1 -key-threshold=1 -format=json`, puis `bao operator unseal <clé>` (en exploitation, lancer la commande sans argument : la clé passée en argument est visible dans `ps`, §5.1). La clé de déverrouillage et le token root vont dans KeePassXC. En administration locale, utiliser `docker exec -e BAO_ADDR=… -e BAO_TOKEN=… <conteneur> bao …`.
- Acquis, AppRole Jenkins : `auth enable approle`, rôle avec `token_policies`, `token_ttl` et `secret_id_ttl`, politique `read` sur `kv/data/jenkins/*` (KV v2 monté sur `kv/` : le chemin de la politique contient `data/`).
- Acquis, plugin Jenkins par JCasC : credential `vaultAppRoleCredential` (`path: approle`, `roleId`, `secretId`), credential `vaultStringCredentialImpl` (`path`, `vaultKey`, `engineVersion: 2`) qui garde l'identifiant de l'ancien credential, et bloc `unclassified.hashicorpVault.configuration` (`vaultUrl`, `vaultCredentialId`, `engineVersion: 2`). Ajouter `hashicorp-vault-plugin` épinglé dans `infra/jenkins-docker/plugins.txt`.
- À traiter, TLS : le prototype tournait en HTTP. Il faut d'abord créer l'autorité locale (§4.3 : racine hors ligne, intermédiaire), puis un certificat d'environ un an signé par elle, avec dans le SAN les noms utilisés par Jenkins, les agents et le cluster. Les agents font déjà confiance au registry par un fichier monté (`jenkins-casc.yaml`, `mountsString`) : y monter le certificat de l'autorité ; cosign recevra `BAO_CACERT` ou `SSL_CERT_FILE`. Le **contrôleur** Jenkins, lui, ne fait aujourd'hui confiance à aucune autorité locale. Or c'est probablement lui qui exécute les lectures du plugin (à confirmer) : il faut alors ajouter l'autorité au truststore Java dans `Dockerfile.jenkins`. Ne pas utiliser l'option du plugin qui désactive la vérification TLS.
- À traiter, réseaux : rattacher OpenBao à `rhdemo-jenkins-network` dans le `docker-compose.yml` et, pour l'étape 3, au réseau `kind`, comme `kind-registry` (raccordement non persistant, à ajouter dans `repair-cluster-after-restart.sh`).
- À traiter, déverrouillage (§5.1) : documenter la procédure (`docker exec -it <conteneur> bao operator unseal`, clé collée depuis KeePassXC). Le conteneur redémarre scellé (`restart: unless-stopped`). Faire signaler l'état scellé par `repair-cluster-after-restart.sh` (`GET /v1/sys/seal-status`) et par le healthcheck (§8).
- À traiter, `rotate-secrets.py` : nouvelle cible `{kind: openbao, path: …, key: …}` dans `secrets/inventory.yaml`, et un module dans `scripts/rotation_lib/` qui écrit par l'API KV v2 (`POST /v1/kv/data/<chemin>`). Ajouter le `secret_id` AppRole à l'inventaire avec une cible `jenkins`.

**Étape 1 bis (fixcve-auto)**

- Acquis : AppRole et KV v2 (socle de l'étape 1). Le poller n'a pas besoin du client `bao` : `curl` (déjà requis) suffit pour `POST /v1/auth/approle/login` puis `GET /v1/kv/data/fixcve/<secret>`. Les valeurs restent en mémoire, comme avec `sops -d`.
- À traiter, OpenBao scellé ou injoignable : le poller écrit une ligne dans `poll.log` et saute le passage, comme pour un Jenkins injoignable. Pas de dépendance nouvelle en pratique : OpenBao tourne dans `jenkins-docker`, sans lequel fixcve-auto n'a rien à faire.
- À traiter, secret de départ : `role_id` et `secret_id` restent sur le disque, lisibles par l'utilisateur du cron, comme la clé AGE aujourd'hui, mais avec une portée limitée à `kv/fixcve/*` et révocables. Lier le `secret_id` à l'adresse locale (`secret_id_bound_cidrs`, `token_bound_cidrs`) le rendrait inutilisable hors du poste. À vérifier : selon le proxy de Docker, OpenBao voit `127.0.0.1` ou l'adresse de la passerelle du réseau Docker.
- À traiter : `curl --cacert` avec l'autorité locale (TLS de l'étape 1) ; renouvellement du `secret_id` par `rotate-secrets.py` (même sujet que pour Jenkins, §7.1). Le skill interactif `/fixcve` n'est pas concerné : il reçoit `JENKINS_USER` et `JENKINS_TOKEN` en variables d'environnement et ne lit pas ce fichier.

**Étape 2 (Cosign)**

- Acquis : une clé Transit `type=ecdsa-p256`, non exportable par défaut, sur un montage dédié (`cosign-transit`). Politique de signature : `update` sur `cosign-transit/sign/cosign` **et** `cosign-transit/sign/cosign/*` (cosign appelle `sign/cosign/sha2-256`), `read` sur `cosign-transit/keys/cosign`. Variables : `BAO_ADDR`, `BAO_TOKEN`, `TRANSIT_SECRET_ENGINE_PATH=cosign-transit`. Clé `openbao://cosign`, mêmes options que l'actuel `Jenkinsfile-CI`. Clé publique par `cosign public-key --key openbao://cosign`.
- À traiter, token de signature : le plugin Jenkins ne transmet pas son token OpenBao au pipeline. Le stage de signature doit donc obtenir lui-même un token court : un second AppRole « cosign » dont `role_id` et `secret_id` sont dans un credential Jenkins, connexion par `curl` sur `/v1/auth/approle/login` dans l'agent, puis `BAO_TOKEN` exporté pour cosign seulement. Non testé, mais il s'agit d'appels d'API standards.
- À traiter, vérification dans la CD : `Jenkinsfile-CD` lit une seule clé publique (credential fichier `cosign-public-key`) et `cosign verify` n'accepte qu'un `--key`. Tant que des images signées par l'ancienne clé restent déployables, il faut essayer successivement l'ancienne et la nouvelle clé. Même logique à chaque rotation de la clé Transit.

**Étape 3 (ESO)**

- Acquis : OpenBao, rattaché au réseau `kind`, joint l'API du cluster à `https://<cluster>-control-plane:6443`, avec l'autorité extraite du kubeconfig.
- À traiter, authentification Kubernetes : OpenBao, hors du cluster, ne dispose pas du token monté dans un pod. Deux options : un token permanent de relecture (`token_reviewer_jwt`), ou l'utilisation du JWT du client (ESO), qui demande `system:auth-delegator` sur le compte d'ESO. Non testé.
- À traiter, flux ESO vers OpenBao : NetworkPolicy de sortie vers l'IP du conteneur OpenBao sur le réseau `kind`. Il faut une IP fixe (`docker network connect --ip`) et une règle `ipBlock`. Avec Cilium, `ipBlock` ne fonctionne pas vers l'hôte (`infra/stagingkub/networkpolicies/README.md`), mais OpenBao est un conteneur distinct : à tester. Il faut aussi vérifier la résolution DNS du nom du conteneur depuis les pods (sinon, utiliser l'IP) et l'accord du nom avec le SAN du certificat.
- À traiter : installer ESO sur le modèle de `infra/stagingkub/scripts/components/install-or-upgrade-*.sh`, image épinglée par digest. Remplacer les `kubectl create secret` de `init-stagingkub.sh` (Secrets `rhdemo-db-secret`, `keycloak-db-secret`, `keycloak-admin-secret`, `rhdemo-app-secrets` ; `shared-tls-cert` relève de l'étape 5).

**Étape 4 (PostgreSQL)**

- Décidé (§8) : pas de moteur database. Rotation par `rotate-secrets.py`, depuis le poste, avec le kubeconfig de l'utilisateur.
- À traiter, ordre des opérations : (1) nouveau mot de passe écrit dans le KV ; (2) synchronisation ESO forcée (annotation `force-sync` de l'`ExternalSecret`) et attente du Secret à jour ; (3) `ALTER ROLE … PASSWORD` par `kubectl exec` dans le pod PostgreSQL, le mot de passe passé par l'entrée standard de `psql` et non en argument ; (4) `kubectl rollout restart` des Deployments concernés. PostgreSQL ne coupe pas les connexions ouvertes lors d'un changement de mot de passe : seules les nouvelles connexions entre (3) et (4) peuvent échouer.
- À traiter : nouveau type de rotation dans `scripts/rotation_lib/` et entrées de l'inventaire (cible `openbao`) pour les mots de passe rhdemo et Keycloak ; tests avec de faux OpenBao et `kubectl`, comme `scripts/tests/test_rotation.py`.

**Étape 5 (option)**

- À traiter, PKI (§4.3) : monter le moteur PKI, y importer l'intermédiaire signé par la racine hors ligne, un rôle par usage (Gateway, registry) limité aux noms autorisés. Installer cert-manager sur le modèle de `infra/stagingkub/scripts/components/install-or-upgrade-*.sh`, image épinglée par digest ; émetteur Vault avec l'authentification Kubernetes de l'étape 3 ; NetworkPolicy de sortie de cert-manager vers OpenBao (mêmes contraintes que pour ESO : IP fixe, `ipBlock` avec Cilium). Réécrire `init-registry-certs.sh` et la partie certificats de `init-stagingkub.sh` ; inventaire #18 : rotation automatique pour le Gateway. Mettre à jour `CERTIFICATS_WEB.md`.
- Acquis, moteur kubernetes : `kubernetes/config` (`kubernetes_host`, `kubernetes_ca_cert`, `service_account_jwt`, `disable_local_ca_jwt=true`), rôle avec `service_account_name` et `allowed_kubernetes_namespaces`, demande par `kubernetes/creds/<rôle>` avec `kubernetes_namespace` et `ttl`. Compte d'OpenBao limité à `create` sur `serviceaccounts/token` avec `resourceNames` restreint au compte visé.
- À traiter : le prototype fournissait à OpenBao un JWT d'une heure. En exploitation, son compte a besoin d'un token durable (Secret `kubernetes.io/service-account-token`), stocké dans OpenBao. Côté Jenkins, le kubeconfig doit être construit au moment du build à partir du token obtenu.

---

## 8. Risques et points ouverts

- **Point unique de défaillance** : OpenBao arrêté ou scellé bloque CI, CD et synchronisations. À mitiger avec un healthcheck qui distingue l'état scellé, une alerte dans Grafana et une procédure de déverrouillage documentée. Le déverrouillage reste manuel (§5).
- **Sauvegarde** : instantané Raft régulier, à restaurer pour test au moins une fois ; sans la clé de déverrouillage, il ne sert à rien.
- **Bootstrap** : le `secret_id` AppRole de Jenkins devient le secret le plus sensible de Jenkins. Il faut lui donner une durée courte et le renouveler par `rotate-secrets.py`.
- **Expiration des certificats courts** : OpenBao scellé longtemps (absence prolongée) empêche les renouvellements. Une durée de 30 à 90 jours, renouvelée aux deux tiers, laisse de la marge ; le certificat d'OpenBao ne dépend pas d'OpenBao (§4.3).
- **Mémoire** : levé, moins de 30 Mo mesurés à l'étape 0 (§7.1).
- **Accès d'OpenBao à PostgreSQL** : décidé, pas de moteur database. Hors du cluster, OpenBao ne joindrait les bases qu'en exposant PostgreSQL (NodePort sur le réseau `kind`), soit un flux entrant vers la base. Une rotation par CronJob dans le cluster demanderait les identifiants d'administration PostgreSQL dans le namespace, une sortie vers OpenBao et le droit de `patch` sur les Deployments ; OpenBao dans le cluster est écarté au §4.1. La rotation est donc confiée à `rotate-secrets.py` (étape 4) : à la demande et non plus automatique, sans flux ni droit nouveau dans le cluster. Une rotation automatique ne justifie pas ces ouvertures pour des bases joignables seulement depuis leur namespace, derrière le Default Deny.
- **Plugin Jenkins** : six avis de sécurité depuis 2022 (tous corrigés), dont une exposition de credentials Vault de portée système en 2025. Garder le plugin à jour.
- **Complexité pédagogique** : bénéfice réel pour une preuve de concept DevSecOps (signature sans clé extractible, secrets hors de Git, audit), mais la documentation d'exploitation (déverrouillage, sauvegarde, restauration) devient indispensable.

## 9. Recommandation

L'étape 0 est concluante (§7.1) : **continuer**. Faire l'étape 1, prérequis, puis enchaîner les étapes 2 (Cosign) et 3 (ESO), qui apportent le plus. L'étape 1 bis (fixcve-auto) peut attendre, mais la clé AGE ne disparaît qu'une fois les étapes 1 bis et 3 terminées. Ne pas poursuivre la phase 2 de l'étude de rotation pour Cosign et les secrets stagingkub tant que cette décision n'est pas prise, pour ne pas coder deux fois.

## Sources

- OpenBao : [notes de version 2.7.0](https://openbao.org/community/release-notes/2-7-0/), [seal static](https://openbao.org/docs/configuration/seal/static/), [moteur database](https://openbao.org/docs/secrets/databases/), [plugin PostgreSQL](https://openbao.org/docs/secrets/databases/postgresql/), [Helm](https://openbao.org/docs/platform/k8s/helm/)
- Sigstore : [support KMS de cosign](https://docs.sigstore.dev/cosign/kms_support), [signature souveraine avec OpenBao et cosign](https://control-plane.io/posts/sovereign-signing-openbao-cosign-flux/)
- External Secrets Operator : [version 2.7.0](https://newreleases.io/project/artifacthub/helm/external-secrets-operator/external-secrets/release/2.7.0), [guide ESO avec OpenBao](https://docs.nvidia.com/mission-control/docs/nmc-software-installation-guide/2.5.0/gitops-components/external-secrets.html)
- Jenkins : [plugin HashiCorp Vault](https://plugins.jenkins.io/hashicorp-vault-plugin) (avis de sécurité listés sur la page)
- Prototype de l'étape 0 (2026-11-20) : §7.1
