"""Public package fallback participates in normal report/account authorization."""
import io
import json
import unittest
from unittest.mock import patch
import zipfile

import server
import test_accounts


GUID = 'wishyoulizationwalkers'


class BundledVisualImportTests(unittest.TestCase):
    def setUp(self):
        test_accounts.AccountTests.setUp(self)
        self.security = patch('server.security_dir', return_value=self.temp/'security')
        self.security.start()

    def tearDown(self):
        self.security.stop()
        test_accounts.AccountTests.tearDown(self)

    create_user = test_accounts.AccountTests.create_user

    def files(self):
        encode = lambda value: json.dumps(value).encode('utf8')
        return {'Samples.csv': b'Value\n123\n',
                'Project.Report/definition/pages/pages.json': encode({'pageOrder': ['health']}),
                'Project.Report/definition/pages/health/page.json': encode({'name': 'health', 'displayName': 'Healthcare'}),
                'Project.Report/definition/pages/health/visuals/walker/visual.json': encode({
                    'name': 'walker', 'position': {'x': 10, 'y': 20, 'width': 300, 'height': 200},
                    'visual': {'visualType': GUID}})}

    def upload(self, client, filename, files):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        boundary = 'bundled-visual-test'
        body = ('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="'+filename+'"\r\n\r\n').encode()
        body += output.getvalue()+('\r\n--'+boundary+'\r\nContent-Disposition: form-data; name="mode"\r\n\r\nnew\r\n--'+boundary+'--\r\n').encode()
        return client.request('POST', '/api/import', raw=body, content_type='multipart/form-data; boundary='+boundary)

    def test_future_pbix_and_pbip_import_attach_public_package_with_normal_grants(self):
        owner, client = self.create_user('walkers-owner')
        reader, shared = self.create_user('walkers-reader')
        _, stranger = self.create_user('walkers-stranger')
        for filename in ('Missing custom visual.pbix', 'Missing custom visual PBIP.zip'):
            with self.subTest(filename=filename):
                status, report = self.upload(client, filename, self.files())
                self.assertEqual(status, 200, report)
                self.assertEqual(report['pages'][0]['visuals'][0]['type'], GUID)
                self.assertEqual(len(report['customVisuals']), 1)
                package = report['customVisuals'][0]
                self.assertEqual(package['guid'], GUID)
                self.assertEqual(package['version'], '1.0.2')
                endpoint = '/api/custom-visuals/'+package['id']
                status, content = client.request('GET', endpoint)
                self.assertEqual(status, 200)
                self.assertTrue(content['js'])
                self.assertEqual(shared.request('GET', endpoint)[0], 404)
                self.assertEqual(stranger.request('GET', endpoint)[0], 404)
                self.assertEqual(client.request('POST', '/api/reports/'+report['id']+'/sharing', {'userIds': [reader['id']]})[0], 200)
                self.assertEqual(shared.request('GET', '/api/models/'+report['id'])[0], 200)
                self.assertEqual(shared.request('GET', endpoint)[0], 200)
                self.assertEqual(stranger.request('GET', endpoint)[0], 404)
                self.assertEqual(client.request('POST', '/api/query', {'id': report['id'], 'sql': 'SELECT * FROM Samples'})[1]['rows'], [[123]])
                self.assertEqual(client.request('POST', '/api/reports/'+report['id']+'/sharing', {'userIds': []})[0], 200)
                self.assertEqual(shared.request('GET', endpoint)[0], 404, 'reader package access follows report sharing revocation')

    def test_existing_report_detail_backfills_only_its_referenced_public_visual(self):
        owner, client = self.create_user('existing-owner')
        _, stranger = self.create_user('existing-stranger')
        status, report = client.upload(123)
        self.assertEqual(status, 200)
        folder = server.DATA/report['id']
        metadata = server.manifest(report['id'])
        metadata['pages'] = [{'id': 'health', 'name': 'Healthcare', 'visuals': [{'id': 'walker', 'type': GUID}]}]
        metadata['customVisuals'] = []
        (folder/'manifest.json').write_text(json.dumps(metadata), 'utf8')
        self.assertEqual(list(server.CUSTOM_VISUALS.glob('*.json')), [])
        self.assertEqual(stranger.request('GET', '/api/models/'+report['id'])[0], 404)
        self.assertEqual(list(server.CUSTOM_VISUALS.glob('*.json')), [], 'unauthorized reads cannot trigger model/package work')
        status, repaired = client.request('GET', '/api/models/'+report['id'])
        self.assertEqual(status, 200, repaired)
        self.assertEqual(len(repaired['customVisuals']), 1)
        self.assertEqual(repaired['customVisuals'][0]['guid'], GUID)
        ident = repaired['customVisuals'][0]['id']
        self.assertEqual(client.request('GET', '/api/custom-visuals/'+ident)[0], 200)
        self.assertEqual(stranger.request('GET', '/api/custom-visuals/'+ident)[0], 404)

    def test_embedded_same_guid_keeps_its_authored_build(self):
        _, client = self.create_user('embedded-owner')
        files = self.files()
        files['Report/CustomVisuals/'+GUID+'/visual.pbiviz.json'] = json.dumps({
            'visual': {'guid': GUID, 'displayName': 'Authored build', 'version': '9.0.0'},
            'capabilities': {'dataRoles': []}, 'content': {'js': '/* report authored build */'}}).encode()
        status, report = self.upload(client, 'Embedded version.zip', files)
        self.assertEqual(status, 200, report)
        self.assertEqual(len(report['customVisuals']), 1)
        package = report['customVisuals'][0]
        self.assertEqual(package['version'], '9.0.0')
        self.assertNotIn('provenance', package)
        self.assertEqual(client.request('GET', '/api/custom-visuals/'+package['id'])[1]['js'], '/* report authored build */')


if __name__ == '__main__':
    unittest.main()
