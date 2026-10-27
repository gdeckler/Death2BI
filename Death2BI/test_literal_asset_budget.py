import unittest
from dax_core import Parser
class LiteralAssetBudget(unittest.TestCase):
 def test_large_literal(self):
  value='a'*250000;ast=Parser('"'+value+'" & "x"').parse();self.assertEqual(ast[2][1],value)
 def test_raw_source_cap(self):
  with self.assertRaisesRegex(ValueError,'2 MB'):Parser('"'+'a'*2000000+'"')
 def test_code_cap(self):
  with self.assertRaisesRegex(ValueError,'executable'):Parser('a'*100001)
 def test_token_cap(self):
  with self.assertRaisesRegex(ValueError,'token limit'):Parser('1+'*16384+'1')
 def test_trailing_quote(self):
  with self.assertRaisesRegex(ValueError,'Unmatched trailing quote'):Parser('"ok""')
if __name__=='__main__':unittest.main()
