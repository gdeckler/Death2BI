import unittest
from unittest.mock import patch
from decimal import Decimal

import duckdb

from dax_core import qi,sv
from dax_engine import Evaluator
from dax_sql import SqlDax,UnsupportedSql,evaluate_groups


class SharedGroupAggregateTests(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect()
        self.con.execute("CREATE TABLE F AS SELECT * FROM (VALUES (1,10,100,10.0,1.0),(1,10,100,10.0,1.0),(2,10,200,30.0,-2.0),(3,20,100,5.0,2.0),(4,20,300,NULL,0.0)) f(ID,CustomerID,ProductID,Revenue,Profit)")
        self.con.execute("CREATE TABLE D AS SELECT * FROM (VALUES (10,'A'),(20,'B'),(30,'Empty')) d(CustomerID,Name)")
        self.con.execute("CREATE TABLE P AS SELECT * FROM (VALUES (100,'Furniture'),(200,'Office'),(300,'Technology')) p(ProductID,Category)")
        self.model={'tables':[{'name':n} for n in ('F','D','P')],'relationships':[
            {'IsActive':True,'Cardinality':'M:1','CrossFilteringBehavior':'Both','FromTableName':'F','FromColumnName':'CustomerID','ToTableName':'D','ToColumnName':'CustomerID'},
            {'IsActive':True,'Cardinality':'M:1','CrossFilteringBehavior':'Both','FromTableName':'F','FromColumnName':'ProductID','ToTableName':'P','ToColumnName':'ProductID'},
        ],'measures':[{'TableName':'M','Name':'Revenue','Expression':'SUM(F[Revenue])'},{'TableName':'M','Name':'Profit','Expression':'SUM(F[Profit])'}]}
        for name in ('Furniture','Office','Technology'):
            self.model['measures'].append({'TableName':'M','Name':name,'Expression':'CALCULATE([Revenue],REMOVEFILTERS(P[Category]),P[Category]="'+name+'")'})
            self.model['measures'].append({'TableName':'M','Name':name+'Share','Expression':'VAR F=[Furniture] VAR O=[Office] VAR T=[Technology] RETURN DIVIDE(['+name+'],F+O+T)'})
        self.model['measures'].append({'TableName':'M','Name':'Class','Expression':'VAR F=[FurnitureShare] VAR O=[OfficeShare] VAR T=[TechnologyShare] VAR Largest=MAX(F,MAX(O,T)) RETURN IF(ISBLANK(Largest),BLANK(),IF(Largest>=0.6,"Specialist","Mixed"))'})

    def tearDown(self):self.con.close()

    def payload(self,external=()):
        names=('Revenue','Profit','FurnitureShare','OfficeShare','TechnologyShare','Class')
        fields=[{'Column':{'Expression':{'SourceRef':{'Entity':'D'}},'Property':'Name'}}]+[{'Measure':{'Expression':{'SourceRef':{'Entity':'M'}},'Property':name}} for name in names]
        groups=[{'values':{'0':value},'filters':[*external,{'table':'D','columns':['Name'],'sql':qi('D')+'.'+qi('Name')+' = '+sv(value)}],'externalFilters':list(external),'scope':[('D','Name')]} for value in ('A','B','Empty')]
        return {'fields':fields,'groups':groups}

    def check(self,payload):
        engine=Evaluator(self.con,self.model,filters=[]);actual=evaluate_groups(self.con,self.model,payload,engine.budget)
        self.assertEqual(engine.budget.get('shared_aggregate_plans'),1)
        with patch.object(SqlDax,'shared_aggregate',lambda self,sql,*args:sql):
            legacy=evaluate_groups(self.con,self.model,payload,Evaluator(self.con,self.model,filters=[]).budget)
        for rows in (legacy,):
            for a,b in zip(actual,rows):
                for x,y in zip(a,b):
                    if isinstance(x,(int,float,Decimal)) and isinstance(y,(int,float,Decimal)):self.assertAlmostEqual(float(x),float(y),places=12)
                    else:self.assertEqual(x,y)
        expected=[]
        with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql),patch('dax_sql.evaluate_expression',side_effect=UnsupportedSql):
            for group in payload['groups']:
                e=Evaluator(self.con,self.model,filters=group['filters']);e.external_filters=group['externalFilters']
                expected.append(tuple([group['values']['0']]+[e.measure(field['Measure']['Property'],'M') for field in payload['fields'][1:]]))
        for a,b in zip(actual,expected):
            for x,y in zip(a,b):
                if isinstance(x,(int,float,Decimal)) and isinstance(y,(int,float,Decimal)):self.assertAlmostEqual(float(x),float(y),places=12)
                else:self.assertEqual(x,y)
        return actual

    def test_repeated_classification_shares_match_python_and_previous_sql(self):
        result=self.check(self.payload())
        self.assertEqual(result[0],('A',50,0,.4,.6,0.0,'Specialist'))
        self.assertEqual(result[1][-1],'Specialist')

    def test_external_filters_and_replaced_category_context(self):
        self.check(self.payload([{'table':'P','columns':['Category'],'sql':'"P"."Category" = \'Office\''}]))
        self.check(self.payload([{'table':'F','columns':['ID'],'sql':'"F"."ID" = 2'}]))

    def test_secured_view_cannot_restore_hidden_rows(self):
        self.con.execute('ALTER TABLE F RENAME TO private_rows')
        self.con.execute('CREATE VIEW F AS SELECT * FROM private_rows WHERE ID=2')
        result=self.check(self.payload())
        self.assertEqual(result[0][1],30)
        self.assertIsNone(result[1][1])

    def test_lexical_iterator_aliases_and_nonnumeric_columns_are_not_hoisted(self):
        e=Evaluator(self.con,self.model,filters=[]);compiler=SqlDax(e);compiler.shared_aggregates={'queries':{},'bytes':0}
        for sql in ('(SELECT SUM(F.Revenue) FROM F WHERE F.ID="__var_123".ID)','(SELECT SUM(F.Revenue) FROM F WHERE F.ID=__rank_g.k0)'):
            self.assertEqual(compiler.shared_aggregate(sql,'F','Revenue',e,None),sql)
        sql='(SELECT MIN(P.Category) FROM P)'
        self.assertEqual(compiler.shared_aggregate(sql,'P','Category',e,None),sql)
        self.assertEqual(compiler.shared_aggregates['queries'],{})
        e.row_stack=[('F',{'ID':1})]
        sql='(SELECT SUM(F.Revenue) FROM F)'
        self.assertEqual(compiler.shared_aggregate(sql,'F','Revenue',e,None),sql)

    def test_shared_plan_is_bounded_and_request_local(self):
        e=Evaluator(self.con,self.model,filters=[]);compiler=SqlDax(e);compiler.shared_aggregates={'queries':{},'bytes':0}
        for index in range(100):compiler.shared_aggregate('(SELECT SUM(F.Revenue) FROM F WHERE F.ID='+str(index)+')','F','Revenue',e,None)
        self.assertEqual(len(compiler.shared_aggregates['queries']),64)
        self.assertIsNone(SqlDax(e).shared_aggregates)


if __name__=='__main__':unittest.main()
