"""Structured filter contexts and relationship traversal for Python DAX."""
from dax_metadata import schema as model_schema, type_name
from dax_core import qi, sv


class ContextMixin:
    def canonical_table(self, name):
        match = next((t['name'] for t in self.model['tables'] if t['name'].casefold() == name.casefold()), None)
        if match is None:
            raise ValueError('Unknown DAX table ' + name)
        return match

    def column(self, node):
        if node[0] != 'col':
            raise ValueError('Expected a qualified model column')
        name=node[1] or (self.stack[-1][0] if self.stack else None)
        if not name:
            raise ValueError('Cannot resolve unqualified DAX column '+node[2]+' outside a measure context')
        table = self.canonical_table(name)
        metadata = self.budget.setdefault('columns', {})
        if table not in metadata:
            metadata[table] = [d[0] for d in model_schema(self,table)]
        cols = metadata[table]
        col = next((c for c in cols if c.casefold() == node[2].casefold()), None)
        if col is None:
            raise ValueError('Unknown DAX column ' + node[2])
        return table, col

    def child(self, filters):
        child = type(self)(self.con, self.model, {}, filters=filters, budget=self.budget)
        child.stack = self.stack
        child.scope = self.scope
        child.external_filters = self.external_filters
        for key in ('selected_measure','selected_measure_name','selected_measure_format'):
            if hasattr(self,key):setattr(child,key,getattr(self,key))
        child.iterator_depth = self.iterator_depth
        child.row_stack = self.row_stack
        child.selection_shadows = self.selection_shadows
        # A modifier or changed filter context invalidates the proof that an
        # implicit full-row transition still identifies exactly this row value.
        child.transition_row = self.transition_row if filters==self.filters else None
        return child

    def require_filters(self):
        if self.filters is None:
            if any(self.contexts.values()):
                raise ValueError('Context changes require structured filters. Refresh the application.')
            return []
        return self.filters

    def path(self, start, end):
        # Nested summaries ask for the same relationship paths thousands of
        # times. Cache only graph metadata within this secured request. Include
        # every traversal property so CROSSFILTER and in-place model changes
        # cannot reuse a path from a different relationship configuration.
        signature=tuple((r.get('FromTableName'),r.get('FromColumnName'),r.get('ToTableName'),r.get('ToColumnName'),bool(r.get('IsActive')),r.get('Cardinality'),r.get('CrossFilteringBehavior')) for r in self.model.get('relationships', []))
        graphs=self.budget.setdefault('relationship_graphs',{})
        if signature not in graphs:
            if len(graphs)>=16:graphs.pop(next(iter(graphs)))
            edges={}
            for source,source_column,target,target_column,active,cardinality,direction in signature:
                if not active or cardinality not in ('M:1','1:1','M:M'):continue
                edges.setdefault(source,[]).append((source,source_column,target,target_column))
                if direction=='Both':edges.setdefault(target,[]).append((target,target_column,source,source_column))
            graphs[signature]=(edges,{})
        edges,paths=graphs[signature];key=(start,end)
        if key in paths:return None if paths[key] is None else list(paths[key])
        queue = [(start, [])]
        seen = {start}
        while queue:
            table, path = queue.pop(0)
            if table == end:
                if len(paths)<1024:paths[key]=tuple(path)
                return path
            for edge in edges.get(table,[]):
                if edge[2] not in seen:
                    seen.add(edge[2])
                    queue.append((edge[2], path + [edge]))
        if len(paths)<1024:paths[key]=None
        return None

    def where(self, table, filters=None):
        filters = self.filters if filters is None else filters
        if filters is None:
            return self.contexts.get(table, '')
        combined, tuples = {}, []
        for f in filters:
            if 'alternatives' in f:
                tuples.append(f)
            else:
                combined.setdefault(f['table'], []).append(f['sql'])
        # Shared relationship paths must constrain the same fact row. Building
        # independent EXISTS branches can match different rows and amplifies SQL.
        tree={'conditions':[], 'edges':{}}
        for source, conditions in combined.items():
            path=[] if source==table else self.path(table,source)
            if path is None:continue
            node=tree
            for edge in path:node=node['edges'].setdefault(edge,{'conditions':[], 'edges':{}})
            node['conditions'].extend(conditions)
        def render(node):
            terms=['('+c+')' for c in node['conditions']]
            for (a,ac,b,bc),child in node['edges'].items():
                predicate=render(child)
                terms.append('EXISTS (SELECT 1 FROM '+qi(b)+' WHERE '+qi(b)+'.'+qi(bc)+' = '+qi(a)+'.'+qi(ac)+(' AND '+predicate if predicate else '')+')')
            return ' AND '.join(terms)
        terms=[render(tree)] if tree['conditions'] or tree['edges'] else []
        for f in tuples:
            terms.append('(' + ' OR '.join('(' + (self.where(table, row) or 'TRUE') + ')' for row in f['alternatives']) + ')' if f['alternatives'] else 'FALSE')
        return ' AND '.join(terms)

    def expanded(self, table):
        names = {table}
        while True:
            previous = set(names)
            for r in self.model.get('relationships', []):
                if r.get('IsActive') and r.get('Cardinality') in ('M:1', '1:1') and r['FromTableName'] in names:
                    names.add(r['ToTableName'])
            if names == previous:
                return names

    def remove(self, columns=(), tables=(), all_filters=False):
        filters = self.require_filters()
        if all_filters:
            return []
        columns, tables = set(columns), set(tables)
        projected=[]
        for f in filters:
            if 'alternatives' in f:
                # Project an OR-of-tuples when CALCULATE replaces only some
                # lineage columns. Retain correlations among the other fields.
                alternatives=[self.child(group).remove(columns,tables) for group in f['alternatives']]
                if any(not group for group in alternatives):continue
                unique=[]
                for group in alternatives:
                    if group not in unique:unique.append(group)
                projected.append({'alternatives':unique});continue
            if f.get('table') not in tables:
                affected={c for t,c in columns if t==f.get('table')};names=set(f.get('columns',[]));remaining=names-affected
                if names&affected and remaining:
                    cols=[(f['table'],c) for c in sorted(remaining)]
                    self.check_budget()
                    rows=self.con.execute('SELECT DISTINCT '+','.join(qi(c) for t,c in cols)+' FROM '+qi(f['table'])+' WHERE '+f['sql']+' LIMIT 5001').fetchall()
                    f=self.value_filter(cols,rows)
            projected.append(f)
        filters=projected
        def touches(f):
            if 'alternatives' in f:
                if any(touches(part) for group in f['alternatives'] for part in group):
                    raise ValueError('Replacing correlated multi-table filters is not supported yet')
                return False
            if f['table'] in tables:
                return True
            affected = {c for t, c in columns if t == f['table']}
            if not affected:
                return False
            names = set(f.get('columns', []))
            if not names:
                raise ValueError('Filter column lineage is unavailable; cannot safely replace the filter')
            overlap = names & affected
            if overlap and names - affected:
                raise ValueError('Replacing only part of a compound column filter is not supported yet')
            return bool(overlap)
        return [f for f in filters if not touches(f)]

    def value_filter(self, columns, rows):
        if not columns or len({t for t, c in columns}) != 1 or columns[0][0].startswith('__'):
            raise ValueError('Table filter requires columns with lineage from one model table')
        if any(len(row)!=len(columns) for row in rows):raise ValueError('DAX filter tuple width must match its columns')
        if len(rows)>100000 or len(rows)*len(columns)>2000000:
            raise RuntimeError('DAX filter exceeds 100,000 tuples or 2,000,000 cells')
        if len(rows)>1000:
            # A bounded request-local relation avoids enormous OR expressions.
            # It is joined to the already secured model connection, so it cannot
            # restore rows removed by RLS. Reuse repeated TREATAS/filter rowsets.
            import hashlib,uuid,pyarrow as pa
            key=hashlib.sha256(repr((columns,rows)).encode('utf-8')).hexdigest()
            cache=self.budget.setdefault('filter_relations',{})
            if key not in cache:
                if len(cache)>=64 or self.budget.get('filter_relation_cells',0)+len(rows)*len(columns)>4000000:
                    raise RuntimeError('DAX request filter relation budget exceeded')
                self.check_budget();table=columns[0][0]
                schema=self.con.execute('SELECT '+','.join(qi(c) for t,c in columns)+' FROM '+qi(table)+' LIMIT 0').to_arrow_table().schema
                values=pa.Table.from_arrays([pa.array([r[i] for r in rows],type=schema.field(i).type) for i in range(len(columns))],schema=schema)
                name='__d2bi_filter_'+uuid.uuid4().hex
                self.con.register(name,values)
                cache[key]=name;self.budget['filter_relation_cells']=self.budget.get('filter_relation_cells',0)+len(rows)*len(columns)
            name=cache[key]
            sql='EXISTS (SELECT 1 FROM '+qi(name)+' WHERE '+' AND '.join(qi(name)+'.'+qi(c)+' IS NOT DISTINCT FROM '+qi(t)+'.'+qi(c) for t,c in columns)+')'
            return {'table':columns[0][0],'columns':[c for t,c in columns],'sql':sql}
        terms = ['(' + ' AND '.join(qi(t) + '.' + qi(c) + (' IS NULL' if value is None else ' = ' + sv(value)) for (t, c), value in zip(columns, row)) + ')' for row in rows]
        return {'table': columns[0][0], 'columns': [c for t, c in columns], 'sql': '(' + ' OR '.join(terms) + ')' if terms else 'FALSE'}

    def transition(self, row):
        filters = list(self.require_filters())
        if row and len(row) > 2:
            by_table = {}
            for (table, col), value in row[2].items():
                by_table.setdefault(table, {})[col] = value
            pending = list(by_table.items())
        else:
            pending = [row] if row else []
        seen = set()
        while pending:
            self.check_budget()
            current = pending.pop()
            if current[0] in seen:
                continue
            if current[0].startswith('__'):
                raise ValueError('Context transition requires model column lineage')
            seen.add(current[0])
            cols = [(current[0], c) for c in current[1]]
            filters = self.child(filters).remove(cols) + [self.value_filter(cols, [list(current[1].values())])]
            for r in self.model.get('relationships', []):
                if r.get('IsActive') and r.get('Cardinality') in ('M:1', '1:1') and r['FromTableName'] == current[0] and r['FromColumnName'] in current[1]:
                    indexes=self.budget.setdefault('transition_indexes',{})
                    token=(r['ToTableName'],r['ToColumnName'])
                    def identity(value):return ('blank',) if value is None else ('value',value.casefold() if isinstance(value,str) else value)
                    index=indexes.setdefault(token,{})
                    key=current[1][r['FromColumnName']];lookup=identity(key)
                    if lookup not in index:
                        target,col=token;ref=qi(col)
                        predicate='lower('+ref+') = lower('+sv(key)+')' if isinstance(key,str) else ref+' IS NOT DISTINCT FROM '+sv(key)
                        cursor=self.con.execute('SELECT * FROM '+qi(target)+' WHERE '+predicate+' LIMIT 2')
                        names=[d[0] for d in cursor.description]
                        index[lookup]=[(target,dict(zip(names,record))) for record in cursor.fetchall()]
                        self.check_budget()
                    matches=index[lookup]
                    if len(matches) > 1:
                        raise ValueError('Relationship one-side key is not unique')
                    if matches:
                        pending.append(matches[0])
        return filters

    def modifier_targets(self, args):
        if not args:
            return [], [], True
        if args[0][0] == 'name':
            if len(args) != 1:
                raise ValueError('A table modifier takes one table')
            return [], list(self.expanded(self.canonical_table(args[0][1]))), False
        cols = [self.column(a) for a in args]
        if len({t for t, c in cols}) != 1:
            raise ValueError('Modifier columns must belong to one table')
        return cols, [], False

    def selection_shadow_stamp(self):
        return tuple(frame['stamp'] for frame in self.selection_shadows)

    def selected_filters(self, args, row=None):
        cols, tables, clear = self.modifier_targets(args)
        external = self.external_filters
        if external is None:
            raise ValueError('ALLSELECTED requires original external filter context. Refresh the application.')
        if row is not None or self.iterator_depth or self.row_stack:
            # A FILTER over an explicitly selected full table has a known
            # physical iteration domain. Restore that domain, rather than an
            # individual row's implicit CALCULATE transition. Other nested
            # iterator/shadow shapes remain deliberately unsupported.
            if len(args)!=1 or args[0][0]!='name' or not self.selection_shadows:
                raise ValueError('ALLSELECTED inside iterator row contexts requires a proven full-table selection shadow')
            table=self.canonical_table(args[0][1]);frame=self.selection_shadows[-1]
            current=frame.get('row')
            if table!=frame['table'] or current is None or frame['relationships']!=repr(self.model.get('relationships',[])):
                raise ValueError('ALLSELECTED iterator shadow does not match this table or relationship context')
            def physical(value):
                return value[2] if len(value)>2 else {} if value[0].startswith('__') else {(value[0],c):v for c,v in value[1].items()}
            if set(physical(current))!=set(frame['columns']) or any(physical(value) and value is not current for value in self.row_stack) or row is not None and row is not current:
                raise ValueError('ALLSELECTED nested physical iterator row contexts are not supported')
            # A held selected table can outlive filters on a related bridge.
            # Replaying its source filters proves the exact physical domain
            # only while filters outside this expanded table remain unchanged.
            # Decline other shapes rather than silently expand that domain.
            if self.remove(cols,tables)!=self.child(frame['filters']).remove(cols,tables):
                raise ValueError('ALLSELECTED iterator shadow requires unchanged filters outside its expanded table')
            external=frame['filters']
        remaining = self.remove(cols, tables, clear)
        if clear:
            return list(external)
        retained = self.child(external).remove(cols, tables)
        affected = [f for f in external if f not in retained]
        return remaining + affected

    def referenced_columns(self, n):
        from dax_runtime import AGGREGATES, ITERATORS
        if n[0] == 'col':
            return [self.column(n)]
        if n[0] == 'call':
            if n[1] in AGGREGATES or n[1] in ITERATORS:
                return []
            return [c for a in n[2] for c in self.referenced_columns(a)]
        if n[0] == 'op':
            return self.referenced_columns(n[2]) + self.referenced_columns(n[3])
        return []

    def calculate(self, args, env, row):
        # Evaluate filter arguments before applying row-context transition.
        actions = []
        for arg in args[1:]:
            keep = arg[0] == 'call' and arg[1] == 'KEEPFILTERS'
            if keep:
                arg = arg[2][0]
            if arg[0]=='col':
                table,col=self.column(arg)
                dtype=str(self.con.execute('SELECT '+qi(col)+' FROM '+qi(table)+' LIMIT 0').description[0][1])
                if dtype=='BOOLEAN':
                    actions.append(('filter',[(table,col)],{'table':table,'columns':[col],'sql':qi(table)+'.'+qi(col)+' IS TRUE'},keep));continue
            # A base-table blank test can retain the original rowset as a SQL
            # predicate instead of allocating every fact row and a tuple per row.
            if arg[0]=='call' and arg[1]=='FILTER' and len(arg[2])==2 and arg[2][0][0]=='name' and arg[2][0][1].casefold() not in env:
                predicate=arg[2][1];negated=predicate[0]=='call' and predicate[1]=='NOT' and len(predicate[2])==1
                test=predicate[2][0] if negated else predicate
                if test[0]=='call' and test[1]=='ISBLANK' and len(test[2])==1 and test[2][0][0]=='col':
                    table=self.canonical_table(arg[2][0][1]);ct,col=self.column(test[2][0])
                    if ct==table:
                        columns=[(table,d[0]) for d in self.con.execute('SELECT * FROM '+qi(table)+' LIMIT 0').description]
                        original=self.where(table)
                        sql=qi(table)+'.'+qi(col)+(' IS NOT NULL' if negated else ' IS NULL')
                        if original:sql+=' AND ('+original+')'
                        actions.append(('filter',columns,{'table':table,'columns':[c for t,c in columns],'sql':sql},keep))
                        continue
            if arg[0] == 'call' and arg[1] == 'CROSSFILTER':
                a,b = self.column(arg[2][0]),self.column(arg[2][1])
                direction = str(arg[2][2][1]).casefold()
                if direction not in ('both','none','oneway'):
                    raise ValueError('Unsupported CROSSFILTER direction '+direction)
                found=next((r for r in self.model.get('relationships',[]) if {(r['FromTableName'],r['FromColumnName']),(r['ToTableName'],r['ToColumnName'])}=={a,b}),None)
                if not found:raise ValueError('CROSSFILTER requires an existing relationship')
                if direction=='oneway' and found.get('Cardinality')=='M:M':raise ValueError('OneWay is ambiguous for a many-to-many relationship')
                actions.append(('relationship',found,direction))
                continue
            if arg[0] == 'call' and arg[1] == 'ALLSELECTED':
                actions.append(('selected', arg[2]))
                continue
            if arg[0] == 'call' and arg[1] in ('ALL', 'ALLNOBLANKROW', 'REMOVEFILTERS', 'ALLEXCEPT'):
                if arg[1] == 'ALLEXCEPT':
                    if len(arg[2]) < 2 or arg[2][0][0] != 'name':
                        raise ValueError('ALLEXCEPT requires a table and columns')
                    table = self.canonical_table(arg[2][0][1])
                    keepcols = [self.column(x) for x in arg[2][1:]]
                    if any(t != table for t, c in keepcols):
                        raise ValueError('ALLEXCEPT columns must belong to its table')
                    cols = [c for c in self.child([]).table(table).columns if c not in keepcols]
                    actions.append(('remove', cols, list(self.expanded(table) - {table}), False))
                else:
                    actions.append(('remove', *self.modifier_targets(arg[2])))
                continue
            if arg[0] == 'op' or arg[0]=='call' and arg[1] in ('NOT','AND','OR','ISBLANK','ISNUMBER','ISTEXT','CONTAINSSTRING','CONTAINSSTRINGEXACT'):
                blank=arg[2][0] if arg[0]=='call' and arg[1]=='NOT' and len(arg[2])==1 else arg
                if blank[0]=='call' and blank[1]=='ISBLANK' and len(blank[2])==1 and blank[2][0][0]=='col':
                    table,col=self.column(blank[2][0]);sql=qi(table)+'.'+qi(col)+(' IS NOT NULL' if blank is not arg else ' IS NULL')
                    actions.append(('filter',[(table,col)],{'table':table,'columns':[col],'sql':sql},keep));continue
                if arg[0]=='op' and arg[1] in ('=','==','<>','>','>=','<','<=') and arg[2][0]=='col' and (arg[3][0]=='lit' or arg[3][0]=='name' and arg[3][1].casefold() in env):
                    constant=self.scalar(self.run(arg[3],env,row))
                    if constant is None or isinstance(constant,(str,int,float,bool)):
                        table,col=self.column(arg[2]);ref=qi(table)+'.'+qi(col);operator=arg[1]
                        if isinstance(constant,str):ref='lower(COALESCE(CAST('+ref+" AS VARCHAR),''))";constant=constant.casefold()
                        elif isinstance(constant,bool):ref='COALESCE('+ref+',FALSE)'
                        elif operator!='==':ref='COALESCE('+ref+',0)';constant=constant or 0
                        sql=ref+(' IS NOT DISTINCT FROM ' if operator=='==' else ' = ' if operator=='=' else ' '+operator+' ')+sv(constant)
                        actions.append(('filter',[(table,col)],{'table':table,'columns':[col],'sql':sql},keep));continue
                cols = list(dict.fromkeys(self.referenced_columns(arg)))
                if not cols or len({t for t, c in cols}) != 1:
                    raise ValueError('CALCULATE Boolean filters need columns from exactly one table')
                # Implicit ALL(column) Boolean domains enumerate secured values;
                # unrelated current-row columns must not erase requested values.
                candidate_engine=self.child([])
                table=cols[0][0]
                where=candidate_engine.where(table)
                # Boolean CALCULATE filters iterate distinct referenced column
                # tuples, not every duplicate fact row or unrelated column.
                self.check_budget()
                sql='SELECT DISTINCT '+','.join(qi(c) for t,c in cols)+' FROM '+qi(table)
                if where:sql+=' WHERE '+where
                values=self.con.execute(sql+' LIMIT 100001').fetchall()
                if len(values)>100000:raise RuntimeError('CALCULATE Boolean domain exceeds 100,000 tuples')
                candidates=[(table,dict(zip([c for t,c in cols],values_row))) for values_row in values]
                matched = [[r[1][c] for t, c in cols] for r in candidates if self.scalar(self.run(arg, env, (*r,)))]
                actions.append(('filter', cols, self.value_filter(cols, matched), keep))
            else:
                values = self.as_table(self.run(arg, env, row))
                if getattr(values,'clear_date_table',None):
                    actions.append(('remove',[],[values.clear_date_table],False))
                cols = values.columns
                tuples = [[r[1][c] for t, c in cols] for r in values]
                actions.append(('filter', cols, self.value_filter(cols, tuples), keep))
        filters = self.transition(row)
        if (row is not None or self.iterator_depth or self.row_stack) and any(a[0]=='selected' for a in actions) and any(a[0]=='relationship' for a in actions):
            raise ValueError('ALLSELECTED iterator shadows with relationship overrides are not supported')
        # Modifiers precede explicit filters; arguments are not applied sequentially.
        for action in actions:
            if action[0] == 'remove':
                filters = self.child(filters).remove(*action[1:])
            elif action[0] == 'selected':
                filters = self.child(filters).selected_filters(action[1],row)
        overwrite = list(dict.fromkeys(c for action in actions if action[0] == 'filter' and not action[3] for c in action[1]))
        if overwrite:
            filters = self.child(filters).remove(overwrite)
        filters += [action[2] for action in actions if action[0] == 'filter']
        child=self.child(filters)
        overrides={id(a[1]):a[2] for a in actions if a[0]=='relationship'}
        if overrides:
            child.model={**self.model,'relationships':[{**r,**({'IsActive':False} if overrides[id(r)]=='none' else {'CrossFilteringBehavior':'Both' if overrides[id(r)]=='both' else 'Single'})} if id(r) in overrides else r for r in self.model.get('relationships',[])]}
        from dax_memo import calculate_value
        return calculate_value(child,args[0],env)
