import unittest,json
from decimal import Decimal
from server import json_scalar
class NumericWireTests(unittest.TestCase):
 def test_decimal_stays_numeric(self):
  value=json.loads(json.dumps({'rows':[[Decimal('32.032'),None,'32.032']]},default=json_scalar))
  self.assertEqual(value['rows'],[[32.032,None,'32.032']]);self.assertIsInstance(value['rows'][0][0],float)
  self.assertIsNone(json_scalar(Decimal('NaN')))
if __name__=='__main__':unittest.main()
