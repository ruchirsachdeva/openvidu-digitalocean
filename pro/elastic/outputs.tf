output "openvidu_credentials" {
  description = "SSH to the instance to get the credentials. For more information, visit https://openvidu.io/latest/docs/self-hosting/elastic/digitalocean/install/#checking-credentials"
  value       = "SSH to the instance to get the credentials. For more information, visit https://openvidu.io/latest/docs/self-hosting/elastic/digitalocean/install/#checking-credentials"
}

output "master_public_ip" {
  description = "Reserved public IP assigned to the OpenVidu master node"
  value       = digitalocean_reserved_ip.master_public_ip.ip_address
}

output "master_private_ip" {
  description = "Private IP assigned to the current OpenVidu master node"
  value       = digitalocean_droplet.openvidu_master_node.ipv4_address_private
}

output "master_droplet_id" {
  description = "Immutable DigitalOcean ID of the current OpenVidu master node"
  value       = digitalocean_droplet.openvidu_master_node.id
}

output "openvidu_url" {
  description = "CourseUltra OpenVidu endpoint"
  value       = var.domainName == "" ? null : "https://${var.domainName}"
}

output "space_name" {
  description = "Private DigitalOcean Space containing OpenVidu cluster data and recordings"
  value       = var.spaceName == "" ? digitalocean_spaces_bucket.openvidu_space[0].name : var.spaceName
}

output "space_region" {
  description = "DigitalOcean region containing the OpenVidu Space"
  value       = var.spaceRegion
}

output "spaces_access_id" {
  description = "Bucket-scoped runtime Spaces access ID; persist it only through the secure handoff script"
  value       = digitalocean_spaces_key.openvidu_space_key.access_key
  sensitive   = true
}

output "spaces_secret_key" {
  description = "Bucket-scoped runtime Spaces secret; persist it only through the secure handoff script"
  value       = digitalocean_spaces_key.openvidu_space_key.secret_key
  sensitive   = true
}

output "ssh_private_key_openssh" {
  description = "Generated cluster SSH key; write it to a mode-0600 file and remove any legacy bootstrap copy from Spaces"
  value       = tls_private_key.openvidu_ssh_key.private_key_openssh
  sensitive   = true
}
