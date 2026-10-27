import unittest
from unittest.mock import patch
import duckdb
from dax_engine import Evaluator, evaluate_visual
from dax_sql import evaluate_scalar, UnsupportedSql

class SqlDaxTests(unittest.TestCase):
 def test_selected_value_in_sql_includes_blank_identity(self):
  c=duckdb.connect()
  try:
   c.execute('CREATE TABLE Choices AS SELECT * FROM (VALUES (1),(2),(NULL)) t(N)')
   model={'tables':[{'name':'Choices'}],'measures':[{'TableName':'M','Name':'Selected','Expression':'SELECTEDVALUE(Choices[N],80)'}]}
   for condition,expected in [('TRUE',80),('"Choices"."N"=1',1),('"Choices"."N" IS NULL',None),('FALSE',80)]:
    filters=[{'table':'Choices','columns':['N'],'sql':condition}]
    self.assertEqual(evaluate_scalar(Evaluator(c,model,filters=filters),'Selected'),expected)
  finally:c.close()

 def test_bidirectional_shared_path_uses_same_fact_row(self):
  c=duckdb.connect()
  try:
   c.execute("CREATE TABLE People AS SELECT 'A' AS Name")
   c.execute("CREATE TABLE Dates AS SELECT * FROM (VALUES (DATE '2020-01-01'),(DATE '2020-01-02')) t(Date)")
   c.execute("CREATE TABLE Events AS SELECT * FROM (VALUES ('A',DATE '2020-01-01','Allowed'),('A',DATE '2020-01-02','Other')) t(Name,Date,Kind)")
   model={'tables':[{'name':t} for t in ['People','Dates','Events']],'measures':[],'relationships':[{'FromTableName':'Events','FromColumnName':a,'ToTableName':b,'ToColumnName':d,'IsActive':1,'Cardinality':'M:1','CrossFilteringBehavior':'Both'} for a,b,d in [('Name','People','Name'),('Date','Dates','Date')]]}
   filters=[{'table':'Events','columns':['Kind'],'sql':'''"Events"."Kind"='Allowed' '''},{'table':'Dates','columns':['Date'],'sql':'''"Dates"."Date"=DATE '2020-01-02' '''}]
   evaluator=Evaluator(c,model,filters=filters)
   self.assertEqual(c.execute('SELECT * FROM People WHERE '+evaluator.where('People')).fetchall(),[])
  finally:c.close()

 def test_grouped_iterator_sql_matches_python_contexts(self):
  c=duckdb.connect()
  try:
   c.execute("CREATE TABLE People AS SELECT * FROM (VALUES ('A','SALARY'),('B','HOURLY'),('C','SALARY')) t(Name,EmployeeType)")
   c.execute("CREATE TABLE Hours AS SELECT * FROM (VALUES ('A','Billable',8),('A','Other',2),('B','Billable',5)) t(Name,Category,Hours)")
   c.execute("CREATE TABLE Calendar AS SELECT * FROM (VALUES (8),(8)) t(WorkHours)")
   expressions={'Billable':'''VAR T=FILTER('Hours',Hours[Category]="billable") RETURN SUMX(T,[Hours])''','Capacity':"SUM(Calendar[WorkHours])",'Total':'''VAR T=SUMMARIZE(People,People[Name],"__H",[Capacity]) RETURN SWITCH(MAX(People[EmployeeType]),"SALARY",SUMX(T,[__H]),"HOURLY",[Billable])''','Utilization':'''VAR T=SUMMARIZE(People,People[Name],"__B",[Billable],"__H",[Total]) RETURN DIVIDE(SUMX(T,[__B]),SUMX(T,[__H]))'''}
   model={'tables':[{'name':t} for t in ['People','Hours','Calendar']],'relationships':[{'FromTableName':'Hours','FromColumnName':'Name','ToTableName':'People','ToColumnName':'Name','IsActive':1,'Cardinality':'M:1','CrossFilteringBehavior':'Single'}],'measures':[{'Name':n,'TableName':'M','Expression':expr} for n,expr in expressions.items()]}
   def reference(filters,name):
    with patch('dax_sql.evaluate_scalar',side_effect=UnsupportedSql),patch('dax_sql.evaluate_groups',side_effect=UnsupportedSql):
     return Evaluator(c,model,filters=filters).measure(name)
   for filters in [[],[{'table':'People','columns':['Name'],'sql':'''"People"."Name"='A' '''}],[{'table':'People','columns':['Name'],'sql':'''"People"."Name"='B' '''}]]:
    for name in expressions:
     fast=Evaluator(c,model,filters=filters)
     if name=='Utilization':
      with self.assertRaisesRegex(UnsupportedSql,'SQL safety fallback'):evaluate_scalar(fast,name)
      self.assertEqual(fast.measure(name),reference(filters,name),name)
     else:self.assertEqual(evaluate_scalar(fast,name),reference(filters,name),name)
   with self.assertRaises(UnsupportedSql):evaluate_scalar(Evaluator(c,model,filters=[]),'Missing')
   groups=[]
   for name in ['A','B','C']:
    groups.append({'values':{'0':name},'externalFilters':[],'scope':[['People','Name']],'filters':[{'table':'People','columns':['Name'],'sql':'"People"."Name" = '+"'"+name+"'"}]})
   payload={'fields':[{'Column':{'Expression':{'SourceRef':{'Entity':'People'}},'Property':'Name'}},{'Measure':{'Property':'Utilization','Expression':{'SourceRef':{'Entity':'M'}}}}],'groups':groups}
   result=evaluate_visual(c,model,payload)
   self.assertNotEqual(result['evaluation'].get('execution'),'batched SQL')
   for row,group in zip(result['rows'],groups):self.assertEqual(row[1],reference(group['filters'],'Utilization'))
   tail=evaluate_visual(c,model,{**payload,'groups':[groups[0]]*65})
   self.assertNotEqual(tail['evaluation'].get('execution'),'batched SQL')
   self.assertEqual(len(tail['rows']),65)
   self.assertTrue(all(row==tail['rows'][0] for row in tail['rows']))
   c.execute("ALTER TABLE Calendar ADD COLUMN Date DATE");c.execute("UPDATE Calendar SET Date=DATE '2020-01-01'")
   c.execute("ALTER TABLE Hours ADD COLUMN Date DATE");c.execute("UPDATE Hours SET Date=DATE '2020-01-01'")
   model['relationships'][0]['CrossFilteringBehavior']='Both'
   model['relationships'].append({'FromTableName':'Hours','FromColumnName':'Date','ToTableName':'Calendar','ToColumnName':'Date','IsActive':1,'Cardinality':'M:1','CrossFilteringBehavior':'Both'})
   external=[{'table':'Hours','columns':['Category'],'sql':'''"Hours"."Category" = 'Billable' '''},{'table':'People','columns':['EmployeeType'],'sql':'''"People"."EmployeeType" = 'SALARY' '''}]
   full=external+[{'table':'Calendar','columns':['Date'],'sql':'''"Calendar"."Date" = DATE '2020-01-01' '''}]
   fast=Evaluator(c,model,filters=full);fast.external_filters=external
   with self.assertRaisesRegex(UnsupportedSql,'SQL safety fallback'):evaluate_scalar(fast,'Utilization')
   self.assertEqual(fast.measure('Utilization'),reference(full,'Utilization'))
  finally:c.close()

if __name__=='__main__':unittest.main()
