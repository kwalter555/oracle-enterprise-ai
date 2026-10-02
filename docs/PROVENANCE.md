# Provenance and scope

## Architecture and deployment link — 2026-10-02

An editable reference architecture and PNG preview were created using official
Oracle OCI draw.io toolkit stencils (v24.2 local library). The preview was exported
with draw.io desktop and visually reviewed. The README deploy button uses Oracle's
documented public GitHub archive URL format and points to the complete `main` tree.
The integration must be merged before that main-branch button includes Terraform.
The diagram distinguishes provisioned infrastructure, manual application/SQL setup
and the optional SQL-review pilot. No cloud resource is provisioned by this change.
The sharing checker admits only the exact reviewed PNG digest; other binaries and
modified image copies remain rejected. Oracle retains rights to its stencil assets.

## Fresh-tenancy ATP correction — 2026-10-02

The owner approved changing the fresh-deployment database from DW to Transaction
Processing (OLTP), retaining 2 ECPUs and 20 GB. The old DW/20 GB combination was
incorrect for standard paid DW provisioning. Earlier distribution archives are
retained as historical artifacts and must not be used for the new deployment.
This change does not migrate or convert an existing database. Gateway, SQL,
application versions and approved-execution source remain unchanged. Account
identifiers and credentials are not embedded in this shareable distribution.
No OCI resource was created, updated or deleted and no GitHub push was performed.

Initially prepared on 2026-09-25 from locally available demo source code and SQL
scripts. Gateway `app.py` is preserved byte-for-byte, SHA-256:
`f6f39489bad8ea0cf4acfbb74c739d84799bedbf34c44765d017a6910fdafd8f`.
This matches the previously reported running gateway hash. The current contents
of the remote VM were not retrieved or independently rechecked during packaging.

The Cohere native tool-result and citation-alias adaptations are included. The old
baseline, patch generator, and fixtures remain for regression tests, not deployment.
Original VM-specific deployment/rollback scripts are excluded: they depended on
running images, private configuration, and the existing topology. This is not a
hidden backup of those scripts; new installations use the Compose template.

The project/analytics SQL comes from the demo. The private compartment OCID was
replaced with a placeholder, with a guard against running the profile template
before substitution. Bootstrap scripts, configuration templates, documentation,
and the sharing checker were newly added. Original source files elsewhere in the
local workspace were not changed.

On 2026-09-28, documentation, diagnostic messages, sample questions, query-result
labels, and descriptive demo data were translated into English in this sharing
copy. Database/tool identifiers, stored category codes, numeric values, dates,
access controls, and SQL proposal-only behavior were retained. These edits do
not update data or functions already installed in a database. Do not rerun creation
scripts as a migration; they intentionally refuse to overwrite existing objects.

Open WebUI and Oracle source code are not redistributed here; their dependencies,
APIs, and container images are used under their own terms. Model and infrastructure
accounts are not included. No new open-source license has been selected for the
owner's code.

On 2026-09-29, a new OCI Resource Manager configuration, root-only VM bootstrap,
English variable form, distribution builder and offline tests were added. This
infrastructure configuration was authored for a fresh environment; it is not an
export of the original OCI resources. SQL, gateway logic and Compose service
definitions were not changed. No OCI Stack, Plan or Apply was run during preparation.

On 2026-09-30, a separate approved-SQL execution pilot was authored in `approved-sql/`.
It reuses the existing proposal function without modifying it. New source includes
the private sidecar, exact-SQL confirmation Tool, dedicated executor grant script,
offline tests and staged installation instructions. It was not installed on the
original VM or database. The original gateway and SQL/MCP scripts remain unchanged.
