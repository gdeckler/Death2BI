"""Workspace lifecycle and authorization tests use disposable accounts and reports."""
import io
import unittest
import zipfile
from test_accounts import AccountTests
from accounts import Accounts

class WorkspaceTests(unittest.TestCase):
    setUp = AccountTests.setUp
    tearDown = AccountTests.tearDown
    create_user = AccountTests.create_user

    def test_lifecycle(self):
        status, spaces = self.admin.request('GET','/api/workspaces')
        self.assertEqual(status,200)
        default=spaces[0]
        self.assertEqual(default['name'],'My Workspace')
        _, report=self.admin.upload(123)
        self.assertEqual(report['workspaceId'],default['id'])
        status, space=self.admin.request('POST','/api/workspaces',{'name':'Planning'})
        self.assertEqual(status,201)
        for name in ('planning',' ','My Workspace'):
            self.assertEqual(self.admin.request('POST','/api/workspaces',{'name':name})[0],400)
        self.assertEqual(self.admin.request('POST','/api/workspaces/rename',{'id':space['id'],'name':'Forecasts'})[0],200)
        self.assertEqual(self.admin.request('POST','/api/workspaces/move-report',{'reportId':report['id'],'workspaceId':space['id']})[0],200)
        self.assertEqual(self.admin.request('GET','/api/models')[1][0]['workspaceId'],space['id'])
        reopened=Accounts(self.store.path)
        self.assertEqual(reopened.workspace_for_report(self.admin_user,report['id']),space['id'])
        self.assertEqual(self.admin.request('POST','/api/workspaces/delete',{'id':default['id']})[0],400)
        self.assertEqual(self.admin.request('POST','/api/workspaces/delete',{'id':space['id']})[0],200)
        models=self.admin.request('GET','/api/models')[1]
        self.assertEqual(len(models),1)
        self.assertEqual(models[0]['workspaceId'],default['id'])
        self.assertEqual(self.admin.request('POST','/api/query',{'id':report['id'],'sql':'SELECT * FROM Samples'})[1]['rows'],[[123]])

    def test_isolation_and_sharing(self):
        alice,a=self.create_user('workspace-alice')
        bob,b=self.create_user('workspace-bob')
        _, private=a.request('POST','/api/workspaces',{'name':'Private'})
        self.assertEqual(len(b.request('GET','/api/workspaces')[1]),1)
        for client in (b,self.admin):
            self.assertEqual(client.request('POST','/api/workspaces/rename',{'id':private['id'],'name':'Stolen'})[0],404)
            self.assertEqual(client.request('POST','/api/workspaces/delete',{'id':private['id']})[0],404)
        _,report=a.upload(456)
        _,received=b.request('POST','/api/workspaces',{'name':'Received'})
        move={'reportId':report['id'],'workspaceId':received['id']}
        self.assertEqual(b.request('POST','/api/workspaces/move-report',move)[0],404)
        self.assertEqual(a.request('POST','/api/reports/'+report['id']+'/sharing',{'userIds':[bob['id']]})[0],200)
        self.assertEqual(b.request('POST','/api/workspaces/move-report',move)[0],200)
        self.assertNotEqual(a.request('GET','/api/models')[1][0]['workspaceId'],received['id'])
        self.assertEqual(b.request('GET','/api/models')[1][0]['workspaceId'],received['id'])
        self.assertEqual(a.request('POST','/api/workspaces/move-report',move)[0],404)
        self.assertEqual(a.request('POST','/api/workspaces/rename',{'id':private['id'],'name':'No CSRF'},csrf=False)[0],403)
        a.request('POST','/api/reports/'+report['id']+'/sharing',{'userIds':[]})
        self.assertEqual(b.request('GET','/api/models')[1],[])
        self.assertEqual(b.request('POST','/api/workspaces/move-report',move)[0],404)

    def test_import_and_legacy_migration(self):
        _,space=self.admin.request('POST','/api/workspaces',{'name':'Imports'})
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('Samples.csv','Value\n789\n')
        def upload(ident):
            raw=b'--wstest\r\nContent-Disposition: form-data; name="file"; filename="sample.zip"\r\n\r\n'+out.getvalue()+b'\r\n--wstest\r\nContent-Disposition: form-data; name="workspaceId"\r\n\r\n'+ident.encode()+b'\r\n--wstest\r\nContent-Disposition: form-data; name="mode"\r\n\r\nnew\r\n--wstest--\r\n'
            return self.admin.request('POST','/api/import',raw=raw,content_type='multipart/form-data; boundary=wstest')
        status,report=upload(space['id'])
        self.assertEqual(status,200)
        self.assertEqual(report['workspaceId'],space['id'])
        self.assertEqual(upload('invalid')[0],404)
        self.assertEqual(len(self.admin.request('GET','/api/models')[1]),1)
        with self.store.connect() as db:db.execute('DELETE FROM workspace_reports WHERE report_id=?',(report['id'],))
        default=self.admin.request('GET','/api/workspaces')[1][0]
        self.assertEqual(self.admin.request('GET','/api/models')[1][0]['workspaceId'],default['id'])
        self.admin.request('POST','/api/delete',{'id':report['id'],'confirmName':report['name']})
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM workspace_reports').fetchone()[0],0)

if __name__=='__main__':unittest.main()
