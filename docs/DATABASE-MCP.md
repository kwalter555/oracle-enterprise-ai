# Your own Autonomous Database and MCP demo

Use a NEW test Autonomous Database with DBMS_CLOUD_AI and DBMS_CLOUD_AI_AGENT
support. PostgreSQL in Compose stores WebUI data; it does not replace Oracle
Autonomous Database. Your account administrator configures OCI/IAM. Schema names
in this guide are generic demo names.

## A. Your own connections and initial privileges

1. Download the wallet for YOUR database from OCI Console if using a SQL Developer
   Cloud Wallet connection. Keep it outside the repository. Use the Oracle user's
   password, not the wallet password. Connect as ADMIN, with Role set to default.
2. Check `SELECT USER FROM dual`. Create WEBUI_MCP through Other Users →
   Create User, with password authentication, DATA tablespace, unlocked/not expired,
   and no broad roles. Enter the password in the dialog, never in a SQL file or Git.
3. As ADMIN, run `sql/bootstrap/00-admin-owner-grants.sql`, then
   `sql/projects/00-admin-permissions.sql`. These grant the initial privileges
   needed by the demo table/tool owner and a limited quota. Do not grant DBA/DWROLE.
4. Create a separate SQL Developer connection as WEBUI_MCP.

Run each entire script with F5 in a new worksheet on the correct connection.
DDL and grants may implicitly commit changes. On error, stop and inspect the
exact output; do not automatically delete or overwrite existing objects.

## B. Demo data and existing tool types

As WEBUI_MCP:

- `sql/bootstrap/02-webui-health-tool.sql`: a fixed test greeting and MCP tool.
- `sql/projects/01-create-and-load.sql`, then `02-verify.sql`: 12 fictional projects.
- `sql/projects/03-create-lookup.sql`, `04-test-and-register-lookup.sql`, and
  `05-verify-lookup-tool.sql`: a restricted lookup by project code only.
- `sql/analytics/01-create-analytics-data.sql`, then `02-verify-analytics-data.sql`:
  five separate DEMO_A tables; the original DEMO_PROJECTS table is unchanged.

Do not run SQL from `oci-gateway/adb-readonly-demo/`: those are historical test fixtures.

The reference analytics dataset has 36 projects, 24 employees, 4 departments,
192 cost entries, and 354 absence-day records. All data is fictional. The snapshot
date is 2026-09-24, so 2026 is not a full year. Always ask about an explicit year
for reproducible comparisons. Total recorded costs: EUR 473699. Annual leave in
2025: 20 distinct employees, 100 days. These are not your company's records.

### Data code glossary

Stored codes are retained for compatibility with existing demo installations,
constraints, and tests. Descriptive names and sample questions are in English.
Translate the meaning in answers, but use the exact stored code in SQL predicates.

| Field | Stored code | English meaning |
|---|---|---|
| Project status | `PLANIRAN` | Planned (12-project demo only) |
| Project status | `U_TIJEKU` | In progress |
| Project status | `PAUZIRAN` | Paused |
| Project status | `ZAVRSEN` | Completed |
| Cost category | `RAD` | Labor |
| Cost category | `CLOUD` | Cloud |
| Cost category | `LICENCE` | Licenses |
| Cost category | `VANJSKE_USLUGE` | External services |
| Leave type | `GODISNJI` | Annual leave |
| Leave type | `EDUKACIJA` | Training |
| Leave status | `ISKORISTEN` | Actually taken |
| Leave status | `ODOBREN` | Approved, not yet taken |
| Leave status | `OTKAZAN` | Cancelled |

The English source files do not migrate existing rows or functions. Do not rerun
creation scripts to translate a running database: they deliberately stop if their
objects already exist. Proper names, identifiers, and the Europe/Zagreb time zone
remain unchanged.

## C. Select AI with a separate reader account

1. As ADMIN, run `sql/analytics/03-select-ai-preflight-admin.sql`.
2. In your OCI account, configure a separate ADB dynamic group and the
   `generative-ai-chat` policy from `config/iam-policy.example.txt`. Use your
   database's exact OCID and your GenAI compartment. Allow time for propagation;
   do not broaden privileges blindly.
3. As ADMIN, run `sql/bootstrap/01-admin-resource-principal.sql`.
4. As ADMIN, create DEMO_AI_READER through Create User with a new password of your
   own, no roles, no quotas, and no additional system privileges. Then run analytics 04.
5. Create a DEMO_AI_READER connection. Check `SELECT USER FROM dual`.
6. Copy `sql/analytics/05-reader-create-profile.sql` to the Git-ignored `local/`
   directory (create it yourself). In that copy, replace **every** occurrence of
   `__OCI_COMPARTMENT_OCID__` with your GenAI compartment OCID. Adjust the region
   and model for your account. Do not commit the personalized copy. The original
   template intentionally refuses to run before substitution.
7. As DEMO_AI_READER, run your local 05, then the original 06 (one billable model
   call) and 07 (two billable calls). SHOWSQL returns a proposal without executing
   it. Reference results do not prove that generated SQL was executed.

## D. MCP SQL proposal tool — no execution

This is not an arbitrary SQL executor and has no approval parameter. After human
review, run the exact SQL MANUALLY in SQL Developer as DEMO_AI_READER, never ADMIN.
Replying "approved" in chat executes nothing. Every new proposal requires a new review.

Run the files in `sql/analytics/` in this order:

| Script | Connection | Purpose |
|---|---|---|
| 08 | ADMIN | Temporarily grants CREATE PROCEDURE to the reader. |
| 09 | DEMO_AI_READER | Creates a function, runs six local rejection tests, grants EXECUTE to WEBUI_MCP. |
| 10 | ADMIN | Removes the temporary privilege; run even if 09 fails, then stop to investigate. |
| 11 | WEBUI_MCP | Creates a local wrapper and tests rejection of invalid input. |
| 12 | WEBUI_MCP | Makes one billable call; expects PROPOSAL_ONLY and executed=false. |
| 13 | WEBUI_MCP | Registers the new tool only after test 12 passes and its output is reviewed. |

Proposed SQL has not been security-validated. Do not execute unexpected functions,
packages, database links, PL/SQL, or extra statements just because the text starts
with SELECT. The wrapper uses a fixed SHOWSQL prefix, fixed profile, and five-table
allowlist; users cannot change the action. Questions are limited to 2000 characters
and responses to 16000 characters. There is no daily model budget or rate limit;
restrict access.

## E. MCP and Open WebUI

Enable MCP for YOUR database in OCI Console following Oracle's documentation:
free-form tag `adb$feature` with value `{"name":"mcp_server","enable":true}`.
If feature tags or a private endpoint already exist, follow their specific
instructions; do not overwrite unrelated settings. Do not open network access to
everyone just to test.

In Open WebUI Admin → Integrations, add a new MCP Streamable HTTP connection.
`config/mcp-connection.example.json` documents values but is not an import format.
Insert your ADB region and OCID in the URL. For a private endpoint, use the format
in OCI documentation. Set OAuth 2.1, Register Client, save, reopen, and Authorize
OAuth with your WEBUI_MCP account. If your ORDS login uses an alias, check your own
Database Actions configuration; do not copy someone else's alias.

Limit the tool filter to:
`WEBUI_HEALTH_CHECK,WEBUI_PROJECT_LOOKUP,WEBUI_SQL_PROPOSE`.
Restrict Access Control to the demo administrator. Use Native function calling
and a new conversation. OAuth WEBUI_URL/callback must be correct for your browser;
a localhost/SSH flow is not guaranteed to work with every OAuth deployment.

Start with a health check without arguments. Then ask:

> Call WEBUI_SQL_PROPOSE: how many distinct employees actually took annual leave
> during 2025, and how many days in total? Show the unexecuted SQL, without numeric results.

Open the actual tool output. It must contain `PROPOSAL_ONLY`, `executed:false`,
and `sql_validation:NOT_VALIDATED`. Only manual execution returns database results.

## References

- [Oracle MCP setup and endpoints](https://docs.oracle.com/en/cloud/paas/autonomous-database/serverless/adbsb/use-mcp-server.html)
- [Oracle Resource Principal](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/resource-principal.html)
- [Select AI API](https://docs.oracle.com/en/cloud/paas/autonomous-database/serverless/adbsb/dbms-cloud-ai-package.html)
- [Open WebUI MCP/OAuth](https://docs.openwebui.com/features/extensibility/mcp/)
