"""Local, account-based Power BI migration workbench. Run: python server.py."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from email.parser import BytesParser
from email.policy import default
import json, zipfile, io, uuid, shutil, re, traceback, threading, os, socket
import errno
from decimal import Decimal
import sys
import ssl
from tls_settings import TLSSettings
from branding import Branding
from federation_settings import FederationSettings
from rls import RLS, connect as rls_connect
import urllib.request
from http.cookies import SimpleCookie
import hmac
import hashlib
import urllib.parse
from oidc_auth import OIDC, base_url
from accounts import Accounts, AuthError, SESSION_SECONDS
from dax_pool import DaxProcessPool, DaxPoolError
from query_cancellation import QueryCancellation, QueryRequestError
from server_address import ServerAddress,authorities
from public_links import PublicLinks,allowed as public_allowed
from presentation import enrich_report, visible_model
from semantic_model import (extract_relationships, extract_formats, merge_report_measures,
                            configure_storage_decoder, SEMANTIC_PARSER_VERSION, STORAGE_DECODER_VERSION)
from model_recovery import recover_tables, unavailable_table_error
from custom_visuals import read_package, save_package, metadata as visual_metadata, register_embedded, register_referenced
from datetime import datetime, timezone
import duckdb

ROOT = Path(__file__).resolve().parent
def state_dir():
    return Path(os.environ.get('D2BI_STATE_DIR') or ROOT)

def security_dir():
    return state_dir() / 'security'

DATA = state_dir() / 'data'
DATA.mkdir(parents=True,exist_ok=True)
LOCK = threading.Lock()
ACTIVE_QUERIES = {}
MAX_UPLOAD = 1024 * 1024 * 1024
REPORT_PARSER_VERSION = 36
APP_VERSION = '0.24.33'
AUTH = None
ORIGINAL_BASE_URL = os.environ.get('D2PBI_BASE_URL')


def address_settings():return ServerAddress(security_dir(),inherited_origin=ORIGINAL_BASE_URL)


def sharing_base_url():
    settings=address_settings()
    return settings.pending_origin() if settings.path.exists() else base_url()


def allowed_authorities(server):return authorities(server,base_url())|{urllib.parse.urlsplit(sharing_base_url()).netloc}


def account_store():
    global AUTH
    if AUTH is None:
        AUTH = Accounts(security_dir()/'accounts.sqlite3')
    return AUTH
CUSTOM_VISUALS = state_dir() / 'custom_visuals'
CUSTOM_VISUALS.mkdir(exist_ok=True)
CUSTOM_SOURCE_CACHE = {}
BUILTIN_KPI = None


def builtin_kpi():
    global BUILTIN_KPI
    if BUILTIN_KPI is None:
        BUILTIN_KPI=json.loads((ROOT/'dist'/'builtin-kpi.json').read_text(encoding='utf-8'))
    return BUILTIN_KPI


def sync_custom_visuals(dest):
    source = next((p for p in (dest/'source.pbix', dest/'source.zip') if p.exists()), None)
    if source is None:
        return []
    key = (str(source), source.stat().st_mtime_ns)
    if key not in CUSTOM_SOURCE_CACHE:
        with zipfile.ZipFile(source) as archive:
            files = {i.filename: archive.read(i) for i in archive.infolist() if i.filename.lower().endswith('.pbiviz.json') and i.file_size <= 32*1024*1024}
        registered, warnings = register_embedded(CUSTOM_VISUALS, files)
        stored=json.loads((dest/'manifest.json').read_text(encoding='utf-8'))
        guids={v.get('type') for page in stored.get('pages',[]) for v in page.get('visuals',[])}
        registered, bundled_warnings=register_referenced(CUSTOM_VISUALS,guids,registered)
        CUSTOM_SOURCE_CACHE[key] = registered
    return CUSTOM_SOURCE_CACHE[key]

def records(df):
    return json.loads(df.to_json(orient='records', date_format='iso'))

def decode(b):
    # PBIX TMDL scripts can be UTF-16 without a BOM and need not start with JSON.
    if b.startswith((b'\xff\xfe', b'\xfe\xff')):
        return b.decode('utf-16').lstrip('\ufeff')
    sample = b[:256]
    odd = sample[1::2]
    even = sample[::2]
    if len(b) % 2 == 0 and odd and odd.count(0) > len(odd) / 2:
        return b.decode('utf-16-le')
    if len(b) % 2 == 0 and even and even.count(0) > len(even) / 2:
        return b.decode('utf-16-be')
    return b.decode('utf-8-sig')

def obj(value):
    if isinstance(value, str):
        try: return json.loads(value)
        except ValueError: return {}
    return value or {}

def legacy_visual(visual):
    """Convert named legacy projections to the queryState used by the renderer."""
    if visual.get('query',{}).get('queryState') or not visual.get('prototypeQuery'):
        return visual
    prototype=visual['prototypeQuery']; aliases={x['Name']:x['Entity'] for x in prototype.get('From',[]) if 'Name' in x and 'Entity' in x}
    def resolve(value):
        if isinstance(value,list): return [resolve(x) for x in value]
        if not isinstance(value,dict): return value
        if 'SourceRef' in value:
            ref=value['SourceRef']
            if ref.get('Source') in aliases: return {'SourceRef':{'Entity':aliases[ref['Source']]}}
        return {k:resolve(v) for k,v in value.items()}
    selected={s.get('Name'):s for s in prototype.get('Select',[])}; state={}
    for role,projections in visual.get('projections',{}).items():
        converted=[]
        for projection in projections:
            item=selected.get(projection.get('queryRef'))
            if item is None: return visual
            field=resolve({k:v for k,v in item.items() if k not in ('Name','NativeReferenceName')})
            converted.append({**projection,'field':field,'nativeQueryRef':visual.get('columnProperties',{}).get(item.get('Name'),{}).get('displayName') or item.get('NativeReferenceName') or next((v.get('Property') for v in field.values() if isinstance(v,dict) and v.get('Property')),item.get('Name','Value'))})
        state[role]={'projections':converted}
    query={'queryState':state}
    if prototype.get('OrderBy'):
        query['sortDefinition']={'sort':[{'field':resolve(s['Expression']),'direction':'Descending' if s.get('Direction')==2 else 'Ascending'} for s in prototype['OrderBy']]}
    return {**visual,'query':query,'visualContainerObjects':visual.get('visualContainerObjects',visual.get('vcObjects',{}))}


def report_pages(files):
    files = {k.replace('\\', '/'): v for k, v in files.items()}
    pages = []
    # Enhanced PBIR also has report.json, but its pages are separate files.
    # Only a document with a sections array is a legacy report layout.
    legacy = None
    for k, value in files.items():
        if k.lower().endswith(('report/layout', 'report.json')):
            document = json.loads(decode(value))
            if isinstance(document.get('sections'), list):
                legacy = document
                break
    enhanced = any(k.lower().endswith('/page.json') for k in files)
    if legacy is not None and not enhanced:
        for section in legacy['sections']:
            vs=[]
            for v in section.get('visualContainers', []):
                c=obj(v.get('config')); sv=legacy_visual(c.get('singleVisual', {})); filters=obj(v.get('filters'))
                prototype=sv.get('prototypeQuery',{})
                if prototype.get('Where'):
                    filters=(filters if isinstance(filters,list) else [filters] if filters else [])+[{'filter':{k:prototype[k] for k in ('Version','From','Where') if k in prototype}}]
                vs.append({'id':c.get('name',str(len(vs))), 'type':sv.get('visualType','unknown'), 'x':v.get('x',0),'y':v.get('y',0),'width':v.get('width',300),'height':v.get('height',200),'definition':sv, 'filters':filters})
            hidden = obj(section.get('config')).get('visibility') in (1, 'HiddenInViewMode')
            pages.append({'id':section.get('name'), 'name':section.get('displayName','Page'), 'hidden':hidden, 'width':section.get('width',1280),'height':section.get('height',720),'visuals':vs,'filters':obj(section.get('filters')),'visualInteractions':obj(section.get('config')).get('visualInteractions',[])})
    else:
        for k,b in files.items():
            if k.lower().endswith('/page.json'):
                p=json.loads(decode(b)); prefix=k.rsplit('/',1)[0]+'/'
                vs=[]
                for vk,vb in files.items():
                    if vk.startswith(prefix) and vk.lower().endswith('/visual.json'):
                        v=json.loads(decode(vb)); pos=v.get('position',{})
                        vs.append({'id':v.get('name',vk),'type':v.get('visual',{}).get('visualType','unknown'), **{s:pos.get(s,d) for s,d in [('x',0),('y',0),('width',300),('height',200)]},'definition':v.get('visual',{}),'filters':v.get('filterConfig',{})})
                pages.append({'id':p.get('name',k),'name':p.get('displayName','Page'),'hidden':p.get('visibility') == 'HiddenInViewMode','width':p.get('width',1280),'height':p.get('height',720),'visuals':vs,'filters':p.get('filterConfig',{}),'visualInteractions':p.get('visualInteractions',[])})
        metadata = next((json.loads(decode(v)) for k,v in files.items() if k.lower().endswith('/pages/pages.json')), {})
        order = {name: i for i, name in enumerate(metadata.get('pageOrder', []))}
        pages.sort(key=lambda p: order.get(p['id'], len(order)))
        for page in pages:
            page['active'] = page['id'] == metadata.get('activePageName')
    return pages

def qid(s): return '"'+str(s).replace('"','""')+'"'

def repair_report_metadata(dest):
    """Upgrade stored report definitions without touching converted model data."""
    path = dest / 'manifest.json'
    result = json.loads(path.read_text(encoding='utf-8'))
    if 'createdAt' not in result:
        result['createdAt'] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    if result.get('reportParserVersion') == REPORT_PARSER_VERSION:
        return result
    source = next((p for p in (dest/'source.pbix', dest/'source.zip') if p.exists()), None)
    if source is None:
        return result
    with zipfile.ZipFile(source) as z:
        files = {i.filename.replace('\\','/'): z.read(i) for i in z.infolist()
                 if not i.is_dir() and (i.filename.lower().endswith(('.json','.png','.jpg','.jpeg','.gif','.webp','.avif','.bmp','.svg')) or i.filename.lower() == 'report/layout')}
    pages = report_pages(files)
    for k,v in files.items():
        if k.lower().endswith(('report.json','report/layout')):
            report = json.loads(decode(v))
            filters = obj(report.get('filters')) or report.get('filterConfig',{})
            if filters:
                for page in pages: page['reportFilters'] = filters
    result['pages'] = pages
    registered, visual_warnings = register_embedded(CUSTOM_VISUALS, files)
    by_guid = {item['guid']:item for item in result.get('customVisuals',[])}
    by_guid.update({item['guid']:item for item in registered})
    result['customVisuals'] = list(by_guid.values())
    result['warnings'] = [warning for warning in result.get('warnings',[]) if not ('External JavaScript dependencies' in warning and any(item['guid'] in warning for item in registered))]
    result['warnings'].extend(warning for warning in visual_warnings if warning not in result['warnings'])
    merge_report_measures(result,files)
    enrich_report(result,files,dest)
    result['reportParserVersion'] = REPORT_PARSER_VERSION
    temporary = dest / 'manifest.json.tmp'
    temporary.write_text(json.dumps(result,default=str),encoding='utf-8')
    temporary.replace(path)
    return result

def repair_semantic_metadata(dest, result):
    if result.get('unavailableTables') and result.get('storageDecoderVersion') != STORAGE_DECODER_VERSION and not ACTIVE_QUERIES.get(dest.name):
        try:
            result = recover_tables(dest, result)
        except Exception as error:
            # A failed staged repair leaves all installed files intact and can
            # retry after a transient lock or resource failure has cleared.
            result = {**result, 'warnings':[*result.get('warnings',[]),'Stored table recovery could not finish: '+str(error)]}
    if result.get('semanticParserVersion') == SEMANTIC_PARSER_VERSION:
        return result
    source = next((p for p in (dest/'source.pbix',dest/'cache.abf') if p.exists()),None)
    if source is None:
        return result
    try:
        from pbixray import PBIXRay
        model = PBIXRay(str(source))
        relationships=records(extract_relationships(model,[t['name'] for t in result['tables']]))
        for relationship in relationships:
            for side in ('From','To'):
                table=next(t for t in result['tables'] if t['name']==relationship[side+'TableName'])
                if relationship[side+'ColumnName'] not in [c['name'] for c in table['columns']]:
                    raise ValueError('Relationship endpoint missing from converted table: '+relationship[side+'TableName'])
        extract_formats(model,result)
        result['relationships']=relationships
        result['semanticParserVersion']=SEMANTIC_PARSER_VERSION
        temporary=dest/'manifest.json.tmp'
        temporary.write_text(json.dumps(result,default=str),encoding='utf-8');temporary.replace(dest/'manifest.json')
    except Exception as e:
        result['warnings']=[*result['warnings'],'Relationship metadata could not be fully verified: '+str(e)]
    return result

def import_model(filename, content):
    ident=uuid.uuid4().hex; dest=DATA/ident; dest.mkdir()
    warnings=[]; tables=[]; measures=[]; relationships=[]; unavailable_tables=[]
    db=None
    try:
        if filename.lower().endswith(('.html','.htm')):
            from html_reports import inspect_html
            source, package = inspect_html(content)
            pages = [{'id':str(i),'name':p['name'],'hidden':bool(p.get('hidden')),'width':1280,'height':800,'visuals':[]} for i,p in enumerate(package['pages'])] if package else [{'id':'html','name':'HTML report','width':1280,'height':800,'visuals':[]}]
            result={'id':ident,'name':filename,'createdAt':datetime.now(timezone.utc).isoformat(),'reportKind':'snapshot' if package else 'html','tables':[],'measures':[],'relationships':[],'pages':pages,'warnings':['HTML reports run in an isolated viewer. Embedded JavaScript is enabled; external resources, application access, forms and popups are restricted. No native semantic model is imported.'],'customVisuals':[],'reportParserVersion':REPORT_PARSER_VERSION}
            (dest/'source.html').write_text(source,encoding='utf-8')
            (dest/'manifest.json').write_text(json.dumps(result),encoding='utf-8')
            return result
        if not filename.lower().endswith(('.pbix','.zip')):
            raise ValueError('Upload a PBIX or a ZIP of the entire PBIP project. A PBIP pointer alone has no model or pages.')
        source=dest/('source.pbix' if filename.lower().endswith('.pbix') else 'source.zip')
        source.write_bytes(content)
        files={}
        with zipfile.ZipFile(source) as z:
            if sum(i.file_size for i in z.infolist())>2*1024**3: raise ValueError('Expanded archive exceeds the 2 GB safety limit.')
            for i in z.infolist():
                name=i.filename.replace('\\','/')
                if not i.is_dir() and (name.lower().endswith(('.json','.tmdl','.bim','.pbip','.pbir','.csv','.parquet','.abf','.png','.jpg','.jpeg','.gif','.webp','.avif','.bmp','.svg')) or name.lower()=='report/layout'):
                    files[name]=z.read(i)
        pages=report_pages(files)
        # Report-wide filters also affect every visual on every page.
        for k,v in files.items():
            if k.lower().endswith(('report.json','report/layout')):
                report=json.loads(decode(v))
                filters=obj(report.get('filters')) or report.get('filterConfig',{})
                if filters:
                    for page in pages: page['reportFilters']=filters
        db=duckdb.connect(str(dest/'model.duckdb'))
        model=None
        if source.suffix=='.pbix':
            try:
                from pbixray import PBIXRay
                model=PBIXRay(str(source))
            except Exception as e: warnings.append('Embedded model extraction failed: '+str(e)+'. Report definitions are still available. Live/DirectQuery reports need exported source data.')
        else:
            cache=next((v for k,v in files.items() if k.lower().endswith('cache.abf')),None)
            if cache:
                (dest/'cache.abf').write_bytes(cache)
                try:
                    from pbixray import PBIXRay
                    model=PBIXRay(str(dest/'cache.abf'))
                except Exception as e: warnings.append('PBIP cache could not be decoded: '+str(e))
        if model:
            import polars as pl
            from semantic_model import configure_date_decoder
            configure_date_decoder(model)
            configure_storage_decoder(model)
            for index,name in enumerate(model.tables):
                try:
                    frame=pl.from_pandas(model.get_table(str(name)))
                except (ValueError,NotImplementedError) as exc:
                    unavailable_tables.append({'name':str(name),'error':str(exc)})
                    warnings.append('Table data could not be extracted for '+str(name)+': '+str(exc))
                    continue
                path=dest/f'table_{index}.parquet'; frame.write_parquet(path)
                db.execute('CREATE TABLE '+qid(name)+' AS SELECT * FROM read_parquet(?)',[str(path)])
            for attr,target in [('dax_measures',measures),('relationships',relationships)]:
                try: target.extend(records(getattr(model,attr)))
                except Exception as e: warnings.append(f'Could not read {attr}: {e}')
            try:
                relationships=records(extract_relationships(model,[r[0] for r in db.execute('SHOW TABLES').fetchall()]))
            except Exception as e:
                warnings.append('Relationship metadata could not be fully verified: '+str(e))
        else:
            for k,v in files.items():
                if k.lower().endswith(('.csv','.parquet')):
                    name=Path(k).stem
                    if name in [r[0] for r in db.execute('SHOW TABLES').fetchall()]: raise ValueError('Duplicate data table name: '+name)
                    path=dest/f'table_{len(db.execute("SHOW TABLES").fetchall())}.parquet'
                    try:
                        import polars as pl
                        frame=pl.read_csv(io.BytesIO(v)) if k.lower().endswith('.csv') else pl.read_parquet(io.BytesIO(v))
                        frame.write_parquet(path)
                    except ImportError:
                        # DuckDB provides a working path before optional Polars is installed.
                        raw=dest/('input.csv' if k.lower().endswith('.csv') else 'input.parquet')
                        raw.write_bytes(v)
                        reader='read_csv_auto' if raw.suffix=='.csv' else 'read_parquet'
                        output_sql="'"+str(path).replace("'","''")+"'"
                        db.execute('COPY (SELECT * FROM '+reader+'(?)) TO '+output_sql+' (FORMAT PARQUET)',[str(raw)])
                        raw.unlink()
                    db.execute('CREATE TABLE '+qid(name)+' AS SELECT * FROM read_parquet(?)',[str(path)])
            for k,v in files.items():
                if k.endswith('.tmdl'):
                    text=decode(v)
                    for match in re.finditer(r'(?m)^\s*measure\s+(.+?)\s*=\s*(.*(?:\n\t{3,}.*)*)',text): measures.append({'Name':match[1].strip("'"),'Expression':match[2].strip()})
            if not db.execute('SHOW TABLES').fetchall(): warnings.append('No table data found. Include .pbi/cache.abf or CSV/Parquet exports in the PBIP ZIP. TMDL and Power Query source are metadata, not rows.')
        for (name,) in db.execute('SHOW TABLES').fetchall():
            cols=[{'name':r[0],'type':r[1]} for r in db.execute('DESCRIBE '+qid(name)).fetchall()]
            tables.append({'name':name,'rows':db.execute('SELECT count(*) FROM '+qid(name)).fetchone()[0],'columns':cols})
        db.close(); db=None
        warnings.extend(['DAX and M are preserved. Supported DAX runs in Python/DuckDB; Power Query transformations are not executed.','Imported Power BI security roles are not automatically enforced. Administrators can configure Death2BI RLS policies in Administration.','Report rendering is partial. Supported source filters and basic slicers execute in SQL; DAX, custom visual host APIs and formatting have bounded support; bookmarks and remaining Power BI features require further implementation.'])
        definitions={k:decode(v) for k,v in files.items() if k.lower().endswith(('.tmdl','.bim'))}
        custom_visuals, custom_warnings = register_embedded(CUSTOM_VISUALS,files)
        custom_visuals,bundled_warnings=register_referenced(CUSTOM_VISUALS,{v.get('type') for page in pages for v in page.get('visuals',[])},custom_visuals)
        custom_warnings.extend(bundled_warnings)
        warnings.extend(custom_warnings)
        result={'id':ident,'name':filename,'createdAt':datetime.now(timezone.utc).isoformat(),'tables':tables,'unavailableTables':unavailable_tables,'measures':measures,'relationships':relationships,'pages':pages,'warnings':warnings,'modelDefinitions':definitions,'reportParserVersion':REPORT_PARSER_VERSION,'customVisuals':custom_visuals}
        if model: result['storageDecoderVersion']=STORAGE_DECODER_VERSION
        if model and not any('Relationship metadata could not' in w for w in warnings):
            result['semanticParserVersion']=SEMANTIC_PARSER_VERSION
        if model: extract_formats(model,result)
        merge_report_measures(result,files)
        enrich_report(result,files,dest)
        (dest/'manifest.json').write_text(json.dumps(result,default=str),encoding='utf-8')
        return result
    except Exception:
        if db is not None: db.close()
        shutil.rmtree(dest,ignore_errors=True)
        raise

def manifest(ident):
    if not re.fullmatch('[a-f0-9]{32}',ident): raise ValueError('Invalid model ID')
    return json.loads((DATA/ident/'manifest.json').read_text(encoding='utf-8'))

def secured_connection(ident,actor,metadata=None,expected_stamp=None,cancellation=None):
    metadata=metadata or manifest(ident)
    effective=security_effective(ident,actor,metadata)
    if expected_stamp is not None and expected_stamp!=effective['stamp']:raise AuthError('Access policies changed. Refresh and retry the query.',409)
    return rls_connect(DATA/ident/'model.duckdb',metadata,effective,cancellation=cancellation)

def visible_report(metadata,actor):
    effective=security_effective(metadata['id'],actor,metadata)
    result=visible_model(metadata,actor)
    if result is metadata:result=dict(result)
    result['securityStamp']=effective['stamp'];result['rlsEnabled']=effective['config']['enabled'];result['rlsApplied']=effective['applied']
    if effective['applied']:
        import copy
        result=copy.deepcopy(result)
        result.pop('modelDefinitions',None)
        if not metadata.get('reportKind'):
            con=secured_connection(metadata['id'],actor,metadata)
            timer=threading.Timer(20,con.interrupt);timer.start()
            try:
                for table in result['tables']:table['rows']=con.execute('SELECT COUNT(*) FROM '+qid(table['name'])).fetchone()[0]
                for key in result.get('colorDomains',{}):
                    table,column=key.split('\x00',1);result['colorDomains'][key]=[r[0] for r in con.execute('SELECT DISTINCT '+qid(column)+' FROM '+qid(table)+' ORDER BY 1 LIMIT 1001').fetchall()]
                for table,parameter in result.get('fieldParameters',{}).items():parameter['rows']=[list(r) for r in con.execute('SELECT * FROM '+qid(table)+' LIMIT 256').fetchall()]
            finally:timer.cancel();con.close()
        else:result['pages']=[]
    if actor.get('publicLink'):
        result=dict(result);result.pop('modelDefinitions',None)
        for key in ('ownerId','ownerUsername','workspaceId'):result.pop(key,None)
        result.update(canManage=False,publicAccess=True)
    return result


def public_report(actor):
    ident=actor['publicReport'];metadata=repair_semantic_metadata(DATA/ident,repair_report_metadata(DATA/ident))
    metadata['customVisuals']=sync_custom_visuals(DATA/ident)
    account_store().register_report_packages(ident,metadata['customVisuals'])
    return visible_report(metadata,actor)


def public_link_list(actor,ident=None):
    rows=PublicLinks(account_store()).list(actor,ident)
    for row in rows:
        try:row['reportName']=manifest(row['report_id'])['name']
        except FileNotFoundError:row['reportName']='Report unavailable'
    return rows

def security_effective(ident,actor,metadata=None):
    metadata=metadata or manifest(ident)
    effective=RLS(account_store()).effective(ident,actor)
    file=DATA/ident/'model.duckdb';signature=file.stat().st_mtime_ns if file.exists() else None
    effective['stamp']=hashlib.sha256(json.dumps([effective['stamp'],metadata.get('revision',metadata.get('createdAt')),signature,metadata.get('relationships',[]),[(t['name'],t['columns']) for t in metadata.get('tables',[])]],sort_keys=True).encode()).hexdigest()
    return effective

def import_matches(filename,actor):
    if not isinstance(filename,str) or not filename or len(filename)>255:
        raise ValueError('Choose a valid report filename.')
    matches=[]
    for path in DATA.glob('*/manifest.json'):
        ident=path.parent.name
        if not re.fullmatch('[a-f0-9]{32}',ident) or not account_store().can_read_report(ident,actor): continue
        report=json.loads(path.read_text(encoding='utf-8'))
        if report.get('name','').casefold()!=filename.casefold(): continue
        owner=account_store().report_owner(ident)
        matches.append({'id':ident,'name':report['name'],'createdAt':report.get('createdAt'),'updatedAt':report.get('updatedAt'),
                        'ownerUsername':account_store().user(owner)['username'],'canOverwrite':actor['isAdmin'] or owner==actor['id'],
                        'workspaceId':account_store().workspace_for_report(actor,ident)})
    return sorted(matches,key=lambda m:m.get('updatedAt') or m.get('createdAt') or '',reverse=True)


def delete_report(ident, confirmation):
    """Caller holds LOCK, shared with imports and queries."""
    report = manifest(ident)
    if confirmation != report['name']:
        raise ValueError('The report name confirmation does not match.')
    if ACTIVE_QUERIES.get(ident):raise AuthError('This report has active queries. Wait for them to finish before deleting it.',409)
    target = DATA / ident
    expected = DATA.resolve() / ident
    if target.is_symlink() or target.is_junction() or target.resolve() != expected:
        raise ValueError('Unsafe report directory.')
    shutil.rmtree(target)
    return {'deleted': ident}

def oidc_service():
    store=account_store()
    if not hasattr(store,'oidc'):
        store.oidc=OIDC(store,ROOT)
    return store.oidc


def invitation_list(actor, report_id=None):
    rows=account_store().list_invitations(actor,report_id)
    for row in rows:
        path=DATA/row['report_id']/'manifest.json'
        row['reportName']=json.loads(path.read_text(encoding='utf-8'))['name'] if path.exists() else '(deleted report)'
    return rows


def json_scalar(value):
    # Decimal is a calculation value, not a display string. Preserve its
    # numeric JSON type so chart channels, sorting and formatting work.
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else None
    return str(value)


def report_source_download(ident, actor):
    """Resolve an authorized original source; callers hold the report lock."""
    account_store().report_access(ident, actor)
    metadata = manifest(ident)
    if RLS(account_store()).effective(ident, actor)['applied']:
        raise AuthError('Original report download is unavailable under RLS. Use filtered CSV exports or a viewer snapshot.', 403)
    if not actor['isAdmin'] and any(page.get('hidden') for page in metadata.get('pages', [])):
        raise AuthError('The original report contains hidden pages and requires an administrator. Use a viewer snapshot instead.', 403)
    folder = DATA / ident
    if folder.is_symlink() or folder.is_junction() or folder.resolve() != DATA.resolve() / ident:
        raise AuthError('Original report file is unavailable.', 404)
    name = str(metadata.get('name') or 'report').replace('\\', '/').rsplit('/', 1)[-1]
    name = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', '_', name).strip(' .') or 'report'
    suffix = Path(name).suffix.lower()
    preferred = 'source.html' if metadata.get('reportKind') in ('html', 'snapshot') or suffix in ('.html', '.htm') else 'source.pbix' if suffix == '.pbix' else 'source.zip'
    candidates = [preferred, *[item for item in ('source.pbix', 'source.zip', 'source.html') if item != preferred]]
    source = next((folder / item for item in candidates if (folder / item).is_file() and not (folder / item).is_symlink()), None)
    if source is None:
        raise AuthError('The original uploaded file is unavailable for this saved report.', 404)
    actual = source.suffix.lower()
    if suffix != actual and not (actual == '.html' and suffix == '.htm'):
        name = (str(Path(name).with_suffix('')) if suffix in ('.pbix', '.zip', '.html', '.htm') else name) + actual
    content_type = 'application/zip' if actual == '.zip' else 'text/html; charset=utf-8' if actual == '.html' else 'application/octet-stream'
    return source, name, content_type


class Handler(BaseHTTPRequestHandler):
    def log_request(self, code='-', size='-'):
        # OIDC authorization codes and state must not be written to request logs.
        self.log_message('%s %s %s',self.command,self.path.split('?')[0],str(code))
    def redirect(self, url, headers=None):
        return self.send(b'',303,ctype='text/html; charset=utf-8',headers=[('Location',url),*(headers or [])])
    def flow_cookie(self,value='',clear=False):
        return ('Set-Cookie','d2pbi_oidc='+value+'; Path=/; HttpOnly; SameSite=Lax; Max-Age='+('0' if clear else '600')+('; Secure' if base_url().startswith('https://') else ''))
    def send(self,value,status=200,ctype='application/json',headers=None):
        body=json.dumps(value,default=json_scalar).encode() if ctype=='application/json' else value
        try:
            self.send_response(status); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','same-origin'); self.send_header('X-Frame-Options','DENY')
            for name,value in (headers.items() if isinstance(headers,dict) else headers or []): self.send_header(name,value)
            self.end_headers(); self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            # Navigation aborts the old fetch before its cancellation reply.
            # The work is already cleaned up; a disconnected reader is normal.
            self.close_connection=True
    def token(self):
        cookie=SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: return ''
        return cookie['d2pbi_session'].value if 'd2pbi_session' in cookie else ''
    def identity(self,csrf=False):
        public_token=self.headers.get('X-Report-Link')
        if public_token is not None:
            guest=PublicLinks(account_store()).resolve(public_token,visit=self.command=='GET' and self.path=='/api/auth/me')
            if not (DATA/guest['publicReport']/'manifest.json').exists():raise AuthError('Public link is unavailable.',404)
            if not public_allowed(self.command,self.path,guest):raise AuthError('This public link provides read-only access to one report.',403)
            session={'user':guest,'csrf':hashlib.sha256(('public-csrf:'+public_token).encode()).hexdigest()}
        else:session=account_store().session(self.token())
        if csrf and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']):
            raise AuthError('Request verification failed. Refresh the page and try again.',403)
        return session
    def cookie(self,token='',clear=False):
        return {'Set-Cookie':'d2pbi_session='+token+'; Path=/; HttpOnly; SameSite=Strict; Max-Age='+('0' if clear else str(SESSION_SECONDS))+('; Secure' if base_url().startswith('https://') else '')}
    def download_report(self, ident, actor, info=False):
        with LOCK:
            path, filename, content_type = report_source_download(ident, actor)
            if info:
                return self.send({'url':'/api/reports/'+ident+'/download', 'filename':filename, 'bytes':path.stat().st_size})
            source = path.open('rb')
            ACTIVE_QUERIES[ident] = ACTIVE_QUERIES.get(ident, 0) + 1
        try:
            # Stream large PBIX files through the browser's download manager.
            # No full-size Python bytes object or browser Blob is required.
            fallback = filename.encode('ascii', 'replace').decode('ascii').replace('?', '_')
            disposition = 'attachment; filename="'+fallback+'"; filename*=UTF-8\'\''+urllib.parse.quote(filename, safe='')
            self.send_response(200)
            for key, value in [('Content-Type',content_type), ('Content-Length',str(os.fstat(source.fileno()).st_size)), ('Content-Disposition',disposition), ('Cache-Control','no-store'), ('X-Content-Type-Options','nosniff'), ('Referrer-Policy','same-origin'), ('X-Frame-Options','DENY')]:
                self.send_header(key, value)
            self.end_headers()
            shutil.copyfileobj(source, self.wfile, length=1024*1024)
        except OSError:
            self.close_connection = True
        finally:
            source.close()
            with LOCK:
                ACTIVE_QUERIES[ident] -= 1
                if not ACTIVE_QUERIES[ident]: ACTIVE_QUERIES.pop(ident, None)
    def do_GET(self):
        if self.headers.get('Host') not in allowed_authorities(self.server):
            return self.send({'error':'Use the local workbench origin.'},403)
        try:
            public=self.path=='/' or self.path=='/api/health' or self.path=='/api/branding' or self.path=='/api/auth/providers' or self.path.startswith('/auth/callback/') or self.path in ('/vendor/vega.min.js','/vendor/vega-lite.min.js','/vendor/vega-embed.min.js','/vendor/world-geography.js')
            if self.path=='/api/branding': return self.send(Branding(security_dir()).load())
            if self.path=='/api/auth/providers':
                return self.send({'providers':list(oidc_service().configs()),'baseUrl':base_url()})
            if self.path.startswith('/auth/callback/'):
                path=urllib.parse.urlsplit(self.path); name=path.path.split('/')[-1]; params=urllib.parse.parse_qs(path.query)
                cookie=SimpleCookie(); cookie.load(self.headers.get('Cookie',''))
                browser=cookie['d2pbi_oidc'].value if 'd2pbi_oidc' in cookie else ''
                try:
                    token,report_id=oidc_service().callback(name,params.get('state',[''])[0],browser,params.get('code',[''])[0])
                    return self.redirect(base_url()+'/#'+('accepted='+report_id if report_id else 'signed-in'),list(self.cookie(token).items())+[self.flow_cookie(clear=True)])
                except Exception:
                    return self.redirect(base_url()+'/#auth-error=Federated%20sign-in%20failed.%20Start%20sign-in%20again%20or%20ask%20an%20administrator%20to%20check%20the%20provider%20configuration.',[self.flow_cookie(clear=True)])
            if not public:
                session=self.identity(); actor=session['user']
            if self.path=='/api/admin/dax-pool':
                account_store().require_admin(actor)
                return self.send(self.server.dax_pool.status())
            if self.path=='/api/admin/server-address':
                account_store().require_admin(actor);settings=address_settings()
                return self.send({**settings.config(),'configured':settings.path.exists(),'activeOrigin':base_url(),
                    'activePort':self.server.server_port,'activeBindAddress':self.server.server_address[0],'pendingOrigin':settings.pending_origin()})
            if self.path=='/api/admin/public-links':
                with LOCK:return self.send(public_link_list(actor))
            if re.fullmatch(r'/api/reports/[a-f0-9]{32}/public-links',self.path):
                with LOCK:return self.send(public_link_list(actor,self.path.split('/')[3]))
            if self.path=='/api/auth/me': return self.send(session)
            if self.path=='/api/reading-position': return self.send(account_store().reading_position(actor))
            if self.path.startswith('/api/security-context?'):
                ident=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0]
                account_store().report_access(ident,actor);manifest(ident)
                effective=security_effective(ident,actor)
                return self.send({'stamp':effective['stamp'],'applied':effective['applied'],'enabled':effective['config']['enabled']})
            if self.path.startswith('/api/admin/rls?'):
                account_store().require_admin(actor)
                ident=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0];metadata=manifest(ident)
                with account_store().connect() as db:audit=[dict(row) for row in db.execute('SELECT actor_id,changed_at,revision FROM rls_audit WHERE report_id=? ORDER BY changed_at DESC LIMIT 20',(ident,))]
                return self.send({'config':RLS(account_store()).config(ident),'tables':metadata['tables'],'audit':audit})
            if self.path=='/api/admin/federation':
                account_store().require_admin(actor)
                return self.send(FederationSettings(security_dir()).status(base_url()))
            if self.path=='/api/admin/tls':
                account_store().require_admin(actor)
                address=address_settings()
                return self.send({**TLSSettings(security_dir()).status(), 'active':isinstance(self.connection,ssl.SSLSocket), 'activeOrigin':base_url(),
                    'addressManaged':address.path.exists(),'suggestedOrigin':address.pending_origin(https=True)})
            if self.path=='/api/workspaces':
                return self.send(account_store().list_workspaces(actor))
            if self.path=='/api/admin/invitations':
                with LOCK: return self.send(invitation_list(actor))
            if re.fullmatch(r'/api/reports/[a-f0-9]{32}/invitations',self.path):
                with LOCK:
                    ident=self.path.split('/')[3]; account_store().report_access(ident,actor,manage=True); manifest(ident)
                    return self.send(invitation_list(actor,ident))
            if self.path=='/api/admin/groups':
                with LOCK: return self.send(account_store().list_groups(actor))
            if re.fullmatch(r'/api/reports/[a-f0-9]{32}/group-sharing',self.path):
                ident=self.path.split('/')[3]
                with LOCK:
                    account_store().report_access(ident,actor,manage=True); manifest(ident)
                    return self.send(account_store().group_sharing(ident,actor))
            if self.path=='/api/admin/accounts':
                with LOCK:
                    users=account_store().list_users(actor)
                    for user in users: user['reportCount']=sum(account_store().report_owner(p.parent.name)==user['id'] for p in DATA.glob('*/manifest.json'))
                return self.send(users)
            if re.fullmatch(r'/api/models/[a-f0-9]{32}',self.path):
                ident=self.path.split('/')[-1]
                with LOCK:
                    store=account_store();store.report_access(ident,actor)
                    if actor.get('publicLink'):return self.send(public_report(actor))
                    model=repair_semantic_metadata(DATA/ident,repair_report_metadata(DATA/ident));owner=store.user(store.report_owner(ident))
                    model.update(ownerId=owner['id'],ownerUsername=owner['username'],canManage=actor['isAdmin'] or owner['id']==actor['id'],sharedWithMe=owner['id']!=actor['id'] and not actor['isAdmin'],workspaceId=store.workspace_for_report(actor,ident))
                    model['customVisuals']=sync_custom_visuals(DATA/ident);store.grant_packages(model['customVisuals'],owner);store.register_report_packages(ident,model['customVisuals'])
                    return self.send(visible_report(model,actor))
            if self.path in ('/api/models','/api/models?summary=1'):
                with LOCK:
                    if actor.get('publicLink'):return self.send([public_report(actor)])
                    actor=account_store().user(actor['id'])
                    paths=[p for p in DATA.glob('*/manifest.json') if account_store().can_read_report(p.parent.name,actor)]
                    summary=self.path.endswith('?summary=1')
                    if summary:
                        models=[]
                        for path in paths:
                            metadata=manifest(path.parent.name)
                            compact={k:metadata[k] for k in ('id','name','createdAt','revision','reportKind') if k in metadata}
                            compact.update(summaryOnly=True,pages=[{'id':p['id'],'name':p['name'],'hidden':p.get('hidden',False)} for p in visible_model(metadata,actor).get('pages',[])])
                            models.append(compact)
                    else:models = [repair_semantic_metadata(p.parent,repair_report_metadata(p.parent)) for p in paths]
                    for model in models:
                        owner=account_store().user(account_store().report_owner(model['id']))
                        model['ownerId']=owner['id']; model['ownerUsername']=owner['username']
                        model['canManage']=actor['isAdmin'] or owner['id']==actor['id']
                        model['sharedWithMe']=owner['id']!=actor['id'] and not actor['isAdmin']
                        model['workspaceId']=account_store().workspace_for_report(actor,model['id'])
                        if not summary:
                            model['customVisuals'] = sync_custom_visuals(DATA/model['id'])
                            account_store().grant_packages(model['customVisuals'],owner)
                            account_store().register_report_packages(model['id'],model['customVisuals'])
                return self.send([m if summary else visible_report(m,actor) for m in sorted(models,key=lambda m:m.get('createdAt',''))])
            if re.fullmatch(r'/api/html/[a-f0-9]{32}', self.path):
                ident=self.path.split('/')[-1]
                with LOCK:
                    account_store().report_access(ident,actor)
                    report=manifest(ident)
                    if RLS(account_store()).effective(ident,actor)['applied']: raise AuthError('Embedded HTML cannot enforce row security.',403)
                    if not actor['isAdmin'] and any(p.get('hidden') for p in report.get('pages',[])):
                        raise AuthError('This HTML report contains hidden pages and requires an administrator.',403)
                    if report.get('reportKind') not in ('html','snapshot'): raise ValueError('This is not an HTML report.')
                    source=(DATA/ident/'source.html').read_text(encoding='utf-8')
                return self.send({'html':source})
            if re.fullmatch(r'/api/reports/[a-f0-9]{32}/sharing', self.path):
                ident=self.path.split('/')[3]
                with LOCK:
                    account_store().report_access(ident,actor,manage=True); manifest(ident)
                    return self.send(account_store().sharing(ident,actor))
            if self.path=='/api/builtin-visuals':
                return self.send([visual_metadata(builtin_kpi())])
            if self.path=='/api/custom-visuals':
                return self.send([visual_metadata(json.loads(p.read_text(encoding='utf-8'))) for p in CUSTOM_VISUALS.glob('*.json') if account_store().package_access(p.stem,actor)])
            if re.fullmatch(r'/api/custom-visuals/[a-f0-9]{32}', self.path):
                if self.path.split('/')[-1]==builtin_kpi()['id']:
                    return self.send(builtin_kpi())
                if not account_store().package_access(self.path.split('/')[-1],actor): raise AuthError('Visual package not found.',404)
                return self.send(json.loads((CUSTOM_VISUALS/(self.path.split('/')[-1]+'.json')).read_text(encoding='utf-8')))
            if self.path=='/api/dax/functions':
                from dax_runtime import support_catalog
                return self.send({'functions':support_catalog()})
            if self.path=='/api/dax/catalog':
                return self.send(json.loads((ROOT/'dax-function-catalog.json').read_text(encoding='utf-8')))
            if self.path=='/api/custom-visuals/support':
                return self.send((ROOT/'CUSTOM_VISUALS.md').read_bytes(),ctype='text/plain; charset=utf-8')
            if self.path=='/api/dax/support':
                return self.send((ROOT/'DAX_SUPPORT.md').read_bytes(),ctype='text/plain; charset=utf-8')
            if self.path=='/api/health': return self.send({'ok':True,'version':APP_VERSION,'reportParserVersion':REPORT_PARSER_VERSION,'pid':os.getpid()})
            if self.path=='/': return self.send((ROOT/'dist/index.html').read_bytes(),ctype='text/html; charset=utf-8')
            if self.path in ('/vendor/vega.min.js','/vendor/vega-lite.min.js','/vendor/vega-embed.min.js','/vendor/world-geography.js'):
                return self.send((ROOT/'dist'/self.path.lstrip('/')).read_bytes(),ctype='application/javascript; charset=utf-8')
            download = re.fullmatch(r'/api/reports/([a-f0-9]{32})/(download|download-info)', self.path)
            if download:
                return self.download_report(download.group(1), actor, info=download.group(2)=='download-info')
            if self.path.startswith('/api/export/'):
                ident=self.path.split('/')[-1]
                with LOCK:
                    account_store().report_access(ident,actor); metadata=manifest(ident)
                    if RLS(account_store()).effective(ident,actor)['applied']: raise AuthError('Raw model export is unavailable under RLS. Use filtered CSV exports or a viewer snapshot.',403)
                    if not actor['isAdmin'] and any(p.get('hidden') for p in metadata.get('pages',[])):
                        raise AuthError('Source export contains hidden pages and requires an administrator. Use a viewer snapshot instead.',403)
                    buf=io.BytesIO()
                    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
                        for p in (DATA/ident).glob('*'):
                            if p.suffix in ('.parquet','.duckdb','.json','.html'): z.write(p,p.name)
                return self.send(buf.getvalue(),ctype='application/zip')
            self.send({'error':'Not found'},404)
        except AuthError as e: self.send({'error':str(e)},e.status)
        except Exception as e: self.send({'error':str(e)},400)
    def do_POST(self):
        # Reject cross-origin browser requests and DNS rebinding before session/CSRF checks.
        hosts=allowed_authorities(self.server)
        if self.headers.get('Host') not in hosts or self.headers.get('Origin') not in {None,base_url(),*(scheme+'://'+host for scheme in ('http','https') for host in hosts)}:
            return self.send({'error':'Use the local workbench origin.'},403)
        try:
            if getattr(self.server,'stopping',False):
                return self.send({'error':'The server is shutting down.'},503)
            length=int(self.headers.get('Content-Length','0'))
            if length<0: raise ValueError('Invalid request length.')
            if length>MAX_UPLOAD+(1024*1024 if self.path=='/api/import' else 0): raise ValueError('Upload limit is 1 GB.')
            if self.path=='/api/dax' and length>64*1024**2:raise ValueError('DAX request exceeds 64 MB.')
            if self.path in ('/api/dax/cancel','/api/query/cancel') and length>2048:raise ValueError('Invalid query cancellation request.')
            if self.path=='/api/admin/branding' and length>750000: raise ValueError('Branding request exceeds 750 KB.')
            if self.path.startswith('/api/admin/tls') and length>1048576: raise ValueError('Certificate request exceeds 1 MB.')
            if self.path.startswith(('/api/auth/','/api/admin/')) and not self.path.startswith('/api/admin/tls') and self.path!='/api/admin/branding' and length>65536: raise ValueError('Account request exceeds 64 KB.')
            if self.path=='/api/reading-position' and length>2048:raise ValueError('Reading position exceeds 2 KB.')
            if self.path not in ('/api/auth/login','/api/auth/invite-preview','/api/auth/oidc/start'):
                actor=self.identity(csrf=True)['user']
            if self.path.startswith('/api/admin/tls'): account_store().require_admin(actor)
            body=self.rfile.read(length)
            if self.path=='/api/admin/server-address':
                account_store().require_admin(actor)
                with LOCK:result=address_settings().save(json.loads(body))
                return self.send(result)
            if self.path=='/api/public-links/remove':
                with LOCK:return self.send(PublicLinks(account_store()).remove(json.loads(body).get('id'),actor))
            if re.fullmatch(r'/api/reports/[a-f0-9]{32}/public-links',self.path):
                ident=self.path.split('/')[3];payload=json.loads(body)
                if payload.get('confirmPublic') is not True:raise ValueError('Confirm that anyone with the link can access this report and its queryable data.')
                with LOCK:
                    account_store().report_access(ident,actor,manage=True);metadata=manifest(ident)
                    if metadata.get('reportKind') in ('html','snapshot') and any(p.get('hidden') for p in metadata.get('pages',[])):
                        raise ValueError('This embedded report contains hidden pages and cannot be shared publicly.')
                    result=PublicLinks(account_store()).create(ident,actor,payload.get('hours',0))
                result['url']=sharing_base_url()+'/#public='+result.pop('token')
                return self.send(result,201)
            if self.path=='/api/reading-position':
                payload=json.loads(body)
                if not isinstance(payload,dict):raise ValueError('Invalid reading position.')
                ident=payload.get('reportId')
                if ident!='demo':
                    account_store().report_access(ident,actor);metadata=manifest(ident)
                    page=next((p for p in metadata.get('pages',[]) if p['id']==payload.get('pageId')),None)
                    if page is None or page.get('hidden') and not actor['isAdmin']:raise ValueError('Report page is unavailable.')
                elif payload.get('pageId') not in ('overview','regions'):raise ValueError('Example page is unavailable.')
                return self.send(account_store().reading_position(actor,payload))
            if self.path=='/api/admin/branding':
                account_store().require_admin(actor)
                with LOCK: result=Branding(security_dir()).save(json.loads(body))
                return self.send(result)
            if self.path in ('/api/admin/rls','/api/admin/rls/preview'):
                account_store().require_admin(actor);payload=json.loads(body);ident=payload['id'];metadata=manifest(ident)
                if self.path.endswith('/preview'):
                    target=account_store().user(payload['userId']);account_store().report_access(ident,target)
                    effective=RLS(account_store()).effective(ident,target);con=secured_connection(ident,target,metadata)
                    timer=threading.Timer(10,con.interrupt);timer.start()
                    try:
                        counts={t['name']:con.execute('SELECT COUNT(*) FROM '+qid(t['name'])).fetchone()[0] for t in metadata['tables']}
                        sql=payload.get('sql','').strip().rstrip(';')
                        if sql and (not re.match(r'(?is)^select\s',sql) or ';' in sql):raise ValueError('Preview requires one SELECT statement.')
                        preview=None
                        if sql:
                            cursor=con.execute('SELECT * FROM ('+sql+') AS preview LIMIT 21');preview={'columns':[d[0] for d in cursor.description],'rows':cursor.fetchmany(20)}
                        return self.send({'applied':effective['applied'],'roles':[r['name'] for r in effective['roles']],'counts':counts,'preview':preview})
                    finally:timer.cancel();con.close()
                with LOCK:result=RLS(account_store()).save(ident,payload['config'],metadata,actor)
                return self.send(result)
            if self.path=='/api/admin/federation':
                account_store().require_admin(actor)
                with LOCK:
                    result=FederationSettings(security_dir()).save(json.loads(body),base_url())
                    oidc_service().cache.clear()
                return self.send(result)
            if self.path in ('/api/admin/tls','/api/admin/tls/disable'):
                with LOCK:
                    settings=TLSSettings(security_dir())
                    payload=json.loads(body)
                    if address_settings().path.exists():payload['origin']=address_settings().pending_origin(https=True)
                    result=settings.disable() if self.path.endswith('/disable') else settings.save(payload)
                return self.send({**result,'restartRequired':True})
            if self.path=='/api/import/check':
                if length>65536: raise ValueError('Import check exceeds 64 KB.')
                payload=json.loads(body)
                with LOCK: return self.send({'matches':import_matches(payload.get('filename'),actor)})
            if self.path in ('/api/admin/groups','/api/admin/groups/update','/api/admin/groups/delete'):
                payload=json.loads(body)
                with LOCK:
                    if self.path=='/api/admin/groups/delete':
                        result=account_store().delete_group(actor,payload.get('id'),payload.get('confirmName'))
                    else:
                        if self.path.endswith('/update') and not payload.get('id'): raise ValueError('Choose a group.')
                        result=account_store().save_group(actor,payload.get('name'),payload.get('memberIds'),payload.get('id') if self.path.endswith('/update') else None)
                return self.send(result,201 if self.path=='/api/admin/groups' else 200)
            if self.path in ('/api/workspaces','/api/workspaces/rename','/api/workspaces/delete','/api/workspaces/move-report'):
                if length>65536: raise ValueError('Workspace request exceeds 64 KB.')
                payload=json.loads(body)
                store=account_store()
                with LOCK:
                    if self.path=='/api/workspaces':
                        return self.send(store.save_workspace(actor,payload.get('name')),201)
                    if self.path=='/api/workspaces/rename':
                        if not payload.get('id'): raise ValueError('Choose a workspace.')
                        return self.send(store.save_workspace(actor,payload.get('name'),payload['id']))
                    if self.path=='/api/workspaces/delete':
                        return self.send(store.delete_workspace(actor,payload.get('id')))
                    manifest(payload.get('reportId'))
                    result=store.move_report_workspace(actor,payload.get('reportId'),payload.get('workspaceId'))
                    return self.send(result)
            if self.path=='/api/auth/invite-preview':
                payload=json.loads(body); preview=account_store().preview_invitation(payload.get('token')); metadata=manifest(preview['reportId'])
                return self.send({**preview,'reportName':metadata['name']})
            if self.path=='/api/auth/oidc/start':
                if self.headers.get('Host')!=urllib.parse.urlsplit(base_url()).netloc:
                    raise ValueError('Open '+base_url()+' before starting federated sign-in.')
                payload=json.loads(body); url,browser=oidc_service().start(payload.get('provider'),payload.get('invitation'))
                return self.send({'url':url},headers=[self.flow_cookie(browser)])
            if self.path=='/api/invitations/redeem':
                payload=json.loads(body)
                with LOCK:
                    preview=account_store().preview_invitation(payload.get('token')); manifest(preview['reportId'])
                    report_id=account_store().redeem_invitation(payload.get('token'),actor)
                return self.send({'reportId':report_id})
            if self.path=='/api/invitations/remove':
                payload=json.loads(body)
                with LOCK: account_store().remove_invitation(payload.get('id'),actor)
                return self.send({'ok':True})
            if re.fullmatch(r'/api/reports/[a-f0-9]{32}/invitations',self.path):
                ident=self.path.split('/')[3]; payload=json.loads(body)
                with LOCK:
                    account_store().report_access(ident,actor,manage=True); manifest(ident)
                    account_store().register_report_packages(ident,sync_custom_visuals(DATA/ident))
                    result=account_store().new_invitation(ident,actor,payload.get('hours',168))
                result['url']=sharing_base_url()+'/#invite='+result.pop('token')
                return self.send(result,201)
            if self.path=='/api/auth/login':
                payload=json.loads(body)
                with LOCK: session,token=account_store().login(payload.get('username'),payload.get('password'),self.client_address[0])
                return self.send(session,headers=self.cookie(token))
            if self.path=='/api/auth/logout':
                account_store().logout(self.token())
                return self.send({'ok':True},headers=self.cookie(clear=True))
            if self.path=='/api/auth/password':
                payload=json.loads(body)
                with LOCK: account_store().change_password(actor,payload.get('currentPassword'),payload.get('newPassword'))
                return self.send({'ok':True,'signInRequired':True},headers=self.cookie(clear=True))
            if self.path=='/api/admin/accounts':
                payload=json.loads(body)
                with LOCK: result=account_store().create(actor,payload.get('username'),payload.get('password'),payload.get('isAdmin',False))
                return self.send(result,201)
            if self.path=='/api/admin/reset-password':
                payload=json.loads(body)
                with LOCK: account_store().reset_password(actor,payload.get('id'),payload.get('password'))
                return self.send({'ok':True,'signInRequired':payload.get('id')==actor['id']})
            if self.path=='/api/admin/delete-account':
                payload=json.loads(body)
                with LOCK: result=account_store().delete(actor,payload.get('id'),payload.get('confirmUsername'))
                return self.send({'deleted':result['id'],'reportsTransferredTo':'admin'})
            if self.path=='/api/custom-visuals/import':
                msg=BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers.get('Content-Type','')+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
                part=next(p for p in msg.iter_parts() if p.get_filename())
                name=Path(part.get_filename()).name
                if not name.lower().endswith('.pbiviz'):
                    raise ValueError('Choose a .pbiviz visual package')
                with LOCK:
                    result=save_package(CUSTOM_VISUALS,read_package(name,part.get_payload(decode=True)))
                    account_store().grant_packages([result],actor)
                return self.send(result)
            if self.path in ('/api/shutdown','/api/restart'):
                account_store().require_admin(actor)
                payload=json.loads(body)
                if payload.get('confirm') is not True:
                    raise ValueError('Server action confirmation required.')
                with LOCK:
                    restarting=self.path=='/api/restart'
                    if restarting:
                        settings=TLSSettings(security_dir())
                        settings.context()  # Refuse restart if saved TLS files cannot load.
                        origin=address_settings().pending_origin()
                    else: origin=None
                    self.server.stopping=True
                    self.server.restart_requested=restarting
                    self.send({'shuttingDown':True,'restarting':restarting,'origin':origin})
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            if re.fullmatch(r'/api/reports/[a-f0-9]{32}/sharing', self.path):
                ident=self.path.split('/')[3]; payload=json.loads(body)
                with LOCK:
                    account_store().report_access(ident,actor,manage=True); metadata=manifest(ident)
                    packages=sync_custom_visuals(DATA/ident)
                    account_store().register_report_packages(ident,packages)
                    account_store().set_sharing(ident,actor,payload.get('userIds'),payload.get('groupIds'))
                return self.send({'ok':True})
            if self.path=='/api/delete':
                payload=json.loads(body)
                with LOCK:
                    account_store().report_access(payload['id'],actor,manage=True)
                    result=delete_report(payload['id'],payload.get('confirmName')); account_store().forget_report(payload['id'])
                    return self.send(result)
            if self.path=='/api/import':
                msg=BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers.get('Content-Type','')+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
                part=next(p for p in msg.iter_parts() if p.get_filename())
                content=part.get_payload(decode=True)
                def form_value(name,default=None):
                    return next((p.get_content().strip() for p in msg.iter_parts() if p.get_param('name',header='content-disposition')==name and not p.get_filename()),default)
                workspace_id=form_value('workspaceId')
                mode=form_value('mode','auto')
                overwrite_id=form_value('overwriteId')
                if mode not in ('new','overwrite','auto'): raise ValueError('Choose add as new or overwrite.')
                if len(content)>MAX_UPLOAD: raise ValueError('Upload limit is 1 GB.')
                filename=Path(part.get_filename()).name
                with LOCK:
                    actor=account_store().user(actor['id'])
                    if mode=='auto':
                        matches=import_matches(filename,actor)
                        if matches: return self.send({'error':'A report with this saved name already exists. Refresh the application to choose Overwrite existing or Add as new.','code':'IMPORT_CONFLICT','matches':matches},409)
                    if mode=='overwrite':
                        account_store().report_access(overwrite_id,actor,manage=True)
                        previous=manifest(overwrite_id)
                        if previous['name'].casefold()!=filename.casefold(): raise ValueError('The uploaded filename must match the report being overwritten.')
                        if ACTIVE_QUERIES.get(overwrite_id):
                            return self.send({'error':'This report is running queries. Wait for them to finish and try overwriting again.'},409)
                        from report_imports import replace_contents
                        result=replace_contents(DATA,account_store(),actor,overwrite_id,filename,content,import_model,previous)
                        for key in list(CUSTOM_SOURCE_CACHE):
                            if str(DATA/overwrite_id) in key[0]: CUSTOM_SOURCE_CACHE.pop(key,None)
                    else:
                        if workspace_id: account_store().check_workspace(actor,workspace_id)
                        from import_worker import isolated_import
                        result=isolated_import(filename,content,DATA,CUSTOM_VISUALS)
                        account_store().own_report(result['id'],actor); account_store().grant_packages(result.get('customVisuals',[]),actor)
                        account_store().register_report_packages(result['id'],result.get('customVisuals',[]))
                        if workspace_id: account_store().move_report_workspace(actor,result['id'],workspace_id)
                    owner=account_store().user(account_store().report_owner(result['id']))
                    result['workspaceId']=account_store().workspace_for_report(actor,result['id'])
                    result['ownerId']=owner['id']; result['ownerUsername']=owner['username']; result['canManage']=actor['isAdmin'] or owner['id']==actor['id']; result['sharedWithMe']=owner['id']!=actor['id'] and not actor['isAdmin']
                    result['overwritten']=mode=='overwrite'
                return self.send(visible_report(result,actor))
            if self.path=='/api/dax/cancel':
                payload=json.loads(body)
                self.server.dax_pool.cancel(actor['id'],payload.get('requestId'))
                return self.send({'cancelled':True})
            if self.path=='/api/query/cancel':
                payload=json.loads(body)
                self.server.query_cancellation.cancel(actor['id'],payload.get('requestId'))
                return self.send({'cancelled':True})
            if self.path=='/api/dax':
                from dax_budget import limits
                payload=json.loads(body)
                with LOCK:
                    account_store().report_access(payload['id'],actor); metadata=manifest(payload['id'])
                    ACTIVE_QUERIES[payload['id']]=ACTIVE_QUERIES.get(payload['id'],0)+1
                try:
                    context={}
                    def prepare():
                        with LOCK:
                            current=self.identity(csrf=True)['user']
                            account_store().report_access(payload['id'],current)
                            metadata=manifest(payload['id']);effective=security_effective(payload['id'],current,metadata)
                            if payload.get('securityStamp') is not None and payload['securityStamp']!=effective['stamp']:raise AuthError('Access policies changed. Refresh and retry the query.',409)
                            context['stamp']=effective['stamp']
                            # Only semantic metadata crosses IPC; no assets, credentials or account database.
                            semantic={k:metadata[k] for k in ('tables','relationships','measures','functions','reportSettings','unavailableTables') if k in metadata}
                            return {'path':str((DATA/payload['id']/'model.duckdb').resolve()),'model':semantic,
                                    'effective':effective,'payload':payload,'limits':limits()}
                    result=self.server.dax_pool.run(prepare,actor['id'],payload.get('requestId'))
                    with LOCK:
                        current=self.identity(csrf=True)['user'];account_store().report_access(payload['id'],current)
                        if security_effective(payload['id'],current)['stamp']!=context['stamp']:raise AuthError('Access policies changed during calculation. Refresh and retry the query.',409)
                finally:
                    with LOCK:
                        ACTIVE_QUERIES[payload['id']]-=1
                        if not ACTIVE_QUERIES[payload['id']]: ACTIVE_QUERIES.pop(payload['id'],None)
                return self.send(result)
            if self.path=='/api/export-data':
                from data_export import make_csv
                payload=json.loads(body)
                with LOCK:
                    account_store().report_access(payload['id'],actor);manifest(payload['id'])
                    con=secured_connection(payload['id'],actor,expected_stamp=payload.get('securityStamp'))
                    ACTIVE_QUERIES[payload['id']]=ACTIVE_QUERIES.get(payload['id'],0)+1
                timer=threading.Timer(30,con.interrupt);timer.start()
                try: content=make_csv(con,payload)
                finally:
                    timer.cancel();con.close()
                    with LOCK:
                        ACTIVE_QUERIES[payload['id']]-=1
                        if not ACTIVE_QUERIES[payload['id']]:ACTIVE_QUERIES.pop(payload['id'],None)
                self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition','attachment; filename="visual-data.csv"');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content);return
            if self.path=='/api/query':
                payload=json.loads(body)
                sql=payload['sql'].strip().rstrip(';')
                if not re.match(r'(?is)^select\s',sql) or ';' in sql: raise ValueError('Enter one SELECT statement.')
                with self.server.query_cancellation.request(actor['id'],payload.get('requestId')) as cancellation:
                    with LOCK:
                        cancellation.check()
                        account_store().report_access(payload['id'],actor); metadata=manifest(payload['id'])
                        ACTIVE_QUERIES[payload['id']]=ACTIVE_QUERIES.get(payload['id'],0)+1
                    con=None;timer=None
                    try:
                        cancellation.check()
                        # RLS setup can copy data. It must not hold the global
                        # report-management lock or block unrelated requests.
                        con=secured_connection(payload['id'],actor,metadata,expected_stamp=payload.get('securityStamp'),cancellation=cancellation)
                        timer=threading.Timer(10,cancellation.interrupt); timer.start()
                        cancellation.check()
                        if payload.get('purpose')=='scatter':
                            from scatter_sampling import sample
                            cursor=con.execute(sql)
                            columns=[d[0] for d in cursor.description];types=[str(d[1]) for d in cursor.description]
                            rows=cursor.fetchall();cancellation.check()
                            result=sample(rows,columns,types,payload.get('scatter',{}),check=cancellation.check)
                        else:
                            limit=10000 if payload.get('purpose')=='visual' else 1000
                            cursor=con.execute('SELECT * FROM ('+sql+') AS result LIMIT '+str(limit+1))
                            rows=cursor.fetchall()
                            result={'columns':[d[0] for d in cursor.description],'types':[str(d[1]) for d in cursor.description],'rows':rows[:limit],'truncated':len(rows)>limit}
                        cancellation.check()
                    except duckdb.CatalogException as error:
                        cancellation.check()
                        raise unavailable_table_error(error,metadata) from None
                    except Exception:
                        cancellation.check()
                        raise
                    finally:
                        if timer:timer.cancel()
                        if con is not None:cancellation.close_connection(con)
                        with LOCK:
                            ACTIVE_QUERIES[payload['id']]-=1
                            if not ACTIVE_QUERIES[payload['id']]: ACTIVE_QUERIES.pop(payload['id'],None)
                return self.send(result)
            self.send({'error':'Not found'},404)
        except (AuthError,DaxPoolError,QueryRequestError) as e:
            self.send({'error':str(e)},e.status)
        except Exception as e:
            self.send({'error':str(e)},400)

class LocalServer(ThreadingHTTPServer):
    def __init__(self,*args,**kwargs):
        self.dax_pool=DaxProcessPool()
        self.query_cancellation=QueryCancellation()
        if ':' in args[0][0]:self.address_family=socket.AF_INET6
        try:super().__init__(*args,**kwargs)
        except BaseException:self.query_cancellation.close();self.dax_pool.close();raise

    def server_close(self):
        self.query_cancellation.close()
        self.dax_pool.close()
        super().server_close()

    # On Windows SO_REUSEADDR allows two processes to bind the same port,
    # making requests reach stale import code. Require a single owner instead.
    allow_reuse_address = False
    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

def main():
    settings=TLSSettings(security_dir())
    try:
        tls_context=settings.context()
    except (ValueError,OSError,ssl.SSLError):
        print('Cannot start: HTTPS certificate configuration could not be loaded. Restore valid files under security/tls; HTTPS will not silently fall back to HTTP.',flush=True)
        return 1
    address=address_settings();listener=address.config()
    os.environ['D2PBI_BASE_URL']=address.pending_origin()
    try:
        httpd = LocalServer((listener['bindAddress'],listener['port']),Handler)
    except OSError as error:
        if error.errno not in (errno.EADDRINUSE,10048) and getattr(error,'winerror',None) != 10048:
            raise
        try:
            with urllib.request.urlopen(base_url()+'/api/health',timeout=3) as response:
                health=json.load(response)
            running=health.get('ok') is True and 'reportParserVersion' in health and 'version' in health
        except (OSError,ValueError):
            running=False
        if running:
            print(f"Death2PowerBI {health['version']} is already running.",flush=True)
            print('Open '+base_url()+' in your browser. No second server is needed.',flush=True)
            print('To restart after an update, stop the existing server with Ctrl+C in its terminal, then run this command again.',flush=True)
            return 0
        print('Cannot start Death2BI: port '+str(listener['port'])+' is being used by another application.',flush=True)
        print('Stop the application using that port, then run Death2PowerBI again.',flush=True)
        return 1
    if tls_context:
        httpd.socket=tls_context.wrap_socket(httpd.socket,server_side=True)
    print(f'Death2BI {APP_VERSION}: {base_url()}',flush=True)
    account_store()
    import signal
    if threading.current_thread() is threading.main_thread():
        def terminate(signum,frame):
            httpd.stopping=True
            threading.Thread(target=httpd.shutdown,daemon=True).start()
        signal.signal(signal.SIGTERM,terminate)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nDeath2PowerBI stopped.',flush=True)
    finally:
        httpd.server_close()
    return 75 if getattr(httpd,'restart_requested',False) else 0

if __name__=='__main__':
    result=main()
    if result==75:
        # Replace the process after closing the listener, reloading code and TLS settings.
        if ORIGINAL_BASE_URL is None: os.environ.pop('D2PBI_BASE_URL',None)
        else: os.environ['D2PBI_BASE_URL']=ORIGINAL_BASE_URL
        os.execv(sys.executable,[sys.executable,str(ROOT/'server.py')])
    raise SystemExit(result)
