"""Request-local projections retain secured context and mutable row isolation."""
import unittest

import duckdb

from dax_engine import Evaluator, Parser


class ConnectionSpy:
    def __init__(self,target):self.target=target;self.queries=[]
    def execute(self,sql,*args,**kwargs):
        self.queries.append(sql)
        return self.target.execute(sql,*args,**kwargs)
    def __getattr__(self,name):return getattr(self.target,name)


class ProjectionCacheTests(unittest.TestCase):
    def setUp(self):
        self.con=ConnectionSpy(duckdb.connect(config={'threads':1}))
        self.con.execute('CREATE TABLE T AS SELECT * FROM (VALUES (1,1),(2,1),(3,2),(4,2)) t(ID,Category)')
        self.model={'tables':[{'name':'T'}],'measures':[],'relationships':[]}
        self.engine=Evaluator(self.con,self.model,filters=[])

    def tearDown(self):self.con.close()

    def test_projection_cache_keys_context_distinct_and_column_order(self):
        engine=self.engine;self.con.queries.clear()
        self.assertEqual(len(engine.project_columns([('T','Category')],True)),2)
        self.assertEqual(len(engine.project_columns([('T','Category')],True)),2)
        self.assertEqual(len(self.con.queries),1)
        self.assertEqual(len(engine.project_columns([('T','Category')],False)),4)
        limited=engine.child([{'table':'T','columns':['ID'],'sql':'"T"."ID"<=2'}])
        self.assertEqual(len(limited.project_columns([('T','Category')],True)),1)
        self.assertEqual(len(limited.project_columns([('T','Category')],True)),1)
        engine.project_columns([('T','ID'),('T','Category')],False)
        reversed_rows=engine.project_columns([('T','Category'),('T','ID')],False)
        self.assertEqual(list(reversed_rows[0][1]),['Category','ID'])
        self.assertEqual(len(self.con.queries),5)

    def test_cached_records_do_not_expose_mutable_rows_and_do_not_cross_requests(self):
        first=self.engine.project_columns([('T','ID')],False)
        first[0][1]['ID']=999;first.pop()
        second=self.engine.project_columns([('T','ID')],False)
        self.assertEqual([r[1]['ID'] for r in second],[1,2,3,4])
        self.con.execute('INSERT INTO T VALUES (5,3)')
        fresh=Evaluator(self.con,self.model,filters=[])
        self.assertEqual(len(fresh.project_columns([('T','ID')],False)),5)

    def test_selected_value_alternate_is_lazy_and_remains_row_dependent(self):
        rows=self.engine.table('T')
        node=Parser('SELECTEDVALUE(T[Category],T[ID])').parse()
        self.assertEqual(self.engine.run(node,{},rows[0]),1)
        self.assertEqual(self.engine.run(node,{},rows[1]),2)
        limited=self.engine.child([{'table':'T','columns':['ID'],'sql':'"T"."ID"<=2'}])
        self.assertEqual(limited.run(Parser('SELECTEDVALUE(T[Category],ERROR("unused"))').parse()),1)

    def test_cache_is_bounded_and_secured_views_are_the_only_source(self):
        self.con.execute('ALTER TABLE T RENAME TO private_rows')
        self.con.execute('CREATE VIEW T AS SELECT * FROM private_rows WHERE ID<=2')
        for value in range(140):
            child=self.engine.child([{'table':'T','columns':['ID'],'sql':'"T"."ID"<='+str(value)}])
            self.assertLessEqual(len(child.project_columns([('T','ID')],False)),2)
        self.assertLessEqual(len(self.engine.budget['projected_columns']),128)
        self.assertLessEqual(self.engine.budget['projected_column_cells'],200000)
        self.assertLessEqual(self.engine.budget['projected_column_bytes'],16000000)

    def test_mutable_complex_columns_do_not_enter_scalar_record_cache(self):
        self.con.execute('CREATE TABLE Nested AS SELECT [1,2] AS Items')
        self.model['tables'].append({'name':'Nested'})
        first=self.engine.project_columns([('Nested','Items')],False)
        first[0][1]['Items'].append(999)
        second=self.engine.project_columns([('Nested','Items')],False)
        self.assertEqual(second[0][1]['Items'],[1,2])
        self.assertFalse(self.engine.budget['projected_columns'])


if __name__=='__main__':unittest.main()
