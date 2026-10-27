"""Original source downloads use disposable reports and preserve raw-export policy."""
import http.client
import json
import re
import unittest
from urllib.parse import parse_qs, unquote, urlsplit
from unittest.mock import patch

import server
import test_accounts


class ReportDownloadTests(unittest.TestCase):
    def setUp(self):
        test_accounts.AccountTests.setUp(self)
        self.security = patch('server.security_dir', return_value=self.temp/'security')
        self.security.start()

    def tearDown(self):
        self.security.stop()
        test_accounts.AccountTests.tearDown(self)

    create_user = test_accounts.AccountTests.create_user

    def fixture(self, name, suffix='.pbix', content=None, client=None):
        status, report = (client or self.admin).upload(123)
        self.assertEqual(status, 200, report)
        folder = server.DATA/report['id']
        original = folder/'source.zip'
        target = folder/('source.html' if suffix in ('.html', '.htm') else 'source'+suffix)
        if target != original:
            original.rename(target)
        if content is not None:
            target.write_bytes(content)
        metadata = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        metadata['name'] = name
        if suffix in ('.html', '.htm'):
            metadata['reportKind'] = 'html'
        self.write_metadata(report, metadata)
        return report, target.read_bytes(), target

    def write_metadata(self, report, metadata):
        (server.DATA/report['id']/'manifest.json').write_text(json.dumps(metadata), encoding='utf-8')

    def request_source(self, client, ident, suffix):
        headers = {'Host': '127.0.0.1:8765', 'Cookie': client.cookie}
        if getattr(client, 'token', None):
            headers['X-Report-Link'] = client.token
        connection = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=10)
        connection.request('GET', '/api/reports/'+ident+'/'+suffix, headers=headers)
        response = connection.getresponse()
        body = response.read()
        result = response.status, dict(response.getheaders()), body
        connection.close()
        return result

    def get(self, client, ident):
        response = self.request_source(client, ident, 'download')
        info_status, info_headers, info_body = self.request_source(client, ident, 'download-info')
        self.assertEqual(info_status, response[0], 'preflight and download must enforce identical access policies')
        self.assertEqual(info_headers['Cache-Control'], 'no-store')
        info = json.loads(info_body)
        if info_status == 200:
            disposition = response[1]['Content-Disposition']
            filename = unquote(re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I).group(1))
            self.assertEqual(info, {'url': '/api/reports/'+ident+'/download', 'filename': filename, 'bytes': len(response[2])})
        else:
            self.assertIn('error', info)
        self.assertFalse(server.ACTIVE_QUERIES, 'completed/preflight downloads must release report mutation protection')
        return response

    def assert_download(self, response, content, filename):
        status, headers, body = response
        self.assertEqual(status, 200, body[:400])
        self.assertEqual(body, content, 'download must stream the stored source, not a converted-model ZIP')
        self.assertEqual(int(headers['Content-Length']), len(content))
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        disposition = headers['Content-Disposition']
        self.assertTrue(disposition.lower().startswith('attachment;'))
        encoded = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I)
        self.assertIsNotNone(encoded, 'Unicode names require an RFC5987 filename* parameter')
        self.assertEqual(unquote(encoded.group(1)), filename)

    def test_pbix_zip_and_stored_html_exact_bytes_unicode_names_and_stream_length(self):
        # Large enough to exercise multiple source-stream chunks; no semantic
        # source parsing is needed for this isolated endpoint fixture.
        payload = (b'original-PBIX\x00\xff' * 90000) + b'END'
        report, stored, _ = self.fixture('Famille été – 日本語.pbix', content=payload)
        self.assert_download(self.get(self.admin, report['id']), stored, 'Famille été – 日本語.pbix')
        report, stored, _ = self.fixture('Entire project.zip', suffix='.zip')
        self.assert_download(self.get(self.admin, report['id']), stored, 'Entire project.zip')
        html = '<!DOCTYPE html>\r\n<html><body>Été 日本語<script>let embedded=42</script></body></html>'.encode('utf-8')
        report, stored, _ = self.fixture('Embedded report.htm', suffix='.htm', content=html)
        self.assert_download(self.get(self.admin, report['id']), stored, 'Embedded report.htm')

    def test_shared_reader_owner_admin_and_unauthorized_accounts(self):
        owner, owner_client = self.create_user('source-owner')
        reader, reader_client = self.create_user('source-reader')
        _, stranger = self.create_user('source-stranger')
        report, stored, _ = self.fixture('Owned.pbix', client=owner_client)
        ident = report['id']
        self.assert_download(self.get(owner_client, ident), stored, 'Owned.pbix')
        self.assert_download(self.get(self.admin, ident), stored, 'Owned.pbix')
        self.assertEqual(self.get(reader_client, ident)[0], 404)
        self.assertEqual(owner_client.request('POST', '/api/reports/'+ident+'/sharing', {'userIds': [reader['id']]})[0], 200)
        self.assert_download(self.get(reader_client, ident), stored, 'Owned.pbix')
        self.assertEqual(self.get(stranger, ident)[0], 404)
        self.assertEqual(self.get(test_accounts.Client(self.httpd), ident)[0], 401)
        self.assertEqual(self.get(owner_client, '0'*32)[0], 404)

    def test_applied_rls_denies_original_source_even_for_allowed_rows(self):
        reader, client = self.create_user('rls-reader')
        report, stored, _ = self.fixture('Secured.pbix')
        ident = report['id']
        self.admin.request('POST', '/api/reports/'+ident+'/sharing', {'userIds': [reader['id']]})
        config = {'enabled': True, 'roles': [{'name': 'Allowed', 'userIds': [reader['id']], 'groupIds': [],
                  'rules': [{'table': 'Samples', 'column': 'Value', 'operator': 'eq', 'values': [123]}]}]}
        self.assertEqual(self.admin.request('POST', '/api/admin/rls', {'id': ident, 'config': config})[0], 200)
        self.assertEqual(client.request('POST', '/api/query', {'id': ident, 'sql': 'SELECT * FROM Samples'})[1]['rows'], [[123]])
        self.assertEqual(self.get(client, ident)[0], 403, 'filtered read access must not expose unrestricted source bytes')
        self.assert_download(self.get(self.admin, ident), stored, 'Secured.pbix')

    def test_hidden_pages_including_tooltips_require_administrator(self):
        owner, client = self.create_user('hidden-owner')
        report, stored, _ = self.fixture('Hidden.pbix', client=client)
        metadata = server.manifest(report['id'])
        metadata['pages'].append({'id': 'secret', 'name': 'Hidden tooltip', 'hidden': True,
                                  'isTooltip': True, 'pageType': 'Tooltip', 'visuals': []})
        self.write_metadata(report, metadata)
        self.assertEqual(self.get(client, report['id'])[0], 403, 'raw source includes hidden pages even if they are renderable only as tooltips')
        self.assert_download(self.get(self.admin, report['id']), stored, 'Hidden.pbix')

    def test_public_link_never_authorizes_original_download_even_with_admin_cookie(self):
        from test_public_links import PublicClient
        report, _, _ = self.fixture('Public.pbix')
        status, link = self.admin.request('POST', '/api/reports/'+report['id']+'/public-links', {'confirmPublic': True})
        self.assertEqual(status, 201, link)
        token = parse_qs(urlsplit(link['url']).fragment)['public'][0]
        guest = PublicClient(self.httpd, token)
        self.assertEqual(self.get(guest, report['id'])[0], 403)
        guest.cookie = self.admin.cookie
        self.assertEqual(self.get(guest, report['id'])[0], 403, 'a public bearer cannot be upgraded by an existing administrator cookie')

    def test_missing_source_and_legacy_filename_suffix_fallback(self):
        report, stored, _ = self.fixture('Legacy report', suffix='.zip')
        self.assert_download(self.get(self.admin, report['id']), stored, 'Legacy report.zip')
        report, stored, _ = self.fixture('Old name.pbix', suffix='.zip')
        self.assert_download(self.get(self.admin, report['id']), stored, 'Old name.zip')
        report, stored, _ = self.fixture('Old web report.HTM', suffix='.html', content=b'<!DOCTYPE html><html>stored</html>')
        self.assert_download(self.get(self.admin, report['id']), stored, 'Old web report.HTM')
        report, _, source = self.fixture('Missing.pbix')
        source.unlink()
        status, _, body = self.get(self.admin, report['id'])
        self.assertEqual(status, 404, body)
        self.assertRegex(json.loads(body)['error'].lower(), r'original|source')
        self.assertTrue((source.parent/'model.duckdb').is_file(), 'missing original source must not modify installed converted content')

    def test_download_filename_cannot_inject_headers_or_server_paths(self):
        report, stored, _ = self.fixture('..\\nested\\bad\r\nX-Injected: yes.pbix')
        status, headers, body = self.get(self.admin, report['id'])
        self.assertEqual(status, 200, body[:400])
        self.assertEqual(body, stored)
        self.assertNotIn('X-Injected', headers)
        disposition = headers['Content-Disposition']
        self.assertNotIn('\r', disposition)
        self.assertNotIn('\n', disposition)
        name = unquote(re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I).group(1))
        self.assertNotRegex(name, r'[\\/\r\n]')
        self.assertTrue(name.endswith('.pbix'))


if __name__ == '__main__':
    unittest.main()
