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
