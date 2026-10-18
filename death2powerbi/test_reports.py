"""Run: py test_reports.py [path/to/LearnPowerBI.pbix]"""
import json
import sys
import unittest
import zipfile
from pathlib import Path
from server import report_pages

def encoded(value):
    return json.dumps(value).encode()

class ReportParsingTests(unittest.TestCase):
    def test_enhanced_report_json_does_not_mask_pages(self):
        files = {
            'Report/definition/report.json': encoded({'themeCollection':{}}),
            'Report/definition/pages/pages.json': encoded({'pageOrder':['b','a'], 'activePageName':'a'}),
            'Report/definition/pages/a/page.json': encoded({'name':'a','displayName':'Visible'}),
            'Report/definition/pages/b/page.json': encoded({'name':'b','displayName':'Template','visibility':'HiddenInViewMode'}),
            'Report/definition/pages/a/visuals/v/visual.json': encoded({'name':'v','position':{'x':12,'y':34,'width':300,'height':200},'visual':{'visualType':'card'}}),
        }
        pages = report_pages(files)
        self.assertEqual([p['id'] for p in pages], ['b','a'])
        self.assertTrue(pages[0]['hidden'])
        self.assertTrue(pages[1]['active'])
        self.assertEqual(pages[1]['visuals'][0]['x'], 12)
        self.assertEqual(pages[1]['visuals'][0]['type'], 'card')

    def test_legacy_utf16_report_still_parses(self):
        layout={'sections':[{'name':'legacy','displayName':'Old page','config':'{"visibility":1}','visualContainers':[]}]}
        pages=report_pages({'Report/Layout':json.dumps(layout).encode('utf-16-le')})
        self.assertEqual(len(pages),1)
        self.assertTrue(pages[0]['hidden'])

    def test_standalone_pbir_without_report_json(self):
        pages=report_pages({'Project.Report/definition/pages/a/page.json':encoded({'name':'a','displayName':'Page'})})
        self.assertEqual(pages[0]['name'],'Page')

if __name__=='__main__':
    if len(sys.argv)>1:
        with zipfile.ZipFile(Path(sys.argv.pop(1))) as z:
            files={k:z.read(k) for k in z.namelist() if k.endswith('.json') or k=='Report/Layout'}
        pages=report_pages(files)
        assert len(pages)==7, len(pages)
        if pages[0]['name']=='Template':
            assert [p['name'] for p in pages]==['Template','Introduction','Executive Summary','Division Management','Branch Management','Hours Detail','Employee Details']
            assert sum(p['hidden'] for p in pages)==1
            assert pages[0]['hidden'] and pages[1]['active']
        else:
            assert [p['name'] for p in pages]==[f'Page {i}' for i in range(1,8)]
        assert all(p['visuals'] for p in pages)
        print('PASS: 7 ordered pages,',sum(p['hidden'] for p in pages),'hidden,',sum(len(p['visuals']) for p in pages),'visuals')
    unittest.main()
