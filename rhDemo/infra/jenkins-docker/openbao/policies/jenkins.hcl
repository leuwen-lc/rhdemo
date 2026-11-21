# Contrôleur Jenkins (plugin HashiCorp Vault, AppRole « jenkins ») :
# lecture des secrets des pipelines, rien d'autre.
path "kv/data/jenkins/*" {
  capabilities = ["read"]
}
