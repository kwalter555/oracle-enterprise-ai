# Sharing scope and security limitations

Only text source files, generic templates, and fictional demo data are included.
Excluded: wallets, private keys, OAuth tokens/client secrets, real environment
files, live container inspection/Compose exports, backup archives, business data,
conversations, original documents, and user passwords.

An OCI OCID is not an authentication secret, but original environment identifiers
have been removed for privacy. Public model IDs, regions, generic demo schema
names, and public documentation URLs are intentionally retained. Synthetic test
values are not credentials.

Before every push, run `scripts/check_share.py` and inspect the staged diff and
history. Heuristics cannot detect every secret. Before public release, also use
an approved dedicated secret scanner and review licenses and dependencies. This
package has not undergone an independent security audit or a complete CVE assessment.

If a real secret is committed or published, revoke/rotate it first. Deleting a
line in a later commit does not remove the old value from history or other copies.
A private GitHub repository is not a secret store. Do not automatically force-push
as a remedy; first agree on history cleanup and coordinate with collaborators.

Keep `.env` and wallets outside Git, with restricted permissions and an encrypted
backup. Docker environment values are accessible to the host administrator.
Membership in the Docker group gives substantial access to the host and its secrets.

No gateway or PostgreSQL port is published. WebUI binds to loopback only, with
authentication enabled. Remote use requires HTTPS, sign-up/access/network controls,
monitoring, budgets, and a recovery plan. Public application deployment is outside
the scope of this package.

A code backup does not include Oracle/PostgreSQL contents, Docker volumes, bucket
objects, IAM/VCN resources, or persisted WebUI settings. Full-system backup is a
separate procedure, and its archives must never be placed in this repository.

The Resource Manager option adds a separate state boundary: the new database ADMIN
password is a sensitive input, but it is still stored in Terraform state. Restrict
access to Stack jobs, state and exports. The UI's hidden View State button is not
an access-control guarantee. Real variable files, state and saved plans are excluded
from this source package. The Stack generates application secrets only on the VM;
it does not automatically start the application, install SQL or enable MCP.
Review the [Stack security and recovery limits](../infra/resource-manager/README.md#security-updates-and-recovery-boundaries)
before provisioning. Destroy protection and a retained boot volume are not backups.

The optional `approved-sql/` pilot adds a separate trust boundary: an administrator-only
WebUI Tool holds transport/signing keys, and a private sidecar holds two database
passwords, mTLS material and a one-use approval ledger. These runtime files and
configured Tool exports are not shareable source. Every analytical query needs
an interactive approval of the exact stored SQL. Database SELECT-only privileges,
read-only transactions and a restricted SQL AST policy are independent safeguards,
not a production security certification. Host/plugin administrators remain trusted.
Read the [pilot boundaries and staged activation](../approved-sql/README.md) before use.
