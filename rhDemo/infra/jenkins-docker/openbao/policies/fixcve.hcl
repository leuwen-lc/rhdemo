# Poller de fixcve-auto (cron du poste, AppRole « fixcve ») : ses trois secrets seulement.
path "kv/data/fixcve/*" {
  capabilities = ["read"]
}
