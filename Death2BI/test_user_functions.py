import unittest
from test_datatable import DataTableTests
from dax_engine import Parser
class UserFunctionTests(DataTableTests):
 def setUp(self):
  super().setUp();self.engine.model['functions']=[{'Name':'Scale','Expression':'(x, factor) => VAR n=x * factor RETURN n'},{'Name':'Nested','Expression':'(x) => Scale(x, 2)'},{'Name':'Recur','Expression':'(x) => Recur(x)'}]
  self.engine.model['measures'].append({'Name':'Custom','TableName':'Facts','Expression':'Nested(SUM(Facts[Value]))'})
 def call(self,s):return self.engine.run(Parser(s,self.engine.model['functions']).parse())
 def test_measure(self):self.assertEqual(self.engine.measure('Custom','Facts'),6)
 def test_lexical(self):self.assertEqual(self.call('VAR factor=99 RETURN Scale(3,4)'),12)
 def test_rows(self):self.assertEqual(self.call('SUMX(Facts,Nested(Facts[Value]))'),6)
 def test_arity(self):
  with self.assertRaisesRegex(ValueError,'argument count'):self.call('Scale(1)')
 def test_recursion(self):
  with self.assertRaisesRegex(ValueError,'depth exceeded'):self.call('Recur(1)')
if __name__=='__main__':unittest.main()
