"""Structured filter contexts and relationship traversal for Python DAX."""
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
            metadata[table] = [d[0] for d in self.con.execute('SELECT * FROM ' + qi(table) + ' LIMIT 0').description]
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
        child.iterator_depth = self.iterator_depth
        return child

    def require_filters(self):
        if self.filters is None:
            if any(self.contexts.values()):
                raise ValueError('Context changes require structured filters. Refresh the application.')
            return []
        return self.filters

    def path(self, start, end):
        queue = [(start, [])]
        seen = {start}
        while queue:
            table, path = queue.pop(0)
            if table == end:
                return path
            for r in self.model.get('relationships', []):
                if not r.get('IsActive') or r.get('Cardinality') not in ('M:1', '1:1'):
                    continue
                edges = [(r['FromTableName'], r['FromColumnName'], r['ToTableName'], r['ToColumnName'])]
                if r.get('CrossFilteringBehavior') == 'Both':
                    edges.append((r['ToTableName'], r['ToColumnName'], r['FromTableName'], r['FromColumnName']))
                for edge in edges:
                    if edge[0] == table and edge[2] not in seen:
                        seen.add(edge[2])
                        queue.append((edge[2], path + [edge]))
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
        terms = []
        for source, conditions in combined.items():
            sql = '(' + ' AND '.join(conditions) + ')'
            if source != table:
                path = self.path(table, source)
                if path is None:
                    continue
                for a, ac, b, bc in reversed(path):
                    sql = 'EXISTS (SELECT 1 FROM ' + qi(b) + ' WHERE ' + qi(b) + '.' + qi(bc) + ' = ' + qi(a) + '.' + qi(ac) + ' AND ' + sql + ')'
            terms.append(sql)
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
        if len(rows) > 5000:
            raise RuntimeError('DAX filter exceeds 5,000 value tuples')
        if not columns or len({t for t, c in columns}) != 1 or columns[0][0].startswith('__'):
            raise ValueError('Table filter requires columns with lineage from one model table')
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
                    matches = [x for x in self.child([]).table(r['ToTableName']) if self.equal(x[1].get(r['ToColumnName']), current[1][r['FromColumnName']], True)]
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

    def selected_filters(self, args):
        cols, tables, clear = self.modifier_targets(args)
        external = self.external_filters
        if external is None:
            raise ValueError('ALLSELECTED requires original external filter context. Refresh the application.')
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
            if arg[0] == 'call' and arg[1] == 'ALLSELECTED':
                if row or self.iterator_depth:
                    raise ValueError('ALLSELECTED inside iterator row contexts is not supported yet')
                actions.append(('selected', arg[2]))
                continue
            if arg[0] == 'call' and arg[1] in ('ALL', 'REMOVEFILTERS', 'ALLEXCEPT'):
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
            if arg[0] == 'op':
                cols = list(dict.fromkeys(self.referenced_columns(arg)))
                if not cols or len({t for t, c in cols}) != 1:
                    raise ValueError('CALCULATE Boolean filters need columns from exactly one table')
                candidates = self.child(self.remove(cols)).table(cols[0][0])
                matched = [[r[1][c] for t, c in cols] for r in candidates if self.scalar(self.run(arg, env, r))]
                actions.append(('filter', cols, self.value_filter(cols, matched), keep))
            else:
                values = self.as_table(self.run(arg, env, row))
                if getattr(values,'clear_date_table',None):
                    actions.append(('remove',[],[values.clear_date_table],False))
                cols = values.columns
                tuples = [[r[1][c] for t, c in cols] for r in values]
                actions.append(('filter', cols, self.value_filter(cols, tuples), keep))
        filters = self.transition(row)
        # Modifiers precede explicit filters; arguments are not applied sequentially.
        for action in actions:
            if action[0] == 'remove':
                filters = self.child(filters).remove(*action[1:])
            elif action[0] == 'selected':
                filters = self.child(filters).selected_filters(action[1])
        overwrite = list(dict.fromkeys(c for action in actions if action[0] == 'filter' and not action[3] for c in action[1]))
        if overwrite:
            filters = self.child(filters).remove(overwrite)
        filters += [action[2] for action in actions if action[0] == 'filter']
        return self.child(filters).run(args[0], env, None)
