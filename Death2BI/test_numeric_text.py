import unittest
from dax_functions import number,format_value
class NumericTextTests(unittest.TestCase):
 def test_groups(self):
  for raw,expected in [('1,000',1000),('-1,234.50',-1234.5),('12,345,678',12345678)]:self.assertEqual(number(raw),expected)
 def test_dax_grouping_mask(self):
  self.assertEqual(format_value(105,'#,0'),'105');self.assertEqual(format_value(12345,'#,0'),'12,345');self.assertEqual(format_value(12345.25,'#,0.00'),'12,345.25')
 def test_invalid(self):
  for raw in ['1,2','1,000,00','1,000x','1.000,50']:
   with self.assertRaises(ValueError):number(raw)
if __name__=='__main__':unittest.main()
