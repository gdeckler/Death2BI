"""Public entry points for the bounded Python DAX evaluator."""
import time
from decimal import Decimal
from dax_core import Parser, qi, sv, CoreEvaluator
from dax_runtime import RuntimeEvaluator as Evaluator
from dax_budget import limits, check_budget

def _sql_safety_diagnostics(budget):
 result={}
 if budget.get('sqlSafetyFallbacks'):
  result.update({'sqlSafetyFallbacks':budget['sqlSafetyFallbacks'],'sqlSafetyReasons':budget.get('sqlSafetyReasons',[])[:8]})
 if budget.get('staged_summary_groups'):
  result.update({'stagedSummaryGroups':budget['staged_summary_groups'],'stagedSummaryLeaves':budget.get('staged_summary_leaves',0)})
 return result

def evaluate_visual(con,model,payload):
 if payload.get('operation')=='formats':return evaluate_formats(con,model,payload)
 if payload.get('operation')=='topN':return evaluate_topn(con,model,payload)
 groups=payload['groups']; fields=payload['fields']
 # SelectRef is a visual-result binding, not a semantic-model column. The
 # presentation engine resolves these summaries after the visual query.
 for field in fields:
  if 'Aggregation' in field:
   aggregate=field['Aggregation'];expression=aggregate.get('Expression') if isinstance(aggregate,dict) else None;column=expression.get('Column') if isinstance(expression,dict) else None
   source=column.get('Expression') if isinstance(column,dict) else None;source=source.get('SourceRef') if isinstance(source,dict) else None
   if not isinstance(source,dict) or not source.get('Entity') or not column.get('Property') or aggregate.get('Function') not in range(7):
    raise ValueError('Unsupported model aggregation: expected a qualified model column; visual series references require rendered-result evaluation')
 if 'baseFilters' in payload:
  base=payload['baseFilters']
  groups=[{**g,'filters':[*base,*g.get('filters',[])],'externalFilters':base} for g in groups]
  payload={**payload,'groups':groups}
 if len(groups)>10000 or len(fields)>50: raise ValueError('Python visual limit exceeded')
 seconds,max_steps=limits(); started=time.monotonic()
 rows=[]; budget={'deadline':started+seconds,'started':started,'seconds':seconds,'max_steps':max_steps,'steps':0}
 from dax_sql import evaluate_groups, UnsupportedSql
 try:
  budget['location']='batched visual groups'
  batched=[]
  for offset in range(0,len(groups),64):
   chunk=groups[offset:offset+64]
   batched.extend(evaluate_groups(con,model,{**payload,'groups':chunk},budget))
 except UnsupportedSql:batched=None
 if batched is not None:
  return {'columns':['v'+str(i) for i in range(len(fields))],'types':['DOUBLE' if any(isinstance(r[i],(int,float,Decimal)) for r in batched) else 'VARCHAR' for i in range(len(fields))],'rows':batched,'truncated':False,'evaluation':{'elapsedSeconds':round(time.monotonic()-started,3),'steps':budget['steps'],'timeLimitSeconds':seconds,'stepLimit':max_steps,'execution':'batched SQL',**_sql_safety_diagnostics(budget)}}
 for group_index,group in enumerate(groups):
  check_budget(budget)
  engine=Evaluator(con,model,group.get('contexts',{}),filters=group.get('filters'),budget=budget); engine.scope=[tuple(c) for c in group.get('scope',[])]; engine.external_filters=group.get('externalFilters',group.get('filters')); result=[]
  for i,f in enumerate(fields):
   budget['location']=f"{f.get('Measure',{}).get('Property', 'field '+str(i+1))}, group {group_index+1}/{len(groups)}"
   if f.get('Measure'):
    from dax_sql import evaluate_scalar, UnsupportedSql
    name=f['Measure']['Property'];table=f['Measure'].get('Expression',{}).get('SourceRef',{}).get('Entity')
    try:value=evaluate_scalar(engine,name,table)
    except UnsupportedSql:value=engine.measure(name,table)
    result.append(value)
   elif f.get('GeoMean'):
    g=f['GeoMean'];table=engine.canonical_table(g['table'])
    for key in ('column','latitude','longitude'):engine.column(('col',table,g[key]))
    if g['column'] not in (g['latitude'],g['longitude']):raise ValueError('Invalid geographic mean field')
    where=engine.where(table);engine.check_budget()
    result.append(con.execute('SELECT AVG(CASE WHEN '+qi(g['latitude'])+' BETWEEN -90 AND 90 AND '+qi(g['longitude'])+' BETWEEN -180 AND 180 THEN '+qi(g['column'])+' END) FROM '+qi(table)+(' WHERE '+where if where else '')).fetchone()[0])
   elif f.get('SparklineData'): result.append(evaluate_sparkline(engine,f['SparklineData']))
   elif f.get('Column') or f.get('GroupRef'): result.append(group['values'][str(i)])
   elif f.get('Aggregation'):
    a=f['Aggregation']; c=a['Expression']['Column']; fn={0:'SUM',1:'AVERAGE',2:'DISTINCTCOUNT',3:'MIN',4:'MAX',5:'COUNTA',6:'MEDIAN'}[a['Function']]
    result.append(engine.run(('call',fn,[('col',c['Expression']['SourceRef']['Entity'],c['Property'])]),{},None))
   else: raise ValueError('Python DAX visual field is not supported')
  check_budget(budget)
  rows.append(result)
 return {'columns':['v'+str(i) for i in range(len(fields))],'types':['DOUBLE' if any(isinstance(r[i],(int,float,Decimal)) for r in rows) else 'VARCHAR' for i in range(len(fields))],'rows':rows,'truncated':False,'evaluation':{'elapsedSeconds':round(time.monotonic()-started,3),'steps':budget['steps'],'timeLimitSeconds':seconds,'stepLimit':max_steps,**_sql_safety_diagnostics(budget)}}



def evaluate_topn(con,model,payload):
    """Evaluate measured Top N before the visual preview/group limit applies."""
    seconds,max_steps=limits();started=time.monotonic()
    budget={'deadline':started+seconds,'started':started,'seconds':seconds,'max_steps':max_steps,'steps':0,'location':'DAX Top N filter'}
    category=payload['category'].get('Column') or payload['category'].get('GroupRef');by=payload['by'];count=payload['count']
    if not category:raise ValueError('Top N category must be a model column')
    if not isinstance(count,int) or not 1<=count<=10000:raise ValueError('Top N count must be between 1 and 10,000')
    filters=payload.get('filters',[]);engine=Evaluator(con,model,{},filters=filters,budget=budget)
    table,col=engine.column(('col',category['Expression']['SourceRef']['Entity'],category['Property']))
    engine.external_filters=filters;engine.scope=[(table,col)]
    where=engine.where(table)
    values=con.execute('SELECT DISTINCT '+qi(col)+' FROM '+qi(table)+(' WHERE '+where if where else '')+' LIMIT 100001').fetchall()
    if len(values)>100000:raise ValueError('Top N category domain exceeds 100,000 rows')
    scored=[]
    from dax_sql import evaluate_groups,UnsupportedSql
    try:
        groups=[{'values':{'0':value},'filters':[*filters,{'table':table,'columns':[col],'sql':qi(table)+'.'+qi(col)+(' IS NULL' if value is None else ' = '+sv(value))}],'externalFilters':filters,'scope':[(table,col)]} for (value,) in values]
        # Let DuckDB score the entire secured domain in one relational plan.
        # Large identities use an Arrow-backed temporary relation, not thousands
        # of repeated scalar queries or a huge VALUES expression.
        results=evaluate_groups(con,model,{'groups':groups,'fields':[{'Column':category},by]},budget) if groups else []
        scored.extend((value,score) for value,score in results if score is not None)
        candidates=[]
    except UnsupportedSql:candidates=values;scored=[]
    for (value,) in candidates:
        check_budget(budget)
        child=engine.child([*filters,engine.value_filter([(table,col)],[[value]])])
        if 'Measure' in by:
            m=by['Measure'];score=child.measure(m['Property'],m.get('Expression',{}).get('SourceRef',{}).get('Entity'))
        elif 'Aggregation' in by:
            a=by['Aggregation'];c=a['Expression']['Column'];fn={0:'SUM',1:'AVERAGE',2:'DISTINCTCOUNT',3:'MIN',4:'MAX',5:'COUNTA',6:'MEDIAN'}[a['Function']]
            score=child.run(('call',fn,[('col',c['Expression']['SourceRef']['Entity'],c['Property'])]),{},None)
        else:raise ValueError('Top N sort must be a measure or aggregate')
        if score is not None:scored.append((value,score))
    scored.sort(key=lambda r:r[1],reverse=payload.get('descending',True))
    chosen=scored[:count]
    if chosen:
        boundary=chosen[-1][1];chosen.extend(r for r in scored[count:] if r[1]==boundary)
    check_budget(budget)
    return {'values':[r[0] for r in chosen],'evaluation':{'elapsedSeconds':round(time.monotonic()-started,3),'steps':budget['steps'],**_sql_safety_diagnostics(budget)}}


def evaluate_sparkline(engine,definition):
    """Evaluate bounded time-series cells in the same secured filter context."""
    grouping=definition.get('Groupings',[]);field=definition.get('Measure',{})
    if len(grouping)!=1 or not grouping[0].get('Column') or not (field.get('Measure') or field.get('Aggregation')):
        raise ValueError('Sparkline requires one model column and a measure')
    c=grouping[0]['Column'];table,col=engine.column(('col',c['Expression']['SourceRef']['Entity'],c['Property']))
    where=engine.where(table);engine.check_budget()
    if field.get('Aggregation'):
        a=field['Aggregation'];column=a.get('Expression',{}).get('Column')
        if not column:raise ValueError('Sparkline aggregate requires a model column')
        target,metric=engine.column(('col',column['Expression']['SourceRef']['Entity'],column['Property']))
        if target!=table:raise ValueError('Sparkline aggregate requires grouping and value columns from the same table')
        fn={0:'SUM',1:'AVG',2:'COUNT_DISTINCT',3:'MIN',4:'MAX',5:'COUNT',6:'MEDIAN'}.get(a['Function'])
        if not fn:raise ValueError('Unsupported sparkline aggregation')
        aggregate='COUNT(DISTINCT '+qi(metric)+')' if fn=='COUNT_DISTINCT' else fn+'('+qi(metric)+')'
        engine.check_budget()
        points=engine.con.execute('SELECT '+qi(col)+','+aggregate+' FROM '+qi(table)+(' WHERE '+where if where else '')+' GROUP BY '+qi(col)+' ORDER BY '+qi(col)+' LIMIT 2001').fetchall()
        if len(points)>2000:raise ValueError('Sparkline exceeds 2,000 points per cell')
        return {'sparkline':[list(p) for p in points]}
    values=engine.con.execute('SELECT DISTINCT '+qi(col)+' FROM '+qi(table)+(' WHERE '+where if where else '')+' ORDER BY 1 LIMIT 2001').fetchall()
    if len(values)>2000:raise ValueError('Sparkline exceeds 2,000 points per cell')
    m=field['Measure'];points=[]
    from dax_sql import evaluate_scalar,UnsupportedSql
    for (x,) in values:
        engine.check_budget()
        child=engine.child([*engine.require_filters(),engine.value_filter([(table,col)],[[x]])]);child.external_filters=engine.external_filters
        try:y=evaluate_scalar(child,m['Property'],m.get('Expression',{}).get('SourceRef',{}).get('Entity'))
        except UnsupportedSql:y=child.measure(m['Property'],m.get('Expression',{}).get('SourceRef',{}).get('Entity'))
        points.append([x,y])
    return {'sparkline':points}


def evaluate_formats(con,model,payload):
    """Evaluate stored format expressions in the same group/filter context as values."""
    groups=payload.get('groups',[]);fields=payload.get('fields',[])
    if len(groups)>10000 or len(fields)>50:raise ValueError('Dynamic format visual limit exceeded')
    seconds,max_steps=limits();started=time.monotonic()
    budget={'deadline':started+seconds,'started':started,'seconds':seconds,'max_steps':max_steps,'steps':0,'location':'dynamic format strings'}
    output=[];warnings=[]
    for group in groups:
        check_budget(budget)
        base=payload.get('baseFilters',[])
        engine=Evaluator(con,model,group.get('contexts',{}),filters=[*base,*group.get('filters',[])],budget=budget)
        engine.external_filters=base;engine.scope=[tuple(x) for x in group.get('scope',[])]
        formats=[]
        for i,field in enumerate(fields):
            measure=field.get('Measure',{});table=measure.get('Expression',{}).get('SourceRef',{}).get('Entity')
            matches=[m for m in model.get('measures',[]) if m['Name']==measure.get('Property') and (not table or m['TableName']==table)]
            definition=matches[0] if len(matches)==1 else {};expression=definition.get('FormatStringExpression')
            if not expression:formats.append(None);continue
            engine.selected_measure=(group.get('measureValues') or [None]*len(fields))[i]
            engine.selected_measure_name=definition['Name'];engine.selected_measure_format=definition.get('FormatString','')
            try:
                value=engine.scalar(engine.run(Parser(expression,model.get('functions',[])).parse(),{},None))
                if value is not None and not isinstance(value,str):raise ValueError('Format expression must return text')
                formats.append(value)
            except ValueError as exc:
                check_budget(budget)
                warnings.append(definition['Name']+': '+str(exc));formats.append(None)
        output.append(formats)
    return {'rowFormats':output,'warnings':list(dict.fromkeys(warnings))[:20]}
