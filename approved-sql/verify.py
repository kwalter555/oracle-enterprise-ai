"""Verify immutable kit files against the packaged checksum inventory, offline."""
import hashlib
from pathlib import Path


def verify(root):
    root=Path(root).resolve()
    inventory=root/'SHA256SUMS.txt'
    if not inventory.is_file():
        raise ValueError('Run this check in the distributed kit, not the source checkout.')
    seen=set()
    for line in inventory.read_text().splitlines():
        expected,name=line.split('  ',1)
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts or name in seen:
            raise ValueError('Unsafe checksum inventory.')
        seen.add(name)
        path=root/relative
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Kit file differs: '+name)
    if not seen: raise ValueError('Empty inventory.')
    print(f'PASS: {len(seen)} immutable kit files verified. No services or database changed.')
    print('Local credentials and runtime state are intentionally not part of the inventory.')


if __name__=='__main__':
    try: verify(Path(__file__).resolve().parent)
    except Exception as error:
        print('STOP: '+str(error)); raise SystemExit(1)
