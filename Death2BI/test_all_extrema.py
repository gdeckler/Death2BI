import unittest,duckdb
from dax_engine import Evaluator
from dax_sql import evaluate_scalar
class AllExtremaTests(unittest.TestCase):
 def test_all_table_extrema_and_security(self):
  c=duckdb.connect();c.execute('CREATE TABLE T AS SELECT * FROM (VALUES (1,2),(2,9),(3,NULL)) t(K,N)');m={'tables':[{'name':'T'}],'relationships':[],'measures':[{'Name':'M','TableName':'T','Expression':'MAXX(ALL(T),T[N])-MINX(ALL(T),T[N])'}]};filters=[{'table':'T','columns':['K'],'sql':'"T"."K"=1'}]
  try:
   self.assertEqual(Evaluator(c,m,filters=filters).measure('M'),7);self.assertEqual(evaluate_scalar(Evaluator(c,m,filters=filters),'M'),7)
   c.execute('DELETE FROM T WHERE K=2');self.assertEqual(evaluate_scalar(Evaluator(c,m,filters=filters),'M'),0)
  finally:c.close()
if __name__=='__main__':unittest.main()
