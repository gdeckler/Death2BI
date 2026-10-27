import unittest,duckdb,datetime
from dax_engine import Evaluator,Parser
class DataTableTests(unittest.TestCase):
 def setUp(self):
  self.con=duckdb.connect();self.con.execute('CREATE TABLE Facts(Value INTEGER)');self.con.execute('INSERT INTO Facts VALUES (1),(2)');self.engine=Evaluator(self.con,{'tables':[{'name':'Facts','columns':[{'name':'Value'}]}],'relationships':[],'measures':[{'TableName':'Facts','Name':'Total','Expression':'SUM(Facts[Value])'}]},{},filters=[])
 def tearDown(self):self.con.close()
 def run_dax(self,s):return self.engine.run(Parser(s).parse())
 def test_typed_table(self):self.assertEqual(self.run_dax('SUMX(DATATABLE("Label",STRING,"N",INTEGER,{{"a",2},{"b",3}}),[N])'),5)
 def test_blank(self):self.assertEqual(self.run_dax('COUNTROWS(FILTER(DATATABLE("N",INTEGER,"B",STRING,{{1,},{2,"x"}}),ISBLANK([B])))'),1)
 def test_no_model_lineage(self):self.assertEqual(self.run_dax('SUMX(DATATABLE("N",INTEGER,{{1},{2}}),CALCULATE([Total]))'),6)
 def test_aliases(self):self.assertEqual(self.run_dax('CONCATENATEX(DATATABLE("S",TEXT,"B",LOGICAL,{{"x",TRUE()}}),[S])'),'x')
 def test_variable_rejected(self):
  with self.assertRaisesRegex(ValueError,'constant'):self.run_dax('VAR a=1 RETURN COUNTROWS(DATATABLE("N",INTEGER,{{a}}))')
 def test_negated_calculate_filter(self):self.assertEqual(self.run_dax('CALCULATE([Total],NOT(Facts[Value] IN {1}))'),2)
 def test_width_rejected(self):
  with self.assertRaisesRegex(ValueError,'width'):self.run_dax('COUNTROWS(DATATABLE("N",INTEGER,{{1,2}}))')
if __name__=='__main__':unittest.main()
