import unittest,duckdb
from dax_engine import Evaluator,Parser
class OperatorPrecedenceTests(unittest.TestCase):
 def test_mixed_concatenation_and_arithmetic(self):
  c=duckdb.connect();self.addCleanup(c.close);e=Evaluator(c,{'tables':[],'measures':[],'relationships':[]},{})
  for expr,value in [('"width=" & 383 - 12 & "px"','width=371px'),('"x" & 2 + 3 * 4','x14'),('("x" & 2) & 3','x23'),('-2^2',-4),('(-2)^2',4),('"x" & 1 + 2 = "x3"',True)]:
   with self.subTest(expr=expr):self.assertEqual(e.run(Parser(expr).parse(),{},None),value)
if __name__=='__main__':unittest.main()
