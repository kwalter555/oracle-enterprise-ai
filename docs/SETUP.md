# Setting up your own demo environment

## 1. What you need to provide

Your own OCI tenancy/compartment, GenAI access and quotas, a Linux Compute VM with
Docker/Compose v2, and outbound HTTPS access to the required services. The gateway
authenticates using that VM's Instance Principal; do not copy anyone else's API
keys. The instance metadata service must be reachable from the gateway container.
Do not expose it to untrusted applications or grant the instance broad IAM permissions.

Use a separate new directory and VM, or at least a separate Compose project. This
template is not an application migration. There is no automated rollback/restore.

Create a Compute dynamic group matching the exact instance OCID and the two
compartment-scoped policies in `config/iam-policy.example.txt`. Check the identity
domain, model availability, and policy propagation. The ADB dynamic group is a
separate group, needed only for Select AI. Do not combine them into one broad group.

The template uses Frankfurt as a public example region. Models and limits are
not available in every region. Check the current OCI catalog and external-processing terms.

## 2. Secrets and configuration

From the repository root, `python3 scripts/init_env.py` creates `.env` with three
distinct random secrets without printing them. It creates the file only if it
does not exist, with permissions 0600. It does not create OCI or Oracle credentials.

Edit locally:

- `OCI_REGION`: the region where you use GenAI.
- `OCI_COMPARTMENT_ID`: your GenAI compartment, not a database or VM OCID.
- `WEBUI_URL`: the address your browser will use. Local tunneling can use
  `http://localhost:3000`; for remote access, set the actual HTTPS origin and a
  secure reverse proxy. An HTTPS proxy is not included in this package.
- Keep the three generated secrets distinct. The PostgreSQL secret uses hex so
  it is safe inside `DATABASE_URL` without additional URL encoding.

`python3 scripts/check_config.py` validates format, not OCI access. Do not send
`.env`, `docker inspect` output, or full `docker compose config` output to chat or
Git: resolved configuration may contain secrets. Use `config --quiet`.

## 3. Startup and first connection

Run the commands in the README. Image tags intentionally match the demo, but are
not pinned by digest. The base Python image and transitive Python dependencies
are not fully locked. This is not a bit-for-bit reproducible or security-audited
build. Before production, assess vulnerabilities, pin digests/dependencies, and
repeat compatibility checks; the adapter contains version-sensitive LiteLLM adaptations.

PostgreSQL and gateway ports are not published. WebUI binds to loopback only.
From your computer, create a tunnel using your own key and host address:

```bash
ssh -i /path/to/your-ssh-key -L 3000:127.0.0.1:3000 ubuntu@YOUR_VM_HOST
```

Open `http://localhost:3000` and create the first administrator account with your
own strong password. Until that account exists, do not share the tunnel/proxy or
allow other users access. Then disable new user registration in Admin settings
and set `ENABLE_SIGNUP=false` locally; apply the Compose change at an agreed time.
Verify that the UI no longer offers sign-up.

Open WebUI persists some settings in its database, which can override new
environment values. Check the Admin UI as well as `.env`. Do not delete a volume
to change a setting. Preserve `WEBUI_SECRET_KEY` privately: it also matters for
stored OAuth secrets.

In Admin Connections, check the OpenAI-compatible URL `http://oci-gateway:4000/v1`
and your gateway key from the local `.env`. Do not substitute an OpenAI API key
for this local key. Choose an allowed model and send a synthetic test prompt.
The call is billed to your OCI account. `/health` confirms initial adapter
authentication, not model availability or all IAM permissions.

## 4. Native tools, embeddings, and RAG

Test native tool calling separately for each selected model. The gateway accepts
at most 32 tool definitions per request; one MCP integration may expose several
tools. Filter to the tools you actually need and disable unnecessary built-in tools.

The `/v1/embeddings` API supports `cohere.embed-v4.0`, with `search_document` and
`search_query` input types. This Compose template does not configure the original
environment's complete RAG flow, Object Storage, Knowledge Base, or vector store.
Open WebUI may initialize its default embedding models; do not upload real
documents until you have verified your own RAG settings and data flow.

The original Object Storage configuration has not been reconstructed. It requires
separate templates and tests; none of the original bucket data is included here.

## 5. Database and MCP

Follow [DATABASE-MCP](DATABASE-MCP.md). A wallet is required only for the selected
SQL Developer connection method; the gateway does not use one. Register MCP OAuth
again in the new WebUI environment. Do not transfer the original application's
client credentials or tokens.

## References

- [Open WebUI environment reference](https://docs.openwebui.com/reference/env-configuration/)
- [Open WebUI MCP](https://docs.openwebui.com/features/extensibility/mcp/)
- [OCI GenAI permissions](https://docs.oracle.com/en-us/iaas/Content/generative-ai/model-permissions.htm)
