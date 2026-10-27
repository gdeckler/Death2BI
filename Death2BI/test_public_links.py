"""Anonymous report links use disposable reports and private account databases only."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import json
import threading
import unittest
from urllib.parse import urlsplit,parse_qs
from unittest.mock import patch
import test_accounts
from public_links import PublicLinks
from test_dax_pool_http import DaxPoolHTTPTests
import server


class PublicClient(test_accounts.Client):
    def __init__(self,httpd,token,cookie=''):
        super().__init__(httpd);self.token=token;self.cookie=cookie
        self.csrf=hashlib.sha256(('public-csrf:'+token).encode()).hexdigest()

    def request(self,method,path,payload=None,csrf=True,**kwargs):
        headers={'Host':'127.0.0.1:8765','Origin':'http://127.0.0.1:8765','X-Report-Link':self.token,'Content-Type':'application/json','Cookie':self.cookie}
        if csrf:headers['X-CSRF-Token']=self.csrf
        con=http.client.HTTPConnection('127.0.0.1',self.port,timeout=15)
        con.request(method,path,json.dumps(payload) if payload is not None else None,headers)
        response=con.getresponse();data=json.loads(response.read());con.close()
        return response.status,data


class PublicLinkTests(unittest.TestCase):
    def setUp(self):
        test_accounts.AccountTests.setUp(self)
        self.security=patch('server.security_dir',return_value=self.temp/'security');self.security.start()
    def tearDown(self):
        self.security.stop();test_accounts.AccountTests.tearDown(self)
    create_user=test_accounts.AccountTests.create_user

    def link(self,client,ident,**values):
        status,result=client.request('POST','/api/reports/'+ident+'/public-links',{'confirmPublic':True,**values})
        self.assertEqual(status,201,result)
        token=parse_qs(urlsplit(result['url']).fragment)['public'][0]
        return result,PublicClient(self.httpd,token)

    def test_repeat_visits_scope_management_and_revocation(self):
        alice,a=self.create_user('alice');bob,b=self.create_user('bob')
        report=a.upload(42)[1];other=b.upload(99)[1];ident=report['id']
        self.assertEqual(b.request('POST','/api/reports/'+ident+'/public-links',{'confirmPublic':True})[0],404)
        self.assertEqual(a.request('POST','/api/reports/'+ident+'/public-links',{})[0],400)
        link,guest=self.link(a,ident)
        with self.store.connect() as db:
            stored=dict(db.execute('SELECT * FROM public_report_links WHERE id=?',(link['id'],)).fetchone())
            self.assertNotIn(guest.token,json.dumps(stored));self.assertEqual(stored['token_hash'],hashlib.sha256(guest.token.encode()).hexdigest())
        for _ in range(2):
            status,session=guest.request('GET','/api/auth/me');self.assertEqual(status,200);self.assertFalse(session['user']['isAdmin'])
        self.assertEqual(test_accounts.Client(self.httpd).request('GET','/api/models/'+ident)[0],401)
        self.assertEqual(guest.request('POST','/api/query',{'id':ident,'sql':'SELECT * FROM Samples'})[1]['rows'],[[42]])
        self.assertEqual(guest.request('POST','/api/query',{'id':other['id'],'sql':'SELECT * FROM Samples'})[0],404)
        for method,path,payload in [('GET','/api/admin/accounts',None),('GET','/api/workspaces',None),('GET','/api/export/'+ident,None),('GET','/api/reading-position',None),('POST','/api/shutdown',{'confirm':True}),('POST','/api/delete',{'id':ident}),('POST','/api/reports/'+ident+'/sharing',{'userIds':[]})]:
            self.assertEqual(guest.request(method,path,payload)[0],403,(method,path))
        self.assertEqual(guest.request('POST','/api/query',{'id':ident,'sql':'SELECT 1'},csrf=False)[0],403)
        # Even an existing administrator's cookie must not upgrade a public bearer.
        guest.cookie=self.admin.cookie
        self.assertEqual(guest.request('GET','/api/admin/accounts')[0],403)
        self.assertFalse(guest.request('GET','/api/auth/me')[1]['user']['isAdmin'])
        audit=self.admin.request('GET','/api/admin/public-links')[1]
        self.assertEqual(audit[0]['visits'],3);self.assertNotIn(guest.token,json.dumps(audit))
        self.assertEqual(b.request('GET','/api/admin/public-links')[0],403)
        self.assertEqual(b.request('POST','/api/public-links/remove',{'id':link['id']})[0],404)
        self.assertEqual(self.admin.request('POST','/api/public-links/remove',{'id':link['id']})[0],200)
        self.assertEqual(guest.request('GET','/api/auth/me')[0],404)
        self.assertIsNotNone(self.admin.request('GET','/api/admin/public-links')[1][0]['removed_at'])

    def test_model_metadata_packages_and_process_pool(self):
        ident=self.admin.upload(123)[1]['id'];path=server.DATA/ident/'manifest.json'
        model=json.loads(path.read_text());model['pages']=[{'id':'visible','name':'Visible','visuals':[]},{'id':'hidden','name':'Hidden','hidden':True,'visuals':[]}]
        model['modelDefinitions']={'privateM':'source-secret'};path.write_text(json.dumps(model))
        link,guest=self.link(self.admin,ident)
        status,visible=guest.request('GET','/api/models/'+ident);self.assertEqual(status,200,visible)
        self.assertEqual([p['id'] for p in visible['pages']],['visible']);self.assertNotIn('modelDefinitions',visible);self.assertFalse(visible['canManage'])
        self.assertEqual([r['id'] for r in guest.request('GET','/api/models?summary=1')[1]],[ident])
        self.assertEqual(guest.request('GET','/api/security-context?id='+ident)[0],200)
        self.assertEqual(guest.request('GET','/api/security-context?id='+'0'*32)[0],403)
        actor=PublicLinks(self.store).resolve(guest.token)
        self.store.register_report_packages(ident,[{'id':'a'*32}])
        self.assertTrue(self.store.package_access('a'*32,actor));self.assertFalse(self.store.package_access('b'*32,actor))
        status,result=guest.request('POST','/api/dax',DaxPoolHTTPTests.payload(self,ident))
        self.assertEqual(status,200,result);self.assertEqual(result['rows'],[[123]]);self.assertEqual(result['evaluation']['executionMode'],'process pool')

    def test_expiry_rls_and_report_deletion(self):
        report=self.admin.upload(1)[1];ident=report['id'];link,guest=self.link(self.admin,ident,hours=24)
        with self.store.connect() as db:db.execute('UPDATE public_report_links SET expires_at=0 WHERE id=?',(link['id'],))
        self.assertEqual(guest.request('GET','/api/auth/me')[0],404)
        link,guest=self.link(self.admin,ident)
        policy={'id':ident,'config':{'enabled':True,'roles':[]}}
        self.assertEqual(self.admin.request('POST','/api/admin/rls',policy)[0],200)
        self.assertEqual(guest.request('GET','/api/auth/me')[0],403)
        self.assertEqual(self.admin.request('POST','/api/reports/'+ident+'/public-links',{'confirmPublic':True})[0],400)
        policy['config']['enabled']=False;self.admin.request('POST','/api/admin/rls',policy)
        self.assertEqual(guest.request('GET','/api/auth/me')[0],200)
        self.assertEqual(self.admin.request('POST','/api/delete',{'id':ident,'confirmName':report['name']})[0],200)
        self.assertEqual(guest.request('GET','/api/auth/me')[0],404)
        self.assertTrue(all(r['removed_at'] for r in self.admin.request('GET','/api/admin/public-links')[1]))

    def test_revoke_during_dax_discards_result(self):
        ident=self.admin.upload(7)[1]['id'];link,guest=self.link(self.admin,ident)
        computed,release=threading.Event(),threading.Event();original=self.httpd.dax_pool.run
        def delayed(prepare,*args):
            result=original(prepare,*args);computed.set();release.wait(5);return result
        with ThreadPoolExecutor(1) as executor,patch.object(self.httpd.dax_pool,'run',side_effect=delayed):
            future=executor.submit(guest.request,'POST','/api/dax',DaxPoolHTTPTests.payload(self,ident))
            try:
                self.assertTrue(computed.wait(5));self.admin.request('POST','/api/public-links/remove',{'id':link['id']})
            finally:release.set()
            status,result=future.result(8)
        self.assertEqual(status,404,result);self.assertNotIn('rows',result)

    def test_embedded_hidden_report_rejected(self):
        report=self.admin.upload(1)[1];ident=report['id'];path=server.DATA/ident/'manifest.json';model=json.loads(path.read_text())
        model.update(reportKind='html',pages=[{'id':'private','name':'Private','hidden':True,'visuals':[]}]);path.write_text(json.dumps(model))
        self.assertEqual(self.admin.request('POST','/api/reports/'+ident+'/public-links',{'confirmPublic':True})[0],400)


if __name__=='__main__':unittest.main()
