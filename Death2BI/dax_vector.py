"""Bounded SQL aggregation over materialized, secured iterator rowsets."""
import uuid
import threading
from dax_metadata import schema as model_schema, type_name
from dax_core import qi,sv
from dax_sql import UnsupportedSql

def cumulative_columns(engine,rows,expressions):
    """Selected-table running sums, including ties, without per-row rescans."""
    if engine.iterator_depth or engine.row_stack or engine.filters!=engine.external_filters or not rows.columns or len({t for t,c in rows.columns})!=1:raise UnsupportedSql('Cumulative shadow context')
    table=rows.columns[0][0];plans=[]
    # The window plan reads a secured physical table. Virtual rows, including
    # generated Value columns and SELECTCOLUMNS aliases, belong to the normal
    # row interpreter and must never be resolved as model-column metadata.
    if table.startswith('__') or any(r[0].startswith('__') for r in rows):raise UnsupportedSql('Virtual cumulative domain')
    for node in expressions:
        if node[0]!='let' or len(node[1])!=1:raise UnsupportedSql('Cumulative binding')
        name,key=node[1][0];calc=node[2]
        if key[0]!='col' or calc[0]!='call' or calc[1]!='CALCULATE' or len(calc[2])!=3:raise UnsupportedSql('Cumulative calculation')
        if engine.column(key)[0]!=table:raise UnsupportedSql('Cumulative calculation')
        agg,modifier,predicate=calc[2]
        if agg[0]!='call' or agg[1]!='SUMX' or agg[2][0][0]!='name' or engine.canonical_table(agg[2][0][1])!=table or agg[2][1][0]!='col' or engine.column(agg[2][1])[0]!=table:raise UnsupportedSql('Cumulative sum')
        if modifier!=('call','ALLSELECTED',[('name',table)]) or predicate[0]!='op' or predicate[1]!='<=' or predicate[2]!=key or predicate[3]!=('name',name):raise UnsupportedSql('Cumulative selected domain')
        plans.append((key[2],agg[2][1][2]))
    where=engine.where(table);domain=qi(table)+(' WHERE '+where if where else '')
    if engine.con.execute('SELECT COUNT(*) FROM '+domain).fetchone()[0]!=len(rows):raise UnsupportedSql('Partial cumulative rowset')
    schema={d[0]:str(d[1]) for d in model_schema(engine,table)}
    for key,column in plans:
        if not all(schema[c].startswith(('TINYINT','SMALLINT','INTEGER','BIGINT','HUGEINT','UTINYINT','USMALLINT','UINTEGER','UBIGINT','FLOAT','DOUBLE','DECIMAL')) for c in (key,column)):raise UnsupportedSql('Non-numeric cumulative columns')
        if engine.con.execute('SELECT 1 FROM '+domain+(' AND ' if where else ' WHERE ')+qi(key)+' IS NULL LIMIT 1').fetchone():raise UnsupportedSql('Blank cumulative rank')
    output=[[] for r in rows]
    for key,column in plans:
        sql='SELECT '+qi(key)+',SUM(SUM('+qi(column)+')) OVER (ORDER BY '+qi(key)+' RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM '+domain+' GROUP BY '+qi(key)
        totals=dict(engine.con.execute(sql).fetchall());engine.check_budget()
        for values,r in zip(output,rows):values.append(totals.get(r[1][key]))
    return output

def sum_rows(engine,rows,expression,env):
    if not rows.columns or len({t for t,c in rows.columns})!=1:raise UnsupportedSql('Vector lineage')
    source=rows.columns[0][0]
    if source.startswith('__'):raise UnsupportedSql('Virtual vector lineage')
    mapping={c:'__rows.'+qi(c) for t,c in rows.columns}
    def scalar(n,bindings,rowmap,table):
        kind=n[0]
        if kind=='lit':return sv(n[1])
        if kind=='name' and n[1].casefold() in bindings:return bindings[n[1].casefold()]
        if kind=='col' and (not n[1] or engine.canonical_table(n[1])==table) and n[2] in rowmap:return rowmap[n[2]]
        if kind=='let':
            local=dict(bindings)
            for name,value in n[1]:local[name.casefold()]=scalar(value,local,rowmap,table)
            return scalar(n[2],local,rowmap,table)
        if kind=='op' and n[1] in ('+','-','*','/'):
            a,b=(scalar(x,bindings,rowmap,table) for x in n[2:])
            if n[1] in ('+','-'):a='COALESCE('+a+',0)';b='COALESCE('+b+',0)'
            return '('+a+n[1]+('NULLIF('+b+',0)' if n[1]=='/' else b)+')'
        if kind=='call' and n[1]=='CALCULATE':
            args=n[2];aggregate=args[0]
            if aggregate[0]!='call' or aggregate[1] not in ('SUMX','SUM','MIN','MAX'):raise UnsupportedSql('Vector lookup aggregate')
            if aggregate[1]=='SUMX' and aggregate[2][0][0]=='name':target=engine.canonical_table(aggregate[2][0][1])
            elif aggregate[1]!='SUMX' and aggregate[2][0][0]=='col':target=engine.column(aggregate[2][0])[0]
            else:raise UnsupportedSql('Vector lookup target')
            clears=[a for a in args[1:] if a[0]=='call' and a[1] in ('ALL','REMOVEFILTERS') and len(a[2])==1 and a[2][0][0]=='name' and engine.canonical_table(a[2][0][1])==target]
            if len(clears)!=1:raise UnsupportedSql('Vector lookup requires explicit table removal')
            removed=engine.expanded(target);remaining=engine.expanded(source)-removed
            conditions=[]
            key_pairs=[]
            for a in args[1:]:
                if a in clears:continue
                if a[0]!='op' or a[1] not in ('=','==') or a[2][0]!='col' or engine.column(a[2])[0]!=target:raise UnsupportedSql('Vector lookup predicate')
                rhs=scalar(a[3],bindings,rowmap,table)
                key_pairs.append((a[2][2],rhs))
                conditions.append(qi(target)+'.'+qi(a[2][2])+' IS NOT DISTINCT FROM '+rhs)
            if not conditions:raise UnsupportedSql('Vector lookup needs a key predicate')
            for relationship in engine.model.get('relationships',[]):
                if relationship.get('IsActive') and relationship['FromTableName']==target and relationship['ToTableName'] in remaining:
                    if relationship['ToTableName']!=source or (relationship['FromColumnName'],mapping.get(relationship['ToColumnName'])) not in key_pairs:raise UnsupportedSql('Vector lookup retains expanded row filters')
            child=engine.child(engine.remove([],list(removed)));where=child.where(target)
            if where:conditions.append('('+where+')')
            cols=[d[0] for d in model_schema(engine,target)]
            targetmap={c:qi(target)+'.'+qi(c) for c in cols}
            value=scalar(aggregate[2][1] if aggregate[1]=='SUMX' else aggregate[2][0],{},targetmap,target)
            fn='SUM' if aggregate[1]=='SUMX' else aggregate[1]
            return '(SELECT '+fn+'('+value+') FROM '+qi(target)+' WHERE '+' AND '.join(conditions)+')'
        raise UnsupportedSql('Vector row expression')
    bindings={k:sv(v) for k,v in env.items() if v is None or isinstance(v,(bool,int,float,str))}
    body=scalar(expression,bindings,mapping,source)
    if not rows:return None
    import pyarrow as pa
    name='__vector_'+uuid.uuid4().hex
    arrow=pa.Table.from_pylist([r[1] for r in rows])
    engine.check_budget();engine.con.register(name,arrow)
    timer=threading.Timer(max(.001,engine.budget['deadline']-__import__('time').monotonic()),engine.con.interrupt);timer.daemon=True;timer.start()
    try:
        import duckdb
        try:return engine.con.execute('SELECT SUM('+body+') FROM '+qi(name)+' AS __rows').fetchone()[0]
        except duckdb.BinderException as exc:raise UnsupportedSql('Non-numeric vector aggregate') from exc
    finally:timer.cancel();engine.con.unregister(name);engine.check_budget()
