from pathlib import Path
import importlib.util
import os
import stat
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scanner = load('check_share')
env = load('init_env')
config = load('check_config')


class ShareTests(unittest.TestCase):
    def test_detects_synthetic_secret_and_identifiers(self):
        examples = [
            'gh'+'p_'+'x'*36,
            'ocid1.'+'compartment.oc1..'+'a'*40,
            '-----BEGIN '+'PRIVATE KEY-----',
            'OCI_GATEWAY_KEY='+'a'*64,
            '/'+'Users/'+'somebody/secret',
            '.'.join(['8','8','8','8']),
        ]
        for sample in examples:
            self.assertTrue(scanner.content_issues(sample))

    def test_examples_are_not_live_identifiers(self):
        self.assertFalse(scanner.content_issues('__OCI_COMPARTMENT_OCID__ 127.0.0.1 https://example.invalid'))
        self.assertFalse(scanner.path_issues('.env.example'))
        for path in ['.env','nested/Wallet_DEMO.zip','private.pem','backups/archive.txt','local/custom.sql']:
            self.assertTrue(scanner.path_issues(path))

    def test_env_generation_no_overwrite_permissions_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'.env.example').write_text((ROOT/'.env.example').read_text())
            env.create_env(root)
            original=(root/'.env').read_text()
            self.assertNotIn('__GENERATE_64_HEX__',original)
            self.assertEqual(stat.S_IMODE((root/'.env').stat().st_mode),0o600)
            with self.assertRaises(FileExistsError): env.create_env(root)
            self.assertEqual((root/'.env').read_text(),original)
            with self.assertRaises(ValueError): config.validate(root/'.env')
            sample='ocid1.'+'compartment.oc1..'+'a'*40
            (root/'.env').write_text(original.replace('__OCI_COMPARTMENT_OCID__',sample))
            config.validate(root/'.env')
            os.chmod(root/'.env',0o644)
            with self.assertRaises(ValueError): config.validate(root/'.env')

    def test_repository_scan(self):
        _, issues=scanner.scan(ROOT)
        self.assertEqual(issues,[])


if __name__=='__main__': unittest.main(verbosity=2)
