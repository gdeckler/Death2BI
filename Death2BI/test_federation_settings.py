import json
from pathlib import Path
import shutil
import unittest
import uuid
from federation_settings import FederationSettings
from oidc_auth import OIDC
import test_tls
import test_accounts


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.folder=Path('work').resolve()/('federation-test-'+uuid.uuid4().hex);self.folder.mkdir(parents=True)
        self.settings=FederationSettings(self.folder/'security')

    def tearDown(self):shutil.rmtree(self.folder)

    def test_preserve_disable_rotate_and_redact(self):
        data={'provider':'google','enabled':True,'clientId':'test.apps.googleusercontent.com','clientSecret':'private-test-secret'}
        result=self.settings.save(data,'http://localhost:8765')
        self.assertNotIn('private-test-secret',json.dumps(result));self.assertTrue(result['providers']['google']['hasSecret'])
        self.settings.save({**data,'clientSecret':'','enabled':False},'http://localhost:8765')
        self.assertFalse(OIDC(None,self.folder).configs())
        self.settings.save({**data,'clientSecret':''},'http://localhost:8765')
        self.assertEqual(OIDC(None,self.folder).configs()['google']['client_secret'],'private-test-secret')
        before=self.settings.path.read_bytes()
        with self.assertRaises(ValueError):self.settings.save({**data,'clientId':'new.apps.googleusercontent.com','clientSecret':''},'http://localhost:8765')
        self.assertEqual(before,self.settings.path.read_bytes())
        entra={'provider':'entra','enabled':True,'clientId':str(uuid.uuid4()),'tenantId':str(uuid.uuid4()),'clientSecret':'entra-test-secret'}
        result=self.settings.save(entra,'https://localhost:8765')
        self.assertEqual(result['providers']['entra']['callbackUrl'],'https://localhost:8765/auth/callback/entra')
        self.assertEqual(OIDC(None,self.folder).configs()['google']['client_secret'],'private-test-secret')
        with self.assertRaises(ValueError):self.settings.save({**entra,'tenantId':'common'},'https://localhost:8765')
        # Existing configuration files without an enabled flag remain compatible.
        existing=json.loads(self.settings.path.read_text());existing['google'].pop('enabled');self.settings.path.write_text(json.dumps(existing))
        self.assertIn('google',OIDC(None,self.folder).configs())


class ConfigurationHTTPTests(unittest.TestCase):
    setUp=test_tls.TLSHTTPTests.setUp
    tearDown=test_tls.TLSHTTPTests.tearDown

    def test_admin_csrf_and_redacted_responses(self):
        _,reader=test_accounts.AccountTests.create_user(self,'federation-reader')
        data={'provider':'google','enabled':True,'clientId':'test.apps.googleusercontent.com','clientSecret':'http-test-secret'}
        self.assertEqual(reader.request('GET','/api/admin/federation')[0],403)
        self.assertEqual(reader.request('POST','/api/admin/federation',data)[0],403)
        self.assertEqual(self.admin.request('POST','/api/admin/federation',data,csrf=False)[0],403)
        status,result=self.admin.request('POST','/api/admin/federation',data);self.assertEqual(status,200);self.assertNotIn('http-test-secret',json.dumps(result))
        status,result=self.admin.request('GET','/api/admin/federation');self.assertEqual(status,200);self.assertNotIn('http-test-secret',json.dumps(result))
        status,result=self.admin.request('GET','/api/auth/providers');self.assertEqual(status,200);self.assertIn('google',result['providers'])


if __name__=='__main__':unittest.main()
