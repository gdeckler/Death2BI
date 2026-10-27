"""Missing public custom visuals resolve offline without private-package access."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import unittest
import uuid
from unittest.mock import patch

from custom_visuals import read_package, register_referenced, save_package
from test_custom_visuals import package


class BundledVisualTests(unittest.TestCase):
    def setUp(self):
        # Inherit the workspace ACL rather than Python 3.13's private Windows
        # tempfile ACL, which excludes the sandbox's restricted test identity.
        self.root = Path(__file__).parent / ('test-bundles-' + uuid.uuid4().hex)
        self.root.mkdir()
        self.addCleanup(self.cleanup_root)
        self.bundles = self.root / 'bundled'
        self.registry = self.root / 'registry'
        self.bundles.mkdir()
        self.registry.mkdir()
        self.guid = 'PublicVisual1234'
        self.resource = {'visual': {'guid': self.guid, 'displayName': 'Public sample'},
                         'apiVersion': '2.1.0', 'capabilities': {'dataRoles': []},
                         'content': {'js': '/* public package, never executed by server */'}}
        self.content = package(self.resource)
        (self.bundles / 'sample.pbiviz').write_bytes(self.content)
        self.entry = {'filename': 'sample.pbiviz', 'sha256': hashlib.sha256(self.content).hexdigest(),
                      'source': 'https://example.org/publisher/sample.pbiviz', 'license': 'MIT'}
        self.catalog()

    def cleanup_root(self):
        assert self.root.resolve().parent == Path(__file__).resolve().parent
        assert self.root.name.startswith('test-bundles-')
        shutil.rmtree(self.root)

    def catalog(self, entry=None):
        (self.bundles / 'catalog.json').write_text(json.dumps({self.guid: self.entry if entry is None else entry}), 'utf8')

    def resolve(self, guids=None, registered=()):
        return register_referenced(self.registry, [self.guid] if guids is None else guids, registered, self.bundles)

    def test_only_referenced_allowlisted_package_is_registered_offline(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('no runtime network')):
            for refs in ([], ['UnknownPrivateVisual1234']):
                self.assertEqual(self.resolve(refs), ([], []))
                self.assertEqual(list(self.registry.iterdir()), [])
            result, warnings = self.resolve([self.guid, self.guid])
            self.assertEqual(warnings, [])
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['guid'], self.guid)
            self.assertNotIn('js', result[0])
            self.assertEqual(result[0]['provenance']['sha256'], self.entry['sha256'])
            saved = json.loads((self.registry / (result[0]['id'] + '.json')).read_text('utf8'))
            self.assertEqual(saved['js'], self.resource['content']['js'])
            before = (self.registry / (result[0]['id'] + '.json')).stat().st_mtime_ns
            self.assertEqual(self.resolve(), (result, []))
            self.assertEqual((self.registry / (result[0]['id'] + '.json')).stat().st_mtime_ns, before)

    def test_embedded_or_explicit_authorized_reference_wins_without_mutation(self):
        registered = [{'id': 'a' * 32, 'guid': self.guid, 'name': 'Embedded newer build'}]
        original = copy.deepcopy(registered)
        (self.bundles / 'sample.pbiviz').unlink()
        self.assertEqual(self.resolve(registered=registered), (registered, []))
        self.assertEqual(registered, original)
        self.assertEqual(list(self.registry.iterdir()), [])

    def test_private_registry_package_with_same_guid_is_not_reused(self):
        private = read_package('private.pbiviz', package({**self.resource, 'content': {'js': 'private source code'}}))
        private_metadata = save_package(self.registry, private)
        result, warnings = self.resolve()
        self.assertEqual(warnings, [])
        self.assertNotEqual(result[0]['id'], private_metadata['id'])
        self.assertEqual(len(list(self.registry.glob('*.json'))), 2)
        self.assertNotIn('private source code', json.dumps(result))

    def test_corrupt_path_hash_and_guid_fail_closed(self):
        cases = [({**self.entry, 'filename': '../sample.pbiviz'}, None, 'allowlist'),
                 ({**self.entry, 'sha256': '0' * 64}, None, 'integrity'),
                 (self.entry, package({**self.resource, 'visual': {'guid': 'DifferentVisual1234'}}), 'GUID')]
        for entry, content, message in cases:
            with self.subTest(message=message):
                if content is not None:
                    (self.bundles / 'sample.pbiviz').write_bytes(content)
                    entry = {**entry, 'sha256': hashlib.sha256(content).hexdigest()}
                self.catalog(entry)
                result, warnings = self.resolve()
                self.assertEqual(result, [])
                self.assertEqual(len(warnings), 1)
                self.assertIn(message, warnings[0])
                self.assertEqual(list(self.registry.iterdir()), [])

    def test_shipped_walkers_package_is_exact_guid_offline_and_license_retained(self):
        bundles = Path(__file__).with_name('bundled_visuals')
        catalog = json.loads((bundles / 'catalog.json').read_text('utf8'))
        guid = 'wishyoulizationwalkers'
        result, warnings = register_referenced(self.registry, [guid])
        self.assertEqual(warnings, [])
        self.assertEqual(result[0]['guid'], guid)
        self.assertEqual(result[0]['version'], '1.0.2')
        self.assertEqual(result[0]['apiVersion'], '2.1.0')
        self.assertEqual({r['name'] for r in result[0]['capabilities']['dataRoles']},
                         {'option', 'category', 'value', 'color', 'optionsorder', 'categoriesorder'})
        self.assertEqual(result[0]['networkDomains'], [])
        self.assertEqual(result[0]['provenance']['commit'], catalog[guid]['commit'])
        self.assertIn('MIT License', (bundles / 'wishyoulizationwalkers.LICENSE.txt').read_text('utf8'))


if __name__ == '__main__':
    unittest.main()
