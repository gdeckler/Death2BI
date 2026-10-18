"""Table, relationship, ranking and classic date-column DAX functions."""
import datetime as dt
import itertools
import math
import calendar
from dax_runtime import Table
from dax_functions import text, number, date, integer


def dispatch(e, fn, args, env, row):
    ev = lambda n: e.run(n, env, row)
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
    if fn == 'SUMMARIZE':
        if args[0][0] != 'name':
            raise ValueError('SUMMARIZE currently requires a model table as its first argument')
        table = e.canonical_table(args[0][1])
        source = e.table(table)
        cols, i = [], 1
        while i < len(args) and args[i][0] == 'col':
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
            key = tuple(r[1][c] if t == table else dispatch(e, 'RELATED', [('col', t, c)], env, r) for t, c in cols)
            norm = tuple(v.casefold() if isinstance(v, str) else v for v in key)
            groups.setdefault(norm, key)
        result = []
        for key in groups.values():
            e.check_budget()
            context = dict(zip(cols, key))
            values = {c: v for (t, c), v in context.items()}
            group_row = ('__summary', values, context)
            child = e.child(e.transition(group_row))
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
        current, seen = row, set()
        while current[0] != table:
            e.check_budget()
            if current[0] in seen:
                raise ValueError('Ambiguous RELATED relationship traversal')
            seen.add(current[0])
            candidates = [r for r in e.model.get('relationships', []) if r.get('IsActive') and r.get('Cardinality') in ('M:1', '1:1') and r['FromTableName'] == current[0] and (r['ToTableName'] == table or e.path(r['ToTableName'], table) is not None)]
            if len(candidates) != 1:
                raise ValueError('RELATED requires one unambiguous active many-to-one path')
            r = candidates[0]
            values = [v for v in e.child([]).table(r['ToTableName']) if e.equal(v[1][r['ToColumnName']], current[1][r['FromColumnName']], True)]
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
        if fn == 'TOPN':
            n, values, sortargs = integer(scalar(args[0])), e.as_table(ev(args[1])), args[2:]
        else:
            values = e.as_table(ev(args[0]))
            sortargs = args[3:] if fn == 'CONCATENATEX' else []
        def key(expr, r):
            value = e.scalar(e.run(expr, env, r))
            return (value is not None, value.casefold() if isinstance(value, str) else value)
        if fn == 'RANKX':
            scores = [e.scalar(e.run(args[1], env, r)) for r in values]
            target = scalar(args[2]) if len(args) > 2 and args[2] != ('lit', None) else scalar(args[1])
            ascending = scalar(args[3]) if len(args) > 3 else False
            ascending = ascending in (True, 1, 'ASC')
            ties = scalar(args[4]) if len(args) > 4 else 'SKIP'
            if ties not in ('SKIP', 'DENSE', None):
                raise ValueError('RANKX ties must be SKIP or DENSE')
            scores = [0 if s is None else s for s in scores]
            target = 0 if target is None else target
            better = [s for s in scores if s < target] if ascending else [s for s in scores if s > target]
            return (len(set(better)) if ties == 'DENSE' else len(better)) + 1
        ordered, pairs = list(values), []
        for i in range(0, len(sortargs), 2):
            direction = scalar(sortargs[i + 1]) if i + 1 < len(sortargs) else False
            pairs.append((sortargs[i], direction not in (True, 1, 'ASC')))
        for expr, reverse in reversed(pairs):
            ordered.sort(key=lambda r: key(expr, r), reverse=reverse)
        if fn == 'CONCATENATEX':
            sep = text(scalar(args[2])) if len(args) > 2 else ''
            result = sep.join(text(e.scalar(e.run(args[1], env, r))) for r in ordered)
            if len(result) > 1000000:
                raise RuntimeError('CONCATENATEX output limit exceeded')
            return result
        if n <= 0:
            return Table([], values.columns)
        if n >= len(ordered):
            return Table(ordered, values.columns)
        boundary = tuple(key(expr, ordered[n - 1]) for expr, reverse in pairs)
        end = n
        while end < len(ordered) and tuple(key(expr, ordered[end]) for expr, reverse in pairs) == boundary:
            end += 1
        return Table(ordered[:end], values.columns)
    if fn in ('ROW', 'ADDCOLUMNS', 'SELECTCOLUMNS'):
        rows, pairs = (Table([('__virtual', {})], []), args) if fn == 'ROW' else (e.as_table(ev(args[0])), args[1:])
        if len(pairs) % 2:
            raise ValueError(fn + ' requires name/expression pairs')
        names = [text(scalar(pairs[i])) for i in range(0, len(pairs), 2)]
        if len(set(n.casefold() for n in names)) != len(names):
            raise ValueError('Duplicate virtual column name')
        output = []
        for r in rows:
            values = dict(r[1]) if fn == 'ADDCOLUMNS' else {}
            if any(name in values for name in names):
                raise ValueError('Virtual column conflicts with an existing column')
            for i, name in enumerate(names):
                values[name] = e.scalar(e.run(pairs[i * 2 + 1], env, r))
            # Mixed model/extension lineage is rejected for filter-context changes.
            output.append(('__virtual', values))
        oldnames = [c for t, c in rows.columns] if fn == 'ADDCOLUMNS' else []
        return Table(output, [('__virtual', c) for c in oldnames + names])
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
            values = [v for v in keys(first) if (norm(v) in other) == (fn == 'INTERSECT')]
        if len(values) > 100000:
            raise RuntimeError('Set operation exceeds 100,000 rows')
        same = all(t.columns == first.columns for t in tables)
        cols = first.columns if same else [('__virtual', c) for t, c in first.columns]
        target = cols[0][0] if cols else '__virtual'
        return Table([(target, {c: v for (_, c), v in zip(cols, vals)}) for vals in values], cols)
    raise ValueError('Unsupported DAX function ' + fn)
