data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = var.vm_shape
  state                    = "AVAILABLE"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

locals {
  # Files are taken from this exact source package, not a mutable GitHub branch.
  # No GitHub token, private key, wallet, or database password enters user_data.
  application_files = [
    ".env.example", "compose.example.yaml",
    "oci-gateway/app.py", "oci-gateway/requirements.txt",
    "oci-gateway/Dockerfile", "oci-gateway/.dockerignore",
    "scripts/init_env.py", "scripts/check_config.py"
  ]
  cloud_config = {
    package_update = true
    packages       = ["docker.io", "docker-compose-v2", "python3", "ca-certificates"]
    write_files = concat([
      for name in local.application_files : {
        path  = "/opt/oracle-enterprise-ai/${name}"
        owner = "root:root"
        # Public source must remain readable by the non-root container user.
        # The parent directory is root-only; secrets are written separately.
        permissions = "0644"
        encoding    = "b64"
        content     = filebase64("${path.module}/../../${name}")
      }
      ], [
      {
        path        = "/opt/oracle-enterprise-ai/stack-settings.json"
        owner       = "root:root"
        permissions = "0600"
        content = jsonencode({
          region         = var.genai_region
          compartment_id = var.compartment_ocid
        })
      },
      {
        path        = "/opt/oracle-enterprise-ai/bootstrap.py"
        owner       = "root:root"
        permissions = "0700"
        encoding    = "b64"
        content     = filebase64("${path.module}/bootstrap.py")
      }
    ])
    runcmd = [
      ["chmod", "0700", "/opt/oracle-enterprise-ai"],
      ["systemctl", "enable", "--now", "docker"],
      ["python3", "/opt/oracle-enterprise-ai/bootstrap.py"]
    ]
    final_message = "Infrastructure bootstrap finished. Check cloud-init status and bootstrap.READY; application startup is manual."
  }
  instance_metadata = {
    ssh_authorized_keys = trimspace(var.ssh_public_key)
    # gzip keeps the bundled application below OCI's 32,000-byte metadata limit.
    user_data = base64gzip("#cloud-config\n${yamlencode(local.cloud_config)}")
  }
}

resource "oci_core_instance" "app" {
  availability_domain  = var.availability_domain
  compartment_id       = var.compartment_ocid
  display_name         = "${var.name_prefix}-app"
  shape                = var.vm_shape
  preserve_boot_volume = true
  shape_config {
    ocpus         = var.vm_ocpus
    memory_in_gbs = var.vm_memory_gb
  }
  create_vnic_details {
    subnet_id        = oci_core_subnet.demo.id
    assign_public_ip = true
    hostname_label   = "enterpriseai"
  }
  source_details {
    source_type             = "image"
    source_id               = try(data.oci_core_images.ubuntu.images[0].id, null)
    boot_volume_size_in_gbs = var.boot_volume_gb
  }
  instance_options {
    are_legacy_imds_endpoints_disabled = true
  }
  metadata      = local.instance_metadata
  freeform_tags = local.tags
  lifecycle {
    prevent_destroy = true
    # A newer catalog image must not replace a VM holding application data.
    ignore_changes = [source_details[0].source_id]
    precondition {
      condition     = length(data.oci_core_images.ubuntu.images) > 0
      error_message = "No compatible Ubuntu 24.04 image found. Stop and review region/shape availability."
    }
    precondition {
      condition     = length(jsonencode(local.instance_metadata)) < 30000
      error_message = "Bundled instance metadata exceeds the conservative 30,000-byte limit. Do not remove this guard."
    }
  }
}
