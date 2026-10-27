import base64
from datetime import datetime, timedelta, timezone
import http.client
import json
from pathlib import Path
import shutil
import ssl
import threading
import unittest
import uuid
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from tls_settings import TLSSettings


def fixture(expired=False):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.now(timezone.utc)
    cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=2)).not_valid_after(now+timedelta(days=-1 if expired else 5)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False).sign(key,hashes.SHA256())
    return key, cert


def payload(key, cert):
    return {'certificate':base64.b64encode(cert.public_bytes(serialization.Encoding.PEM)).decode(), 'privateKey':base64.b64encode(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())).decode()}


class TLSUnitTests(unittest.TestCase):
    def setUp(self):
        self.folder=Path('work').resolve()/('tls-test-'+uuid.uuid4().hex)
        self.folder.mkdir(parents=True)
        self.store=TLSSettings(self.folder)

    def tearDown(self):
        shutil.rmtree(self.folder)

    def test_validation_rotation_pfx_and_atomic_failure(self):
        key,cert=fixture();self.assertFalse(self.store.status()['enabled'])
        self.store.save(payload(key,cert));previous=self.store.config()
        wrong,_=fixture()
        with self.assertRaisesRegex(ValueError,'do not match'):self.store.save(payload(wrong,cert))
        self.assertEqual(previous,self.store.config())
        expired_key,expired_cert=fixture(True)
        with self.assertRaisesRegex(ValueError,'expired'):self.store.save(payload(expired_key,expired_cert))
        bundle=pkcs12.serialize_key_and_certificates(b'test',key,cert,None,serialization.BestAvailableEncryption(b'password'))
        self.store.save({'format':'pkcs12','certificate':base64.b64encode(bundle).decode(),'password':'password'})
        self.assertNotIn('bundle',self.store.status());self.assertIsInstance(self.store.context(),ssl.SSLContext)
        self.store.disable();self.assertIsNone(self.store.context())

    def test_real_tls_handshake(self):
        import server
        key,cert=fixture();self.store.save(payload(key,cert))
        httpd=server.LocalServer(('127.0.0.1',0),server.Handler)
        httpd.socket=self.store.context().wrap_socket(httpd.socket,server_side=True)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        try:
            context=ssl.create_default_context(cadata=cert.public_bytes(serialization.Encoding.PEM).decode())
            client=http.client.HTTPSConnection('localhost',httpd.server_port,context=context)
            client.request('GET','/api/health',headers={'Host':'localhost:8765'})
            response=client.getresponse();self.assertEqual(response.status,200);self.assertTrue(json.loads(response.read())['ok']);client.close()
        finally:httpd.shutdown();httpd.server_close();thread.join()


class TLSHTTPTests(unittest.TestCase):
    def setUp(self):
        import test_accounts,server
        test_accounts.AccountTests.setUp(self)
        self.old_root=server.ROOT;server.ROOT=self.temp

    def tearDown(self):
        import test_accounts,server
        server.ROOT=self.old_root;test_accounts.AccountTests.tearDown(self)

    def test_admin_csrf_and_private_status(self):
        import test_accounts
        status,info=self.admin.request('GET','/api/admin/tls');self.assertEqual(status,200)
        key,cert=fixture();data=payload(key,cert)
        self.assertEqual(self.admin.request('POST','/api/admin/tls',data,csrf=False)[0],403)
        user,client=test_accounts.AccountTests.create_user(self,'tls-reader')
        self.assertEqual(client.request('GET','/api/admin/tls')[0],403)
        self.assertEqual(client.request('POST','/api/admin/tls',data)[0],403)
        status,info=self.admin.request('POST','/api/admin/tls',data)
        self.assertEqual(status,200);self.assertTrue(info['restartRequired']);self.assertNotIn('privateKey',info);self.assertNotIn('bundle',info)


if __name__=='__main__':unittest.main()
