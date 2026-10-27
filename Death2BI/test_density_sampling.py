import unittest
from scatter_sampling import sample
class DensityTests(unittest.TestCase):
 def test_full_domain(self):
  rows=[[i,i%100,i] for i in range(35000)]+[[None,1,0],['text',2,0]]
  a=sample(rows,['x','y','id'],[],{'x':0,'y':1})
  self.assertEqual(a['sampling']['validRows'],35000);self.assertEqual(len(a['rows']),3500);self.assertEqual(a['rows'][0],rows[0]);self.assertEqual(a['rows'][-1],rows[34999]);self.assertEqual(a['rows'],sample(rows,['x','y','id'],[],{'x':0,'y':1})['rows']);self.assertGreater(sum(r[2]>=10000 for r in a['rows']),1000)
 def test_dense_cluster_sparse_outlier(self):
  rows=[[i%10,i%7] for i in range(20000)]+[[10000,10000]]
  r=sample(rows,['x','y'],[],{'x':0,'y':1});self.assertEqual(len(r['rows']),3500);self.assertIn([10000,10000],r['rows']);self.assertEqual(sum(x<10 for x,y in r['rows']),3499)
 def test_invalid(self):
  r=sample([[1,2],[None,3],['a',4],[3,float('inf')]],['x','y'],[],{'x':0,'y':1});self.assertEqual(r['rows'],[[1,2]])
if __name__=='__main__':unittest.main()
