"""Table, relationship, ranking and classic date-column DAX functions."""
import datetime as dt
import itertools
import math
import calendar
import bisect
from dax_runtime import Table
from dax_core import qi
from dax_functions import text, number, date, integer


def filtered_extensions(e, source, predicate, env, outer):
    """Evaluate only extension columns needed at each AND filter stage."""
    from dax_sql import add_columns, UnsupportedSql
    if source[0]!='call' or source[1]!='ADDCOLUMNS' or outer is not None:
        raise UnsupportedSql('Staged extension source')
    args=source[2]
    if len(args[1:])%2:raise UnsupportedSql('Extension pairs')
    base=e.as_table(e.run(args[0],env,None))
    names=[text(e.scalar(e.run(x,env,None))) for x in args[1::2]]
    if len(set(x.casefold() for x in names))!=len(names) or any(c.casefold() in {x.casefold() for x in names} for t,c in base.columns):
        raise UnsupportedSql('Conflicting extension names')
    definitions=dict(zip(names,args[2::2]));computed={};selected=list(range(len(base)))
    def references(n):
        if n[0]=='col' and not n[1]:return {n[2].casefold()}
        if n[0]=='op':return references(n[2])|references(n[3])
        if n[0]=='call':return set().union(*(references(x) for x in n[2]))
        return set()
    def clauses(n):
        return clauses(n[2])+clauses(n[3]) if n[0]=='op' and n[1]=='&&' else [n]
    def compute(needed):
        needed=[name for name in needed if name not in computed]
        if not needed:return
        subset=Table([base[i] for i in selected],base.columns)
        try:values=add_columns(e,subset,[definitions[name] for name in needed])
        except UnsupportedSql:
            values=[[e.scalar(e.run(definitions[name],env,(*r,))) for name in needed] for r in subset]
        for j,name in enumerate(needed):computed[name]={i:values[k][j] for k,i in enumerate(selected)}
    def expanded(i):
        r=base[i];values={**r[1],**{name:column[i] for name,column in computed.items()}}
        lineage=dict(r[2]) if len(r)>2 else {(t,c):r[1][c] for t,c in base.columns if not t.startswith('__')}
        return ('__virtual',values,lineage)
    for clause in clauses(predicate):
        needed=references(clause);compute([name for name in names if name.casefold() in needed])
        selected=[i for i in selected if e.scalar(e.run(clause,env,expanded(i)))]
    compute(names)
    return Table([expanded(i) for i in selected],list(base.columns)+[('__virtual',name) for name in names])


def dispatch(e, fn, args, env, row):
    ev = lambda n: e.run(n, env, row)
    if fn == 'CONTAINS':
        if len(args)%2!=1:raise ValueError('CONTAINS requires column/value pairs')
        source=e.as_table(ev(args[0]));tests=[]
        for i in range(1,len(args),2):
            node=args[i]
            if node[0]!='col':raise ValueError('CONTAINS requires column references')
            if node[1]:target=e.column(node)
            else:
                matches=[(t,c) for t,c in source.columns if c.casefold()==node[2].casefold()]
                if len(matches)!=1:raise ValueError('CONTAINS column is missing or ambiguous')
                target=matches[0]
            tests.append((target,e.scalar(ev(args[i+1]))))
        for candidate in source:
            e.check_budget()
            def get(target):
                if target in source.columns:return candidate[1][target[1]]
                if len(candidate)>2 and target in candidate[2]:return candidate[2][target]
                return dispatch(e,'RELATED',[('col',*target)],env,candidate)
            if all(e.equal(get(target),value,True) for target,value in tests):return True
        return False
    if fn == 'DATATABLE':
        if len(args)%2!=1 or args[-1][0]!='table':raise ValueError('DATATABLE requires name/type pairs and constant rows')
        aliases={'LOGICAL':'BOOLEAN','DECIMAL':'CURRENCY','INT64':'INTEGER','TEXT':'STRING'}
        names=[];types=[]
        for i in range(0,len(args)-1,2):
            if args[i][0]!='lit' or not isinstance(args[i][1],str) or args[i+1][0]!='name':raise ValueError('DATATABLE requires constant column names and data types')
            name=args[i][1];kind=args[i+1][1].upper();kind=aliases.get(kind,kind)
            if not name or name.casefold() in {x.casefold() for x in names}:raise ValueError('DATATABLE column names must be distinct')
            if kind not in ('STRING','INTEGER','DOUBLE','CURRENCY','DATETIME','BOOLEAN'):raise ValueError('Unsupported DATATABLE data type: '+kind)
            names.append(name);types.append(kind)
        nodes=args[-1][1]
        if len(nodes)>10000 or len(nodes)*len(names)>100000:raise ValueError('DATATABLE constant row limit exceeded')
        def constant(n):
            if n[0]=='lit':return True
            if n[0]=='name' and n[1].upper() in ('TRUE','FALSE'):return True
            if n[0]=='unary' and n[1] in ('+','-'):return constant(n[2])
            if n[0]=='op' and n[1]=='+':return constant(n[2]) and constant(n[3])
            if n[0]=='call' and n[1] in ('DATE','TIME','BLANK','TRUE','FALSE'):return all(constant(x) for x in n[2])
            return False
        rows=[]
        from decimal import Decimal,ROUND_HALF_UP
        for node in nodes:
            if node[0]!='table' or len(node[1])!=len(names):raise ValueError('DATATABLE row width must match the declared columns')
            values=[]
            for cell,kind in zip(node[1],types):
                if not constant(cell):raise ValueError('DATATABLE values must be constant expressions')
                value=e.scalar(ev(cell))
                if value is not None:
                    if kind=='STRING':value=text(value)
                    elif kind=='INTEGER':value=integer(value)
                    elif kind=='DOUBLE':value=float(number(value))
                    elif kind=='CURRENCY':value=Decimal(str(number(value))).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP)
                    elif kind=='DATETIME':value=date(value)
                    elif kind=='BOOLEAN':
                        if isinstance(value,str):
                            if value.casefold() not in ('true','false'):raise ValueError('Invalid DATATABLE boolean')
                            value=value.casefold()=='true'
                        else:value=bool(value)
                values.append(value)
            rows.append(('__virtual',dict(zip(names,values)),{}))
        return Table(rows,[('__virtual',name) for name in names])
    if fn == 'TREATAS':
        values=e.as_table(ev(args[0]))
        targets=[e.column(arg) for arg in args[1:]]
        if len(targets)!=len(values.columns):
            raise ValueError('TREATAS source and target column counts must match')
        if len(set(targets))!=len(targets) or len({table for table,col in targets})!=1:
            raise ValueError('TREATAS currently requires distinct columns from one target table')
        # Resolve against the secured database, ignoring ordinary filter context:
        # CALCULATE may replace that context, but must never bypass physical RLS.
        domains=e.budget.setdefault('treatas_domains',{})
        normalize=lambda value: value.casefold() if isinstance(value,str) else value
        for table,col in targets:
            if (table,col) not in domains:
                e.check_budget()
                available=e.con.execute('SELECT DISTINCT '+qi(col)+' FROM '+qi(table)+' LIMIT 100001').fetchall()
                if len(available)>100000:
                    raise ValueError('TREATAS target domain exceeds 100,000 values')
                domains[(table,col)]={normalize(item[0]):item[0] for item in available}
        result=[]
        for source in values:
            e.check_budget()
            raw=[source[1][original] for _,original in values.columns]
            if all(normalize(value) in domains[target] for target,value in zip(targets,raw)):
                result.append((targets[0][0],{dest:domains[(table,dest)][normalize(value)] for (table,dest),value in zip(targets,raw)}))
        return e.distinct(Table(result,targets))
    if fn=='SAMEPERIODLASTYEAR':
        table,col=e.column(args[0]); current=e.project(args[0],True)
        available=e.child([]).project(args[0],True)
        def day(value):
            if not isinstance(value,(dt.date,dt.datetime)) or date(value).time()!=dt.time():
                raise ValueError('SAMEPERIODLASTYEAR requires a typed date column at midnight')
            return date(value).date()
        full={day(r[1][col]) for r in available if r[1][col] is not None}
        selected={day(r[1][col]) for r in current if r[1][col] is not None}
        if full and len(full)!=(max(full)-min(full)).days+1:
            raise ValueError('SAMEPERIODLASTYEAR requires a continuous date table')
        if selected and len(selected)!=(max(selected)-min(selected)).days+1:
            raise ValueError('SAMEPERIODLASTYEAR requires a contiguous date selection')
        shifted={d.replace(year=d.year-1,day=min(d.day,calendar.monthrange(d.year-1,d.month)[1])) for d in selected}
        for d in selected:
            if d.day==calendar.monthrange(d.year,d.month)[1] and d-dt.timedelta(days=1) in selected:
                end=calendar.monthrange(d.year-1,d.month)[1]
                shifted.update(dt.date(d.year-1,d.month,n) for n in range(min(d.day,end),end+1))
        result=Table([r for r in available if r[1][col] is not None and day(r[1][col]) in shifted],[(table,col)])
        result.clear_date_table=table
        return result
    scalar = lambda n: e.scalar(ev(n))
    if fn == 'ISONORAFTER':
        i = 0
        while i < len(args):
            if i + 1 >= len(args):
                raise ValueError('ISONORAFTER requires expression/value pairs with optional sort direction')
            a, b = scalar(args[i]), scalar(args[i + 1])
            i += 2
            direction = 'ASC'
            if i < len(args) and args[i][0] == 'name' and args[i][1].upper() in ('ASC', 'DESC'):
                direction = args[i][1].upper()
                i += 1
            if e.equal(a, b):
                continue
            a, b = (0 if a is None else a), (0 if b is None else b)
            if isinstance(a, str) and isinstance(b, str):
                a, b = a.casefold(), b.casefold()
            return a > b if direction == 'ASC' else a < b
        return True
    if fn == 'CURRENTGROUP':
        if '__currentgroup_table__' not in env:raise ValueError('CURRENTGROUP is only valid inside GROUPBY extension expressions')
        return env['__currentgroup_table__']
    if fn == 'GROUPBY':
        source=e.as_table(ev(args[0]));cols=[];i=1
        while i<len(args) and args[i][0]=='col':
            node=args[i];matches=[(t,c) for t,c in source.columns if c.casefold()==node[2].casefold() and (not node[1] or t==node[1])]
            if len(matches)!=1:raise ValueError('GROUPBY column is missing or ambiguous')
            cols.append(matches[0]);i+=1
        pairs=args[i:]
        if len(pairs)%2:raise ValueError('GROUPBY requires name/expression pairs')
        names=[text(e.scalar(ev(pairs[j]))) for j in range(0,len(pairs),2)]
        if len({c.casefold() for t,c in cols}|{n.casefold() for n in names})!=len(cols)+len(names):raise ValueError('GROUPBY has duplicate output columns')
        groups={}
        for r in source:
            e.check_budget();key=tuple(r[1][c] for t,c in cols);norm=tuple(v.casefold() if isinstance(v,str) else v for v in key)
            groups.setdefault(norm,(key,[]))[1].append(r)
        result=[]
        for key,members in groups.values():
            e.check_budget();values={c:v for (t,c),v in zip(cols,key)};lineage=dict(zip(cols,key));local={**env,'__currentgroup_table__':Table(members,source.columns)}
            for j,name in enumerate(names):values[name]=e.scalar(e.run(pairs[j*2+1],local,row))
            result.append(('__group',values,lineage))
        return Table(result,cols+[('__virtual',n) for n in names])
    if fn == 'SUMMARIZE':
        source = e.as_table(ev(args[0]))
        source_tables={t for t,c in source.columns if not t.startswith('__')}
        table=next(iter(source_tables)) if len(source_tables)==1 else None
        cols, i = [], 1
        while i < len(args) and args[i][0] == 'col':
            if not args[i][1] and table is None:raise ValueError('SUMMARIZE grouping requires qualified model columns')
            node = args[i] if args[i][1] else ('col', table, args[i][2])
            cols.append(e.column(node))
            i += 1
        if not cols:
            raise ValueError('SUMMARIZE requires grouping columns')
        pairs = args[i:]
        if len(pairs) % 2:
            raise ValueError('SUMMARIZE requires name/expression pairs')
        names = [text(scalar(pairs[j])) for j in range(0, len(pairs), 2)]
        allnames = [c for t, c in cols] + names
        if len(set(n.casefold() for n in allnames)) != len(allnames):
            raise ValueError('SUMMARIZE has duplicate output column names')
        groups = {}
        for r in source:
            e.check_budget()
            def grouped(t,c):
                if (t,c) in source.columns:return r[1][c]
                if len(r)>2 and (t,c) in r[2]:return r[2][t,c]
                return dispatch(e, 'RELATED', [('col', t, c)], env, (*r,))
            key = tuple(grouped(t,c) for t,c in cols)
            norm = tuple(v.casefold() if isinstance(v, str) else v for v in key)
            groups.setdefault(norm, (key,[]))[1].append(r)
        if not names:
            # A grouping-only domain has no extension expression to evaluate.
            # Constructing child contexts here needlessly expands foreign keys
            # for every row (and can turn a TREATAS tuple set into thousands
            # of individual model lookups).
            return Table([('__summary',{c:v for (t,c),v in zip(cols,key)},dict(zip(cols,key))) for key,members in groups.values()],cols)
        if args[0][0]=='name' and args[0][1].casefold() not in env and table:
            from dax_summary import extensions
            from dax_sql import UnsupportedSql
            try:return extensions(e,source,table,cols,groups,names,pairs[1::2],env)
            except UnsupportedSql:pass
        result = []
        for key,members in groups.values():
            e.check_budget()
            context = dict(zip(cols, key))
            values = {c: v for (t, c), v in context.items()}
            group_row = ('__summary', values, context)
            child = e.child(e.transition(group_row))
            if names and args[0][0]!='name':
                if len(source_tables)!=1 or any(t.startswith('__') for t,c in source.columns):
                    raise ValueError('SUMMARIZE extension columns require source model lineage')
                child=e.child([*child.require_filters(),e.value_filter(source.columns,[[r[1][c] for t,c in source.columns] for r in members])])
            for j, name in enumerate(names):
                values[name] = child.scalar(child.run(pairs[j * 2 + 1], env, None))
            result.append(('__summary', values, context))
        return Table(result, cols + [('__virtual', name) for name in names])
    if fn in ('ISFILTERED', 'ISCROSSFILTERED', 'HASONEFILTER', 'FILTERS'):
        if args[0][0] == 'col':
            columns = [e.column(args[0])]
            table = columns[0][0]
        else:
            table, columns = e.canonical_table(args[0][1]), []
        def direct(f):
            if 'alternatives' in f:
                return any(direct(x) for g in f['alternatives'] for x in g)
            return f['table'] == table and (not columns or columns[0][1] in f.get('columns', []))
        filters = e.require_filters()
        matched = [f for f in filters if direct(f)]
        if fn == 'ISFILTERED':
            return bool(matched)
        if fn == 'ISCROSSFILTERED':
            def reaches(f):
                if 'alternatives' in f:
                    return any(reaches(x) for g in f['alternatives'] for x in g)
                return e.path(table, f['table']) is not None
            return bool(matched) or any(reaches(f) for f in filters)
        if not columns:
            raise ValueError(fn + ' requires a column')
        values = e.child(matched).project(args[0], True)
        return bool(matched) and len(values) == 1 if fn == 'HASONEFILTER' else values
    if fn == 'RELATEDTABLE':
        if not row or args[0][0] != 'name':
            raise ValueError('RELATEDTABLE requires row context and a model table')
        return e.child(e.transition(row)).table(args[0][1])
    if fn == 'RELATED':
        if not row:
            raise ValueError('RELATED requires row context')
        table, col = e.column(args[0])
        def reaches(start,target):
            pending=[start];visited=set()
            while pending:
                node=pending.pop()
                if node==target:return True
                if node in visited:continue
                visited.add(node)
                pending.extend(r['ToTableName'] for r in e.model.get('relationships',[]) if r.get('IsActive') and r.get('Cardinality') in ('M:1','1:1') and r['FromTableName']==node)
            return False
        current, seen = row, set()
        if current[0].startswith('__') and len(current)>2:
            if (table,col) in current[2]:return current[2][table,col]
            sources={t for t,c in current[2] if reaches(t,table)}
            if len(sources)!=1:raise ValueError('RELATED virtual row requires unambiguous base-table lineage')
            source=next(iter(sources));current=(source,{c:v for (t,c),v in current[2].items() if t==source})
        while current[0] != table:
            e.check_budget()
            if current[0] in seen:
                raise ValueError('Ambiguous RELATED relationship traversal')
            seen.add(current[0])
            candidates = [r for r in e.model.get('relationships', []) if r.get('IsActive') and r.get('Cardinality') in ('M:1', '1:1') and r['FromTableName'] == current[0] and (r['ToTableName'] == table or reaches(r['ToTableName'], table))]
            if len(candidates) != 1:
                raise ValueError('RELATED requires one unambiguous active many-to-one path')
            r = candidates[0]
            # RELATED ignores query filters on the lookup side, but still reads
            # the secured connection. Build its key index once per evaluation
            # instead of scanning the entire dimension for every iterator row.
            indexes = e.budget.setdefault('related_indexes', {})
            key = (r['ToTableName'], r['ToColumnName'])
            if key not in indexes:
                index = {}
                for v in e.child([]).table(r['ToTableName']):
                    e.check_budget()
                    value = v[1][r['ToColumnName']]
                    normalized = value.casefold() if isinstance(value, str) else value
                    index.setdefault(normalized, []).append(v)
                indexes[key] = index
            value = current[1][r['FromColumnName']]
            normalized = value.casefold() if isinstance(value, str) else value
            values = indexes[key].get(normalized, [])
            if len(values) > 1:
                raise ValueError('Relationship one-side key is not unique')
            if not values:
                return None
            current = values[0]
        return current[1][col]
    if fn == 'LOOKUPVALUE':
        table, col = e.column(args[0])
        rest, alternate = args[1:], None
        if len(rest) % 2:
            alternate, rest = rest[-1], rest[:-1]
        tests = []
        for i in range(0, len(rest), 2):
            t, c = e.column(rest[i])
            if t != table:
                raise ValueError('LOOKUPVALUE search columns must belong to the result table')
            tests.append((c, scalar(rest[i + 1])))
        values = [r[1][col] for r in e.child([]).table(table) if all(e.equal(r[1][c], v, True) for c, v in tests)]
        unique = []
        for value in values:
            if not any(e.equal(value, v, True) for v in unique):
                unique.append(value)
        if len(unique) == 1:
            return unique[0]
        if alternate is not None:
            return ev(alternate)
        if not unique:
            return None
        raise ValueError('LOOKUPVALUE found multiple distinct results')
    if fn == 'PATH':
        table, key = e.column(args[0])
        pt, parent = e.column(args[1])
        if table != pt or not row or row[0] != table:
            raise ValueError('PATH requires row context and columns from one table')
        pairs = {}
        for r in e.child([]).table(table):
            k, p = r[1][key], r[1][parent]
            if k is None:
                continue
            if '|' in text(k):
                raise ValueError('PATH identifier contains |')
            if k in pairs and pairs[k] != p:
                raise ValueError('PATH identifier has conflicting parents')
            pairs[k] = p
        result, seen, current = [], set(), row[1][key]
        if current is None:
            return None
        while current is not None:
            e.check_budget()
            if current in seen or current not in pairs:
                raise ValueError('PATH has a cycle or missing parent')
            seen.add(current)
            result.append(text(current))
            current = pairs[current]
        return '|'.join(reversed(result))
    if fn in ('FIRSTDATE', 'LASTDATE', 'DATESBETWEEN', 'DATESYTD', 'DATESQTD', 'DATESMTD', 'TOTALYTD', 'TOTALQTD', 'TOTALMTD'):
        if fn.startswith('TOTAL'):
            dates = dispatch(e, 'DATES' + fn[5:], args[1:2], env, row)
            filters = e.child(e.transition(row)).remove(dates.columns)
            filters.append(e.value_filter(dates.columns, [[next(iter(r[1].values()))] for r in dates]))
            return e.child(filters).calculate([args[0], args[2]], env, None) if len(args) == 3 else e.child(filters).run(args[0], env, None)
        node = args[0]
        table, col = e.column(node)
        values = e.project(node, True)
        ordered = sorted([r for r in values if r[1][col] is not None], key=lambda r: date(r[1][col]))
        if fn in ('FIRSTDATE', 'LASTDATE'):
            return Table(ordered[:1] if fn == 'FIRSTDATE' else ordered[-1:], [(table, col)])
        raw = e.child(e.remove([(table, col)])).project(node, True)
        available = sorted([r for r in raw if r[1][col] is not None], key=lambda r: date(r[1][col]))
        if any(not isinstance(r[1][col], (dt.date, dt.datetime)) or date(r[1][col]).time() != dt.time() for r in available):
            raise ValueError('Time intelligence requires a typed date column with dates at midnight')
        if fn == 'DATESBETWEEN':
            lo, hi = scalar(args[1]), scalar(args[2])
            lo = date(lo) if lo is not None else date(available[0][1][col]) if available else None
            hi = date(hi) if hi is not None else date(available[-1][1][col]) if available else None
        else:
            if not ordered:
                return Table([], [(table, col)])
            hi = date(ordered[-1][1][col])
            month = 1 if fn == 'DATESYTD' else (hi.month - 1) // 3 * 3 + 1 if fn == 'DATESQTD' else hi.month
            lo = dt.datetime(hi.year, month, 1)
        return Table([r for r in available if lo is not None and hi is not None and lo <= date(r[1][col]) <= hi], [(table, col)])
    if fn in ('TOPN', 'RANKX', 'CONCATENATEX'):
        if fn=='RANKX':
            from dax_sql import rank_value, UnsupportedSql
            try:return rank_value(e,args,env,row)
            except UnsupportedSql:pass
        if fn == 'TOPN':
            n, values, sortargs = integer(scalar(args[0])), e.as_table(ev(args[1])), args[2:]
        else:
            values = e.as_table(ev(args[0]))
            sortargs = args[3:] if fn == 'CONCATENATEX' else []
        score_cache={}
        def key(expr, r):
            token=repr(expr)
            if token not in score_cache:
                from dax_sql import iterator_scores,UnsupportedSql
                from dax_rowset import evaluate_rows
                try:
                    scores=evaluate_rows(e,values,[expr],env)
                    score_cache[token]=('rows',{id(candidate):result[0] for candidate,result in zip(values,scores)})
                except UnsupportedSql:
                    try:score_cache[token]=('tuples',iterator_scores(e,expr,values))
                    except UnsupportedSql:score_cache[token]=None
            scores=score_cache[token]
            value=(scores[1].get(id(r)) if scores[0]=='rows' else scores[1].get(tuple(v.casefold() if isinstance(v,str) else v for v in r[1].values()))) if scores is not None else e.scalar(e.run(expr, env, (*r,)))
            return (value is not None, value.casefold() if isinstance(value, str) else value)
        if fn == 'RANKX':
            available={c.casefold() for t,c in values.columns};qualified=set(values.columns)|(set(values[0][2]) if values and len(values[0])>2 else set())
            pure={'SWITCH','IF','COALESCE','DIVIDE','ABS','ROUND','ROUNDUP','ROUNDDOWN','INT','TRUNC','LOG10','LN','POWER','SQRT','BLANK','TRUE','FALSE'}
            def cacheable(node):
                if not isinstance(node,(tuple,list)):return True
                if node and node[0]=='col':return (node[1],node[2]) in qualified if node[1] else node[2].casefold() in available
                if node and node[0]=='call' and node[1] not in pure:return False
                return all(cacheable(part) for part in node if isinstance(part,(tuple,list)))
            cache=e.budget.setdefault('rank_vectors',{});token=(id(values),repr(args[1]),tuple((k,id(v) if isinstance(v,Table) else repr(v)) for k,v in env.items()),repr(e.filters)) if cacheable(args[1]) else None
            cached=cache.get(token) if token is not None else None
            if cached is not None and cached[0] is values:scores=cached[1]
            else:
                from dax_rowset import evaluate_rows
                scoring=e
                if values and e.row_stack:
                    # A complete inner row shadows the same outer row columns.
                    # EARLIER and other outer-dependent operations are still
                    # rejected by the kernel compiler and use the interpreter.
                    def lineage(r):return set(r[2]) if len(r)>2 else {(r[0],c) for c in r[1]} if not r[0].startswith('__') else set()
                    covered=lineage(values[0])
                    fields={c.casefold() for c in values[0][1]}
                    if all(lineage(outer)<=covered and {c.casefold() for c in outer[1]}<=fields for outer in e.row_stack):
                        scoring=e.child(e.filters);scoring.row_stack=[]
                try:scores=[r[0] for r in evaluate_rows(scoring,values,[args[1]],env)]
                except UnsupportedSql:
                    from dax_grouped import evaluate_context_rows
                    try:scores=[r[0] for r in evaluate_context_rows(scoring,values,[args[1]],env)]
                    except UnsupportedSql:scores=[e.scalar(e.run(args[1],env,(*r,))) for r in values]
                if token is not None and len(cache)<8 and sum(len(entry[0])*max(1,len(entry[0].columns)) for entry in cache.values())+len(values)*max(1,len(values.columns))<=2000000:cache[token]=(values,scores)

            if token not in cache:token=None
            target = scalar(args[2]) if len(args) > 2 and args[2] != ('lit', None) else scalar(args[1])
            ascending = scalar(args[3]) if len(args) > 3 else False
            ascending = ascending in (True, 1, 'ASC')
            ties = scalar(args[4]) if len(args) > 4 else 'SKIP'
            if ties not in ('SKIP', 'DENSE', None):
                raise ValueError('RANKX ties must be SKIP or DENSE')
            scores = [0 if s is None else s for s in scores]
            target = 0 if target is None else target
            ordered_cache=e.budget.setdefault('rank_ordered',{})
            orderkey=(token,ties)
            ordered=ordered_cache.get(orderkey) if token is not None else None
            if ordered is None:
                ordered=sorted(set(scores) if ties=='DENSE' else scores)
                if token is not None and len(ordered_cache)<16:ordered_cache[orderkey]=ordered
            better=bisect.bisect_left(ordered,target) if ascending else len(ordered)-bisect.bisect_right(ordered,target)
            return better+1
        ordered, pairs = list(values), []
        for i in range(0, len(sortargs), 2):
            direction = scalar(sortargs[i + 1]) if i + 1 < len(sortargs) else False
            pairs.append((sortargs[i], direction not in (True, 1, 'ASC')))
        for expr, reverse in reversed(pairs):
            ordered.sort(key=lambda r: key(expr, r), reverse=reverse)
        if fn == 'CONCATENATEX':
            sep = text(scalar(args[2])) if len(args) > 2 else ''
            result = sep.join(text(e.scalar(e.run(args[1], env, (*r,)))) for r in ordered)
            if len(result) > 1000000:
                raise RuntimeError('CONCATENATEX output limit exceeded')
            return result
        if n <= 0:
            return Table([], values.columns)
        if not pairs:return Table(ordered[:n],values.columns)
        if n >= len(ordered):
            return Table(ordered, values.columns)
        boundary = tuple(key(expr, ordered[n - 1]) for expr, reverse in pairs)
        end = n
        while end < len(ordered) and tuple(key(expr, ordered[end]) for expr, reverse in pairs) == boundary:
            end += 1
        return Table(ordered[:end], values.columns)
    if fn in ('ROW', 'ADDCOLUMNS', 'SELECTCOLUMNS'):
        rows, pairs = (Table([('__virtual', {})], []), args) if fn == 'ROW' else (e.as_table(ev(args[0])), args[1:])
        if fn=='SELECTCOLUMNS':
            expanded=[];i=0
            while i<len(pairs):
                if pairs[i][0]=='col':expanded.extend([('lit',pairs[i][2]),pairs[i]]);i+=1
                elif i+1<len(pairs):expanded.extend(pairs[i:i+2]);i+=2
                else:raise ValueError('SELECTCOLUMNS requires a column or name/expression pair')
            pairs=expanded
        if len(pairs) % 2:
            raise ValueError(fn + ' requires name/expression pairs')
        names = [text(scalar(pairs[i])) for i in range(0, len(pairs), 2)]
        if len(set(n.casefold() for n in names)) != len(names):
            raise ValueError('Duplicate virtual column name')
        output = [];batched=None
        if fn=='ADDCOLUMNS':
            from dax_sql import add_columns,UnsupportedSql
            try:batched=add_columns(e,rows,pairs[1::2])
            except UnsupportedSql:pass
        for row_index,r in enumerate(rows):
            values = dict(r[1]) if fn == 'ADDCOLUMNS' else {}
            if any(name in values for name in names):
                raise ValueError('Virtual column conflicts with an existing column')
            for i, name in enumerate(names):
                values[name] = batched[row_index][i] if batched is not None else e.scalar(e.run(pairs[i * 2 + 1], env, row if fn == 'ROW' else (*r,)))
            lineage=dict(r[2]) if len(r)>2 else {(t,c):r[1][c] for t,c in rows.columns if not t.startswith('__') and c in r[1]}
            if fn=='SELECTCOLUMNS':lineage={(e.column(expr)):values[name] for name,expr in zip(names,pairs[1::2]) if expr[0]=='col' and expr[1]}
            output.append(('__virtual', values,lineage))
        oldnames = [c for t, c in rows.columns] if fn == 'ADDCOLUMNS' else []
        return Table(output, (list(rows.columns) if fn=='ADDCOLUMNS' else []) + [('__virtual', c) for c in names])
    if fn in ('GENERATE', 'GENERATEALL'):
        outer = e.as_table(ev(args[0]))
        result = []
        columns = None
        for left in outer:
            e.check_budget()
            inner = e.as_table(e.run(args[1], env, left))
            if {c.casefold() for _,c in outer.columns} & {c.casefold() for _,c in inner.columns}:
                raise ValueError(fn + ' has duplicate column names')
            current = list(outer.columns) + list(inner.columns)
            if columns is not None and columns != current:
                raise ValueError(fn + ' requires a stable inner table schema')
            columns = current
            right_rows = inner if inner else ([('__virtual', {c:None for _,c in inner.columns}, {})] if fn == 'GENERATEALL' else [])
            for right in right_rows:
                e.check_budget()
                if len(result) >= 100000:
                    raise RuntimeError(fn + ' exceeds 100,000 rows')
                lineage = {}
                for item, schema in ((left, outer.columns), (right, inner.columns)):
                    lineage.update(item[2] if len(item)>2 else {(t,c):item[1][c] for t,c in schema if not t.startswith('__')})
                result.append(('__virtual', {**left[1], **right[1]}, lineage))
        return Table(result, columns if columns is not None else outer.columns)
    if fn in ('GENERATESERIES', 'CALENDAR'):
        a, b = [scalar(n) for n in args[:2]]
        if fn == 'CALENDAR':
            a, b = date(a).replace(hour=0, minute=0, second=0, microsecond=0), date(b).replace(hour=0, minute=0, second=0, microsecond=0)
            if a > b:
                raise ValueError('CALENDAR start must not exceed end')
            count, col = (b - a).days + 1, 'Date'
            value = lambda i: a + dt.timedelta(days=i)
        else:
            a, b = number(a), number(b)
            step = number(scalar(args[2])) if len(args) > 2 else 1
            if step <= 0:
                raise ValueError('GENERATESERIES increment must be positive')
            count, col = max(0, math.floor((b - a) / step) + 1), 'Value'
            value = lambda i: a + i * step
        if count > 100000:
            raise RuntimeError('Generated table exceeds 100,000 rows')
        return Table([('__virtual', {col: value(i)}) for i in range(count)], [('__virtual', col)])
    if fn in ('UNION', 'INTERSECT', 'EXCEPT', 'CROSSJOIN'):
        tables = [e.as_table(ev(n)) for n in args]
        first = tables[0]
        if fn == 'CROSSJOIN':
            if math.prod(len(t) for t in tables) > 100000:
                raise RuntimeError('CROSSJOIN exceeds 100,000 rows')
            names = [c for t in tables for _, c in t.columns]
            if len(set(names)) != len(names):
                raise ValueError('CROSSJOIN has duplicate column names')
            return Table([('__virtual', {k: v for r in combo for k, v in r[1].items()}) for combo in itertools.product(*tables)], [('__virtual', c) for c in names])
        if any(len(t.columns) != len(first.columns) for t in tables):
            raise ValueError(fn + ' tables require the same column count')
        keys = lambda table: [tuple(r[1].values()) for r in table]
        norm = lambda values: tuple(v.casefold() if isinstance(v, str) else v for v in values)
        if fn == 'UNION':
            values = [v for table in tables for v in keys(table)]
        else:
            other = {norm(v) for v in keys(tables[1])}
            # EXCEPT/INTERSECT inherit names and lineage from the first table,
            # regardless of the second table's aliases or lineage.
            kept = [r for r in first if (norm(tuple(r[1].values())) in other) == (fn == 'INTERSECT')]
            return Table(kept, first.columns)
        if len(values) > 100000:
            raise RuntimeError('Set operation exceeds 100,000 rows')
        same = all(t.columns == first.columns for t in tables)
        cols = first.columns if same else [('__virtual', c) for t, c in first.columns]
        target = cols[0][0] if cols else '__virtual'
        return Table([(target, {c: v for (_, c), v in zip(cols, vals)}) for vals in values], cols)
    raise ValueError('Unsupported DAX function ' + fn)
