"""Immutable model-column metadata shared within one secured DAX request."""
from dax_core import qi


def schema(engine, table):
    # All child evaluators in a request use the same secured connection and
    # model. Never retain these descriptions across users, imports or jobs.
    cache = engine.budget.setdefault('model_schemas', {})
    if table not in cache:
        engine.check_budget()
        cache[table] = tuple(engine.con.execute('SELECT * FROM ' + qi(table) + ' LIMIT 0').description)
        engine.budget.setdefault('columns', {})[table] = [entry[0] for entry in cache[table]]
    return cache[table]


def type_name(engine, table, column):
    for name, dtype, *rest in schema(engine, table):
        if name == column:
            return str(dtype)
    raise ValueError('Unknown DAX column ' + column)
