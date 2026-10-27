import unittest
from dax_functions import format_value
class FormatScalingTests(unittest.TestCase):
 def test_units_and_literal_masks(self):
  for value,mask,expected in [(1234567890123,'$0,,,,T','$1T'),(1234567890123,'$0,,,,.00T','$1.23T'),(1234567,'0.0,,"M"','1.2M'),(1234567,'#,##0.00','1,234,567.00'),(.25,'0"%"','0%'),(.25,'0%','25%')]:
   with self.subTest(mask=mask):self.assertEqual(format_value(value,mask),expected)
  self.assertEqual(format_value(1234567,'0,,.00"M"','es-PY'),'1,23M')
if __name__=='__main__':unittest.main()
