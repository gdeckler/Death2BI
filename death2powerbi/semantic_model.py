"""PBIXRay adapter retaining relationships involving calculated model tables."""
SEMANTIC_PARSER_VERSION = 2

def extract_relationships(model, table_names):
    # PBIXRay 0.15.5's public relationships endpoint filters SystemFlags = 0.
    # Calculated user tables can have SystemFlags = 2, so use all endpoints
    # present in the actual converted model, excluding internal storage tables.
    source = model._metadata.source
    resolve = source._rel_col
    fc,tc,ft,tt,from_card,to_card = [resolve(c) for c in (
        'FromColumnID','ToColumnID','FromTableID','ToTableID','FromCardinality','ToCardinality')]
    result = source._db.query(f'''
        SELECT r.ID,ft.Name AS FromTableName,
            COALESCE(fc.ExplicitName,fc.InferredName) AS FromColumnName,
            tt.Name AS ToTableName,
            COALESCE(tc.ExplicitName,tc.InferredName) AS ToColumnName,
            r.IsActive,
            CASE WHEN r.{from_card}=2 THEN 'M' ELSE '1' END || ':' ||
            CASE WHEN r.{to_card}=2 THEN 'M' ELSE '1' END AS Cardinality,
            CASE WHEN r.CrossFilteringBehavior=1 THEN 'Single'
                 WHEN r.CrossFilteringBehavior=2 THEN 'Both'
                 ELSE CAST(r.CrossFilteringBehavior AS TEXT) END AS CrossFilteringBehavior,
            r.RelyOnReferentialIntegrity
        FROM Relationship r
        JOIN [Table] ft ON ft.ID=r.{ft}
        JOIN [Table] tt ON tt.ID=r.{tt}
        JOIN [Column] fc ON fc.ID=r.{fc}
        JOIN [Column] tc ON tc.ID=r.{tc}
    ''')
    if result.empty:
        return result.reindex(columns=['ID','FromTableName','FromColumnName','ToTableName','ToColumnName','IsActive','Cardinality','CrossFilteringBehavior','RelyOnReferentialIntegrity'])
    names=set(table_names)
    return result[result.FromTableName.isin(names) & result.ToTableName.isin(names)]

def extract_formats(model,result):
    db=model._metadata.source._db
    columns=db.query('SELECT t.Name AS TableName, COALESCE(c.ExplicitName,c.InferredName) AS Name,c.FormatString FROM [Column] c JOIN [Table] t ON t.ID=c.TableID').to_dict('records')
    measures=db.query('SELECT t.Name AS TableName,m.Name,m.FormatString FROM Measure m JOIN [Table] t ON t.ID=m.TableID').to_dict('records')
    for table in result['tables']:
        for column in table['columns']:
            match=next((c for c in columns if c['TableName']==table['name'] and c['Name']==column['name']),{})
            column['formatString']=match.get('FormatString') or ''
    for measure in result['measures']:
        match=next((m for m in measures if m['TableName']==measure['TableName'] and m['Name']==measure['Name']),{})
        measure['FormatString']=match.get('FormatString') or ''
