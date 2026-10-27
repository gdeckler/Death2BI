import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

from custom_visuals import read_package, normalize, metadata


def package(resource, extra=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('package.json', json.dumps({'visual': resource['visual'], 'resources': [{'resourceId': 'r0', 'file': 'resources/visual.pbiviz.json'}], 'metadata': {'pbivizjson': {'resourceId': 'r0'}}}))
        archive.writestr('resources/visual.pbiviz.json', json.dumps(resource))
        if extra: archive.writestr(extra, 'invalid')
    return output.getvalue()


class Packages(unittest.TestCase):
    def setUp(self):
        self.resource = {'visual': {'guid': 'SampleVisual0123456789', 'displayName': 'Sample'}, 'apiVersion': '5.11.0', 'capabilities': {'dataRoles': [], 'privileges': [{'name': 'WebAccess', 'parameters': ['https://*.tile.openstreetmap.org', 'https://raw.githubusercontent.com', 'http://localhost:8765', "https://x.com' unsafe-inline"]}]}, 'content': {'js': 'window.example=true', 'css': '.sample{}'}}

    def test_normalize_and_identity(self):
        a = read_package('one.pbiviz', package(self.resource))
        b = read_package('two.pbiviz', package(self.resource))
        self.assertEqual(a['id'], b['id'])
        self.assertNotIn('js', metadata(a))
        self.assertEqual(a['networkDomains'], ['https://*.tile.openstreetmap.org', 'https://raw.githubusercontent.com'])
        changed = {**self.resource, 'content': {'js': 'changed'}}
        self.assertNotEqual(a['id'], normalize(changed, 'changed.pbiviz')['id'])

    def test_legacy_build_dependencies_are_metadata_only(self):
        resource={**self.resource,'externalJS':['node_modules/d3/d3.min.js','node_modules/jquery/dist/jquery.slim.min.js']}
        result=normalize(resource,'legacy.pbiviz')
        self.assertEqual(result['js'],self.resource['content']['js'])
        self.assertNotIn('externalJS',result)
        for path in ['//example.com/code.js','../code.js','file:///code.js','C:/code.js']:
            with self.assertRaisesRegex(ValueError,'External JavaScript'):
                normalize({**resource,'externalJS':[path]},'invalid.pbiviz')

    def test_bad_archive_paths_and_external_scripts(self):
        with self.assertRaisesRegex(ValueError, 'archive path'):
            read_package('bad.pbiviz', package(self.resource, '../outside.js'))
        with self.assertRaisesRegex(ValueError, 'External JavaScript'):
            normalize({**self.resource, 'externalJS': ['https://example.com/code.js']}, 'external.pbiviz')
        with self.assertRaisesRegex(ValueError, 'GUID'):
            normalize({**self.resource, 'visual': {'guid': '../../file'}}, 'bad.pbiviz')


if __name__ == '__main__':
    # Optional real package validation without running their JavaScript.
    for filename in sys.argv[1:]:
        path = Path(filename)
        p = read_package(path.name, path.read_bytes())
        print('Validated:', p['name'], p['apiVersion'], len(p['capabilities']['dataRoles']), 'roles')
    unittest.main(argv=[sys.argv[0]])
