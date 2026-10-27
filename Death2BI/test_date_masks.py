import unittest,datetime as dt
from dax_functions import format_value
class DateMaskTests(unittest.TestCase):
 def test_clock_and_date(self):
  d=dt.datetime(2026,10,25,13,7,9)
  self.assertEqual(format_value(d,'dd-MMM-yyyy hh:mm AM/PM'),'25-Oct-2026 01:07 PM')
  self.assertEqual(format_value(d,'yyyy/mm/dd hh:mm:ss'),'2026/10/25 13:07:09')
  self.assertEqual(format_value(d,'d mmmm yyyy h:n','es-PY'),'25 octubre 2026 13:7')
  self.assertEqual(format_value(d,'"Updated" dd mmm yyyy'),'Updated 25 Oct 2026')
 def test_midnight(self):self.assertEqual(format_value(dt.datetime(2026,1,1),'h:mm AM/PM'),'12:00 AM')
 def test_invalid(self):
  with self.assertRaisesRegex(ValueError,'Unsupported'):format_value(dt.datetime(2026,1,1),'unsupported')
if __name__=='__main__':unittest.main()
