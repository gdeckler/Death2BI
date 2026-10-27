"""Extended DAX dispatch, with shared operation/time budgets across contexts."""
import datetime as dt
import math
import statistics
import time
from decimal import Decimal
from dax_metadata import schema as model_schema, type_name
from dax_core import CoreEvaluator, Parser, qi, cached_ast
from dax_context import ContextMixin
from dax_budget import check_budget, limits
from dax_functions import FUNCTIONS, DEFAULT_ARGUMENTS, number, text, date, integer, power, numeric_pair


class Table(list):
    def __init__(self, rows=(), columns=()):
        super().__init__(rows)
        self.columns = list(columns)


AGGREGATES = {'SUM', 'AVERAGE', 'MIN', 'MAX', 'COUNT', 'COUNTA', 'COUNTBLANK', 'DISTINCTCOUNT', 'DISTINCTCOUNTNOBLANK', 'PRODUCT', 'MEDIAN', 'STDEV.S', 'STDEV.P', 'VAR.S', 'VAR.P'}
ITERATORS = {'SUMX': 'SUM', 'AVERAGEX': 'AVERAGE', 'MINX': 'MIN', 'MAXX': 'MAX', 'COUNTX': 'COUNT', 'COUNTAX': 'COUNTA', 'PRODUCTX': 'PRODUCT', 'MEDIANX': 'MEDIAN', 'STDEVX.S': 'STDEV.S', 'STDEVX.P': 'STDEV.P', 'VARX.S': 'VAR.S', 'VARX.P': 'VAR.P'}
SPECIAL = {
    'FILTER': (2, 2, 'Table manipulation'), 'COUNTROWS': (1, 1, 'Aggregation'),
    'SELECTEDMEASURE': (0,0,'Format expression'), 'SELECTEDMEASURENAME': (0,0,'Format expression'), 'SELECTEDMEASUREFORMATSTRING': (0,0,'Format expression'),
    'IF': (2, 3, 'Logical'), 'IF.EAGER': (2, 3, 'Logical'), 'SWITCH': (3, 99, 'Logical'),
    'IFERROR': (2, 2, 'Logical'), 'ISERROR': (1, 1, 'Information'),
    'COALESCE': (1, 99, 'Logical'), 'DIVIDE': (2, 3, 'Math and trig'), 'ERROR': (1, 1, 'Information'),
    'VALUES': (1, 1, 'Filter'), 'DISTINCT': (1, 1, 'Table manipulation'),
    'TREATAS': (2, 50, 'Filter'), 'DATATABLE': (3, 99, 'Table manipulation'),
    'CONTAINS': (3, 99, 'Information'),
    'SELECTEDVALUE': (1, 2, 'Filter'), 'HASONEVALUE': (1, 1, 'Information'),
    'ISFILTERED': (1, 1, 'Information'), 'ISCROSSFILTERED': (1, 1, 'Information'),
    'HASONEFILTER': (1, 1, 'Information'), 'FILTERS': (1, 1, 'Filter'),
    'CROSSFILTER': (3, 3, 'Filter'), 'CALCULATE': (1, 99, 'Filter'), 'CALCULATETABLE': (1, 99, 'Filter'),
    'ALL': (0, 99, 'Filter'), 'ALLNOBLANKROW': (1, 99, 'Filter'), 'REMOVEFILTERS': (0, 99, 'Filter'),
    'ALLEXCEPT': (2, 99, 'Filter'), 'KEEPFILTERS': (1, 1, 'Filter'),
    'RELATED': (1, 1, 'Relationship'), 'RELATEDTABLE': (1, 1, 'Relationship'),
    'LOOKUPVALUE': (3, 99, 'Filter'), 'ISEMPTY': (1, 1, 'Information'),
    'TOPN': (2, 99, 'Table manipulation'), 'RANKX': (2, 5, 'Statistical'),
    'CONCATENATEX': (2, 51, 'Text'), 'EARLIER': (1, 2, 'Filter'), 'ADDCOLUMNS': (3, 99, 'Table manipulation'),
    'SELECTCOLUMNS': (2, 99, 'Table manipulation'), 'ROW': (2, 98, 'Table manipulation'),
    'UNION': (2, 99, 'Table manipulation'), 'INTERSECT': (2, 2, 'Table manipulation'),
    'EXCEPT': (2, 2, 'Table manipulation'), 'CROSSJOIN': (2, 99, 'Table manipulation'),
    'GENERATE': (2, 2, 'Table manipulation'), 'GENERATEALL': (2, 2, 'Table manipulation'),
    'GENERATESERIES': (2, 3, 'Table manipulation'), 'CALENDAR': (2, 2, 'Date and time'),
    'FIRSTDATE': (1, 1, 'Time intelligence'), 'LASTDATE': (1, 1, 'Time intelligence'),
    'DATESBETWEEN': (3, 3, 'Time intelligence'), 'DATESYTD': (1, 1, 'Time intelligence'),
    'DATESQTD': (1, 1, 'Time intelligence'), 'DATESMTD': (1, 1, 'Time intelligence'),
    'TOTALYTD': (2, 3, 'Time intelligence'), 'TOTALQTD': (2, 3, 'Time intelligence'),
    'TOTALMTD': (2, 3, 'Time intelligence'), 'PATH': (2, 2, 'Parent and child'),
    'GROUPBY': (1, 99, 'Table manipulation'), 'CURRENTGROUP': (0, 0, 'Table manipulation'),
    'SUMMARIZE': (2, 99, 'Table manipulation'), 'ISINSCOPE': (1, 1, 'Information'),
    'ALLSELECTED': (0, 99, 'Filter'), 'ISONORAFTER': (2, 99, 'Filter'),
    'SAMEPERIODLASTYEAR': (1, 1, 'Time intelligence'),
}
for name in AGGREGATES:
    SPECIAL[name] = (1, 2 if name in ('MIN', 'MAX') else 1, 'Aggregation')
for name in ITERATORS:
    SPECIAL[name] = (2, 2, 'Aggregation')
for name in ('PERCENTILE.INC', 'PERCENTILE.EXC'):
    SPECIAL[name] = (2, 2, 'Statistical')
for name in ('PERCENTILEX.INC', 'PERCENTILEX.EXC'):
    SPECIAL[name] = (3, 3, 'Statistical')


def support_catalog():
    result = {n: {'name': n, 'family': family, 'minArgs': lo, 'maxArgs': hi} for n, (lo, hi, family, _) in FUNCTIONS.items()}
    result.update({n: {'name': n, 'family': family, 'minArgs': lo, 'maxArgs': hi} for n, (lo, hi, family) in SPECIAL.items()})
    return sorted(result.values(), key=lambda x: (x['family'], x['name']))


class RuntimeEvaluator(ContextMixin, CoreEvaluator):
    def __init__(self, con, model, contexts=None, filters=None, budget=None):
        super().__init__(con, model, contexts or {})
        self.filters = filters
        if budget is None:
            seconds, max_steps = limits()
            started = time.monotonic()
            budget = {'deadline': started + seconds, 'started': started, 'steps': 0, 'seconds': seconds, 'max_steps': max_steps}
        self.budget = budget
        self.deadline = self.budget['deadline']
        self.scope = []
        self.external_filters = filters
        self.iterator_depth = 0
        self.row_stack = []
        self.selection_shadows = []
        self.transition_row = None

    def check_budget(self):
        check_budget(self.budget, 1)

    @staticmethod
    def equal(a, b, strict=False):
        if strict and (a is None or b is None):
            return a is b
        if a is None:
            a = '' if isinstance(b, str) else False if isinstance(b, bool) else 0
        if b is None:
            b = '' if isinstance(a, str) else False if isinstance(a, bool) else 0
        return a.casefold() == b.casefold() if isinstance(a, str) and isinstance(b, str) else a == b

    @staticmethod
    def scalar(value):
        if isinstance(value, Table):
            if not value:
                return None
            if len(value) != 1 or len(value[0][1]) != 1:
                raise ValueError('Multiple table values cannot be converted to a scalar')
            return next(iter(value[0][1].values()))
        return value

    @staticmethod
    def as_table(value):
        if not isinstance(value, Table):
            raise ValueError('Expected a DAX table expression')
        return value

    @staticmethod
    def distinct(values):
        seen, rows = set(), []
        for row in values:
            key = tuple(v.casefold() if isinstance(v, str) else v for v in row[1].values())
            if key not in seen:
                rows.append(row)
                seen.add(key)
        return Table(rows, values.columns)

    def table(self, name):
        self.check_budget()
        table = self.canonical_table(name)
        shared = self.budget.setdefault('tables', {})
        where = self.where(table)
        key = (table, where)
        if key in shared:
            return shared[key]
        if table not in self.cache:
            cursor = self.con.execute('SELECT * FROM ' + qi(table) + (' WHERE ' + where if where else '') + ' LIMIT 100001')
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
            if len(rows) > 100000:
                raise RuntimeError('Python DAX row limit exceeded (100,000 rows per table/context)')
            self.cache[table] = Table([(table, dict(zip(columns, r))) for r in rows], [(table, c) for c in columns])
            while shared and (len(shared) >= 64 or sum(len(v) for v in shared.values()) + len(rows) > 200000):
                del shared[next(iter(shared))]
            shared[key] = self.cache[table]
        return self.cache[table]

    def project_columns(self, cols, distinct=True):
        table=cols[0][0]
        if any(t!=table for t,c in cols):raise ValueError('Projected columns must belong to one table')
        self.check_budget();where=self.where(table)
        # A request uses one secured connection. Cache immutable SQL records,
        # rather than mutable DAX Table rows, for repeated selected domains.
        key=(table,tuple(cols),bool(distinct),where)
        cache=self.budget.setdefault('projected_columns',{})
        cached=cache.get(key)
        if cached is not None:
            rows=cached[0]
            return Table([(table,dict(zip([c for t,c in cols],r))) for r in rows],cols)
        sql='SELECT '+('DISTINCT ' if distinct else '')+','.join(qi(c) for t,c in cols)+' FROM '+qi(table)
        if where:sql+=' WHERE '+where
        rows=self.con.execute(sql+' LIMIT 100001').fetchall()
        if len(rows)>100000:raise RuntimeError('Python DAX row limit exceeded (100,000 rows per table/context)')
        cells=len(rows)*len(cols)
        size=len(where)*2+sum(len(v)*2 if isinstance(v,str) else len(v) if isinstance(v,bytes) else 32 for record in rows for v in record)
        immutable=all(v is None or isinstance(v,(str,bytes,int,float,Decimal,dt.date,dt.time,dt.timedelta)) for record in rows for v in record)
        if immutable and cells<=200000 and size<=16000000:
            total_cells=self.budget.get('projected_column_cells',0)
            total_bytes=self.budget.get('projected_column_bytes',0)
            while cache and (len(cache)>=128 or total_cells+cells>200000 or total_bytes+size>16000000):
                _,old_cells,old_size=cache.pop(next(iter(cache)))
                total_cells-=old_cells;total_bytes-=old_size
            cache[key]=(tuple(rows),cells,size)
            self.budget['projected_column_cells']=total_cells+cells
            self.budget['projected_column_bytes']=total_bytes+size
        return Table([(table,dict(zip([c for t,c in cols],r))) for r in rows],cols)

    def project(self, node, distinct=False):
        return self.project_columns([self.column(node)],distinct)

    def shadow_measure(self,name,table=None):
        """Avoid repeatedly lowering a known row-shadow dependency as SQL."""
        if not self.selection_shadows:return False
        cache=self.budget.setdefault('shadow_measure_dependencies',{})
        def measure(name,table,seen):
            matches=[m for m in self.model['measures'] if m['Name'].casefold()==name.casefold() and (not table or m['TableName'].casefold()==table.casefold())]
            if len(matches)!=1:return False
            definition=matches[0];key=(definition['TableName'],definition['Name'],definition['Expression'])
            if key in cache:return cache[key]
            if key in seen:return False
            result=walk(cached_ast(self,definition['Expression']),seen|{key})
            cache[key]=result
            return result
        def walk(node,seen):
            if node[0]=='call':return node[1]=='ALLSELECTED' or any(walk(a,seen) for a in node[2])
            if node[0]=='col':return measure(node[2],node[1],seen)
            if node[0]=='let':return any(walk(a,seen) for _,a in node[1]) or walk(node[2],seen)
            if node[0] in ('op','unary'):return any(walk(a,seen) for a in node[2:])
            if node[0] in ('tuple','table'):return any(walk(a,seen) for a in node[1])
            return False
        return measure(name,table,set())

    def measure(self, name, table=None, row=None):
        if row:
            # HTML/table iterators frequently repeat row-local measures after
            # their Top N pass. Reuse the same safe kernel for those scalar
            # cells instead of rebuilding a full SQL transition for each cell.
            from dax_rowset import evaluate_rows
            from dax_sql import UnsupportedSql
            child=self.child(self.filters);child.contexts=self.contexts
            if child.row_stack and child.row_stack[-1] is row:child.row_stack=child.row_stack[:-1]
            singletons=self.budget.setdefault('scalar_rowsets',{})
            key=id(row[1]);cached=singletons.get(key)
            if cached is not None and cached[0] is row[1] and (len(row)<3 or cached[1] is row[2]):singleton=cached[2]
            else:
                singleton=Table([row])
                if len(singletons)<128:singletons[key]=(row[1],row[2] if len(row)>2 else None,singleton)
            try:return evaluate_rows(child,singleton,[('col',table,name)])[0][0]
            except UnsupportedSql:pass
            matches=[m for m in self.model['measures'] if m['Name'].casefold()==name.casefold() and (not table or m['TableName'].casefold()==table.casefold())]
            if len(matches)==1:
                definition=matches[0];expression=cached_ast(self,definition['Expression'])
                if expression[0]=='call' and expression[1] in ('CALCULATE','CALCULATETABLE'):
                    identity=(definition['TableName'],definition['Name'])
                    if identity in self.stack or len(self.stack)>=30:raise ValueError('Cyclic or excessive DAX measure dependency')
                    self.stack.append(identity)
                    try:return self.scalar(self.run(expression,{},row))
                    finally:self.stack.pop()
            child = self.child(self.transition(row))
            child.iterator_depth += 1
            if self.selection_shadows:
                frame=self.selection_shadows[-1]
                if frame.get('row') is row and frame.get('row_measure_safe') and self.filters==frame['context_filters']:
                    child.transition_row=row
            return child.measure(name, table)
        key=self.measure_cache_key(name,table)
        cache=self.budget.setdefault('measure_values',{})
        if key in cache:return cache[key]
        # Nested measures deserve the same conservative SQL fast path as visual
        # roots; HTML/string measures often depend on costly numeric iterators.
        from dax_sql import evaluate_scalar,UnsupportedSql
        if self.shadow_measure(name,table):result=self.scalar(super().measure(name,table))
        else:
            try:result=evaluate_scalar(self,name,table)
            except UnsupportedSql:result=self.scalar(super().measure(name, table))
        size=len(result) if isinstance(result,str) else 32
        if len(cache)<2000 and self.budget.get('measure_cache_bytes',0)+size<32000000:
            cache[key]=result;self.budget['measure_cache_bytes']=self.budget.get('measure_cache_bytes',0)+size
        return result

    def measure_cache_key(self,name,table=None):
        """The complete secured evaluation context for a request-local value."""
        return (name.casefold(),(table or '').casefold(),repr(self.filters),repr(self.contexts),repr(self.scope),repr(self.external_filters),bool(self.iterator_depth),repr(self.row_stack),repr(self.model.get('relationships',[])),self.selection_shadow_stamp())

    def run(self,n,env=None,row=None):
        pushed=row is not None and (not self.row_stack or self.row_stack[-1] is not row)
        if pushed:self.row_stack.append(row)
        try:return self._run(n,env,row)
        finally:
            if pushed:self.row_stack.pop()

    def _run(self, n, env=None, row=None):
        self.check_budget()
        env = {} if env is None else env
        kind = n[0]
        if kind=='call' and n[1] in ('SELECTEDMEASURE','SELECTEDMEASURENAME','SELECTEDMEASUREFORMATSTRING') and hasattr(self,'selected_measure'):
            if n[2]:raise ValueError(n[1]+' takes no arguments')
            return {'SELECTEDMEASURE':self.selected_measure,'SELECTEDMEASURENAME':self.selected_measure_name,'SELECTEDMEASUREFORMATSTRING':self.selected_measure_format}[n[1]]
        if kind == 'tuple':
            return tuple(self.scalar(self.run(x, env, row)) for x in n[1])
        if kind == 'table':
            values = [self.run(x, env, row) for x in n[1]]
            width = len(values[0]) if values and isinstance(values[0], tuple) else 1
            tuples = [v if isinstance(v, tuple) else (self.scalar(v),) for v in values]
            if any(len(v) != width for v in tuples):
                raise ValueError('DAX table constructor rows have inconsistent column counts')
            names = ['Value'] if width == 1 else ['Value' + str(i + 1) for i in range(width)]
            return Table([('__virtual', dict(zip(names, v))) for v in tuples], [('__virtual', c) for c in names])
        if kind == 'name':
            if n[1].casefold() in env:
                return env[n[1].casefold()]
            constants = {'ASC': 'ASC', 'DESC': 'DESC', 'SKIP': 'SKIP', 'DENSE': 'DENSE', 'TEXT': 0, 'INTEGER': 1}
            constants.update({k: k for k in ('YEAR', 'QUARTER', 'MONTH', 'WEEK', 'DAY', 'HOUR', 'MINUTE', 'SECOND')})
            if n[1].upper() in constants:
                return constants[n[1].upper()]
        if kind == 'col':
            if row and len(row) > 2 and n[1]:
                match = next((value for (table, col), value in row[2].items() if table.casefold() == n[1].casefold() and col.casefold() == n[2].casefold()), None)
                if any(table.casefold() == n[1].casefold() and col.casefold() == n[2].casefold() for table, col in row[2]):
                    return match
            if row and (not n[1] or n[1].casefold() == row[0].casefold()):
                col = next((c for c in row[1] if c.casefold() == n[2].casefold()), None)
                if col is not None:
                    return row[1][col]
            if not n[1]:
                for outer in reversed(self.row_stack[:-1]):
                    col=next((c for c in outer[1] if c.casefold()==n[2].casefold()),None)
                    if col is not None:return outer[1][col]
            if not n[1] or any(m['Name'].casefold() == n[2].casefold() and m['TableName'].casefold() == n[1].casefold() for m in self.model['measures']):
                return self.measure(n[2], n[1], row)
            if n[1]:
                for outer in reversed(self.row_stack[:-1]):
                    lineage=outer[2] if len(outer)>2 else {(outer[0],c):value for c,value in outer[1].items()}
                    for (table,col),value in lineage.items():
                        if table.casefold()==n[1].casefold() and col.casefold()==n[2].casefold():return value
            return self.scalar(self.project(n,True))
        if kind == 'unary':
            return number(self.scalar(self.run(n[2], env, row))) * (1 if n[1] == '+' else -1)
        if kind == 'op':
            if n[1] == 'IN':
                left = self.run(n[2], env, row)
                left = left if isinstance(left, tuple) else (self.scalar(left),)
                values = self.as_table(self.run(n[3], env, row))
                if len(left) != len(values.columns):
                    raise ValueError('IN operands have different column counts')
                return any(all(self.equal(a, b, True) for a, b in zip(left, r[1].values())) for r in values)
            a, b = (self.scalar(self.run(x, env, row)) for x in n[2:])
            op = n[1]
            if op == '&':
                return text(a) + text(b)
            if op in ('=', '==', '<>'):
                return not self.equal(a, b) if op == '<>' else self.equal(a, b, op == '==')
            if op in ('&&', '||'):
                return bool(a) and bool(b) if op == '&&' else bool(a) or bool(b)
            if op in ('<', '>', '<=', '>='):
                a, b = (0 if a is None else a), (0 if b is None else b)
                if isinstance(a, (dt.date, dt.datetime)) and isinstance(b, (dt.date, dt.datetime)):
                    a, b = date(a), date(b)
                if isinstance(a, str) and isinstance(b, str):
                    a, b = a.casefold(), b.casefold()
                return {'<': lambda: a < b, '>': lambda: a > b, '<=': lambda: a <= b, '>=': lambda: a >= b}[op]()
            if a is None and b is None:
                return None
            if op == '*' and (a is None or b is None):
                return None
            if isinstance(a, (dt.date, dt.datetime)) or isinstance(b, (dt.date, dt.datetime)):
                if op == '-' and isinstance(a, (dt.date, dt.datetime)) and isinstance(b, (dt.date, dt.datetime)):
                    return (date(a) - date(b)).total_seconds() / 86400
                if op in ('+', '-') and isinstance(a, (dt.date, dt.datetime)):
                    return date(a) + dt.timedelta(days=number(b) * (1 if op == '+' else -1))
                if op == '+' and isinstance(b, (dt.date, dt.datetime)):
                    return date(b) + dt.timedelta(days=number(a))
                raise ValueError('Unsupported date arithmetic operation')
            a,b=numeric_pair(a,b)
            if op == '/' and not b:
                raise ZeroDivisionError('DAX division by zero; use DIVIDE for an alternate result')
            return {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b, '/': lambda: a / b, '^': lambda: power(a, b)}[op]()
        if kind != 'call':
            return super().run(n, env, row)
        fn, args = n[1:]
        definition = SPECIAL.get(fn) or FUNCTIONS.get(fn)
        if definition is None:
            functions=[f for f in self.model.get('functions',[]) if f.get('Name','').casefold()==fn.casefold()]
            if len(functions)==1:
                import re
                source=functions[0]['Expression'];match=re.match(r'\s*\(([^()]*)\)\s*=>',source)
                if not match:raise ValueError('Unsupported DAX user-function signature: '+fn)
                params=[p.strip() for p in match[1].split(',')] if match[1].strip() else []
                if any(not re.fullmatch(r'[A-Za-z_]\w*',p) for p in params) or len({p.casefold() for p in params})!=len(params):raise ValueError('Unsupported DAX user-function parameters: '+fn)
                if len(args)!=len(params):raise ValueError('Invalid argument count for DAX user function '+fn)
                depth=self.budget.get('udf_depth',0)
                if depth>=32:raise ValueError('DAX user-function call depth exceeded (32)')
                local={p.casefold():self.run(a,env,row) for p,a in zip(params,args)}
                cache=self.budget.setdefault('udf_ast',{});key=(fn,source)
                if key not in cache:cache[key]=Parser(source[match.end():],self.model.get('functions',[])).parse()
                self.budget['udf_depth']=depth+1
                try:return self.run(cache[key],local,row)
                finally:self.budget['udf_depth']=depth
            raise ValueError('Unsupported DAX function: ' + fn + ' (see DAX_SUPPORT.md)')
        if not definition[0] <= len(args) <= definition[1]:
            raise ValueError('Invalid argument count for DAX ' + fn)
        ev = lambda node: self.run(node, env, row)
        if fn=='EARLIER':
            depth=int(self.scalar(ev(args[1]))) if len(args)>1 else 1
            if depth<1 or depth>=len(self.row_stack):raise ValueError('EARLIER requires an outer row context')
            return self.run(args[0],env,self.row_stack[-1-depth])
        scalar = lambda node: self.scalar(ev(node))
        if fn=='FORMAT' and len(args)==2:
            return FUNCTIONS[fn][3](scalar(args[0]),scalar(args[1]),self.model.get('reportSettings',{}).get('locale') or 'en-US')
        if fn in FUNCTIONS:
            defaults = DEFAULT_ARGUMENTS.get(fn,{})
            result = FUNCTIONS[fn][3](*[defaults[i] if a == ('lit',None) and i in defaults else scalar(a) for i,a in enumerate(args)])
            if isinstance(result, complex) or isinstance(result, float) and not math.isfinite(result):
                raise ValueError('Non-finite DAX result')
            return result
        if fn in ('IF', 'IF.EAGER'):
            condition = scalar(args[0])
            if fn == 'IF.EAGER':
                a, b = ev(args[1]), ev(args[2]) if len(args) > 2 else None
                return a if condition else b
            return ev(args[1]) if condition else ev(args[2]) if len(args) > 2 else None
        if fn == 'SWITCH':
            value, pairs = scalar(args[0]), args[1:]
            for i in range(0, len(pairs) - 1, 2):
                if self.equal(value, scalar(pairs[i]), True):
                    return ev(pairs[i + 1])
            return ev(pairs[-1]) if len(pairs) % 2 else None
        if fn in ('IFERROR', 'ISERROR'):
            try:
                value = ev(args[0])
                return False if fn == 'ISERROR' else value
            except (ValueError, ArithmeticError):
                return True if fn == 'ISERROR' else ev(args[1])
        if fn == 'ERROR':
            raise ValueError(text(scalar(args[0])))
        if fn == 'COALESCE':
            for arg in args:
                value = scalar(arg)
                if value is not None:
                    return value
            return None
        if fn == 'DIVIDE':
            a, b = scalar(args[0]), scalar(args[1])
            if not b:return scalar(args[2]) if len(args)>2 else None
            a,b=numeric_pair(a,b);return a/b
        if fn in AGGREGATES or fn in ITERATORS or fn.startswith('PERCENTILE'):
            return self.aggregate(fn, args, env, row)
        if fn in ('COUNTROWS', 'ISEMPTY'):
            if args[0][0]=='name' and args[0][1].casefold() not in env:
                table=self.canonical_table(args[0][1]);where=self.where(table)
                count=self.con.execute('SELECT COUNT(*) FROM '+qi(table)+(' WHERE '+where if where else '')).fetchone()[0]
                self.check_budget()
                return count==0 if fn=='ISEMPTY' else count or None
            values = self.as_table(ev(args[0]))
            return not values if fn == 'ISEMPTY' else len(values) or None
        if fn == 'FILTER':
            from dax_tables import filtered_extensions
            from dax_sql import UnsupportedSql
            try:return filtered_extensions(self,args[0],args[1],env,row)
            except UnsupportedSql:pass
            from dax_sql import filter_rows,UnsupportedSql
            try:return filter_rows(self,args[0],args[1],env)
            except UnsupportedSql:pass
            values = self.as_table(ev(args[0]))
            from dax_rowset import evaluate_rows
            try:
                selected=evaluate_rows(self,values,[args[1]],env)
            except UnsupportedSql:selected=None
            if selected is not None:return Table([r for r,test in zip(values,selected) if self.scalar(test[0])],values.columns)
            shadow=getattr(values,'selection_shadow',None)
            if shadow is None:
                return Table([r for r in values if self.scalar(self.run(args[1], env, (*r,)))], values.columns)
            from dax_rowset import prove_row_transition_domain
            frame={**shadow,'row':None,'context_filters':self.filters,'row_measure_safe':False}
            try:frame['row_measure_safe']=prove_row_transition_domain(self,values)==frame['table']
            except UnsupportedSql:pass
            previous=self.selection_shadows
            self.selection_shadows=[*previous,frame]
            try:
                matched=[]
                for candidate in values:
                    frame['row']=(*candidate,)
                    if self.scalar(self.run(args[1],env,frame['row'])):matched.append(candidate)
                return Table(matched,values.columns)
            finally:self.selection_shadows=previous
        if fn == 'KEEPFILTERS':
            return ev(args[0])
        if fn in ('VALUES', 'DISTINCT'):
            return self.project(args[0], True) if args[0][0] == 'col' else self.distinct(self.as_table(ev(args[0])))
        if fn in ('HASONEVALUE', 'SELECTEDVALUE'):
            table,column=self.column(args[0]);key=(table,column,self.where(table))
            cache=self.budget.setdefault('selected_scalar_values',{})
            if key in cache:single,value=cache[key]
            else:
                values=self.project(args[0],True);single=len(values)==1
                value=next(iter(values[0][1].values())) if single else None
                size=len(key[2])+(len(value) if isinstance(value,str) else 32)
                if len(cache)<2000 and self.budget.get('selected_scalar_bytes',0)+size<=8000000:
                    cache[key]=(single,value);self.budget['selected_scalar_bytes']=self.budget.get('selected_scalar_bytes',0)+size
            if fn == 'HASONEVALUE':
                return single
            return value if single else scalar(args[1]) if len(args) > 1 else None
        if fn == 'ISINSCOPE':
            return self.column(args[0]) in self.scope
        if fn in ('CALCULATE', 'CALCULATETABLE'):
            result = self.calculate(args, env, row)
            return self.as_table(result) if fn == 'CALCULATETABLE' else self.scalar(result)
        if fn == 'ALLSELECTED':
            if not args:
                raise ValueError('ALLSELECTED() is only supported as a CALCULATE modifier')
            filters=self.selected_filters(args,row)
            child = self.child(filters)
            cols, tables, clear = self.modifier_targets(args)
            if tables:
                values=child.table(args[0][1])
                result=Table(values,values.columns)
                table=self.canonical_table(args[0][1]);relationships=repr(self.model.get('relationships',[]))
                result.selection_shadow={'table':table,'columns':tuple(values.columns),'filters':list(filters),'relationships':relationships,'stamp':(table,repr(filters),relationships)}
                return result
            return child.project_columns(cols)
        if fn in ('ALL', 'ALLNOBLANKROW', 'REMOVEFILTERS', 'ALLEXCEPT'):
            if fn not in ('ALL','ALLNOBLANKROW') or not args:
                raise ValueError(fn + ' with these arguments is supported only as a CALCULATE modifier')
            cols, tables, clear = self.modifier_targets(args)
            child = self.child(self.remove(cols, tables, clear))
            if tables:
                return self.child([]).table(args[0][1])
            # Physical source rows retain real blanks; no synthetic unknown member is added.
            return child.project_columns(cols)
        from dax_tables import dispatch
        return dispatch(self, fn, args, env, row)

    def aggregate(self, fn, args, env, row):
        if fn in ('MIN','MAX') and len(args)==1 and args[0][0]=='col' and self.transition_row is not None and self.selection_shadows:
            frame=self.selection_shadows[-1];current=self.transition_row
            if frame.get('row_measure_safe') and frame.get('row') is current:
                table,column=self.column(args[0])
                physical=current[2] if len(current)>2 else {(current[0],c):value for c,value in current[1].items()}
                if table==frame['table'] and (table,column) in physical:
                    value=physical[table,column]
                    if value is None or isinstance(value,(int,float,Decimal,str,dt.date,dt.datetime)) and not isinstance(value,bool):
                        return value
        if fn in ('MINX','MAXX') and args[0][0]=='call' and args[0][1]=='ALL' and len(args[0][2])==1 and args[0][2][0][0]=='name' and args[0][2][0][1].casefold() not in env and args[1][0]=='col':
            table=self.canonical_table(args[0][2][0][1]);ct,col=self.column(args[1])
            dtype=type_name(self,table,col)
            if table==ct and dtype not in ('VARCHAR','BOOLEAN','BLOB'):
                child=self.child(self.remove(*self.modifier_targets(args[0][2])));where=child.where(table)
                result=self.con.execute('SELECT '+fn[:-1]+'('+qi(col)+') FROM '+qi(table)+(' WHERE '+where if where else '')).fetchone()[0]
                self.check_budget();return result
        # Let DuckDB aggregate model columns without materializing entire fact tables.
        if len(args)==1 and args[0][0]=='col' and fn in ('SUM','AVERAGE','MIN','MAX','COUNT','COUNTA','MEDIAN'):
            table,col=self.column(args[0]); where=self.where(table)
            dtype=type_name(self,table,col).upper()
            numeric=dtype.split('(')[0] in {'TINYINT','SMALLINT','INTEGER','BIGINT','HUGEINT','UTINYINT','USMALLINT','UINTEGER','UBIGINT','UHUGEINT','DECIMAL','DOUBLE','FLOAT','REAL'}
            if numeric or fn=='COUNTA' or fn=='COUNT' and 'BOOL' not in dtype or fn in ('MIN','MAX') and (dtype=='DATE' or dtype.startswith('TIMESTAMP') and '[' not in dtype):
                key=(fn,table,col,where);cache=self.budget.setdefault('aggregates',{})
                if key not in cache:
                    sqlfn={'AVERAGE':'AVG','COUNTA':'COUNT'}.get(fn,fn)
                    value=self.con.execute('SELECT '+sqlfn+'('+qi(col)+') FROM '+qi(table)+(' WHERE '+where if where else '')).fetchone()[0]
                    self.check_budget()
                    if fn in ('COUNT','COUNTA') and value==0:value=None
                    if len(cache)>=5000:cache.clear()
                    cache[key]=value
                return cache[key]
        ev = lambda n: self.run(n, env, row)
        if fn in ITERATORS or fn.startswith('PERCENTILEX'):
            source=self.as_table(ev(args[0]))
            if fn=='SUMX':
                from dax_vector import sum_rows
                from dax_sql import UnsupportedSql
                try:return sum_rows(self,source,args[1],env)
                except UnsupportedSql:pass
            values = [self.scalar(self.run(args[1], env, (*r,))) for r in source]
            agg = ITERATORS.get(fn, fn.replace('PERCENTILEX', 'PERCENTILE'))
        elif fn in ('MIN', 'MAX') and len(args) == 2:
            values = [self.scalar(ev(a)) for a in args]
            if all(v is None for v in values):
                return None
            values = [0 if v is None else v for v in values]
            agg = fn
        else:
            values = [next(iter(r[1].values())) for r in self.project(args[0])]
            agg = fn
        nonblank = [v for v in values if v is not None]
        numeric = [v for v in nonblank if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)]
        if agg == 'COUNTBLANK':
            return sum(v is None or v == '' for v in values) if values else None
        if agg.startswith('DISTINCTCOUNT'):
            vs = values if agg == 'DISTINCTCOUNT' else nonblank
            return len(set(v.casefold() if isinstance(v, str) else v for v in vs)) if values else None
        if agg == 'COUNT':
            return sum(not isinstance(v, bool) for v in nonblank) or None
        if agg == 'COUNTA':
            return len(nonblank) or None
        if fn.startswith('PERCENTILEX') and any(v is None for v in values):
            raise ValueError('Percentile iterator blank results are not supported yet; explicitly filter blanks')
        if not nonblank and not (agg == 'MEDIAN' and fn == 'MEDIANX' and values):
            return None
        if agg in ('MIN', 'MAX'):
            if any(isinstance(v, bool) for v in nonblank):
                raise ValueError(agg + ' does not support Boolean values')
            vs = numeric if numeric and len(numeric) != len(nonblank) else nonblank
            return (min if agg == 'MIN' else max)(vs, key=lambda x: x.casefold() if isinstance(x, str) else x)
        if agg == 'MEDIAN' and fn == 'MEDIANX':
            numeric = [0 if v is None else v for v in values if v is None or isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)]
        if not numeric:
            return None
        if any(isinstance(v,float) for v in numeric) and any(isinstance(v,Decimal) for v in numeric):numeric=[float(v) for v in numeric]
        if agg == 'SUM':
            return sum(numeric)
        if agg == 'AVERAGE':
            return sum(numeric) / len(numeric)
        if agg == 'PRODUCT':
            return math.prod(numeric)
        if agg == 'MEDIAN':
            return statistics.median(numeric)
        if agg in ('STDEV.S', 'STDEV.P', 'VAR.S', 'VAR.P'):
            if len(numeric) < 2:
                raise ValueError(agg + ' requires at least two nonblank numeric values')
            return {'STDEV.S': statistics.stdev, 'STDEV.P': statistics.pstdev, 'VAR.S': statistics.variance, 'VAR.P': statistics.pvariance}[agg](numeric)
        if agg.startswith('PERCENTILE'):
            k, ordered = float(self.scalar(ev(args[-1]))), sorted(numeric)
            if not 0 <= k <= 1:
                raise ValueError('Percentile k must be between 0 and 1')
            rank = (len(ordered) - 1) * k if agg.endswith('INC') else (len(ordered) + 1) * k - 1
            if not 0 <= rank <= len(ordered) - 1:
                raise ValueError('Exclusive percentile cannot interpolate outside the data range')
            lo, hi = math.floor(rank), math.ceil(rank)
            return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)
        raise ValueError('Unsupported aggregate ' + agg)
