import unittest
import duckdb
from dax_engine import Evaluator, Parser

class TreatasTests(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect()
        self.con.execute('CREATE TABLE Selector(Category VARCHAR); CREATE TABLE Sales(Category VARCHAR,Region VARCHAR,Amount INTEGER)')
        self.con.execute("INSERT INTO Selector VALUES ('A'),('B'),('Missing'); INSERT INTO Sales VALUES ('A','North',10),('A','South',20),('B','North',50)")
        self.model={'tables':[{'name':'Selector'},{'name':'Sales'}],'relationships':[],'measures':[]}
    def tearDown(self):self.con.close()
    def evaluate(self,expression,filters=None):
        return Evaluator(self.con,self.model,{},filters=filters).run(Parser(expression).parse(),{},None)
    def test_disconnected_selector_and_missing_values(self):
        self.assertEqual(self.evaluate('COUNTROWS(TREATAS(VALUES(Selector[Category]),Sales[Category]))'),2)
        expression='CALCULATE(SUM(Sales[Amount]),TREATAS(VALUES(Selector[Category]),Sales[Category]))'
        self.assertEqual(self.evaluate(expression),80)
        select=[{'table':'Selector','columns':['Category'],'sql':"Selector.Category='A'"}]
        self.assertEqual(self.evaluate(expression,select),30)
        select=[{'table':'Selector','columns':['Category'],'sql':"Selector.Category='Missing'"}]
        self.assertIsNone(self.evaluate(expression,select))
    def test_tuple_identity_not_independent_column_filters(self):
        expression='CALCULATE(SUM(Sales[Amount]),TREATAS({("A","North"),("B","South")},Sales[Category],Sales[Region]))'
        self.assertEqual(self.evaluate(expression),10)
        with self.assertRaisesRegex(ValueError,'column counts'):
            self.evaluate('CALCULATE(SUM(Sales[Amount]),TREATAS({1},Sales[Category],Sales[Region]))')
    def test_overwrite_and_keepfilters(self):
        select=[{'table':'Sales','columns':['Category'],'sql':"Sales.Category='B'"}]
        self.assertEqual(self.evaluate('CALCULATE(SUM(Sales[Amount]),TREATAS({"A"},Sales[Category]))',select),30)
        self.assertIsNone(self.evaluate('CALCULATE(SUM(Sales[Amount]),KEEPFILTERS(TREATAS({"A"},Sales[Category])))',select))

if __name__=='__main__':unittest.main()
