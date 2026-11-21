# Administrateur (utilisateur userpass « admin », jeton d'une heure) : remplace le
# jeton root, révoqué après l'installation. Utilisé par configure-openbao.sh,
# rotate-secrets.py et openbao-migrate.py. Pas d'accès à sys/raw ni au déscellement.

# Secrets KV (lecture, écriture, métadonnées, versions)
path "kv/*" {
  capabilities = ["create", "read", "update", "patch", "delete", "list"]
}

# Moteurs, méthodes d'authentification, politiques
path "sys/mounts" {
  capabilities = ["read", "list"]
}
path "sys/mounts/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
path "sys/auth" {
  capabilities = ["read", "list"]
}
path "sys/auth/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
path "sys/policies/acl/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "auth/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Transit : gestion de la clé Cosign (création, rotation, lecture de la clé publique).
# Pas d'export : la clé est créée non exportable.
path "cosign-transit/keys/*" {
  capabilities = ["create", "read", "update", "list"]
}

# Consultation de l'audit et sauvegarde Raft
path "sys/audit" {
  capabilities = ["read", "list", "sudo"]
}
path "sys/storage/raft/snapshot" {
  capabilities = ["read"]
}
