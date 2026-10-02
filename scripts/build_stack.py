"""Build a reviewed Resource Manager ZIP; no OCI access or credentials required.

The complete repository layout is preserved. In Resource Manager select the
Terraform working directory infra/resource-manager, for both ZIP and Git sources.
"""
import argparse
import hashlib
from pathlib import Path
import zipfile

from check_share import ROOT, scan


def build(output, root=ROOT):
    root = Path(root).resolve()
    output = Path(output).resolve()
    if root == output or root in output.parents:
        raise ValueError('Write the distribution ZIP outside the source repository')
    names, issues = scan(root)
    if issues:
        raise ValueError('Sharing checks failed; run scripts/check_share.py for rule names')
    manifest = root / 'SOURCE-MANIFEST.sha256'
    entries = {}
    for line in manifest.read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or name in entries:
            raise ValueError('Unsafe or duplicate manifest path')
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != digest:
            raise ValueError('Source manifest mismatch; review changes and refresh it first')
        entries[name] = digest
    if set(entries) | {'SOURCE-MANIFEST.sha256'} != set(names):
        raise ValueError('Source manifest does not exactly cover the reviewed package')
    if 'infra/resource-manager/schema.yaml' not in entries:
        raise ValueError('Stack schema is missing')
    # Exclusive creation prevents silently replacing an earlier release.
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 29, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (root / name).read_bytes())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP integrity verification failed')
    return hashlib.sha256(output.read_bytes()).hexdigest(), len(names)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New ZIP path outside the repository')
    args = parser.parse_args()
    digest, count = build(args.output)
    print(f'Created and checked {count} source files. SHA-256: {digest}')
    print('Resource Manager working directory: infra/resource-manager')
    print('No OCI calls made. Review Plan before Apply; SQL and app startup remain manual.')
