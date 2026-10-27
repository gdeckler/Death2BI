import json,unittest
from presentation import enrich_report
class ModernSlicer(unittest.TestCase):
 def test_list_slicer_is_normalized(self):
  source={'name':'list','visual':{'visualType':'listSlicer','objects':{'data':[{'properties':{'dropdownMode':{'expr':{'Literal':{'Value':'true'}}}}}]},'query':{'queryState':{'Values':{'projections':[]}}}}}
  model={'pages':[{'id':'p','visuals':[{'id':'list','type':'listSlicer','definition':source['visual']}]}]}
  enrich_report(model,{'Report/definition/pages/p/visuals/list/visual.json':json.dumps(source).encode()})
  visual=model['pages'][0]['visuals'][0];self.assertEqual(visual['type'],'slicer');self.assertEqual(visual['originalType'],'listSlicer');self.assertEqual(visual['definition']['objects']['data'][0]['properties']['dropdownMode']['expr']['Literal']['Value'],'true')
if __name__=='__main__':unittest.main()
