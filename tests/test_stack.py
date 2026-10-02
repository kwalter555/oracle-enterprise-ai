"""Offline stack/bootstrap/distribution guards; no Terraform Apply or OCI calls."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / 'infra/resource-manager'
sys.path.insert(0, str(ROOT / 'scripts'))
import build_stack
import check_share
import check_config

spec = importlib.util.spec_from_file_location('stack_bootstrap', STACK / 'bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def fixture(root):
    (root / 'scripts').mkdir()
    for name in ['.env.example', 'scripts/init_env.py', 'scripts/check_config.py']:
        shutil.copyfile(ROOT / name, root / name)
    settings = {'region': 'eu-amsterdam-1',
                'compartment_id': 'ocid1.' + 'compartment.oc1..' + 'x' * 40}
    (root / 'stack-settings.json').write_text(json.dumps(settings))
    return settings


class BootstrapTests(unittest.TestCase):
    def test_local_configuration_random_secrets_and_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = fixture(root)
            # Run the actual local configuration checker; no Docker or network.
            with contextlib.redirect_stdout(io.StringIO()) as output:
                bootstrap.configure(root)
            content = (root / '.env').read_text()
            self.assertIn('OCI_REGION=' + settings['region'], content)
            self.assertIn('OCI_COMPARTMENT_ID=' + settings['compartment_id'], content)
            self.assertNotIn('__GENERATE_', content)
            secrets = re.findall(r'^(?:OCI_GATEWAY_KEY|POSTGRES_PASSWORD|WEBUI_SECRET_KEY)=(.+)$', content, re.M)
            self.assertEqual(len(set(secrets)), 3)
            for value in secrets:
                self.assertNotIn(value, output.getvalue())
            self.assertEqual(stat.S_IMODE((root / '.env').stat().st_mode), 0o600)
            check_config.validate(root / '.env')
            self.assertFalse((root / 'bootstrap.READY').exists())

    def test_rerun_preserves_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root)
            with patch.object(bootstrap.subprocess, 'run'):
                bootstrap.configure(root)
            before = (root / '.env').read_bytes()
            with self.assertRaisesRegex(ValueError, 'preserved'):
                bootstrap.configure(root)
            self.assertEqual(before, (root / '.env').read_bytes())

    def test_dangling_symlink_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root)
            (root / '.env').symlink_to(root / 'missing')
            with self.assertRaisesRegex(ValueError, 'preserved'):
                bootstrap.configure(root)
            self.assertFalse((root / 'missing').exists())

    def test_invalid_settings_do_not_write_secrets(self):
        for settings in [{'region': 'bad; command', 'compartment_id': 'wrong'},
                         {'region': 'eu-frankfurt-1', 'compartment_id': 'wrong'}]:
            with self.subTest(settings=settings), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                fixture(root)
                (root / 'stack-settings.json').write_text(json.dumps(settings))
                with self.assertRaises(ValueError):
                    bootstrap.configure(root)
                self.assertFalse((root / '.env').exists())

    def test_template_drift_refused_before_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root)
            template = root / '.env.example'
            template.write_text(template.read_text().replace('OCI_REGION=eu-frankfurt-1', 'OCI_REGION=other'))
            with self.assertRaisesRegex(ValueError, 'template'):
                bootstrap.configure(root)
            self.assertFalse((root / '.env').exists())


class StackGuards(unittest.TestCase):
    def test_small_database_uses_transaction_processing_not_warehouse(self):
        database = (STACK / 'database.tf').read_text()
        self.assertRegex(database, r'db_workload\s+= "OLTP"')
        self.assertNotRegex(database, r'db_workload\s+= "DW"')
        self.assertRegex(database, r'compute_model\s+= "ECPU"')
        self.assertRegex(database, r'license_model\s+= "LICENSE_INCLUDED"')
        self.assertRegex(database, r'data_storage_size_in_gb\s+= var.adb_storage_gb')
        self.assertNotIn('data_storage_size_in_tbs', database)
        variables = (STACK / 'variables.tf').read_text()
        storage = variables.split('variable "adb_storage_gb" {', 1)[1].split('variable "enable_mcp"', 1)[0]
        self.assertRegex(storage, r'default\s+= 20')
        self.assertIn('var.adb_storage_gb >= 20', storage)
        self.assertIn('var.adb_storage_gb <= 100', storage)
        self.assertIn('floor(var.adb_storage_gb) == var.adb_storage_gb', storage)

    def test_demo_cost_flags_remain_explicit(self):
        database = (STACK / 'database.tf').read_text()
        for flag in ['is_auto_scaling_enabled', 'is_auto_scaling_for_storage_enabled', 'is_free_tier']:
            self.assertRegex(database, rf'{flag}\s+= false')
        schema = (STACK / 'schema.yaml').read_text()
        self.assertIn('version: "2026.10.02"', schema)
        self.assertIn('Transaction Processing storage (GB)', schema)
        guide = (STACK / 'README.md').read_text()
        self.assertIn('no automatic start/stop schedule', guide)
        self.assertIn('monthly target is not guaranteed', guide)

    def test_cloud_init_has_no_remote_scripts_or_app_start(self):
        source = (STACK / 'compute.tf').read_text()
        self.assertIn('base64gzip(', source)
        self.assertIn('permissions = "0644"', source)
        self.assertIn('"chmod", "0700", "/opt/oracle-enterprise-ai"', source)
        self.assertNotIn('adb_admin_password', source)
        all_tf = '\n'.join(p.read_text() for p in STACK.glob('*.tf'))
        for prohibited in ['remote-exec', 'local-exec', 'null_resource', 'curl |', 'private_key']:
            self.assertNotIn(prohibited, all_tf)
        bootstrap_source = (STACK / 'bootstrap.py').read_text()
        self.assertNotIn("'up'", bootstrap_source)
        self.assertNotIn('RUN_TOOL', bootstrap_source)

    def test_network_database_and_destroy_guards(self):
        network = (STACK / 'network.tf').read_text()
        self.assertEqual(network.count('ingress_security_rules {'), 1)
        self.assertRegex(network, r'source\s+= var.admin_cidr')
        self.assertRegex(network, r'min\s+= 22')
        self.assertRegex(network, r'max\s+= 22')
        self.assertIn('var.acknowledge_costs', network)
        database = (STACK / 'database.tf').read_text()
        self.assertIn('whitelisted_ips = [var.admin_cidr, "${oci_core_instance.app.public_ip}/32"]', database)
        self.assertNotIn('0.0.0.0', database)
        self.assertRegex(database, r'is_mtls_connection_required\s+= true')
        for name in ['database.tf', 'compute.tf']:
            self.assertIn('prevent_destroy = true', (STACK / name).read_text())
        variables = (STACK / 'variables.tf').read_text()
        for name in ['enable_mcp', 'acknowledge_costs']:
            self.assertRegex(variables, rf'(?s)variable "{name}" \{{.*?default\s+= false')

    def test_iam_matches_only_exact_resources(self):
        iam = (STACK / 'iam.tf').read_text()
        self.assertIn("instance.id = '${oci_core_instance.app.id}'", iam)
        self.assertIn("resource.id = '${oci_database_autonomous_database.demo.id}'", iam)
        self.assertEqual(iam.count('Allow dynamic-group id '), 3)
        self.assertNotIn('manage all-resources', iam)
        self.assertNotIn('resource.compartment.id', iam)
        self.assertNotIn('instance.compartment.id', iam)

    def test_terraform_sensitive_artifacts_are_rejected(self):
        for name in ['terraform.tfstate', 'terraform.tfstate.backup', 'x.tfvars',
                     'x.tfvars.json', 'review.tfplan', '.terraform/providers/plugin']:
            self.assertTrue(check_share.path_issues(name), name)
        self.assertFalse(check_share.path_issues('infra/resource-manager/.terraform.lock.hcl'))

    def test_only_specific_documented_vcn_example_is_allowed(self):
        self.assertFalse(check_share.content_issues('10.42.0.0/16'))
        base = '.'.join(['10', '42', '0', '0'])
        for sample in [base, base + '/24', '.'.join(['10', '43', '0', '0']) + '/16']:
            self.assertIn('public-ip', check_share.content_issues(sample))


class DistributionTests(unittest.TestCase):
    def source(self, folder):
        root = Path(folder) / 'source'
        (root / 'infra/resource-manager').mkdir(parents=True)
        (root / 'infra/resource-manager/schema.yaml').write_text('schemaVersion: 1.1.0\n')
        (root / 'README.md').write_text('Synthetic fixture. No account identifiers.\n')
        paths = ['README.md', 'infra/resource-manager/schema.yaml']
        manifest = '\n'.join(hashlib.sha256((root / name).read_bytes()).hexdigest() + '  ' + name for name in paths) + '\n'
        (root / 'SOURCE-MANIFEST.sha256').write_text(manifest)
        return root

    def test_complete_reproducible_zip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.source(folder)
            output = Path(folder) / 'stack.zip'
            digest, count = build_stack.build(output, root)
            self.assertEqual(count, 3)
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), set(check_share.candidate_paths(root)))
            other_digest, _ = build_stack.build(Path(folder) / 'stack2.zip', root)
            self.assertEqual(digest, other_digest)
            with self.assertRaises(FileExistsError):
                build_stack.build(output, root)
            with self.assertRaisesRegex(ValueError, 'outside'):
                build_stack.build(root / 'stack.zip', root)

    def test_modified_source_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.source(folder)
            (root / 'README.md').write_text('Unreviewed change')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                build_stack.build(Path(folder) / 'stack.zip', root)

    def test_unmanifested_file_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.source(folder)
            (root / 'unexpected.txt').write_text('Additional file')
            with self.assertRaisesRegex(ValueError, 'exactly cover'):
                build_stack.build(Path(folder) / 'stack.zip', root)

    def test_forbidden_file_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.source(folder)
            (root / '.env').write_text('Sensitive local file')
            with self.assertRaisesRegex(ValueError, 'Sharing checks'):
                build_stack.build(Path(folder) / 'stack.zip', root)

    def test_manifest_traversal_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.source(folder)
            (root / 'SOURCE-MANIFEST.sha256').write_text('0' * 64 + '  ../outside\n')
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                build_stack.build(Path(folder) / 'stack.zip', root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
