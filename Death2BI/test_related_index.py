import unittest
import duckdb
from dax_engine import Evaluator,Parser
class RelatedIndexTests(unittest.TestCase):
 def setUp(self):
  self.c=duckdb.connect();self.addCleanup(self.c.close)
  self.c.execute("CREATE TABLE F(K VARCHAR); INSERT INTO F VALUES ('a'),('A'),('b'),('hidden'),(NULL); CREATE TABLE Raw(K VARCHAR,N INTEGER); INSERT INTO Raw VALUES('a',10),('b',20),('hidden',99),(NULL,7); CREATE VIEW D AS SELECT * FROM Raw WHERE K IS NULL OR K<>'hidden'")
  self.m={'tables':[{'name':'F'},{'name':'D'}],'measures':[],'relationships':[{'FromTableName':'F','FromColumnName':'K','ToTableName':'D','ToColumnName':'K','IsActive':True,'Cardinality':'M:1'}]}
 def test_lookup_case_blank_security_and_reuse(self):
  e=Evaluator(self.c,self.m,{},filters=[{'table':'D','columns':['N'],'sql':'D.N=10'}])
  for key,expected in [('a',10),('A',10),('b',20),('hidden',None),(None,7)]:
   self.assertEqual(e.run(Parser('RELATED(D[N])').parse(),{},('F',{'K':key})),expected)
  self.assertEqual(len(e.budget['related_indexes']),1)
 def test_duplicate_dimension_key_still_rejected(self):
  self.c.execute("INSERT INTO Raw VALUES ('A',11)")
  e=Evaluator(self.c,self.m,{})
  with self.assertRaisesRegex(ValueError,'not unique'):e.run(Parser('RELATED(D[N])').parse(),{},('F',{'K':'a'}))
if __name__=='__main__':unittest.main()
