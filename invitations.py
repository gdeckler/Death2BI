"""Single-use report invitations and identity records, stored without raw link tokens."""
import hashlib
import secrets
import time
import uuid


def token_hash(token):
    if not isinstance(token, str) or not 32 <= len(token) <= 256:
        raise ValueError('Invalid invitation link.')
    return hashlib.sha256(token.encode()).hexdigest()


class InvitationAccounts:
    def init_invitations(self, db):
        db.executescript("""
            CREATE TABLE IF NOT EXISTS invitations (
                id TEXT PRIMARY KEY, report_id TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
                created_by TEXT NOT NULL, created_name TEXT NOT NULL, created_at REAL NOT NULL,
                expires_at REAL NOT NULL, used_at REAL, used_by TEXT, used_name TEXT,
                removed_at REAL, removed_by TEXT);
            CREATE TABLE IF NOT EXISTS federated_identities (
                issuer TEXT NOT NULL, subject TEXT NOT NULL, user_id TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL, display_name TEXT, email TEXT,
                PRIMARY KEY(issuer,subject), FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS oidc_flows (
                state_hash TEXT PRIMARY KEY, browser_hash TEXT NOT NULL, provider TEXT NOT NULL,
                nonce TEXT NOT NULL, verifier TEXT NOT NULL, invitation_hash TEXT,
                expires_at REAL NOT NULL);
        """)

    def new_invitation(self, report_id, actor, hours=168):
        self.report_access(report_id, actor, manage=True)
        if not isinstance(hours, int) or isinstance(hours, bool) or not 1 <= hours <= 720:
            raise ValueError('Choose an expiry from 1 to 720 hours.')
        raw, ident, now = secrets.token_urlsafe(32), uuid.uuid4().hex, time.time()
        with self.connect() as db:
            db.execute('INSERT INTO invitations(id,report_id,token_hash,created_by,created_name,created_at,expires_at) VALUES (?,?,?,?,?,?,?)', (ident,report_id,token_hash(raw),actor['id'],actor['username'],now,now+hours*3600))
        return {'id':ident,'token':raw,'expiresAt':now+hours*3600}

    def list_invitations(self, actor, report_id=None):
        if report_id:
            self.report_access(report_id,actor,manage=True)
        else:
            self.require_admin(actor)
        with self.connect() as db:
            rows=db.execute('SELECT * FROM invitations'+(' WHERE report_id=?' if report_id else '')+' ORDER BY created_at DESC', (report_id,) if report_id else ()).fetchall()
        return [{k:r[k] for k in r.keys() if k!='token_hash'} for r in rows]

    def remove_invitation(self, ident, actor):
        with self.connect() as db:
            row=db.execute('SELECT * FROM invitations WHERE id=?',(ident,)).fetchone()
        if row is None:
            raise ValueError('Invitation not found.')
        self.report_access(row['report_id'],actor,manage=True)
        with self.connect() as db:
            db.execute('UPDATE invitations SET removed_at=COALESCE(removed_at,?),removed_by=COALESCE(removed_by,?) WHERE id=?',(time.time(),actor['id'],ident))

    @staticmethod
    def invitation_row(db, digest):
        row=db.execute('SELECT * FROM invitations WHERE token_hash=?',(digest,)).fetchone()
        if row is None or row['used_at'] is not None or row['removed_at'] is not None or row['expires_at'] <= time.time():
            raise ValueError('This invitation is invalid, expired, removed or already used.')
        return row

    def preview_invitation(self, raw):
        with self.connect() as db:
            row=self.invitation_row(db,token_hash(raw))
            return {'reportId':row['report_id'],'expiresAt':row['expires_at']}

    @staticmethod
    def consume_invitation(db, digest, user):
        row=InvitationAccounts.invitation_row(db,digest)
        count=db.execute('UPDATE invitations SET used_at=?,used_by=?,used_name=? WHERE id=? AND used_at IS NULL AND removed_at IS NULL',(time.time(),user['id'],user['username'],row['id'])).rowcount
        if count!=1:
            raise ValueError('This invitation has already been used.')
        db.execute('INSERT OR IGNORE INTO report_shares VALUES (?,?)',(row['report_id'],user['id']))
        return row['report_id']

    def redeem_invitation(self, raw, actor):
        actor=self.user(actor['id'])
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            return self.consume_invitation(db,token_hash(raw),actor)

    def federated_login(self, provider, claims, invitation_digest=None):
        # Match the immutable issuer/subject pair; never merge users by email or username.
        issuer,subject=claims['iss'],claims['sub']
        with self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if invitation_digest:
                self.invitation_row(db,invitation_digest)
            identity=db.execute('SELECT user_id FROM federated_identities WHERE issuer=? AND subject=?',(issuer,subject)).fetchone()
            if identity:
                row=db.execute('SELECT * FROM users WHERE id=?',(identity['user_id'],)).fetchone()
            else:
                if not invitation_digest:
                    raise ValueError('A report invitation is required for your first federated sign-in.')
                ident=uuid.uuid4().hex
                username=provider+'_'+ident[:20]
                # No usable password exists for a federated stub.
                db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)',(ident,username,'','',0,time.time()))
                db.execute('INSERT INTO federated_identities VALUES (?,?,?,?,?,?)',(issuer,subject,ident,provider,str(claims.get('name',''))[:256],str(claims.get('email',''))[:320]))
                row=db.execute('SELECT * FROM users WHERE id=?',(ident,)).fetchone()
            user={'id':row['id'],'username':row['username']}
            report_id=self.consume_invitation(db,invitation_digest,user) if invitation_digest else None
            token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
            db.execute('INSERT INTO sessions VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],csrf,time.time()+8*3600))
        return token,report_id

    def federated_identity(self, ident):
        with self.connect() as db:
            row=db.execute('SELECT provider,display_name,email FROM federated_identities WHERE user_id=?',(ident,)).fetchone()
        return dict(row) if row else None
