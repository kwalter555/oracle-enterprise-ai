# Optional: default identity domain only. For custom domains, set create_iam=false
# and have your IAM administrator create the equivalent exact-resource rules.
resource "oci_identity_dynamic_group" "compute" {
  count          = var.create_iam ? 1 : 0
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = "${var.name_prefix}-compute-dg"
  description    = "Only this demo VM, for GenAI chat and embeddings."
  matching_rule  = "ALL {instance.id = '${oci_core_instance.app.id}'}"
}

resource "oci_identity_dynamic_group" "adb" {
  count          = var.create_iam ? 1 : 0
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = "${var.name_prefix}-adb-dg"
  description    = "Only this demo Autonomous Database, for Select AI chat."
  matching_rule  = "ALL {resource.type = 'autonomousdatabase', resource.id = '${oci_database_autonomous_database.demo.id}'}"
}

resource "oci_identity_policy" "genai" {
  count          = var.create_iam ? 1 : 0
  provider       = oci.home
  compartment_id = var.compartment_ocid
  name           = "${var.name_prefix}-genai"
  description    = "Demo principals may call GenAI in the demo compartment only."
  statements = [
    "Allow dynamic-group id ${oci_identity_dynamic_group.compute[0].id} to use generative-ai-chat in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group id ${oci_identity_dynamic_group.compute[0].id} to use generative-ai-text-embedding in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group id ${oci_identity_dynamic_group.adb[0].id} to use generative-ai-chat in compartment id ${var.compartment_ocid}"
  ]
}
