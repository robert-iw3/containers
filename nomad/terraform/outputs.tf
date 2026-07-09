output "nomad_acl_token" {
  description = "Nomad ACL bootstrap token"
  value       = random_uuid.nomad_acl_token.result
  sensitive   = true
}

output "nomad_gossip_key" {
  description = "Nomad gossip encryption key"
  value       = random_uuid.nomad_gossip_key.result
  sensitive   = true
}

output "vault_token" {
  description = "Vault token for Nomad integration"
  value       = random_uuid.vault_token.result
  sensitive   = true
}
