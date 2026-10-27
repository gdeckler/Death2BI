import unittest
import test_accounts
from unittest.mock import patch


class ServerActionTests(unittest.TestCase):
    setUp=test_accounts.AccountTests.setUp
    tearDown=test_accounts.AccountTests.tearDown

    def test_restart_authorization_confirmation_and_shutdown(self):
        _,reader=test_accounts.AccountTests.create_user(self,'server-reader')
        for route in ('/api/restart','/api/shutdown'):
            self.assertEqual(reader.request('POST',route,{'confirm':True})[0],403)
            self.assertEqual(self.admin.request('POST',route,{'confirm':True},csrf=False)[0],403)
            self.assertEqual(self.admin.request('POST',route,{'confirm':False})[0],400)
        with patch('server.TLSSettings.context',side_effect=ValueError('Invalid saved TLS certificate.')):
            self.assertEqual(self.admin.request('POST','/api/restart',{'confirm':True})[0],400)
        self.assertFalse(getattr(self.httpd,'stopping',False))
        status,result=self.admin.request('POST','/api/restart',{'confirm':True})
        self.assertEqual(status,200);self.assertTrue(result['restarting']);self.assertTrue(self.httpd.restart_requested)

    def test_confirmed_shutdown_does_not_restart(self):
        status,result=self.admin.request('POST','/api/shutdown',{'confirm':True})
        self.assertEqual(status,200);self.assertTrue(result['shuttingDown']);self.assertFalse(result['restarting']);self.assertFalse(self.httpd.restart_requested)


if __name__=='__main__':unittest.main()
