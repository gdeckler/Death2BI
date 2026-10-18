"""Public entry points for the bounded Python DAX evaluator."""
import time
from decimal import Decimal
from dax_core import Parser, qi, sv, CoreEvaluator
from dax_runtime import RuntimeEvaluator as Evaluator
from dax_budget import limits, check_budget

def evaluate_visual(con,model,payload):
 groups=payload['groups']; fields=payload['fields']
 if len(groups)>1000 or len(fields)>50: raise ValueError('Python visual limit exceeded')
 seconds,max_steps=limits(); started=time.monotonic()
 rows=[]; budget={'deadline':started+seconds,'started':started,'seconds':seconds,'max_steps':max_steps,'steps':0}
 for group_index,group in enumerate(groups):
  check_budget(budget)
  engine=Evaluator(con,model,group.get('contexts',{}),filters=group.get('filters'),budget=budget); engine.scope=[tuple(c) for c in group.get('scope',[])]; engine.external_filters=group.get('externalFilters',group.get('filters')); result=[]
  for i,f in enumerate(fields):
   budget['location']=f"{f.get('Measure',{}).get('Property', 'field '+str(i+1))}, group {group_index+1}/{len(groups)}"
   if f.get('Measure'): result.append(engine.measure(f['Measure']['Property'],f['Measure'].get('Expression',{}).get('SourceRef',{}).get('Entity')))
   elif f.get('Column') or f.get('GroupRef'): result.append(group['values'][str(i)])
   elif f.get('Aggregation'):
    a=f['Aggregation']; c=a['Expression']['Column']; fn={0:'SUM',1:'AVERAGE',2:'COUNT',3:'MIN',4:'MAX',5:'DISTINCTCOUNT'}[a['Function']]
    result.append(engine.run(('call',fn,[('col',c['Expression']['SourceRef']['Entity'],c['Property'])]),{},None))
   else: raise ValueError('Python DAX visual field is not supported')
  check_budget(budget)
  rows.append(result)
 return {'columns':['v'+str(i) for i in range(len(fields))],'types':['DOUBLE' if any(isinstance(r[i],(int,float,Decimal)) for r in rows) else 'VARCHAR' for i in range(len(fields))],'rows':rows,'truncated':False,'evaluation':{'elapsedSeconds':round(time.monotonic()-started,3),'steps':budget['steps'],'timeLimitSeconds':seconds,'stepLimit':max_steps}}

