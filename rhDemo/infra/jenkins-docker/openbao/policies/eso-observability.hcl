# External Secrets Operator dans le namespace loki-stack de stagingkub (authentification
# Kubernetes, rôle « eso-observability ») : mot de passe admin de Grafana seulement. Distinct
# de eso-stagingkub : une compromission de loki-stack ne donne pas les secrets applicatifs.
path "kv/data/observability/*" {
  capabilities = ["read"]
}
