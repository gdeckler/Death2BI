import unittest,io,zipfile,uuid,shutil
from contextlib import contextmanager
@contextmanager
def test_directory():
 root=Path.cwd().resolve();path=root/("extraction-test-"+uuid.uuid4().hex);path.mkdir()
 try:yield path
 finally:
  assert path.resolve().parent==root
  shutil.rmtree(path)
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import server
class PartialExtractionTests(unittest.TestCase):
 def test_one_unsupported_table_preserves_good_data_and_pages(self):
  class FakeModel:
   tables=['Good','Unsupported']
   dax_measures=pd.DataFrame([])
   relationships=pd.DataFrame([])
   def get_table(self,name):
    if name=='Unsupported':raise ValueError('Missing unsupported segment metadata')
    return pd.DataFrame({'N':[1,2]})
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:z.writestr('Report/definition/pages/p/page.json','{"name":"p","displayName":"Page"}')
  with test_directory() as directory,patch.object(server,'DATA',Path(directory)),patch('pbixray.PBIXRay',return_value=FakeModel()),patch.object(server,'extract_relationships',return_value=[]),patch.object(server,'extract_formats'):
   result=server.import_model('partial.pbix',raw.getvalue())
   self.assertEqual(result['tables'][0]['rows'],2);self.assertEqual(len(result['pages']),1);self.assertEqual(result['unavailableTables'][0]['name'],'Unsupported');self.assertIn('segment metadata',result['warnings'][0]);self.assertTrue((Path(directory)/result['id']/'source.pbix').exists())
if __name__=='__main__':unittest.main()

