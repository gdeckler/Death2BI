import unittest,datetime as dt
from concurrent.futures import ThreadPoolExecutor
from dax_functions import format_value
from dax_engine import Evaluator,Parser
import duckdb

class LocaleFormatTests(unittest.TestCase):
 def test_localized_separators_and_rounding(self):
  for locale,expected in [('es-PY','1.234.568'),('es-py','1.234.568'),('es_PY','1.234.568'),('en-US','1,234,568'),('de-DE','1.234.568')]:
   self.assertEqual(format_value(1234567.89,'#,##0',locale),expected)
  self.assertEqual(format_value(1234.5,'#,##0.00','es-PY'),'1.234,50')
  self.assertEqual(format_value(-1234.5,'#,##0.00;(#,##0.00)','de-DE'),'(1.234,50)')
  self.assertEqual(format_value(.125,'0.00%','es-PY'),'12,50%')
  self.assertEqual(format_value(1234.5,'#,##0.00','fr-FR'),'1\u202f234,50')
  self.assertEqual(format_value(1.2,'0.00##','es-PY'),'1,20')
 def test_localized_dates_and_existing_masks(self):
  d=dt.date(2026,10,24)
  self.assertEqual(format_value(d,'mmmm yyyy','es-PY'),'octubre 2026')
  self.assertEqual(format_value(d,'d mmm yyyy','en-US'),'24 Oct 2026')
  self.assertEqual(format_value(d,'yyyy-mm-dd','es-PY'),'2026-10-24')
  self.assertEqual(format_value(dt.datetime(2026,10,24,17,42,3),'hh:nn:ss','es-PY'),'17:42:03')
  self.assertEqual(format_value(None,'#,##0','es-PY'),'')
  with self.assertRaisesRegex(ValueError,'does not recognize locale'):format_value(1,'0','not-a-locale')
 def test_dax_dispatch_and_request_locale_isolation(self):
  c=duckdb.connect();self.addCleanup(c.close)
  self.assertEqual(Evaluator(c,{'tables':[],'measures':[],'relationships':[]},filters=[]).run(Parser('FORMAT(12345.67,"#,##0.00","es-PY")').parse(),{},None),'12.345,67')
  locales=['es-PY','en-US']*20
  with ThreadPoolExecutor(max_workers=4) as pool:values=list(pool.map(lambda locale:format_value(1234.5,'#,##0.00',locale),locales))
  self.assertEqual(values,['1.234,50','1,234.50']*20)
if __name__=='__main__':unittest.main()
