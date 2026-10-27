"""Fast iterator scoring must agree with the existing bounded interpreter."""
import unittest
from decimal import Decimal
from unittest.mock import patch
import duckdb
from dax_engine import Evaluator,Parser
from dax_sql import UnsupportedSql


class RowsetIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect(config={'threads':1})
        self.con.execute("CREATE TABLE T AS SELECT * FROM (VALUES (1,2.0,'a'),(2,8.0,'B'),(3,8.0,'b'),(4,NULL,'c')) t(K,N,Label)")
        self.con.execute('CREATE TABLE P AS SELECT * FROM (VALUES (0.0),(0.5),(1.0)) t(Weight)')
        self.model={'tables':[{'name':'T'},{'name':'P'}],'relationships':[],'measures':[
            {'Name':'Score','TableName':'T','Expression':'VAR w=SELECTEDVALUE(P[Weight],0.5) RETURN SELECTEDVALUE(T[N])*w'},
            {'Name':'Unused','TableName':'T','Expression':'RAND()'}]}
    def tearDown(self):self.con.close()

    def run_both(self,expression,filters=None):
        node=Parser(expression).parse()
        fast=Evaluator(self.con,self.model,filters=filters or []);fast.external_filters=filters or []
        result=fast.run(node)
        with patch('dax_rowset.evaluate_rows',side_effect=UnsupportedSql('reference interpreter')):
            slow=Evaluator(self.con,self.model,filters=filters or []);slow.external_filters=filters or []
            expected=slow.run(node)
        self.assertEqual(result,expected)
        return result,fast.budget

    def test_filter_topn_ties_and_parameter_context(self):
        expression='CONCATENATEX(TOPN(1,FILTER(ALLSELECTED(T),NOT ISBLANK([Score])),[Score],DESC),T[K],",",T[K],ASC)'
        result,budget=self.run_both(expression);self.assertEqual(result,'2,3')
        zero=[{'table':'P','columns':['Weight'],'sql':'"P"."Weight"=0'}]
        self.assertEqual(self.run_both(expression,zero)[0],'1,2,3')
        self.con.execute('DELETE FROM T WHERE K=2')
        self.assertEqual(self.run_both(expression)[0],'3')

    def test_virtual_full_lineage_and_disconnected_outer_row(self):
        expression='VAR Rows=ADDCOLUMNS(T,"Extra",[Score]) VAR Domains={1,2} RETURN CONCATENATEX(Domains,VAR wanted=[Value] VAR Part=FILTER(Rows,T[K]=wanted) RETURN CONCATENATEX(TOPN(1,Part,[Score],DESC),T[Label],""),"|")'
        self.assertEqual(self.run_both(expression)[0],'a|B')

    def test_filter_context_and_bare_selectedvalue_are_distinct(self):
        expression='COUNTROWS(FILTER(T,ISBLANK(SELECTEDVALUE(T[N]))))'
        self.assertEqual(self.run_both(expression)[0],4)
        expression='CONCATENATEX(TOPN(1,T,[Score],DESC,T[K],ASC),T[K],",")'
        filtered=[{'table':'T','columns':['K'],'sql':'"T"."K" IN (1,4)'}]
        self.assertEqual(self.run_both(expression,filtered)[0],'1')

    def test_fetched_float_context_transition_retains_its_original_row(self):
        self.con.execute('ALTER TABLE T ADD COLUMN Precise DOUBLE')
        self.con.execute('UPDATE T SET Precise=? WHERE K=2',[0.9995651464912757])
        self.model['measures'].append({'Name':'Selected','TableName':'T','Expression':'SELECTEDVALUE(T[K])'})
        e=Evaluator(self.con,self.model,filters=[]);row=next(r for r in e.table('T') if r[1]['K']==2)
        self.assertEqual(e.measure('Selected',row=row),2)
        from decimal import Decimal
        from dax_core import sv
        self.assertEqual(self.con.execute('SELECT '+sv(Decimal('0.35'))).fetchone()[0],Decimal('0.35'))

    def test_browser_float_groups_keep_batched_plan_and_exact_identity(self):
        from dax_sql import evaluate_groups
        value=0.9995651464912757
        self.con.execute('ALTER TABLE T ADD COLUMN Precise DOUBLE');self.con.execute('UPDATE T SET Precise=? WHERE K=2',[value])
        self.model['measures'].append({'Name':'Amount','TableName':'T','Expression':'SUM(T[N])'})
        field={'Column':{'Expression':{'SourceRef':{'Entity':'T'}},'Property':'Precise'}}
        measure={'Measure':{'Expression':{'SourceRef':{'Entity':'T'}},'Property':'Amount'}}
        group={'values':{'0':value},'filters':[{'table':'T','columns':['Precise'],'sql':'"T"."Precise" = '+str(value)}],'externalFilters':[],'scope':[['T','Precise']]}
        budget=Evaluator(self.con,self.model,filters=[]).budget
        self.assertEqual(evaluate_groups(self.con,self.model,{'groups':[group],'fields':[field,measure]},budget),[(value,Decimal('8.0'))])

    def test_rank_keeps_outer_virtual_columns_that_shadow_a_measure(self):
        node=Parser('RANKX(domain,[Score],99,ASC)').parse()
        def result():
            e=Evaluator(self.con,self.model,filters=[])
            e.row_stack=[('__virtual',{'K':1,'Score':99},{('T','K'):1})]
            return e.run(node,{'domain':e.table('T')})
        self.assertEqual(result(),1)
        with patch('dax_rowset.evaluate_rows',side_effect=UnsupportedSql('reference')):self.assertEqual(result(),1)

    def test_legacy_contexts_are_not_silently_discarded(self):
        e=Evaluator(self.con,self.model,{'P':'"Weight"=0.5'})
        row=e.table('T')[0]
        with self.assertRaisesRegex(ValueError,'structured filters'):e.measure('Score',row=row)


if __name__=='__main__':unittest.main()
