import unittest
from unittest.mock import patch
import duckdb
from dax_engine import Evaluator, Parser, evaluate_visual, evaluate_topn
from dax_sql import UnsupportedSql

class RankFilterTests(unittest.TestCase):
 def setUp(self):
  self.con=duckdb.connect();self.addCleanup(self.con.close)
  self.con.execute("CREATE TABLE Raw(ID INTEGER,N DOUBLE,Category VARCHAR); INSERT INTO Raw VALUES(1,10,'A'),(2,30,'A'),(3,30,'A'),(4,90,'B'),(5,NULL,'A'); CREATE VIEW T AS SELECT * FROM Raw WHERE ID<>4")
  self.model={'tables':[{'name':'T'}],'relationships':[],'measures':[{'TableName':'M','Name':'Score','Expression':'SUM(T[N])'},{'TableName':'M','Name':'Rank','Expression':'RANKX(ALL(T[ID]),[Score],,DESC,DENSE)'}]}
 def ev(self,text,filters):
  e=Evaluator(self.con,self.model,{},filters=filters);e.external_filters=[];e.scope=[('T','ID')]
  return e.run(Parser(text).parse(),{},None),e
 def test_rank_score_cache_matches_interpreter(self):
  for text in ['RANKX(ALL(T[ID]),[Score],,DESC,DENSE)','RANKX(ALLSELECTED(T[ID]),[Score],,ASC,SKIP)','RANKX(ALL(T[ID]),SUM(T[N]),,DESC,DENSE)']:
   filters=[{'table':'T','columns':['ID'],'sql':'T.ID=1'}]
   fast,e=self.ev(text,filters)
   with patch('dax_sql.rank_value',side_effect=UnsupportedSql('reference')):reference,_=self.ev(text,filters)
   self.assertEqual(fast,reference)
  self.assertEqual(self.ev('[Rank]',[{'table':'T','columns':['ID'],'sql':'T.ID=1'}])[0],2)
 def test_topn_ties_respects_secured_source_and_filters(self):
  payload={'category':{'Column':{'Expression':{'SourceRef':{'Entity':'T'}},'Property':'ID'}},'by':{'Measure':{'Expression':{'SourceRef':{'Entity':'M'}},'Property':'Rank'}},'count':1,'descending':False,'filters':[]}
  result=evaluate_topn(self.con,self.model,payload);self.assertEqual(set(result['values']),{2,3});self.assertNotIn(4,result['values'])
  payload['filters']=[{'table':'T','columns':['Category'],'sql':"T.Category='B'"}];self.assertEqual(evaluate_topn(self.con,self.model,payload)['values'],[])
 def test_shared_base_filters_match_expanded_context(self):
  field={'Measure':{'Expression':{'SourceRef':{'Entity':'M'}},'Property':'Score'}};base=[{'table':'T','columns':['Category'],'sql':"T.Category='A'"}];local=[{'table':'T','columns':['ID'],'sql':'T.ID=1'}]
  compact=evaluate_visual(self.con,self.model,{'fields':[field],'baseFilters':base,'groups':[{'filters':local,'scope':[]}]})
  old=evaluate_visual(self.con,self.model,{'fields':[field],'groups':[{'filters':base+local,'externalFilters':base,'scope':[]}]})
  self.assertEqual(compact['rows'],old['rows']);self.assertEqual(compact['rows'],[[10]])
if __name__=='__main__':unittest.main()
