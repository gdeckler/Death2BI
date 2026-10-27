import unittest
import server
from test_datatable import DataTableTests
class EncodingTests(unittest.TestCase):
 def test_encodings(self):
  for s in ['createOrReplace\n\tmeasure X = "·"', '{"name":"café"}', '  [1,2]']:
   for encoding in ['utf-8','utf-8-sig','utf-16','utf-16-le','utf-16-be']:
    self.assertEqual(server.decode(s.encode(encoding)),s)
class GenerateTests(DataTableTests):
 def test_correlated(self):self.assertEqual(self.run_dax('SUMX(GENERATE(SELECTCOLUMNS({1,2},"N",[Value]),ROW("Twice",[N]*2)),[Twice])'),6)
 def test_correlated_virtual(self):self.assertEqual(self.run_dax('SUMX(GENERATE(SELECTCOLUMNS({1,2},"kid",[Value]),FILTER(SELECTCOLUMNS({1,2,3},"aid",[Value]),[aid]=[kid])),[aid])'),3)
 def test_empty_inner(self):self.assertEqual(self.run_dax('COUNTROWS(GENERATE(SELECTCOLUMNS({1,2},"N",[Value]),FILTER({9},FALSE())))'),None)
 def test_generateall(self):self.assertEqual(self.run_dax('COUNTROWS(GENERATEALL(SELECTCOLUMNS({1,2},"N",[Value]),FILTER({9},FALSE())))'),2)
 def test_duplicates(self):
  with self.assertRaisesRegex(ValueError,'duplicate'):self.run_dax('COUNTROWS(GENERATE({1},{2}))')
 def test_lineage(self):self.assertEqual(self.run_dax('SUMX(GENERATE(Facts,ROW("N",Facts[Value]*2)),Facts[Value]+[N])'),9)
if __name__=='__main__':unittest.main()

