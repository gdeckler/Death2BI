import unittest,duckdb
from dax_engine import Evaluator,Parser
class ReportBehaviorTests(unittest.TestCase):
 def setUp(self):
  self.con=duckdb.connect();self.con.execute('create table T(A int,B int,N int)');self.con.execute('insert into T values (1,10,100),(2,10,200),(1,20,300),(2,20,400)');self.con.execute('create table D as select 10 B union all select 20 B')
  self.model={'tables':[{'name':'T'},{'name':'D'}],'relationships':[],'measures':[],'reportSettings':{'locale':'de-DE'}}
 def tearDown(self):self.con.close()
 def test_project_compound_selection_when_one_field_is_replaced(self):
  e=Evaluator(self.con,self.model,filters=[])
  a=lambda n:e.value_filter([('T','A')],[[n]])
  b=lambda n:e.value_filter([('D','B')],[[n]])
  e.filters=[{'alternatives':[[a(1),b(10)],[a(2),b(20)]]}]
  projected=e.remove([('T','A')]);self.assertEqual(len(projected[0]['alternatives']),2)
  self.assertTrue(all(part['table']=='D' for group in projected[0]['alternatives'] for part in group))
  self.assertEqual(e.remove([],['T','D']),[])
 def test_locale_default_and_explicit_override(self):
  e=Evaluator(self.con,self.model,filters=[])
  self.assertEqual(e.run(Parser('FORMAT(1234.5,"#,0.00")').parse()),'1.234,50')
  self.assertEqual(e.run(Parser('FORMAT(1234.5,"#,0.00","en-US")').parse()),'1,234.50')
if __name__=='__main__':unittest.main()
