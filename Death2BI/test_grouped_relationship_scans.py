import time
import unittest
from unittest.mock import patch

import duckdb

from dax_core import qi, sv
from dax_engine import Evaluator, evaluate_topn
from dax_grouped import evaluate_grouped
from dax_sql import UnsupportedSql, evaluate_groups


class GroupedRelationshipScanTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute('CREATE TABLE F AS SELECT * FROM (VALUES (1,10.0,2.0,3.0),(1,10.0,2.0,3.0),(2,20.0,4.0,9.0),(3,NULL,0.0,NULL),(4,7.0,1.0,5.0),(5,100.0,10.0,1.0)) f(ID,Revenue,Budget,Popularity)')
        self.con.execute('CREATE TABLE Bridge AS SELECT * FROM (VALUES (1,10),(1,10),(1,11),(2,10),(2,20),(3,30),(4,NULL),(5,999)) b(ID,GroupID)')
        self.con.execute("CREATE TABLE D AS SELECT * FROM (VALUES (10,'A'),(11,'A'),(20,'B'),(30,NULL),(40,'Empty'),(NULL,NULL)) d(GroupID,Category)")
        self.model = {'tables': [{'name': n} for n in ('F', 'Bridge', 'D')], 'relationships': [
            {'IsActive': True, 'Cardinality': 'M:M', 'CrossFilteringBehavior': 'Single', 'FromTableName': 'F', 'FromColumnName': 'ID', 'ToTableName': 'Bridge', 'ToColumnName': 'ID'},
            {'IsActive': True, 'Cardinality': 'M:1', 'CrossFilteringBehavior': 'Single', 'FromTableName': 'Bridge', 'FromColumnName': 'GroupID', 'ToTableName': 'D', 'ToColumnName': 'GroupID'},
        ], 'measures': [
            {'TableName': 'M', 'Name': 'Revenue', 'Expression': 'SUM(F[Revenue])'},
            {'TableName': 'M', 'Name': 'Profit', 'Expression': 'SUM(F[Revenue])-SUM(F[Budget])'},
            {'TableName': 'M', 'Name': 'Count', 'Expression': 'CALCULATE(COUNTROWS(F))'},
            {'TableName': 'M', 'Name': 'Median', 'Expression': 'MEDIAN(F[Popularity])'},
            {'TableName': 'M', 'Name': 'MedianX', 'Expression': 'MEDIANX(F,F[Popularity])'},
            {'TableName': 'M', 'Name': 'MedianROI', 'Expression': 'MEDIANX(FILTER(F,F[Budget]>=1),DIVIDE(F[Revenue]-F[Budget],F[Budget]))'},
            {'TableName': 'M', 'Name': 'ConditionalMedian', 'Expression': 'VAR Minimum=3 VAR N=CALCULATE(COUNTROWS(F)) RETURN IF(N>=Minimum,MEDIAN(F[Popularity]),BLANK())'},
            {'TableName': 'M', 'Name': 'Distinct', 'Expression': 'DISTINCTCOUNT(F[Popularity])'},
        ]}

    def tearDown(self):
        self.con.close()

    def payload(self, names, values=('A', 'B', None, 'Empty', 'Missing'), external=(), table='D', column='Category'):
        fields = [{'Column': {'Expression': {'SourceRef': {'Entity': table}}, 'Property': column}}] + [{'Measure': {'Expression': {'SourceRef': {'Entity': 'M'}}, 'Property': name}} for name in names]
        groups = []
        for value in values:
            predicate = qi(table) + '.' + qi(column) + (' IS NULL' if value is None else ' = ' + sv(value))
            groups.append({'values': {'0': value}, 'filters': [*external, {'table': table, 'columns': [column], 'sql': predicate}], 'externalFilters': list(external), 'scope': [(table, column)]})
        return {'fields': fields, 'groups': groups}

    def evaluate(self, payload):
        engine = Evaluator(self.con, self.model, filters=[])
        result = evaluate_grouped(self.con, self.model, payload, engine.budget)
        self.assertEqual(engine.budget['grouped_relationship_scans'], 1)
        return result

    def compare(self, payload):
        actual = self.evaluate(payload)
        expected = []
        for group in payload['groups']:
            engine = Evaluator(self.con, self.model, filters=group['filters'])
            engine.external_filters = group['externalFilters']
            with patch('dax_sql.evaluate_scalar', side_effect=UnsupportedSql):
                expected.append(tuple([group['values']['0']] + [engine.measure(field['Measure']['Property'], 'M') for field in payload['fields'][1:]]))
        self.assertEqual(actual, expected)
        return actual

    def test_bridge_fanout_deduplicates_membership_but_keeps_duplicate_fact_rows(self):
        result = self.compare(self.payload(['Revenue', 'Count', 'Median', 'MedianX', 'MedianROI']))
        self.assertEqual(result[0], ('A', 40, 3, 3, 3, 4))
        self.assertEqual(result[1], ('B', 20, 1, 9, 9, 4))
        self.assertEqual(result[2], (None, None, 1, None, 0, None))
        self.assertEqual(result[3], ('Empty', None, None, None, None, None))

    def test_scalar_arithmetic_count_guard_and_blank_groups(self):
        self.compare(self.payload(['Profit', 'ConditionalMedian', 'Distinct']))
        self.assertEqual(self.evaluate(self.payload(['ConditionalMedian']))[0], ('A', 3))
        self.assertEqual(self.evaluate(self.payload(['ConditionalMedian']))[1], ('B', None))

    def test_external_filters_apply_to_secured_fact_domain(self):
        filters = [{'table': 'F', 'columns': ['Revenue'], 'sql': '"F"."Revenue">=15'}]
        result = self.compare(self.payload(['Revenue', 'Count', 'MedianROI'], external=filters))
        self.assertEqual(result[0], ('A', 20, 1, 4))

    def test_rls_view_is_the_only_fact_source(self):
        self.con.execute('ALTER TABLE F RENAME TO private_rows')
        self.con.execute('CREATE VIEW F AS SELECT * FROM private_rows WHERE ID=2')
        result = self.compare(self.payload(['Revenue', 'Count']))
        self.assertEqual(result[0], ('A', 20, 1))
        self.assertEqual(result[1], ('B', 20, 1))

    def test_disconnected_categories_repeat_aggregate(self):
        self.con.execute("CREATE TABLE Unrelated AS SELECT * FROM (VALUES ('X'),('Y')) u(Category)")
        self.model['tables'].append({'name': 'Unrelated'})
        result = self.compare(self.payload(['Revenue', 'Count'], values=('X', 'Y'), table='Unrelated'))
        self.assertEqual(result, [('X', 147, 6), ('Y', 147, 6)])

    def test_duplicate_group_inputs_preserve_order(self):
        result = self.evaluate(self.payload(['Revenue'], values=('B', 'A', 'A')))
        self.assertEqual(result, [('B', 20), ('A', 40), ('A', 40)])

    def test_topn_ties_include_boundary_and_uses_complete_domain(self):
        self.con.execute('INSERT INTO Bridge VALUES (2,40)')
        category = self.payload([])['fields'][0]
        by = self.payload(['Revenue'])['fields'][1]
        result = evaluate_topn(self.con, self.model, {'category': category, 'by': by, 'count': 2, 'descending': True, 'filters': []})
        self.assertEqual(set(result['values']), {'A', 'B', 'Empty'})

    def test_noncanonical_context_and_modified_calculate_fall_back(self):
        payload = self.payload(['Revenue'])
        payload['groups'][0]['filters'][-1]['sql'] = 'TRUE'
        engine = Evaluator(self.con, self.model, filters=[])
        with self.assertRaises(UnsupportedSql):
            evaluate_grouped(self.con, self.model, payload, engine.budget)
        self.model['measures'].append({'TableName': 'M', 'Name': 'Modified', 'Expression': 'CALCULATE(SUM(F[Revenue]),ALL(F))'})
        with self.assertRaises(UnsupportedSql):
            self.evaluate(self.payload(['Modified']))

    def test_relation_cleanup_and_budget(self):
        self.evaluate(self.payload(['Revenue']))
        remaining = self.con.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '__group_scan_%'").fetchall()
        self.assertEqual(remaining, [])
        engine = Evaluator(self.con, self.model, filters=[])
        engine.budget['deadline'] = time.monotonic() - 1
        with self.assertRaisesRegex(RuntimeError, 'time limit'):
            evaluate_grouped(self.con, self.model, self.payload(['Revenue']), engine.budget)

    def test_fact_internal_column_name_cannot_collide(self):
        self.con.execute('ALTER TABLE F ADD COLUMN __fact_row INTEGER DEFAULT 999')
        self.assertEqual(self.evaluate(self.payload(['Revenue', 'Count']))[0], ('A', 40, 3))

    def test_boolean_count_falls_back_but_counta_is_supported(self):
        self.con.execute('ALTER TABLE F ADD COLUMN Flag BOOLEAN DEFAULT TRUE')
        self.model['measures'].extend([{'Name': 'BooleanCount', 'TableName': 'M', 'Expression': 'COUNT(F[Flag])'}, {'Name': 'BooleanCountA', 'TableName': 'M', 'Expression': 'COUNTA(F[Flag])'}])
        with self.assertRaises(UnsupportedSql):
            self.evaluate(self.payload(['BooleanCount']))
        self.assertEqual(self.evaluate(self.payload(['BooleanCountA']))[0], ('A', 3))

    def test_strict_and_compound_row_comparisons_preserve_blank_identity(self):
        self.model['measures'].extend([
            {'Name': 'Strict', 'TableName': 'M', 'Expression': 'SUMX(FILTER(F,F[Revenue]==0),F[Popularity])'},
            {'Name': 'BothBlank', 'TableName': 'M', 'Expression': 'SUMX(FILTER(F,ISBLANK(F[Revenue]+F[Budget])),F[Popularity])'},
        ])
        self.con.execute('ALTER TABLE F ALTER COLUMN Popularity TYPE DOUBLE')
        self.con.execute('INSERT INTO F VALUES (9,NULL,NULL,100),(10,0,0,2),(11,10,10,50)')
        self.con.execute('INSERT INTO Bridge VALUES (9,10),(10,10),(11,10)')
        payload = self.payload(['Strict', 'BothBlank'], values=('A',))
        engine = Evaluator(self.con, self.model, filters=[])
        actual = evaluate_groups(self.con, self.model, payload, engine.budget)
        self.assertEqual(actual, [('A', 2, 100)])
        self.compare(payload)

    def test_weak_comparisons_coalesce_nested_numeric_expressions(self):
        self.con.execute('ALTER TABLE F ALTER COLUMN Popularity TYPE DOUBLE')
        self.con.execute('DELETE FROM F')
        self.con.execute('INSERT INTO F VALUES (1,NULL,2,100),(2,0,1,2),(3,10,10,50)')
        self.con.execute('DELETE FROM Bridge')
        self.con.execute('INSERT INTO Bridge VALUES (1,10),(2,10),(3,10)')
        self.model['measures'].extend([
            {'Name': 'WeakProduct', 'TableName': 'M', 'Expression': 'SUMX(FILTER(F,F[Revenue]*F[Budget]=0),F[Popularity])'},
            {'Name': 'WeakDivide', 'TableName': 'M', 'Expression': 'SUMX(FILTER(F,DIVIDE(F[Revenue],0)=0),F[Popularity])'},
        ])
        payload = self.payload(['WeakProduct', 'WeakDivide'], values=('A',))
        engine = Evaluator(self.con, self.model, filters=[])
        self.assertEqual(evaluate_groups(self.con, self.model, payload, engine.budget), [('A', 102, 152)])
        self.compare(payload)

    def test_relation_removed_when_external_source_building_fails(self):
        with patch('dax_grouped.SqlDax.source', side_effect=UnsupportedSql('test source failure')):
            with self.assertRaises(UnsupportedSql):
                self.evaluate(self.payload(['Revenue']))
        self.assertEqual(self.con.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '__group_scan_%'").fetchall(), [])

    def test_disconnected_parameter_selects_only_its_authored_cohort(self):
        self.con.execute("ALTER TABLE F ADD COLUMN Status VARCHAR DEFAULT 'Normal'")
        self.con.execute("UPDATE F SET Status='Outlier' WHERE ID=2")
        self.con.execute("CREATE TABLE Choices AS SELECT * FROM (VALUES ('Include'),('Exclude'),('Only')) c(Choice)")
        self.model['tables'].append({'name': 'Choices'})
        for name, expression in (
            ('SelectedRevenue', 'SWITCH(SELECTEDVALUE(Choices[Choice]),"Exclude",CALCULATE(SUM(F[Revenue]),F[Status]="Normal"),"Only",CALCULATE(SUM(F[Revenue]),F[Status]="Outlier"),"Include",SUM(F[Revenue]))'),
            ('SelectedMedian', 'COALESCE(SWITCH(SELECTEDVALUE(Choices[Choice]),"Exclude",CALCULATE(MEDIAN(F[Popularity]),F[Status]="Normal"),"Only",CALCULATE(MEDIAN(F[Popularity]),F[Status]="Outlier"),"Include",MEDIAN(F[Popularity])),BLANK())'),
            ('SelectedDistinct', 'SWITCH(SELECTEDVALUE(Choices[Choice]),"Exclude",CALCULATE(DISTINCTCOUNT(F[Popularity]),F[Status]="Normal"),"Only",CALCULATE(DISTINCTCOUNT(F[Popularity]),F[Status]="Outlier"),"Include",DISTINCTCOUNT(F[Popularity]))'),
        ):
            self.model['measures'].append({'TableName': 'M', 'Name': name, 'Expression': expression})
        for choice, revenue, median in (('Include', 40, 3), ('Exclude', 20, 3), ('Only', 20, 9)):
            filters = [{'table': 'Choices', 'columns': ['Choice'], 'sql': '"Choices"."Choice"=\'' + choice + '\''}]
            with self.subTest(choice=choice):
                result = self.compare(self.payload(['SelectedRevenue', 'SelectedMedian', 'SelectedDistinct'], external=filters))
                self.assertEqual(result[0][1:3], (revenue, median))
        # A group-dependent selector cannot become a global constant; external
        # filters overwritten by CALCULATE require the more general evaluator.
        self.model['measures'].append({'TableName': 'M', 'Name': 'DynamicChoice', 'Expression': 'SWITCH(SELECTEDVALUE(D[Category]),"A",SUM(F[Revenue]),SUM(F[Budget]))'})
        with self.assertRaises(UnsupportedSql):
            self.evaluate(self.payload(['DynamicChoice']))
        filters = [{'table': 'Choices', 'columns': ['Choice'], 'sql': '"Choices"."Choice"=\'Exclude\''}, {'table': 'F', 'columns': ['Status'], 'sql': '"F"."Status"=\'Outlier\''}]
        with self.assertRaises(UnsupportedSql):
            self.evaluate(self.payload(['SelectedRevenue'], external=filters))

    def test_constant_folding_keeps_unchosen_errors_lazy(self):
        self.model['measures'].extend([
            {'TableName': 'M', 'Name': 'LazyFixed', 'Expression': 'IF(1=1,SUM(F[Revenue]),1/0)'},
            {'TableName': 'M', 'Name': 'LazyDynamic', 'Expression': 'IF(SUM(F[Revenue])>0,SUM(F[Revenue]),1/0)'},
        ])
        self.assertEqual(self.compare(self.payload(['LazyFixed'], values=('A',)))[0][1], 40)
        engine=Evaluator(self.con,self.model,filters=[])
        self.assertEqual(evaluate_groups(self.con,self.model,self.payload(['LazyDynamic'],values=('A',)),engine.budget),[('A',40)])
        with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql),patch('dax_sql.evaluate_expression',side_effect=UnsupportedSql):
            engine=Evaluator(self.con,self.model,filters=[{'table':'D','columns':['Category'],'sql':'"D"."Category" = \'Missing\''}])
            with self.assertRaises(ZeroDivisionError):engine.measure('LazyDynamic','M')


if __name__ == '__main__':
    unittest.main()
