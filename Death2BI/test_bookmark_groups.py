import json
import unittest
from presentation import enrich_report, bookmark_metadata, visible_model


class BookmarkGroupTests(unittest.TestCase):
    def test_pbir_metadata_preserves_group_and_child_order(self):
        root='Report/definition/bookmarks/'
        doc=lambda name:{'name':name,'displayName':name.upper(),'explorationState':{'activeSection':'main'}}
        files={root+'bookmarks.json':json.dumps({'items':[{'name':'outside'},{'name':'group','displayName':'Page-2','children':['second',{'name':'nested','children':['first']}]}]}).encode(),
               **{root+name+'.bookmark.json':json.dumps(doc(name)).encode() for name in ('first','second','outside')}}
        model={'pages':[]}
        enrich_report(model,files)
        self.assertEqual([b['name'] for b in model['bookmarks']],['outside','second','first'])
        self.assertEqual(model['bookmarkGroups'][0],{'name':'group','displayName':'Page-2','children':['second','nested']})
        self.assertEqual(model['bookmarkGroups'][1]['children'],['first'])

    def test_legacy_nested_groups_are_not_actionable_bookmarks(self):
        a={'name':'a','explorationState':{'activeSection':'main'}}
        bookmarks,groups=bookmark_metadata({}, {'bookmarks':[{'name':'g','displayName':'Group','children':[a]},{'name':'b','explorationState':{}}]})
        self.assertEqual([b['name'] for b in bookmarks],['a','b'])
        self.assertEqual(groups,[{'name':'g','displayName':'Group','children':['a']}])
        # Authorization removes hidden-page bookmarks before the navigator resolves IDs.
        model={'pages':[{'id':'main'},{'id':'secret','hidden':True}],'bookmarks':bookmarks+[{'name':'hidden','explorationState':{'activeSection':'secret'}}],'bookmarkGroups':groups}
        visible=visible_model(model,{'isAdmin':False})
        self.assertNotIn('hidden',[b['name'] for b in visible['bookmarks']])


if __name__=='__main__':unittest.main()
