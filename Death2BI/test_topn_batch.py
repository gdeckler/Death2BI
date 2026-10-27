import unittest
from unittest.mock import patch
import duckdb
from dax_engine import Evaluator, evaluate_topn
from dax_sql import evaluate_scalar, evaluate_groups, UnsupportedSql
from dax_core import Parser


class TopNBatchTests(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect();self.addCleanup(self.con.close)
        self.con.execute('CREATE TABLE T AS SELECT i ID, i*2.0 N, i%2 K, i%3<>0 Reliable FROM range(2100) r(i)')
        self.con.execute('CREATE TABLE Choice AS SELECT * FROM (VALUES (0),(1),(2)) r(Choice)')
        self.con.execute('CREATE TABLE D AS SELECT * FROM (VALUES (0),(1)) r(K)')
        self.model={'tables':[{'name':t} for t in ('T','Choice','D')], 'relationships':[{'FromTableName':'T','FromColumnName':'K','ToTableName':'D','ToColumnName':'K','IsActive':True,'Cardinality':'M:1','CrossFilteringBehavior':'Single'}], 'measures':[
            {'TableName':'M','Name':'Score','Expression':'VAR choice=SELECTEDVALUE(Choice[Choice]) RETURN SWITCH(choice,0,CALCULATE(AVERAGE(T[N]),T[Reliable],CROSSFILTER(T[K],D[K],Both)),1,MEDIANX(CALCULATETABLE(FILTER(T,T[Reliable]),CROSSFILTER(T[K],D[K],Both)),DIVIDE(T[N],2)),2,CONCATENATEX(T,T[N]))'},
            {'TableName':'M','Name':'Related','Expression':'VAR choice=SELECTEDVALUE(T[K]) RETURN SWITCH(choice,0,10,1,20)'},
            {'TableName':'M','Name':'Both','Expression':'CALCULATE(COUNTROWS(D),CROSSFILTER(T[K],D[K],Both))'},
            {'TableName':'M','Name':'None','Expression':'CALCULATE(COUNTROWS(T),CROSSFILTER(T[K],D[K],None))'},
        ]}
        self.payload={'category':{'Column':{'Expression':{'SourceRef':{'Entity':'T'}},'Property':'ID'}},'by':{'Measure':{'Expression':{'SourceRef':{'Entity':'M'}},'Property':'Score'}},'count':3,'descending':True,'filters':[]}

    def test_entire_domain_uses_one_batch_and_prunes_unused_branches(self):
        for selection in (0,1,None):
            self.payload['filters']=[] if selection is None else [{'table':'Choice','columns':['Choice'],'sql':'"Choice"."Choice"='+str(selection)}]
            with patch('dax_engine.Evaluator.measure',side_effect=AssertionError('Unexpected per-category evaluation')),patch('dax_sql.evaluate_groups',wraps=evaluate_groups) as batched:
                result=evaluate_topn(self.con,self.model,self.payload)
                self.assertEqual(batched.call_count,1)
                self.assertEqual(set(result['values']),set() if selection is None else {2099,2098,2096})
            self.assertFalse(self.con.execute("SELECT table_name FROM duckdb_tables() WHERE temporary AND table_name LIKE '__dax_groups_%'").fetchall())

    def test_category_dependent_selection_is_not_folded_globally(self):
        self.payload['by']['Measure']['Property']='Related'
        result=evaluate_topn(self.con,self.model,self.payload)
        self.assertEqual(len(result['values']),1050)  # TOPN includes ties.
        self.assertTrue(all(i%2==1 for i in result['values']))

    def test_median_lowering_preserves_blanks_and_rejects_text(self):
        from dax_sql import evaluate_expression
        self.con.execute("CREATE TABLE Numbers(N DOUBLE,Label VARCHAR); INSERT INTO Numbers VALUES(NULL,'a'),(2,'b'),(4,'c')")
        self.model['tables'].append({'name':'Numbers'})
        expr=Parser('MEDIANX(FILTER(Numbers,TRUE()),Numbers[N])').parse()
        e=Evaluator(self.con,self.model,filters=[])
        self.assertEqual(evaluate_expression(e,expr),e.run(expr))
        self.assertEqual(evaluate_expression(e,Parser('MEDIANX(Numbers,Numbers[N])').parse()),2)
        self.assertEqual(evaluate_expression(e,Parser('MEDIANX(FILTER(Numbers,ISBLANK(Numbers[N])),Numbers[N])').parse()),0)
        self.assertIsNone(evaluate_expression(e,Parser('MEDIANX(FILTER(Numbers,FALSE()),Numbers[N])').parse()))
        with self.assertRaises(UnsupportedSql):evaluate_expression(e,Parser('MEDIANX(FILTER(Numbers,TRUE()),Numbers[Label])').parse())

    def test_relationship_modifiers_match_interpreter_and_secured_domain(self):
        for name,filters,expected in [('Both',[{'table':'T','columns':['ID'],'sql':'"T"."ID"=1'}],1),('None',[{'table':'D','columns':['K'],'sql':'"D"."K"=1'}],2100)]:
            engine=Evaluator(self.con,self.model,filters=filters);engine.external_filters=filters
            self.assertEqual(evaluate_scalar(engine,name,'M'),expected)
            with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql):self.assertEqual(Evaluator(self.con,self.model,filters=filters).measure(name,'M'),expected)
        self.con.execute('CREATE OR REPLACE VIEW Secured AS SELECT * FROM T WHERE ID<10')
        self.model['tables'].append({'name':'Secured'})
        self.model['measures'].append({'TableName':'M','Name':'SecuredScore','Expression':'SUM(Secured[N])'})
        self.payload['category']['Column']['Expression']['SourceRef']['Entity']='Secured'
        self.payload['by']['Measure']['Property']='SecuredScore'
        self.assertEqual(set(evaluate_topn(self.con,self.model,self.payload)['values']),{7,8,9})


if __name__=='__main__':unittest.main()
