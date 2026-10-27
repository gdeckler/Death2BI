"""Presentation import and hidden-page authorization use disposable report fixtures."""
import base64
import io
import json
import unittest
import zipfile
from test_accounts import AccountTests
from presentation import enrich_report, visible_model, document

class PresentationTests(unittest.TestCase):
    setUp=AccountTests.setUp
    tearDown=AccountTests.tearDown
    create_user=AccountTests.create_user

    def test_theme_groups_images_and_hidden_page_access(self):
        owner,o=self.create_user('presentation-owner')
        reader,r=self.create_user('presentation-reader')
        root='Report/definition/'
        literal=lambda x:{'expr':{'Literal':{'Value':x}}}
        visual=lambda name,kind,x,z,parent=None:{'name':name,'position':{'x':x,'y':4,'z':z,'width':30,'height':20},'parentGroupName':parent,'visual':{'visualType':kind,'objects':{}}}
        g={'name':'group','position':{'x':100,'y':20,'z':10,'width':100,'height':100},'visualGroup':{'displayName':'Group'}}
        shape=visual('shape','shape',5,2,'group')
        image=visual('logo','image',30,3,'group');image['visual']['objects']={'general':[{'properties':{'imageUrl':{'expr':{'ResourcePackageItem':{'ItemName':'logo.png'}}}}}]}
        files={root+'report.json':{'themeCollection':{'baseTheme':{'name':'Base'},'customTheme':{'name':'Custom.json'}}},root+'pages/pages.json':{'pageOrder':['public','secret']},root+'pages/public/page.json':{'name':'public','displayName':'Public','objects':{'background':[{'properties':{'color':{'solid':{'color':literal("'#ffeeaa'")}}}}]}},root+'pages/secret/page.json':{'name':'secret','displayName':'Admin only tooltip','visibility':'HiddenInViewMode','type':'Tooltip'},root+'pages/public/visuals/group/visual.json':g,root+'pages/public/visuals/shape/visual.json':shape,root+'pages/public/visuals/logo/visual.json':image,'Report/StaticResources/SharedResources/BaseThemes/Base.json':{'dataColors':['#111111','#222222'],'foreground':'#333333'},'Report/StaticResources/RegisteredResources/Custom.json':{'dataColors':['#123456','#abcdef']},root+'bookmarks/open.bookmark.json':{'name':'open','explorationState':{'activeSection':'public','sections':{'secret':{'private':True}}}},root+'bookmarks/secret.bookmark.json':{'name':'secret','explorationState':{'activeSection':'secret'}}}
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for name,doc in files.items():z.writestr(name,json.dumps(doc))
            z.writestr('Report/StaticResources/RegisteredResources/logo.png',base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='))
            z.writestr('Report/StaticResources/RegisteredResources/hidden.png',b'private fixture image')
            z.writestr('Samples.csv','Value\n42\n')
        body=b'--pbitest\r\nContent-Disposition: form-data; name="file"; filename="Presentation.zip"\r\n\r\n'+out.getvalue()+b'\r\n--pbitest--\r\n'
        status,imported=o.request('POST','/api/import',raw=body,content_type='multipart/form-data; boundary=pbitest')
        self.assertEqual(status,200)
        self.assertEqual([p['id'] for p in imported['pages']],['public'])
        self.assertTrue(imported['hiddenPagesRestricted'])
        rid=imported['id'];full=next(m for m in self.admin.request('GET','/api/models')[1] if m['id']==rid)
        self.assertEqual(len(full['pages']),2)
        self.assertTrue(full['pages'][1]['isTooltip'])
        self.assertEqual(full['theme']['dataColors'],['#123456','#abcdef'])
        self.assertEqual(full['theme']['foreground'],'#333333')
        public=full['pages'][0];byid={v['id']:v for v in public['visuals']}
        self.assertEqual(byid['shape']['x'],105)
        self.assertEqual(byid['shape']['y'],24)
        self.assertEqual(byid['shape']['groupChain'],['group'])
        self.assertGreater(byid['logo']['layerOrder'],byid['shape']['layerOrder'])
        self.assertIn('logo.png',imported['assets'])
        self.assertNotIn('hidden.png',imported['assets'])
        self.assertEqual(len(imported['bookmarks']),1)
        self.assertEqual(imported['bookmarks'][0]['explorationState']['sections'],{})
        self.assertEqual(o.request('GET','/api/export/'+rid)[0],403)
        self.assertEqual(self.admin.request('GET','/api/export/'+rid)[0],200)
        o.request('POST','/api/reports/'+rid+'/sharing',{'userIds':[reader['id']]})
        self.assertEqual([p['id'] for p in r.request('GET','/api/models')[1][0]['pages']],['public'])
        self.assertEqual(r.request('POST','/api/query',{'id':rid,'sql':'SELECT * FROM Samples'})[1]['rows'],[[42]])
        self.assertEqual(r.request('GET','/api/export/'+rid)[0],403)

    def test_azure_layers_own_visibility_and_stale_bookmark_group(self):
        root='Report/definition/pages/main/visuals/'
        literal=lambda x:{'expr':{'Literal':{'Value':x}}}
        group={'name':'newGroup','visualGroup':{'displayName':'Map group'},'isHidden':True}
        filled={'name':'filled','parentGroupName':'newGroup','visual':{'visualType':'azureMap','objects':{'filledMap':[{'properties':{'show':literal('true')}}]}}}
        point={'name':'point','visual':{'visualType':'azureMap','objects':{'filledMap':[{'properties':{'show':literal('true')}}],'bubbleLayer':[{'properties':{'show':literal('true')}}]}}}
        bookmark={'name':'show','explorationState':{'activeSection':'main','sections':{'main':{'visualContainerGroups':{'oldGroup':{'isHidden':False}},'visualContainers':{'filled':{'singleVisual':{}}}}}}}
        files={root+'newGroup/visual.json':json.dumps(group).encode(),root+'filled/visual.json':json.dumps(filled).encode(),root+'point/visual.json':json.dumps(point).encode(),'Report/definition/bookmarks/show.bookmark.json':json.dumps(bookmark).encode()}
        model={'pages':[{'id':'main','visuals':[{'id':'newGroup','type':'group'},{'id':'filled','type':'azureMap'},{'id':'point','type':'azureMap'}]}]}
        enrich_report(model,files)
        byid={v['id']:v for v in model['pages'][0]['visuals']}
        self.assertEqual(byid['filled']['type'],'filledMap')
        self.assertEqual(byid['point']['type'],'map')
        self.assertEqual(byid['filled']['originalType'],'azureMap')
        self.assertTrue(byid['filled']['hidden'])
        self.assertFalse(byid['filled']['ownHidden'])
        section=model['bookmarks'][0]['explorationState']['sections']['main']
        self.assertEqual(section['visualContainerGroups'],{'newGroup':{'isHidden':False}})
        self.assertEqual(section['repairedGroupIds'],{'oldGroup':'newGroup'})

    def test_utf16_legacy_page_presentation(self):
        legacy={'config':json.dumps({'themeCollection':{}}),'sections':[{'name':'main','displayName':'Main','config':json.dumps({'objects':{'background':[{'properties':{'transparency':{'expr':{'Literal':{'Value':'100D'}}}}}]}}),'visualContainers':[]}]}
        encoded=json.dumps(legacy).encode('utf-16-le')
        self.assertEqual(document(encoded)['sections'][0]['name'],'main')
        model={'pages':[{'id':'main','visuals':[]}]}
        enrich_report(model,{'Report/Layout':encoded})
        self.assertIn('background',model['pages'][0]['objects'])

if __name__=='__main__':unittest.main()
