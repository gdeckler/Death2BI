"""Bounded CSV downloads using the same read-only DuckDB connection policy as queries."""
import csv
import io
import re
MAX_ROWS=250000
MAX_BYTES=64*1024*1024

def make_csv(con,payload):
    labels=payload.get('labels')
    if 'sql' in payload:
        sql=payload['sql'].strip().rstrip(';')
        if not re.match(r'(?is)^select\s',sql) or ';' in sql:raise ValueError('Enter one SELECT statement.')
        cursor=con.execute('SELECT * FROM ('+sql+') AS exported LIMIT '+str(MAX_ROWS+1))
        columns=[d[0] for d in cursor.description]
        def records():
            while True:
                chunk=cursor.fetchmany(4096)
                if not chunk:break
                yield from chunk
        rows=records()
    else:
        columns=payload.get('columns');rows=payload.get('rows')
        if not isinstance(columns,list) or not isinstance(rows,list):raise ValueError('Export requires query data.')
    if not isinstance(columns,list) or len(columns)>4096:raise ValueError('Invalid export columns.')
    if labels is not None:
        if not isinstance(labels,list) or len(labels)!=len(columns):raise ValueError('Export labels must match query columns.')
        columns=labels
    def cell(x):
        if x is None:return ''
        if isinstance(x,str) and x.startswith(('=','+','-','@','\t','\r')):return "'"+x
        return x
    output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow([cell(str(x)) for x in columns])
    count=0
    for row in rows:
        count+=1
        if count>MAX_ROWS:raise ValueError('CSV export exceeds 250,000 rows. Narrow the filters and export again.')
        if len(row)!=len(columns):raise ValueError('Export row width does not match its columns.')
        writer.writerow([cell(x) for x in row])
        if output.tell()>MAX_BYTES:raise ValueError('CSV export exceeds 64 MB. Narrow the filters and export again.')
    content=output.getvalue().encode('utf-8-sig')
    if len(content)>MAX_BYTES:raise ValueError('CSV export exceeds 64 MB. Narrow the filters and export again.')
    return content
