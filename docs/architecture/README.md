# Enterprise AI reference architecture

Deliverables: `enterprise-ai-atp.drawio` (editable source) and
`enterprise-ai-atp.png` (README preview). All labels are English. Official
stencils come from the Oracle OCI Architecture Diagram Toolkit, local v24.2
library, linked from [Oracle's toolkit page](https://docs.oracle.com/en-us/iaas/Content/General/Reference/graphicsfordiagrams.htm).
Oracle's asset terms apply; these are not newly designed service logos.

## Infrastructure and application boundaries

- Resource Manager creates a new VCN, public subnet, Internet Gateway, restricted
  SSH ingress, Ubuntu E4 Flex VM and paid Autonomous Transaction Processing
  database. Optional IAM resources target the exact new VM and database.
- Open WebUI, the OCI gateway and PostgreSQL run on the VM after **manual startup**.
  WebUI listens on loopback; the administrator uses an SSH tunnel. PostgreSQL and
  the gateway have no published host ports. Data lives on the retained boot disk.
- Autonomous Database has a **public managed endpoint outside the VCN**, restricted
  to the administrator and VM addresses. It is not a private-endpoint deployment.
- The gateway calls the existing regional OCI Generative AI service with Instance
  Principal. Select AI in the database uses its own Resource Principal. Model calls
  and embedding calls are separately billable and require IAM and available quota.
- The WebUI-to-database MCP flow requires manual SQL, tools and OAuth setup.
  SQL scripts are included but not executed by Terraform. The proposal tool does
  not execute its generated SQL.
- Orange dashed paths represent the **optional** direct SQL-review pilot. It
  requires a separately reviewed installation for the new environment, wallet and
  restricted database users, and exact-SQL approval. Execution starts disabled.
  The existing-environment pilot installer is not an automatic Stack installer.

Arrows represent logical requests, not every network hop. VM service calls use
Internet Gateway egress. The diagram intentionally includes no Service Gateway,
NAT Gateway, public HTTPS ingress, Object Storage bucket or private DB endpoint.
Automatic shutdown, budget alerts and backup policies are not part of this Stack.
An intermittent-use cost estimate is not a spending cap.

## Editing and verification

Open the `.drawio` file in draw.io/diagrams.net. The diagram consists of editable
cells and embedded official stencils, not one flattened bitmap. XML IDs and edge
references are checked by repository tests; the PNG was exported with draw.io
desktop and visually reviewed for overlaps. Update both files together and review
the PNG before updating its exact-file digest in the sharing checker and the
repository source manifest. Other binary files remain rejected by default.

Use generic labels when sharing. Do not add real addresses, account identifiers,
customer data, credentials or local workstation paths. The Frankfurt region and
default sizes are illustrative deployment settings, not a capacity or cost promise.
This is a reference for the supplied Terraform and runbooks, not evidence of a
successful new-tenancy deployment.
