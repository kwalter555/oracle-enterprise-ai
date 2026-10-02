locals {
  tags = { application = "oracle-enterprise-ai-demo", environment = var.name_prefix }
}

resource "oci_core_vcn" "demo" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "${var.name_prefix}-vcn"
  dns_label      = "entaidemo"
  freeform_tags  = local.tags
  lifecycle {
    precondition {
      condition     = var.acknowledge_costs
      error_message = "Review paid-resource costs and set acknowledge_costs=true before planning deployment."
    }
  }
}

resource "oci_core_internet_gateway" "demo" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.demo.id
  display_name   = "${var.name_prefix}-igw"
  enabled        = true
  freeform_tags  = local.tags
}

resource "oci_core_route_table" "demo" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.demo.id
  display_name   = "${var.name_prefix}-routes"
  route_rules {
    network_entity_id = oci_core_internet_gateway.demo.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }
  freeform_tags = local.tags
}

# This replaces use of the VCN's default security list for our subnet.
# Only one incoming port, from one administrator IP. No WebUI/DB/gateway ingress.
resource "oci_core_security_list" "demo" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.demo.id
  display_name   = "${var.name_prefix}-ssh-only"
  ingress_security_rules {
    protocol    = "6"
    source      = var.admin_cidr
    source_type = "CIDR_BLOCK"
    stateless   = false
    tcp_options {
      min = 22
      max = 22
    }
  }
  # Internet egress is required for Ubuntu packages, container images, OCI APIs,
  # DNS and external model endpoints. Production egress filtering is separate work.
  egress_security_rules {
    protocol         = "all"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    stateless        = false
  }
  freeform_tags = local.tags
}

resource "oci_core_subnet" "demo" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.demo.id
  cidr_block                 = cidrsubnet(var.vcn_cidr, 8, 0)
  display_name               = "${var.name_prefix}-subnet"
  dns_label                  = "app"
  route_table_id             = oci_core_route_table.demo.id
  security_list_ids          = [oci_core_security_list.demo.id]
  prohibit_public_ip_on_vnic = false
  prohibit_internet_ingress  = false
  freeform_tags              = local.tags
}
