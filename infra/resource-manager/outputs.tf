output "instance_public_ip" {
  description = "Use only for SSH from admin_cidr. WebUI has no public listener."
  value       = oci_core_instance.app.public_ip
}

output "ssh_tunnel" {
  value = "ssh -i /path/to/your-private-key -L 3000:127.0.0.1:3000 ubuntu@${oci_core_instance.app.public_ip}"
}

output "database_ocid" {
  value = oci_database_autonomous_database.demo.id
}

output "mcp_endpoint" {
  description = "Usable only after enabling MCP, installing tools, and configuring OAuth. Commercial OCI realm only."
  value       = "https://dataaccess.adb.${var.region}.oraclecloudapps.com/adb/mcp/v1/databases/${oci_database_autonomous_database.demo.id}"
}

output "compute_dynamic_group_rule" {
  value = "ALL {instance.id = '${oci_core_instance.app.id}'}"
}

output "adb_dynamic_group_rule" {
  value = "ALL {resource.type = 'autonomousdatabase', resource.id = '${oci_database_autonomous_database.demo.id}'}"
}

output "next_steps" {
  value = "Check cloud-init status and bootstrap.READY on the VM. Verify IAM propagation, then start Compose manually. Install SQL as documented and configure MCP/OAuth. Apply success does not prove application readiness."
}
