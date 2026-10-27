import unittest
from unittest.mock import patch

import duckdb

from dax_engine import Evaluator, Parser
from dax_runtime import Table
from dax_sql import UnsupportedSql
from dax_vector import cumulative_columns


class VirtualIteratorFallbackTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute('CREATE TABLE M (Unused INTEGER)')
        self.model = {'tables': [{'name': 'M'}], 'measures': []}

    def tearDown(self):
        self.con.close()

    def measure(self, expression):
        model = {**self.model, 'measures': [
            {'TableName': 'M', 'Name': 'Caption', 'Expression': expression}
        ]}
        return Evaluator(self.con, model, filters=[]).measure('Caption')

    def test_generated_virtual_prefix_sums_keep_row_value_and_blank(self):
        expression = '''
        VAR T = GENERATESERIES(1, 3)
        VAR A = ADDCOLUMNS(T, "@a", [Value] * 10)
        VAR X = ADDCOLUMNS(A, "@x",
            VAR i = [Value]
            RETURN SUMX(FILTER(A, [Value] < i), [@a]))
        RETURN CONCATENATEX(X, [@x], ",", [Value], ASC)
        '''
        self.assertEqual(self.measure(expression), ',10,30')
        with patch('dax_vector.cumulative_columns', side_effect=UnsupportedSql):
            self.assertEqual(self.measure(expression), ',10,30')

    def test_constructor_and_selectcolumns_aliases_use_virtual_scope(self):
        for source, key in [('{1,2,3}', 'Value'),
                            ('SELECTCOLUMNS(GENERATESERIES(1,3), "Position", [Value])', 'Position')]:
            with self.subTest(source=source):
                expression = f'''VAR T={source}
                VAR X=ADDCOLUMNS(T,"@x",VAR i=[{key}] RETURN SUMX(FILTER(T,[{key}]<i),[{key}]))
                RETURN CONCATENATEX(X,[@x],",",[{key}],ASC)'''
                self.assertEqual(self.measure(expression), ',1,3')

    def test_generated_value_shadows_same_named_home_table_column(self):
        self.con.execute('ALTER TABLE M ADD COLUMN Value INTEGER')
        self.con.execute('INSERT INTO M VALUES (1, 999)')
        expression = '''VAR T=GENERATESERIES(1,3)
        VAR X=ADDCOLUMNS(T,"@x",VAR i=[Value] RETURN SUMX(FILTER(T,[Value]<i),[Value]))
        RETURN CONCATENATEX(X,[@x],",",[Value],ASC)'''
        self.assertEqual(self.measure(expression), ',1,3')

    def test_eligibility_never_resolves_virtual_columns_as_physical(self):
        engine = Evaluator(self.con, self.model, filters=[])
        rows = Table([('__virtual', {'Value': 1})], [('__virtual', 'Value')])
        expression = Parser('VAR i=[Value] RETURN SUMX({1},[Value])').parse()
        with patch.object(engine, 'column', side_effect=AssertionError('metadata lookup')):
            with self.assertRaisesRegex(UnsupportedSql, 'Virtual cumulative domain'):
                cumulative_columns(engine, rows, [expression])

    def test_unsupported_physical_expression_is_declined_before_metadata(self):
        engine = Evaluator(self.con, self.model, filters=[])
        rows = engine.table('M')
        expression = Parser('VAR i=[OuterAlias] RETURN "caption"').parse()
        with patch.object(engine, 'column', side_effect=AssertionError('metadata lookup')):
            with self.assertRaisesRegex(UnsupportedSql, 'Cumulative calculation'):
                cumulative_columns(engine, rows, [expression])

    def test_true_source_resolution_errors_still_surface(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            self.measure('''VAR T=GENERATESERIES(1,3)
            RETURN CONCATENATEX(ADDCOLUMNS(T,"X",VAR i=M[Missing] RETURN i),[X],",")''')


if __name__ == '__main__':
    unittest.main()
