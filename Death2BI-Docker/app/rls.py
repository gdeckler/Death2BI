"""Structured, server-owned row policies and physically isolated query databases."""
import copy
import hashlib
import json
import math
import threading
import time
import uuid
import duckdb
from dax_context import ContextMixin
from dax_core import qi


def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS report_rls(report_id TEXT PRIMARY KEY,config TEXT NOT NULL,revision TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS rls_audit(report_id TEXT,actor_id TEXT,changed_at REAL,revision TEXT);''')


class RLS:
    def __init__(self,store):self.store=store

    def config(self,ident):
        with self.store.connect() as db:row=db.execute('SELECT config,revision FROM report_rls WHERE report_id=?',(ident,)).fetchone()
        return {**json.loads(row['config']),'revision':row['revision']} if row else {'enabled':False,'roles':[],'bidirectional':False,'revision':'0'}

    def effective(self,ident,actor):
        actor=self.store.user(actor['id']);config=self.config(ident)
        if actor.get('publicLink'):
            from accounts import AuthError
            if ident!=actor['publicReport'] or config['enabled']:raise AuthError('Public access is unavailable for this report.',403)
            return {'config':config,'actor':actor,'roles':[],'applied':False,'stamp':hashlib.sha256((ident+actor['publicLink']+config['revision']).encode()).hexdigest()}
        with self.store.connect() as db:groups={r['group_id'] for r in db.execute('SELECT group_id FROM group_members WHERE user_id=?',(actor['id'],))}
        roles=[r for r in config['roles'] if actor['id'] in r['userIds'] or groups.intersection(r['groupIds'])]
        applied=config['enabled'] and not actor['isAdmin']
        identity=actor.get('identity') or {}
        stamp=hashlib.sha256(json.dumps([ident,config['revision'],actor['id'],actor['username'],identity,actor['isAdmin'],[r['id'] for r in roles]],sort_keys=True).encode()).hexdigest()
        return {'config':config,'actor':actor,'roles':roles,'applied':applied,'stamp':stamp}

    def save(self,ident,payload,model,actor):
        self.store.require_admin(actor)
        if not isinstance(payload.get('enabled'),bool) or not isinstance(payload.get('bidirectional',False),bool):raise ValueError('Choose valid RLS enabled/direction settings.')
        if model.get('reportKind'):raise ValueError('RLS requires a native semantic model; HTML and snapshots contain already embedded data.')
        if payload['enabled'] and any(r.get('IsActive') and r.get('Cardinality') not in ('M:1','1:1') for r in model.get('relationships',[])):
            raise ValueError('RLS currently supports active many-to-one and one-to-one relationships only.')
        roles=payload.get('roles',[])
        if not isinstance(roles,list) or len(roles)>32:raise ValueError('At most 32 RLS roles are supported.')
        tables={t['name']:{c['name'] for c in t['columns']} for t in model['tables']}
        with self.store.connect() as db:
            users={r['id'] for r in db.execute('SELECT id FROM users')};groups={r['id'] for r in db.execute('SELECT id FROM local_groups')}
        result=[];seen=set()
        for role in roles:
            name=role.get('name','');rules=role.get('rules',[]);unrestricted=role.get('unrestricted',False)
            if not isinstance(name,str) or not 1<=len(name.strip())<=80 or name.casefold() in seen:raise ValueError('Role names must be unique and contain 1–80 characters.')
            seen.add(name.casefold())
            if not isinstance(unrestricted,bool) or not isinstance(rules,list) or len(rules)>64 or (not rules and not unrestricted) or (rules and unrestricted):raise ValueError('Add role rules, or explicitly mark a role unrestricted.')
            for key,known in [('userIds',users),('groupIds',groups)]:
                if not isinstance(role.get(key,[]),list) or len(role.get(key,[]))>10000 or any(not isinstance(i,str) or i not in known for i in role.get(key,[])):raise ValueError('Unknown account/group assignment.')
            clean=[]
            for rule in rules:
                table,column,op=rule.get('table'),rule.get('column'),rule.get('operator')
                if table not in tables or column not in tables[table]:raise ValueError('RLS rule references an unknown model table or column.')
                if op not in ('eq','neq','in','notIn','gt','gte','lt','lte','isNull','notNull'):raise ValueError('Unsupported RLS operator.')
                values=rule.get('values',[])
                if not isinstance(values,list) or len(values)>200 or (op not in ('isNull','notNull','in','notIn') and len(values)!=1):raise ValueError('Choose the required rule values.')
                if op=='notIn' and not values:raise ValueError('Not-in rules require at least one value; use an explicit unrestricted role to grant all rows.')
                for value in values:
                    if isinstance(value,dict):
                        if set(value)!= {'identity'} or value['identity'] not in ('id','username','email'):raise ValueError('Use id, username or email identity values.')
                    elif value is not None and not isinstance(value,(str,int,float,bool)):raise ValueError('RLS values must be scalar values or identity references.')
                    elif isinstance(value,str) and len(value)>2000 or isinstance(value,float) and not math.isfinite(value):raise ValueError('Invalid RLS value.')
                clean.append({'table':table,'column':column,'operator':op,'values':values})
            result.append({'id':uuid.uuid4().hex,'name':name.strip(),'rules':clean,'unrestricted':unrestricted,'userIds':list(set(role.get('userIds',[]))),'groupIds':list(set(role.get('groupIds',[])))})
        config={'enabled':payload['enabled'],'bidirectional':payload.get('bidirectional',False),'roles':result};revision=uuid.uuid4().hex
        with self.store.connect() as db:
            db.execute('INSERT OR REPLACE INTO report_rls VALUES (?,?,?)',(ident,json.dumps(config),revision))
            db.execute('INSERT INTO rls_audit VALUES (?,?,?,?)',(ident,actor['id'],time.time(),revision))
        return {**config,'revision':revision}


def literal(value):
    if value is None:return 'NULL'
    if isinstance(value,bool):return 'TRUE' if value else 'FALSE'
    if isinstance(value,(int,float)):return str(value)
    return "'"+str(value).replace("'","''")+"'"


def predicate(rule,actor):
    column=qi(rule['table'])+'.'+qi(rule['column']);op=rule['operator'];values=[]
    for value in rule['values']:
        if isinstance(value,dict):
            key=value['identity'];value=(actor.get('identity') or {}).get('email') if key=='email' else actor.get(key)
            if value is None or value=='':return 'FALSE'
        values.append(value)
    compare=lambda value:column+' IS NULL' if value is None else column+' = '+literal(value)
    if op=='isNull':return column+' IS NULL'
    if op=='notNull':return column+' IS NOT NULL'
    if op in ('in','notIn','eq','neq'):
        term='('+' OR '.join(compare(v) for v in values)+')' if values else 'FALSE'
        return 'NOT '+term if op in ('notIn','neq') else term
    return column+{'gt':' > ','gte':' >= ','lt':' < ','lte':' <= '}[op]+literal(values[0])


def connect(path,model,effective,*,threads=2,cancellation=None):
    def close(connection):
        if cancellation:cancellation.close_connection(connection)
        else:connection.close()
    def check():
        if cancellation:cancellation.check()
    source=duckdb.connect(str(path),read_only=True,config={'enable_external_access':'false','memory_limit':'512MB','threads':str(threads)})
    try:
        if cancellation:cancellation.attach(source)
    except Exception:
        close(source)
        raise
    if not effective['applied']:return source
    from accounts import AuthError
    secured=None
    try:
        if model.get('reportKind'):raise ValueError('RLS cannot filter embedded HTML data.')
        roles=effective['roles'];plans=[];schema={t['name']:{c['name'] for c in t['columns']} for t in model['tables']}
        for role in roles:
            check()
            filters=[]
            for rule in role['rules']:
                if rule['table'] not in schema or rule['column'] not in schema[rule['table']]:raise ValueError('RLS policy no longer matches the model. Ask an administrator to update it.')
                filters.append({'table':rule['table'],'sql':predicate(rule,effective['actor'])})
            engine=SecurityContext();engine.model=copy.deepcopy(model);engine.filters=filters
            for relationship in engine.model.get('relationships',[]):
                relationship['CrossFilteringBehavior']='Both' if effective['config'].get('bidirectional') or relationship.get('Cardinality')=='1:1' else 'Single'
            plans.append(engine)
        secured=duckdb.connect(':memory:',config={'enable_external_access':'false','autoload_known_extensions':'false','autoinstall_known_extensions':'false','memory_limit':'512MB','threads':str(threads)})
        if cancellation:cancellation.attach(secured)
        def interrupt():
            if cancellation:cancellation.interrupt()
            else:source.interrupt();secured.interrupt()
        timer=threading.Timer(30,interrupt);timer.start()
        try:
            for table in schema:
                check()
                terms=[engine.where(table) or 'TRUE' for engine in plans]
                where=' OR '.join('('+term+')' for term in terms) if terms else 'FALSE'
                arrow=source.execute('SELECT * FROM '+qi(table)+' WHERE '+where).fetch_arrow_table()
                check()
                alias='_rls_'+uuid.uuid4().hex
                secured.register(alias,arrow)
                check()
                secured.execute('CREATE TABLE '+qi(table)+' AS SELECT * FROM '+qi(alias))
                secured.unregister(alias)
        finally:timer.cancel()
        return secured
    except Exception as error:
        if secured:close(secured)
        check()
        raise AuthError('RLS could not be applied; access denied. Ask an administrator to review the policy and model relationships.',403) from None
    finally:close(source)


class SecurityContext(ContextMixin):
    def path(self,start,end):
        edges={};paths=[];steps=0
        for r in self.model.get('relationships',[]):
            if not r.get('IsActive'):continue
            if r.get('Cardinality') not in ('M:1','1:1'):raise ValueError('Unsupported active security relationship.')
            edge=(r['FromTableName'],r['FromColumnName'],r['ToTableName'],r['ToColumnName']);edges.setdefault(edge[0],[]).append(edge)
            if r.get('CrossFilteringBehavior')=='Both':edges.setdefault(edge[2],[]).append((edge[2],edge[3],edge[0],edge[1]))
        def visit(table,path,seen):
            nonlocal steps
            steps+=1
            if steps>10000:raise ValueError('Security relationship traversal limit exceeded.')
            if table==end:
                paths.append(path)
                if len(paths)>1:raise ValueError('Ambiguous security relationship paths; simplify the model or security direction.')
                return
            for edge in edges.get(table,[]):
                if edge[2] not in seen:visit(edge[2],path+[edge],seen|{edge[2]})
        visit(start,[],{start})
        return paths[0] if paths else None
