"""Fresh-VM configuration only: local secrets, no model calls or app startup.

Invoked by cloud-init as root after Ubuntu installs Docker and Compose.
No private credentials are embedded in Terraform user_data.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def configure(root):
    root = Path(root)
    settings = json.loads((root / 'stack-settings.json').read_text())
    region = settings['region']
    compartment = settings['compartment_id']
    if not re.fullmatch(r'[a-z]+-[a-z0-9-]+-[0-9]+', region):
        raise ValueError('Invalid region; no environment file written')
    if not re.fullmatch(r'ocid1\.compartment\.[a-z0-9-]+\.\.[a-z0-9]{20,}', compartment):
        raise ValueError('Invalid compartment; no environment file written')
    # Refuse reruns over any existing environment, including symlinks.
    target = root / '.env'
    if target.exists() or target.is_symlink():
        raise ValueError('Existing .env preserved; inspect before retrying bootstrap')
    template = (root / '.env.example').read_text()
    if template.count('OCI_REGION=eu-frankfurt-1') != 1 or template.count('__OCI_COMPARTMENT_OCID__') != 1:
        raise ValueError('Unexpected environment template; no environment file written')
    import importlib.util
    spec = importlib.util.spec_from_file_location('local_init_env', root / 'scripts/init_env.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.create_env(root)
    content = target.read_text()
    content = content.replace('OCI_REGION=eu-frankfurt-1', 'OCI_REGION=' + region)
    content = content.replace('__OCI_COMPARTMENT_OCID__', compartment)
    # No shell evaluation; generated secrets remain in this root-only file.
    with target.open('w') as stream:
        stream.write(content)
    target.chmod(0o600)
    subprocess.run([sys.executable, str(root / 'scripts/check_config.py')], check=True, cwd=root)


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Run only as root on the new demo VM.')
    os.umask(0o077)
    root = Path('/opt/oracle-enterprise-ai')
    configure(root)
    subprocess.run(['docker', 'compose', 'version'], check=True)
    subprocess.run(['docker', 'compose', '--env-file', '.env', '-f',
                    'compose.example.yaml', 'config', '--quiet'], cwd=root, check=True)
    (root / 'bootstrap.READY').write_text('Bootstrap verified. Application has not been started.\n')
    print('READY: local credentials generated; no values printed. Follow the stack README before starting the application.')
