# Provenance and scope

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
