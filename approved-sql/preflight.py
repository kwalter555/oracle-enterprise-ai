"""Read-only inventory of the existing VM. Never prints container environment."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def run(args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Read-only Docker check failed; verify sudo -n and Compose locally.')
    return result.stdout.strip()


def check(project):
    project = Path(project).resolve()
    for name in ['compose.yaml', 'compose.oci.yaml', 'oci-gateway/app.py']:
        if not (project/name).is_file():
            raise ValueError('Expected existing application file is missing: ' + name)
    base = ['sudo','-n','docker','compose','-f',str(project/'compose.yaml'),'-f',str(project/'compose.oci.yaml')]
    container = run(base+['ps','-q','open-webui'])
    if not container or '\n' in container:
        raise ValueError('Expected one running Open WebUI container.')
    fmt = '{"image":{{json .Config.Image}},"running":{{json .State.Running}},"networks":{{json .NetworkSettings.Networks}}}'
    info = json.loads(run(['sudo','-n','docker','inspect','--format',fmt,container]))
    if not info['running'] or info['image'] != 'ghcr.io/open-webui/open-webui:v0.11.3':
        raise ValueError('This pilot requires the reviewed Open WebUI v0.11.3 image.')
    # Detect stripped/changed reserved-argument filtering or approval ownership guard.
    script = "from pathlib import Path; p=Path('/app/backend/open_webui'); a=(p/'utils/middleware.py').read_text(); b=(p/'socket/main.py').read_text(); print('PASS' if 'if key in allowed_params' in a and \"session.get('id') != request_info.get('user_id')\" in b else 'FAIL')"
    if run(base+['exec','-T','open-webui','python','-c',script]) != 'PASS':
        raise ValueError('Installed WebUI approval/argument guard differs. Review before installing.')
    host_hash = hashlib.sha256((project/'oci-gateway/app.py').read_bytes()).hexdigest()
    print('Open WebUI: v0.11.3, running; approval/argument guard markers present')
    print('Available Docker networks: ' + ', '.join(sorted(info['networks'])))
    print('Host gateway SHA-256: ' + host_hash)
    print('READ-ONLY PREFLIGHT PASS. No files, services or database resources changed.')
    print('This is not a database connection, UI approval, or deployment test.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir',required=True)
    args=parser.parse_args()
    try:
        check(args.project_dir)
    except Exception as error:
        print('STOP: '+str(error) if isinstance(error,(ValueError,RuntimeError)) else 'STOP: '+type(error).__name__)
        raise SystemExit(1)
