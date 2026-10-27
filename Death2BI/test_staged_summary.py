"""Staged groups preserve contexts while replacing repeated physical scans."""
import time
import unittest
from unittest.mock import patch

import duckdb

from dax_core import Parser
from dax_engine import Evaluator
from dax_runtime import Table
from dax_sql import UnsupportedSql


class Connection:
    def __init__(self,con):self.con=con;self.statements=[]
    def execute(self,sql,*args,**kwargs):
        self.statements.append(sql)
        return self.con.execute(sql,*args,**kwargs)
    def __getattr__(self,name):return getattr(self.con,name)


class StagedSummaryTests(unittest.TestCase):
    def setUp(self):
        self.con=Connection(duckdb.connect(config={'threads':1}))
        self.con.execute("CREATE TABLE People AS SELECT * FROM (VALUES (1,'A','SALARY'),(2,'B','HOURLY'),(3,'C','SUB-CONTRACTOR'),(4,'None','SALARY'),(5,NULL,'SALARY'),(6,'A','HOURLY')) p(ID,Name,EmployeeType)")
        self.con.execute('CREATE TABLE Calendar AS SELECT * FROM (VALUES (1,8),(2,8),(3,0)) c(Day,WorkHours)')
        self.con.execute("CREATE TABLE Hours AS SELECT * FROM (VALUES (1,1,'Billable','Allowed',6.),(1,2,'Billable','Allowed',2.),(1,2,'Other','Allowed',2.),(2,1,'Billable','Allowed',10.),(3,3,'Billable','Excluded',6.),(5,1,'Billable','Allowed',3.),(6,1,'Billable','Allowed',1.)) h(PersonID,Day,Category,Division,Amount)")
        self.con.execute('ALTER TABLE Hours ALTER COLUMN Amount TYPE DECIMAL(18,2)')
        self.model={'tables':[{'name':t} for t in ('People','Calendar','Hours')],'relationships':[
            {'IsActive':True,'Cardinality':'M:1','CrossFilteringBehavior':'Both','FromTableName':'Hours','FromColumnName':'PersonID','ToTableName':'People','ToColumnName':'ID'},
            {'IsActive':True,'Cardinality':'M:1','CrossFilteringBehavior':'Both','FromTableName':'Hours','FromColumnName':'Day','ToTableName':'Calendar','ToColumnName':'Day'},
        ],'measures':[
            {'TableName':'M','Name':'Billable','Expression':'VAR Rows=FILTER(Hours,Hours[Category]="Billable") RETURN SUMX(Rows,[Amount])'},
            {'TableName':'M','Name':'Capacity','Expression':'SUM(Calendar[WorkHours])'},
            {'TableName':'M','Name':'Total','Expression':'VAR PerPerson=SUMMARIZE(People,People[Name],"@Hours",[Capacity]) RETURN SWITCH(MAX(People[EmployeeType]),"HOURLY",[Billable],"SUB-CONTRACTOR",[Billable],SUMX(PerPerson,[@Hours]))'},
        ]}
        self.expression='SUMMARIZE(People,People[Name],"Billed",[Billable],"Available",[Total],"Type",MAX(People[EmployeeType]))'
        self.filters=[{'table':'Hours','columns':['Division'],'sql':'"Hours"."Division"=\'Allowed\''}]

    def tearDown(self):self.con.close()

    def run_summary(self,expression=None,filters=None,enabled=True,model=None):
        engine=Evaluator(self.con,model or self.model,filters=self.filters if filters is None else filters)
        before=len(self.con.statements)
        if enabled:result=engine.run(Parser(expression or self.expression).parse(),{},None)
        else:
            with patch('dax_summary.extensions',side_effect=UnsupportedSql):result=engine.run(Parser(expression or self.expression).parse(),{},None)
        return result,engine,self.con.statements[before:]

    def compare(self,expression=None,filters=None,model=None):
        actual,engine,sql=self.run_summary(expression,filters,model=model)
        with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql),patch('dax_sql.filter_rows',side_effect=UnsupportedSql):
            expected,_,_=self.run_summary(expression,filters,enabled=False,model=model)
        self.assertEqual(actual,expected)
        self.assertEqual(actual.columns,expected.columns)
        return actual,engine,sql

    def test_nested_extensions_match_interpreter_and_independent_values(self):
        rows,engine,sql=self.compare()
        values={row[1]['Name']:(row[1]['Billed'],row[1]['Available'],row[1]['Type']) for row in rows}
        self.assertEqual(values,{'A':(9,16,'SALARY'),'B':(10,10,'HOURLY'),None:(3,8,'SALARY')})
        self.assertGreater(engine.budget.get('staged_summary_leaves',0),0)
        self.assertGreater(engine.budget.get('staged_summary_groups',0),0)
        self.assertGreater(engine.budget.get('sqlSafetyFallbacks',0),0)

    def test_context_changes_dates_blank_groups_and_duplicate_names(self):
        filters=[*self.filters,{'table':'Calendar','columns':['Day'],'sql':'"Calendar"."Day"=1'}]
        rows,_,_=self.compare(filters=filters)
        self.assertEqual({r[1]['Name']:r[1]['Available'] for r in rows},{'A':8,'B':10,None:8})
        rows,_,_=self.compare(filters=[])
        self.assertIn('None',{r[1]['Name'] for r in rows})
        self.assertIsNone(next(r[1]['Available'] for r in rows if r[1]['Name']=='None'))

    def test_secured_view_and_external_filters_are_not_bypassed(self):
        self.con.execute('ALTER TABLE Calendar RENAME TO private_calendar')
        self.con.execute('CREATE VIEW Calendar AS SELECT * FROM private_calendar WHERE Day=1')
        rows,_,_=self.compare()
        self.assertEqual({r[1]['Name']:r[1]['Available'] for r in rows},{'A':8,'B':10,None:8})

    def test_groups_keep_case_representative_null_and_output_order(self):
        self.con.execute("INSERT INTO People VALUES (7,'a','SALARY')")
        self.con.execute("INSERT INTO Hours VALUES (7,1,'Billable','Allowed',100)")
        rows,_,_=self.compare()
        self.assertEqual(next(r[1]['Billed'] for r in rows if r[1]['Name']=='A'),9)
        self.assertEqual([r[1]['Name'] for r in rows],['A','B',None])

    def test_text_filter_case_and_blank_semantics(self):
        self.con.execute("UPDATE Hours SET Category='bIlLaBlE' WHERE PersonID=2")
        self.con.execute("INSERT INTO Hours VALUES (2,1,NULL,'Allowed',50)")
        rows,_,_=self.compare()
        self.assertEqual(next(r[1]['Billed'] for r in rows if r[1]['Name']=='B'),10)
        self.model['measures'][0]['Expression']='SUMX(FILTER(Hours,Hours[Category]=""),Hours[Amount])'
        rows,_,_=self.compare()
        self.assertEqual(next(r[1]['Billed'] for r in rows if r[1]['Name']=='B'),50)
        self.con.execute("INSERT INTO Hours VALUES (2,1,'','Allowed',5)")
        self.model['measures'][0]['Expression']='SUMX(FILTER(Hours,Hours[Category]==""),Hours[Amount])'
        rows,_,_=self.compare()
        self.assertEqual(next(r[1]['Billed'] for r in rows if r[1]['Name']=='B'),5)
        self.model['measures'][0]['Expression']='SUMX(FILTER(Hours,Hours[Category]<>""),Hours[Amount])'
        rows,_,_=self.compare()
        self.assertEqual(next(r[1]['Billed'] for r in rows if r[1]['Name']=='B'),10)

    def test_request_cache_cannot_leak_into_another_context(self):
        first,_,_=self.run_summary()
        second,_,_=self.run_summary(filters=[*self.filters,{'table':'Calendar','columns':['Day'],'sql':'"Calendar"."Day"=2'}])
        self.assertEqual({r[1]['Name']:r[1]['Available'] for r in first}['A'],16)
        self.assertEqual({r[1]['Name']:r[1]['Available'] for r in second}, {'A':8})

    def test_dormant_error_or_volatile_dependencies_are_not_prefetched(self):
        self.model['measures'].extend([
            {'TableName':'M','Name':'Fail','Expression':'ERROR("must stay dormant")'},
            {'TableName':'M','Name':'Safe','Expression':'IF(FALSE(),[Fail],[Capacity])'},
        ])
        self.compare('SUMMARIZE(People,People[Name],"Value",[Safe])')
        self.model['measures'].append({'TableName':'Other','Name':'Capacity','Expression':'ERROR("ambiguous")'})
        self.compare('SUMMARIZE(People,People[Name],"Value",M[Capacity])')
        with self.assertRaisesRegex(ValueError,'Cannot resolve DAX measure Capacity'):
            self.run_summary('SUMMARIZE(People,People[Name],"Value",IF(TRUE(),M[Capacity],[Capacity]),"Ambiguous",[Capacity])')

    def test_dormant_invalid_source_dependency_or_column_is_not_resolved(self):
        self.model['measures'].append({'TableName':'M','Name':'Invalid Source','Expression':'UnsupportedUploadedFunction()'})
        self.model['measures'].append({'TableName':'M','Name':'Missing Column','Expression':'SUM(People[Missing])'})
        self.compare('SUMMARIZE(People,People[Name],"Value",IF(FALSE(),[Invalid Source],1))')
        self.compare('SUMMARIZE(People,People[Name],"Value",IF(FALSE(),People[Missing],1))')
        self.compare('SUMMARIZE(People,People[Name],"Value",IF(ISBLANK(BLANK()),1,[Invalid Source]))')
        self.compare('SUMMARIZE(People,People[Name],"Value",IF(ISBLANK(BLANK()),1,[Missing Column]))')
        with self.assertRaisesRegex(ValueError,'Unsupported DAX function'):
            self.run_summary('SUMMARIZE(People,People[Name],"Value",IF(ISBLANK(BLANK()),[Invalid Source],1))')

    def test_expanded_key_and_virtual_domains_decline_the_stage(self):
        rows,engine,_=self.compare('SUMMARIZE(Hours,Hours[PersonID],"Value",SUM(Hours[Amount]))')
        self.assertNotIn('staged_summary_groups',engine.budget)
        self.compare('SUMMARIZE(FILTER(People,People[ID]>0),People[Name],"Value",[Capacity])')

    def test_grouping_only_foreign_keys_never_transition_or_query_one_side(self):
        self.con.execute("INSERT INTO People VALUES (7,'a','SALARY')")
        self.con.execute("INSERT INTO Hours VALUES (7,1,'Billable','Allowed',100)")
        engine=Evaluator(self.con,self.model,filters=[])
        with patch.object(Evaluator,'transition',side_effect=AssertionError('A grouping domain does not perform context transition')):
            source=engine.run(Parser('SUMMARIZE(Hours,Hours[PersonID],Hours[Day])').parse(),{},None)
            names=engine.run(Parser('SUMMARIZE(People,People[Name])').parse(),{},None)
        self.assertEqual(source.columns,[('Hours','PersonID'),('Hours','Day')])
        self.assertEqual(source[0],('__summary',{'PersonID':1,'Day':1},{('Hours','PersonID'):1,('Hours','Day'):1}))
        self.assertEqual([r[1]['Name'] for r in names],['A','B','C','None',None])
        self.assertTrue(all(set(r[2])=={('People','Name')} for r in names))
        self.assertFalse(any('SELECT * FROM "People" WHERE' in sql for sql in self.con.statements))

    def test_large_grouping_only_domain_has_constant_query_count_and_full_lineage(self):
        self.con.execute('DELETE FROM Hours')
        self.con.execute("INSERT INTO Hours SELECT i,1,'Billable','Allowed',4 FROM range(1,5001) r(i)")
        engine=Evaluator(self.con,self.model,filters=[])
        before=len(self.con.statements)
        with patch.object(Evaluator,'transition',side_effect=AssertionError('Unexpected row transition')):
            result=engine.run(Parser('SUMMARIZE(Hours,Hours[PersonID],Hours[Day])').parse(),{},None)
        self.assertEqual(len(result),5000)
        self.assertEqual(result[-1][2],{('Hours','PersonID'):5000,('Hours','Day'):1})
        self.assertLessEqual(len(self.con.statements)-before,2)

    def test_many_groups_use_bounded_scans_and_cache_sizes(self):
        self.con.execute('DELETE FROM Hours');self.con.execute('DELETE FROM People')
        self.con.execute("INSERT INTO People SELECT i,'Person '||i,'SALARY' FROM range(1,161) r(i)")
        self.con.execute("INSERT INTO Hours SELECT i,1,'Billable','Allowed',4 FROM range(1,161) r(i)")
        rows,engine,sql=self.run_summary()
        self.assertEqual(len(rows),160)
        self.assertTrue(all(r[1]['Billed']==4 and r[1]['Available']==8 for r in rows))
        self.assertLess(len(sql),40)
        self.assertLessEqual(len(engine.budget['measure_values']),2000)
        self.assertLessEqual(len(engine.budget['projected_columns']),128)
        self.assertLessEqual(len(engine.budget['tables']),64)
        self.assertFalse(self.con.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '__group_scan_%'").fetchall())

    def test_budget_is_still_enforced(self):
        engine=Evaluator(self.con,self.model,filters=self.filters)
        engine.budget['deadline']=time.monotonic()-1
        with self.assertRaisesRegex(RuntimeError,'time limit'):
            engine.run(Parser(self.expression).parse(),{},None)

    def test_user_cancellation_is_not_swallowed_by_speculative_prefetch(self):
        with patch('dax_grouped.evaluate_context_rows',side_effect=duckdb.InterruptException('cancelled')):
            with self.assertRaises(duckdb.InterruptException):self.run_summary()

    def test_unicode_text_predicates_decline_without_seeding_incorrect_values(self):
        self.con.execute("UPDATE Hours SET Category='ß' WHERE PersonID=2")
        self.model['measures'][0]['Expression']='SUMX(FILTER(Hours,Hours[Category]="SS"),Hours[Amount])'
        # Force the existing generic SQL fallback away as well: its legacy
        # lower() behavior is outside this new fast path's eligibility proof.
        with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql),patch('dax_sql.filter_rows',side_effect=UnsupportedSql):
            rows,engine,_=self.compare()
        self.assertEqual(next(r[1]['Billed'] for r in rows if r[1]['Name']=='B'),10)
        self.assertIs(engine.budget['grouped_text_ascii']['Hours','Category'],False)
        # A non-ASCII literal also declines even when the source is ASCII.
        self.con.execute("UPDATE Hours SET Category='K' WHERE PersonID=2")
        self.model['measures'][0]['Expression']='SUMX(FILTER(Hours,Hours[Category]="K"),Hours[Amount])'
        with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql),patch('dax_sql.filter_rows',side_effect=UnsupportedSql):
            rows,_,_=self.compare()
        self.assertEqual(next(r[1]['Billed'] for r in rows if r[1]['Name']=='B'),10)

    def test_ascii_proof_is_request_local_and_preserves_cancellation(self):
        rows,engine,statements=self.run_summary()
        self.assertTrue(engine.budget['grouped_text_ascii']['Hours','Category'])
        self.assertEqual(sum('regexp_full_match' in sql for sql in statements),1)
        execute=self.con.execute
        def cancelled(sql,*args,**kwargs):
            if 'regexp_full_match' in sql:raise duckdb.InterruptException('cancelled while checking secured source')
            return execute(sql,*args,**kwargs)
        with patch.object(self.con,'execute',side_effect=cancelled):
            with self.assertRaises(duckdb.InterruptException):self.run_summary()

    def test_unicode_on_either_physical_comparison_column_declines(self):
        self.con.execute("ALTER TABLE Hours ADD COLUMN OtherCategory VARCHAR DEFAULT 'No match'")
        self.con.execute("UPDATE Hours SET Category='SS',OtherCategory='ß' WHERE PersonID=2")
        self.model['measures'][0]['Expression']='SUMX(FILTER(Hours,Hours[Category]=Hours[OtherCategory]),Hours[Amount])'
        with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql),patch('dax_sql.filter_rows',side_effect=UnsupportedSql):
            rows,engine,_=self.compare()
        self.assertEqual(next(r[1]['Billed'] for r in rows if r[1]['Name']=='B'),10)
        self.assertIs(engine.budget['grouped_text_ascii']['Hours','Category'],True)
        self.assertIs(engine.budget['grouped_text_ascii']['Hours','OtherCategory'],False)

    def test_dormant_overflow_prefetch_does_not_raise_or_pollute_cache(self):
        self.con.execute('CREATE TABLE Huge(Amount HUGEINT)')
        self.con.execute("INSERT INTO Huge VALUES (170141183460469231731687303715884105727),(1)")
        self.model['tables'].append({'name':'Huge'})
        self.model['measures'].extend([
            {'TableName':'M','Name':'Overflow','Expression':'SUM(Huge[Amount])'},
            {'TableName':'M','Name':'Safe Overflow','Expression':'IF(FALSE(),[Overflow],[Capacity])'},
        ])
        self.compare('SUMMARIZE(People,People[Name],"Value",[Safe Overflow])')


if __name__=='__main__':unittest.main()
