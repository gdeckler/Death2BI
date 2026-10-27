import unittest
from test_datatable import DataTableTests
class GroupByTests(DataTableTests):
 def test_groups(self):self.assertEqual(self.run_dax('SUMX(GROUPBY(DATATABLE("K",STRING,"N",INTEGER,{{"a",1},{"A",2},{"b",4}}),[K],"Total",SUMX(CURRENTGROUP(),[N])),[Total])'),7)
 def test_counts(self):self.assertEqual(self.run_dax('MAXX(GROUPBY(DATATABLE("K",STRING,{{"a"},{"A"},{"b"}}),[K],"N",COUNTX(CURRENTGROUP(),1)),[N])'),2)
 def test_unique(self):self.assertEqual(self.run_dax('COUNTROWS(GROUPBY(DATATABLE("K",STRING,{{"a"},{"A"},{"b"}}),[K]))'),2)
 def test_scope(self):
  with self.assertRaisesRegex(ValueError,'only valid'):self.run_dax('COUNTROWS(CURRENTGROUP())')
if __name__=='__main__':unittest.main()
