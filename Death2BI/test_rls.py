import io
import json
from pathlib import Path
import shutil
import unittest
import uuid
import zipfile
import duckdb
import test_accounts
import test_tls
from rls import RLS,connect
from accounts import Accounts,AuthError


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.folder=Path('work').resolve()/('rls-test-'+uuid.uuid4().hex);self.folder.mkdir(parents=True)
        self.store=Accounts(self.folder/'accounts.sqlite3');self.admin=self.store.user(self.store.admin_id)
        self.alice=self.store.create(self.admin,'alice','ExamplePassword!1')
        self.path=self.folder/'model.duckdb';db=duckdb.connect(str(self.path))
        db.execute("CREATE TABLE Regions(Code VARCHAR); INSERT INTO Regions VALUES ('US'),('CA'),('GB')")
        db.execute("CREATE TABLE Sales(Region VARCHAR, Amount INTEGER, Owner VARCHAR); INSERT INTO Sales VALUES ('US',10,'alice'),('CA',20,'bob'),('GB',30,'carol')");db.close()
        self.model={'tables':[{'name':'Regions','columns':[{'name':'Code'}]},{'name':'Sales','columns':[{'name':x} for x in ['Region','Amount','Owner']]}],'relationships':[{'IsActive':True,'Cardinality':'M:1','FromTableName':'Sales','FromColumnName':'Region','ToTableName':'Regions','ToColumnName':'Code','CrossFilteringBehavior':'Both'}],'measures':[{'Name':'All Sales','TableName':'Sales','Expression':'CALCULATE(SUM(Sales[Amount]), ALL(Sales))'}]}
        self.rls=RLS(self.store)

    def tearDown(self):shutil.rmtree(self.folder)

    def role(self,values,user=True):return {'name':'Regions','userIds':[self.alice['id']] if user else [],'groupIds':[],'rules':[{'table':'Regions','column':'Code','operator':'in','values':values}]}
    def save(self,roles):return self.rls.save('report',{'enabled':True,'roles':roles},self.model,self.admin)
    def db(self,actor=None):return connect(self.path,self.model,self.rls.effective('report',actor or self.alice))

    def test_relations_sql_bypass_and_dax_all(self):
        self.save([self.role(['US'])]);db=self.db()
        try:
            self.assertEqual(db.execute('SELECT * FROM main.Sales').fetchall(),[('US',10,'alice')])
            self.assertEqual(db.execute('SELECT * FROM Regions').fetchall(),[('US',)])
            with self.assertRaises(duckdb.Error):db.execute("SELECT * FROM read_parquet('missing.parquet')")
            with self.assertRaises(duckdb.Error):db.execute('SELECT * FROM model.main.Sales')
            from dax_engine import evaluate_visual
            result=evaluate_visual(db,self.model,{'fields':[{'Measure':{'Expression':{'SourceRef':{'Entity':'Sales'}},'Property':'All Sales'}}],'groups':[{'filters':[],'externalFilters':[],'contexts':{},'scope':[],'values':{}}]})
            self.assertEqual(result['rows'],[[10]])
        finally:db.close()
        db=self.db(self.admin)
        try:self.assertEqual(db.execute('SELECT SUM(Amount) FROM Sales').fetchone()[0],60)
        finally:db.close()

    def test_roles_groups_dynamic_and_fail_closed(self):
        first=self.role(['US']);second={**self.role(['CA']),'name':'Canada'};self.save([first,second]);db=self.db()
        try:self.assertEqual(db.execute('SELECT SUM(Amount) FROM Sales').fetchone()[0],30)
        finally:db.close()
        group=self.store.save_group(self.admin,'US readers',[self.alice['id']]);role=self.role(['US'],False);role['groupIds']=[group['id']];self.save([role]);stamp=self.rls.effective('report',self.alice)['stamp']
        self.store.save_group(self.admin,'US readers',[],group['id']);self.assertNotEqual(stamp,self.rls.effective('report',self.alice)['stamp']);db=self.db()
        try:self.assertEqual(db.execute('SELECT COUNT(*) FROM Sales').fetchone()[0],0)
        finally:db.close()
        dynamic={'name':'Own rows','userIds':[self.alice['id']],'groupIds':[],'rules':[{'table':'Sales','column':'Owner','operator':'eq','values':[{'identity':'username'}]}]};self.save([dynamic]);db=self.db()
        try:self.assertEqual(db.execute('SELECT SUM(Amount) FROM Sales').fetchone()[0],10)
        finally:db.close()
        dynamic['rules'][0]['values']=[{'identity':'email'}];self.save([dynamic]);db=self.db()
        try:self.assertEqual(db.execute('SELECT COUNT(*) FROM Sales').fetchone()[0],0)
        finally:db.close()
        self.save([self.role(['US'])]);self.model['tables'][0]['columns']=[]
        with self.assertRaises(AuthError):self.db()

    def test_injection_and_ambiguous_relationships_fail_closed(self):
        self.save([self.role(["US' OR TRUE --"])]);db=self.db()
        try:self.assertEqual(db.execute('SELECT COUNT(*) FROM Sales').fetchone()[0],0)
        finally:db.close()
        self.save([self.role(['US'])]);self.model['relationships'].append(dict(self.model['relationships'][0]))
        with self.assertRaises(AuthError):self.db()


class PolicyHTTPTests(unittest.TestCase):
    setUp=test_tls.TLSHTTPTests.setUp
    tearDown=test_tls.TLSHTTPTests.tearDown

    def test_queries_csv_metadata_exports_and_preview(self):
        alice,a=test_accounts.AccountTests.create_user(self,'alice');bob,b=test_accounts.AccountTests.create_user(self,'bob')
        status,report=self.admin.upload(123);self.assertEqual(status,200);ident=report['id']
        self.admin.request('POST','/api/reports/'+ident+'/sharing',{'userIds':[alice['id'],bob['id']]})
        data={'id':ident,'config':{'enabled':True,'roles':[{'name':'Allowed','userIds':[alice['id']],'groupIds':[],'rules':[{'table':'Samples','column':'Value','operator':'eq','values':[123]}]}]}}
        self.assertEqual(a.request('POST','/api/admin/rls',data)[0],403)
        self.assertEqual(self.admin.request('POST','/api/admin/rls',data,csrf=False)[0],403)
        self.assertEqual(self.admin.request('POST','/api/admin/rls',data)[0],200)
        query={'id':ident,'sql':'SELECT * FROM Samples'}
        self.assertEqual(a.request('POST','/api/query',query)[1]['rows'],[[123]])
        self.assertEqual(b.request('POST','/api/query',query)[1]['rows'],[])
        status,csv=b.request('POST','/api/export-data',query);self.assertEqual(status,200);self.assertNotIn(b'123',csv)
        self.assertEqual(a.request('GET','/api/export/'+ident)[0],403)
        metadata=b.request('GET','/api/models')[1][0];self.assertEqual(metadata['tables'][0]['rows'],0);self.assertTrue(metadata['rlsApplied'])
        stamp=a.request('GET','/api/security-context?id='+ident)[1]['stamp']
        data['config']['roles'][0]['rules'][0]['values']=[999];self.assertEqual(self.admin.request('POST','/api/admin/rls',data)[0],200)
        self.assertNotEqual(stamp,a.request('GET','/api/security-context?id='+ident)[1]['stamp'])
        self.assertEqual(a.request('POST','/api/query',{**query,'securityStamp':stamp})[0],409)
        self.assertEqual(a.request('POST','/api/query',query)[1]['rows'],[])
        status,result=self.admin.request('POST','/api/admin/rls/preview',{'id':ident,'userId':alice['id'],'sql':'SELECT * FROM Samples'})
        self.assertEqual(status,200);self.assertEqual(result['counts']['Samples'],0);self.assertEqual(result['preview']['rows'],[])
        status,owned=a.upload(456);self.assertEqual(status,200)
        self.assertEqual(self.admin.request('POST','/api/admin/rls',{'id':owned['id'],'config':{'enabled':True,'roles':[]}})[0],200)
        self.assertEqual(a.request('POST','/api/query',{'id':owned['id'],'sql':'SELECT * FROM Samples'})[1]['rows'],[])
        self.assertEqual(a.request('GET','/api/export/'+owned['id'])[0],403)


if __name__=='__main__':unittest.main()
