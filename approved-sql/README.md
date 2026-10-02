# Approved SQL execution — restricted demo pilot

Status: prepared and offline-tested source; **not deployed or live-certified**.
Designed for the existing Open WebUI **v0.11.3** application. Start with the
read-only host inventory in step 1 and review its output before continuing.
Do not replace the running application's Compose files, gateway or MCP tools.
All artifacts and examples are in English; questions and answers may be Croatian.

## What changes

A separate private service and one administrator-only Python Tool provide:

1. A natural-language question goes to the existing fixed Select AI proposal function.
2. A deliberately small SQL policy rejects unsupported proposals, then produces
   canonical Oracle SQL. The exact canonical SQL and fingerprint appear in a
   browser confirmation dialog, **before an analytical query runs**.
3. A positive click signs a five-minute, one-use approval bound to the SQL,
   requesting user and chat. Chat text such as "approved" cannot authorize it.
4. The service executes the stored SQL as a separate SELECT-only account and
   returns actual rows to the selected model for a natural-language answer.

Generation calls the configured Select AI model **before** query approval and may
incur charges. Approval is for execution and subsequent disclosure of results to
the selected chat model; the prompt/schema generation itself is not approval-gated.
This pilot is for the five **synthetic** `WEBUI_MCP.DEMO_A_*` tables only (snapshot
2026-09-24). It is not authorization to query real employee or business records.
Selected chat models may process results externally; review provider terms/region.

The existing `WEBUI_SQL_PROPOSE`, project lookup, health check, Select AI profile,
gateway and database data are unchanged. This is a native Python WebUI Tool, **not**
a new general-purpose MCP SQL executor. It uses the same existing proposal function
through a separate database connection. It does not use the existing OAuth token.

## Prerequisites and trust boundary

- A running Ubuntu VM with Docker Compose v2, the existing two Compose files,
  WebUI v0.11.3, and network access from that VM to the database's mTLS endpoint.
  A successful MCP HTTPS connection does not itself prove direct SQL/mTLS access.
- Existing `DEMO_AI_READER.DEMO_AI_SQL_PROPOSAL` is VALID and uses profile
  `DEMO_ANALYTICS_OCI`. Know that account's database password locally.
- A wallet from **your** database, including `ewallet.pem` and `tnsnames.ora`,
  its download password, and its `_low` service alias. No wallet is included.
- One trusted WebUI administrator for the pilot. You need their exact internal
  user ID, not their email/name. In the logged-in browser, inspect the JSON response
  to `/api/v1/auths/` in Developer Tools → Network and copy only `id` locally.
  Never share authentication headers, tokens, cookies or the complete response.
- No untrusted code-execution, terminal, Python tools, plugins or filters running
  in the WebUI backend. Host/Docker administrators, plugin editors and tool
  administrators can access the signing keys and are **trusted**. This design
  does not defend against a compromised WebUI server or a malicious administrator.
- Tool access and editing must remain private to the pilot administrator. Do not
  publish it or grant others write access. Do not export configured Valves.

## 1. Read-only inventory — run this first

Transfer `oci-approved-sql-kit-20260930.zip` to the existing application directory.
The ZIP creates a **new** `oci-approved-sql-kit/` directory; never overlay it onto
`oci-gateway/` or another kit. On the VM:

```bash
cd /home/ubuntu/enterprise-ai-demo
test ! -e oci-approved-sql-kit && unzip oci-approved-sql-kit-20260930.zip
cd oci-approved-sql-kit
python3 verify.py
python3 preflight.py --project-dir /home/ubuntu/enterprise-ai-demo
```

If anything reports STOP, do not continue. Send only the non-secret inventory output
for review. It prints the WebUI image, Docker network names, gateway checksum and
checks for the reviewed injected-argument/session-ownership guard markers; it does
not guarantee the entire installed image is unmodified. No changes or model calls.
If the target directory already exists, stop and inspect instead of extracting over it.

## 2. Create the dedicated executor in your database

After inventory review, open SQL Developer on the **ADMIN** connection. Use
Create User to create **DEMO_SQL_EXECUTOR**, with your own strong password,
default tablespace DATA, no quotas, no roles, no extra system privileges,
and no forced password expiry. Do not send or put its password in a SQL file.

In a new ADMIN worksheet run `01-admin-executor-grants.sql` with **Run Script / F5**.
Expected result: one `CREATE SESSION` system privilege, no roles, five `SELECT`
object grants without grant option. The script checks first, will not reset an
existing account, and refuses unexpected grants/objects. Oracle grants auto-commit;
if a mid-script error occurs, inspect the partial state before rerunning. No
automatic destructive cleanup is supplied. Do not enable a resource principal,
Select AI profile, CREATE PROCEDURE or generic SQL tools for this new executor.

## 3. Configure private files locally on the VM

Place your wallet ZIP in a private VM directory outside any Git checkout. Protect
the original ZIP with mode 0600. The installer does not delete or upload it.

```bash
cd /home/ubuntu/enterprise-ai-demo/oci-approved-sql-kit
sudo python3 configure.py
```

Enter the existing WebUI network name from step 1, your exact WebUI administrator
ID, low-service alias, wallet path and the three locally prompted passwords.
Passwords are not echoed or placed on command lines. The script refuses existing
configuration, generates two independent keys, and writes:

- `private/sql-review.json`: mode 0600, owned by container UID/GID 10001;
- `private/client-config/`: only the two required thin-driver client files;
- `.env`: the existing Docker network name only.

Execution is initially **disabled**. Do not paste these private files into chat,
commit them, include them in Terraform variables, or share a configured bundle.
`config.example.json` contains placeholders, not working credentials.

## 4. Start only the new service; verify database metadata

```bash
sudo docker compose -f compose.approved-sql.yaml build
sudo docker compose -f compose.approved-sql.yaml up -d
sudo docker compose -f compose.approved-sql.yaml ps
sudo docker compose -f compose.approved-sql.yaml exec -T sql-review python check.py --database
```

These commands use their own Compose project `oci-approved-sql-demo` and join an
existing network without recreating WebUI, the gateway or PostgreSQL. No host port
is published. Building downloads dependencies; the health check is local HTTP only.
The database check opens the two accounts and queries fixed metadata, not demo
data or a model. It must report PASS. If it fails, keep execution disabled; check
local credentials, database ACL/firewall, mTLS wallet/service and grants. Do not
open SQL ports to the entire Internet to fix connectivity. Share only sanitized
error type/code if troubleshooting is needed.

## 5. Install the WebUI Tool and test the preview dialog

As the pilot administrator, open **Workspace → Tools → Create**, paste the entire
`webui_tool.py` file, save as `Approved Demo Database Query`, and keep access private.
Do not replace the existing MCP integration or create this as a Filter/Function.

In its administrator **Valves**, set `API_KEY` and `APPROVAL_KEY` by copying the
corresponding two values from `private/sql-review.json` using a local privileged
editor. The password-format editor is only display masking, **not encryption**.
The values are stored by WebUI; treat its database/backups and admin exports as
secrets. Database passwords and the wallet stay in the sidecar, not in the Tool.

Open a new **saved, interactive** chat. Set Function Calling to **Native** and
enable this Tool only for the test. Do not run through API-only clients, scheduled
tasks, channels or delegated agents. Use a fresh chat for each model/acceptance test.
Start with GPT-OSS, then test the other configured models separately. The gateway
has no new provider-specific logic, but this new UI flow still needs live testing.

Example prompt:

> Use ask_demo_database to find the actual recorded project costs grouped by the
> calendar year of COST_DATE. Use only actual tool results. Never claim execution
> when executed is false or null. Answer in Croatian after approval.

With execution disabled you should get a **Preview only** confirmation dialog.
Check that **all** SQL is visible/readable, including long SQL (scroll if necessary),
and that confirmation returns `PREVIEW_ONLY` with `executed:false`. Cancel must
return `DENIED`. Closing/disconnecting the tab or an expired request must not run
an analytical query. If SQL is truncated, the dialog is missing, or confirmation
behaves unexpectedly, **do not enable execution**. No frontend rendering test has
been performed against your live installation by the package author.

## 6. Explicitly enable the pilot, then perform live acceptance

Only after the preceding checks succeed, use a privileged local editor to change
**only** `execution_enabled` to `true` in `private/sql-review.json`. Keep the file's
owner 10001:10001 and mode 0600; verify with `sudo stat` after saving. Restart only
the new service so it reloads configuration:

```bash
sudo docker compose -f compose.approved-sql.yaml restart sql-review
sudo docker compose -f compose.approved-sql.yaml exec -T sql-review python check.py --database
```

In new chats, test in this order:

1. Ask a query, **cancel**, verify `executed:false`. The local audit must have
   DENIED and no APPROVED_AND_CLAIMED/SUCCEEDED for that proposal.
2. Ask again, review the SQL, **approve once**. Verify tool output has
   `status:SUCCEEDED`, `executed:true`, the matching proposal hash and actual rows.
3. For the original, unchanged synthetic dataset verify:
   - projects **started in calendar 2025**: 18;
   - recorded costs by COST_DATE year: 2025 = 185523 EUR, 2026 = 288176 EUR;
   - total recorded costs: 473699 EUR;
   - calendar-2025 leave where LEAVE_TYPE='GODISNJI' and
     LEAVE_STATUS='ISKORISTEN': 20 distinct employees, 100 days.
4. Test a disallowed request such as deleting projects: it must not execute.
   Generation may instead propose a harmless SELECT; inspect what actually happened.
5. Check blocked access for a non-admin/non-allowlisted account, timeout/disconnect,
   and verify another click/retry cannot reuse an already consumed proposal.
6. Repeat the approved/cancelled path for each configured model. Model summaries
   can still be wrong: compare the actual Tool rows, not just the prose.

For non-secret local audit events (last 20):

```bash
sudo docker compose -f compose.approved-sql.yaml exec -T sql-review python check.py --audit
```

On failure, never automatically retry an execution. It may have completed even if
the response was lost; a new question and fresh approval are required.

## Limits and known boundaries

- Supported SQL: one SELECT over 1–5 explicitly qualified allowed tables, selected
  columns, simple filters, JOIN ON, aggregates, CASE, GROUP/HAVING/ORDER, ISO date
  literals and YEAR/MONTH/DAY extraction. Unsupported SQL fails closed. No arbitrary
  functions, packages, links, comments/hints, CTEs, subqueries, unions, SELECT *,
  SELECT INTO, FOR UPDATE, DML, DDL or PL/SQL. SQLGlot is **not** a security validator;
  explicit AST allowlists and database privileges are separate layers. Widening the
  allowlist or changing source tables requires review and new regression tests.
- No query against views, VPD-policy tables, virtual/user-defined-type columns in
  this pilot. Runtime checks recheck direct privileges, roles and table metadata.
  Oracle PUBLIC privileges still exist; this is not a complete PUBLIC/package audit.
- A new unpooled executor connection starts with `SET TRANSACTION READ ONLY`.
  No generated SQL executes in the Select AI proposal account. No write tools.
- One database operation at a time; 30 generation attempts per user/hour including
  failed attempts. This limits accidents, not provider billing or hostile admins.
- 100 returned rows, fetch of 101 to detect truncation, 20 result columns, 2000
  characters per string, 64 KB result-data limit. `truncated:true` means incomplete
  detail rows, not permission to invent totals. Oracle decimals may be JSON strings
  to preserve precision. These are output limits, not limits on rows Oracle scans.
- 15-second analytical operation deadline with best-effort cancellation plus
  per-round-trip timeout; connection establishment has a separate timeout.
  This is **not a guaranteed database CPU/resource cutoff**. Configure database
  resource management separately before larger/production workloads. Proposal
  generation gets 60 seconds. Low service is required.
- Confirmation expires after five minutes; browser wait is at most four minutes
  and may time out earlier under WebUI's websocket settings. Only a boolean true
  from the interactive callback authorizes; strings/error objects do not.
- SQLite persists one-use state before contacting Oracle. Crashes leave a consumed
  approval, never a retryable one. Keep its volume; do not run multiple replicas.
  Audit is local, not immutable/compliance-grade. Questions/SQL are nulled after
  expiry and events older than 30 days are pruned **when another proposal is created**;
  it is not a scheduled erasure guarantee or forensic secure deletion. WebUI keeps
  its own chats/tool output under its retention settings. Encrypt private backups.

## Disable / recovery

Disable this Tool in WebUI and stop the sidecar:

```bash
sudo docker compose -f compose.approved-sql.yaml stop sql-review
```

This does not undo an already completed read or erase chat results. An in-flight
database request might continue until cancelled/timed out. For credential compromise
the database administrator should lock the dedicated executor account and rotate
the private keys/passwords; assess the separate proposal account too. Do not delete
the audit volume, wallet, existing backups or any tables. Existing proposal-only
MCP tools continue to work. To return to preview mode, set execution_enabled=false
locally and restart the sidecar. No automatic DROP/REVOKE rollback is included.

## Offline developer validation

In a separate Python 3.12 environment (not the active gateway environment):

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python test_approved_sql.py -v
```

Tests use mocked Oracle operations and in-process HTTP; no real models or database.
Container build, actual Oracle SQL/grants, wallet connectivity and browser acceptance
remain deployment checks. Direct dependencies are pinned; the base image and
transitive dependencies are not a fully reproducible, vulnerability-audited supply
chain. Review/scan the built image and record its digest before wider use.

## GitHub and Terraform

Commit source `approved-sql/` only after the repository sharing check; never the
configured VM directory. The Resource Manager source bundle includes this optional
directory, but Terraform **does not** create the executor, install this Tool, store
these passwords or enable execution. On a fresh Stack, first finish the existing
manual analytics/Select AI setup, then follow this runbook. The older 20260929
Stack ZIP remains unchanged and does not contain this add-on.

References: [WebUI interactive events](https://docs.openwebui.com/features/extensibility/plugin/development/events/),
[reviewed WebUI v0.11.3 implementation](https://github.com/open-webui/open-webui/tree/v0.11.3),
[python-oracledb connection API](https://python-oracledb.readthedocs.io/en/latest/api_manual/connection.html),
[Oracle received object grants](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/USER_TAB_PRIVS_RECD.html).
