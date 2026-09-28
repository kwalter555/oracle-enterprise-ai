"""Validate a local demo .env without network requests or printing values."""
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def validate(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing symlink .env')
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('.env must not be group/world accessible; use chmod 600 .env')
    values = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        k, sep, v = line.partition('=')
        if not sep or k in values:
            raise ValueError('Malformed or duplicate .env entry')
        values[k] = v
    for key in ('OCI_GATEWAY_KEY', 'POSTGRES_PASSWORD', 'WEBUI_SECRET_KEY'):
        value = values.get(key, '')
        if not re.fullmatch(r'[0-9a-f]{64}', value) or len(set(value)) < 8:
            raise ValueError(f'{key}: expected a fresh randomly generated 64-character hex value')
    if len({values[k] for k in ('OCI_GATEWAY_KEY','POSTGRES_PASSWORD','WEBUI_SECRET_KEY')}) != 3:
        raise ValueError('Secrets must be distinct')
    if not re.fullmatch(r'ocid1\.compartment\.[a-z0-9-]+\.\.[a-z0-9]{20,}', values.get('OCI_COMPARTMENT_ID','')):
        raise ValueError('Set your own OCI_COMPARTMENT_ID')
    if not re.fullmatch(r'[a-z]+-[a-z0-9-]+-[0-9]+', values.get('OCI_REGION','')):
        raise ValueError('Set a valid OCI_REGION')
    url = urlsplit(values.get('WEBUI_URL',''))
    if url.username or url.password or url.query or url.fragment or not url.hostname:
        raise ValueError('WEBUI_URL must be an origin without credentials/query/fragment')
    if url.scheme != 'https' and not (url.scheme=='http' and url.hostname in ('localhost','127.0.0.1')):
        raise ValueError('Use HTTPS except for localhost-only access')
    if values.get('ENABLE_SIGNUP') not in ('true','false'):
        raise ValueError('ENABLE_SIGNUP must be true or false')


if __name__ == '__main__':
    try:
        validate(ROOT / '.env')
    except (ValueError, OSError) as exc:
        # Do not print OSError paths or configuration values.
        raise SystemExit(str(exc) if isinstance(exc, ValueError) else 'Cannot read local .env')
    print('Configuration format/permissions: OK. OCI credentials, IAM and services have NOT been tested.')
