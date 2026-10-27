from test_accounts import AccountTests,Client
from accounts import Accounts,DEFAULT_PASSWORD
import json
import server

class ReadingPositionTests(AccountTests):
 def test_position_survives_new_browser_and_store_reload(self):
  self.assertEqual(self.admin.request('GET','/api/reading-position'),(200,{}))
  status,workspaces=self.admin.request('GET','/api/workspaces');self.assertEqual(status,200)
  position={'reportId':'demo','pageId':'regions','workspaceId':workspaces[0]['id']}
  self.assertEqual(self.admin.request('POST','/api/reading-position',position),(200,position))
  browser=Client(self.httpd);browser.login('admin',DEFAULT_PASSWORD)
  self.assertEqual(browser.request('GET','/api/reading-position'),(200,position))
  store=Accounts(self.store.path);self.assertEqual(store.reading_position(self.admin_user),position)
 def test_position_requires_authentication_csrf_and_valid_page(self):
  self.assertEqual(Client(self.httpd).request('GET','/api/reading-position')[0],401)
  workspace=self.admin.request('GET','/api/workspaces')[1][0]['id']
  position={'reportId':'demo','pageId':'regions','workspaceId':workspace}
  self.assertEqual(self.admin.request('POST','/api/reading-position',position,csrf=False)[0],403)
  self.assertEqual(self.admin.request('POST','/api/reading-position',{**position,'pageId':'missing'})[0],400)
  self.assertEqual(self.admin.request('POST','/api/reading-position',[])[0],400)
 def test_accounts_have_independent_positions(self):
  user,alice=self.create_user('alice')
  own=alice.request('GET','/api/workspaces')[1][0]['id'];other=self.admin.request('GET','/api/workspaces')[1][0]['id']
  p={'reportId':'demo','pageId':'overview','workspaceId':own}
  self.assertEqual(alice.request('POST','/api/reading-position',p)[0],200)
  self.assertEqual(self.admin.request('GET','/api/reading-position')[1],{})
  self.assertEqual(alice.request('POST','/api/reading-position',{**p,'workspaceId':other})[0],404)
  self.assertEqual(alice.request('POST','/api/reading-position',{**p,'reportId':'a'*32})[0],404)
 def test_report_page_permissions_are_checked_when_saving(self):
  user,client=self.create_user('alice');status,report=client.upload(123);self.assertEqual(status,200)
  path=server.DATA/report['id']/'manifest.json';model=json.loads(path.read_text(encoding='utf-8'))
  model['pages']=[{'id':'public','name':'Public','width':800,'height':600,'visuals':[]},{'id':'private','name':'Private','hidden':True,'width':800,'height':600,'visuals':[]}]
  path.write_text(json.dumps(model),encoding='utf-8')
  workspace=client.request('GET','/api/workspaces')[1][0]['id'];position={'reportId':report['id'],'pageId':'public','workspaceId':workspace}
  self.assertEqual(client.request('POST','/api/reading-position',position)[0],200)
  self.assertEqual(client.request('POST','/api/reading-position',{**position,'pageId':'private'})[0],400)
  self.assertEqual(client.request('POST','/api/reading-position',{**position,'pageId':'missing'})[0],400)
  self.assertEqual(client.request('GET','/api/reading-position')[1],position)
