# Sanitized package validation

## Architecture and public deployment-button integration — 2026-10-02

25 repository/Stack tests passed, including four new tests for editable diagram
references, the complete public main-branch archive link, the exact reviewed PNG
and rejection of modified/unlisted images. Five SQL proposal tests, 26 approved-SQL
tests, 63 gateway offline tests and synthetic data reference checks passed again.
Terraform formatting and local validation passed with Terraform 1.5.7 / OCI 9.7.1.
No OCI Plan, Apply, model call or database connection was made.

The 140-cell draw.io XML parsed with unique IDs. The PNG was exported using
draw.io desktop and visually inspected after removing overlapping stock stencil
captions. Its only PNG chunk types are IHDR, IDAT and IEND: no text metadata or
embedded document. The sharing gate admits only its reviewed path and digest.
The source manifest and distribution archive are checked by the ZIP builder.

The deploy link follows Oracle's documented format and targets public `main`.
It must not be used until this integration is merged. The authenticated OCI
Console import, working-directory selector, schema rendering and deployment
have not been exercised; the documented complete-ZIP workflow is the fallback.

## Fresh-tenancy ATP package — 2026-10-02

The database workload was corrected from DW to OLTP for the 20 GB default.
Terraform 1.5.7 `fmt -check` and `validate` passed with the cached OCI 9.7.1
provider. The initial sandbox provider launch failed; the same read-only local
validation succeeded outside the sandbox. This was not an OCI Plan or Apply.

21 repository/Stack tests (including two new sizing/cost-flag regressions),
5 SQL proposal artifact tests, 26 approved-execution tests and 63 gateway offline
tests passed. Synthetic demo data reference checks passed. The Console YAML
parsed, covered all 21 Terraform variables, and matched the 2 ECPU/20 GB and
disabled MCP/cost-acknowledgement defaults. The earlier full meta-schema check
was not repeated for this text-only Console form update. Sharing checks and
distribution hash/integrity verification are required by the ZIP builder.

No fresh VM build, Oracle SQL compilation, model availability test, OCI Plan/Apply,
EUR account-price verification, or new-tenancy runtime test was performed. The
monthly budget and 20-hour weekly use assumptions are not enforcement controls.
No automatic start/stop schedule, budget alert or new cloud resource was installed.
Earlier validation entries below are historical evidence, not live acceptance
of this new tenancy. Deprecation warnings remain as documented previously.

Initial validation: 2026-09-25. English translation recheck: 2026-09-28.
Resource Manager addition and regression recheck: 2026-09-29.
No production database access, OCI model calls, or VM changes.

| Check | Result |
|---|---|
| Gateway offline regressions | 63 tests passed; mocked HTTP/signing, socket and DNS blocked. |
| Sharing/secrets/environment generator | 4 tests passed, including overwrite refusal and permissions 0600. |
| SQL proposal static checks | 5 tests passed; not Oracle compilation. |
| Demo data | Offline SQLite reference checks passed: foreign keys, dates, record counts, and aggregates. |
| Python | AST syntax checks passed for included Python sources. |
| Compose | YAML parsing and structural checks passed: loopback-only WebUI port; no published gateway/PostgreSQL ports. |
| JSON/profile templates | JSON parsing, the five-table allowlist, and compartment placeholder checked. |
| Gateway integrity | app.py matches the verified local source and previously reported VM hash. |
| Git ignore | Sample environment, wallet, private-key, backup, and local SQL files correctly ignored. |
| Heuristic content scan | Passed for Git-visible files; matched values are never printed. |
| Stack/bootstrap/distribution regressions | 15 additional tests passed: input/template guards, no environment overwrite, permissions, source-only packaging, manifest coverage, tamper refusal and ZIP reproducibility. |
| Terraform formatting and provider schema | `fmt -check` and `validate` passed with Terraform 1.5.7 and OCI provider 9.7.1. Provider initialization downloaded the signed provider; no OCI Plan/Apply. |
| Stack Console form | YAML parsed and validated against Oracle's published Resource Manager meta schema; all 21 Terraform variables covered by the form/groups. No live Console upload tested. |
| Rendered cloud-init | Terraform console with synthetic inputs: compressed metadata 27,260 bytes for the test key; 9 bundled source files matched originals; database password absent. A 30,000-byte guard leaves margin below OCI's 32,000-byte limit. |
| Terraform input rejection | 14 invalid synthetic inputs rejected, including broad/private/invalid IPs, a private-key header, invalid password formats and a tenancy OCID in the compartment field. |

Gateway test runtime: Python 3.12.14; LiteLLM 1.101.0, OCI 2.185.2,
FastAPI 0.141.1, Uvicorn 0.53.0. Expected provider errors appear deliberately in
negative-test output. A warning about a future httpx replacement in Starlette's
TestClient was observed; dependency pins are not changed without separate compatibility tests.

The translation retains stored category codes and the database/tool interfaces.
English natural-language prompts have not been retested against a live model.
Existing deployments are not modified by these source changes.

## Not verified by this testing

- Docker Compose CLI schema/build/start: Docker is unavailable in the preparation environment.
- Fresh WebUI/PostgreSQL/gateway installation and first-admin authentication.
- The recipient's OCI IAM, regions, models, and networking; no billable inference tests.
- Bootstrap and translated SQL execution/compilation in a new Oracle database.
- OAuth callback/MCP authorization in a new installation.
- A complete dependency vulnerability/license audit or dedicated secret-scanner audit.
- Current remote VM contents, data backups, or recovery testing.
- Resource Manager Console rendering, live Terraform Plan/Apply, regional capacity,
  cloud-init boot/package installation, database creation and IAM propagation.

The Stack's local tests do not prove OCI API acceptance for every combination of
region, size, shape and account entitlement. Source-only distribution excludes
Terraform state, plans, actual variable values and provider binaries. The database
ADMIN password will enter protected state only when the recipient deploys.

This record distinguishes local evidence from the previously user-verified demo.
It is not proof that the package has been installed or published to GitHub.

## Approved SQL pilot — 2026-09-30

26 additional offline unit/integration tests passed in a separate Python 3.12.14
environment with SQLGlot 30.20.0, python-oracledb 26.0.1, FastAPI 0.141.1,
Uvicorn 0.53.0 and httpx 0.28.1. The cases cover canonical SQL round trips and
negative syntax, exact-SQL/user/chat binding, signatures, expiry, persistent replay
rejection, concurrent claims, failed-query consumption, generation rate limits,
strict boolean UI approval, cancel/disconnect errors, preview mode, extra request
fields, private configuration, archive path checks and separate private deployment.
Oracle is mocked; metadata/grant checks and read-only execution ordering are tested
locally, not compiled or executed against a live Oracle instance. The existing
19 repository/Stack tests, 5 proposal-artifact tests, 63 gateway tests and synthetic
analytics reference checks were rerun successfully. Gateway source hash is unchanged.

The optional Compose document was parsed locally and its no-public-port/isolation
properties checked. Docker is unavailable here, so container build/start, actual
wallet authentication, Oracle metadata/grants and the WebUI confirmation dialog
remain required live acceptance tests. The package starts with execution disabled.
Dependency warnings about future Starlette/httpx compatibility remain; no active
gateway dependency was changed. No VM/DB/OCI changes or GitHub push were performed.
