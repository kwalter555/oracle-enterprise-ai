"""Create fresh local secrets without printing them or overwriting existing files."""
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def create_env(root=ROOT):
    root = Path(root)
    content = (root / '.env.example').read_text()
    for name in ('OCI_GATEWAY_KEY', 'POSTGRES_PASSWORD', 'WEBUI_SECRET_KEY'):
        marker = f'{name}=__GENERATE_64_HEX__'
        if content.count(marker) != 1:
            raise ValueError('Unexpected template; no file written')
        content = content.replace(marker, f'{name}={secrets.token_hex(32)}')
    fd = os.open(root / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)


if __name__ == '__main__':
    try:
        create_env()
    except FileExistsError:
        raise SystemExit('STOP: .env already exists; nothing overwritten.')
    print('Created local .env (0600). Set your OCI compartment, region and WebUI URL. No secrets printed.')
