import math
import unittest
from unittest.mock import patch

import duckdb

from dax_engine import Evaluator, evaluate_visual
from dax_sql import evaluate_scalar, UnsupportedSql


class SqlTrigonometryTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("CREATE TABLE T AS SELECT * FROM (VALUES (1,DATE '2020-03-01',2.5),(2,DATE '2022-07-15',0.0)) t(ID,D,R)")
        self.model = {'tables': [{'name': 'T'}], 'relationships': [], 'measures': [
            {'Name': 'Angle', 'TableName': 'M', 'Expression': 'VAR selection="YEAR" VAR arc=RADIANS(300) VAR minDate=1990 VAR maxDate=2023 VAR years=maxDate-minDate VAR current=IF(selection="YEAR",YEAR(SELECTEDVALUE(T[D]))-YEAR(minDate),SELECTEDVALUE(T[D])-minDate) RETURN RADIANS(-54)+DIVIDE(current,years,0)*arc'},
            {'Name': 'X', 'TableName': 'M', 'Expression': 'CALCULATE(SELECTEDVALUE(T[R])*COS([Angle]))'},
            {'Name': 'Y', 'TableName': 'M', 'Expression': 'CALCULATE(SELECTEDVALUE(T[R])*SIN([Angle]))'},
        ]}

    def tearDown(self):
        self.con.close()

    def test_polar_grouped_coordinates_match_interpreter(self):
        groups = [{'values': {'0': i}, 'filters': [{'table': 'T', 'columns': ['ID'], 'sql': '"T"."ID" = ' + str(i)}], 'externalFilters': [], 'scope': [('T', 'ID')]} for i in (1, 2)]
        fields = [{'Column': {'Expression': {'SourceRef': {'Entity': 'T'}}, 'Property': 'ID'}}] + [{'Measure': {'Expression': {'SourceRef': {'Entity': 'M'}}, 'Property': n}} for n in ('X', 'Y')]
        result = evaluate_visual(self.con, self.model, {'groups': groups, 'fields': fields})
        self.assertEqual(result['evaluation']['execution'], 'batched SQL')
        with patch('dax_sql.evaluate_scalar', side_effect=UnsupportedSql), patch('dax_sql.evaluate_expression', side_effect=UnsupportedSql):
            for row, group in zip(result['rows'], groups):
                engine = Evaluator(self.con, self.model, filters=group['filters'])
                for i, name in enumerate(('X', 'Y'), 1):
                    self.assertAlmostEqual(row[i], engine.measure(name), places=12)

    def test_numeric_date_literals_keep_serial_year_semantics(self):
        for value, expected in (('1990', 1905), ('0', 1899), ('"2022-05-06"', 2022)):
            self.model['measures'].append({'Name': 'YearValue', 'TableName': 'M', 'Expression': 'YEAR(' + value + ')'})
            self.assertEqual(evaluate_scalar(Evaluator(self.con, self.model, filters=[]), 'YearValue'), expected)
            self.model['measures'].pop()

    def test_blank_trig_and_signed_angles_match_runtime(self):
        for expression, expected in (('COS(BLANK())', 1), ('SIN(BLANK())', 0), ('RADIANS(BLANK())', 0), ('COS(RADIANS(-54))', math.cos(math.radians(-54)))):
            self.model['measures'].append({'Name': 'Value', 'TableName': 'M', 'Expression': expression})
            self.assertAlmostEqual(evaluate_scalar(Evaluator(self.con, self.model, filters=[]), 'Value'), expected, places=12)
            self.model['measures'].pop()

    def test_text_numeric_coercion_keeps_conservative_fallback(self):
        self.model['measures'].append({'Name': 'TextValue', 'TableName': 'M', 'Expression': 'COS("1,000")'})
        with self.assertRaises(UnsupportedSql):
            evaluate_scalar(Evaluator(self.con, self.model, filters=[]), 'TextValue')
        self.assertAlmostEqual(Evaluator(self.con, self.model, filters=[]).measure('TextValue'), math.cos(1000), places=12)

    def test_constant_if_does_not_bind_an_unreachable_invalid_branch(self):
        self.model['measures'].append({'Name': 'Conditional', 'TableName': 'M', 'Expression': 'VAR mode="YEAR" RETURN IF(mode="YEAR",YEAR(SELECTEDVALUE(T[D])),SELECTEDVALUE(T[D])-1990)'})
        filters = [{'table': 'T', 'columns': ['ID'], 'sql': '"T"."ID"=1'}]
        self.assertEqual(evaluate_scalar(Evaluator(self.con, self.model, filters=filters), 'Conditional'), 2020)


if __name__ == '__main__':
    unittest.main()
