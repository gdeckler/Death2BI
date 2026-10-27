"""PBIXRay adapter retaining relationships involving calculated model tables."""
SEMANTIC_PARSER_VERSION = 6
STORAGE_DECODER_VERSION = 1
STORAGE_DECODER_VERSION = 1


def configure_storage_decoder(model):
    """Decode validated IDFX payload/metadata streams on this PBIXRay instance.

    Some model writers append CP metadata and its uint64 byte length to IDFX
    data instead of storing a companion metadata file. Keep ordinary storage
    untouched, and never infer values when the serialized layout is malformed.
    """
    decoder=getattr(model,'_vertipaq_decoder',None)
    source=getattr(getattr(model,'_metadata',None),'source',None)
    data_model=getattr(model,'_data_model',None)
    if decoder is None or source is None or data_model is None or getattr(decoder,'_death2bi_storage',False):return
    files={item['FileName'] for item in data_model.file_log}
    inline={name for name in files if name.lower().endswith('.idfx') and name+'meta' not in files}
    if not inline:return
    import hashlib
    import io
    import struct
    from pbixray.column_data.idfmeta import IdfmetaParser
    from pbixray.utils import get_data_slice
    original_meta=source.get_segment_meta;original_parse=decoder._parse_idf
    metadata_cache={};payloads={}

    def identity(data):return len(data),hashlib.sha256(data).digest()

    def read_inline(name):
        data=get_data_slice(data_model,name)
        def invalid(reason):raise ValueError('Malformed inline IDFX storage '+name+': '+reason)
        if len(data)<28:invalid('missing metadata length footer')
        length=struct.unpack_from('<Q',data,len(data)-8)[0]
        if length<20 or length>len(data)-8:invalid('metadata length is outside the stream')
        end=len(data)-8-length;metadata=data[end:-8]
        if metadata[:6]!=b'<1:CP\0':invalid('metadata CP signature is missing')
        declared=struct.unpack_from('<Q',metadata,6)[0]
        if declared>len(metadata)//6:invalid('segment count is outside the metadata')
        try:
            parsed=IdfmetaParser.from_io(io.BytesIO(metadata))
        except Exception as error:
            raise ValueError('Malformed inline IDFX storage '+name+': invalid CP metadata') from error
        if not parsed._io.is_eof():invalid('metadata has trailing bytes')
        segments=[];offset=0
        for segment in parsed.column_partition.segments:
            records=segment.records
            if segment.ss.row_count!=records:invalid('segment record counts disagree')
            if offset+8>end:invalid('data has fewer segments than metadata')
            primary=struct.unpack_from('<Q',data,offset)[0];offset+=8
            if primary>(end-offset)//8:invalid('primary segment exceeds the data payload')
            total=0
            for position in range(offset,offset+primary*8,8):
                total+=min(struct.unpack_from('<I',data,position+4)[0],max(0,records-total))
            if total!=records:invalid('data row count disagrees with metadata')
            offset+=primary*8
            if offset+8>end:invalid('subsegment length is missing')
            packed=struct.unpack_from('<Q',data,offset)[0];offset+=8
            if packed>(end-offset)//8:invalid('subsegment exceeds the data payload')
            offset+=packed*8
            bit_records=segment.subsegment.records if segment.has_subsegment else 0
            if bit_records>records:invalid('subsegment record count exceeds its parent')
            segments.append({'min_data_id':segment.ss.min_data_id,'has_nulls':segment.ss.has_nulls,
                             'count_bit_packed':bit_records,'bit_width':segment.bit_width,'records':records})
        if offset!=end:invalid('data and metadata segment counts disagree')
        payloads[identity(data)]=(end,len(segments))
        return segments

    def get_segment_meta(column,idf=None):
        name=idf or column['IDF']
        if name not in inline:return original_meta(column,idf)
        if name not in metadata_cache:metadata_cache[name]=read_inline(name)
        return [dict(segment) for segment in metadata_cache[name]]

    def parse_idf(data):
        known=payloads.get(identity(data))
        if known is None:return original_parse(data)
        end,count=known;parsed=original_parse(data[:end])
        if len(parsed.segments)!=count:raise ValueError('Inline IDFX data and metadata segment counts disagree')
        return parsed

    source.get_segment_meta=get_segment_meta
    decoder._parse_idf=parse_idf
    decoder._death2bi_storage=True


def configure_date_decoder(model):
    """Recover pandas date arithmetic overflow without discarding model dates."""
    decoder=getattr(model,'_vertipaq_decoder',None)
    if decoder is None or getattr(decoder,'_death2bi_dates',False):return
    original=decoder._handle_special_cases
    def handle(values,kind,column_name=None):
        try:return original(values,kind,column_name)
        except (FloatingPointError,OverflowError):
            if kind!='Date':raise
            import numpy as np
            import pandas as pd
            days=pd.to_numeric(values,errors='raise').to_numpy(dtype='float64',na_value=np.nan)
            mask=~np.isnan(days)
            # OLE dates relative to 1899-12-30; real missing values stay NaT.
            if np.any(~np.isfinite(days[mask])) or np.any(days[mask]<-693593) or np.any(days[mask]>=2958466):
                raise ValueError('Decoded date lies outside years 1 through 9999')
            out=np.full(len(days),np.datetime64('NaT','us'),dtype='datetime64[us]')
            out[mask]=np.datetime64('1899-12-30','us')+np.rint(days[mask]*86400000000).astype('timedelta64[us]')
            return pd.Series(out,index=values.index)
    decoder._handle_special_cases=handle
    decoder._death2bi_dates=True

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
    import re
    db=model._metadata.source._db
    if not db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='Function'").empty:
        result['functions']=db.query('SELECT Name,Expression,Description FROM [Function]').to_dict('records')
    columns=db.query('SELECT t.Name AS TableName, COALESCE(c.ExplicitName,c.InferredName) AS Name,c.FormatString, COALESCE(sc.ExplicitName,sc.InferredName) AS SortByColumn FROM [Column] c JOIN [Table] t ON t.ID=c.TableID LEFT JOIN [Column] sc ON sc.ID=c.SortByColumnID').to_dict('records')
    measures=db.query('SELECT t.Name AS TableName,m.Name,m.FormatString FROM Measure m JOIN [Table] t ON t.ID=m.TableID').to_dict('records')
    dynamic=[]
    if 'FormatStringDefinitionID' in db.query('PRAGMA table_info([Measure])')['name'].tolist():
        dynamic=db.query('SELECT t.Name AS TableName,m.Name,f.Expression FROM Measure m JOIN [Table] t ON t.ID=m.TableID JOIN FormatStringDefinition f ON f.ID=m.FormatStringDefinitionID').to_dict('records')
    for table in result['tables']:
        for column in table['columns']:
            match=next((c for c in columns if c['TableName']==table['name'] and c['Name']==column['name']),{})
            column['formatString']=match.get('FormatString') or ''
            if match.get('SortByColumn'):column['sortByColumn']=match['SortByColumn']
    for measure in result['measures']:
        match=next((m for m in measures if m['TableName']==measure['TableName'] and m['Name']==measure['Name']),{})
        if match:measure['FormatString']=match.get('FormatString') or ''
        else:measure.setdefault('FormatString','')
        definition=next((d for d in dynamic if d['TableName']==measure['TableName'] and d['Name']==measure['Name']),{})
        expression=definition.get('Expression')
        if expression:
            measure['FormatStringExpression']=expression
            constant=re.fullmatch(r'\s*"((?:""|[^"])*)"\s*',expression)
            if constant:measure['FormatString']=constant[1].replace('""','"')


def merge_report_measures(result, files):
    """PBIR report extensions contain local DAX measures absent from the ABF model."""
    import json
    measures = {(m.get('TableName'), m['Name']): m for m in result.get('measures', [])}
    for name, data in files.items():
        if not name.lower().endswith('/reportextensions.json'):
            continue
        extension = json.loads(data.decode('utf-8-sig') if isinstance(data, bytes) else data)
        for entity in extension.get('entities', []):
            for measure in entity.get('measures', []):
                if not measure.get('name') or not isinstance(measure.get('expression'), str):
                    continue
                item = {'TableName': entity['name'], 'Name': measure['name'], 'Expression': measure['expression'],
                        'FormatString': measure.get('formatString', ''), 'DataCategory': measure.get('dataCategory', '')}
                dynamic=measure.get('formatStringDefinition',{}).get('expression')
                if dynamic:item['FormatStringExpression']=dynamic
                measures[(entity['name'], measure['name'])] = item
    result['measures'] = list(measures.values())
