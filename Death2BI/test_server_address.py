import http.client
import json
import os
from pathlib import Path
import shutil
import unittest
import uuid
from unittest.mock import patch
import server
from server_address import ServerAddress,domain,origin
import test_accounts


class AddressUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp=Path('work').resolve()/('address-test-'+uuid.uuid4().hex);self.temp.mkdir(parents=True)
    def tearDown(self):shutil.rmtree(self.temp)

    def test_domain_and_port_validation(self):
        self.assertEqual(domain('REPORTS.Example.com.'),'reports.example.com')
        self.assertEqual(domain('[::1]'),'::1');self.assertEqual(domain('bücher.example'),'xn--bcher-kva.example')
        for value in ('https://reports.example.com','example.com:8765','name/path','user@host','bad host','','host\n','[bad]','-bad.example'):
            with self.assertRaises(ValueError,msg=value):domain(value)
        settings=ServerAddress(self.temp,inherited_origin=None)
        payload={'domain':'reports.example.com','port':8765,'bindAddress':'127.0.0.1','scheme':'https','publicPort':443}
        self.assertEqual(settings.save(payload)['pendingOrigin'],'https://reports.example.com')
        previous=settings.config()
        for change in ({'port':0},{'port':True},{'port':65536},{'publicPort':0},{'scheme':'file'},{'bindAddress':'example.com'}):
            with self.assertRaises(ValueError):settings.save({**payload,**change})
            self.assertEqual(settings.config(),previous)
        self.assertEqual(origin('::1',9443,'https'),'https://[::1]:9443')

    def test_legacy_proxy_and_persistent_listener_are_separate(self):
        with patch.dict(os.environ,{'D2BI_BIND_HOST':'0.0.0.0','D2BI_PORT':'8765'}):
            settings=ServerAddress(self.temp,inherited_origin='http://127.0.0.1:8766')
            self.assertEqual(settings.config()['port'],8765);self.assertEqual(settings.config()['publicPort'],8766)
            self.assertEqual(settings.pending_origin(),'http://127.0.0.1:8766')
            settings.save({**settings.config(),'domain':'reports.example.com','scheme':'https','publicPort':443})
        reloaded=ServerAddress(self.temp,inherited_origin=None)
        self.assertEqual(reloaded.pending_origin(),'https://reports.example.com');self.assertEqual(reloaded.config()['port'],8765)


class AddressHTTPTests(unittest.TestCase):
    def setUp(self):
        test_accounts.AccountTests.setUp(self)
        self.security=patch('server.security_dir',return_value=self.temp/'security');self.security.start()
    def tearDown(self):self.security.stop();test_accounts.AccountTests.tearDown(self)

    def test_immediate_link_domain_admin_csrf_and_host_guards(self):
        user,reader=test_accounts.AccountTests.create_user(self,'reader')
        payload={'domain':'reports.example.com','scheme':'https','publicPort':443,'port':8765,'bindAddress':'127.0.0.1'}
        self.assertEqual(reader.request('GET','/api/admin/server-address')[0],403)
        self.assertEqual(reader.request('POST','/api/admin/server-address',payload)[0],403)
        self.assertEqual(self.admin.request('POST','/api/admin/server-address',payload,csrf=False)[0],403)
        active=server.base_url();self.assertEqual(self.admin.request('POST','/api/admin/server-address',payload)[0],200)
        self.assertEqual(server.base_url(),active)
        report=self.admin.upload(3)[1]['id']
        for suffix,body,fragment in [('invitations',{'hours':24},'invite'),('public-links',{'confirmPublic':True},'public')]:
            status,result=self.admin.request('POST','/api/reports/'+report+'/'+suffix,body)
            self.assertEqual(status,201,result);self.assertTrue(result['url'].startswith('https://reports.example.com/#'+fragment+'='))
        info=self.admin.request('GET','/api/admin/server-address')[1];self.assertEqual(info['activePort'],self.httpd.server_port)
        self.assertEqual(info['pendingOrigin'],'https://reports.example.com')
        def request(host,origin):
            con=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port)
            con.request('POST','/api/auth/login',json.dumps({'username':'x','password':'y'}),{'Host':host,'Origin':origin,'Content-Type':'application/json'})
            response=con.getresponse();response.read();con.close();return response.status
        self.assertEqual(request('attacker.invalid','http://attacker.invalid'),403)
        self.assertEqual(request('reports.example.com','http://attacker.invalid'),403)
        self.assertEqual(request('reports.example.com','https://reports.example.com'),401)


if __name__=='__main__':unittest.main()
