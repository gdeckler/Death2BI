import unittest
from unittest.mock import patch
import duckdb
from dax_engine import Evaluator, Parser
from dax_sql import evaluate_scalar, UnsupportedSql


class CalculationMemoTests(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect()
        self.con.execute('CREATE TABLE T AS SELECT * FROM (VALUES (1,2),(2,8),(3,4)) t(Y,N)')
        self.model={'tables':[{'name':'T'}],'relationships':[],'measures':[
            {'Name':'Amount','TableName':'M','Expression':'SUM(T[N])'},
            {'Name':'Peak','TableName':'M','Expression':'CALCULATE(MAXX(VALUES(T[Y]),[Amount]),ALLSELECTED(T[Y]))'}]}
    def tearDown(self):self.con.close()
    def test_selected_extremum_reused_across_categories(self):
        root=Evaluator(self.con,self.model,filters=[])
        for year in (1,2,3):
            e=root.child([root.value_filter([('T','Y')],[[year]])]);e.external_filters=[]
            self.assertEqual(e.measure('Peak'),8)
        self.assertGreaterEqual(root.budget.get('calculation_cache_hits',0),2)
        e=root.child([]);e.external_filters=[root.value_filter([('T','Y')],[[1],[3]])]
        self.assertEqual(e.measure('Peak'),4)
    def test_lexical_variables_and_blank(self):
        e=Evaluator(self.con,self.model,filters=[])
        node=Parser('CALCULATE(x)').parse()
        self.assertEqual([e.run(node,{'x':v}) for v in (2,8,None,None)], [2,8,None,None])
        self.assertGreaterEqual(e.budget.get('calculation_cache_hits',0),1)
    def test_volatile_dependency_not_cached(self):
        self.model['measures'].append({'Name':'Unstable','TableName':'M','Expression':'NOW()'})
        e=Evaluator(self.con,self.model,filters=[])
        node=Parser('CALCULATE([Unstable])').parse()
        e.run(node);e.run(node)
        self.assertEqual(len(e.budget.get('calculation_values',{})),0)
    def test_not_equal_sql_blank_and_case_semantics(self):
        self.con.execute("CREATE TABLE S AS SELECT * FROM (VALUES ('en',1),('EN',2),('es',3),(NULL,4)) t(L,N)")
        self.model['tables'].append({'name':'S'})
        for predicate,expected in [('S[L]<>"en"',7),('S[L]<>""',6),('S[N]<>2',8)]:
            measure={'Name':'Result','TableName':'M','Expression':f'CALCULATE(SUM(S[N]),{predicate})'}
            self.model['measures']=[measure]
            e=Evaluator(self.con,self.model,filters=[])
            self.assertEqual(evaluate_scalar(e,'Result'),expected)
            with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql),patch('dax_sql.filter_rows',side_effect=UnsupportedSql):
                self.assertEqual(Evaluator(self.con,self.model,filters=[]).measure('Result'),expected)

if __name__=='__main__':unittest.main()
