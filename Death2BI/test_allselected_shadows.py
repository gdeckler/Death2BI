"""Bounded FILTER/ALLSELECTED shadows preserve the selected secured row domain."""
import unittest

import duckdb

from dax_engine import Evaluator, Parser


class AllselectedShadowTests(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect(config={'threads':1})
        self.con.execute('CREATE TABLE T AS SELECT * FROM (VALUES (1,1.0,10.0,1),(2,2.0,20.0,1),(3,3.0,30.0,2),(4,4.0,40.0,2)) t(ID,ROI,Budget,GroupID)')
        self.con.execute("CREATE TABLE D AS SELECT * FROM (VALUES (1,'A'),(2,'B')) d(ID,Category)")
        self.model={'tables':[{'name':'T'},{'name':'D'}],'relationships':[{'IsActive':True,'Cardinality':'M:1','CrossFilteringBehavior':'Single','FromTableName':'T','FromColumnName':'GroupID','ToTableName':'D','ToColumnName':'ID'}],'measures':[
            {'Name':'Selected ROI','TableName':'M','Expression':'CALCULATE(MEDIAN(T[ROI]),ALLSELECTED(T))'},
            {'Name':'Selected Budget','TableName':'M','Expression':'CALCULATE(MEDIAN(T[Budget]),ALLSELECTED(T))'},
            {'Name':'Quadrant','TableName':'M','Expression':'IF(MAX(T[ROI])>=[Selected ROI] && MAX(T[Budget])>=[Selected Budget],1,3)'},
            {'Name':'Upper Count','TableName':'M','Expression':'COUNTROWS(FILTER(ALLSELECTED(T),[Quadrant]=1))'},
        ]}

    def tearDown(self):self.con.close()

    def engine(self,filters=(),external=None):
        engine=Evaluator(self.con,self.model,filters=list(filters))
        engine.external_filters=list(filters if external is None else external)
        return engine

    def test_medians_restore_selected_domain_after_each_row_transition(self):
        class ConnectionSpy:
            def __init__(self,target):self.target=target;self.queries=[]
            def execute(self,sql,*args,**kwargs):
                self.queries.append(sql)
                return self.target.execute(sql,*args,**kwargs)
            def __getattr__(self,name):return getattr(self.target,name)
        self.con=ConnectionSpy(self.con)
        engine=self.engine()
        self.assertEqual(engine.measure('Upper Count','M'),2)
        self.assertFalse(engine.selection_shadows)
        # The selected-domain medians are queried once, rather than per movie.
        self.assertEqual(len([sql for sql in self.con.queries if 'MEDIAN(' in sql.upper()]),2)
        self.assertEqual(engine.measure('Upper Count','M'),2)

    def test_external_filters_and_visual_row_filters_have_distinct_scope(self):
        external=[{'table':'T','columns':['ID'],'sql':'"T"."ID"<=3'}]
        visual={'table':'T','columns':['ID'],'sql':'"T"."ID"=1'}
        engine=self.engine([*external,visual],external)
        self.assertEqual(engine.measure('Upper Count','M'),2)
        # The visual's current movie does not reduce the ALLSELECTED domain.
        self.assertEqual(engine.run(Parser('COUNTROWS(ALLSELECTED(T))').parse()),3)
        self.assertFalse(engine.selection_shadows)

    def test_related_external_filter_and_held_selected_table_are_preserved(self):
        filters=[{'table':'D','columns':['Category'],'sql':'"D"."Category"=\'A\''}]
        engine=self.engine(filters)
        self.assertEqual(engine.measure('Upper Count','M'),1)
        expression='VAR Selected=ALLSELECTED(T) RETURN CALCULATE(COUNTROWS(FILTER(Selected,T[ROI]>=[Selected ROI])),T[ID]=1)'
        self.assertEqual(engine.run(Parser(expression).parse()),1)

    def test_changed_bridge_filter_does_not_expand_a_held_selection_shadow(self):
        self.con.execute("CREATE TABLE B AS SELECT * FROM (VALUES (1,'A'),(2,'B')) b(ID,Label)")
        self.model['tables'].append({'name':'B'})
        self.model['relationships'].append({'IsActive':True,'Cardinality':'M:M','CrossFilteringBehavior':'Both','FromTableName':'T','FromColumnName':'GroupID','ToTableName':'B','ToColumnName':'ID'})
        filters=[{'table':'B','columns':['Label'],'sql':'"B"."Label"=\'A\''}]
        engine=self.engine(filters)
        expression='VAR Held=ALLSELECTED(T) RETURN CALCULATE(COUNTROWS(FILTER(Held,T[ROI]>=[Selected ROI])),B[Label]="B")'
        with self.assertRaisesRegex(ValueError,'unchanged filters outside'):
            engine.run(Parser(expression).parse())
        self.assertFalse(engine.selection_shadows)

    def test_row_aggregate_shortcut_does_not_survive_a_modifier(self):
        self.model['measures'].append({'Name':'Changed Max','TableName':'M','Expression':'CALCULATE(MAX(T[ROI]),REMOVEFILTERS(T))'})
        self.assertEqual(self.engine().run(Parser('COUNTROWS(FILTER(ALLSELECTED(T),[Changed Max]=4))').parse()),4)

    def test_held_rows_excluded_by_surviving_related_filter_do_not_shortcut(self):
        self.con.execute("CREATE TABLE B AS SELECT * FROM (VALUES (1,'A'),(2,'B')) b(ID,Label)")
        self.model['tables'].append({'name':'B'})
        self.model['relationships'].append({'IsActive':True,'Cardinality':'M:M','CrossFilteringBehavior':'Both','FromTableName':'T','FromColumnName':'GroupID','ToTableName':'B','ToColumnName':'ID'})
        self.model['measures'].append({'Name':'Plain Max','TableName':'M','Expression':'MAX(T[ROI])'})
        expression='VAR Held=ALLSELECTED(T) RETURN CALCULATE(COUNTROWS(FILTER(Held,[Plain Max]>0)),B[Label]="A")'
        self.assertEqual(self.engine().run(Parser(expression).parse()),2)

    def test_secured_view_is_the_only_source_for_shadow_and_median(self):
        self.con.execute('ALTER TABLE T RENAME TO private_rows')
        self.con.execute('CREATE VIEW T AS SELECT * FROM private_rows WHERE ID<=2')
        engine=self.engine()
        self.assertEqual(engine.measure('Upper Count','M'),1)
        self.assertEqual(engine.run(Parser('COUNTROWS(ALLSELECTED(T))').parse()),2)

    def test_unproven_plain_and_nested_physical_iterators_remain_unsupported(self):
        for expression in ('SUMX(T,[Selected ROI])','SUMX(T,COUNTROWS(FILTER(ALLSELECTED(T),[Quadrant]=1)))'):
            engine=self.engine()
            with self.subTest(expression=expression),self.assertRaisesRegex(ValueError,'shadow|iterator'):
                engine.run(Parser(expression).parse())
            self.assertFalse(engine.selection_shadows)

    def test_column_targets_and_relationship_overrides_remain_unsupported(self):
        for expression in ('COUNTROWS(FILTER(ALLSELECTED(T),CALCULATE(SUM(T[ROI]),ALLSELECTED(T[ROI]))>0))','COUNTROWS(FILTER(ALLSELECTED(T),CALCULATE(SUM(T[ROI]),ALLSELECTED(T),CROSSFILTER(T[GroupID],D[ID],Both))>0))'):
            engine=self.engine()
            with self.subTest(expression=expression),self.assertRaisesRegex(ValueError,'shadow|iterator'):
                engine.run(Parser(expression).parse())
            self.assertFalse(engine.selection_shadows)

    def test_error_restores_engine_state(self):
        engine=self.engine()
        with self.assertRaisesRegex(ValueError,'stop'):
            engine.run(Parser('COUNTROWS(FILTER(ALLSELECTED(T),ERROR("stop")))').parse())
        self.assertFalse(engine.selection_shadows)
        self.assertFalse(engine.row_stack)
        self.assertEqual(engine.measure('Upper Count','M'),2)


if __name__=='__main__':unittest.main()
