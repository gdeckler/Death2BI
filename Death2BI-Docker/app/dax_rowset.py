"""Bounded scalar kernels over secured, materialized DAX iterator rows.

Only proven row-local calculations are compiled. Measures perform an implicit
context transition; a full physical row makes SELECTEDVALUE of its own columns
equivalent to reading that row. Disconnected parameters keep their filter
context and are read once. All other context-sensitive operations fall back.
No generated source code, global data cache, or additional connection is used.
"""
import datetime as dt
import math
from decimal import Decimal

from dax_budget import check_budget
from dax_metadata import schema as model_schema, type_name
from dax_core import qi, cached_ast
from dax_functions import FUNCTIONS, DEFAULT_ARGUMENTS, number, numeric_pair, text, date, power
from dax_sql import UnsupportedSql


_MISSING = object()
_PURE = {
    'ABS', 'ACOS', 'ACOSH', 'ASIN', 'ASINH', 'ATAN', 'ATANH', 'COS', 'COSH',
    'SIN', 'SINH', 'TAN', 'TANH', 'SQRT', 'EXP', 'LN', 'LOG10', 'LOG', 'POWER',
    'DEGREES', 'RADIANS', 'SIGN', 'INT', 'PI', 'MOD', 'QUOTIENT', 'ROUND',
    'ROUNDUP', 'ROUNDDOWN', 'TRUNC', 'MROUND', 'CEILING', 'FLOOR', 'EVEN', 'ODD',
    'TRUE', 'FALSE', 'NOT', 'AND', 'OR', 'ISBLANK', 'ISNUMBER', 'ISTEXT',
    'ISNONTEXT', 'ISLOGICAL', 'ISEVEN', 'ISODD', 'BLANK', 'VALUE', 'LEN',
    'LOWER', 'UPPER', 'TRIM', 'CONCATENATE', 'EXACT',
}


class _Value:
    def __init__(self, run=None, fixed=_MISSING):
        self.fixed = fixed
        self.run = (lambda row, local: fixed) if fixed is not _MISSING else run


def _scalar(value):
    return value is None or isinstance(value, (bool, int, float, Decimal, str, dt.date, dt.datetime))


def _physical(row):
    if len(row) > 2:
        return row[2]
    return {} if row[0].startswith('__') else {(row[0], c): v for c, v in row[1].items()}


class _Compiler:
    def __init__(self, engine, rows):
        self.engine = engine
        self.slots = 0
        self.stack = []
        self.parameters = {}
        first = rows[0]
        lineage = _physical(first)
        tables = {t for t, c in lineage if not t.startswith('__')}
        if len(tables) != 1:
            raise UnsupportedSql('Row kernel requires one complete physical row lineage')
        self.table = next(iter(tables))
        schema = model_schema(engine,self.table)
        self.columns = {c.casefold(): c for c, *rest in schema}
        self.available = {c.casefold(): c for c in first[1]}
        required = {(self.table, c) for c in self.columns.values()}
        for index, row in enumerate(rows):
            if index % 128 == 0:
                engine.check_budget()
            physical = _physical(row)
            if set(physical) != required or {c.casefold() for c in row[1]} != set(self.available):
                raise UnsupportedSql('Partial or inconsistent row lineage')
            # Qualified access uses lineage in the interpreter. Reject a virtual
            # extension which disguises a different physical value by name.
            if any(c not in row[1] or row[1][c] != physical[self.table, c] for c in self.columns.values()):
                raise UnsupportedSql('Renamed or conflicting physical row fields')
        self.expanded = engine.expanded(self.table)
        # Context transition retains filters outside the expanded physical
        # table. A held table variable can predate a later dimension filter.
        # Validate the whole materialized rowset against those surviving
        # predicates once, instead of assuming that every held row is eligible.
        retained = engine.child(engine.remove([], self.expanded))
        where = retained.where(self.table)
        if where:
            integers = [c for c, dtype, *rest in schema if str(dtype).startswith(('TINYINT', 'SMALLINT', 'INTEGER', 'BIGINT', 'HUGEINT', 'UTINYINT', 'USMALLINT', 'UINTEGER', 'UBIGINT'))]
            if not integers:
                raise UnsupportedSql('Surviving related filters need a bounded row identity')
            key = integers[0]
            if engine.con.execute('SELECT 1 FROM ' + qi(self.table) + ' GROUP BY ' + qi(key) + ' HAVING COUNT(*)>1 OR ' + qi(key) + ' IS NULL LIMIT 1').fetchone():
                raise UnsupportedSql('Surviving related filters need a unique row identity')
            eligible = {v[0] for v in engine.con.execute('SELECT ' + qi(key) + ' FROM ' + qi(self.table) + ' WHERE ' + where + ' LIMIT 100001').fetchall()}
            engine.check_budget()
            if len(eligible) > 100000 or any(_physical(row)[self.table, key] not in eligible for row in rows):
                raise UnsupportedSql('Held rows are excluded by a surviving related filter')

        # The ordinary transition validates one-side relationship uniqueness.
        # Keep that behavior even when the numeric score only reads base fields.
        validated = engine.budget.setdefault('rowset_dimensions', set())
        for relation in engine.model.get('relationships', []):
            if not relation.get('IsActive') or relation.get('Cardinality') not in ('M:1', '1:1') or relation['FromTableName'] not in self.expanded:
                continue
            target, key = relation['ToTableName'], relation['ToColumnName']
            identity = (target, key)
            if identity not in validated:
                if engine.con.execute('SELECT 1 FROM ' + qi(target) + ' GROUP BY ' + qi(key) + ' HAVING COUNT(*)>1 LIMIT 1').fetchone():
                    raise UnsupportedSql('Ambiguous expanded row relationship')
                validated.add(identity)
                engine.check_budget()

    @staticmethod
    def lift(fn, values):
        if all(v.fixed is not _MISSING for v in values):
            try:
                return _Value(fixed=fn(*[v.fixed for v in values]))
            except (ArithmeticError, ValueError, TypeError, RuntimeError):
                # Compilation also visits unchosen lazy branches. Keep their
                # scalar errors dormant until that branch is actually used.
                pass
        return _Value(lambda row, local: fn(*[v.run(row, local) for v in values]))

    def column(self, node):
        table, name = node[1], node[2]
        if not table or table.casefold() in (self.table.casefold(), '__virtual'):
            actual = self.available.get(name.casefold())
            if actual is not None:
                return _Value(lambda row, local: row[1][actual])
        if table and table.casefold() == self.table.casefold():
            actual = self.columns.get(name.casefold())
            if actual is not None:
                return _Value(lambda row, local: _physical(row)[self.table, actual])
        return None

    def compile(self, node, scope=None, transition=False):
        self.engine.check_budget()
        scope = {} if scope is None else scope
        kind = node[0]
        if kind == 'lit':
            if not _scalar(node[1]):
                raise UnsupportedSql('Non-scalar row constant')
            return _Value(fixed=node[1])
        if kind == 'name':
            if node[1].casefold() in scope:
                return scope[node[1].casefold()]
            if node[1].upper() in ('TRUE', 'FALSE'):
                return _Value(fixed=node[1].upper() == 'TRUE')
            raise UnsupportedSql('Non-scalar row binding')
        if kind == 'col':
            # A measure body runs after implicit context transition, without
            # the caller's iterator row context. Virtual extensions and bare
            # physical names must therefore not shadow its measure references.
            if not transition:
                direct = self.column(node)
                if direct is not None:
                    return direct
            matches = [m for m in self.engine.model['measures'] if m['Name'].casefold() == node[2].casefold() and (not node[1] or m['TableName'].casefold() == node[1].casefold())]
            if len(matches) == 1:
                measure = matches[0]
                identity = (measure['TableName'], measure['Name'])
                if identity in self.stack or len(self.stack) >= 30:
                    raise UnsupportedSql('Recursive row measure')
                self.stack.append(identity)
                try:
                    return self.compile(cached_ast(self.engine, measure['Expression']), {}, True)
                finally:
                    self.stack.pop()
            if transition and node[1] and node[1].casefold() == self.table.casefold():
                actual = self.columns.get(node[2].casefold())
                if actual is not None:
                    return _Value(lambda row, local: _physical(row)[self.table, actual])
            if not transition and not node[1]:
                for outer in reversed(self.engine.row_stack):
                    actual = next((c for c in outer[1] if c.casefold() == node[2].casefold()), None)
                    if actual is not None and _scalar(outer[1][actual]):
                        return _Value(fixed=outer[1][actual])
            raise UnsupportedSql('Nonlocal row column or ambiguous measure')
        if kind == 'let':
            inner = dict(scope)
            assignments = []
            for name, expr in node[1]:
                value = self.compile(expr, inner, transition)
                if value.fixed is not _MISSING:
                    inner[name.casefold()] = value
                else:
                    slot = self.slots
                    self.slots += 1
                    assignments.append((slot, value))
                    inner[name.casefold()] = _Value(lambda row, local, slot=slot: local[slot])
            body = self.compile(node[2], inner, transition)
            if not assignments:
                return body
            def binding(row, local):
                for slot, value in assignments:
                    local[slot] = value.run(row, local)
                return body.run(row, local)
            return _Value(binding)
        if kind == 'unary':
            if node[1] not in ('+', '-'):
                raise UnsupportedSql('Row unary operation')
            return self.lift(lambda value: number(value) * (1 if node[1] == '+' else -1), [self.compile(node[2], scope, transition)])
        if kind == 'op':
            if node[1] not in ('+', '-', '*', '/', '^', '&', '=', '==', '<>', '<', '>', '<=', '>=', '&&', '||'):
                raise UnsupportedSql('Row binary operation')
            return self.lift(lambda a, b: self.binary(node[1], a, b), [self.compile(x, scope, transition) for x in node[2:]])
        if kind != 'call':
            raise UnsupportedSql('Non-scalar row expression')
        fn, args = node[1], node[2]
        if fn == 'SELECTEDVALUE' and 1 <= len(args) <= 2 and args[0][0] == 'col':
            table, col = self.engine.column(args[0])
            if transition and table == self.table:
                return _Value(lambda row, local: _physical(row)[table, col])
            if transition and any(self.engine.path(table, target) is not None for target in self.expanded):
                raise UnsupportedSql('Related row selection needs expanded context')
            key = (table, col)
            if key not in self.parameters:
                projected = self.engine.project(('col', table, col), True)
                distinct = {}
                for item in projected:
                    value = next(iter(item[1].values()))
                    identity = ('text', value.casefold()) if isinstance(value, str) else ('value', value)
                    if identity not in distinct or isinstance(value, str) and value < distinct[identity]:
                        distinct[identity] = value
                self.parameters[key] = list(distinct.values())
            selected = self.parameters[key]
            if len(selected) == 1:
                return _Value(fixed=selected[0])
            return self.compile(args[1], scope, transition) if len(args) == 2 else _Value(fixed=None)
        if fn == 'IF' and 2 <= len(args) <= 3:
            condition = self.compile(args[0], scope, transition)
            if condition.fixed is not _MISSING:
                return self.compile(args[1] if condition.fixed else args[2], scope, transition) if condition.fixed or len(args) > 2 else _Value(fixed=None)
            yes = self.compile(args[1], scope, transition)
            no = self.compile(args[2], scope, transition) if len(args) > 2 else _Value(fixed=None)
            return _Value(lambda row, local: (yes if condition.run(row, local) else no).run(row, local))
        if fn == 'SWITCH' and len(args) >= 3:
            target = self.compile(args[0], scope, transition)
            pairs = []
            remaining = args[1:]
            for i in range(0, len(remaining) - 1, 2):
                match = self.compile(remaining[i], scope, transition)
                if target.fixed is not _MISSING and match.fixed is not _MISSING:
                    if not self.engine.equal(target.fixed, match.fixed, True):
                        continue
                    chosen = self.compile(remaining[i + 1], scope, transition)
                    if not pairs:
                        return chosen
                    fallback = chosen
                    break
                pairs.append((match, self.compile(remaining[i + 1], scope, transition)))
            else:
                fallback = self.compile(remaining[-1], scope, transition) if len(remaining) % 2 else _Value(fixed=None)
            def switch(row, local):
                value = target.run(row, local)
                for match, result in pairs:
                    if self.engine.equal(value, match.run(row, local), True):
                        return result.run(row, local)
                return fallback.run(row, local)
            return _Value(switch) if pairs else fallback
        if fn == 'COALESCE' and args:
            compiled = [self.compile(x, scope, transition) for x in args]
            def coalesce(row, local):
                for item in compiled:
                    value = item.run(row, local)
                    if value is not None:
                        return value
                return None
            return _Value(coalesce)
        if fn == 'DIVIDE' and 2 <= len(args) <= 3:
            a, b = [self.compile(x, scope, transition) for x in args[:2]]
            alternate = self.compile(args[2], scope, transition) if len(args) > 2 else _Value(fixed=None)
            def divide(row, local):
                left, right = a.run(row, local), b.run(row, local)
                if not right:
                    return alternate.run(row, local)
                left, right = numeric_pair(left, right)
                return left / right
            return _Value(divide)
        if fn in ('MIN', 'MAX') and len(args) == 2:
            def extreme(a, b):
                if a is None and b is None:
                    return None
                values = [0 if x is None else x for x in (a, b)]
                if any(isinstance(x, bool) for x in values):
                    raise ValueError(fn + ' does not support Boolean values')
                numeric = [x for x in values if isinstance(x, (int, float, Decimal))]
                return (min if fn == 'MIN' else max)(numeric if numeric and len(numeric) != len(values) else values, key=lambda x: x.casefold() if isinstance(x, str) else x)
            return self.lift(extreme, [self.compile(x, scope, transition) for x in args])
        if fn in _PURE and fn in FUNCTIONS:
            minimum, maximum, family, function = FUNCTIONS[fn]
            if not minimum <= len(args) <= maximum:
                raise ValueError('Invalid argument count for DAX ' + fn)
            defaults = DEFAULT_ARGUMENTS.get(fn, {})
            compiled = [_Value(fixed=defaults[i]) if a == ('lit', None) and i in defaults else self.compile(a, scope, transition) for i, a in enumerate(args)]
            def invoke(*values):
                result = function(*values)
                if isinstance(result, complex) or isinstance(result, float) and not math.isfinite(result):
                    raise ValueError('Non-finite DAX result')
                return result
            return self.lift(invoke, compiled)
        raise UnsupportedSql('Context-sensitive or unsupported row function: ' + fn)

    def binary(self, op, a, b):
        if op == '&':
            return text(a) + text(b)
        if op in ('=', '==', '<>'):
            return not self.engine.equal(a, b) if op == '<>' else self.engine.equal(a, b, op == '==')
        if op in ('&&', '||'):
            return bool(a) and bool(b) if op == '&&' else bool(a) or bool(b)
        if op in ('<', '>', '<=', '>='):
            a, b = (0 if a is None else a), (0 if b is None else b)
            if isinstance(a, (dt.date, dt.datetime)) and isinstance(b, (dt.date, dt.datetime)):
                a, b = date(a), date(b)
            if isinstance(a, str) and isinstance(b, str):
                a, b = a.casefold(), b.casefold()
            return {'<': lambda: a < b, '>': lambda: a > b, '<=': lambda: a <= b, '>=': lambda: a >= b}[op]()
        if a is None and b is None or op == '*' and (a is None or b is None):
            return None
        if isinstance(a, (dt.date, dt.datetime)) or isinstance(b, (dt.date, dt.datetime)):
            if op == '-' and isinstance(a, (dt.date, dt.datetime)) and isinstance(b, (dt.date, dt.datetime)):
                return (date(a) - date(b)).total_seconds() / 86400
            if op in ('+', '-') and isinstance(a, (dt.date, dt.datetime)):
                return date(a) + dt.timedelta(days=number(b) * (1 if op == '+' else -1))
            if op == '+' and isinstance(b, (dt.date, dt.datetime)):
                return date(b) + dt.timedelta(days=number(a))
            raise ValueError('Unsupported date arithmetic operation')
        a, b = numeric_pair(a, b)
        if op == '/' and not b:
            raise ZeroDivisionError('DAX division by zero; use DIVIDE for an alternate result')
        return {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b, '/': lambda: a / b, '^': lambda: power(a, b)}[op]()


def prove_row_transition_domain(engine, rows):
    """Validate a complete selected iterator domain before scalar shortcuts."""
    engine.check_budget()
    if not rows or len(rows)>100000 or engine.iterator_depth or any(_physical(row) for row in engine.row_stack):
        raise UnsupportedSql('Unproven physical iterator domain')
    return _Compiler(engine,rows).table


def evaluate_rows(engine, rows, expressions, env=None):
    """Return row-major scalar results, or reject an unsafe kernel before work."""
    engine.check_budget()
    if engine.filters is None and any(engine.contexts.values()):raise UnsupportedSql('Legacy row contexts require the interpreter')
    if engine.iterator_depth or any(_physical(row) for row in engine.row_stack):
        raise UnsupportedSql('Physical outer row context')
    # HTML measures often bind unrelated table variables before the numeric
    # expression is visited. Only free scalar bindings read by this kernel
    # matter; a measure's own lexical variables are compiled separately.
    names = set()
    def referenced(node):
        if node[0] == 'name':
            names.add(node[1].casefold())
        elif node[0] == 'let':
            for name, value in node[1]:
                referenced(value)
            referenced(node[2])
        elif node[0] == 'call':
            for value in node[2]:
                referenced(value)
        elif node[0] in ('op', 'unary'):
            for value in node[2:]:
                referenced(value)
    for expression in expressions:
        referenced(expression)
    env = {name: value for name, value in (env or {}).items() if name.casefold() in names}
    if any(not _scalar(value) for value in env.values()):
        raise UnsupportedSql('Non-scalar outer row binding')
    if len(rows) > 100000 or len(expressions) > 50:
        raise UnsupportedSql('Row kernel size limit')
    if not rows:
        return []
    token = (id(rows), repr(expressions), repr(sorted(env.items())), repr(engine.filters), repr(engine.contexts), repr(engine.external_filters), repr(engine.scope), repr(engine.model.get('relationships', [])), repr(engine.row_stack), repr(engine.stack))
    cache = engine.budget.setdefault('rowset_values', {})
    previous = cache.get(token)
    if previous is not None and previous[0] is rows:
        engine.budget['rowset_cache_hits'] = engine.budget.get('rowset_cache_hits', 0) + 1
        return previous[1]
    compiler = _Compiler(engine, rows)
    scope = {name.casefold(): _Value(fixed=value) for name, value in env.items()}
    kernels = [compiler.compile(node, scope) for node in expressions]
    result = []
    byte_count = 0
    for index, row in enumerate(rows):
        if index % 64 == 0:
            check_budget(engine.budget, 64 * max(1, len(kernels)))
        local = [None] * compiler.slots
        values = [kernel.run(row, local) for kernel in kernels]
        result.append(values)
        byte_count += sum(len(v) if isinstance(v, str) else 32 for v in values)
    engine.check_budget()
    retained_cells = len(rows) * (len(rows[0][1]) + len(expressions))
    if len(cache) < 8 and engine.budget.get('rowset_cache_bytes', 0) + byte_count <= 16000000 and engine.budget.get('rowset_cache_cells', 0) + retained_cells <= 2000000:
        cache[token] = (rows, result)
        engine.budget['rowset_cache_bytes'] = engine.budget.get('rowset_cache_bytes', 0) + byte_count
        engine.budget['rowset_cache_cells'] = engine.budget.get('rowset_cache_cells', 0) + retained_cells
    engine.budget['rowset_evaluated_rows'] = engine.budget.get('rowset_evaluated_rows', 0) + len(rows)
    return result
