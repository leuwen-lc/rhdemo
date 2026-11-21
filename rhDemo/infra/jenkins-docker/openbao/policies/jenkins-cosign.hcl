# Stage de signature de Jenkinsfile-CI (AppRole « jenkins-cosign ») : utiliser la clé
# Transit sans jamais pouvoir l'exporter (ETUDE_OPENBAO.md §7.1). cosign appelle
# sign/cosign/sha2-256, d'où le chemin avec suffixe.
path "cosign-transit/sign/cosign" {
  capabilities = ["update"]
}
path "cosign-transit/sign/cosign/*" {
  capabilities = ["update"]
}
path "cosign-transit/keys/cosign" {
  capabilities = ["read"]
}
