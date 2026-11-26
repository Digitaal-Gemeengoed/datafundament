# OpenBao op dfw: de sleutel van de kluis (DF-ADR-015). Naar het voorbeeld van
# oa-uitrol/openbao. Luistert zonder TLS, alleen op het WireGuard-adres
# (WireGuard versleutelt). Voor productie: TLS en automatisch ontzegelen (HSM of KMS).

ui = false
disable_mlock = true

storage "raft" {
  path    = "/openbao/file"
  node_id = "df-kluis-1"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

api_addr     = "http://127.0.0.1:8200"
cluster_addr = "http://127.0.0.1:8201"

# Elke vraag om een HMAC in het auditlog (de invoer staat er gehasht in, niet als
# BSN). OpenBao 2 wil auditapparaten in de configuratie, niet via de API.
audit "file" "auditlog" {
  options {
    file_path = "/openbao/logs/audit.log"
  }
}
