# OCI Resource Manager Stack — fresh demo environment

This package prepares **new, paid infrastructure** in your own OCI tenancy. It
does not import, update, or back up an existing deployment. No credentials from
the original environment are included. All deployment steps below are performed
by you; building this source package does not create a Stack in OCI.

## Scope

| Created by Terraform | Deliberately manual |
|---|---|
| VCN, Internet Gateway, route, restricted security list, public subnet | Application startup and first WebUI administrator |
| Ubuntu 24.04 x86 VM, public IP, retained boot volume | SQL users, grants, demo tables, Select AI profile and MCP tools |
| Docker/Compose packages and this package's application files on the VM | Wallet download to your own computer, OAuth login and integration testing |
| New paid Autonomous Transaction Processing database (OLTP, ECPU, mTLS) | Model availability, quota, processing terms and billable inference tests |
| Optional exact-resource dynamic groups and GenAI policy | Backups, recovery tests and production hardening |

Defaults: VM E4 Flex, 2 OCPUs, 16 GB RAM, 100 GB boot disk; database 2 ECPUs,
20 GB Transaction Processing storage, license included, autoscaling off. These are **not Always Free**.
Estimate charges in your tenancy before accepting the cost acknowledgement.
Regional capacity, service limits and account eligibility are not established by
local validation. No Object Storage bucket, load balancer, dedicated GenAI
endpoint, public HTTPS service, or automatic SQL execution is included.

### October 2026 correction and intermittent demo use

Use the **2026-10-02 ATP distribution** for a fresh deployment. Earlier Stack
packages incorrectly paired `DW` with 20 GB storage. This release uses `OLTP`;
Oracle documents a 20 GB minimum for Transaction Processing and a 1 TB minimum
for Lakehouse/Data Warehouse. See [compute and storage models](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/autonomous-compute-models.html).
Do not apply this change to an existing Stack/database to convert its workload.
Use a new Stack and review its Plan for new resources only. Existing SQL scripts
remain unchanged; their compilation, Select AI and MCP behavior must be tested
on the new database before acceptance.

For 20 hours of use per week, a planning allowance is approximately 87 hours per
month (20 * 52 / 12); this is not a schedule or a spending cap. Confirm EUR prices,
tax treatment and the projected total in the new account before Apply. Include
VM compute/memory, boot storage/performance, database compute/storage, backups,
Object Storage if added separately, and all model/embedding calls. A EUR 200
monthly target is not guaranteed by this configuration.

This Stack installs **no automatic start/stop schedule, budget alert or hard
spending limit**. Do not leave the deployment running continuously based on an
87-hour estimate. Stop the standard-shape VM through OCI Console/API, not only
by closing the browser, stopping Docker or shutting down the guest OS. Stop the
standard paid Autonomous database separately. Check both resources report
Stopped; persistent storage and backups remain chargeable. Resume deliberately
and verify application/database health before the next session. Do not force
stop a VM with active database writes. See [VM stopped-instance billing](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/resource-billing-stopped-instances.htm)
and [Autonomous billing](https://docs.oracle.com/en/cloud/paas/autonomous-database/serverless/adbsb/autonomous-features-billing.html).

Create budget alerts separately before normal use and review spending regularly.
Alerts are delayed notifications, not automatic shutdown controls. Agree on any
shutdown schedule before enabling it; a schedule can interrupt users and jobs.

## Prerequisites

- An existing, dedicated compartment in the commercial OCI realm (`oc1`).
- Your tenancy's home region and a deployment region with the required services.
- Your own SSH key pair; supply **only the public key** to the Stack.
- Your workstation's current public IPv4 address with `/32`, not a LAN address.
- A new, unique database name and a new ADMIN password held in your password manager.
- Sufficient OCI permissions and quotas. Your administrator must authorize the
  Resource Manager operator to create the listed network, instance, volume and
  Autonomous Database resources in the compartment, and read the image/region/AD
  information used by the selectors. IAM creation additionally requires rights
  to create tenancy dynamic groups and compartment policies. This package does
  not grant the operator permissions or bypass an organization's IAM rules.

The automatic IAM option targets the **default identity domain**. For a custom
domain or centrally managed IAM, set `create_iam=false` and use the manual IAM
section below. No OCI API signing key is embedded: Resource Manager supplies its
own provider authentication, and the application later uses Instance Principal.

## Deploy button (public GitHub repository)

Use the **Deploy to Oracle Cloud** button in the [repository README](../../README.md).
It loads the complete public repository archive from `main`. The archive must
contain this module: merge the reviewed integration before using the main-branch
button. No GitHub token, wallet, or private download URL belongs in the link.

1. Sign in to your **new** OCI tenancy and select the intended deployment region.
2. Verify the loaded source, choose your compartment and set **Working directory**
   to `infra/resource-manager` (inside GitHub's extracted repository directory,
   if that outer directory is shown). Keep the complete source tree: this module
   uses application files two levels above it.
3. Select Terraform **1.5.x** and complete the inputs described below.
4. **Clear “Run apply” on the review page.** The button workflow can select it
   automatically. Create only the Stack configuration, then run **Plan**.
5. Review the Plan and charges before choosing to Apply. Nothing in this package
   approves those actions for you.

If the Console cannot select the nested working directory, use the ZIP workflow
below; do not move the Terraform files away from their application sources. For
reproducible deployment, check out a reviewed commit and run
`python3 scripts/build_stack.py --output /path/outside/repository/stack.zip` from
the repository root, then upload that ZIP. The builder checks the source manifest
and refuses secrets, unreviewed binary files and overwritten archives.

The button follows [Oracle's documented format](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Tasks/deploybutton.htm).
The source URL must remain public; if repository visibility changes, use an
authorized Git configuration source or local ZIP upload instead.

## Create a Stack from the ZIP

1. Open **OCI Console → Developer Services → Resource Manager → Stacks** in your
   intended region/compartment, then **Create stack**.
2. Choose a ZIP configuration and upload the complete generated distribution.
   Do not upload only this subdirectory: VM source files come from `../../`.
3. Set **Working directory** to `infra/resource-manager` and Terraform version
   to **1.5.x**. The module requires Terraform 1.5 and pins OCI provider 9.7.1.
   Keep the included provider lock file. The English form comes from `schema.yaml`.
4. Select your compartment, actual tenancy home region and availability domain.
   Deployment region is inherited from the Stack's region. Use a unique
   environment prefix. Supply your public
   IPv4 `/32`, public SSH key and database ADMIN password. Review all sizes.
   Leave **Enable database MCP endpoint** off initially.
5. Review pricing/quotas and then check the cost acknowledgement. Leave any
   **Run apply** / immediate deployment option **off** when creating the Stack.
6. Run **Plan**, not Apply. Inspect every proposed resource: fresh resources only,
   SSH limited to your `/32`, database restricted to your IP and the new VM IP,
   no public application/database-container ports, expected IAM scope and sizes.
7. Only after accepting that Plan and the charges, run **Apply** on that reviewed
   plan. If Terraform requests replacement or deletion of anything, stop.

The same complete repository layout may be used with a Resource Manager Git
configuration source. Select a reviewed commit/branch containing these files and
the same working directory. Authenticate a private repository through your own
OCI configuration-source setup; never place a GitHub token in Terraform files.
Creating this local branch does not publish it to GitHub.

The configuration is based on Oracle's [Resource Manager packaging guidance](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Concepts/terraformconfigresourcemanager.htm)
and [supported Terraform versions](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Reference/terraformversions.htm).

## Verify the new VM, then start the application

Apply completion is **not** proof that cloud-init or the application succeeded.
Use the returned VM address and your own private key to connect as `ubuntu`.
Run on the new VM:

```bash
sudo cloud-init status --wait
sudo test -f /opt/oracle-enterprise-ai/bootstrap.READY
sudo docker compose version
```

Continue only if cloud-init reports success, the marker exists and Compose v2 is
available. Cloud-init installs packages, copies reviewed source files, generates
three random local secrets in a root-only `.env`, checks configuration, and stops.
It neither launches containers nor calls models. A rerun refuses to overwrite
an existing `.env`. Do not delete that file to force a retry; inspect the failure.

Start services deliberately on this **new VM only**:

```bash
sudo -i
cd /opt/oracle-enterprise-ai
python3 scripts/check_config.py
docker compose --env-file .env -f compose.example.yaml config --quiet
docker compose --env-file .env -f compose.example.yaml up -d --build
docker compose --env-file .env -f compose.example.yaml ps
exit
```

The first build downloads packages/images. Do not use `docker compose config`
without `--quiet` in shared output, because it can reveal environment secrets.
Check cloud-init/container logs locally if startup fails; redact secrets and
identifiers before sharing. IAM propagation can delay gateway readiness.

On your computer, use the `ssh_tunnel` output, replacing the private-key path:

```bash
ssh -i /path/to/your-private-key -L 3000:127.0.0.1:3000 ubuntu@YOUR_VM_PUBLIC_IP
```

Keep the tunnel open and visit `http://localhost:3000`. Create your first admin
account privately, then disable sign-ups in WebUI and set `ENABLE_SIGNUP=false`
in the VM's existing `.env` without regenerating its secrets. From a root shell
in `/opt/oracle-enterprise-ai`, run `docker compose --env-file .env -f
compose.example.yaml up -d --no-deps open-webui` and verify sign-up is disabled.
See the [setup guide](../../docs/SETUP.md) for persisted WebUI setting caveats.
Docker image tags and application dependencies are pinned to the demo versions;
the Terraform provider pin does not imply a dependency vulnerability audit.

## Database and MCP setup

1. Connect to the **new** database using Database Actions or SQL Developer and
   your own ADMIN credentials. Download its wallet from OCI if needed and keep
   it outside this repository. Wallet and database-account passwords differ.
2. Follow [DATABASE-MCP](../../docs/DATABASE-MCP.md) in order. Verify the new
   database has the required `DBMS_CLOUD_AI` and `DBMS_CLOUD_AI_AGENT` features.
   Use `WEBUI_MCP` for demo ownership/tools and the restricted `DEMO_AI_READER`
   account for analytics. Do not make the application an ADMIN client.
3. Substitute your new compartment and selected GenAI region in local SQL/profile
   configuration; preserve the original sharing templates. The Stack does not
   create SQL accounts, enable database Resource Principal, or install profiles.
4. After grants/tools have been reviewed, set `enable_mcp=true` in the Stack,
   inspect a new Plan and apply only the intended database tag update. The MCP
   endpoint output follows Oracle's [MCP endpoint format](https://docs.oracle.com/en/cloud/paas/autonomous-database/serverless/adbsb/use-mcp-server.html).
5. Add that endpoint in WebUI, complete your own OAuth registration/authorization,
   and restrict the tool filter to the demo tools you intend to expose. Verify
   the callback and database access from your actual browser/VM; they have not
   been exercised by offline tests. Never add an all-address database allowlist
   merely to work around an OAuth/network failure.
6. Test the health tool, project lookup and SQL proposal tool individually. Use
   Native function calling for each model being tested. Model calls are billable.

`WEBUI_SQL_PROPOSE` still returns **unexecuted SQL**. Chat approval does not execute
it; a human reviews and runs the exact SQL as `DEMO_AI_READER`. This Stack does
not implement automatic natural-language SQL execution as part of provisioning.
An optional [approved-execution pilot](../../approved-sql/README.md) is included in
the updated source repository. Install it separately only after the base SQL/MCP
setup is verified. It is disabled by default and adds per-query interactive review;
Terraform does not manage its credentials, executor grants, Tool or activation.

## Manual IAM alternative

With `create_iam=false`, the VM/database can be provisioned but model access will
not work until your IAM administrator configures it. Use the two exact matching
rules in the Stack outputs, one for the new VM and one for the new database.
Do not substitute a rule matching every resource in the compartment.

After creating the dynamic groups in the intended identity domain, the IAM
administrator can adapt these compartment-scoped statements using their OCIDs:

```text
Allow dynamic-group id <COMPUTE_DYNAMIC_GROUP_OCID> to use generative-ai-chat in compartment id <DEMO_COMPARTMENT_OCID>
Allow dynamic-group id <COMPUTE_DYNAMIC_GROUP_OCID> to use generative-ai-text-embedding in compartment id <DEMO_COMPARTMENT_OCID>
Allow dynamic-group id <ADB_DYNAMIC_GROUP_OCID> to use generative-ai-chat in compartment id <DEMO_COMPARTMENT_OCID>
```

Identity-domain support, policy placement, propagation and model availability
must be verified in that tenancy. Do not compensate for failures with tenancy-wide
`manage all-resources`. The separate SQL Resource Principal/grants remain necessary.

## Security, updates and recovery boundaries

- The database ADMIN password is sensitive but **is stored in Terraform state**.
  Restrict Resource Manager access and protect state exports and plans. Hiding
  the Console View State button is not an IAM control or encryption guarantee.
  Never commit state, plans, real `.tfvars`, passwords, `.env`, wallets or keys.
- Application secrets are generated on the VM, not stored in user-data or Terraform
  outputs. Root/host administrators can access them. Source files in user-data are
  sanitized, not confidential. Terraform contains no private SSH key.
- Inbound VM access is SSH from one `/32`; Docker publishes WebUI only on loopback.
  Database service access is allowlisted to that `/32` and the new VM's `/32`.
  Outbound VM traffic is unrestricted for demo package downloads and OCI services;
  production egress filtering, private endpoints and public HTTPS are not included.
- A changed workstation public IP requires a reviewed Stack variable/Plan update.
  Changing `admin_cidr` is not permission to widen it to an entire network.
- VM and database have `prevent_destroy`. The boot volume is also retained on VM
  termination. These controls are **not backups**, and retained volumes cost money.
  Deleting a resource block removes its lifecycle guard; preserve/review the code.
- The latest compatible Ubuntu image is chosen on initial creation. Subsequent
  image-catalog changes are ignored for that VM. Updating cloud-init metadata does
  not redeploy the running application; software maintenance is a separate reviewed
  operation. This is not a rolling-upgrade or migration system.
- Before any deliberate teardown, export/verify required backups, inspect the Plan,
  and explicitly authorize removal of the lifecycle protections. Do not force
  destruction to resolve a deployment error. No automated teardown script is supplied.
- PostgreSQL/WebUI data live on the VM boot disk; SQL data live in the new ADB.
  Git/source ZIPs contain neither. Retention, recovery, monitoring, budgets and
  production security need a separate operational plan.

## Local checks and distribution build

```bash
terraform -chdir=infra/resource-manager init -backend=false
terraform -chdir=infra/resource-manager fmt -check
terraform -chdir=infra/resource-manager validate
python3 -m unittest discover -s tests -v
python3 scripts/check_share.py
```

Provider installation requires internet access; validation is not an OCI Plan.
Keep the source manifest current after reviewed edits, then build outside the repo:

```bash
python3 scripts/build_stack.py --output ../oracle-enterprise-ai-resource-manager.zip
```

The builder checks sharing rules, exact manifest coverage and hashes, rejects
overwrites, preserves the complete source layout and verifies ZIP integrity.
See [validation evidence and limitations](../../docs/VALIDATION.md). No live
Terraform Plan/Apply, fresh VM boot, Docker build or new ADB installation was
performed when this source package was prepared.
