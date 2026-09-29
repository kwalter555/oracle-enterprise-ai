# Sanitized package validation

Initial validation: 2026-09-25. English translation recheck: 2026-09-28.
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

This record distinguishes local evidence from the previously user-verified demo.
It is not proof that the package has been installed or published to GitHub.
