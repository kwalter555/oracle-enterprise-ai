variable "tenancy_ocid" {
  type        = string
  description = "Your tenancy OCID. Automatically populated by Resource Manager."
  validation {
    condition     = can(regex("^ocid1\\.tenancy\\.oc1\\.\\.[a-z0-9]{20,}$", var.tenancy_ocid))
    error_message = "Provide your commercial-realm (oc1) tenancy OCID."
  }
}

variable "compartment_ocid" {
  type        = string
  description = "Existing dedicated demo compartment; not the tenancy root."
  validation {
    condition     = can(regex("^ocid1\\.compartment\\.oc1\\.\\.[a-z0-9]{20,}$", var.compartment_ocid))
    error_message = "Select an existing commercial-realm (oc1) compartment, not the tenancy root."
  }
}

variable "region" {
  type        = string
  description = "Deployment region in the commercial OCI realm (oc1)."
  validation {
    condition     = can(regex("^[a-z]+-[a-z0-9-]+-[0-9]+$", var.region))
    error_message = "Provide a region identifier, such as eu-frankfurt-1."
  }
}

variable "home_region" {
  type        = string
  description = "Actual home region of your tenancy, used for IAM."
  validation {
    condition     = can(regex("^[a-z]+-[a-z0-9-]+-[0-9]+$", var.home_region))
    error_message = "Provide your tenancy home region identifier."
  }
}

variable "availability_domain" {
  type        = string
  description = "Availability domain in the selected deployment region."
  validation {
    condition     = length(trimspace(var.availability_domain)) > 0
    error_message = "Select an availability domain."
  }
}

variable "name_prefix" {
  type        = string
  default     = "enterprise-ai-demo"
  description = "Unique prefix for the new environment and IAM names."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,24}$", var.name_prefix))
    error_message = "Use 3-25 lowercase letters, digits, or hyphens, starting with a letter."
  }
}

variable "acknowledge_costs" {
  type        = bool
  default     = false
  description = "Confirm that this creates PAID resources, not an Always Free environment."
}

variable "admin_cidr" {
  type        = string
  description = "Your public IPv4 address with /32, for SSH and database access. No broad CIDRs."
  validation {
    condition = (
      can(cidrnetmask(var.admin_cidr)) && can(regex("/32$", var.admin_cidr)) &&
      !can(regex("^(0\\.|10\\.|127\\.|169\\.254\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.|192\\.168\\.|100\\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\\.)", var.admin_cidr)) &&
      try(tonumber(split(".", var.admin_cidr)[0]) < 224, false)
    )
    error_message = "Enter one public IPv4 address with /32; broad networks are not accepted."
  }
}

variable "ssh_public_key" {
  type        = string
  description = "One SSH PUBLIC key. The private key stays on your own computer."
  validation {
    condition     = can(regex("^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp256) [A-Za-z0-9+/=]+( [ -~]*)?$", trimspace(var.ssh_public_key))) && length(var.ssh_public_key) < 4096
    error_message = "Provide one supported public SSH key with an optional ASCII comment, never a private key."
  }
}

variable "vcn_cidr" {
  type        = string
  default     = "10.42.0.0/16"
  description = "New isolated VCN. The first /24 is used for the VM subnet. Check for overlap."
  validation {
    condition     = can(cidrnetmask(var.vcn_cidr)) && can(regex("^10\\.[0-9]+\\.0\\.0/16$", var.vcn_cidr))
    error_message = "Use a private 10.x.0.0/16 CIDR; the first /24 is reserved for the VM."
  }
}

variable "vm_shape" {
  type        = string
  default     = "VM.Standard.E4.Flex"
  description = "x86_64 flexible shape; ARM is not supported by this initial package."
  validation {
    condition     = contains(["VM.Standard.E4.Flex", "VM.Standard.E5.Flex"], var.vm_shape)
    error_message = "Choose VM.Standard.E4.Flex or VM.Standard.E5.Flex."
  }
}

variable "vm_ocpus" {
  type        = number
  default     = 2
  description = "VM OCPUs, limited to 2-4 for this demo."
  validation {
    condition     = var.vm_ocpus >= 2 && var.vm_ocpus <= 4 && floor(var.vm_ocpus) == var.vm_ocpus
    error_message = "Choose 2, 3, or 4 OCPUs."
  }
}

variable "vm_memory_gb" {
  type        = number
  default     = 16
  description = "VM memory in GB."
  validation {
    condition     = var.vm_memory_gb >= 16 && var.vm_memory_gb <= 32 && floor(var.vm_memory_gb) == var.vm_memory_gb
    error_message = "Choose an integer from 16 to 32 GB."
  }
}

variable "boot_volume_gb" {
  type        = number
  default     = 100
  description = "Boot volume also holds PostgreSQL and WebUI data; this is not a backup."
  validation {
    condition     = var.boot_volume_gb >= 100 && var.boot_volume_gb <= 250 && floor(var.boot_volume_gb) == var.boot_volume_gb
    error_message = "Choose an integer from 100 to 250 GB."
  }
}

variable "genai_region" {
  type        = string
  default     = "eu-frankfurt-1"
  description = "GenAI endpoint region. Independently verify model availability and processing terms."
  validation {
    condition     = can(regex("^[a-z]+-[a-z0-9-]+-[0-9]+$", var.genai_region))
    error_message = "Provide a valid GenAI region identifier."
  }
}

variable "create_iam" {
  type        = bool
  default     = true
  description = "Create two exact-resource dynamic groups and GenAI policies in the default identity domain. Requires tenancy IAM rights."
}

variable "adb_name" {
  type        = string
  default     = "ENTAIDEMO"
  description = "New Autonomous Database name; must be unique in the applicable OCI scope."
  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9]{0,13}$", var.adb_name))
    error_message = "Use 1-14 alphanumeric characters, starting with a letter."
  }
}

variable "adb_admin_password" {
  type        = string
  sensitive   = true
  description = "New database ADMIN password. Hidden in normal output but stored in protected Terraform state. Never commit it."
  validation {
    condition     = length(var.adb_admin_password) >= 12 && length(var.adb_admin_password) <= 30 && can(regex("[A-Z]", var.adb_admin_password)) && can(regex("[a-z]", var.adb_admin_password)) && can(regex("[0-9]", var.adb_admin_password)) && !strcontains(lower(var.adb_admin_password), "admin") && !can(regex("[\"\\r\\n]", var.adb_admin_password))
    error_message = "Use 12-30 characters with uppercase, lowercase, and digits; no double quote, newline, or word admin."
  }
}

variable "adb_ecpus" {
  type        = number
  default     = 2
  description = "Paid ECPU allocation. Automatic compute scaling is disabled."
  validation {
    condition     = contains([2, 4, 8], var.adb_ecpus)
    error_message = "Choose 2, 4, or 8 ECPUs."
  }
}

variable "adb_storage_gb" {
  type        = number
  default     = 20
  description = "Paid Transaction Processing storage in GB (minimum 20). Automatic storage scaling is disabled."
  validation {
    condition     = var.adb_storage_gb >= 20 && var.adb_storage_gb <= 100 && floor(var.adb_storage_gb) == var.adb_storage_gb
    error_message = "Choose an integer from 20 to 100 GB."
  }
}

variable "enable_mcp" {
  type        = bool
  default     = false
  description = "Enable the ADB MCP feature only after database users/tools and access controls have been reviewed."
}
