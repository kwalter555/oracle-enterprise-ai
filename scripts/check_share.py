"""Heuristic gate for git-visible files. Prints paths/rule names, never values.

Not a replacement for gitleaks/trufflehog, history review or human review.
Ignored local files are excluded; explicitly tracked secrets still fail.
"""
from pathlib import Path
import hashlib
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# Exact reviewed diagram only. Re-exporting requires another visual/privacy review.
# Do not replace this with a general image-extension exemption.
REVIEWED_IMAGES = {
    'docs/architecture/enterprise-ai-atp.png':
        '796bfbb109c83fe699ca6d82f57a29fb19cf9e3a61917cad2018489ae3ceb41e',
}
RULES = {
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'github-token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b'),
    'api-token': re.compile(r'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{25,}\b'),
    'jwt': re.compile(r'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b'),
    'real-oci-identifier': re.compile(r'\bocid1\.[a-z0-9]+\.[a-z0-9-]*\.[a-z0-9._-]{20,}', re.I),
    'personal-home-path': re.compile('/' + r'Users/[^/\s<>]+/'),
    'credential-assignment': re.compile(r'(?im)^\s*(?:OCI_GATEWAY_KEY|WEBUI_SECRET_KEY|POSTGRES_PASSWORD)\s*=\s*["\']?[0-9a-f]{32,}'),
    'approval-service-key': re.compile(r'"(?:api_key|approval_key)"\s*:\s*"[0-9a-f]{64}"'),
    'public-ip': re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
}


def content_issues(text):
    issues = set()
    for label, pattern in RULES.items():
        for match in pattern.finditer(text):
            if label == 'public-ip':
                parts = [int(v) for v in match[0].split('.')]
                if any(v > 255 for v in parts):
                    continue
                if parts[0] == 127 or match[0] == '0.0.0.0':
                    continue
                # One documented private VCN example, not arbitrary private IPs.
                if parts == [10, 42, 0, 0] and text[match.end():match.end()+3] == '/16':
                    continue
                if parts[:3] in ([192,0,2], [198,51,100], [203,0,113]):
                    continue
            if label == 'email' and match[0].split('@')[1].endswith(('.invalid','.example')):
                continue
            issues.add(label)
    return issues


def path_issues(name):
    p = Path(name)
    low = name.lower()
    if p.name == '.env.example':
        return set()
    if (p.name.startswith('.env') or p.suffix.lower() in
        {'.key','.pem','.p12','.pfx','.sso','.jks','.dump','.db','.sqlite','.zip','.gz','.tgz','.7z','.log'}
        or 'wallet' in low or any('backup' in part.lower() for part in p.parts)
        or '.tfstate' in p.name or p.name.endswith(('.tfplan','.tfvars','.tfvars.json'))
        or p.name in {'tnsnames.ora','sqlnet.ora','roles.sql'}
        or any(part in {'.oci','.ssh','.terraform','local','private','uploads','data','__pycache__'} for part in p.parts)):
        return {'forbidden-file'}
    return set()


def candidate_paths(root=ROOT):
    root = Path(root)
    if (root / '.git').exists():
        result = subprocess.run(['git','ls-files','-z','--cached','--others','--exclude-standard'],
                                cwd=root,check=True,capture_output=True)
        return sorted(set(v.decode() for v in result.stdout.split(b'\0') if v))
    # Exported source bundle has no .git. Scan everything, excluding only caches.
    return sorted(str(p.relative_to(root)) for p in root.rglob('*')
                  if (p.is_file() or p.is_symlink()) and '__pycache__' not in p.parts)


def scan(root=ROOT):
    root = Path(root)
    failures = []
    names = candidate_paths(root)
    for name in names:
        path = root / name
        issues = path_issues(name)
        if path.is_symlink():
            issues.add('symlink')
        elif path.exists():
            if path.stat().st_size > 2_000_000:
                issues.add('oversized-file')
            else:
                try:
                    raw = path.read_bytes()
                    if name in REVIEWED_IMAGES:
                        if hashlib.sha256(raw).hexdigest() != REVIEWED_IMAGES[name]:
                            issues.add('unreviewed-image')
                    else:
                        issues |= content_issues(raw.decode('utf-8'))
                except UnicodeError:
                    issues.add('binary-file')
        else:
            issues.add('missing-tracked-file')
        if issues:
            failures.append((name, sorted(issues)))
    return names, failures


if __name__ == '__main__':
    names, failures = scan()
    for name, issues in failures:
        print(name + ': ' + ', '.join(issues))
    print(f'{"FAIL" if failures else "PASS"}: {len(names)} git-visible/exported files checked; no matched values printed.')
    sys.exit(bool(failures))
