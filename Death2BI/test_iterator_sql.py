import unittest
from unittest.mock import patch
import duckdb
from dax_engine import Evaluator, Parser, evaluate_visual
from dax_sql import evaluate_scalar, UnsupportedSql


class IteratorSqlTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("CREATE TABLE T AS SELECT * FROM (VALUES ('A',1,2.),('B',2,8.),('C',9,NULL)) t(Label,K,N)")
        self.con.execute("CREATE TABLE D AS SELECT * FROM (VALUES (1,'one'),(2,'two')) t(K,Description)")
        self.model = {'tables': [{'name': 'T'}, {'name': 'D'}], 'relationships': [
            {'IsActive': True, 'Cardinality': 'M:1', 'FromTableName': 'T', 'FromColumnName': 'K', 'ToTableName': 'D', 'ToColumnName': 'K', 'CrossFilteringBehavior': 'Single'}], 'measures': [
            {'Name': 'Threshold', 'TableName': 'M', 'Expression': 'CALCULATE(AVERAGE(T[N]),ALL(T),T[N]>0)'},
            {'Name': 'Good', 'TableName': 'M', 'Expression': 'SUMX(FILTER(T,T[N]>=[Threshold]),1)'},
            {'Name': 'Amount', 'TableName': 'M', 'Expression': 'SUM(T[N])'},
            {'Name': 'DimensionRows', 'TableName': 'M', 'Expression': 'COUNTROWS(D)'}]}

    def tearDown(self):
        self.con.close()

    def engine(self):
        return Evaluator(self.con, self.model, filters=[])

    def reference(self, expression):
        with patch('dax_sql.evaluate_scalar', side_effect=UnsupportedSql), patch('dax_sql.filter_rows', side_effect=UnsupportedSql), patch('dax_sql.add_columns', side_effect=UnsupportedSql):
            return self.engine().run(Parser(expression).parse())

    def test_invariant_threshold_and_ordered_calculate(self):
        self.assertEqual(evaluate_scalar(self.engine(), 'Good'), self.reference('[Good]'))
        self.assertEqual(evaluate_scalar(self.engine(), 'Threshold'), 5)

    def test_explicit_calculate_filter_arguments_before_row_transition(self):
        # Root CALCULATE must not get an extra implicit transition first.
        self.assertEqual(evaluate_scalar(self.engine(),'Good'),1)
        self.assertEqual(self.reference('[Good]'),1)

    def test_all_table_rowset_ignores_bridge_filters(self):
        self.con.execute("CREATE TABLE B AS SELECT * FROM (VALUES ('A','selected'),('B','other')) x(Label,Category)")
        self.model['tables'].append({'name':'B'})
        self.model['relationships'].append({'IsActive':True,'Cardinality':'M:M','FromTableName':'T','FromColumnName':'Label','ToTableName':'B','ToColumnName':'Label','CrossFilteringBehavior':'Both'})
        self.model['measures'].append({'Name':'AllAverage','TableName':'M','Expression':'AVERAGEX(FILTER(ALL(T),T[N]>0),T[N])'})
        filters=[{'table':'B','columns':['Category'],'sql':'"B"."Category"=\'selected\''}]
        e=Evaluator(self.con,self.model,filters=filters)
        self.assertEqual(evaluate_scalar(e,'AllAverage'),5)
        with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql):
            self.assertEqual(e.measure('AllAverage'),5)

    def test_literal_variables_and_keepfilters(self):
        self.model['measures'].append({'Name':'Kept','TableName':'M','Expression':'VAR cutoff=4 RETURN CALCULATE(SUM(T[N]),KEEPFILTERS(T[N]>=cutoff))'})
        self.assertEqual(evaluate_scalar(self.engine(),'Kept'),8)

    def test_filter_blank_coercion(self):
        for expression in ['COUNTROWS(FILTER(T,T[N]<3))', 'COUNTROWS(FILTER(T,[N]>=0))', 'COUNTROWS(FILTER(T,T[N]>=[Threshold]))']:
            self.assertEqual(self.engine().run(Parser(expression).parse()), self.reference(expression))

    def test_batched_expanded_context_including_missing_key(self):
        expression = 'ADDCOLUMNS(ALL(T[Label],T[K]),"Value",[Amount],"Dimension",[DimensionRows])'
        key=lambda r:r[1]['Label']
        self.assertEqual(sorted(self.engine().run(Parser(expression).parse()),key=key), sorted(self.reference(expression),key=key))

    def test_row_dependent_measure_does_not_hoist(self):
        self.model['measures'].append({'Name': 'Dependent', 'TableName': 'M', 'Expression': 'SUMX(FILTER(T,[Amount]>4),1)'})
        self.assertEqual(evaluate_scalar(self.engine(), 'Dependent'), 1)
        self.assertEqual(self.engine().measure('Dependent'), self.reference('[Dependent]'))

    def test_lookup_index_reused_and_duplicate_keys_rejected(self):
        e = self.engine()
        for n in range(3):
            e.transition(('T', {'K': 1}))
        self.assertEqual(len(e.budget['transition_indexes']), 1)
        self.con.execute("INSERT INTO D VALUES(1,'duplicate')")
        with self.assertRaisesRegex(ValueError, 'not unique'):
            self.engine().transition(('T', {'K': 1}))

    def test_calculate_domain_precedes_all_modifier(self):
        filters=[{'table':'T','columns':['Label'],'sql':'"T"."Label"=\'A\''}]
        e=Evaluator(self.con,self.model,filters=filters)
        self.assertEqual(evaluate_scalar(e,'Threshold'),5)

    def test_duplicate_row_identifiers_and_bare_aggregate(self):
        self.con.execute("INSERT INTO T VALUES ('D',1,9),('D',1,9)")
        self.assertEqual(evaluate_scalar(self.engine(),'Good'),self.reference('[Good]'))
        expression='ADDCOLUMNS(ALL(T[Label]),"Total",SUM(T[N]))'
        key=lambda r:r[1]['Label']
        self.assertEqual(sorted(self.engine().run(Parser(expression).parse()),key=key),sorted(self.reference(expression),key=key))

    def test_grouped_threshold_materialization(self):
        col=lambda name:{'Column':{'Expression':{'SourceRef':{'Entity':'T'}},'Property':name}}
        payload={'fields':[col('Label'),{'Measure':{'Property':'Threshold','Expression':{'SourceRef':{'Entity':'M'}}}}], 'baseFilters':[], 'groups':[
            {'values':{'0':label},'scope':[['T','Label']], 'filters':[{'table':'T','columns':['Label'],'sql':'"T"."Label" = \''+label+'\''}]} for label in ['A','B','C']]}
        result=evaluate_visual(self.con,self.model,payload)
        self.assertEqual([list(r) for r in result['rows']],[['A',5],['B',5],['C',5]])

    def test_staged_extension_filter_matches_eager_results(self):
        expression='FILTER(ADDCOLUMNS(ALL(T[Label]),"@A",[Amount],"@B",[Amount]),[@A]>4 && [@B]>0)'
        result=self.engine().run(Parser(expression).parse())
        with patch('dax_tables.filtered_extensions',side_effect=UnsupportedSql):
            expected=self.reference(expression)
        self.assertEqual(result,expected)

    def test_large_arrow_group_domain(self):
        self.con.execute('CREATE TABLE U AS SELECT i AS ID, i*2 AS N FROM range(1100) r(i)')
        self.model['tables'].append({'name':'U'})
        self.model['measures'].append({'Name':'UAmount','TableName':'M','Expression':'SUM(U[N])'})
        rows=self.engine().run(Parser('ADDCOLUMNS(ALL(U[ID]),"Amount",[UAmount])').parse())
        self.assertEqual(len(rows),1100)
        self.assertTrue(all(r[1]['Amount']==r[1]['ID']*2 for r in rows))
        self.assertFalse(any(r[0].startswith('__dax_groups_') for r in self.con.execute('SHOW TABLES').fetchall()))


if __name__ == '__main__':
    unittest.main()
