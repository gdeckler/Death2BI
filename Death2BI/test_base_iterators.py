import unittest,duckdb
from dax_engine import Evaluator
from dax_sql import evaluate_scalar,UnsupportedSql
class BaseIteratorTests(unittest.TestCase):
 def test_numeric_rows_filters_and_blank_division(self):
  c=duckdb.connect();c.execute('CREATE TABLE T AS SELECT * FROM (VALUES (1,10,2),(2,9,0),(3,NULL,2)) t(K,A,B)');m={'tables':[{'name':'T'}],'relationships':[],'measures':[{'Name':'M','TableName':'T','Expression':'AVERAGEX(T,DIVIDE(T[a]-T[b],T[b]))'}]}
  try:
   self.assertEqual(evaluate_scalar(Evaluator(c,m,filters=[]),'M'),1.5)
   f=[{'table':'T','columns':['K'],'sql':'"T"."K"=1'}];self.assertEqual(evaluate_scalar(Evaluator(c,m,filters=f),'M'),4)
   c.execute('DELETE FROM T WHERE K=1');self.assertEqual(evaluate_scalar(Evaluator(c,m,filters=[]),'M'),-1)
  finally:c.close()
if __name__=='__main__':unittest.main()

