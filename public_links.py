"""Revocable, hashed bearer links scoped to one public, read-only report."""
import hashlib
import re
import secrets
import time
import uuid


def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS public_report_links(
        id TEXT PRIMARY KEY,report_id TEXT NOT NULL,token_hash TEXT NOT NULL UNIQUE,
        created_by TEXT NOT NULL,created_name TEXT NOT NULL,created_at REAL NOT NULL,
        expires_at REAL,removed_at REAL,visits INTEGER NOT NULL DEFAULT 0,last_seen_at REAL);
        CREATE INDEX IF NOT EXISTS public_links_report ON public_report_links(report_id);''')


class PublicLinks:
    def __init__(self,store):self.store=store

    def create(self,ident,actor,hours=0):
        self.store.report_access(ident,actor,manage=True)
        if isinstance(hours,bool) or hours not in (0,24,168,720):raise ValueError('Choose no expiry, 1 day, 7 days or 30 days.')
        from rls import RLS
        if RLS(self.store).config(ident)['enabled']:raise ValueError('Reports with row-level security cannot be shared through a public link.')
        token=secrets.token_urlsafe(32);ident_link=uuid.uuid4().hex;now=time.time()
        with self.store.connect() as db:
            db.execute('INSERT INTO public_report_links(id,report_id,token_hash,created_by,created_name,created_at,expires_at) VALUES(?,?,?,?,?,?,?)',
                (ident_link,ident,hashlib.sha256(token.encode()).hexdigest(),actor['id'],actor['username'],now,now+hours*3600 if hours else None))
        return {'id':ident_link,'token':token}

    def list(self,actor,ident=None):
        if ident:self.store.report_access(ident,actor,manage=True)
        else:self.store.require_admin(actor)
        with self.store.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,report_id,created_by,created_name,created_at,expires_at,removed_at,visits,last_seen_at FROM public_report_links'+(' WHERE report_id=?' if ident else '')+' ORDER BY created_at DESC',(ident,) if ident else ())]

    def remove(self,link,actor):
        from accounts import AuthError
        with self.store.connect() as db:row=db.execute('SELECT report_id FROM public_report_links WHERE id=?',(link,)).fetchone()
        if not row:raise AuthError('Public link not found.',404)
        self.store.report_access(row['report_id'],actor,manage=True)
        with self.store.connect() as db:db.execute('UPDATE public_report_links SET removed_at=COALESCE(removed_at,?) WHERE id=?',(time.time(),link))
        return {'removed':link}

    def resolve(self,token,visit=False):
        from accounts import AuthError
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise AuthError('Public link is unavailable.',404)
        digest=hashlib.sha256(token.encode()).hexdigest()
        with self.store.connect() as db:row=db.execute('SELECT id FROM public_report_links WHERE token_hash=?',(digest,)).fetchone()
        if not row:raise AuthError('Public link is unavailable.',404)
        actor=self.actor('public:'+row['id'])
        if visit:
            with self.store.connect() as db:db.execute('UPDATE public_report_links SET visits=visits+1,last_seen_at=? WHERE id=?',(time.time(),row['id']))
        return actor

    def actor(self,ident):
        from accounts import AuthError
        from rls import RLS
        with self.store.connect() as db:row=db.execute('SELECT * FROM public_report_links WHERE id=?',(ident.removeprefix('public:'),)).fetchone()
        if not row or row['removed_at'] or row['expires_at'] is not None and row['expires_at']<=time.time():raise AuthError('Public link is unavailable.',404)
        if RLS(self.store).config(row['report_id'])['enabled']:raise AuthError('Public access is unavailable for this report.',403)
        return {'id':ident,'username':'Public viewer','isAdmin':False,'publicLink':row['id'],'publicReport':row['report_id'],'identity':None}


def allowed(method,path,actor):
    """A public bearer never authorizes management, exports or account endpoints."""
    from urllib.parse import urlsplit,parse_qs
    parsed=urlsplit(path);p=parsed.path;ident=actor['publicReport']
    if method=='GET':
        if p in ('/api/auth/me','/api/models','/api/builtin-visuals','/api/custom-visuals'):return True
        if p=='/api/security-context':return parse_qs(parsed.query).get('id')==[ident]
        if p in ('/api/models/'+ident,'/api/html/'+ident):return True
        return bool(re.fullmatch('/api/custom-visuals/[a-f0-9]{32}',p))
    return method=='POST' and p in ('/api/query','/api/query/cancel','/api/dax','/api/dax/cancel')
