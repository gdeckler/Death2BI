"""Local group administration and dynamic report access tests."""
import unittest
from test_accounts import AccountTests
from accounts import Accounts

class GroupTests(unittest.TestCase):
    setUp=AccountTests.setUp
    tearDown=AccountTests.tearDown
    create_user=AccountTests.create_user

    def test_membership_access_and_revocation(self):
        owner,o=self.create_user('group-owner')
        member,m=self.create_user('group-member')
        outsider,x=self.create_user('group-outsider')
        _,report=o.upload(321)
        rid=report['id']
        status,group=self.admin.request('POST','/api/admin/groups',{'name':'Analysts','memberIds':[member['id']]})
        self.assertEqual(status,201)
        for client in (o,m,x):
            self.assertEqual(client.request('GET','/api/admin/groups')[0],403)
            self.assertEqual(client.request('POST','/api/admin/groups',{'name':'Denied','memberIds':[]})[0],403)
        self.assertEqual(m.request('GET','/api/models')[1],[])
        status,options=o.request('GET','/api/reports/'+rid+'/group-sharing')
        self.assertEqual(status,200)
        self.assertEqual(options[0]['memberCount'],1)
        self.assertNotIn('memberIds',options[0])
        self.assertEqual(o.request('POST','/api/reports/'+rid+'/sharing',{'userIds':[],'groupIds':[group['id']]})[0],200)
        self.assertEqual(len(m.request('GET','/api/models')[1]),1)
        query={'id':rid,'sql':'SELECT * FROM Samples'}
        self.assertEqual(m.request('POST','/api/query',query)[1]['rows'],[[321]])
        self.assertEqual(m.request('POST','/api/dax',{'id':rid,'groups':[],'fields':[]})[0],200)
        self.assertEqual(m.request('GET','/api/export/'+rid)[0],200)
        self.assertEqual(m.request('POST','/api/delete',{'id':rid,'confirmName':report['name']})[0],404)
        self.assertEqual(m.request('GET','/api/reports/'+rid+'/group-sharing')[0],404)
        self.assertEqual(x.request('POST','/api/query',query)[0],404)
        package='ab'*16
        self.store.register_report_packages(rid,[{'id':package}])
        self.assertTrue(self.store.package_access(package,member))
        self.assertFalse(self.store.package_access(package,outsider))
        self.assertEqual(self.admin.request('POST','/api/admin/groups/update',{'id':group['id'],'name':'Analysts renamed','memberIds':[]})[0],200)
        self.assertEqual(m.request('GET','/api/models')[1],[])
        for path in ('/api/query','/api/dax'):
            self.assertEqual(m.request('POST',path,query)[0],404)
        self.assertEqual(m.request('GET','/api/export/'+rid)[0],404)
        self.assertFalse(self.store.package_access(package,member))
        self.assertEqual(self.admin.request('POST','/api/admin/groups/update',{'id':group['id'],'name':'Analysts renamed','memberIds':[member['id']]})[0],200)
        self.assertTrue(self.store.package_access(package,member))
        self.assertEqual(o.request('POST','/api/reports/'+rid+'/sharing',{'userIds':[],'groupIds':[]})[0],200)
        self.assertFalse(self.store.package_access(package,member))
        self.assertEqual(m.request('POST','/api/query',query)[0],404)

    def test_validation_atomicity_deletion_and_direct_shares(self):
        member,m=self.create_user('group-test')
        _,report=self.admin.upload(654)
        rid=report['id']
        _,g=self.admin.request('POST','/api/admin/groups',{'name':'Team','memberIds':[member['id'],member['id']]})
        self.assertEqual(len(g['memberIds']),1)
        for name in ('team',' ','x'*81):
            self.assertEqual(self.admin.request('POST','/api/admin/groups',{'name':name,'memberIds':[]})[0],400)
        self.assertEqual(self.admin.request('POST','/api/admin/groups/update',{'id':g['id'],'name':'Bad change','memberIds':['missing']})[0],400)
        groups=self.admin.request('GET','/api/admin/groups')[1]
        self.assertEqual(groups[0]['name'],'Team')
        self.assertEqual(groups[0]['memberIds'],[member['id']])
        self.assertEqual(self.admin.request('POST','/api/admin/groups/update',{'id':g['id'],'name':'No CSRF','memberIds':[]},csrf=False)[0],403)
        share='/api/reports/'+rid+'/sharing'
        self.admin.request('POST',share,{'userIds':[member['id']],'groupIds':[g['id']]})
        self.assertEqual(self.admin.request('POST',share,{'userIds':[],'groupIds':['invalid']})[0],400)
        self.assertTrue(self.store.can_read_report(rid,member))
        # Old clients can update direct shares without accidentally clearing groups.
        self.admin.request('POST',share,{'userIds':[]})
        self.assertTrue(self.store.can_read_report(rid,member))
        self.admin.request('POST',share,{'userIds':[member['id']]})
        self.assertEqual(self.admin.request('POST','/api/admin/groups/delete',{'id':g['id'],'confirmName':'wrong'})[0],400)
        self.assertEqual(self.admin.request('POST','/api/admin/groups/delete',{'id':g['id'],'confirmName':'Team'})[0],200)
        self.assertTrue(self.store.can_read_report(rid,member))
        self.admin.request('POST',share,{'userIds':[]})
        self.assertFalse(self.store.can_read_report(rid,member))
        # Empty groups allow future memberships and survive account-store reload.
        _,empty=self.admin.request('POST','/api/admin/groups',{'name':'Future','memberIds':[]})
        self.admin.request('POST',share,{'userIds':[],'groupIds':[empty['id']]})
        self.admin.request('POST','/api/admin/groups/update',{'id':empty['id'],'name':'Future','memberIds':[member['id']]})
        reopened=Accounts(self.store.path)
        self.assertTrue(reopened.can_read_report(rid,member))
        self.admin.request('POST','/api/admin/delete-account',{'id':member['id'],'confirmUsername':member['username']})
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM group_members').fetchone()[0],0)
        self.admin.request('POST','/api/delete',{'id':rid,'confirmName':report['name']})
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM report_group_shares').fetchone()[0],0)

if __name__=='__main__':unittest.main()
