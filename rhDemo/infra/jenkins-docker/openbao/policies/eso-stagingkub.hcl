# External Secrets Operator dans stagingkub (authentification Kubernetes, rôle
# « eso-stagingkub ») : lecture des secrets applicatifs de stagingkub.
path "kv/data/stagingkub/*" {
  capabilities = ["read"]
}
