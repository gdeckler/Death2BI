import unittest,datetime as dt,duckdb
from dax_engine import Evaluator,Parser
class HtmlDaxTests(unittest.TestCase):
 def setUp(self):
  self.con=duckdb.connect();self.con.execute('CREATE TABLE T(ID INTEGER,N INTEGER,Category VARCHAR); INSERT INTO T VALUES (1,10,\'A\'),(2,20,\'A\'),(3,30,\'B\')')
  self.model={'tables':[{'name':'T'}],'relationships':[],'measures':[{'TableName':'T','Name':'Amount','Expression':'SUM(T[N])'}]}
 def tearDown(self):self.con.close()
 def ev(self,text,filters=None):return Evaluator(self.con,self.model,{},filters=filters or []).run(Parser(text).parse(),{},None)
 def test_comments_and_unary_not(self):
  self.assertEqual(self.ev('VAR h="<div>-- keep // keep</div>" -- ignore ; :\nRETURN IF(NOT FALSE(),h,"wrong")'),'<div>-- keep // keep</div>')
 def test_virtual_lineage_and_outer_context(self):
  self.assertEqual(self.ev('SUMX(ADDCOLUMNS(T,"Extra",1),CALCULATE(SUM(T[N])))'),60)
  self.assertEqual(self.ev('SUMX(T,COUNTROWS(FILTER(T,T[ID]<=EARLIER(T[ID]))))'),6)
  self.assertEqual(self.ev('CONCATENATEX(T,T[Category],",",T[Category],ASC,T[N],DESC)'),'A,A,B')
 def test_dates_and_context_cache(self):
  self.assertEqual(self.ev('FORMAT(DATE(2026,10,3),"ddd, mmm d")'),'Sat, Oct 3')
  self.assertEqual(self.ev('INT(DATE(2026,10,3))'),(dt.date(2026,10,3)-dt.date(1899,12,30)).days)
  e=Evaluator(self.con,self.model,{},filters=[]);self.assertEqual(e.measure('Amount','T'),60)
  child=e.child([{'table':'T','columns':['Category'],'sql':"T.Category='A'"}]);self.assertEqual(child.measure('Amount','T'),30);self.assertEqual(e.measure('Amount','T'),60)
if __name__=='__main__':unittest.main()
