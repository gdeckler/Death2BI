"""Local, account-based Power BI migration workbench. Run: python server.py."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from email.parser import BytesParser
from email.policy import default
import json, zipfile, io, uuid, shutil, re, traceback, threading, os, socket
import errno
import urllib.request
from http.cookies import SimpleCookie
import hmac
import urllib.parse
from oidc_auth import OIDC, base_url
from accounts import Accounts, AuthError, SESSION_SECONDS
from semantic_model import extract_relationships, extract_formats, SEMANTIC_PARSER_VERSION
from custom_visuals import read_package, save_package, metadata as visual_metadata, register_embedded
from datetime import datetime, timezone
import duckdb

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
LOCK = threading.Lock()
MAX_UPLOAD = 1024 * 1024 * 1024
REPORT_PARSER_VERSION = 5
APP_VERSION = '0.16.0'
AUTH = None


def account_store():
    global AUTH
    if AUTH is None:
        AUTH = Accounts(ROOT/'security'/'accounts.sqlite3')
    return AUTH
CUSTOM_VISUALS = ROOT / 'custom_visuals'
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
        CUSTOM_SOURCE_CACHE[key] = registered
    return CUSTOM_SOURCE_CACHE[key]

def records(df):
    return json.loads(df.to_json(orient='records', date_format='iso'))

def decode(b):
    return b.decode('utf-16-le' if b[:2] in (b'\xff\xfe', b'{\x00') else 'utf-8-sig').lstrip('\ufeff')

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
                 if not i.is_dir() and (i.filename.lower().endswith('.json') or i.filename.lower() == 'report/layout')}
    pages = report_pages(files)
    for k,v in files.items():
        if k.lower().endswith(('report.json','report/layout')):
            report = json.loads(decode(v))
            filters = obj(report.get('filters')) or report.get('filterConfig',{})
            if filters:
                for page in pages: page['reportFilters'] = filters
    result['pages'] = pages
    result['reportParserVersion'] = REPORT_PARSER_VERSION
    temporary = dest / 'manifest.json.tmp'
    temporary.write_text(json.dumps(result,default=str),encoding='utf-8')
    temporary.replace(path)
    return result

def repair_semantic_metadata(dest, result):
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
    warnings=[]; tables=[]; measures=[]; relationships=[]
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
                if not i.is_dir() and (name.lower().endswith(('.json','.tmdl','.bim','.pbip','.pbir','.csv','.parquet','.abf')) or name.lower()=='report/layout'):
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
            for index,name in enumerate(model.tables):
                frame=pl.from_pandas(model.get_table(str(name)))
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
        db.close()
        warnings.extend(['DAX and M are preserved. Supported DAX runs in Python/DuckDB; Power Query transformations are not executed.','Original security roles are not enforced. Use this local workbench only with data you are authorized to inspect.','Report rendering is partial. Supported source filters and basic slicers execute in SQL; DAX, custom visual host APIs and formatting have bounded support; bookmarks and remaining Power BI features require further implementation.'])
        definitions={k:decode(v) for k,v in files.items() if k.lower().endswith(('.tmdl','.bim'))}
        custom_visuals, custom_warnings = register_embedded(CUSTOM_VISUALS,files)
        warnings.extend(custom_warnings)
        result={'id':ident,'name':filename,'createdAt':datetime.now(timezone.utc).isoformat(),'tables':tables,'measures':measures,'relationships':relationships,'pages':pages,'warnings':warnings,'modelDefinitions':definitions,'reportParserVersion':REPORT_PARSER_VERSION,'customVisuals':custom_visuals}
        if model and not any('Relationship metadata could not' in w for w in warnings):
            result['semanticParserVersion']=SEMANTIC_PARSER_VERSION
        if model: extract_formats(model,result)
        (dest/'manifest.json').write_text(json.dumps(result,default=str),encoding='utf-8')
        return result
    except Exception:
        shutil.rmtree(dest,ignore_errors=True)
        raise

def manifest(ident):
    if not re.fullmatch('[a-f0-9]{32}',ident): raise ValueError('Invalid model ID')
    return json.loads((DATA/ident/'manifest.json').read_text(encoding='utf-8'))

def delete_report(ident, confirmation):
    """Caller holds LOCK, shared with imports and queries."""
    report = manifest(ident)
    if confirmation != report['name']:
        raise ValueError('The report name confirmation does not match.')
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


class Handler(BaseHTTPRequestHandler):
    def log_request(self, code='-', size='-'):
        # OIDC authorization codes and state must not be written to request logs.
        self.log_message('%s %s %s',self.command,self.path.split('?')[0],str(code))
    def redirect(self, url, headers=None):
        return self.send(b'',303,ctype='text/html; charset=utf-8',headers=[('Location',url),*(headers or [])])
    def flow_cookie(self,value='',clear=False):
        return ('Set-Cookie','d2pbi_oidc='+value+'; Path=/; HttpOnly; SameSite=Lax; Max-Age='+('0' if clear else '600')+('; Secure' if base_url().startswith('https://') else ''))
    def send(self,value,status=200,ctype='application/json',headers=None):
        body=json.dumps(value,default=str).encode() if ctype=='application/json' else value
        self.send_response(status); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','same-origin'); self.send_header('X-Frame-Options','DENY')
        for name,value in (headers.items() if isinstance(headers,dict) else headers or []): self.send_header(name,value)
        self.end_headers(); self.wfile.write(body)
    def token(self):
        cookie=SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: return ''
        return cookie['d2pbi_session'].value if 'd2pbi_session' in cookie else ''
    def identity(self,csrf=False):
        session=account_store().session(self.token())
        if csrf and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']):
            raise AuthError('Request verification failed. Refresh the page and try again.',403)
        return session
    def cookie(self,token='',clear=False):
        return {'Set-Cookie':'d2pbi_session='+token+'; Path=/; HttpOnly; SameSite=Strict; Max-Age='+('0' if clear else str(SESSION_SECONDS))+('; Secure' if base_url().startswith('https://') else '')}
    def do_GET(self):
        if self.headers.get('Host') not in ('127.0.0.1:8765','localhost:8765',urllib.parse.urlsplit(base_url()).netloc):
            return self.send({'error':'Use the local workbench origin.'},403)
        try:
            public=self.path=='/' or self.path=='/api/health' or self.path=='/api/auth/providers' or self.path.startswith('/auth/callback/') or self.path in ('/vendor/vega.min.js','/vendor/vega-lite.min.js','/vendor/vega-embed.min.js','/vendor/world-geography.js')
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
            if self.path=='/api/auth/me': return self.send(session)
            if self.path=='/api/admin/invitations':
                with LOCK: return self.send(invitation_list(actor))
            if re.fullmatch(r'/api/reports/[a-f0-9]{32}/invitations',self.path):
                with LOCK:
                    ident=self.path.split('/')[3]; account_store().report_access(ident,actor,manage=True); manifest(ident)
                    return self.send(invitation_list(actor,ident))
            if self.path=='/api/admin/accounts':
                with LOCK:
                    users=account_store().list_users(actor)
                    for user in users: user['reportCount']=sum(account_store().report_owner(p.parent.name)==user['id'] for p in DATA.glob('*/manifest.json'))
                return self.send(users)
            if self.path=='/api/models':
                with LOCK:
                    actor=account_store().user(actor['id'])
                    paths=[p for p in DATA.glob('*/manifest.json') if account_store().can_read_report(p.parent.name,actor)]
                    models = [repair_semantic_metadata(p.parent,repair_report_metadata(p.parent)) for p in paths]
                    for model in models:
                        owner=account_store().user(account_store().report_owner(model['id']))
                        model['ownerId']=owner['id']; model['ownerUsername']=owner['username']
                        model['canManage']=actor['isAdmin'] or owner['id']==actor['id']
                        model['sharedWithMe']=owner['id']!=actor['id'] and not actor['isAdmin']
                        model['customVisuals'] = sync_custom_visuals(DATA/model['id'])
                        account_store().grant_packages(model['customVisuals'],owner)
                        account_store().register_report_packages(model['id'],model['customVisuals'])
                return self.send(sorted(models,key=lambda m:m.get('createdAt','')))
            if re.fullmatch(r'/api/html/[a-f0-9]{32}', self.path):
                ident=self.path.split('/')[-1]
                with LOCK:
                    account_store().report_access(ident,actor)
                    report=manifest(ident)
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
            if self.path.startswith('/api/export/'):
                ident=self.path.split('/')[-1]
                with LOCK:
                    account_store().report_access(ident,actor); manifest(ident)
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
        if self.headers.get('Host') not in ('127.0.0.1:8765','localhost:8765',urllib.parse.urlsplit(base_url()).netloc) or self.headers.get('Origin') not in (None,'http://127.0.0.1:8765','http://localhost:8765',base_url()):
            return self.send({'error':'Use the local workbench origin.'},403)
        try:
            if getattr(self.server,'stopping',False):
                return self.send({'error':'The server is shutting down.'},503)
            length=int(self.headers.get('Content-Length','0'))
            if length<0: raise ValueError('Invalid request length.')
            if length>MAX_UPLOAD+(1024*1024 if self.path=='/api/import' else 0): raise ValueError('Upload limit is 1 GB.')
            if self.path.startswith(('/api/auth/','/api/admin/')) and length>65536: raise ValueError('Account request exceeds 64 KB.')
            if self.path not in ('/api/auth/login','/api/auth/invite-preview','/api/auth/oidc/start'):
                actor=self.identity(csrf=True)['user']
            body=self.rfile.read(length)
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
                result['url']=base_url()+'/#invite='+result.pop('token')
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
            if self.path=='/api/shutdown':
                payload=json.loads(body)
                if payload.get('confirm') is not True:
                    raise ValueError('Shutdown confirmation required.')
                with LOCK:
                    account_store().require_admin(actor)
                    self.server.stopping=True
                    self.send({'shuttingDown':True})
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            if re.fullmatch(r'/api/reports/[a-f0-9]{32}/sharing', self.path):
                ident=self.path.split('/')[3]; payload=json.loads(body)
                with LOCK:
                    account_store().report_access(ident,actor,manage=True); metadata=manifest(ident)
                    packages=sync_custom_visuals(DATA/ident)
                    account_store().register_report_packages(ident,packages)
                    account_store().set_sharing(ident,actor,payload.get('userIds'))
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
                if len(content)>MAX_UPLOAD: raise ValueError('Upload limit is 1 GB.')
                with LOCK:
                    actor=account_store().user(actor['id'])
                    result=import_model(Path(part.get_filename()).name,content)
                    account_store().own_report(result['id'],actor); account_store().grant_packages(result.get('customVisuals',[]),actor)
                    account_store().register_report_packages(result['id'],result.get('customVisuals',[]))
                    result['ownerId']=actor['id']; result['ownerUsername']=actor['username']; result['canManage']=True; result['sharedWithMe']=False
                return self.send(result)
            if self.path=='/api/dax':
                from dax_engine import evaluate_visual
                from dax_budget import limits
                payload=json.loads(body)
                with LOCK:
                    account_store().report_access(payload['id'],actor); metadata=manifest(payload['id'])
                    con=duckdb.connect(str(DATA/payload['id']/'model.duckdb'),read_only=True,config={'enable_external_access':'false','memory_limit':'512MB','threads':'2'})
                timer=threading.Timer(limits()[0]+2,con.interrupt); timer.start()
                try: result=evaluate_visual(con,metadata,payload)
                finally: timer.cancel(); con.close()
                return self.send(result)
            if self.path=='/api/query':
                payload=json.loads(body)
                sql=payload['sql'].strip().rstrip(';')
                if not re.match(r'(?is)^select\s',sql) or ';' in sql: raise ValueError('Enter one SELECT statement.')
                with LOCK:
                    account_store().report_access(payload['id'],actor); manifest(payload['id'])
                    con=duckdb.connect(str(DATA/payload['id']/'model.duckdb'),read_only=True,config={'enable_external_access':'false','memory_limit':'512MB','threads':'2'})
                timer=threading.Timer(10,con.interrupt); timer.start()
                try:
                    cursor=con.execute('SELECT * FROM ('+sql+') AS result LIMIT 1001')
                    rows=cursor.fetchall()
                    result={'columns':[d[0] for d in cursor.description],'types':[str(d[1]) for d in cursor.description],'rows':rows[:1000],'truncated':len(rows)>1000}
                finally: timer.cancel(); con.close()
                return self.send(result)
            self.send({'error':'Not found'},404)
        except AuthError as e:
            self.send({'error':str(e)},e.status)
        except Exception as e:
            self.send({'error':str(e)},400)

class LocalServer(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR allows two processes to bind the same port,
    # making requests reach stale import code. Require a single owner instead.
    allow_reuse_address = False
    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

def main():
    try:
        httpd = LocalServer(('127.0.0.1',8765),Handler)
    except OSError as error:
        if error.errno not in (errno.EADDRINUSE,10048) and getattr(error,'winerror',None) != 10048:
            raise
        try:
            with urllib.request.urlopen('http://127.0.0.1:8765/api/health',timeout=3) as response:
                health=json.load(response)
            running=health.get('ok') is True and 'reportParserVersion' in health and 'version' in health
        except (OSError,ValueError):
            running=False
        if running:
            print(f"Death2PowerBI {health['version']} is already running.",flush=True)
            print('Open http://127.0.0.1:8765 in your browser. No second server is needed.',flush=True)
            print('To restart after an update, stop the existing server with Ctrl+C in its terminal, then run this command again.',flush=True)
            return 0
        print('Cannot start Death2PowerBI: port 8765 is being used by another application.',flush=True)
        print('Stop the application using that port, then run Death2PowerBI again.',flush=True)
        return 1
    print(f'Death2PowerBI {APP_VERSION}: http://127.0.0.1:8765',flush=True)
    account_store()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nDeath2PowerBI stopped.',flush=True)
    finally:
        httpd.server_close()
    return 0

if __name__=='__main__':
    raise SystemExit(main())
