import unittest,duckdb
from dax_engine import Evaluator,evaluate_sparkline
class SparklineAggregateTests(unittest.TestCase):
 def test_implicit_average_and_filter(self):
  c=duckdb.connect();c.execute("CREATE TABLE T AS SELECT * FROM (VALUES (DATE '2026-01-01',2,'A'),(DATE '2026-01-01',4,'A'),(DATE '2026-01-02',8,'A'),(DATE '2026-01-01',100,'B')) x(D,N,K)")
  m={'tables':[{'name':'T'}],'relationships':[],'measures':[]};col=lambda n:{'Column':{'Expression':{'SourceRef':{'Entity':'T'}},'Property':n}}
  d={'Groupings':[col('D')],'Measure':{'Aggregation':{'Expression':col('N'),'Function':1}}}
  try:
   e=Evaluator(c,m,filters=[{'table':'T','columns':['K'],'sql':'''"T"."K"='A' '''}]);r=evaluate_sparkline(e,d);self.assertEqual([p[1] for p in r['sparkline']],[3,8])
   c.execute("DELETE FROM T WHERE K='B'");self.assertEqual([p[1] for p in evaluate_sparkline(Evaluator(c,m,filters=[]),d)['sparkline']],[3,8])
  finally:c.close()
if __name__=='__main__':unittest.main()
