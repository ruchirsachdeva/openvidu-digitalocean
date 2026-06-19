variable "doToken" {
  description = "Temporary DigitalOcean provisioning token used by Terraform"
  type        = string
  sensitive   = true
}

variable "autoscalerToken" {
  description = "Scoped DigitalOcean runtime token used only by the media-node autoscaler and draining nodes"
  type        = string
  sensitive   = true
}

variable "awsRegion" {
  description = "AWS region containing the Route53 and SSM operational resources"
  type        = string
  default     = "ap-south-1"
}

variable "route53ZoneId" {
  description = "Route53 hosted-zone ID used when domainName is configured"
  type        = string
  default     = ""
}

variable "sshAllowedCidrs" {
  description = "CIDR ranges allowed to SSH to OpenVidu nodes"
  type        = list(string)

  validation {
    condition = length(var.sshAllowedCidrs) > 0 && alltrue([
      for cidr in var.sshAllowedCidrs :
      try(can(cidrhost(cidr, 0)) && tonumber(split("/", cidr)[1]) > 0, false)
    ])
    error_message = "sshAllowedCidrs must contain valid IPv4 or IPv6 CIDRs and must not allow the entire internet."
  }
}

variable "region" {
  description = "DigitalOcean region where resources will be created"
  type        = string
  default     = "ams3"
}

variable "vpcIpRange" {
  description = "Private CIDR for the OpenVidu VPC; it must not overlap any VPC in the DigitalOcean account"
  type        = string
  default     = "10.10.10.0/24"

  validation {
    condition     = can(cidrhost(var.vpcIpRange, 0)) && !strcontains(var.vpcIpRange, ":")
    error_message = "vpcIpRange must be a valid IPv4 CIDR."
  }
}

variable "stackName" {
  description = "Stack name for OpenVidu deployment"
  type        = string
}

variable "certificateType" {
  description = "[selfsigned] Not recommended for production use. Just for testing purposes or development environments. You don't need a FQDN to use this option. [owncert] Valid for production environments. Use your own certificate. You need a FQDN to use this option. [letsencrypt] Valid for production environments. Can be used with or without a FQDN (if no FQDN is provided, a random sslip.io domain will be used)."
  type        = string
  default     = "letsencrypt"
  validation {
    condition     = contains(["selfsigned", "owncert", "letsencrypt"], var.certificateType)
    error_message = "certificateType must be one of: selfsigned, owncert, letsencrypt"
  }
}

variable "domainName" {
  description = "Domain name for the OpenVidu Deployment."
  type        = string
  default     = ""
  validation {
    condition     = can(regex("^$|^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$", var.domainName))
    error_message = "The domain name does not have a valid domain name format"
  }
}

variable "ownPublicCertificate" {
  description = "If certificate type is 'owncert', this parameter will be used to specify the public certificate in base64 format"
  type        = string
  default     = ""
}

variable "ownPrivateCertificate" {
  description = "If certificate type is 'owncert', this parameter will be used to specify the private certificate in base64 format"
  type        = string
  default     = ""
}

variable "initialMeetAdminPassword" {
  description = "Initial password for the 'admin' user in OpenVidu Meet. If not provided, a random password will be generated."
  type        = string
  default     = ""
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]*$", var.initialMeetAdminPassword))
    error_message = "Must contain only alphanumeric characters (A-Z, a-z, 0-9). Leave empty to generate a random password."
  }
}

variable "initialMeetApiKey" {
  description = "Initial API key for OpenVidu Meet. If not provided, no API key will be set and the user can set it later from Meet Console."
  type        = string
  default     = ""
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]*$", var.initialMeetApiKey))
    error_message = "Must contain only alphanumeric characters (A-Z, a-z, 0-9). Leave empty to not set an initial API key."
  }
}

variable "masterNodeInstanceType" {
  description = "Specifies the Droplet size for your OpenVidu Master Node"
  type        = string
  default     = "s-4vcpu-8gb"
}

variable "mediaNodeInstanceType" {
  description = "Specifies the Droplet size for your OpenVidu Media Nodes"
  type        = string
  default     = "s-4vcpu-8gb"
}

variable "minNumberOfMediaNodes" {
  description = "Minimum number of media nodes (autoscaler will never scale below this)"
  type        = number
  default     = 1

  validation {
    condition     = var.minNumberOfMediaNodes >= 1 && floor(var.minNumberOfMediaNodes) == var.minNumberOfMediaNodes
    error_message = "minNumberOfMediaNodes must be a positive whole number."
  }
}

variable "maxNumberOfMediaNodes" {
  description = "Maximum number of media nodes (autoscaler will never scale above this)"
  type        = number
  default     = 5

  validation {
    condition = (
      var.maxNumberOfMediaNodes >= var.minNumberOfMediaNodes &&
      floor(var.maxNumberOfMediaNodes) == var.maxNumberOfMediaNodes
    )
    error_message = "maxNumberOfMediaNodes must be a whole number at least as large as minNumberOfMediaNodes."
  }
}

variable "scaleTargetCPU" {
  description = "Target average CPU percentage for autoscaling. Scale out above this, scale in below 70% of this."
  type        = number
  default     = 50

  validation {
    condition     = var.scaleTargetCPU > 0 && var.scaleTargetCPU <= 100
    error_message = "scaleTargetCPU must be greater than 0 and no greater than 100."
  }
}

variable "fixedNumberOfMediaNodes" {
  description = "Fixed number of media nodes to create (0 = use autoscaling)"
  type        = number
  default     = 0

  validation {
    condition     = var.fixedNumberOfMediaNodes >= 0 && floor(var.fixedNumberOfMediaNodes) == var.fixedNumberOfMediaNodes
    error_message = "fixedNumberOfMediaNodes must be zero or a positive whole number."
  }
}

variable "openviduLicense" {
  description = "Visit https://openvidu.io/account"
  type        = string
  sensitive   = true
}

variable "rtcEngine" {
  description = "RTCEngine media engine to use"
  type        = string
  default     = "pion"
  validation {
    condition     = contains(["pion", "mediasoup"], var.rtcEngine)
    error_message = "rtcEngine must be one of: pion, mediasoup"
  }
}

variable "enabledModules" {
  description = "Comma-separated OpenVidu modules enabled on the master node"
  type        = string
  default     = "observability,openviduMeet"

  validation {
    condition     = can(regex("^[A-Za-z0-9,._-]+$", var.enabledModules))
    error_message = "enabledModules must be a comma-separated list of OpenVidu module names."
  }
}

variable "additionalInstallFlags" {
  description = "Additional optional flags to pass to the OpenVidu installer (comma-separated, e.g.,'--flag1=value, --flag2')."
  type        = string
  default     = ""
  validation {
    condition     = can(regex("^[A-Za-z0-9, =_.\\-]*$", var.additionalInstallFlags))
    error_message = "Must be a comma-separated list of flags (for example, --flag=value, --bool-flag)."
  }
}

variable "spaceName" {
  description = "Name of the DigitalOcean Space (S3-compatible bucket) to store application data and recordings. If empty, a bucket will be created with default name"
  type        = string
  default     = ""
}

variable "spaceRegion" {
  description = "Region for the DigitalOcean Space. Common values: nyc3, ams3, sgp1, sfo3"
  type        = string
  default     = "ams3"
}

variable "spacesAccessId" {
  description = "Access key ID for DigitalOcean Spaces (S3-compatible). Required if spaceName is empty (a new bucket will be created)."
  type        = string
  default     = ""
}

variable "spacesSecretKey" {
  description = "Secret access key for DigitalOcean Spaces (S3-compatible). Required if spaceName is empty (a new bucket will be created)."
  type        = string
  default     = ""
}
