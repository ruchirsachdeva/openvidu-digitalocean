resource "aws_route53_record" "openvidu" {
  count = var.domainName == "" ? 0 : 1

  zone_id = var.route53ZoneId
  name    = var.domainName
  type    = "A"
  ttl     = 60
  records = [digitalocean_reserved_ip.master_public_ip.ip_address]

  lifecycle {
    precondition {
      condition     = var.route53ZoneId != ""
      error_message = "route53ZoneId is required when domainName is configured."
    }
  }
}
