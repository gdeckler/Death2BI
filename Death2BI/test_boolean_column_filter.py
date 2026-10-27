import unittest,duckdb
from dax_engine import Evaluator,Parser
from dax_sql import evaluate_scalar
class BareBooleanTests(unittest.TestCase):
 def test_boolean_filter_overwrites_and_rls(self):
  c=duckdb.connect();c.execute('CREATE TABLE T AS SELECT * FROM (VALUES (TRUE,2),(FALSE,9),(NULL,7)) t(Flag,N)');m={'tables':[{'name':'T'}],'relationships':[],'measures':[{'Name':'M','TableName':'M','Expression':'CALCULATE(SUM(T[N]),T[Flag])'}]}
  try:
   filters=[{'table':'T','columns':['Flag'],'sql':'"T"."Flag" IS FALSE'}]
   self.assertEqual(Evaluator(c,m,filters=filters).measure('M'),2);self.assertEqual(evaluate_scalar(Evaluator(c,m,filters=filters),'M'),2)
   c.execute('DELETE FROM T WHERE Flag IS TRUE');self.assertIsNone(Evaluator(c,m,filters=[]).measure('M'))
  finally:c.close()
if __name__=='__main__':unittest.main()
