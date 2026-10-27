import datetime as dt
import time
import unittest
from decimal import Decimal
from unittest.mock import patch

import duckdb

from dax_core import Parser
from dax_engine import Evaluator
from dax_rowset import evaluate_rows
from dax_runtime import Table
from dax_sql import UnsupportedSql


class RowsetScoreTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("CREATE TABLE T AS SELECT * FROM (VALUES (1,0.2,0.9),(2,0.9,0.3),(3,NULL,0.7),(4,0.2,0.9)) t(ID,A,B)")
        self.con.execute("CREATE TABLE P AS SELECT * FROM (VALUES (0.0),(0.5),(1.0)) p(W)")
        self.con.execute("CREATE TABLE Mode AS SELECT * FROM (VALUES ('Arithmetic'),('Geometric')) m(Mode)")
        self.model = {'tables': [{'name': t} for t in ('T', 'P', 'Mode')], 'relationships': [], 'measures': [
            {'TableName': 'M', 'Name': 'Weight', 'Expression': 'VAR w=SELECTEDVALUE(P[W],0.5) RETURN MAX(0,MIN(1,w))'},
            {'TableName': 'M', 'Name': 'Score', 'Expression': 'VAR w=[Weight] VAR a=SELECTEDVALUE(T[A]) VAR b=SELECTEDVALUE(T[B]) VAR mode=SELECTEDVALUE(Mode[Mode],"Arithmetic") RETURN IF(mode="Geometric", MAX(a,1e-9)^w * MAX(b,1e-9)^(1-w), a*w+b*(1-w))'},
            {'TableName': 'M', 'Name': 'Amount', 'Expression': 'SUM(T[A])'},
        ]}

    def tearDown(self):
        self.con.close()

    def engine(self, filters=()):
        return Evaluator(self.con, self.model, filters=list(filters))

    def compare(self, expression, filters=(), env=None):
        fast = self.engine(filters)
        rows = fast.table('T')
        node = Parser(expression).parse()
        actual = [v[0] for v in evaluate_rows(fast, rows, [node], env)]
        slow = self.engine(filters)
        with patch('dax_sql.evaluate_scalar', side_effect=UnsupportedSql):
            expected = [slow.scalar(slow.run(node, env, (*r,))) for r in rows]
        self.assertEqual(actual, expected)
        return fast, rows, node, actual

    def test_weighted_math_matches_python_with_parameter_selections(self):
        for mode in ('Arithmetic', 'Geometric'):
            for weight in (0, Decimal('0.5'), 1):
                with self.subTest(mode=mode, weight=weight):
                    filters = [{'table': 'P', 'columns': ['W'], 'sql': '"P"."W"=' + str(weight)}, {'table': 'Mode', 'columns': ['Mode'], 'sql': '"Mode"."Mode"=\'' + mode + '\''}]
                    self.compare('[Score]', filters)

    def test_blank_and_strict_equality(self):
        for expr in ('T[A]+T[B]', 'T[A]*T[B]', 'T[A]=0', 'T[A]==BLANK()', 'NOT ISBLANK([Score])', 'IF(ISBLANK(T[A]),0,T[A])', 'DIVIDE(T[A],0,99)', 'COALESCE(T[A],T[B])'):
            with self.subTest(expr=expr):
                self.compare(expr)

    def test_bare_selectedvalue_keeps_filter_context(self):
        self.compare('SELECTEDVALUE(T[A],-1)')
        self.compare('SELECTEDVALUE(T[A],-1)', [{'table': 'T', 'columns': ['A'], 'sql': '"T"."A"=0.2'}])

    def test_ties_and_request_local_reuse(self):
        engine, rows, node, values = self.compare('[Score]')
        self.assertEqual(values[0], values[3])
        repeated = evaluate_rows(engine, rows, [node], {'UnusedTable': rows})
        self.assertEqual(repeated, [[value] for value in values])
        self.assertEqual(engine.budget['rowset_cache_hits'], 1)

    def test_virtual_extension_and_empty_lineage_outer_context(self):
        engine = self.engine()
        physical = engine.table('T')
        rows = Table([('__virtual', {**r[1], '@Group': i % 2}, {(t, c): r[1][c] for t, c in physical.columns}) for i, r in enumerate(physical)], [*physical.columns, ('__virtual', '@Group')])
        engine.row_stack = [('__virtual', {'GroupVal': 1}, {})]
        values = evaluate_rows(engine, rows, [Parser('[@Group]=[GroupVal]').parse(), Parser('[Score]').parse()])
        self.assertEqual([v[0] for v in values], [False, True, False, True])

    def test_measure_transition_drops_virtual_field_shadowing(self):
        self.model['measures'].extend([
            {'TableName': 'M', 'Name': 'Child', 'Expression': '2'},
            {'TableName': 'M', 'Name': 'Parent', 'Expression': '[Child]'},
            {'TableName': 'M', 'Name': 'ParentSelected', 'Expression': 'SELECTEDVALUE(T[A])+[Child]'},
        ])
        engine = self.engine()
        base = engine.table('T')
        virtual = Table([('__virtual', {**r[1], 'Child': 99}, {(t, c): r[1][c] for t, c in base.columns}) for r in base], [*base.columns, ('__virtual', 'Child')])
        result = evaluate_rows(engine, virtual, [Parser(expression).parse() for expression in ('[Child]', "'M'[Parent]", "'M'[ParentSelected]")])
        self.assertEqual(result[0], [99, 2, Decimal('2.2')])
        self.assertEqual(result[2], [99, 2, 2])
        with patch('dax_rowset.evaluate_rows', side_effect=UnsupportedSql):
            reference = [engine.run(Parser("'M'[Parent]").parse(), {}, (*r,)) for r in virtual]
        self.assertEqual([v[1] for v in result], reference)

    def test_measure_unqualified_name_resolves_measure_before_physical_column(self):
        self.model['measures'].extend([
            {'TableName': 'M', 'Name': 'ID', 'Expression': '42'},
            {'TableName': 'M', 'Name': 'Parent', 'Expression': '[ID]'},
            {'TableName': 'M', 'Name': 'Physical', 'Expression': 'T[ID]'},
        ])
        engine = self.engine()
        rows = engine.table('T')
        result = evaluate_rows(engine, rows, [Parser(expression).parse() for expression in ('[ID]', "'M'[Parent]", "'M'[Physical]")])
        self.assertEqual(result, [[i, 42, i] for i in (1, 2, 3, 4)])

    def test_unused_table_bindings_do_not_block_scores(self):
        engine = self.engine()
        rows = engine.table('T')
        evaluate_rows(engine, rows, [Parser('[Score]').parse()], {'Unused': rows})
        with self.assertRaises(UnsupportedSql):
            evaluate_rows(engine, rows, [Parser('Unused').parse()], {'Unused': rows})

    def test_partial_lineage_context_modifiers_and_volatile_rejected(self):
        engine = self.engine()
        rows = engine.project(('col', 'T', 'ID'), True)
        with self.assertRaises(UnsupportedSql):
            evaluate_rows(engine, rows, [Parser('[Score]').parse()])
        rows = engine.table('T')
        for expression in ('CALCULATE([Score],ALL(T))', 'NOW()', 'SUM(T[A])'):
            with self.subTest(expression=expression), self.assertRaises(UnsupportedSql):
                evaluate_rows(engine, rows, [Parser(expression).parse()])

    def test_arithmetic_errors_not_hidden(self):
        engine = self.engine()
        rows = engine.table('T')
        with self.assertRaises(ZeroDivisionError):
            evaluate_rows(engine, rows, [Parser('T[A]/0').parse()])

    def test_lazy_branches_do_not_evaluate_unchosen_constant_errors(self):
        for expression in ('IF(T[ID]>0,T[ID],1/0)', 'COALESCE(T[ID],1/0)', 'DIVIDE(T[ID],1,1/0)', 'SWITCH(T[ID],1,7,2,8,3,9,4,10,1/0)'):
            with self.subTest(expression=expression):
                self.compare(expression)
        for expression in ('IF(T[ID]>0,1/0,T[ID])', 'COALESCE(BLANK(),1/0)', 'DIVIDE(T[ID],0,1/0)', 'SWITCH(T[ID],-1,7,1/0)'):
            with self.subTest(expression=expression), self.assertRaises(ZeroDivisionError):
                self.compare(expression)

    def test_text_parameter_uses_case_insensitive_identity(self):
        self.con.execute("CREATE TABLE Label AS SELECT * FROM (VALUES ('A'),('a')) p(Label)")
        self.model['tables'].append({'name': 'Label'})
        self.model['measures'].append({'TableName': 'M', 'Name': 'LabelValue', 'Expression': 'SELECTEDVALUE(Label[Label],"many")'})
        engine = self.engine()
        rows = engine.table('T')
        actual = evaluate_rows(engine, rows, [Parser('[LabelValue]').parse()])
        self.assertEqual(actual, [['A']] * 4)

    def test_function_non_finite_results_match_python(self):
        engine = self.engine()
        rows = engine.table('T')
        for expression in ('POWER(-T[ID],0.5)', 'IF(T[ID]>0,T[ID],POWER(-1,0.5))'):
            if expression.startswith('IF'):
                self.compare(expression)
            else:
                with self.assertRaisesRegex(ValueError, 'Non-finite'):
                    evaluate_rows(engine, rows, [Parser(expression).parse()])
    def test_budget_and_filtered_connection_respected(self):
        self.con.execute('DELETE FROM T WHERE ID=2')
        engine = self.engine()
        rows = engine.table('T')
        values = evaluate_rows(engine, rows, [Parser('[Score]').parse()])
        self.assertEqual(len(values), 3)
        engine.budget['deadline'] = time.monotonic() - 1
        with self.assertRaisesRegex(RuntimeError, 'time limit'):
            evaluate_rows(engine, rows, [Parser('[Score]').parse()])

    def test_related_selectedvalue_and_physical_outer_row_rejected(self):
        self.con.execute('CREATE TABLE D AS SELECT 1 ID, 42 N')
        self.model['tables'].append({'name': 'D'})
        self.model['relationships'].append({'FromTableName': 'T', 'FromColumnName': 'ID', 'ToTableName': 'D', 'ToColumnName': 'ID', 'IsActive': True, 'Cardinality': 'M:1'})
        self.model['measures'].append({'Name': 'RelatedValue', 'TableName': 'M', 'Expression': 'SELECTEDVALUE(D[N])'})
        engine = self.engine()
        rows = engine.table('T')
        with self.assertRaises(UnsupportedSql):
            evaluate_rows(engine, rows, [Parser('[RelatedValue]').parse()])
        engine.row_stack = [rows[0]]
        with self.assertRaises(UnsupportedSql):
            evaluate_rows(engine, rows, [Parser('[Score]').parse()])

    def test_held_rows_with_a_later_related_filter_fall_back(self):
        self.con.execute("CREATE TABLE Bridge AS SELECT * FROM (VALUES (1,'A'),(2,'B'),(3,'A'),(4,'B')) b(ID,Category)")
        self.model['tables'].append({'name': 'Bridge'})
        self.model['relationships'].append({'FromTableName': 'T', 'FromColumnName': 'ID', 'ToTableName': 'Bridge', 'ToColumnName': 'ID', 'IsActive': True, 'Cardinality': 'M:M'})
        engine = self.engine()
        held = engine.table('T')
        changed = engine.child([{'table': 'Bridge', 'columns': ['Category'], 'sql': '"Bridge"."Category"=\'A\''}])
        with self.assertRaisesRegex(UnsupportedSql, 'excluded'):
            evaluate_rows(changed, held, [Parser('[Score]').parse()])
        current = changed.table('T')
        self.assertEqual(len(evaluate_rows(changed, current, [Parser('[Score]').parse()])), 2)


if __name__ == '__main__':
    unittest.main()
