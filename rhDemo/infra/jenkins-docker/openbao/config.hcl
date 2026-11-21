# Configuration du serveur OpenBao de RHDemo (docs/OPENBAO.md, ETUDE_OPENBAO.md §4).
# Un seul nœud, stockage Raft, TLS obligatoire, journal d'audit fichier.
# Monté en lecture seule par docker-compose.yml, hors de /openbao/config : l'entrypoint
# de l'image ferait un chown -R de ce dossier s'il était monté depuis le dépôt.

ui            = false
disable_mlock = true   # recommandé avec le stockage Raft ; conteneur sans capacité IPC_LOCK (§7.2)

listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_cert_file = "/openbao/tls/openbao.crt"   # certificat + intermédiaire (init-local-ca.sh)
  tls_key_file  = "/openbao/tls/openbao.key"
  tls_min_version = "tls12"
}

storage "raft" {
  path    = "/openbao/file"   # volume nommé, appartient à l'utilisateur openbao de l'image
  node_id = "rhdemo-openbao-1"
}

api_addr     = "https://openbao:8200"
cluster_addr = "https://127.0.0.1:8201"

# Chaque requête est journalisée : identité, chemin, opération, politiques, adresse.
# Les valeurs (secret lu, condensé signé) sont remplacées par un HMAC.
audit "file" "fichier" {
  description = "Journal d'audit RHDemo"
  options {
    file_path = "/openbao/logs/audit.log"   # volume nommé dédié
  }
}
