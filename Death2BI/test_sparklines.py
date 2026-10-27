import unittest,duckdb
from dax_engine import evaluate_visual
class SparklineTests(unittest.TestCase):
 def test_secured_context_and_period_order(self):
  c=duckdb.connect();self.addCleanup(c.close);c.execute("CREATE TABLE Raw(C VARCHAR,Y INTEGER,N DOUBLE);INSERT INTO Raw VALUES('A',2022,3),('A',2020,1),('B',2020,9),('secret',2020,100);CREATE VIEW T AS SELECT * FROM Raw WHERE C<>'secret'")
  m={'tables':[{'name':'T'}],'relationships':[],'measures':[{'TableName':'M','Name':'N','Expression':'SUM(T[N])'}]}
  f={'SparklineData':{'Measure':{'Measure':{'Expression':{'SourceRef':{'Entity':'M'}},'Property':'N'}},'Groupings':[{'Column':{'Expression':{'SourceRef':{'Entity':'T'}},'Property':'Y'}}]}}
  r=evaluate_visual(c,m,{'fields':[f],'groups':[{'filters':[{'table':'T','columns':['C'],'sql':"T.C='A'"}],'values':{}}]});self.assertEqual(r['rows'][0][0]['sparkline'],[[2020,1],[2022,3]])
 def test_coordinate_mean_ignores_invalid_pairs_and_secured_rows(self):
  c=duckdb.connect();self.addCleanup(c.close);c.execute("CREATE TABLE Raw(Lat DOUBLE,Lon DOUBLE,Allowed BOOLEAN);INSERT INTO Raw VALUES(10,20,true),(30,40,true),(50,-999999,true),(80,90,false);CREATE VIEW T AS SELECT * FROM Raw WHERE Allowed")
  m={'tables':[{'name':'T'}],'relationships':[],'measures':[]}
  f={'GeoMean':{'table':'T','column':'Lat','latitude':'Lat','longitude':'Lon'}}
  r=evaluate_visual(c,m,{'fields':[f],'groups':[{'filters':[],'values':{}}]});self.assertEqual(r['rows'],[[20]])
if __name__=='__main__':unittest.main()
