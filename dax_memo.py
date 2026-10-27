"""Request-local reuse of scalar expressions after CALCULATE establishes context."""
from dax_core import Parser

def calculate_value(engine,node,env):
    from dax_runtime import SPECIAL, FUNCTIONS
    names=set()
    def collect(n):
        if n[0]=='name':names.add(n[1].casefold())
        elif n[0]=='call':
            for a in n[2]:collect(a)
        elif n[0]=='let':
            for name,a in n[1]:collect(a)
            collect(n[2])
        elif n[0] in ('op','unary'):
            for a in n[2:]:collect(a)
        elif n[0] in ('tuple','table'):
            for a in n[1]:collect(a)
    collect(node)
    bindings={k:v for k,v in env.items() if k.casefold() in names}
    if any(v is not None and not isinstance(v,(bool,int,float,str)) for v in bindings.values()):return engine.run(node,env,None)
    def deterministic(n,seen=frozenset()):
        if n[0]=='call':
            if n[1] in ('RAND','RANDBETWEEN','NOW','TODAY','UTCNOW','UTCTODAY') or n[1] not in SPECIAL and n[1] not in FUNCTIONS:return False
            return all(deterministic(a,seen) for a in n[2])
        if n[0]=='col':
            matches=[m for m in engine.model['measures'] if m['Name'].casefold()==n[2].casefold() and (not n[1] or m['TableName'].casefold()==n[1].casefold())]
            if len(matches)==1:
                measure=matches[0];identity=(measure['TableName'],measure['Name'])
                if identity in seen:return False
                expression=measure['Expression'].strip().lstrip('=');asts=engine.budget.setdefault('asts',{})
                if expression not in asts:asts[expression]=Parser(expression,engine.model.get('functions',[])).parse()
                return deterministic(asts[expression],seen|{identity})
        if n[0]=='let':return all(deterministic(a,seen) for name,a in n[1]) and deterministic(n[2],seen)
        if n[0] in ('op','unary'):return all(deterministic(a,seen) for a in n[2:])
        if n[0] in ('tuple','table'):return all(deterministic(a,seen) for a in n[1])
        return True
    eligibility=engine.budget.setdefault('calculation_memo_eligibility',{});definition=repr(node)
    if definition not in eligibility:eligibility[definition]=deterministic(node)
    if not eligibility[definition]:return engine.run(node,env,None)
    key=(definition,repr(sorted(bindings.items())),repr(engine.filters),repr(engine.contexts),repr(engine.scope),repr(engine.external_filters),engine.iterator_depth,repr(engine.row_stack),repr(engine.model.get('relationships',[])),engine.selection_shadow_stamp(),engine.stack[-1][0] if engine.stack else None,repr(tuple(getattr(engine,k,None) for k in ('selected_measure','selected_measure_name','selected_measure_format'))))
    cache=engine.budget.setdefault('calculation_values',{})
    if key in cache:
        engine.budget['calculation_cache_hits']=engine.budget.get('calculation_cache_hits',0)+1
        return cache[key]
    from dax_sql import evaluate_expression,UnsupportedSql
    try:result=evaluate_expression(engine,node,env)
    except UnsupportedSql:result=engine.run(node,env,None)
    size=sum(len(str(part)) for part in key)+(len(result.encode('utf-8')) if isinstance(result,str) else 32)
    if (result is None or isinstance(result,(bool,int,float,str))) and len(cache)<2000 and engine.budget.get('calculation_cache_bytes',0)+size<=16000000:
        cache[key]=result;engine.budget['calculation_cache_bytes']=engine.budget.get('calculation_cache_bytes',0)+size
    return result
