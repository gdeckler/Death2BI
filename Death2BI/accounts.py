"""Local accounts, scrypt password hashes, revocable sessions and object ownership."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from invitations import InvitationAccounts
from workspaces import WorkspaceAccounts
from groups import GroupAccounts

DEFAULT_PASSWORD = 'Death2PowerBI!'
SESSION_SECONDS = 8 * 60 * 60


class AuthError(Exception):
    def __init__(self, message, status=401):
        super().__init__(message)
        self.status = status


def password_hash(password, salt=None):
    if not isinstance(password, str) or not 8 <= len(password) <= 256:
        raise ValueError('Passwords must contain between 8 and 256 characters.')
    salt = secrets.token_bytes(16) if salt is None else bytes.fromhex(salt)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=1, dklen=32)
    return salt.hex(), digest.hex()


def verify_password(password, user):
    if not isinstance(password, str) or not 8 <= len(password) <= 256:
        return False
    _, digest = password_hash(password, user['salt'])
    return hmac.compare_digest(digest, user['password_hash'])


class Accounts(GroupAccounts, WorkspaceAccounts, InvitationAccounts):
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.failures = {}
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    salt TEXT NOT NULL, password_hash TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    csrf TEXT NOT NULL, expires REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS report_owners (report_id TEXT PRIMARY KEY, user_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reading_positions (
                    user_id TEXT PRIMARY KEY, report_id TEXT NOT NULL,
                    page_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS package_access (
                    package_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    PRIMARY KEY(package_id,user_id));
                CREATE TABLE IF NOT EXISTS report_shares (
                    report_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    PRIMARY KEY(report_id,user_id),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS report_packages (
                    report_id TEXT NOT NULL, package_id TEXT NOT NULL,
                    PRIMARY KEY(report_id,package_id));
            ''')
            self.init_invitations(db)
            self.init_workspaces(db)
            self.init_groups(db)
            from rls import initialize
            initialize(db)
            from public_links import initialize as initialize_public_links
            initialize_public_links(db)
            admin = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()
            if admin is None:
                # Only a new store is bootstrapped. Never silently recreate/reset a missing admin.
                if db.execute('SELECT count(*) FROM users').fetchone()[0]:
                    raise RuntimeError('Account store is missing its protected admin account.')
                salt, digest = password_hash(DEFAULT_PASSWORD)
                self.admin_id = uuid.uuid4().hex
                db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)', (self.admin_id, 'admin', salt, digest, 1, time.time()))
            else:
                self.admin_id = admin['id']
        self.dummy = dict(zip(('salt', 'password_hash'), password_hash(secrets.token_urlsafe(24))))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def reading_position(self, actor, position=None):
        if position is not None:
            if not isinstance(position,dict) or any(not isinstance(position.get(k),str) or len(position[k])>160 for k in ('reportId','pageId','workspaceId')):
                raise ValueError('Invalid reading position.')
            if position['reportId']!='demo':self.report_access(position['reportId'],actor)
        with self.lock,self.connect() as db:
            if position is not None:
                self._workspace(db,actor,position['workspaceId'])
                db.execute('INSERT INTO reading_positions VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET report_id=excluded.report_id,page_id=excluded.page_id,workspace_id=excluded.workspace_id',
                    (actor['id'],position['reportId'],position['pageId'],position['workspaceId']))
            row=db.execute('SELECT report_id,page_id,workspace_id FROM reading_positions WHERE user_id=?',(actor['id'],)).fetchone()
            return dict(zip(('reportId','pageId','workspaceId'),row)) if row else {}

    def public(self, row):
        return {'identity': self.federated_identity(row['id']), 'id': row['id'], 'username': row['username'], 'isAdmin': bool(row['is_admin']), 'createdAt': row['created_at']}

    def user(self, ident):
        if isinstance(ident,str) and ident.startswith('public:'):
            from public_links import PublicLinks
            return PublicLinks(self).actor(ident)
        with self.connect() as db:
            user = db.execute('SELECT * FROM users WHERE id=?', (ident,)).fetchone()
        if user is None:
            raise AuthError('Please sign in.')
        return self.public(user)

    def require_admin(self, actor):
        actor = self.user(actor['id'])
        if not actor['isAdmin']:
            raise AuthError('Administrator access is required.', 403)
        return actor

    def login(self, username, password, address='local'):
        username = username.strip() if isinstance(username, str) else ''
        if len(username) > 64:
            raise AuthError('Invalid username or password.')
        key = (address, username.casefold())
        with self.lock:
            now = time.time()
            count, until = self.failures.get(key, (0, 0))
            if until > now and count >= 8:
                raise AuthError('Too many sign-in attempts. Try again in one minute.', 429)
            with self.connect() as db:
                row = db.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE', (username,)).fetchone()
                valid = verify_password(password, row if row is not None and row['salt'] else self.dummy) and bool(row is not None and row['salt'])
                if row is None or not valid:
                    if len(self.failures) > 1024:
                        self.failures = {k: v for k, v in self.failures.items() if v[1] > now}
                    self.failures[key] = (count + 1 if until > now else 1, now + 60)
                    raise AuthError('Invalid username or password.')
                self.failures.pop(key, None)
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                db.execute('DELETE FROM sessions WHERE expires<=?', (now,))
                db.execute('INSERT INTO sessions VALUES (?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['id'], csrf, now + SESSION_SECONDS))
                return {'user': self.public(row), 'csrf': csrf}, token

    def session(self, token):
        if not token or len(token) > 128:
            raise AuthError('Please sign in.')
        with self.connect() as db:
            row = db.execute('SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        if row is None:
            raise AuthError('Your session has expired. Please sign in again.')
        return {'user': self.public(row), 'csrf': row['csrf']}

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def create(self, actor, username, password, is_admin=False):
        self.require_admin(actor)
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', username):
            raise ValueError('Use a username of 1–64 letters, numbers, dots, underscores or hyphens.')
        if not isinstance(is_admin, bool):
            raise ValueError('isAdmin must be true or false.')
        salt, digest = password_hash(password)
        ident = uuid.uuid4().hex
        try:
            with self.connect() as db:
                db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)', (ident, username, salt, digest, int(is_admin), time.time()))
        except sqlite3.IntegrityError:
            raise ValueError('That username already exists.')
        return self.user(ident)

    def list_users(self, actor):
        self.require_admin(actor)
        with self.connect() as db:
            return [self.public(row) for row in db.execute('SELECT * FROM users ORDER BY username COLLATE NOCASE')]

    def change_password(self, actor, current, new):
        if self.federated_identity(actor['id']):
            raise ValueError('Manage this password at your identity provider.')
        with self.lock, self.connect() as db:
            row = db.execute('SELECT * FROM users WHERE id=?', (actor['id'],)).fetchone()
            if row is None or not verify_password(current, row):
                raise AuthError('The current password is incorrect.', 403)
            salt, digest = password_hash(new)
            db.execute('UPDATE users SET salt=?,password_hash=? WHERE id=?', (salt, digest, actor['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?', (actor['id'],))

    def reset_password(self, actor, ident, password):
        self.require_admin(actor)
        self.user(ident)
        if self.federated_identity(ident):
            raise ValueError('Federated accounts do not have local passwords.')
        salt, digest = password_hash(password)
        with self.lock, self.connect() as db:
            db.execute('UPDATE users SET salt=?,password_hash=? WHERE id=?', (salt, digest, ident))
            db.execute('DELETE FROM sessions WHERE user_id=?', (ident,))

    def delete(self, actor, ident, confirm):
        self.require_admin(actor)
        target = self.user(ident)
        if ident in (self.admin_id, actor['id']):
            raise ValueError('The default admin and your own account cannot be deleted.')
        if confirm != target['username']:
            raise ValueError('Type the exact username to confirm account deletion.')
        with self.lock, self.connect() as db:
            db.execute('UPDATE report_owners SET user_id=? WHERE user_id=?', (self.admin_id, ident))
            db.execute('DELETE FROM package_access WHERE user_id=?', (ident,))
            db.execute('DELETE FROM users WHERE id=?', (ident,))
        return target

    def report_owner(self, report_id):
        with self.connect() as db:
            row = db.execute('SELECT user_id FROM report_owners WHERE report_id=?', (report_id,)).fetchone()
        return row[0] if row else self.admin_id

    def own_report(self, report_id, actor):
        self.user(actor['id'])
        with self.connect() as db:
            db.execute('INSERT INTO report_owners VALUES (?,?)', (report_id, actor['id']))

    def can_read_report(self, report_id, actor):
        if actor.get('publicLink'):return self.user(actor['id'])['publicReport']==report_id
        if actor['isAdmin'] or self.report_owner(report_id) == actor['id']:
            return True
        with self.connect() as db:
            return db.execute('SELECT 1 FROM report_shares WHERE report_id=? AND user_id=? UNION ALL SELECT 1 FROM report_group_shares s JOIN group_members m ON m.group_id=s.group_id WHERE s.report_id=? AND m.user_id=?', (report_id, actor['id'], report_id, actor['id'])).fetchone() is not None

    def report_access(self, report_id, actor, manage=False):
        actor = self.user(actor['id'])
        if actor.get('publicLink'):
            if manage or actor['publicReport']!=report_id:raise AuthError('Report not found.',404)
            return
        if not re.fullmatch('[a-f0-9]{32}', report_id):
            raise ValueError('Invalid model ID')
        allowed = (actor['isAdmin'] or self.report_owner(report_id) == actor['id']) if manage else self.can_read_report(report_id, actor)
        if not allowed:
            raise AuthError('Report not found.', 404)

    def sharing(self, report_id, actor):
        self.report_access(report_id, actor, manage=True)
        owner = self.report_owner(report_id)
        with self.connect() as db:
            shared = {r[0] for r in db.execute('SELECT user_id FROM report_shares WHERE report_id=?', (report_id,))}
            return [{'id': r['id'], 'username': r['username'], 'shared': r['id'] in shared} for r in db.execute('SELECT id,username,is_admin FROM users ORDER BY username COLLATE NOCASE') if r['id'] != owner and not r['is_admin']]

    def set_sharing(self, report_id, actor, users, groups=None):
        self.report_access(report_id, actor, manage=True)
        if not isinstance(users, list) or len(users) > 1000 or any(not isinstance(u, str) for u in users):
            raise ValueError('Choose a list of account IDs.')
        valid = {u['id'] for u in self.sharing(report_id, actor)}
        if set(users) - valid:
            raise ValueError('One or more selected accounts are unavailable.')
        if groups is not None and (not isinstance(groups,list) or len(groups)>1000 or any(not isinstance(g,str) for g in groups)):
            raise ValueError('Choose a list of group IDs.')
        with self.lock, self.connect() as db:
            if groups is not None:
                valid_groups={r[0] for r in db.execute('SELECT id FROM local_groups')}
                if set(groups)-valid_groups: raise ValueError('One or more selected groups are unavailable.')
                db.execute('DELETE FROM report_group_shares WHERE report_id=?',(report_id,))
                db.executemany('INSERT INTO report_group_shares VALUES (?,?)',[(report_id,g) for g in set(groups)])
            db.execute('DELETE FROM report_shares WHERE report_id=?', (report_id,))
            db.executemany('INSERT INTO report_shares VALUES (?,?)', [(report_id, u) for u in set(users)])

    def register_report_packages(self, report_id, packages):
        with self.connect() as db:
            db.execute('DELETE FROM report_packages WHERE report_id=?', (report_id,))
            db.executemany('INSERT OR IGNORE INTO report_packages VALUES (?,?)', [(report_id, p['id']) for p in packages])

    def forget_report(self, report_id):
        with self.connect() as db:
            db.execute('DELETE FROM report_rls WHERE report_id=?', (report_id,))
            db.execute('DELETE FROM report_group_shares WHERE report_id=?', (report_id,))
            db.execute('DELETE FROM workspace_reports WHERE report_id=?', (report_id,))
            db.execute('DELETE FROM report_owners WHERE report_id=?', (report_id,))
            db.execute('UPDATE invitations SET removed_at=COALESCE(removed_at,?) WHERE report_id=?', (time.time(), report_id))
            db.execute('UPDATE public_report_links SET removed_at=COALESCE(removed_at,?) WHERE report_id=?', (time.time(), report_id))
            db.execute('DELETE FROM report_shares WHERE report_id=?', (report_id,))
            db.execute('DELETE FROM report_packages WHERE report_id=?', (report_id,))

    def grant_packages(self, packages, actor):
        with self.connect() as db:
            db.executemany('INSERT OR IGNORE INTO package_access VALUES (?,?)', [(p['id'], actor['id']) for p in packages])

    def package_access(self, ident, actor):
        actor = self.user(actor['id'])
        if actor.get('publicLink'):
            with self.connect() as db:return db.execute('SELECT 1 FROM report_packages WHERE report_id=? AND package_id=?',(actor['publicReport'],ident)).fetchone() is not None
        if actor['isAdmin']:
            return True
        with self.connect() as db:
            return db.execute('SELECT 1 FROM package_access WHERE package_id=? AND user_id=? UNION ALL SELECT 1 FROM report_packages p JOIN report_shares s ON s.report_id=p.report_id WHERE p.package_id=? AND s.user_id=? UNION ALL SELECT 1 FROM report_packages p JOIN report_group_shares s ON s.report_id=p.report_id JOIN group_members m ON m.group_id=s.group_id WHERE p.package_id=? AND m.user_id=?', (ident, actor['id'], ident, actor['id'], ident, actor['id'])).fetchone() is not None
