import unittest,duckdb
from dax_engine import Evaluator,Parser
class FilterRelationTests(unittest.TestCase):
 def setUp(self):
  self.con=duckdb.connect();self.con.execute('CREATE TABLE Facts AS SELECT i::BIGINT A,(i%3)::BIGINT B FROM range(10000) x(i)');self.e=Evaluator(self.con,{'tables':[{'name':'Facts'}],'measures':[],'relationships':[]},filters=[])
 def tearDown(self):self.con.close()
 def test_large_correlated(self):
  rows=[(i,i%3) for i in range(6000)];f=self.e.value_filter([('Facts','A'),('Facts','B')],rows);self.assertIn('EXISTS',f['sql']);self.assertEqual(self.con.execute('SELECT COUNT(*) FROM Facts WHERE '+f['sql']).fetchone()[0],6000);self.assertEqual(self.e.value_filter([('Facts','A'),('Facts','B')],rows)['sql'],f['sql']);self.assertEqual(len(self.e.budget['filter_relations']),1)
 def test_nulls_and_secured_rows(self):
  self.con.execute('DELETE FROM Facts WHERE A>=5000');self.con.execute('INSERT INTO Facts VALUES(NULL,1)');f=self.e.value_filter([('Facts','A'),('Facts','B')],[(i,i%3) for i in range(6000)]+[(None,1)]);self.assertEqual(self.con.execute('SELECT COUNT(*) FROM Facts WHERE '+f['sql']).fetchone()[0],5001)
 def test_bound(self):
  with self.assertRaisesRegex(RuntimeError,'100,000'):self.e.value_filter([('Facts','A')],[(1,)]*100001)
 def test_width(self):
  with self.assertRaisesRegex(ValueError,'width'):self.e.value_filter([('Facts','A')],[(1,2)])
if __name__=='__main__':unittest.main()
