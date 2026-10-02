"""Offline diagram, deployment-link and strict image-sharing checks."""
from pathlib import Path
import re
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_share


class ArchitectureTests(unittest.TestCase):
    def test_editable_xml_and_references(self):
        root = ET.parse(ROOT / 'docs/architecture/enterprise-ai-atp.drawio').getroot()
        cells = list(root.iter('mxCell'))
        ids = [c.get('id') for c in cells]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(len(cells), 80)
        for cell in cells:
            for attribute in ['source', 'target', 'parent']:
                if cell.get(attribute):
                    self.assertIn(cell.get(attribute), ids)
        for expected in ['vcn-2', 'subnet-2', 'webui', 'gateway', 'postgres',
                         'adb', 'genai', 'review', 'review-input-flow', 'mcp-flow']:
            self.assertIn(expected, ids)

    def test_button_loads_complete_public_main_archive(self):
        readme = (ROOT / 'README.md').read_text()
        url = re.search(r'\]\((https://cloud\.oracle\.com/resourcemanager/stacks/create[^)]+)\)', readme)[1]
        query = parse_qs(urlparse(url).query)
        self.assertEqual(set(query), {'zipUrl'})
        self.assertEqual(query['zipUrl'], [
            'https://github.com/kwalter555/oracle-enterprise-ai/archive/refs/heads/main.zip'])
        self.assertIn('infra/resource-manager', readme)
        self.assertIn('turn off “Run apply”', readme)
        self.assertIn('only after this change is merged', readme)
        self.assertTrue((ROOT / 'infra/resource-manager/schema.yaml').is_file())

    def test_reviewed_image_accepted_but_changed_copy_rejected(self):
        name = 'docs/architecture/enterprise-ai-atp.png'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / name
            image.parent.mkdir(parents=True)
            image.write_bytes((ROOT / name).read_bytes())
            self.assertEqual(check_share.scan(root)[1], [])
            image.write_bytes(image.read_bytes() + b'tampered')
            self.assertIn('unreviewed-image', check_share.scan(root)[1][0][1])

    def test_unlisted_binary_image_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'unreviewed.png').write_bytes(
                (ROOT / 'docs/architecture/enterprise-ai-atp.png').read_bytes())
            self.assertIn('binary-file', check_share.scan(root)[1][0][1])


if __name__ == '__main__':
    unittest.main()
