# Wat de ingestie en het portaal mogen: alleen de HMAC van een BSN laten
# berekenen met de sleutel kluis-bsn. Niet de sleutel lezen, exporteren,
# roteren of verwijderen; geen andere sleutels of engines.

path "transit/hmac/kluis-bsn" {
  capabilities = ["update"]
}
path "transit/hmac/kluis-bsn/*" {
  capabilities = ["update"]
}
path "auth/token/renew-self" {
  capabilities = ["update"]
}
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
