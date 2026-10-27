import unittest,duckdb
from dax_engine import Evaluator
from dax_sql import evaluate_scalar
class CalculateSqlTests(unittest.TestCase):
 def test_replace_category_and_keep_person(self):
  c=duckdb.connect();c.execute("CREATE TABLE T AS SELECT * FROM (VALUES ('A','x',2),('A','y',3),('B','x',10)) t(Person,Category,N)")
  model={'tables':[{'name':'T'}],'relationships':[],'measures':[{'Name':'Amount','TableName':'M','Expression':'SUM(T[N])'},{'Name':'Result','TableName':'M','Expression':'CALCULATE([Amount],REMOVEFILTERS(T[Category]),T[Category]="x")'}]}
  filters=[{'table':'T','columns':['Person'],'sql':'''"T"."Person"='A' '''},{'table':'T','columns':['Category'],'sql':'''"T"."Category"='y' '''}]
  try:
   self.assertEqual(evaluate_scalar(Evaluator(c,model,filters=filters),'Result'),2)
   self.assertEqual(Evaluator(c,model,filters=filters).measure('Result'),2)
   c.execute("DELETE FROM T WHERE Category='x'");self.assertIsNone(evaluate_scalar(Evaluator(c,model,filters=filters),'Result'))
  finally:c.close()
 def test_scalar_extrema(self):
  c=duckdb.connect()
  try:
   for expr,expected in [('MAX(2,3)',3),('VAR x=2 RETURN x+x',4),('VAR s="A" RETURN s & BLANK()',"A"),('MIN(2,BLANK())',0),('MAX(BLANK(),BLANK())',None)]:
    m={'tables':[],'relationships':[],'measures':[{'Name':'M','TableName':'M','Expression':expr}]};self.assertEqual(evaluate_scalar(Evaluator(c,m,filters=[]),'M'),expected)
  finally:c.close()
if __name__=='__main__':unittest.main()
