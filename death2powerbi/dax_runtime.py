"""Extended DAX dispatch, with shared operation/time budgets across contexts."""
import datetime as dt
import math
import statistics
import time
from decimal import Decimal
from dax_core import CoreEvaluator, Parser, qi
from dax_context import ContextMixin
from dax_budget import check_budget, limits
from dax_functions import FUNCTIONS, number, text, date, integer, power


class Table(list):
    def __init__(self, rows=(), columns=()):
        super().__init__(rows)
        self.columns = list(columns)


AGGREGATES = {'SUM', 'AVERAGE', 'MIN', 'MAX', 'COUNT', 'COUNTA', 'COUNTBLANK', 'DISTINCTCOUNT', 'DISTINCTCOUNTNOBLANK', 'PRODUCT', 'MEDIAN', 'STDEV.S', 'STDEV.P', 'VAR.S', 'VAR.P'}
ITERATORS = {'SUMX': 'SUM', 'AVERAGEX': 'AVERAGE', 'MINX': 'MIN', 'MAXX': 'MAX', 'COUNTX': 'COUNT', 'COUNTAX': 'COUNTA', 'PRODUCTX': 'PRODUCT', 'MEDIANX': 'MEDIAN', 'STDEVX.S': 'STDEV.S', 'STDEVX.P': 'STDEV.P', 'VARX.S': 'VAR.S', 'VARX.P': 'VAR.P'}
SPECIAL = {
    'FILTER': (2, 2, 'Table manipulation'), 'COUNTROWS': (1, 1, 'Aggregation'),
    'IF': (2, 3, 'Logical'), 'IF.EAGER': (2, 3, 'Logical'), 'SWITCH': (3, 99, 'Logical'),
    'IFERROR': (2, 2, 'Logical'), 'ISERROR': (1, 1, 'Information'),
    'COALESCE': (1, 99, 'Logical'), 'DIVIDE': (2, 3, 'Math and trig'), 'ERROR': (1, 1, 'Information'),
    'VALUES': (1, 1, 'Filter'), 'DISTINCT': (1, 1, 'Table manipulation'),
    'SELECTEDVALUE': (1, 2, 'Filter'), 'HASONEVALUE': (1, 1, 'Information'),
    'ISFILTERED': (1, 1, 'Information'), 'ISCROSSFILTERED': (1, 1, 'Information'),
    'HASONEFILTER': (1, 1, 'Information'), 'FILTERS': (1, 1, 'Filter'),
    'CALCULATE': (1, 99, 'Filter'), 'CALCULATETABLE': (1, 99, 'Filter'),
    'ALL': (0, 99, 'Filter'), 'REMOVEFILTERS': (0, 99, 'Filter'),
    'ALLEXCEPT': (2, 99, 'Filter'), 'KEEPFILTERS': (1, 1, 'Filter'),
    'RELATED': (1, 1, 'Relationship'), 'RELATEDTABLE': (1, 1, 'Relationship'),
    'LOOKUPVALUE': (3, 99, 'Filter'), 'ISEMPTY': (1, 1, 'Information'),
    'TOPN': (3, 99, 'Table manipulation'), 'RANKX': (2, 5, 'Statistical'),
    'CONCATENATEX': (2, 5, 'Text'), 'ADDCOLUMNS': (3, 99, 'Table manipulation'),
    'SELECTCOLUMNS': (3, 99, 'Table manipulation'), 'ROW': (2, 98, 'Table manipulation'),
    'UNION': (2, 99, 'Table manipulation'), 'INTERSECT': (2, 2, 'Table manipulation'),
    'EXCEPT': (2, 2, 'Table manipulation'), 'CROSSJOIN': (2, 99, 'Table manipulation'),
    'GENERATESERIES': (2, 3, 'Table manipulation'), 'CALENDAR': (2, 2, 'Date and time'),
    'FIRSTDATE': (1, 1, 'Time intelligence'), 'LASTDATE': (1, 1, 'Time intelligence'),
    'DATESBETWEEN': (3, 3, 'Time intelligence'), 'DATESYTD': (1, 1, 'Time intelligence'),
    'DATESQTD': (1, 1, 'Time intelligence'), 'DATESMTD': (1, 1, 'Time intelligence'),
    'TOTALYTD': (2, 3, 'Time intelligence'), 'TOTALQTD': (2, 3, 'Time intelligence'),
    'TOTALMTD': (2, 3, 'Time intelligence'), 'PATH': (2, 2, 'Parent and child'),
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

    def project(self, node, distinct=False):
        table, col = self.column(node)
        values = Table([(table, {col: r[1][col]}) for r in self.table(table)], [(table, col)])
        return self.distinct(values) if distinct else values

    def measure(self, name, table=None, row=None):
        if row:
            child = self.child(self.transition(row))
            child.iterator_depth += 1
            return child.measure(name, table)
        return self.scalar(super().measure(name, table))

    def run(self, n, env=None, row=None):
        self.check_budget()
        env = {} if env is None else env
        kind = n[0]
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
            if not n[1] or any(m['Name'].casefold() == n[2].casefold() and m['TableName'].casefold() == n[1].casefold() for m in self.model['measures']):
                return self.measure(n[2], n[1], row)
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
            a, b = number(a), number(b)
            if op == '/' and not b:
                raise ZeroDivisionError('DAX division by zero; use DIVIDE for an alternate result')
            return {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b, '/': lambda: a / b, '^': lambda: power(a, b)}[op]()
        if kind != 'call':
            return super().run(n, env, row)
        fn, args = n[1:]
        definition = SPECIAL.get(fn) or FUNCTIONS.get(fn)
        if definition is None:
            raise ValueError('Unsupported DAX function: ' + fn + ' (see DAX_SUPPORT.md)')
        if not definition[0] <= len(args) <= definition[1]:
            raise ValueError('Invalid argument count for DAX ' + fn)
        ev = lambda node: self.run(node, env, row)
        scalar = lambda node: self.scalar(ev(node))
        if fn in FUNCTIONS:
            result = FUNCTIONS[fn][3](*[scalar(a) for a in args])
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
            return number(a) / number(b) if b else scalar(args[2]) if len(args) > 2 else None
        if fn in AGGREGATES or fn in ITERATORS or fn.startswith('PERCENTILE'):
            return self.aggregate(fn, args, env, row)
        if fn in ('COUNTROWS', 'ISEMPTY'):
            values = self.as_table(ev(args[0]))
            return not values if fn == 'ISEMPTY' else len(values) or None
        if fn == 'FILTER':
            values = self.as_table(ev(args[0]))
            return Table([r for r in values if self.scalar(self.run(args[1], env, r))], values.columns)
        if fn == 'KEEPFILTERS':
            return ev(args[0])
        if fn in ('VALUES', 'DISTINCT'):
            return self.project(args[0], True) if args[0][0] == 'col' else self.distinct(self.as_table(ev(args[0])))
        if fn in ('HASONEVALUE', 'SELECTEDVALUE'):
            values = self.project(args[0], True)
            if fn == 'HASONEVALUE':
                return len(values) == 1
            return next(iter(values[0][1].values())) if len(values) == 1 else scalar(args[1]) if len(args) > 1 else None
        if fn == 'ISINSCOPE':
            return self.column(args[0]) in self.scope
        if fn in ('CALCULATE', 'CALCULATETABLE'):
            result = self.calculate(args, env, row)
            return self.as_table(result) if fn == 'CALCULATETABLE' else self.scalar(result)
        if fn == 'ALLSELECTED':
            if row or self.iterator_depth:
                raise ValueError('ALLSELECTED inside iterator row contexts requires shadow contexts and is not supported yet')
            if not args:
                raise ValueError('ALLSELECTED() is only supported as a CALCULATE modifier')
            child = self.child(self.selected_filters(args))
            cols, tables, clear = self.modifier_targets(args)
            if tables:
                return child.table(args[0][1])
            return self.distinct(Table([(cols[0][0], {c: r[1][c] for t, c in cols}) for r in child.table(cols[0][0])], cols))
        if fn in ('ALL', 'REMOVEFILTERS', 'ALLEXCEPT'):
            if fn != 'ALL' or not args:
                raise ValueError(fn + ' with these arguments is supported only as a CALCULATE modifier')
            cols, tables, clear = self.modifier_targets(args)
            child = self.child(self.remove(cols, tables, clear))
            if tables:
                return child.table(args[0][1])
            values = Table([(cols[0][0], {c: r[1][c] for t, c in cols}) for r in child.table(cols[0][0])], cols)
            return self.distinct(values)
        from dax_tables import dispatch
        return dispatch(self, fn, args, env, row)

    def aggregate(self, fn, args, env, row):
        # Let DuckDB aggregate model columns without materializing entire fact tables.
        if len(args)==1 and args[0][0]=='col' and fn in ('SUM','AVERAGE','MIN','MAX','COUNT','COUNTA'):
            table,col=self.column(args[0]); where=self.where(table)
            dtype=str(self.con.execute('SELECT '+qi(col)+' FROM '+qi(table)+' LIMIT 0').description[0][1]).upper()
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
            values = [self.scalar(self.run(args[1], env, r)) for r in self.as_table(ev(args[0]))]
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
