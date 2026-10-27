import base64
import io
import unittest
from unittest.mock import patch
from PIL import Image
import test_accounts
from branding import Branding, DEFAULTS

class BrandingTests(unittest.TestCase):
    setUp=test_accounts.AccountTests.setUp
    tearDown=test_accounts.AccountTests.tearDown
    def test_settings_and_access(self):
        with patch('server.ROOT',self.temp):
            self.assertEqual(self.admin.request('GET','/api/branding')[1],DEFAULTS)
            _,reader=test_accounts.AccountTests.create_user(self,'brand-reader')
            image=io.BytesIO();Image.new('RGBA',(512,512),(1,2,3,255)).save(image,format='PNG')
            payload={'name':'Custom BI','slogan':'Our analytics','sidebarColor':'#abcdef','icon':'data:image/png;base64,'+base64.b64encode(image.getvalue()).decode()}
            self.assertEqual(reader.request('POST','/api/admin/branding',payload)[0],403)
            self.assertEqual(self.admin.request('POST','/api/admin/branding',payload,csrf=False)[0],403)
            status,saved=self.admin.request('POST','/api/admin/branding',payload)
            self.assertEqual(status,200);self.assertEqual(saved['name'],'Custom BI')
            self.assertEqual(Image.open(io.BytesIO(base64.b64decode(saved['icon'].split(',')[1]))).size,(256,256))
            self.assertEqual(Branding(self.temp/'security').load(),saved)
            self.assertEqual(reader.request('GET','/api/branding')[1],saved)
            for bad in ({'name':''},{'sidebarColor':'red'},{'icon':'data:image/svg+xml,<svg onload=alert(1)>'}):
                self.assertEqual(self.admin.request('POST','/api/admin/branding',{**payload,**bad})[0],400)
                self.assertEqual(Branding(self.temp/'security').load(),saved)
            self.assertEqual(self.admin.request('POST','/api/admin/branding',{'reset':True})[1],DEFAULTS)

if __name__=='__main__':unittest.main()
