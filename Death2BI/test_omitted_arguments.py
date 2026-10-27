import unittest
import duckdb
from dax_engine import Evaluator,Parser
class OmittedArguments(unittest.TestCase):
 def setUp(self):self.con=duckdb.connect();self.engine=Evaluator(self.con,{'tables':[],'measures':[],'relationships':[]},{},filters=[])
 def tearDown(self):self.con.close()
 def evaluate(self,s):return self.engine.run(Parser(s).parse())
 def test_search_default_start(self):self.assertEqual(self.evaluate('SEARCH("b","abc",,0)'),2)
 def test_find_default_start(self):self.assertEqual(self.evaluate('FIND("b","abc",,0)'),2)
 def test_not_found_fallback(self):self.assertEqual(self.evaluate('SEARCH("z","abc",,0)'),0)
 def test_explicit_blank_is_not_omitted(self):
  with self.assertRaisesRegex(ValueError,'start position'):self.evaluate('SEARCH("a","abc",BLANK(),0)')
 def test_optional_substitute_argument(self):self.assertEqual(self.evaluate('SUBSTITUTE("aba","a","x",)'), 'xbx')
if __name__=='__main__':unittest.main()
