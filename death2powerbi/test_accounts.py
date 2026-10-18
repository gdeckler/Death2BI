"""Account lifecycle and HTTP isolation tests using temporary accounts/reports only."""
from pathlib import Path
import http.client
import io
import json
import shutil
import threading
import unittest
import uuid
import zipfile

import server
from accounts import Accounts, AuthError, DEFAULT_PASSWORD


class Client:
    def __init__(self, httpd):
        self.port = httpd.server_port
        self.cookie = ''
        self.csrf = ''

    def request(self, method, path, payload=None, raw=None, csrf=True, origin='http://127.0.0.1:8765', content_type='application/json'):
        headers = {'Host': '127.0.0.1:8765', 'Origin': origin, 'Content-Type': content_type}
        if self.cookie: headers['Cookie'] = self.cookie
        if csrf: headers['X-CSRF-Token'] = self.csrf
        body = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        con = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
        con.request(method, path, body, headers)
        response = con.getresponse()
        data = response.read()
        cookie = response.getheader('Set-Cookie')
        if cookie: self.cookie = cookie.split(';', 1)[0]
        result = json.loads(data) if response.getheader('Content-Type', '').startswith('application/json') else data
        if isinstance(result, dict) and result.get('csrf'): self.csrf = result['csrf']
        status = response.status
        con.close()
        return status, result

    def login(self, username, password):
        return self.request('POST', '/api/auth/login', {'username': username, 'password': password}, csrf=False)

    def upload(self, number):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('Samples.csv', 'Value\n' + str(number) + '\n')
        boundary = 'account-test'
        body = b'--account-test\r\nContent-Disposition: form-data; name="file"; filename="Same.zip"\r\n\r\n' + output.getvalue() + b'\r\n--account-test--\r\n'
        return self.request('POST', '/api/import', raw=body, content_type='multipart/form-data; boundary=' + boundary)


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.base = (Path.cwd() / 'work').resolve()
        self.base.mkdir(exist_ok=True)
        self.temp = self.base / ('accounts-test-' + uuid.uuid4().hex)
        self.temp.mkdir()
        self.original = server.DATA, server.AUTH, server.CUSTOM_VISUALS
        server.DATA = self.temp / 'reports'
        server.DATA.mkdir()
        server.CUSTOM_VISUALS = self.temp / 'visuals'
        server.CUSTOM_VISUALS.mkdir()
        server.AUTH = Accounts(self.temp / 'security' / 'accounts.sqlite3')
        self.store = server.AUTH
        self.httpd = server.LocalServer(('127.0.0.1', 0), server.Handler)
        self.worker = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.worker.start()
        self.admin = Client(self.httpd)
        status, session = self.admin.login('admin', DEFAULT_PASSWORD)
        self.assertEqual(status, 200)
        self.admin_user = session['user']

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.worker.join(timeout=5)
        server.DATA, server.AUTH, server.CUSTOM_VISUALS = self.original
        self.assertEqual(self.temp.resolve().parent, self.base)
        shutil.rmtree(self.temp)

    def create_user(self, username):
        status, user = self.admin.request('POST', '/api/admin/accounts', {'username': username, 'password': 'ExamplePassword!1'})
        self.assertEqual(status, 201)
        client = Client(self.httpd)
        self.assertEqual(client.login(username, 'ExamplePassword!1')[0], 200)
        return user, client

    def test_slow_dax_does_not_block_table_or_custom_visual_queries(self):
        from unittest.mock import patch
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        status, report = self.admin.upload(123)
        self.assertEqual(status, 200)
        results = {}
        def slow_evaluation(*args):
            started.set()
            release.wait(5)
            return {'columns': ['v0'], 'rows': [[1]], 'types': ['INTEGER'], 'truncated': False}
        def dax_request():
            results['dax'] = self.admin.request('POST', '/api/dax', {'id': report['id']})
        other = Client(self.httpd)
        other.cookie, other.csrf = self.admin.cookie, self.admin.csrf
        def table_request():
            results['table'] = other.request('POST', '/api/query', {'id': report['id'], 'sql': 'SELECT 42 AS answer'})
            finished.set()
        with patch('dax_engine.evaluate_visual', side_effect=slow_evaluation):
            dax = threading.Thread(target=dax_request)
            dax.start()
            self.assertTrue(started.wait(2))
            table = threading.Thread(target=table_request)
            table.start()
            try:
                self.assertTrue(finished.wait(2), 'Unrelated visual query waited for slow DAX')
            finally:
                release.set()
                dax.join(10)
                table.join(10)
        self.assertEqual(results['table'][0], 200)
        self.assertEqual(results['table'][1]['rows'], [[42]])
        self.assertEqual(results['dax'][0], 200)

    def test_report_isolation_and_administration(self):
        anonymous = Client(self.httpd)
        for method, path, payload in [('GET', '/api/models', None), ('POST', '/api/query', {'id': uuid.uuid4().hex, 'sql': 'SELECT 1'}), ('GET', '/api/admin/accounts', None), ('GET', '/api/custom-visuals', None)]:
            self.assertEqual(anonymous.request(method, path, payload)[0], 401)
        self.assertEqual(anonymous.request('GET', '/')[0], 200)
        alice, a = self.create_user('alice')
        bob, b = self.create_user('bob')
        self.assertEqual(a.request('GET', '/api/admin/accounts')[0], 403)
        self.assertEqual(a.request('POST', '/api/admin/accounts', {'username': 'bad', 'password': 'ValidPassword!1'})[0], 403)
        self.assertEqual(a.request('POST', '/api/shutdown', {'confirm': True})[0], 403)
        self.assertEqual(a.request('POST', '/api/import', raw=b'bad', csrf=False)[0], 403)
        self.assertEqual(a.request('POST', '/api/auth/logout', origin='http://foreign.invalid')[0], 403)
        self.assertEqual(a.upload(123)[0], 200)
        self.assertEqual(b.upload(456)[0], 200)
        ar = a.request('GET', '/api/models')[1]
        br = b.request('GET', '/api/models')[1]
        self.assertEqual(len(ar), 1)
        self.assertEqual(len(br), 1)
        self.assertNotEqual(ar[0]['id'], br[0]['id'])
        self.assertEqual(ar[0]['ownerId'], alice['id'])
        self.assertEqual(len(self.admin.request('GET', '/api/models')[1]), 2)
        own, foreign = ar[0]['id'], br[0]['id']
        self.assertEqual(a.request('POST', '/api/query', {'id': own, 'sql': 'SELECT * FROM Samples'})[1]['rows'], [[123]])
        for method, path, payload in [
            ('POST', '/api/query', {'id': foreign, 'sql': 'SELECT * FROM Samples'}),
            ('POST', '/api/dax', {'id': foreign, 'groups': [], 'fields': []}),
            ('POST', '/api/delete', {'id': foreign, 'confirmName': 'Same.zip'}),
            ('GET', '/api/export/' + foreign, None),
        ]:
            self.assertEqual(a.request(method, path, payload)[0], 404)
        self.assertEqual(a.request('GET', '/api/export/' + own)[0], 200)
        other_file = next((server.DATA / foreign).glob('*.parquet'))
        sql = "SELECT * FROM read_parquet('" + str(other_file).replace("'", "''") + "')"
        self.assertEqual(a.request('POST', '/api/query', {'id': own, 'sql': sql})[0], 400)
        status, users = self.admin.request('GET', '/api/admin/accounts')
        self.assertEqual(status, 200)
        self.assertEqual({u['username']: u['reportCount'] for u in users}, {'admin': 0, 'alice': 1, 'bob': 1})
        self.assertFalse(any('password' in key or 'salt' in key for u in users for key in u))
        self.assertEqual(self.admin.request('POST', '/api/admin/delete-account', {'id': bob['id'], 'confirmUsername': 'wrong'})[0], 400)
        self.assertEqual(self.admin.request('POST', '/api/admin/delete-account', {'id': bob['id'], 'confirmUsername': 'bob'})[0], 200)
        self.assertEqual(b.request('GET', '/api/models')[0], 401)
        self.assertTrue((server.DATA / foreign / 'model.duckdb').exists())
        self.assertEqual(self.store.report_owner(foreign), self.admin_user['id'])
        self.assertEqual(self.admin.request('POST', '/api/admin/delete-account', {'id': self.admin_user['id'], 'confirmUsername': 'admin'})[0], 400)

    def test_report_sharing_grants_and_revokes_read_access(self):
        alice, a = self.create_user('alice')
        bob, b = self.create_user('bob')
        carol, c = self.create_user('carol')
        status, report = a.upload(321)
        self.assertEqual(status, 200)
        ident = report['id']
        # Add an embedded package to this disposable report's uploaded source.
        with zipfile.ZipFile(server.DATA / ident / 'source.zip', 'a') as archive:
            archive.writestr('custom/share.pbiviz.json', json.dumps({'visual': {'guid': 'SharedVisual0123456789'}, 'content': {'js': 'window.example=true'}, 'capabilities': {'dataRoles': []}}))
        endpoint = '/api/reports/' + ident + '/sharing'
        self.assertEqual(b.request('GET', endpoint)[0], 404)
        users = a.request('GET', endpoint)[1]
        self.assertEqual({u['username'] for u in users}, {'bob', 'carol'})
        self.assertEqual(a.request('POST', endpoint, {'userIds': [bob['id']]}, csrf=False)[0], 403)
        self.assertEqual(a.request('POST', endpoint, {'userIds': ['missing']})[0], 400)
        self.assertEqual(a.request('POST', endpoint, {'userIds': [bob['id'], carol['id']]})[0], 200)
        shared = b.request('GET', '/api/models')[1]
        self.assertEqual(len(shared), 1)
        self.assertTrue(shared[0]['sharedWithMe'])
        self.assertFalse(shared[0]['canManage'])
        self.assertEqual(shared[0]['ownerUsername'], 'alice')
        package_id = shared[0]['customVisuals'][0]['id']
        self.assertEqual(b.request('GET', '/api/custom-visuals/' + package_id)[0], 200)
        self.assertEqual(b.request('POST', '/api/query', {'id': ident, 'sql': 'SELECT * FROM Samples'})[1]['rows'], [[321]])
        self.assertEqual(b.request('POST', '/api/dax', {'id': ident, 'groups': [], 'fields': []})[0], 200)
        self.assertEqual(b.request('GET', '/api/export/' + ident)[0], 200)
        self.assertEqual(b.request('POST', '/api/delete', {'id': ident, 'confirmName': 'Same.zip'})[0], 404)
        self.assertEqual(b.request('POST', endpoint, {'userIds': []})[0], 404)
        # Sharing survives a new store instance; revoking one recipient preserves the other.
        self.assertTrue(Accounts(self.store.path).can_read_report(ident, bob))
        self.assertEqual(a.request('POST', endpoint, {'userIds': [carol['id']]})[0], 200)
        self.assertEqual(b.request('GET', '/api/models')[1], [])
        for method, path, payload in [
            ('POST', '/api/query', {'id': ident, 'sql': 'SELECT 1'}),
            ('POST', '/api/dax', {'id': ident, 'groups': [], 'fields': []}),
            ('GET', '/api/export/' + ident, None),
            ('GET', '/api/custom-visuals/' + package_id, None),
        ]:
            self.assertEqual(b.request(method, path, payload)[0], 404)
        self.assertEqual(b.request('GET', '/api/custom-visuals')[1], [])
        self.assertEqual(len(c.request('GET', '/api/models')[1]), 1)
        self.assertEqual(self.admin.request('POST', endpoint, {'userIds': []})[0], 200)
        self.assertEqual(c.request('GET', '/api/models')[1], [])
        self.assertEqual(a.request('POST', endpoint, {'userIds': [carol['id']]})[0], 200)
        self.assertEqual(a.request('POST', '/api/delete', {'id': ident, 'confirmName': 'Same.zip'})[0], 200)
        self.assertEqual(c.request('GET', '/api/custom-visuals/' + package_id)[0], 404)
        self.assertEqual(a.request('GET', endpoint)[0], 404)

    def test_passwords_sessions_and_legacy_ownership(self):
        alice, a = self.create_user('alice')
        self.assertEqual(a.request('POST', '/api/auth/password', {'currentPassword': 'WrongPassword', 'newPassword': 'ChangedPassword!2'})[0], 403)
        self.assertEqual(a.request('POST', '/api/auth/password', {'currentPassword': 'ExamplePassword!1', 'newPassword': 'ChangedPassword!2'})[0], 200)
        self.assertEqual(a.request('GET', '/api/models')[0], 401)
        self.assertEqual(a.login('alice', 'ExamplePassword!1')[0], 401)
        self.assertEqual(a.login('alice', 'ChangedPassword!2')[0], 200)
        self.assertEqual(self.admin.request('POST', '/api/admin/reset-password', {'id': alice['id'], 'password': 'ResetPassword!3'})[0], 200)
        self.assertEqual(a.request('GET', '/api/models')[0], 401)
        self.assertEqual(a.login('alice', 'ResetPassword!3')[0], 200)
        old_id = uuid.uuid4().hex
        self.assertEqual(self.store.report_owner(old_id), self.admin_user['id'])
        self.assertEqual(a.request('POST', '/api/auth/logout')[0], 200)
        self.assertEqual(a.request('GET', '/api/auth/me')[0], 401)
        self.assertEqual(self.admin.request('POST', '/api/admin/accounts', {'username': 'ADMIN', 'password': 'AnotherPassword!'})[0], 400)
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM users WHERE id=?', (alice['id'],)).fetchone()
            self.assertNotEqual(row['password_hash'], 'ResetPassword!3')
            self.assertEqual(len(row['salt']), 32)
        reloaded = Accounts(self.store.path)
        self.assertEqual(reloaded.admin_id, self.admin_user['id'])
        self.assertEqual(reloaded.login('alice', 'ResetPassword!3')[0]['user']['id'], alice['id'])

    def test_package_isolation_and_session_expiry(self):
        alice, a = self.create_user('alice')
        bob, b = self.create_user('bob')
        from test_custom_visuals import package
        resource = {'visual': {'guid': 'SampleAccountVisual1234'}, 'content': {'js': 'window.sample=true'}, 'capabilities': {'dataRoles': []}}
        raw = package(resource)
        body = b'--visual-test\r\nContent-Disposition: form-data; name="file"; filename="Sample.pbiviz"\r\n\r\n' + raw + b'\r\n--visual-test--\r\n'
        status, visual = b.request('POST', '/api/custom-visuals/import', raw=body, content_type='multipart/form-data; boundary=visual-test')
        self.assertEqual(status, 200)
        self.assertEqual(a.request('GET', '/api/custom-visuals')[1], [])
        self.assertEqual(a.request('GET', '/api/custom-visuals/' + visual['id'])[0], 404)
        self.assertEqual(b.request('GET', '/api/custom-visuals/' + visual['id'])[0], 200)
        self.assertEqual(self.admin.request('GET', '/api/custom-visuals/' + visual['id'])[0], 200)
        with self.store.connect() as db:
            db.execute('UPDATE sessions SET expires=0 WHERE user_id=?', (alice['id'],))
        self.assertEqual(a.request('GET', '/api/auth/me')[0], 401)


if __name__ == '__main__':
    unittest.main()
