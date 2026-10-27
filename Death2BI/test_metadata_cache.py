"""Physical schema proofs are request-local and shared by calculation contexts."""
import datetime
import re
import unittest

import duckdb
from dax_metadata import schema, type_name
from dax_runtime import RuntimeEvaluator


class CountingConnection:
    def __init__(self, connection):
        self.connection = connection
        self.metadata_sql = []
        self.sql = []

    def execute(self, sql, *args, **kwargs):
        self.sql.append(sql)
        if re.search(r'\bLIMIT\s+0\s*$', sql, re.I):
            self.metadata_sql.append(sql)
        self.connection.execute(sql, *args, **kwargs)
        return self

    def __getattr__(self, name):
        return getattr(self.connection, name)


class MetadataCacheTests(unittest.TestCase):
    def evaluator(self, connection, table='Data', columns=('Amount', 'Label')):
        counted = CountingConnection(connection)
        model = {'tables': [{'name': table, 'columns': [{'name': name, 'type': 'VARCHAR'} for name in columns]}],
                 'relationships': [], 'measures': []}
        return RuntimeEvaluator(counted, model, filters=[]), counted

    def database(self):
        connection = duckdb.connect(':memory:')
        self.addCleanup(connection.close)
        return connection

    def test_one_schema_fetch_across_names_types_aggregates_and_child_filters(self):
        connection = self.database()
        connection.execute("CREATE TABLE Data(Amount DECIMAL(12,2),Label VARCHAR); INSERT INTO Data VALUES(10.25,'one'),(23.50,'two')")
        engine, counted = self.evaluator(connection)
        description = schema(engine, 'Data')
        self.assertIsInstance(description, tuple)
        self.assertEqual([column[0] for column in description], ['Amount', 'Label'])
        self.assertEqual(type_name(engine, 'Data', 'Amount'), 'DECIMAL(12,2)')
        self.assertEqual(engine.column(('col', 'data', 'amount')), ('Data', 'Amount'))
        for index in range(20):
            child = engine.child([{'table': 'Data', 'columns': ['Label'], 'sql': '"Data"."Label" = \'two\''}])
            self.assertIs(schema(child, 'Data'), description, 'context changes keep the same secured physical schema')
            self.assertEqual(type_name(child, 'Data', 'Amount'), 'DECIMAL(12,2)')
            self.assertEqual(child.column(('col', 'Data', 'label')), ('Data', 'Label'))
            self.assertEqual(float(child.aggregate('SUM', [('col', 'Data', 'Amount')], {}, None)), 23.5)
        self.assertEqual(float(engine.aggregate('SUM', [('col', 'Data', 'Amount')], {}, None)), 33.75)
        self.assertEqual(len(counted.metadata_sql), 1, 'do not repeatedly prepare LIMIT0 SQL for each aggregate/context')
        with self.assertRaises(ValueError):
            engine.column(('col', 'Data', 'Missing'))

    def test_same_table_names_in_separate_requests_never_reuse_different_schemas(self):
        first = self.database()
        first.execute('CREATE TABLE Data(Amount INTEGER,Label VARCHAR)')
        second = self.database()
        second.execute('CREATE TABLE Data(Amount DATE,Other BOOLEAN)')
        engine_a, counted_a = self.evaluator(first)
        engine_b, counted_b = self.evaluator(second, columns=('Amount', 'Other'))
        self.assertEqual(type_name(engine_a, 'Data', 'Amount'), 'INTEGER')
        self.assertEqual(type_name(engine_b, 'Data', 'Amount'), 'DATE')
        self.assertEqual(engine_b.column(('col', 'Data', 'Other')), ('Data', 'Other'))
        self.assertNotIn('Label', [column[0] for column in schema(engine_b, 'Data')])
        self.assertEqual(len(counted_a.metadata_sql), 1)
        self.assertEqual(len(counted_b.metadata_sql), 1)
        self.assertIsNot(engine_a.budget, engine_b.budget)

    def test_secured_view_schema_and_data_override_stale_manifest_types(self):
        connection = self.database()
        connection.execute("CREATE TABLE PrivateData(Owner VARCHAR,Raw VARCHAR); INSERT INTO PrivateData VALUES('alice','10.25'),('bob','9999.00')")
        connection.execute("CREATE TEMP VIEW Data AS SELECT CAST(Raw AS DECIMAL(12,2)) AS Amount FROM PrivateData WHERE Owner='alice'")
        engine, counted = self.evaluator(connection, columns=('Amount',))
        self.assertEqual([column[0] for column in schema(engine, 'Data')], ['Amount'])
        self.assertEqual(type_name(engine, 'Data', 'Amount'), 'DECIMAL(12,2)', 'manifest VARCHAR is not a physical numeric proof')
        self.assertEqual(float(engine.aggregate('SUM', [('col', 'Data', 'Amount')], {}, None)), 10.25)
        self.assertEqual(len(counted.metadata_sql), 1)
        self.assertTrue(all('PrivateData' not in sql for sql in counted.sql), 'only the caller secured view may be inspected/queried')

    def test_quoted_physical_identifiers_and_temporal_types(self):
        connection = self.database()
        connection.execute('CREATE TABLE "Line ""Items"""("Cost ""USD""" DOUBLE,"Order" TIMESTAMP)')
        connection.execute("INSERT INTO \"Line \"\"Items\"\"\" VALUES(12.5,TIMESTAMP '2026-01-02 03:04:05')")
        engine, counted = self.evaluator(connection, table='Line "Items"', columns=('Cost "USD"', 'Order'))
        self.assertEqual(type_name(engine, 'Line "Items"', 'Cost "USD"'), 'DOUBLE')
        self.assertEqual(type_name(engine, 'Line "Items"', 'Order'), 'TIMESTAMP')
        self.assertEqual(engine.column(('col', 'Line "Items"', 'order')), ('Line "Items"', 'Order'))
        self.assertEqual(engine.aggregate('MAX', [('col', 'Line "Items"', 'Order')], {}, None), datetime.datetime(2026, 1, 2, 3, 4, 5))
        self.assertEqual(len(counted.metadata_sql), 1)


if __name__ == '__main__':
    unittest.main()
