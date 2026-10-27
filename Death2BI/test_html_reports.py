"""HTML/snapshot imports use existing account boundaries and never execute source."""
import base64
import json
import unittest
from html_reports import inspect_html
import test_accounts as fixtures


class HTMLReportTests(fixtures.AccountTests):
    # Reuse fixture setup without rerunning unrelated inherited account tests.
    test_slow_dax_does_not_block_table_or_custom_visual_queries = None
    test_report_isolation_and_administration = None
    test_report_sharing_grants_and_revokes_read_access = None
    test_passwords_sessions_and_legacy_ownership = None
    test_package_isolation_and_session_expiry = None

    def upload_html(self, client, source, name='Report.html'):
        boundary = 'html-test-boundary'
        body = ('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="'+name+'"\r\nContent-Type: text/html\r\n\r\n').encode()+source.encode()+('\r\n--'+boundary+'\r\nContent-Disposition: form-data; name="mode"\r\n\r\nnew\r\n--'+boundary+'--\r\n').encode()
        return client.request('POST','/api/import',raw=body,content_type='multipart/form-data; boundary='+boundary)

    def test_html_isolation_sharing_and_deletion(self):
        alice,a=self.create_user('alice')
        bob,b=self.create_user('bob')
        source='<html><body><h1>Embedded data</h1><script>window.payload=[1,2,3]</script></body></html>'
        status,report=self.upload_html(a,source)
        self.assertEqual(status,200)
        self.assertEqual(report['reportKind'],'html')
        ident=report['id']; endpoint='/api/html/'+ident
        self.assertEqual(a.request('GET',endpoint)[1]['html'],source)
        self.assertEqual(b.request('GET',endpoint)[0],404)
        self.assertEqual(self.admin.request('GET',endpoint)[0],200)
        self.assertEqual(a.request('POST','/api/reports/'+ident+'/sharing',{'userIds':[bob['id']]})[0],200)
        self.assertEqual(b.request('GET',endpoint)[1]['html'],source)
        self.assertFalse(b.request('GET','/api/models')[1][0]['canManage'])
        self.assertEqual(a.request('POST','/api/reports/'+ident+'/sharing',{'userIds':[]})[0],200)
        self.assertEqual(b.request('GET',endpoint)[0],404)
        second=self.upload_html(a,source)[1]
        self.assertNotEqual(ident,second['id'])
        self.assertEqual(a.request('POST','/api/delete',{'id':ident,'confirmName':report['name']})[0],200)
        self.assertEqual(a.request('GET',endpoint)[0],404)

    def test_snapshot_metadata_and_invalid_package(self):
        package={'format':'death2powerbi-snapshot','version':1,'pages':[{'name':'Summary','html':'<svg></svg>'},{'name':'Hidden page','hidden':True,'html':'<table></table>'}]}
        source='<script type="application/octet-stream" id="death2powerbi-snapshot">'+base64.b64encode(json.dumps(package).encode()).decode()+'</script>'
        status,report=self.upload_html(self.admin,source)
        self.assertEqual(status,200)
        self.assertEqual(report['reportKind'],'snapshot')
        self.assertEqual(len(report['pages']),2)
        self.assertTrue(report['pages'][1]['hidden'])
        self.assertEqual(self.upload_html(self.admin,source.replace('snapshot">','snapshot">!'))[0],400)
        with self.assertRaises(ValueError):inspect_html(b'\xff\xfe')


if __name__=='__main__':unittest.main()
