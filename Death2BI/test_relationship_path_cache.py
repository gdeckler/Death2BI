import unittest
import duckdb
from dax_engine import Evaluator


class RelationshipPathCacheTests(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect()
        self.model={'tables':[],'measures':[],'relationships':[
            {'FromTableName':'F','FromColumnName':'DId','ToTableName':'D','ToColumnName':'Id','IsActive':1,'Cardinality':'M:1','CrossFilteringBehavior':'Both'},
            {'FromTableName':'F','FromColumnName':'Date','ToTableName':'Calendar','ToColumnName':'Date','IsActive':1,'Cardinality':'M:1','CrossFilteringBehavior':'Both'},
        ]}
        self.engine=Evaluator(self.con,self.model,filters=[])

    def tearDown(self):self.con.close()

    def test_multihop_disconnected_and_mutable_return_values(self):
        expected=[('Calendar','Date','F','Date'),('F','DId','D','Id')]
        first=self.engine.path('Calendar','D')
        self.assertEqual(first,expected)
        first.clear()
        child=self.engine.child([])
        self.assertEqual(child.path('Calendar','D'),expected)
        self.assertIsNone(child.path('Calendar','Missing'))
        self.assertIsNone(child.path('Calendar','Missing'))
        self.assertEqual(child.path('D','D'),[])
        self.assertEqual(len(self.engine.budget['relationship_graphs']),1)

    def test_relationship_changes_never_reuse_another_graph(self):
        self.assertIsNotNone(self.engine.path('D','Calendar'))
        relation=self.model['relationships'][0]
        relation['CrossFilteringBehavior']='Single'
        self.assertIsNone(self.engine.path('D','Calendar'))
        relation['CrossFilteringBehavior']='Both'
        relation['FromColumnName']='Changed'
        self.assertEqual(self.engine.path('D','F'),[('D','Id','F','Changed')])
        relation['IsActive']=0
        self.assertIsNone(self.engine.path('D','F'))
        relation['IsActive']=1
        relation['Cardinality']='unsupported'
        self.assertIsNone(self.engine.path('D','F'))
        relation['Cardinality']='M:1'
        self.assertIsNotNone(self.engine.path('D','F'))

    def test_request_isolation_and_bounded_graph_variants(self):
        self.engine.path('F','D')
        other=Evaluator(self.con,self.model,filters=[])
        self.assertNotIn('relationship_graphs',other.budget)
        for index in range(30):
            self.model['relationships'][0]['FromColumnName']='Key'+str(index)
            self.engine.path('F','D')
        self.assertLessEqual(len(self.engine.budget['relationship_graphs']),16)
        self.assertEqual(self.engine.path('F','D'),[('F','Key29','D','Id')])


if __name__=='__main__':unittest.main()
