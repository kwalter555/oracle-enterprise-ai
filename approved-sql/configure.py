"""Interactive, local-only secret setup for the Ubuntu VM. Never overwrites files."""
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import zipfile

ROOT = Path(__file__).resolve().parent


def wallet_members(path, alias):
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        if len(set(names)) != len(names) or len(names)>100:
            raise ValueError('Unexpected archive entries.')
        for name in names:
            if Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name:
                raise ValueError('Unsafe archive path.')
        result={}
        for name in ['ewallet.pem','tnsnames.ora']:
            info=archive.getinfo(name)
            if not 0<info.file_size<=2_000_000 or (info.external_attr>>16)&0o170000 == 0o120000:
                raise ValueError('Invalid client configuration member.')
            result[name]=archive.read(name)
        if not re.search(r'^\s*'+re.escape(alias)+r'\s*=',result['tnsnames.ora'].decode(),re.M|re.I):
            raise ValueError('Requested low service alias not found in this archive.')
        return result


def write_private(path, content):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as file:
        file.write(content)
    os.chown(path,10001,10001)


def main():
    if os.geteuid()!=0:
        raise ValueError('Run this setup locally with sudo; container UID 10001 owns the private files.')
    if (ROOT/'private').exists() or (ROOT/'.env').exists():
        raise ValueError('Configuration already exists. Nothing overwritten; inspect it privately.')
    network=input('Existing WebUI Docker network (from preflight): ').strip()
    user=input('Your exact Open WebUI administrator user ID: ').strip()
    alias=input('Database low service alias (example: yourdatabase_low): ').strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',network): raise ValueError('Invalid network name.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',user): raise ValueError('Invalid user ID.')
    if not re.fullmatch(r'[A-Za-z0-9_]+_low',alias): raise ValueError('Use the low service alias.')
    archive=Path(input('Absolute path to YOUR downloaded wallet ZIP: ').strip())
    if not archive.is_absolute(): raise ValueError('Use an absolute local path.')
    members=wallet_members(archive,alias)
    config=dict(execution_enabled=False,allowed_user_ids=[user],dsn=alias,
                api_key=secrets.token_hex(32),approval_key=secrets.token_hex(32))
    for key,label in [('proposal_password','DEMO_AI_READER database password'),
                      ('executor_password','DEMO_SQL_EXECUTOR database password'),
                      ('wallet_password','Wallet download password')]:
        config[key]=getpass.getpass(label+': ')
        if not config[key]: raise ValueError('Empty passwords are not accepted.')
    os.umask(0o077)
    private=ROOT/'private'
    private.mkdir(mode=0o700); os.chown(private,10001,10001)
    client=private/'client-config'; client.mkdir(mode=0o700); os.chown(client,10001,10001)
    for name,content in members.items(): write_private(client/name,content)
    write_private(private/'sql-review.json',json.dumps(config,indent=2).encode())
    # Network name is not a secret. Exclusive creation still prevents overwrite.
    with (ROOT/'.env').open('x') as file: file.write('WEBUI_DOCKER_NETWORK='+network+'\n')
    os.chmod(ROOT/'.env',0o644)
    print('Created private configuration; execution_enabled is FALSE. No database/model calls made.')
    print('Copy only api_key and approval_key privately into the tool administrator Valves.')
    print('Never share private/ or an export of configured tool Valves.')


if __name__=='__main__':
    try: main()
    except (Exception,KeyboardInterrupt) as error:
        print('STOP: '+str(error) if isinstance(error,ValueError) else 'STOP: '+type(error).__name__)
        print('No automatic cleanup. If partial files were created, inspect them privately before retrying.')
        raise SystemExit(1)
