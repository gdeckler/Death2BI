import unittest
from test_datatable import DataTableTests
class ContainsTests(DataTableTests):
 def test_present(self):self.assertTrue(self.run_dax('CONTAINS(Facts,Facts[Value],2)'))
 def test_absent(self):self.assertFalse(self.run_dax('CONTAINS(Facts,Facts[Value],4)'))
 def test_same_row(self):self.assertFalse(self.run_dax('CONTAINS(DATATABLE("A",INTEGER,"B",INTEGER,{{1,2},{2,1}}),[A],1,[B],1)'))
 def test_blank_is_strict(self):self.assertFalse(self.run_dax('CONTAINS(DATATABLE("A",INTEGER,{{0}}),[A],BLANK())'))
 def test_case_insensitive(self):self.assertTrue(self.run_dax('CONTAINS(DATATABLE("A",STRING,{{"hello"}}),[A],"HELLO")'))
if __name__=='__main__':unittest.main()
