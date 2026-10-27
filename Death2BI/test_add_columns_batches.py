import unittest
from unittest.mock import patch

import duckdb

from dax_core import Parser
from dax_engine import Evaluator
from dax_runtime import Table
from dax_sql import add_columns,evaluate_groups,UnsupportedSql


class AddColumnsBatchTests(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect(config={'threads':1})
        self.con.execute('CREATE TABLE D(ID INTEGER,Name VARCHAR,Weight DOUBLE)')
        self.con.executemany('INSERT INTO D VALUES (?,?,?)',[(i,None if i==130 else 'Customer '+str(i),0.9995651464912757 if i==130 else i/10) for i in range(131)])
        self.con.execute('CREATE TABLE F(ID INTEGER,CustomerID INTEGER,Amount DOUBLE)')
        self.con.executemany('INSERT INTO F VALUES (?,?,?)',[(i,i,float(i*2)) for i in range(131)])
        self.model={'tables':[{'name':'D'},{'name':'F'}],'relationships':[{'IsActive':True,'Cardinality':'M:1','CrossFilteringBehavior':'Single','FromTableName':'F','FromColumnName':'CustomerID','ToTableName':'D','ToColumnName':'ID'}],'measures':[{'TableName':'M','Name':'Amount','Expression':'SUM(F[Amount])'}]}

    def tearDown(self):self.con.close()

    def batched(self,engine,rows):
        calls=[]
        def record(con,model,payload,budget,expressions):
            calls.append((len(payload['groups']),id(budget),tuple((f.get('Column') or {}).get('Property') for f in payload['fields'])))
            return evaluate_groups(con,model,payload,budget,expressions)
        with patch('dax_sql.evaluate_groups',side_effect=record):result=add_columns(engine,rows,[Parser('[Amount]').parse()])
        return result,calls

    def test_large_projected_domain_preserves_order_nulls_floats_and_one_budget(self):
        engine=Evaluator(self.con,self.model,filters=[])
        rows=engine.project_columns([('D','Name'),('D','Weight')],False)
        result,calls=self.batched(engine,rows)
        self.assertEqual([size for size,_,_ in calls],[64,64,3])
        self.assertEqual({budget for _,budget,_ in calls},{id(engine.budget)})
        self.assertEqual(result,[[float(i*2)] for i in range(131)])
        self.assertIsNone(rows[-1][1]['Name'])
        self.assertEqual(rows[-1][1]['Weight'],0.9995651464912757)

    def test_different_expanded_lineage_partitions_keep_original_positions(self):
        self.con.execute('UPDATE F SET CustomerID=999 WHERE ID>=100')
        engine=Evaluator(self.con,self.model,filters=[])
        rows=engine.project_columns([('F','ID'),('F','CustomerID')],False)
        result,calls=self.batched(engine,rows)
        self.assertEqual([size for size,_,_ in calls],[64,36,31])
        self.assertEqual(result,[[float(i*2)] for i in range(131)])
        self.assertTrue(any('Name' in fields for _,_,fields in calls))
        self.assertTrue(any('Name' not in fields for _,_,fields in calls))
        with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql),patch('dax_rowset.evaluate_rows',side_effect=UnsupportedSql):
            expected=[[engine.measure('Amount','M',row)] for row in rows]
        self.assertEqual(result,expected)


if __name__=='__main__':unittest.main()
