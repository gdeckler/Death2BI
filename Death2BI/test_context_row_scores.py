import unittest
from unittest.mock import patch

import duckdb

from dax_core import Parser
from dax_engine import Evaluator
from dax_grouped import evaluate_context_rows
from dax_runtime import Table
from dax_sql import UnsupportedSql


class ContextRowScoreTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("CREATE TABLE F AS SELECT * FROM (VALUES (1,10,2010,3.0,'Normal'),(1,10,2010,3.0,'Normal'),(2,10,2020,9.0,'Outlier'),(3,20,2010,5.0,'Normal'),(4,20,2010,NULL,'Outlier'),(5,NULL,2010,8.0,'Normal')) f(ID,CategoryID,Year,Amount,Status)")
        self.con.execute("CREATE TABLE D AS SELECT * FROM (VALUES (10,'A'),(20,'B'),(30,'Empty'),(NULL,NULL)) d(CategoryID,Category)")
        self.con.execute("CREATE TABLE Calendar AS SELECT * FROM (VALUES (2010,'2010s'),(2020,'2020s')) c(Year,Decade)")
        self.con.execute("CREATE TABLE Choices AS SELECT * FROM (VALUES ('All'),('Normal')) c(Choice)")
        self.model = {'tables': [{'name': n} for n in ('F', 'D', 'Calendar', 'Choices')], 'relationships': [
            {'IsActive': True, 'Cardinality': 'M:1', 'CrossFilteringBehavior': 'Single', 'FromTableName': 'F', 'FromColumnName': 'CategoryID', 'ToTableName': 'D', 'ToColumnName': 'CategoryID'},
            {'IsActive': True, 'Cardinality': 'M:1', 'CrossFilteringBehavior': 'Single', 'FromTableName': 'F', 'FromColumnName': 'Year', 'ToTableName': 'Calendar', 'ToColumnName': 'Year'},
        ], 'measures': [
            {'TableName': 'M', 'Name': 'Amount', 'Expression': 'SUM(F[Amount])'},
            {'TableName': 'M', 'Name': 'Median', 'Expression': 'MEDIAN(F[Amount])'},
            {'TableName': 'M', 'Name': 'ChoiceAmount', 'Expression': 'SWITCH(SELECTEDVALUE(Choices[Choice]),"All",SUM(F[Amount]),"Normal",CALCULATE(SUM(F[Amount]),F[Status]="Normal"))'},
        ]}
        self.rows = Table([('D', {'Category': c}) for c in ('A', 'B', 'Empty', None)], [('D', 'Category')])
        self.filters = [{'table': 'Calendar', 'columns': ['Decade'], 'sql': '"Calendar"."Decade" = \'2010s\''}, {'table': 'D', 'columns': ['Category'], 'sql': '"D"."Category" = \'A\''}]

    def tearDown(self):
        self.con.close()

    def compare(self, expressions, filters=None, env=None, rows=None):
        rows = self.rows if rows is None else rows
        engine = Evaluator(self.con, self.model, filters=self.filters if filters is None else filters)
        asts = [Parser(expression).parse() for expression in expressions]
        actual = evaluate_context_rows(engine, rows, asts, env)
        with patch('dax_sql.evaluate_scalar', side_effect=UnsupportedSql), patch('dax_rowset.evaluate_rows', side_effect=UnsupportedSql):
            expected = [[engine.scalar(engine.run(ast, env or {}, row)) for ast in asts] for row in rows]
        self.assertEqual(actual, expected)
        return actual

    def test_partial_dimension_transition_replaces_category_and_keeps_date(self):
        self.assertEqual(self.compare(['[Amount]', '[Median]']), [[6, 3], [5, 5], [None, None], [None, None]])

    def test_explicit_transition_scalar_variables_and_unused_table_bindings(self):
        values = self.compare(['CALCULATE([Amount])*factor+bonus'], env={'factor': 10, 'bonus': 2, 'UnusedRows': self.rows})
        self.assertEqual(values, [[62], [52], [2], [2]])

    def test_parameters_and_secured_views_preserve_filters(self):
        for choice in ('All', 'Normal'):
            filters = [*self.filters, {'table': 'Choices', 'columns': ['Choice'], 'sql': '"Choices"."Choice" = \'' + choice + '\''}]
            self.compare(['[ChoiceAmount]'], filters)
        self.con.execute('ALTER TABLE F RENAME TO private_rows')
        self.con.execute('CREATE VIEW F AS SELECT * FROM private_rows WHERE ID=3')
        self.assertEqual(self.compare(['[Amount]']), [[None], [5], [None], [None]])

    def test_keep_values_requires_an_existing_unchanged_domain(self):
        expression = 'CALCULATE([Amount],KEEPFILTERS(VALUES(Calendar[Decade])))'
        self.assertEqual(self.compare([expression]), [[6], [5], [None], [None]])
        engine = Evaluator(self.con, self.model, filters=[])
        with self.assertRaises(UnsupportedSql):
            evaluate_context_rows(engine, self.rows, [Parser(expression).parse()])
        calendar_rows = Table([('Calendar', {'Decade': '2010s'}), ('Calendar', {'Decade': '2020s'})], [('Calendar', 'Decade')])
        engine = Evaluator(self.con, self.model, filters=self.filters)
        with self.assertRaises(UnsupportedSql):
            evaluate_context_rows(engine, calendar_rows, [Parser(expression).parse()])

    def test_unsafe_row_contexts_and_bare_aggregates_decline(self):
        engine = Evaluator(self.con, self.model, filters=self.filters)
        with self.assertRaises(UnsupportedSql):
            evaluate_context_rows(engine, self.rows, [Parser('SUM(F[Amount])').parse()])
        foreign_keys = Table([('F', {'CategoryID': 10})], [('F', 'CategoryID')])
        with self.assertRaises(UnsupportedSql):
            evaluate_context_rows(engine, foreign_keys, [Parser('[Amount]').parse()])
        virtual = Table([('__virtual', {'Category': 'A'}, {('D', 'Category'): 'A'})], [('D', 'Category')])
        with self.assertRaises(UnsupportedSql):
            evaluate_context_rows(engine, virtual, [Parser('[Amount]').parse()])
        engine.row_stack = [('D', {'Category': 'A'})]
        with self.assertRaises(UnsupportedSql):
            evaluate_context_rows(engine, self.rows, [Parser('[Amount]').parse()])

    def test_rankx_uses_identical_ties_and_scalar_target(self):
        expression = 'RANKX(ALL(D[Category]),CALCULATE([Amount],KEEPFILTERS(VALUES(Calendar[Decade]))),,DESC,SKIP)'
        ast = Parser(expression).parse()
        engine = Evaluator(self.con, self.model, filters=self.filters)
        actual = engine.run(ast, {}, None)
        self.assertEqual(engine.budget.get('grouped_relationship_scans'), 1)
        with patch('dax_grouped.evaluate_context_rows', side_effect=UnsupportedSql):
            expected = engine.run(ast, {}, None)
        self.assertEqual(actual, expected)
        self.assertEqual(actual, 1)

    def test_projected_physical_names_keep_pre_transition_shadowing(self):
        self.con.execute('ALTER TABLE D ADD COLUMN Amount INTEGER')
        self.con.execute('UPDATE D SET Amount=CategoryID*10')
        rows=Table([('D',{'Amount':100}),('D',{'Amount':200})],[('D','Amount')])
        engine=Evaluator(self.con,self.model,filters=[])
        for expression in ('[Amount]','D[Amount]'):
            with self.subTest(expression=expression),self.assertRaises(UnsupportedSql):
                evaluate_context_rows(engine,rows,[Parser(expression).parse()])
        # CALCULATE consumes the row context before resolving its expression;
        # a qualified model measure is also unambiguous before transition.
        self.assertEqual(self.compare(['CALCULATE([Amount])','M[Amount]'],filters=[],rows=rows),[[15,15],[5,5]])


if __name__ == '__main__':
    unittest.main()
