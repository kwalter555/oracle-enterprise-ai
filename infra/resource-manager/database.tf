resource "oci_database_autonomous_database" "demo" {
  compartment_id = var.compartment_ocid
  display_name   = "${var.name_prefix}-adb"
  db_name        = var.adb_name
  # OLTP supports the 20 GB minimum used by this small demo.
  # This configuration is for a NEW database, not an existing DW conversion.
  db_workload                         = "OLTP"
  admin_password                      = var.adb_admin_password
  compute_model                       = "ECPU"
  compute_count                       = var.adb_ecpus
  data_storage_size_in_gb             = var.adb_storage_gb
  license_model                       = "LICENSE_INCLUDED"
  is_free_tier                        = false
  is_auto_scaling_enabled             = false
  is_auto_scaling_for_storage_enabled = false
  is_mtls_connection_required         = true
  # Public service endpoint, restricted to the administrator and this new VM.
  # No access to all addresses; no attempt to modify an existing database.
  whitelisted_ips = [var.admin_cidr, "${oci_core_instance.app.public_ip}/32"]
  freeform_tags = merge(local.tags, {
    "adb$feature" = jsonencode({ name = "mcp_server", enable = var.enable_mcp })
  })
  lifecycle {
    prevent_destroy = true
  }
}
