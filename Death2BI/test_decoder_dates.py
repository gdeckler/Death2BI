import unittest,pandas as pd
from types import SimpleNamespace
from semantic_model import configure_date_decoder
class DateDecoderTests(unittest.TestCase):
 def test_missing_fraction_and_bounds(self):
  def failing(*args):raise FloatingPointError('overflow encountered in multiply')
  m=SimpleNamespace(_vertipaq_decoder=SimpleNamespace(_handle_special_cases=failing));configure_date_decoder(m);f=m._vertipaq_decoder._handle_special_cases
  dates=f(pd.Series([float('nan'),0,2.5,73050,-36522,2419768]),'Date')
  self.assertTrue(pd.isna(dates[0]));self.assertEqual(str(dates[1]),'1899-12-30 00:00:00');self.assertEqual(str(dates[2]),'1900-01-01 12:00:00');self.assertEqual(dates[5].year,8525)
  with self.assertRaises(ValueError):f(pd.Series([2958466]),'Date')
  with self.assertRaises(FloatingPointError):f(pd.Series([1]),'Currency')
if __name__=='__main__':unittest.main()
