"""Staged, request-local evaluation of physical SUMMARIZE extensions.

Each grouped scan contains only a proven aggregate leaf. Complex nested
extensions keep the interpreter and its original context-transition semantics.
"""
from dax_core import cached_ast
from dax_sql import UnsupportedSql
from dax_runtime import Table


_AGGREGATES={'SUM','AVERAGE','MIN','MAX','COUNT','COUNTA','DISTINCTCOUNT','MEDIAN'}
_PURE=_AGGREGATES|{'SUMX','AVERAGEX','MINX','MAXX','MEDIANX','FILTER','ISBLANK','NOT','BLANK'}


def _expand(node,bindings=None):
    """Substitute lexical aliases only for the small aggregate-leaf grammar."""
    bindings={} if bindings is None else bindings
    kind=node[0]
    if kind=='name':return bindings.get(node[1].casefold(),node)
    if kind=='let':
        local=dict(bindings)
        for name,value in node[1]:local[name.casefold()]=_expand(value,local)
        return _expand(node[2],local)
    if kind=='call':return ('call',node[1],[_expand(x,bindings) for x in node[2]])
    if kind in ('op','unary'):return (*node[:2],*[_expand(x,bindings) for x in node[2:]])
    return node


def _pure(node):
    kind=node[0]
    if kind in ('lit','name','col'):return True
    if kind=='let':return all(_pure(value) for name,value in node[1]) and _pure(node[2])
    if kind=='call':return node[1] in _PURE and all(_pure(x) for x in node[2])
    if kind=='op':return node[1] in ('=','==','<>','<','>','<=','>=','&&','||') and all(_pure(x) for x in node[2:])
    return False


def _leaf(engine,measure):
    source=cached_ast(engine,measure['Expression'])
    if not _pure(source):return None
    node=_expand(source)
    if node[0]!='call':return None
    fn,args=node[1:]
    if fn in _AGGREGATES and len(args)==1 and args[0][0]=='col' and args[0][1]:return node
    if fn in ('SUMX','AVERAGEX','MINX','MAXX','MEDIANX') and len(args)==2 and args[1][0]=='col':
        source=args[0]
        if source[0]=='call' and source[1]=='FILTER' and len(source[2])==2 and source[2][0][0]=='name':return node
    return None


def _dependencies(engine,expressions):
    found={}
    def visit(node,seen=frozenset()):
        if node[0]=='col':
            matches=[m for m in engine.model['measures'] if m['Name'].casefold()==node[2].casefold() and (not node[1] or m['TableName'].casefold()==node[1].casefold())]
            if len(matches)==1:
                measure=matches[0];key=(measure['TableName'],measure['Name'])
                if key in seen or len(seen)>=30:return
                try:expression=_leaf(engine,measure)
                except ValueError:return  # An invalid dormant dependency stays dormant.
                if expression is not None:found[key]=(measure,expression)
                else:visit(cached_ast(engine,measure['Expression']),seen|{key})
        elif node[0]=='call':
            for value in node[2]:visit(value,seen)
        elif node[0]=='let':
            for name,value in node[1]:visit(value,seen)
            visit(node[2],seen)
        elif node[0] in ('op','unary'):
            for value in node[2:]:visit(value,seen)
    for expression in expressions:visit(expression)
    return list(found.values())[:32]


def _projection_columns(engine,table,expressions):
    """Physical single-column domains needed by interpreted aggregate leaves."""
    found=set()
    def visit(node,seen=frozenset()):
        if node[0]=='col':
            matches=[m for m in engine.model['measures'] if m['Name'].casefold()==node[2].casefold() and (not node[1] or m['TableName'].casefold()==node[1].casefold())]
            if len(matches)==1:
                measure=matches[0];key=(measure['TableName'],measure['Name'])
                if key not in seen and len(seen)<30:
                    try:expression=cached_ast(engine,measure['Expression'])
                    except ValueError:return
                    visit(expression,seen|{key})
            elif node[1] and node[1].casefold()==table.casefold():
                try:found.add(engine.column(node)[1])
                except ValueError:return
        elif node[0]=='call':
            for value in node[2]:visit(value,seen)
        elif node[0]=='let':
            for name,value in node[1]:visit(value,seen)
            visit(node[2],seen)
        elif node[0] in ('op','unary'):
            for value in node[2:]:visit(value,seen)
    for expression in expressions:visit(expression)
    return list(found)[:50]


def _remember_projection(engine,table,column,where,members):
    rows=tuple((row[1][column],) for row in members)
    cells=len(rows);size=len(where)*2+sum(len(row[0])*2 if isinstance(row[0],str) else len(row[0]) if isinstance(row[0],bytes) else 32 for row in rows)
    if cells>200000 or size>16000000:return
    cache=engine.budget.setdefault('projected_columns',{});key=(table,((table,column),),False,where)
    if key in cache:return
    total_cells=engine.budget.get('projected_column_cells',0);total_bytes=engine.budget.get('projected_column_bytes',0)
    while cache and (len(cache)>=128 or total_cells+cells>200000 or total_bytes+size>16000000):
        _,old_cells,old_size=cache.pop(next(iter(cache)));total_cells-=old_cells;total_bytes-=old_size
    cache[key]=(rows,cells,size)
    engine.budget['projected_column_cells']=total_cells+cells
    engine.budget['projected_column_bytes']=total_bytes+size


def _remember(engine,name,table,value):
    cache=engine.budget.setdefault('measure_values',{});key=engine.measure_cache_key(name,table)
    if key in cache:return
    size=len(value) if isinstance(value,str) else 32
    total=engine.budget.get('measure_cache_bytes',0)
    while cache and (len(cache)>=2000 or total+size>=32000000):
        old=cache.pop(next(iter(cache)));total-=len(old) if isinstance(old,str) else 32
    if total+size<32000000:cache[key]=value;total+=size
    engine.budget['measure_cache_bytes']=total


def extensions(engine,source,table,columns,groups,names,expressions,env):
    """Evaluate each extension across actual groups, declining rich row scopes."""
    if engine.iterator_depth or engine.row_stack or engine.selection_shadows or not names or len(groups)<2:
        raise UnsupportedSql('Staged summary requires a direct physical group domain')
    if len(groups)>100000 or len(columns)>8 or any(t!=table for t,c in columns):
        raise UnsupportedSql('Staged summary dimensions')
    if len(groups)*(len(columns)+len(names))>2000000:
        raise UnsupportedSql('Staged summary cell budget')
    if any(r.get('IsActive') and r.get('Cardinality') in ('M:1','1:1') and (r['FromTableName'],r['FromColumnName']) in columns for r in engine.model.get('relationships',[])):
        raise UnsupportedSql('Staged summary needs expanded row transitions')
    if any(len(row)!=2 or row[0]!=table for row in source):raise UnsupportedSql('Staged summary physical source')
    from dax_grouped import evaluate_context_rows
    import duckdb
    projected=Table([(table,dict(zip([c for t,c in columns],key))) for key,members in groups.values()],columns)
    leaves=[]
    dependencies=_dependencies(engine,expressions)
    if len(projected)*len(dependencies)>2000000:dependencies=[]
    for measure,expression in dependencies:
        try:
            # An explicit transition is identical to the implicit measure
            # transition here; the small leaf compiler validates its contents.
            values=evaluate_context_rows(engine,projected,[('call','CALCULATE',[expression])])
            leaves.append((measure,[value[0] for value in values]))
        except duckdb.InterruptException:raise
        except (ValueError,ArithmeticError,duckdb.Error):
            # Speculative prefetch must not surface errors from dormant branches.
            engine.check_budget()
    computed=[]
    for expression in expressions:
        try:computed.append(evaluate_context_rows(engine,projected,[expression],env))
        except duckdb.InterruptException:raise
        except (ValueError,ArithmeticError,duckdb.Error):
            # A compiler can visit both sides of a lazy conditional. Let each
            # original group decide whether a source/numeric error is live.
            engine.check_budget();computed.append(None)
    projection_columns=_projection_columns(engine,table,expressions)
    result=[]
    for index,(key,members) in enumerate(groups.values()):
        engine.check_budget();lineage=dict(zip(columns,key));values={c:v for (t,c),v in lineage.items()}
        child=engine.child(engine.transition(('__summary',values,lineage)))
        for measure,leaf_values in leaves:
            if sum(m['Name'].casefold()==measure['Name'].casefold() for m in engine.model['measures'])==1:
                _remember(child,measure['Name'],None,leaf_values[index])
            _remember(child,measure['Name'],measure['TableName'],leaf_values[index])
        # The original secured source already contains these complete rows.
        # Restrict to the exact representative identity used by transition,
        # since DAX grouping folds text case but SQL row filters may not.
        exact=[row for row in members if all(row[1][c]==value for (t,c),value in lineage.items())]
        shared=engine.budget.setdefault('tables',{});where=child.where(table)
        while shared and (len(shared)>=64 or sum(len(rows) for rows in shared.values())+len(exact)>200000):shared.pop(next(iter(shared)))
        if len(exact)<=100000:shared[table,where]=Table(exact,source.columns)
        for column in projection_columns:_remember_projection(child,table,column,where,exact)
        for j,name in enumerate(names):
            values[name]=computed[j][index][0] if computed[j] is not None else child.scalar(child.run(expressions[j],env,None))
        result.append(('__summary',values,lineage))
    engine.budget['staged_summary_groups']=engine.budget.get('staged_summary_groups',0)+len(result)
    engine.budget['staged_summary_leaves']=engine.budget.get('staged_summary_leaves',0)+len(leaves)
    return Table(result,columns+[('__virtual',name) for name in names])
