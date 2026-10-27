import unittest
from decimal import Decimal
from test_datatable import DataTableTests
from dax_engine import Parser
class MovieNumericTests(DataTableTests):
 def test_unnamed_projection(self):self.assertEqual(self.run_dax('SUMX(SELECTCOLUMNS(Facts,Facts[Value]),[Value])'),3)
 def test_mixed_projection(self):self.assertEqual(self.run_dax('SUMX(SELECTCOLUMNS(Facts,Facts[Value],"Doubled",Facts[Value]*2),[Doubled])'),6)
 def test_decimal_float(self):
  self.con.execute('CREATE TABLE Money(N DECIMAL(12,4));INSERT INTO Money VALUES (1.25)');self.engine.model['tables'].append({'name':'Money'})
  self.assertEqual(self.run_dax('SUM(Money[N])*0.5'),.625)
  self.assertEqual(self.run_dax('DIVIDE(SUM(Money[N]),0.5)'),2.5)
  self.assertEqual(self.run_dax('MOD(SUM(Money[N]),0.5)'),.25)
if __name__=='__main__':unittest.main()
