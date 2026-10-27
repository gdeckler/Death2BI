"""Unsafe correlated groups stage through the same secured bounded evaluator."""
import unittest
from unittest.mock import patch

import duckdb

from dax_engine import Evaluator, evaluate_visual
from dax_sql import UnsupportedSql, evaluate_scalar


class ConnectionSpy:
    def __init__(self,con):self.con=con;self.statements=[]
    def execute(self,sql,*args,**kwargs):
        self.statements.append(sql)
        if '__dax' in sql and 'Calendar' in sql:
            raise AssertionError('Unsafe correlated calendar/group SQL reached native execution')
        return self.con.execute(sql,*args,**kwargs)
    def __getattr__(self,key):return getattr(self.con,key)


class GroupedSqlSafetyTests(unittest.TestCase):
    def setUp(self):
        con=duckdb.connect(config={'threads':1})
        con.execute("CREATE TABLE People AS SELECT * FROM (VALUES (1,'A'),(2,'B'),(3,'C')) p(ID,Name)")
        con.execute('CREATE TABLE Calendar AS SELECT * FROM (VALUES (1,8.),(2,8.),(3,8.)) c(Day,WorkHours)')
        con.execute("CREATE TABLE Hours AS SELECT * FROM (VALUES (1,1,'Billable','Allowed',6.),(1,2,'Billable','Allowed',2.),(1,2,'Other','Allowed',2.),(2,1,'Billable','Allowed',10.),(3,3,'Billable','Excluded',6.)) h(PersonID,Day,Category,Division,Amount)")
        self.con=ConnectionSpy(con)
        self.model={'tables':[{'name':name} for name in ('People','Calendar','Hours')],'relationships':[
            {'IsActive':True,'Cardinality':'M:1','CrossFilteringBehavior':'Both','FromTableName':'Hours','FromColumnName':'PersonID','ToTableName':'People','ToColumnName':'ID'},
            {'IsActive':True,'Cardinality':'M:1','CrossFilteringBehavior':'Both','FromTableName':'Hours','FromColumnName':'Day','ToTableName':'Calendar','ToColumnName':'Day'},
        ],'measures':[
            {'TableName':'M','Name':'Billable','Expression':'SUMX(FILTER(Hours,Hours[Category]="Billable"),Hours[Amount])'},
            {'TableName':'M','Name':'Work Hours','Expression':'SUM(Calendar[WorkHours])'},
            {'TableName':'M','Name':'Total Hours','Expression':'VAR PerPerson=SUMMARIZE(People,People[Name],"@Hours",[Work Hours]) RETURN SUMX(PerPerson,[@Hours])'},
            {'TableName':'M','Name':'Utilization','Expression':'DIVIDE([Billable],[Total Hours])'},
            {'TableName':'M','Name':'Nested Total','Expression':'SUMX(SUMMARIZE(People,People[Name],"@Total",[Total Hours]),[@Total])'},
            {'TableName':'M','Name':'Simple Total','Expression':'SUMX(SUMMARIZE(People,People[Name],"@Billable",[Billable]),[@Billable])'},
            {'TableName':'M','Name':'Status','Expression':'IF([Utilization]>=0.8,"green","red")'},
        ]}
        self.filters=[{'table':'Hours','columns':['Division'],'sql':'"Hours"."Division"=\'Allowed\''}]

    def tearDown(self):self.con.close()

    def engine(self,filters=None):return Evaluator(self.con,self.model,filters=self.filters if filters is None else filters)

    def payload(self):
        fields=[{'Column':{'Expression':{'SourceRef':{'Entity':'People'}},'Property':'Name'}}]
        fields.extend({'Measure':{'Expression':{'SourceRef':{'Entity':'M'}},'Property':name}} for name in ('Utilization','Status'))
        groups=[{'values':{'0':name},'scope':[['People','Name']],'filters':[{'table':'People','columns':['Name'],'sql':'"People"."Name" = \''+name+'\''}]} for name in ('A','B','C')]
        return {'fields':fields,'baseFilters':self.filters,'groups':groups}

    def test_nested_and_multihop_group_plans_decline_before_native_execution(self):
        for name,reason in [('Total Hours','multiple relationship hops'),('Nested Total','nested grouped iterator')]:
            engine=self.engine()
            with self.subTest(name=name),self.assertRaisesRegex(UnsupportedSql,reason):evaluate_scalar(engine,name,'M')
            self.assertGreater(engine.budget['sqlSafetyFallbacks'],0)
            self.assertTrue(any(reason in item for item in engine.budget['sqlSafetyReasons']))
        self.assertFalse(any('__dax' in sql and 'Calendar' in sql for sql in self.con.statements))

    def test_grouped_visual_matches_interpreter_and_independent_physical_truth(self):
        payload=self.payload()
        actual=evaluate_visual(self.con,self.model,payload)
        with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql),patch('dax_sql.evaluate_groups',side_effect=UnsupportedSql):
            expected=evaluate_visual(self.con,self.model,payload)
        self.assertEqual(actual['rows'],expected['rows'])
        rows={r[0]:r[1:] for r in actual['rows']}
        # A's 8 billable hours cover two 8-hour dates; B has 10 on one date.
        physical=self.con.execute("SELECT SUM(WorkHours) FROM Calendar c WHERE EXISTS (SELECT 1 FROM Hours h JOIN People p ON p.ID=h.PersonID WHERE p.Name='A' AND h.Division='Allowed' AND h.Day=c.Day)").fetchone()[0]
        self.assertEqual(physical,16)
        self.assertEqual(rows,{'A':[0.5,'red'],'B':[1.25,'green'],'C':[None,'red']})

    def test_one_hop_grouped_fact_aggregates_keep_the_sql_fast_path(self):
        engine=self.engine()
        self.assertEqual(evaluate_scalar(engine,'Simple Total','M'),18)
        self.assertEqual(engine.budget.get('sqlSafetyFallbacks',0),0)

    def test_unqualified_aggregate_columns_use_each_measure_home_table(self):
        # An extension's referenced measure has a different home table from
        # the outer measure. Its unqualified physical column must stay guarded.
        work=next(m for m in self.model['measures'] if m['Name']=='Work Hours')
        work.update(TableName='Calendar',Expression='SUM([WorkHours])')
        engine=self.engine()
        with self.assertRaisesRegex(UnsupportedSql,'multiple relationship hops'):evaluate_scalar(engine,'Total Hours','M')
        self.assertEqual(engine.measure('Total Hours','M'),24)
        self.assertEqual({r[0]:r[1] for r in evaluate_visual(self.con,self.model,self.payload())['rows']},{'A':0.5,'B':1.25,'C':None})
        # The same rule applies to an aggregate written directly in the
        # SUMMARIZE extension, without an intervening measure reference.
        self.model['measures'].append({'TableName':'Calendar','Name':'Direct Group Capacity','Expression':'SUMX(SUMMARIZE(People,People[Name],"@Hours",SUM([WorkHours])),[@Hours])'})
        with self.assertRaisesRegex(UnsupportedSql,'multiple relationship hops'):evaluate_scalar(self.engine(),'Direct Group Capacity','Calendar')

    def test_secured_view_survives_fallback_and_removefilters(self):
        self.con.execute('ALTER TABLE Calendar RENAME TO private_calendar')
        self.con.execute('CREATE VIEW Calendar AS SELECT * FROM private_calendar WHERE Day=1')
        self.model['measures'].append({'TableName':'M','Name':'All Calendar','Expression':'CALCULATE([Total Hours],REMOVEFILTERS(Calendar))'})
        engine=self.engine()
        self.assertEqual(engine.measure('All Calendar','M'),16)
        self.assertGreater(engine.budget['sqlSafetyFallbacks'],0)
        result=evaluate_visual(self.con,self.model,self.payload())
        self.assertEqual({r[0]:r[1] for r in result['rows']},{'A':1.0,'B':1.25,'C':None})

    def test_dependency_inspection_consumes_the_existing_budget(self):
        engine=self.engine();engine.budget['max_steps']=1
        with self.assertRaisesRegex(RuntimeError,'step limit'):evaluate_scalar(engine,'Nested Total','M')


if __name__=='__main__':unittest.main()
