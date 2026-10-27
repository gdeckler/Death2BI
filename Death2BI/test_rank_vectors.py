import unittest,duckdb
from dax_engine import Evaluator,Parser
class RankVectorTests(unittest.TestCase):
 def test_dense_and_skip_reuse(self):
  c=duckdb.connect();c.execute('CREATE TABLE T AS SELECT i::INTEGER K,(i%3)::INTEGER N FROM range(300) r(i)');m={'tables':[{'name':'T'}],'relationships':[],'measures':[]}
  try:
   e=Evaluator(c,m,filters=[]);v=e.run(Parser('SUMX(ADDCOLUMNS(T,"R",RANKX(T,T[N],,ASC,DENSE)),[R])').parse());self.assertEqual(v,600);self.assertEqual(len(e.budget['rank_vectors']),1);self.assertLess(e.budget['steps'],20000)
   e=Evaluator(c,m,filters=[]);v=e.run(Parser('SUMX(ADDCOLUMNS(T,"R",RANKX(T,T[N],,DESC,SKIP)),[R])').parse());self.assertEqual(v,30300)
  finally:c.close()
 def test_unordered_topn(self):
  c=duckdb.connect()
  try:self.assertEqual(Evaluator(c,{'tables':[],'measures':[],'relationships':[]},filters=[]).run(Parser('COUNTROWS(TOPN(2,{1,2,3,4}))').parse()),2)
  finally:c.close()
if __name__=='__main__':unittest.main()
