# Historical test fixtures — do not install

These two SQL files are preserved solely as inputs to the gateway regression
tests. They define an older three-row literal-data example with the same function
name as the newer database demo. **Do not run these files in Oracle.**

Install only the documented scripts under `sql/`, following `docs/DATABASE-MCP.md`.
`baseline.py`, `native_support.py` and `prepare.py` in the parent directory are
also regression-test fixtures, not deployment instructions. Only `app.py` is
copied into the gateway image.
