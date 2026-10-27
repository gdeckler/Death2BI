import unittest
from test_datatable import DataTableTests
class SummarizeExpressionTests(DataTableTests):
 def test_distinct_boolean_domain(self):
  self.con.execute('INSERT INTO Facts SELECT 1 FROM range(10000)');before=self.engine.budget['steps'];self.assertEqual(self.run_dax('CALCULATE(SUM(Facts[Value]),Facts[Value]=1)'),10001);self.assertLess(self.engine.budget['steps']-before,100)
 def test_all(self):self.assertEqual(self.run_dax('COUNTROWS(SUMMARIZE(ALL(Facts),Facts[Value]))'),2)
 def test_filtered(self):self.assertEqual(self.run_dax('SUMX(SUMMARIZE(FILTER(ALL(Facts),Facts[Value]>1),Facts[Value]),Facts[Value])'),2)
 def test_variable(self):self.assertEqual(self.run_dax('VAR T=FILTER(Facts,Facts[Value]>1) RETURN COUNTROWS(SUMMARIZE(T,Facts[Value]))'),1)
 def test_extension(self):self.assertEqual(self.run_dax('SUMX(SUMMARIZE(FILTER(Facts,Facts[Value]>1),Facts[Value],"Total",SUM(Facts[Value])),[Total])'),2)
 def test_lineage(self):self.assertEqual(self.run_dax('SUMX(SUMMARIZE(ALL(Facts),Facts[Value]),[Total])'),3)
if __name__=='__main__':unittest.main()
