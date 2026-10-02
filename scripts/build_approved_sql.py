"""Build the optional VM add-on from reviewed, manifested source only."""
import argparse
import hashlib
from pathlib import Path
import zipfile
from check_share import ROOT, scan


def build(output, root=ROOT):
    root=Path(root).resolve(); output=Path(output).resolve()
    if root==output or root in output.parents:
        raise ValueError('Write the ZIP outside the repository.')
    names,issues=scan(root)
    if issues: raise ValueError('Sharing check failed; review rule names locally.')
    manifest={}
    for line in (root/'SOURCE-MANIFEST.sha256').read_text().splitlines():
        digest,name=line.split('  ',1)
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or name in manifest:
            raise ValueError('Invalid source manifest.')
        if hashlib.sha256((root/p).read_bytes()).hexdigest()!=digest:
            raise ValueError('Source manifest differs; review and refresh it.')
        manifest[name]=digest
    if set(manifest)|{'SOURCE-MANIFEST.sha256'} != set(names):
        raise ValueError('Manifest must cover all shareable source.')
    selected=sorted(n for n in names if n.startswith('approved-sql/'))
    if not selected: raise ValueError('Add-on source is missing.')
    checksums=''.join(manifest[n]+'  '+n.removeprefix('approved-sql/')+'\n' for n in selected)
    files={n.removeprefix('approved-sql/'):(root/n).read_bytes() for n in selected}
    files['SHA256SUMS.txt']=checksums.encode()
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo('oci-approved-sql-kit/'+name,date_time=(2026,9,30,0,0,0))
            info.external_attr=0o100644<<16; info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None: raise ValueError('ZIP failed integrity verification.')
    return hashlib.sha256(output.read_bytes()).hexdigest(),len(files)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    digest,count=build(args.output)
    print(f'Created {count} files. SHA-256: {digest}')
    print('Source only. No VM, database, OCI or GitHub changes made.')
