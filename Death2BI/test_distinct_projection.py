import unittest,duckdb
from dax_engine import Evaluator,Parser
class ProjectionTests(unittest.TestCase):
 def test_distinct_large_fact_and_real_blank(self):
  c=duckdb.connect();c.execute('CREATE TABLE T AS SELECT CASE WHEN range%3=0 THEN NULL ELSE range%3 END AS K, range AS N FROM range(150000)')
  e=Evaluator(c,{'tables':[{'name':'T'}],'relationships':[],'measures':[]},filters=[{'table':'T','columns':['K'],'sql':'"T"."K"=1'}])
  try:
   self.assertEqual(e.run(Parser('COUNTROWS(VALUES(T[K]))').parse()),1)
   self.assertEqual(e.run(Parser('COUNTROWS(ALLNOBLANKROW(T[K]))').parse()),3)
   self.assertEqual(e.run(Parser('CALCULATE(COUNTROWS(VALUES(T[K])),ALLNOBLANKROW(T[K]))').parse()),3)
   self.assertEqual(e.run(Parser('COUNTROWS(T)').parse()),50000)
   self.assertEqual(Evaluator(c,e.model,filters=[]).run(Parser('COUNTROWS(T)').parse()),150000)
   c.execute('DELETE FROM T WHERE K=2')
   self.assertEqual(Evaluator(c,e.model,filters=e.filters).run(Parser('COUNTROWS(ALLNOBLANKROW(T[K]))').parse()),2)
  finally:c.close()
if __name__=='__main__':unittest.main()

