"""One grouped scan for safe aggregate measures across relationship bridges.

Join fan-out is deduplicated by physical fact-row ordinal, never by fact values
or a presumed unique business key. Every source is the caller's secured DuckDB
connection and is filtered through the existing DAX relationship context.
"""
import threading
import time
import uuid
from decimal import Decimal

from dax_budget import check_budget
from dax_metadata import schema as model_schema, type_name
from dax_core import qi, sv, cached_ast
from dax_sql import UnsupportedSql, SqlDax


_NUMERIC = ('TINYINT', 'SMALLINT', 'INTEGER', 'BIGINT', 'HUGEINT', 'UTINYINT', 'USMALLINT', 'UINTEGER', 'UBIGINT', 'UHUGEINT', 'FLOAT', 'DOUBLE', 'REAL', 'DECIMAL')


class _Plan:
    def __init__(self, engine):
        self.engine = engine
        self.fact = None
        self.aggregates = []
        self.stack = []
        self.constants = {}
        self.cohorts = []

    def ascii_column(self,table,column):
        # SQL lower() agrees with DAX casefold equality on ASCII. Keep the
        # newly supported text-row predicates away from Unicode folds such
        # as sharp-s/SS and Kelvin/K until a dedicated lowering supports them.
        proofs=self.engine.budget.setdefault('grouped_text_ascii',{});key=(table,column)
        if key not in proofs:
            self.engine.check_budget()
            reference=qi(column)
            non_ascii=self.engine.con.execute('SELECT 1 FROM '+qi(table)+' WHERE '+reference+' IS NOT NULL AND NOT regexp_full_match('+reference+','+sv(r'[\x00-\x7f]*')+') LIMIT 1').fetchone()
            self.engine.check_budget()
            valid=non_ascii is None
            if len(proofs)<2000:proofs[key]=valid
            return valid
        return proofs[key]

    def fixed(self,value):
        if value is None:result=('NULL','blank')
        elif isinstance(value,bool):result=('TRUE' if value else 'FALSE','boolean')
        elif isinstance(value,(int,float,Decimal)):result=(sv(value),'number')
        elif isinstance(value,str):result=(sv(value),'text')
        else:raise UnsupportedSql('Grouped scalar constant type')
        self.constants[result]=value
        return result

    def compile(self, node, env=None):
        env = {} if env is None else env
        self.engine.check_budget()
        kind = node[0]
        if kind == 'lit':
            return self.fixed(node[1])
        if kind == 'name':
            if node[1].casefold() in env:
                return env[node[1].casefold()]
            if node[1].upper() in ('TRUE', 'FALSE'):
                return self.fixed(node[1].upper()=='TRUE')
            raise UnsupportedSql('Grouped scalar binding')
        if kind == 'let':
            local = dict(env)
            for name, expression in node[1]:
                local[name.casefold()] = self.compile(expression, local)
            return self.compile(node[2], local)
        if kind == 'col':
            matches = [m for m in self.engine.model['measures'] if m['Name'].casefold() == node[2].casefold() and (not node[1] or m['TableName'].casefold() == node[1].casefold())]
            if len(matches) != 1:
                raise UnsupportedSql('Grouped measure reference')
            measure = matches[0]
            identity = (measure['TableName'], measure['Name'])
            if identity in self.stack or len(self.stack) >= 30:
                raise UnsupportedSql('Grouped measure recursion')
            self.stack.append(identity)
            self.engine.stack.append(identity)
            try:
                return self.compile(cached_ast(self.engine, measure['Expression']))
            finally:
                self.engine.stack.pop()
                self.stack.pop()
        if kind == 'unary' and node[1] in ('+', '-'):
            value, typ = self.compile(node[2], env)
            if typ not in ('number', 'blank'):
                raise UnsupportedSql('Grouped unary type')
            return '(' + node[1] + 'COALESCE(' + value + ',0))', 'number'
        if kind == 'op':
            op = node[1]
            a, at = self.compile(node[2], env)
            b, bt = self.compile(node[3], env)
            if (a,at) in self.constants and (b,bt) in self.constants:
                try:return self.fixed(self.engine.scalar(self.engine.run(('op',op,('lit',self.constants[a,at]),('lit',self.constants[b,bt])),{},None)))
                except (ArithmeticError,TypeError,ValueError) as error:
                    # Compilation can visit an unchosen SQL CASE branch. Let
                    # the lazy interpreter decide whether its error is live.
                    raise UnsupportedSql('Grouped constant requires lazy evaluation') from error
            if op in ('&&', '||') and at in ('boolean', 'blank') and bt in ('boolean', 'blank'):
                return '(COALESCE(' + a + ',FALSE) ' + ('AND' if op == '&&' else 'OR') + ' COALESCE(' + b + ',FALSE))', 'boolean'
            if at not in ('number', 'blank') or bt not in ('number', 'blank'):
                raise UnsupportedSql('Grouped scalar operand types')
            if op in ('+', '-'):
                return '(CASE WHEN ' + a + ' IS NULL AND ' + b + ' IS NULL THEN NULL ELSE COALESCE(' + a + ',0)' + op + 'COALESCE(' + b + ',0) END)', 'number'
            if op == '*':
                return '(' + a + '*' + b + ')', 'number'
            if op in ('=', '<>', '<', '>', '<=', '>='):
                return '(COALESCE(' + a + ',0)' + op + 'COALESCE(' + b + ',0))', 'boolean'
            if op == '==':
                return '(' + a + ' IS NOT DISTINCT FROM ' + b + ')', 'boolean'
            raise UnsupportedSql('Grouped scalar operator')
        if kind != 'call':
            raise UnsupportedSql('Grouped scalar AST')
        fn, args = node[1], node[2]
        if fn == 'CALCULATE' and args:
            added=[]
            for argument in args[1:]:
                if argument[0]=='call' and argument[1]=='KEEPFILTERS' and len(argument[2])==1:
                    values=argument[2][0]
                    if values[0]=='call' and values[1]=='VALUES' and len(values[2])==1 and values[2][0][0]=='col':
                        table,column=self.engine.column(values[2][0])
                        # An existing explicit column filter already restricts
                        # eligible facts to this VALUES domain. Dropping this
                        # redundant intersection is safe only if the changing
                        # iterator identities cannot alter that table's domain.
                        present=any(f.get('table')==table and column in f.get('columns',[]) for f in self.engine.require_filters())
                        changes=any(self.engine.path(table,t) is not None for t,c in self.engine.sql_bound_groups)
                        if present and not changes:continue
                    raise UnsupportedSql('Grouped KEEPFILTERS needs a proven unchanged value domain')
                if argument[0]!='op' or argument[1] not in ('=','==') or argument[2][0]!='col':raise UnsupportedSql('Grouped CALCULATE cohort predicate')
                table,column=self.engine.column(argument[2]);right=self.compile(argument[3],env)
                if right not in self.constants:raise UnsupportedSql('Grouped CALCULATE cohort constant')
                if (table,column) in self.engine.sql_bound_groups:raise UnsupportedSql('Grouped CALCULATE changes a group identity')
                def conflicts(filters):
                    return any(conflicts(part) for f in filters for part in f.get('alternatives',[])) or any(f.get('table')==table and (not f.get('columns') or column in f['columns']) for f in filters)
                if conflicts(self.engine.require_filters()):raise UnsupportedSql('Grouped CALCULATE replaces an external column filter')
                if any((t,c)==(table,column) for t,c,op,value in [*self.cohorts,*added]):raise UnsupportedSql('Grouped nested cohort replacement')
                added.append((table,column,argument[1],self.constants[right]))
            before=self.cohorts
            self.cohorts=[*before,*added]
            try:return self.compile(args[0],env)
            finally:self.cohorts=before
        if fn=='SELECTEDVALUE' and args:
            # Bound group columns must never be folded into a global constant.
            fixed=SqlDax(self.engine).constant(node,self.engine,{})
            if fixed is None:raise UnsupportedSql('Group-dependent SELECTEDVALUE')
            return self.fixed(fixed[0])
        if fn=='SWITCH' and len(args)>=3:
            chosen=self.compile(args[0],env)
            if chosen not in self.constants:raise UnsupportedSql('Grouped dynamic SWITCH')
            pairs=args[1:]
            for index in range(0,len(pairs)-1,2):
                candidate=self.compile(pairs[index],env)
                if candidate not in self.constants:raise UnsupportedSql('Grouped dynamic SWITCH case')
                if self.engine.equal(self.constants[chosen],self.constants[candidate],True):return self.compile(pairs[index+1],env)
            return self.compile(pairs[-1],env) if len(pairs)%2 else self.fixed(None)
        if fn=='COALESCE' and args:
            values=[self.compile(argument,env) for argument in args]
            types={typ for sql,typ in values if typ!='blank'}
            if len(types)>1:raise UnsupportedSql('Grouped COALESCE types')
            return 'COALESCE('+','.join(sql for sql,typ in values)+')',next(iter(types),'blank')
        if fn == 'BLANK' and not args:
            return self.fixed(None)
        if fn in ('TRUE', 'FALSE') and not args:
            return self.fixed(fn=='TRUE')
        if fn in ('SUM', 'AVERAGE', 'MIN', 'MAX', 'COUNT', 'COUNTA', 'DISTINCTCOUNT', 'MEDIAN') and len(args) == 1 and args[0][0] == 'col':
            table, column = self.engine.column(args[0])
            return self.aggregate(fn, table, ('col', table, column), None)
        if fn == 'COUNTROWS' and len(args) == 1 and args[0][0] == 'name' and args[0][1].casefold() not in env:
            return self.aggregate(fn, self.engine.canonical_table(args[0][1]), None, None)
        if fn in ('MEDIANX', 'SUMX', 'AVERAGEX', 'MINX', 'MAXX') and len(args) == 2:
            source, predicate = args[0], None
            if source[0] == 'call' and source[1] == 'FILTER' and len(source[2]) == 2:
                source, predicate = source[2]
            if source[0] != 'name' or source[1].casefold() in env:
                raise UnsupportedSql('Grouped iterator domain')
            table = self.engine.canonical_table(source[1])
            # MEDIANX has distinct blank-as-zero semantics. Other iterator
            # aggregates are admitted only for a bare physical numeric column.
            if fn != 'MEDIANX' and args[1][0] != 'col':
                raise UnsupportedSql('Grouped iterator row arithmetic')
            return self.aggregate(fn, table, args[1], predicate)
        if fn == 'IF' and 2 <= len(args) <= 3:
            condition, ct = self.compile(args[0], env)
            if (condition,ct) in self.constants:
                if self.constants[condition,ct]:return self.compile(args[1],env)
                return self.compile(args[2],env) if len(args)>2 else self.fixed(None)
            yes, yt = self.compile(args[1], env)
            no, nt = self.compile(args[2], env) if len(args) == 3 else ('NULL', 'blank')
            if ct not in ('boolean', 'number', 'blank') or yt != nt and 'blank' not in (yt, nt):
                raise UnsupportedSql('Grouped IF types')
            predicate = 'COALESCE(' + condition + ',FALSE)' if ct == 'boolean' else 'COALESCE(' + condition + ',0)<>0'
            return '(CASE WHEN ' + predicate + ' THEN ' + yes + ' ELSE ' + no + ' END)', nt if yt == 'blank' else yt
        if fn == 'ISBLANK' and len(args) == 1:
            return '(' + self.compile(args[0], env)[0] + ' IS NULL)', 'boolean'
        if fn == 'NOT' and len(args) == 1:
            value, typ = self.compile(args[0], env)
            if typ != 'boolean':
                raise UnsupportedSql('Grouped NOT type')
            return '(NOT ' + value + ')', 'boolean'
        raise UnsupportedSql('Unsupported grouped scalar function ' + fn)

    def aggregate(self, fn, table, expression, predicate):
        if self.fact is not None and self.fact != table:
            raise UnsupportedSql('Grouped measure spans multiple fact tables')
        self.fact = table
        schema = {d[0]: str(d[1]) for d in model_schema(self.engine,table)}
        if any(target!=table for target,column,operator,value in self.cohorts):raise UnsupportedSql('Grouped cohort must filter the aggregate fact table')
        mapping = {c: '"__f".' + qi(c) for c in schema}

        def ascii_operand(node):
            if node[0]=='lit':return all(ord(character)<128 for character in node[1])
            column=next(c for c in schema if c.casefold()==node[2].casefold())
            return self.ascii_column(table,column)

        def row(node, boolean=False):
            kind = node[0]
            if kind == 'lit':
                if isinstance(node[1],str):return 'text'
                if node[1] is None or isinstance(node[1], (int, float, Decimal)) and not isinstance(node[1], bool):
                    return 'number'
                raise UnsupportedSql('Grouped numeric row literal')
            if kind == 'col':
                if node[1] and self.engine.canonical_table(node[1]) != table:
                    raise UnsupportedSql('Grouped iterator related column')
                name = next((c for c in schema if c.casefold() == node[2].casefold()), None)
                if name is not None and schema[name]=='VARCHAR':return 'text'
                if name is None or not schema[name].startswith(_NUMERIC):
                    raise UnsupportedSql('Grouped iterator numeric column')
                return 'number'
            if kind == 'op':
                types = [row(x) for x in node[2:]]
                if node[1] in ('+', '-', '*') and types == ['number', 'number']:
                    return 'number'
                if node[1] in ('=', '==', '<>', '<', '>', '<=', '>=') and types == ['number', 'number']:
                    return 'boolean'
                if node[1] in ('=','==','<>') and types==['text','text']:
                    if not all(ascii_operand(value) for value in node[2:]):
                        raise UnsupportedSql('Grouped text row predicate needs ASCII operands')
                    return 'boolean'
                if node[1] in ('&&', '||') and types == ['boolean', 'boolean']:
                    return 'boolean'
            if kind == 'call' and node[1] == 'DIVIDE' and len(node[2]) in (2, 3) and all(row(x) == 'number' for x in node[2]):
                return 'number'
            if kind == 'call' and node[1] == 'ISBLANK' and len(node[2]) == 1 and row(node[2][0]) == 'number':
                return 'boolean'
            if kind == 'call' and node[1] == 'NOT' and len(node[2]) == 1 and row(node[2][0]) == 'boolean':
                return 'boolean'
            raise UnsupportedSql('Grouped iterator row expression')

        def row_sql(node):
            # Keep row arithmetic's BLANK identity before comparisons or
            # ISBLANK inspect it. The generic scalar SQL compiler historically
            # coalesces both-BLANK sums and strict comparisons too early.
            kind = node[0]
            if kind == 'lit':
                return sv(node[1])
            if kind == 'col':
                column = next(c for c in mapping if c.casefold() == node[2].casefold())
                return mapping[column]
            if kind == 'op':
                a, b = [row_sql(x) for x in node[2:]]
                op = node[1]
                if row(node[2])=='text' and row(node[3])=='text':
                    if op=='==':return '(lower('+a+') IS NOT DISTINCT FROM lower('+b+'))'
                    return "(lower(COALESCE("+a+",''))"+op+"lower(COALESCE("+b+",'')))"
                if op in ('+', '-'):
                    return '(CASE WHEN ' + a + ' IS NULL AND ' + b + ' IS NULL THEN NULL ELSE COALESCE(' + a + ',0)' + op + 'COALESCE(' + b + ',0) END)'
                if op == '*':
                    return '(' + a + '*' + b + ')'
                if op == '==':
                    return '(' + a + ' IS NOT DISTINCT FROM ' + b + ')'
                if op in ('=', '<>', '<', '>', '<=', '>='):
                    return '(COALESCE(' + a + ',0)' + op + 'COALESCE(' + b + ',0))'
                return '(COALESCE(' + a + ',FALSE) ' + ('AND' if op == '&&' else 'OR') + ' COALESCE(' + b + ',FALSE))'
            fn, args = node[1], node[2]
            if fn == 'DIVIDE':
                a, b = [row_sql(x) for x in args[:2]]
                alternate = row_sql(args[2]) if len(args) > 2 else 'NULL'
                return '(CASE WHEN ' + b + ' IS NULL OR ' + b + '=0 THEN ' + alternate + ' ELSE COALESCE(' + a + ',0)/' + b + ' END)'
            if fn == 'ISBLANK':
                return '(' + row_sql(args[0]) + ' IS NULL)'
            return '(NOT COALESCE(' + row_sql(args[0]) + ',FALSE))'

        if expression is None:
            value = '*'
        elif fn in ('COUNT', 'COUNTA', 'DISTINCTCOUNT'):
            if expression[0] != 'col':
                raise UnsupportedSql('Grouped count expression')
            if fn == 'COUNT' and schema[expression[2]] == 'BOOLEAN':
                raise UnsupportedSql('COUNT excludes Boolean values')
            value = mapping[expression[2]]
        else:
            if row(expression) != 'number':
                raise UnsupportedSql('Grouped aggregate value type')
            value = row_sql(expression)
        condition = None
        if predicate is not None:
            if row(predicate) != 'boolean':
                raise UnsupportedSql('Grouped iterator predicate type')
            condition = row_sql(predicate)
        for target,column,operator,cohort_value in self.cohorts:
            reference=mapping[column];dtype=schema[column]
            if dtype=='VARCHAR' and isinstance(cohort_value,str):
                cohort='lower('+('COALESCE('+reference+",'')" if operator=='=' else reference)+')'+(' IS NOT DISTINCT FROM ' if operator=='==' else '=')+'lower('+sv(cohort_value)+')'
            elif dtype.startswith(_NUMERIC) and (cohort_value is None or isinstance(cohort_value,(int,float,Decimal)) and not isinstance(cohort_value,bool)):
                cohort=reference+' IS NOT DISTINCT FROM '+sv(cohort_value) if operator=='==' else 'COALESCE('+reference+',0)=COALESCE('+sv(cohort_value)+',0)'
            else:raise UnsupportedSql('Grouped cohort value type')
            condition='('+condition+') AND ('+cohort+')' if condition else cohort
        if fn == 'MEDIANX':
            value = 'COALESCE(' + value + ',0)'
        qualifier=' FILTER (WHERE '+condition+')' if condition else ''
        if fn in ('COUNT', 'COUNTA', 'COUNTROWS'):
            sql = 'NULLIF(COUNT(' + value + ')'+qualifier+',0)'
        elif fn == 'DISTINCTCOUNT':
            column = expression[2]
            distinct = 'lower(' + value + ')' if schema[column] == 'VARCHAR' else value
            total='COUNT(*)'+qualifier;nonblank='COUNT('+value+')'+qualifier
            sql = '(CASE WHEN '+total+'=0 THEN NULL ELSE COUNT(DISTINCT ' + distinct + ')'+qualifier+'+CASE WHEN '+total+'>'+nonblank+' THEN 1 ELSE 0 END END)'
        else:
            sqlfn = {'AVERAGE': 'AVG', 'AVERAGEX': 'AVG', 'SUMX': 'SUM', 'MINX': 'MIN', 'MAXX': 'MAX', 'MEDIANX': 'MEDIAN'}.get(fn, fn)
            sql = sqlfn + '(' + value + ')'+qualifier
        if sql not in self.aggregates:
            self.aggregates.append(sql)
        index = self.aggregates.index(sql)
        return '"__a".' + qi('a' + str(index)), 'number'


def evaluate_grouped(con, model, payload, budget, expressions_by_index=None):
    from dax_runtime import RuntimeEvaluator
    groups, fields = payload['groups'], payload['fields']
    grouping = [(i, f.get('Column') or f.get('GroupRef')) for i, f in enumerate(fields) if f.get('Column') or f.get('GroupRef')]
    if not groups or not grouping or len(grouping) > 8 or len(groups) > 100000:
        raise UnsupportedSql('Grouped scan dimensions')
    external, scope = groups[0].get('externalFilters'), groups[0].get('scope')
    if external is None or any(g.get('externalFilters') != external or g.get('scope') != scope for g in groups):
        raise UnsupportedSql('Grouped scan contexts')
    engine = RuntimeEvaluator(con, model, {}, filters=list(external), budget=budget)
    engine.external_filters = external
    engine.scope = [tuple(c) for c in scope or []]
    columns = []
    for index, field in grouping:
        table, column = engine.column(('col', field['Expression']['SourceRef']['Entity'], field['Property']))
        dtype = type_name(engine,table,column)
        if not all(c.isalnum() or c in '(),_ ' for c in dtype):
            raise UnsupportedSql('Grouped scan identity type')
        columns.append((index, table, column, dtype))
    engine.sql_bound_groups={(table,column):'"__g".'+qi('v'+str(index)) for index,table,column,dtype in columns}
    for group in groups:
        if group.get('filters', [])[:len(external)] != external:
            raise UnsupportedSql('Grouped scan filter prefix')
        tail = group.get('filters', [])[len(external):]
        if len(tail) != len(columns):
            raise UnsupportedSql('Grouped scan additional predicates')
        for f, (index, table, column, dtype) in zip(tail, columns):
            if str(index) not in group.get('values', {}) and index not in group.get('values', {}):
                raise UnsupportedSql('Grouped scan missing identity')
            value = group['values'].get(str(index), group['values'].get(index))
            expected = qi(table) + '.' + qi(column) + (' IS NULL' if value is None else ' = ' + sv(value))
            legacy = qi(table) + '.' + qi(column) + ' = ' + str(value) if isinstance(value, float) else expected
            if f.get('sql') not in (expected, legacy) or f.get('table') != table or f.get('columns') != [column]:
                raise UnsupportedSql('Grouped scan noncanonical predicate')

    plan = _Plan(engine)
    output = []
    for index, field in enumerate(fields):
        if expressions_by_index and index in expressions_by_index:
            value = plan.compile(expressions_by_index[index])[0]
        elif field.get('Column') or field.get('GroupRef'):
            value = '"__g".' + qi('v' + str(index))
        elif field.get('Measure'):
            measure = field['Measure']
            value = plan.compile(('col', measure.get('Expression', {}).get('SourceRef', {}).get('Entity'), measure['Property']))[0]
        elif field.get('Aggregation'):
            aggregate = field['Aggregation']
            column = aggregate['Expression'].get('Column')
            function = {0: 'SUM', 1: 'AVERAGE', 2: 'DISTINCTCOUNT', 3: 'MIN', 4: 'MAX', 5: 'COUNTA', 6: 'MEDIAN'}.get(aggregate['Function'])
            if column is None or function is None:
                raise UnsupportedSql('Grouped scan field aggregate')
            value = plan.compile(('call', function, [('col', column['Expression']['SourceRef']['Entity'], column['Property'])]))[0]
        else:
            raise UnsupportedSql('Grouped scan visual field')
        output.append(value + ' AS ' + qi('out' + str(index)))
    if plan.fact is None or not plan.aggregates:
        raise UnsupportedSql('Grouped scan has no fact aggregates')

    # Merge common relationship prefixes. Two predicates on the same bridge
    # branch must match the same bridge row, just as ContextMixin.where does.
    joins, aliases, predicates = [], {(): '"__f"'}, []
    for index, table, column, dtype in columns:
        path = engine.path(plan.fact, table)
        if path is None:
            continue  # Disconnected categories repeat the same aggregate.
        prefix = ()
        for edge in path:
            parent = aliases[prefix]
            prefix = (*prefix, edge)
            if prefix not in aliases:
                alias = qi('__r' + str(len(joins)))
                aliases[prefix] = alias
                a, ac, b, bc = edge
                joins.append((b, alias, parent + '.' + qi(ac) + '=' + alias + '.' + qi(bc)))
        predicates.append(aliases[prefix] + '.' + qi(column) + ' IS NOT DISTINCT FROM "__g".' + qi('v' + str(index)))

    relation = '__group_scan_' + uuid.uuid4().hex
    view = relation + '_input'
    import pyarrow as pa
    records = {'__index': pa.array(range(len(groups)), type=pa.int64())}
    for index, table, column, dtype in columns:
        records['v' + str(index)] = pa.array([None if g['values'].get(str(index), g['values'].get(index)) is None else str(g['values'].get(str(index), g['values'].get(index))) for g in groups], type=pa.string())
    engine.check_budget()
    con.register(view, pa.table(records))
    try:
        con.execute('CREATE TEMP TABLE ' + qi(relation) + ' AS SELECT __index,' + ','.join('CAST(' + qi('v' + str(i)) + ' AS ' + dtype + ') AS ' + qi('v' + str(i)) for i, table, column, dtype in columns) + ' FROM ' + qi(view))
    finally:
        con.unregister(view)
    timer = threading.Timer(max(.001, budget['deadline'] - time.monotonic()), con.interrupt)
    timer.daemon = True
    timer.start()
    try:
        row_key = '__fact_row_' + uuid.uuid4().hex
        fact_columns = {d[0] for d in model_schema(engine,plan.fact)}
        while row_key in fact_columns:
            row_key = '__fact_row_' + uuid.uuid4().hex
        compiler = SqlDax(engine)
        fact = '(SELECT ROW_NUMBER() OVER () AS ' + qi(row_key) + ',* FROM ' + compiler.source(plan.fact) + ')'
        aggregate_values = ','.join(value + ' AS ' + qi('a' + str(index)) for index, value in enumerate(plan.aggregates))
        if predicates:
            source = '"__facts" AS "__f"'
            for table, alias, condition in joins:
                source += ' JOIN (SELECT * FROM ' + compiler.source(table) + ') AS ' + alias + ' ON ' + condition
            source += ' JOIN ' + qi(relation) + ' AS "__g" ON ' + ' AND '.join(predicates)
            members = 'SELECT DISTINCT "__g".__index,"__f".' + qi(row_key) + ' FROM ' + source
            aggregates = 'SELECT "__m".__index,' + aggregate_values + ' FROM "__members" AS "__m" JOIN "__facts" AS "__f" ON "__f".' + qi(row_key) + '="__m".' + qi(row_key) + ' GROUP BY "__m".__index'
            sql = 'WITH "__facts" AS MATERIALIZED ' + fact + ',"__members" AS (' + members + '),"__aggregates" AS (' + aggregates + ') SELECT ' + ','.join(output) + ' FROM ' + qi(relation) + ' AS "__g" LEFT JOIN "__aggregates" AS "__a" ON "__a".__index="__g".__index ORDER BY "__g".__index'
        else:
            sql = 'WITH "__facts" AS MATERIALIZED ' + fact + ',"__aggregates" AS (SELECT ' + aggregate_values + ' FROM "__facts" AS "__f") SELECT ' + ','.join(output) + ' FROM ' + qi(relation) + ' AS "__g" CROSS JOIN "__aggregates" AS "__a" ORDER BY "__g".__index'
        try:
            engine.check_budget()
            result = con.execute(sql).fetchall()
            engine.check_budget()
            budget['grouped_relationship_scans'] = budget.get('grouped_relationship_scans', 0) + 1
            return result
        except Exception:
            engine.check_budget()
            raise
    finally:
        timer.cancel()
        con.execute('DROP TABLE IF EXISTS ' + qi(relation))


def evaluate_context_rows(engine,rows,expressions,env=None):
    """Batch explicit/measure transitions over partial physical iterator rows.

    Bare aggregates remain in their original filter context and are rejected.
    Foreign-key projections which would expand a transition to more tables are
    also rejected; the ordinary evaluator handles those richer row contexts.
    """
    if engine.iterator_depth or engine.row_stack or not rows or not rows.columns or len(rows)>100000:
        raise UnsupportedSql('Grouped iterator context')
    columns=list(rows.columns);tables={t for t,c in columns}
    if len(tables)!=1 or next(iter(tables)).startswith('__'):
        raise UnsupportedSql('Grouped iterator lineage')
    table=next(iter(tables));names=[c for t,c in columns]
    if len(set(names))!=len(names) or any(len(row)!=2 or row[0]!=table or set(row[1])!=set(names) for row in rows):
        raise UnsupportedSql('Grouped iterator needs genuine projected physical rows')
    if any(r.get('IsActive') and r.get('Cardinality') in ('M:1','1:1') and (r['FromTableName'],r['FromColumnName']) in columns for r in engine.model.get('relationships',[])):
        raise UnsupportedSql('Grouped iterator requires expanded row transition')
    bindings={k.casefold():v for k,v in (env or {}).items()}
    def bind(node,local=frozenset()):
        kind=node[0]
        if kind=='name' and node[1].casefold() not in local:
            name=node[1].casefold()
            if name not in bindings:return node
            value=bindings[name]
            if value is not None and not isinstance(value,(bool,int,float,Decimal,str)):
                raise UnsupportedSql('Grouped iterator scalar binding')
            return ('lit',value)
        if kind=='let':
            scope=set(local);items=[]
            for name,value in node[1]:
                items.append((name,bind(value,frozenset(scope))));scope.add(name.casefold())
            return ('let',items,bind(node[2],frozenset(scope)))
        if kind=='call':return ('call',node[1],[bind(x,local) for x in node[2]])
        if kind in ('op','unary'):return (*node[:2],*[bind(x,local) for x in node[2:]])
        return node
    def safe(node):
        kind=node[0]
        if kind in ('lit','name'):return
        if kind=='col':
            if node[2].casefold() in {name.casefold() for name in names} and (not node[1] or node[1].casefold()==table.casefold()):
                raise UnsupportedSql('Grouped iterator physical column shadows a measure')
            if not any(m['Name'].casefold()==node[2].casefold() and (not node[1] or m['TableName'].casefold()==node[1].casefold()) for m in engine.model['measures']):
                raise UnsupportedSql('Grouped iterator bare column')
            return
        if kind=='call':
            if node[1]=='CALCULATE':return  # Validated by the grouped plan.
            if node[1] not in ('IF','COALESCE','DIVIDE','ISBLANK','NOT','TRUE','FALSE','BLANK'):
                raise UnsupportedSql('Grouped iterator bare/context-sensitive function')
            for value in node[2]:safe(value)
            return
        if kind=='let':
            for name,value in node[1]:safe(value)
            safe(node[2]);return
        if kind in ('op','unary'):
            for value in node[2:]:safe(value)
            return
        raise UnsupportedSql('Grouped iterator expression')
    bound=[bind(node) for node in expressions]
    for node in bound:safe(node)
    base=engine.remove(columns);fields=[{'Column':{'Expression':{'SourceRef':{'Entity':t}},'Property':c}} for t,c in columns]+[{} for node in expressions]
    groups=[]
    for index,row in enumerate(rows):
        if index%128==0:engine.check_budget()
        values={str(i):row[1][c] for i,(t,c) in enumerate(columns)}
        tail=[{'table':t,'columns':[c],'sql':qi(t)+'.'+qi(c)+(' IS NULL' if values[str(i)] is None else ' = '+sv(values[str(i)]))} for i,(t,c) in enumerate(columns)]
        groups.append({'values':values,'filters':[*base,*tail],'externalFilters':base,'scope':engine.scope})
    result=evaluate_grouped(engine.con,engine.model,{'fields':fields,'groups':groups},engine.budget,{len(columns)+i:node for i,node in enumerate(bound)})
    return [list(row[len(columns):]) for row in result]
