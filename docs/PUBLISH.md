# Publishing to GitHub

The original sharing branch was `codex/shareable-demo`; its pull request has been
merged. The English update is on `codex/english-version`. Preparing or editing
local files does not publish them: review, commit, and push are separate actions.
Keep the repository private until the owner decides on licensing and access.

Run commands only from this standalone repository, not its parent workspace:

```bash
git status --short
git branch --show-current
python3 scripts/check_share.py
git diff --check
git add README.md .env.example .gitignore compose.example.yaml config docs oci-gateway scripts sql tests SOURCE-MANIFEST.sha256
git diff --cached --stat
git diff --cached
python3 scripts/check_share.py
```

Review every staged file, including synthetic test examples. A dedicated secret
scanner and history review are also recommended; the heuristic is not exhaustive.
Do not display or paste a diff if you have added a real secret locally.

Only after review, using your own Git identity and authorization:

```bash
git commit -m "Translate documentation and demo text into English"
git fetch origin && git merge --no-edit origin/main
```

The local branch was created from the original sharing commit with the translated
files preserved. Fetch the current remote state and merge `origin/main` only after
committing the reviewed translation. If fetching fails or merging reports conflicts,
stop before pushing and inspect the output. Do not force-push or discard changes.

After a successful merge, recheck the content before publishing:

```bash
python3 scripts/check_share.py
shasum -a 256 -c SOURCE-MANIFEST.sha256
git status --short
git push -u origin codex/english-version
```

If the manifest check fails because newer files were merged from `main`, review
those changes and refresh the manifest before pushing. Open a new pull request
with base `main` and compare `codex/english-version`. Keep merging that request
and repository visibility changes as separate, deliberate decisions.

For HTTPS authentication, enter your GitHub username and an appropriately scoped
personal access token at the password prompt, not your account password. Never
put the token in a remote URL, a command, a tracked file, or a chat message.

`SOURCE-MANIFEST.sha256` records the hashes of the distributed source files. Refresh
it when preparing a changed release. ZIP exports contain reviewed source only,
without `.git`, real `.env` files, caches, or wallets. After local edits, regenerate
and review the ZIP before sharing it; old ZIPs are not synchronized automatically.
