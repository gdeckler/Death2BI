"""SQL cancellation uses isolated servers/databases and owner-scoped requests."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import unittest
import http.client
import json
import os
import socket
import struct
from unittest.mock import patch
import uuid

import duckdb
import rls
import server
import test_accounts
from query_cancellation import QueryCancellation, QueryRequestError


def wait_until(predicate, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Expected SQL request state was not reached')


class RegistryTests(unittest.TestCase):
    def test_owner_early_duplicate_expiry_bounds_and_legacy_requests(self):
        registry = QueryCancellation(early_limit=3, early_seconds=.02)
        request = uuid.uuid4().hex
        registry.cancel('alice', request)
        with registry.request('bob', request):
            with self.assertRaises(QueryRequestError) as duplicate:
                with registry.request('bob', request):
                    pass
            self.assertEqual(duplicate.exception.status, 409)
        with self.assertRaises(QueryRequestError) as early:
            with registry.request('alice', request):
                self.fail('early-cancelled request must never enter SQL setup')
        self.assertEqual(early.exception.status, 499)
        for _ in range(8):
            registry.cancel('alice', uuid.uuid4().hex)
        self.assertEqual(len(registry.early), 3)
        time.sleep(.03)
        with registry.request('alice'):
            self.assertEqual(len(registry.jobs), 1)
        self.assertFalse(registry.early)
        self.assertFalse(registry.jobs)
        for invalid in ('', 'invalid', None, 1):
            with self.assertRaises(QueryRequestError):
                registry.cancel('alice', invalid)

    def test_interrupt_and_close_are_serialized_and_cancel_remains_effective(self):
        class Connection:
            closed = False
            calls = 0
            after_close = 0
            def interrupt(self):
                if self.closed:
                    self.after_close += 1
                    raise AssertionError('interrupt raced a closed connection')
                self.calls += 1
            def close(self):
                time.sleep(.02)
                self.closed = True
        registry = QueryCancellation()
        con = Connection()
        with registry.request('alice', uuid.uuid4().hex) as request:
            request.attach(con)
            request.cancel()
            wait_until(lambda: con.calls >= 2)
            request.close_connection(con)
            calls = con.calls
            time.sleep(.08)
            self.assertEqual(con.calls, calls)
            self.assertEqual(con.after_close, 0)
            with self.assertRaises(QueryRequestError):
                request.check()
        self.assertTrue(request.finished.is_set())
        self.assertFalse(request.interrupter.is_alive())
        self.assertFalse(registry.jobs)
        registry.close()
        with self.assertRaises(QueryRequestError) as closed:
            with registry.request('alice'):
                pass
        self.assertEqual(closed.exception.status, 503)


class QueryCancellationHTTPTests(unittest.TestCase):
    def setUp(self):
        test_accounts.AccountTests.setUp(self)
        self.security = patch('server.security_dir', return_value=self.temp/'security')
        self.security.start()
        self.report = self.admin.upload(123)[1]

    def tearDown(self):
        self.security.stop()
        test_accounts.AccountTests.tearDown(self)

    create_user = test_accounts.AccountTests.create_user

    def query(self, client, request_id=None, sql='SELECT 42 AS answer'):
        payload = {'id': self.report['id'], 'sql': sql, 'purpose': 'visual'}
        if request_id is not None:
            payload['requestId'] = request_id
        return client.request('POST', '/api/query', payload)

    def test_running_sql_cancellation_owner_isolation_and_next_query(self):
        _, other = self.create_user('other')
        request = uuid.uuid4().hex
        with ThreadPoolExecutor(1) as executor:
            future = executor.submit(self.query, self.admin, request,
                                     'SELECT SUM(SIN(i)) FROM range(1000000000000) t(i)')
            wait_until(lambda: any(job.connections for job in self.httpd.query_cancellation.jobs.values()))
            self.assertEqual(other.request('POST', '/api/query/cancel', {'requestId': request})[0], 200)
            time.sleep(.1)
            self.assertFalse(future.done(), 'another account must not interrupt this calculation')
            started = time.monotonic()
            self.assertEqual(self.admin.request('POST', '/api/query/cancel', {'requestId': request})[0], 200)
            status, result = future.result(3)
        self.assertLess(time.monotonic()-started, 2)
        self.assertEqual(status, 499, result)
        self.assertIn('cancelled', result['error'])
        self.assertFalse(self.httpd.query_cancellation.jobs)
        self.assertFalse(server.ACTIVE_QUERIES)
        self.assertEqual(self.query(self.admin)[1]['rows'], [[42]], 'old callers without request IDs remain valid')
        self.assertEqual(self.query(self.admin, uuid.uuid4().hex)[1]['rows'], [[42]])
        self.assertEqual(self.admin.request('POST', '/api/query/cancel', {'requestId': request}, csrf=False)[0], 403)
        self.assertEqual(self.admin.request('POST', '/api/query/cancel', {'requestId': 'invalid'})[0], 400)

    def test_early_and_waiting_for_report_lock_cancellation(self):
        early = uuid.uuid4().hex
        self.admin.request('POST', '/api/query/cancel', {'requestId': early})
        self.assertEqual(self.query(self.admin, early)[0], 499)
        request = uuid.uuid4().hex
        server.LOCK.acquire()
        try:
            with ThreadPoolExecutor(1) as executor:
                future = executor.submit(self.query, self.admin, request)
                try:
                    wait_until(lambda: (self.admin_user['id'], request) in self.httpd.query_cancellation.jobs)
                    self.assertEqual(self.admin.request('POST', '/api/query/cancel', {'requestId': request})[0], 200)
                finally:
                    server.LOCK.release()
                status, result = future.result(3)
        finally:
            if server.LOCK.locked():
                server.LOCK.release()
        self.assertEqual(status, 499, result)
        self.assertFalse(server.ACTIVE_QUERIES)
        self.assertFalse(self.httpd.query_cancellation.jobs)
        self.assertEqual(self.query(self.admin)[0], 200)

    def test_rls_setup_is_interruptible_does_not_hold_global_lock_and_fails_closed(self):
        alice, client = self.create_user('alice')
        ident = self.report['id']
        self.admin.request('POST', '/api/reports/'+ident+'/sharing', {'userIds': [alice['id']]})
        config = {'enabled': True, 'roles': [{'name': 'Own', 'userIds': [alice['id']], 'groupIds': [],
                  'rules': [{'table': 'Samples', 'column': 'Value', 'operator': 'eq', 'values': [123]}]}]}
        self.assertEqual(self.admin.request('POST', '/api/admin/rls', {'id': ident, 'config': config})[0], 200)
        started = threading.Event()
        original = duckdb.connect
        class SlowSecuredSource:
            def __init__(self, connection):
                self.connection = connection
            def execute(self, sql, *args):
                if sql.startswith('SELECT * FROM "Samples" WHERE '):
                    started.set()
                    return self.connection.execute('SELECT SUM(SIN(i)) FROM range(1000000000000) t(i)')
                return self.connection.execute(sql, *args)
            def interrupt(self):
                self.connection.interrupt()
            def close(self):
                self.connection.close()
        def connect(path, *args, **kwargs):
            connection = original(path, *args, **kwargs)
            return SlowSecuredSource(connection) if str(path).endswith('model.duckdb') else connection
        request = uuid.uuid4().hex
        with patch.object(rls.duckdb, 'connect', side_effect=connect), ThreadPoolExecutor(1) as executor:
            future = executor.submit(self.query, client, request)
            self.assertTrue(started.wait(3))
            self.assertEqual(self.query(self.admin)[1]['rows'], [[42]], 'RLS materialization must not block unrelated requests')
            self.assertEqual(client.request('POST', '/api/query/cancel', {'requestId': request})[0], 200)
            status, result = future.result(3)
        self.assertEqual(status, 499, result)
        self.assertNotEqual(status, 403, 'cancellation is not an RLS policy failure')
        self.assertFalse(server.ACTIVE_QUERIES)
        self.assertFalse(self.httpd.query_cancellation.jobs)
        self.assertEqual(self.query(client)[1]['rows'], [[42]], 'the next request still establishes a secured connection')

    def test_public_link_cancellation_is_authenticated_and_owner_scoped(self):
        from test_public_links import PublicClient
        from urllib.parse import urlsplit, parse_qs
        guests = []
        for _ in range(2):
            status, link = self.admin.request('POST', '/api/reports/'+self.report['id']+'/public-links', {'confirmPublic': True})
            self.assertEqual(status, 201, link)
            guests.append(PublicClient(self.httpd, parse_qs(urlsplit(link['url']).fragment)['public'][0]))
        request = uuid.uuid4().hex
        with ThreadPoolExecutor(1) as executor:
            future = executor.submit(self.query, guests[0], request,
                                     'SELECT SUM(SIN(i)) FROM range(1000000000000) t(i)')
            wait_until(lambda: any(job.connections for job in self.httpd.query_cancellation.jobs.values()))
            guests[1].request('POST', '/api/query/cancel', {'requestId': request})
            time.sleep(.1)
            self.assertFalse(future.done())
            self.assertEqual(guests[0].request('POST', '/api/query/cancel', {'requestId': request}, csrf=False)[0], 403)
            self.assertEqual(guests[0].request('POST', '/api/query/cancel', {'requestId': request})[0], 200)
            self.assertEqual(future.result(3)[0], 499)
        self.assertEqual(self.query(guests[0])[1]['rows'], [[42]])

    def test_disconnected_http_response_does_not_log_a_handler_failure(self):
        request = uuid.uuid4().hex
        con = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        headers = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765',
                   'Content-Type': 'application/json', 'Cookie': self.admin.cookie,
                   'X-CSRF-Token': self.admin.csrf}
        body = json.dumps({'id': self.report['id'], 'requestId': request,
                           'sql': 'SELECT SUM(SIN(i)) FROM range(1000000000000) t(i)'})
        delivered = threading.Event()
        original_send = server.Handler.send
        def send(handler, *args, **kwargs):
            try:
                return original_send(handler, *args, **kwargs)
            finally:
                if handler.path == '/api/query':
                    delivered.set()
        with patch.object(server.Handler, 'send', new=send), patch.object(self.httpd, 'handle_error') as errors:
            con.request('POST', '/api/query', body, headers)
            wait_until(lambda: any(job.connections for job in self.httpd.query_cancellation.jobs.values()))
            # Close with an actual TCP reset, as a browser abandoning fetch can.
            con.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                struct.pack('HH' if os.name == 'nt' else 'ii', 1, 0))
            con.close()
            self.assertEqual(self.admin.request('POST', '/api/query/cancel', {'requestId': request})[0], 200)
            self.assertTrue(delivered.wait(3))
            self.assertFalse(errors.called, 'normal abandoned responses must not emit misleading server tracebacks')
        self.assertFalse(server.ACTIVE_QUERIES)
        self.assertFalse(self.httpd.query_cancellation.jobs)
        self.assertEqual(self.query(self.admin)[1]['rows'], [[42]])


class ScatterCancellationTests(unittest.TestCase):
    def test_checkpoint_cancellation_stops_before_scanning_the_full_domain(self):
        from scatter_sampling import sample
        rows = [[i, i%97] for i in range(20000)]
        calls = []
        def check():
            calls.append(True)
            if len(calls) == 3:
                raise QueryRequestError('SQL request cancelled.', 499)
        with self.assertRaises(QueryRequestError):
            sample(rows, ['X', 'Y'], ['DOUBLE', 'DOUBLE'], {'x': 0, 'y': 1}, check=check)
        self.assertEqual(len(calls), 3)
        plain = sample(rows, ['X', 'Y'], ['DOUBLE', 'DOUBLE'], {'x': 0, 'y': 1})
        checked = sample(rows, ['X', 'Y'], ['DOUBLE', 'DOUBLE'], {'x': 0, 'y': 1}, check=lambda: None)
        for result in (plain, checked):
            result['sampling'].pop('elapsedSeconds')
        self.assertEqual(plain, checked, 'cancellation checkpoints preserve selected rows and full-domain statistics')


if __name__ == '__main__':
    unittest.main()
