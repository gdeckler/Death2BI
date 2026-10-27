import unittest,duckdb
from dax_engine import evaluate_topn
class BatchedTopNTests(unittest.TestCase):
 def test_large_domain_and_ties(self):
  c=duckdb.connect();c.execute('CREATE TABLE T AS SELECT i::INTEGER K,(i//2)::INTEGER N FROM range(1600) r(i)')
  m={'tables':[{'name':'T'}],'relationships':[],'measures':[{'Name':'Score','TableName':'M','Expression':'SUM(T[N])'}]}
  payload={'category':{'Column':{'Expression':{'SourceRef':{'Entity':'T'}},'Property':'K'}},'by':{'Measure':{'Expression':{'SourceRef':{'Entity':'M'}},'Property':'Score'}},'count':1,'filters':[]}
  try:
   r=evaluate_topn(c,m,payload);self.assertEqual(set(r['values']),{1598,1599})
   c.execute('DELETE FROM T WHERE K>=1000');self.assertEqual(set(evaluate_topn(c,m,payload)['values']),{998,999})
  finally:c.close()
if __name__=='__main__':unittest.main()
