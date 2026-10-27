import unittest,duckdb
from dax_engine import Evaluator,Parser
class IteratorScoresTests(unittest.TestCase):
 def setUp(self):
  self.con=duckdb.connect();self.con.execute("CREATE TABLE T(K VARCHAR,N INTEGER); INSERT INTO T VALUES ('a',2),('A',2),('b',3),('c',NULL)")
  self.model={'tables':[{'name':'T','columns':[{'name':'K'},{'name':'N'}]}],'relationships':[],'measures':[{'Name':'Score','TableName':'T','Expression':'SUM(T[N])'}]}
 def tearDown(self):self.con.close()
 def run_dax(self,s,filters=None):return Evaluator(self.con,self.model,filters=[] if filters is None else filters).run(Parser(s).parse())
 def test_duplicate_context(self):self.assertEqual(self.run_dax('CONCATENATEX(TOPN(1,T,[Score],DESC),T[K],",")'),'a,A')
 def test_filtered(self):self.assertEqual(self.run_dax('CONCATENATEX(TOPN(1,T,[Score],DESC),T[K],",")',[{'table':'T','columns':['N'],'sql':'"T"."N">2'}]),'b')
 def test_virtual_fallback(self):self.assertEqual(self.run_dax('CONCATENATEX(TOPN(1,SELECTCOLUMNS(T,"N",T[N]),[Score],DESC),[N],",")'),'2,2')
if __name__=='__main__':unittest.main()
