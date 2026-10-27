import unittest
from test_accounts import AccountTests
class VisualQueryLimitTests(AccountTests):
 def test_visual_and_explorer_limits(self):
  status,report=self.admin.upload(1)
  self.assertEqual(status,200)
  for purpose,count,expected,truncated in [(None,10005,1000,True),('visual',10005,10000,True),('visual',4800,4800,False),('visual',10000,10000,False)]:
   payload={'id':report['id'],'sql':f'SELECT range AS value FROM range({count})'}
   if purpose:payload['purpose']=purpose
   status,result=self.admin.request('POST','/api/query',payload)
   self.assertEqual(status,200,result)
   self.assertEqual(len(result['rows']),expected)
   self.assertEqual(result['truncated'],truncated)

 def test_full_scatter_density_query(self):
  status,report=self.admin.upload(1)
  self.assertEqual(status,200)
  status,result=self.admin.request('POST','/api/query',{'id':report['id'],'sql':'SELECT range AS x, range % 100 AS y FROM range(20005)','purpose':'scatter','scatter':{'x':0,'y':1}})
  self.assertEqual(status,200,result);self.assertEqual(result['sampling']['inputRows'],20005);self.assertEqual(len(result['rows']),3500);self.assertFalse(result['truncated']);self.assertEqual(result['rows'][0],[0,0]);self.assertEqual(result['rows'][-1],[20004,4])
