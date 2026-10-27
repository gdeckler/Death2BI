import unittest
from unittest.mock import patch
import duckdb
from dax_engine import Evaluator,Parser
from dax_runtime import Table
from dax_sql import UnsupportedSql,filter_rows,add_columns

class IteratorVectorTests(unittest.TestCase):
 def setUp(self):
  self.con=duckdb.connect();self.con.execute('CREATE TABLE T AS SELECT * FROM (VALUES (1,100,40),(2,200,100)) t(ID,Revenue,Budget)')
  self.con.execute('CREATE TABLE B AS SELECT * FROM (VALUES (1,0.5),(1,0.5),(2,1.0)) t(ID,Share)')
  self.model={'tables':[{'name':'T'},{'name':'B'}],'measures':[],'relationships':[{'IsActive':True,'Cardinality':'M:M','FromTableName':'T','FromColumnName':'ID','ToTableName':'B','ToColumnName':'ID','CrossFilteringBehavior':'Single'}]}
 def tearDown(self):self.con.close()
 def e(self):return Evaluator(self.con,self.model,filters=[])
 def test_weighted_lookup_preserves_duplicate_contributions(self):
  expr=Parser('SUMX(B,VAR id=B[ID] VAR amount=CALCULATE(SUMX(T,T[Revenue]-T[Budget]),ALL(T),T[ID]=id) RETURN B[Share]*amount)').parse()
  self.assertEqual(float(self.e().run(expr)),160)
  with patch('dax_vector.sum_rows',side_effect=UnsupportedSql):self.assertEqual(float(self.e().run(expr)),160)
 def test_membership_filters_before_materializing_large_bridge(self):
  self.con.execute('CREATE TABLE Large AS SELECT i ID FROM range(110000) r(i)');self.model['tables'].append({'name':'Large'})
  rows=filter_rows(self.e(),('name','Large'),Parser('Large[ID] IN selected').parse(),{'selected':Table([('T',{'ID':3}),('T',{'ID':7})],[('T','ID')])})
  self.assertEqual([r[1]['ID'] for r in rows],[3,7])
 def test_running_sum_ties_and_external_selection(self):
  self.con.execute('CREATE TABLE R AS SELECT * FROM (VALUES (1,10),(2,3),(2,4),(3,-1)) t(K,N)');self.model['tables'].append({'name':'R'})
  e=self.e();expr=Parser('VAR rank=R[K] RETURN CALCULATE(SUMX(R,R[N]),ALLSELECTED(R),R[K]<=rank)').parse()
  self.assertEqual(add_columns(e,e.table('R'),[expr]),[[10],[17],[17],[16]])
  e=e.child([e.value_filter([('R','K')],[[2],[3]])]);e.external_filters=e.filters
  self.assertEqual(add_columns(e,e.table('R'),[expr]),[[7],[7],[6]])
 def test_global_boolean_domain_does_not_erase_requested_row(self):
  self.model['measures']=[{'Name':'Total','TableName':'M','Expression':'CALCULATE(SUM(T[Revenue]),ALL(T),T[ID]=1)'}]
  e=self.e();e.filters=[e.value_filter([('T','Budget')],[[100]])];e.external_filters=[]
  self.assertEqual(e.measure('Total'),100)
  with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql):self.assertEqual(e.measure('Total'),100)

if __name__=='__main__':unittest.main()
